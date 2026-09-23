"""Encrypted user workspaces in AVANAgent; every retrieval checks current visibility."""

import hashlib
import json
import secrets
from datetime import datetime, timezone
from . import agent_storage


class RevisionConflict(Exception):
    pass


def user_key(kind, scope, actor):
    identity = json.dumps([str(scope["tenant_id"]), actor], ensure_ascii=False)
    return kind + ":" + hashlib.sha256(identity.encode()).hexdigest()


def scope_stamp(scope):
    value = [scope["pm_uid"], scope["role"], sorted(scope.get("visible_uids", []))]
    return hashlib.sha256(json.dumps(value).encode()).hexdigest()


def visible(turn, scope, meeting_ids):
    return (
        turn["scope"] == scope_stamp(scope)
        and set(turn["meeting_ids"]) <= set(meeting_ids)
        and set(turn["modules"]) <= set(scope["license"]["modules"])
    )


def conversations(scope, actor, meeting_ids):
    with agent_storage.transaction() as tx:
        rows = tx.get(user_key("conversations", scope, actor), [])
    # Hide the entire conversation if any retained answer is outside current scope.
    return [c for c in rows if all(visible(t, scope, meeting_ids) for t in c["turns"])]


def conversation(scope, actor, identifier, meeting_ids):
    rows = conversations(scope, actor, meeting_ids)
    row = next((r for r in rows if r["id"] == identifier), None)
    if not row:
        raise PermissionError("Conversation unavailable")
    return row


def save_turn(scope, actor, identifier, question, answer, meeting_ids):
    key = user_key("conversations", scope, actor)
    with agent_storage.transaction() as tx:
        rows = tx.get(key, [], lock=True)
        row = (
            next((r for r in rows if r["id"] == identifier), None)
            if identifier
            else None
        )
        if identifier and (
            not row or not all(visible(t, scope, meeting_ids) for t in row["turns"])
        ):
            raise PermissionError("Conversation unavailable")
        if row is None:
            row = {
                "id": secrets.token_urlsafe(24),
                "title": question[:120],
                "turns": [],
            }
            rows.insert(0, row)
        turn = {
            "id": secrets.token_urlsafe(18),
            "question": question,
            "answer": answer,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "scope": scope_stamp(scope),
            "meeting_ids": sorted(meeting_ids),
            "modules": sorted(scope["license"]["modules"]),
        }
        row["turns"].append(turn)
        row["turns"] = row["turns"][-20:]
        # Bound persistent personal history independently of tool output limits.
        while len(row["turns"]) > 1 and len(json.dumps(row).encode()) > 1_000_000:
            row["turns"].pop(0)
        row["updated_at"] = turn["created_at"]
        rows = [row] + [r for r in rows if r["id"] != row["id"]]
        tx.put(key, rows[:30])
        return row["id"], turn["id"]


def delete_conversation(scope, actor, identifier):
    key = user_key("conversations", scope, actor)
    with agent_storage.transaction() as tx:
        rows = tx.get(key, [], lock=True)
        tx.put(key, [r for r in rows if r["id"] != identifier])
        tx.audit(scope["tenant_id"], actor, "CONVERSATION_DELETED", {})


def public_conversation(row):
    return {k: v for k, v in row.items() if k != "turns"} | {
        "turns": [
            {k: v for k, v in t.items() if k not in ("scope", "meeting_ids", "modules")}
            for t in row["turns"]
        ]
    }
