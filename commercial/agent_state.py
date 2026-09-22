"""Agent-owned encrypted SQL Server drafts, monitoring baselines and audit metadata."""

from datetime import datetime, timezone
from collections import Counter
import secrets
from . import agent_storage
from .agent_tools import source, instant


def audit(scope, actor, event, detail, con=None):
    safe = {
        k: v
        for k, v in detail.items()
        if k
        in (
            "model",
            "tools",
            "input_tokens",
            "output_tokens",
            "draft_id",
            "status",
            "question_hash",
            "coverage_complete",
            "error_code",
        )
    }
    if con is not None:
        con.audit(scope["tenant_id"], actor, event, safe)
    else:
        with agent_storage.transaction() as tx:
            tx.audit(scope["tenant_id"], actor, event, safe)


def observe(scope, actor, meetings, now, complete):
    name = "monitor:" + scope["tenant_id"] + ":" + actor
    observations = {}
    with agent_storage.transaction() as tx:
        old = tx.get(name, {}, lock=True)
        saved = dict(old) if not complete else {}
        for m in meetings:
            for a in m.get("actions", []):
                key = source(m, a)["id"]
                before = old.get(key)
                value = a.get("progress_percent")
                changed = (
                    before["changed_at"]
                    if before and before.get("progress") == value
                    else now.isoformat()
                )
                observations[key] = {
                    "progress": value,
                    "changed_at": changed,
                    "last_seen": now.isoformat(),
                }
                saved[key] = observations[key]
        previous = old.get("__backlog")
        if complete:
            counts = dict(
                Counter(
                    a.get("owner_unit") or "واحد ثبت نشده"
                    for m in meetings
                    for a in m.get("actions", [])
                    if not a.get("is_closed")
                )
            )
            if not previous or not previous.get("complete"):
                previous = {"counts": counts, "at": now.isoformat(), "complete": True}
            observations["__backlog"] = previous
            saved["__backlog"] = (
                {"counts": counts, "at": now.isoformat(), "complete": True}
                if (now - instant(previous["at"])).total_seconds() >= 86400
                else previous
            )
        tx.put(name, saved)
    return observations


def save_draft(scope, actor, meeting_id, payload):
    identifier = secrets.token_urlsafe(24)
    with agent_storage.transaction() as tx:
        tx.put(
            "draft:" + identifier,
            {
                "id": identifier,
                "tenant": scope["tenant_id"],
                "actor": actor,
                "meeting_id": meeting_id,
                "payload": payload,
                "status": "draft",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "approved_at": None,
            },
        )
        audit(scope, actor, "SECRETARY_DRAFT_CREATED", {"draft_id": identifier}, tx)
    return identifier


def _allowed(row, scope, actor, allowed):
    if (
        not row
        or row["tenant"] != scope["tenant_id"]
        or row["actor"] != actor
        or row["meeting_id"] not in allowed
    ):
        raise PermissionError("Draft unavailable")
    return {k: v for k, v in row.items() if k not in ("tenant", "actor")}


def get_draft(scope, actor, identifier, allowed_meetings):
    with agent_storage.transaction() as tx:
        row = tx.get("draft:" + identifier)
    return _allowed(row, scope, actor, allowed_meetings)


def approve_draft(scope, actor, identifier, allowed_meetings):
    with agent_storage.transaction() as tx:
        row = tx.get("draft:" + identifier, lock=True)
        _allowed(row, scope, actor, allowed_meetings)
        if row["status"] == "draft":
            row["status"] = "approved"
            row["approved_at"] = datetime.now(timezone.utc).isoformat()
            tx.put("draft:" + identifier, row)
            audit(
                scope, actor, "SECRETARY_DRAFT_APPROVED", {"draft_id": identifier}, tx
            )
    return _allowed(row, scope, actor, allowed_meetings)
