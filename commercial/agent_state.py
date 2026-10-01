"""Agent-owned encrypted SQL Server drafts, monitoring baselines and audit metadata."""

from datetime import datetime, timezone
from collections import Counter
import secrets
from . import agent_storage
from .agent_workspace import source_user_key, scope_stamp, RevisionConflict
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
    name = source_user_key("monitor_observations", scope, actor)
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
                "scope": scope_stamp(scope),
                "meeting_id": meeting_id,
                "payload": payload,
                "status": "draft",
                "revision": 1,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "approved_at": None,
            },
        )
        index_key = source_user_key('drafts', scope, actor)
        index = tx.get(index_key, [], lock=True)
        tx.put(index_key, ([identifier] + index)[:200])
        audit(scope, actor, "SECRETARY_DRAFT_CREATED", {"draft_id": identifier}, tx)
    return identifier


def _allowed(row, scope, actor, allowed):
    if (
        not row
        or row["tenant"] != scope["tenant_id"]
        or row["actor"] != actor
        or row.get("scope") != scope_stamp(scope)
        or row["meeting_id"] not in allowed
    ):
        raise PermissionError("Draft unavailable")
    return {k: v for k, v in row.items() if k not in ("tenant", "actor")}


def get_draft(scope, actor, identifier, allowed_meetings):
    with agent_storage.transaction() as tx:
        row = tx.get("draft:" + identifier)
    return _allowed(row, scope, actor, allowed_meetings)


def approve_draft(scope, actor, identifier, allowed_meetings, revision=None):
    with agent_storage.transaction() as tx:
        row = tx.get("draft:" + identifier, lock=True)
        _allowed(row, scope, actor, allowed_meetings)
        if revision is not None and revision != row.get('revision', 1):
            raise RevisionConflict('Draft changed; reload before approval')
        if row["status"] == "draft":
            row["status"] = "approved"
            row["approved_at"] = datetime.now(timezone.utc).isoformat()
            tx.put("draft:" + identifier, row)
            audit(
                scope, actor, "SECRETARY_DRAFT_APPROVED", {"draft_id": identifier}, tx
            )
    return _allowed(row, scope, actor, allowed_meetings)


def list_drafts(scope, actor, allowed_meetings):
    with agent_storage.transaction() as tx:
        ids = tx.get(source_user_key('drafts', scope, actor), [])
        result = []
        for identifier in ids:
            row = tx.get('draft:' + identifier)
            try:
                data = _allowed(row, scope, actor, allowed_meetings)
            except PermissionError:
                continue
            result.append({k: data[k] for k in ('id', 'meeting_id', 'status', 'created_at')}
                          | {'meeting_no': data['payload'].get('meeting_no', ''),
                             'summary': data['payload'].get('summary', '')[:160],
                             'revision': data.get('revision', 1)})
        return result


def update_draft(scope, actor, identifier, allowed_meetings, payload, revision):
    with agent_storage.transaction() as tx:
        row = tx.get('draft:' + identifier, lock=True)
        _allowed(row, scope, actor, allowed_meetings)
        if row.get('revision', 1) != revision or row['status'] != 'draft':
            raise RevisionConflict('Approved or changed draft cannot be overwritten')
        row['payload'] = payload
        row['revision'] = revision + 1
        row['updated_at'] = datetime.now(timezone.utc).isoformat()
        tx.put('draft:' + identifier, row)
        audit(scope, actor, 'SECRETARY_DRAFT_EDITED', {'draft_id': identifier}, tx)
        return _allowed(row, scope, actor, allowed_meetings)


def alert_id(alert):
    import hashlib
    return hashlib.sha256((alert['kind'] + ':' + alert['source']['id']).encode()).hexdigest()[:32]


def alert_status(scope, actor, result):
    key = source_user_key('alert_status', scope, actor)
    with agent_storage.transaction() as tx:
        data = tx.get(key, {}, lock=True)
        now = datetime.now(timezone.utc).isoformat()
        for alert in result['alerts']:
            identifier = alert_id(alert)
            item = data.get(identifier) or {'first_seen': now, 'acknowledged': False}
            item['last_seen'] = now
            data[identifier] = item
            alert.update({'id': identifier, **item})
        # Retain recent acknowledgements across omitted/truncated result pages.
        data = dict(sorted(data.items(), key=lambda pair: pair[1]['last_seen'], reverse=True)[:5000])
        tx.put(key, data)
    return result


def acknowledge(scope, actor, identifier):
    key = user_key('alert_status', scope, actor)
    with agent_storage.transaction() as tx:
        data = tx.get(key, {}, lock=True)
        if identifier not in data:
            raise PermissionError('Alert unavailable')
        data[identifier]['acknowledged'] = True
        data[identifier]['acknowledged_at'] = datetime.now(timezone.utc).isoformat()
        tx.put(key, data)
        audit(scope, actor, 'MONITOR_ALERT_ACKNOWLEDGED', {'status': 'acknowledged'}, tx)


def reopen_draft(scope, actor, identifier, allowed_meetings, revision):
    with agent_storage.transaction() as tx:
        row = tx.get('draft:' + identifier, lock=True)
        _allowed(row, scope, actor, allowed_meetings)
        if row.get('revision', 1) != revision:
            raise RevisionConflict('Draft changed')
        if row['status'] == 'approved':
            row.update({'status': 'draft', 'approved_at': None, 'revision': revision + 1})
            tx.put('draft:' + identifier, row)
            audit(scope, actor, 'SECRETARY_DRAFT_REOPENED', {'draft_id': identifier}, tx)
        return _allowed(row, scope, actor, allowed_meetings)
