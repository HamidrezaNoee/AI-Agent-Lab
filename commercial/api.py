"""Private commercial gateway FOUNDATION; not yet a customer-facing AI chat service.

OIDC access token -> verified tenant principal -> SQL membership/subscription
-> per-connection SQL RLS tenant context -> tenant-scoped meeting index.
No legacy MTG/AI lab tables or raw SQL endpoints are exposed.
"""
from functools import lru_cache
from typing import Annotated
import os
import uuid

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from .modules import OPTIONAL_MODULES, modules_snapshot, require_module, set_module_enabled

from .answer import MODEL, AnswerUnreliable, build_answer
from .quota import (
    ChatAccessDenied, QuotaExceeded, QuotaUnavailable,
    reserve_request, finalize_request,
)
from .security import (
    AuthenticationFailed, ConfigurationFailed, Principal,
    VerifiedTokenAuthenticator,
)
from .sql_store import (
    AccessDenied, StoreUnavailable, authorization_snapshot,
    scoped_connection, visible_meetings, visible_meetings_page, authorized_documents,
    authorized_evidence,
)

app = FastAPI(
    title="Commercial Agent — security foundation (LAB ONLY)",
    version="0.1.0",
    docs_url=None, redoc_url=None, openapi_url=None,
)


@app.middleware("http")
async def quarantine_legacy_content(request, call_next):
    """Keep old fixture-grant-only routes off a hierarchy-based deployment.

    An Expert could otherwise use an old /v1 report/chat URL to bypass the
    newer ProcessMaker participant/subtree checks. v1 identity/module catalog
    remain for the transitional UI, but ALL content goes through /v2.
    """
    path = request.url.path
    allowed = path in {"/v1/me", "/v1/modules"}
    allowed = allowed or path.startswith("/v1/admin/modules/")
    if (os.getenv("COMMERCIAL_V2_ONLY", "0") == "1"
            and path.startswith("/v1/") and not allowed):
        return JSONResponse(
            status_code=410,
            content={"detail": "Legacy meeting/document endpoint retired; use authorized /v2"},
            headers={"Cache-Control": "no-store"},
        )
    return await call_next(request)


@lru_cache(maxsize=1)
def _verifier() -> VerifiedTokenAuthenticator:
    return VerifiedTokenAuthenticator.from_environment()


def _authenticated_principal(
    authorization: Annotated[str | None, Header()] = None,
) -> Principal:
    try:
        return _verifier().authenticate(authorization)
    except ConfigurationFailed:
        raise HTTPException(status_code=503, detail="Identity provider not configured")
    except AuthenticationFailed:
        raise HTTPException(
            status_code=401, detail="Unauthorized",
            headers={"WWW-Authenticate": "Bearer"},
        )


PrincipalDep = Annotated[Principal, Depends(_authenticated_principal)]


def _query(principal: Principal, action):
    try:
        with scoped_connection(principal) as con:
            membership = authorization_snapshot(con, principal)
            result = action(con, principal)
            return membership, result
    except AccessDenied:
        raise HTTPException(status_code=403, detail="Tenant access denied")
    except StoreUnavailable:
        raise HTTPException(status_code=503, detail="Commercial lab store not configured")


@app.get("/health")
def health():
    """Process health only; does not claim database or agent readiness."""
    return {"status": "up", "mode": "commercial-security-lab"}


@app.get("/v1/me")
def whoami(principal: PrincipalDep):
    membership, _ = _query(principal, lambda con, p: None)
    return {
        "tenant_id": str(principal.tenant_id),
        "subject": principal.subject,
        "role": membership["role"],
        "plan": membership["plan"],
        "expires_at_utc": membership["expires_at_utc"],
        "quota_enforced": False,
        "data_scope": "synthetic-commercial-index-only",
    }


@app.get("/v1/meetings")
def list_meetings(principal: PrincipalDep):
    _, meetings = _query(principal, visible_meetings)
    return {
        "tenant_id": str(principal.tenant_id),
        "returned": len(meetings),
        "max_returned": 20,
        "meetings": meetings,
        "data_scope": "synthetic-commercial-index-only",
    }



@app.get("/v1/meetings/page")
def meeting_page(
    principal: PrincipalDep,
    cursor: int | None = Query(default=None, gt=0),
    limit: int = Query(default=20, ge=1, le=50),
):
    """All authorized meetings via bounded stable keyset pages, NOT unrestricted export."""
    # Historic /v1 remains grant-only for isolated regression; /v2 applies
    # the linked ProcessMaker user + organizational hierarchy rules.
    _, page = _query(principal, lambda con, p: visible_meetings_page(
        con, p, before_id=cursor, limit=limit
    ))
    return {
        "tenant_id": str(principal.tenant_id),
        **page,
        "data_scope": "synthetic-commercial-index-only",
    }


class ChatPreviewRequest(BaseModel):
    """No client-provided tenant ID, subject, SQL statement, tool name or ACL."""
    model_config = ConfigDict(extra="forbid")
    question: str = Field(min_length=3, max_length=350)
    meeting_id: int | None = Field(default=None, gt=0)


@app.get("/v1/knowledge/search")
def search_knowledge(
    principal: PrincipalDep,
    q: str = Query(min_length=3, max_length=350),
):
    _, matches = _query(
        principal, lambda con, p: authorized_documents(con, p, q, limit=5)
    )
    return {"tenant_id": str(principal.tenant_id), "matches": matches,
            "retrieval_method": "lexical (not semantic)",
            "source_policy": "fictional tenant-scoped test documents only"}


@app.post("/v1/chat/preview")
def chat_preview(body: ChatPreviewRequest, principal: PrincipalDep):
    """Return ONLY ACL-filtered, cited evidence; no external model API is called.

    A separate, quota-metered completion path must be added before AI chat
    is enabled. Never use the shared, unscoped legacy MTG/RAG tools here.
    """
    _, evidence = _query(
        principal,
        lambda con, p: authorized_evidence(
            con, p, body.question, meeting_id=body.meeting_id
        ),
    )
    return {
        "tenant_id": str(principal.tenant_id),
        "question": body.question,
        "requested_meeting_accessible": (
            None if body.meeting_id is None else
            any(item["kind"] == "meeting" for item in evidence)
        ),
        "evidence": evidence,
        "evidence_count": len(evidence),
        "answer": None,
        "completion_enabled": False,
        "note": "Evidence preview only: no LLM call, no unsupported answer."
    }


@app.post("/v1/chat/answer")
def chat_answer(body: ChatPreviewRequest, principal: PrincipalDep):
    """LAB ONLY: ACL evidence -> atomic request quota -> LLM -> final usage record.

    No raw model tools, no query-to-SQL, and no original unscoped MTG access.
    Disabled unless an operator explicitly enables the isolated test gateway.
    """
    if (os.getenv("COMMERCIAL_MODE") != "lab"
            or os.getenv("COMMERCIAL_SQL_DATABASE") != "EnterpriseProcess2_AI_Test"
            or os.getenv("COMMERCIAL_CHAT_ENABLED") != "1"
            or not os.getenv("OPENAI_API_KEY")):
        raise HTTPException(status_code=503, detail="Commercial lab chat is disabled")
    if not body.question.strip():
        raise HTTPException(status_code=422, detail="Question must contain text")

    request_id = uuid.uuid4()  # Server-generated, never accepted from client.
    try:
        with scoped_connection(principal) as con:
            authorization_snapshot(con, principal)
            evidence = authorized_evidence(
                con, principal, body.question, meeting_id=body.meeting_id
            )
            if (body.meeting_id is not None and
                    not any(item.get("kind") == "meeting" for item in evidence)):
                raise HTTPException(status_code=404, detail="Meeting not found")
            if not evidence:
                return {
                    "request_id": str(request_id), "answer": None, "claims": [],
                    "sources": [], "status": "no_authorized_evidence",
                    "charged_request": False, "completion_enabled": True,
                }
            reservation = reserve_request(con, principal, request_id, MODEL)
    except ChatAccessDenied:
        raise HTTPException(status_code=403, detail="Tenant access denied")
    except QuotaExceeded:
        raise HTTPException(status_code=429, detail="Monthly chat request quota exceeded")
    except (QuotaUnavailable, StoreUnavailable):
        raise HTTPException(status_code=503, detail="Commercial lab quota/store unavailable")
    except AccessDenied:
        raise HTTPException(status_code=403, detail="Tenant access denied")

    # SQL connection was closed before the external model request.
    result = None
    model_error = None
    try:
        result = build_answer(body.question, evidence)
    except Exception as exc:
        # A reservation still counts toward the monthly limit if the provider
        # fails: an external request may have incurred a charge.
        model_error = exc

    # Never return an unrecorded model response; fail closed on failed finalize.
    try:
        with scoped_connection(principal) as con:
            finalize_request(
                con, principal, request_id, completed=(model_error is None),
                input_tokens=(result.input_tokens if result is not None else None),
                output_tokens=(result.output_tokens if result is not None else None),
            )
    except (QuotaUnavailable, StoreUnavailable):
        raise HTTPException(status_code=503, detail="Chat usage finalization unavailable")
    if model_error is not None:
        raise HTTPException(status_code=502, detail="Model answer unavailable or ungrounded")

    return {
        "request_id": str(request_id),
        "answer": result.answer,
        "claims": result.claims,
        "sources": result.sources,
        "model": result.model,
        "usage": {
            "input_tokens": result.input_tokens,
            "output_tokens": result.output_tokens,
        },
        "quota": {
            "used_this_month": reservation.used_this_month,
            "monthly_limit": reservation.monthly_limit,
        },
        "status": "answered",
        "charged_request": True,
        "completion_enabled": True,
        "data_scope": "synthetic-authorized-commercial-evidence-only",
    }



# The catalog is public metadata ONLY; activation state is private tenant data.
# Every protected module endpoint checks JWT -> DB membership/subscription ->
# tenant-licensed AND enabled before querying ANY module-specific information.
@app.get("/v1/modules")
def list_modules(principal: PrincipalDep):
    _, values = _query(principal, modules_snapshot)
    return {"tenant_id": str(principal.tenant_id), "modules": values,
            "note": "Module 1 is core; optional modules require verified purchase and admin enablement."}


class ModuleSetting(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enabled: bool


@app.put("/v1/admin/modules/{module_code}")
def toggle_optional_module(module_code: int, body: ModuleSetting,
                           principal: PrincipalDep):
    if module_code not in OPTIONAL_MODULES:
        raise HTTPException(status_code=404, detail="Unknown optional module")
    try:
        with scoped_connection(principal) as con:
            membership = authorization_snapshot(con, principal)
            if membership["role"] not in ("Owner", "Admin"):
                raise HTTPException(status_code=403, detail="Tenant administrator required")
            current = next(m for m in modules_snapshot(con, principal)
                           if m["module_code"] == module_code)
            if not current["licensed"]:
                raise HTTPException(status_code=403, detail="Module license missing or expired")
            # SQL procedure repeats active tenant/member/license checks and writes AuditEvent.
            changed = set_module_enabled(con, principal, module_code, body.enabled)
            return {"tenant_id": str(principal.tenant_id), "module": changed,
                    "note": "Licensed module enabled/disabled; payment is not processed by this endpoint."}
    except (AccessDenied,):
        raise HTTPException(status_code=403, detail="Module activation not permitted")
    except StoreUnavailable:
        raise HTTPException(status_code=503, detail="Commercial lab store unavailable")


@app.get("/v1/secretary/preparation/{meeting_id}")
def secretary_preparation(meeting_id: int, principal: PrincipalDep):
    """Module 2: human-reviewable draft based on granted records, never auto-write."""
    if meeting_id <= 0:
        raise HTTPException(status_code=422, detail="Invalid meeting ID")
    def action(con, p):
        require_module(con, p, 2)
        from .sql_store import authorized_meeting
        meeting = authorized_meeting(con, p, meeting_id)
        if meeting is None:
            raise HTTPException(status_code=404, detail="Meeting not found")
        docs = authorized_documents(con, p, meeting["title"], limit=5, meeting_id=meeting_id)
        cur = con.cursor()
        cur.execute("""
            SELECT TOP (20) a.ActionNo,a.ActionTitle,a.OwnerUnit,
                   a.DueAtUtc,a.ProgressPercent,a.IsClosed
            FROM AgentProduct.ActionIndex a
            WHERE a.TenantID=? AND a.MeetingID=? AND
              EXISTS(SELECT 1 FROM AgentProduct.MeetingGrant g
                     WHERE g.TenantID=a.TenantID AND g.MeetingID=a.MeetingID
                       AND g.SubjectID=?)
            ORDER BY a.DueAtUtc,a.ActionNo
        """, str(p.tenant_id), meeting_id, p.subject)
        actions = [
            {"action_no": str(r[0]), "title": str(r[1]),
             "owner_unit": str(r[2]), "due_at_utc": str(r[3]),
             "progress_percent": int(r[4]), "is_closed": bool(r[5])}
            for r in cur.fetchall()
        ]
        open_items = [item for item in actions
                      if not item["is_closed"] and item["progress_percent"]<100]
        return {"meeting": meeting, "related_evidence": docs,
                "actions": actions,
                "draft_agenda": (
                    ["مرور اقدامات باز و علت تأخیر مربوط به این جلسه"] +
                    [f"پیگیری {a['action_no']}: {a['title']}" for a in open_items[:5]] +
                    ["بررسی موضوع جلسه و مدارک دارای مجوز",
                     "ثبت مسئول، موعد و معیار پذیرش اقدامات پس از تأیید انسانی"]
                ),
                "human_approval_required": True,
                "processmaker_write_performed": False,
                "note": "Read-only preparation draft; transcription and automatic ProcessMaker entry not implemented."}
    _, result = _query(principal, action)
    return result


@app.get("/v1/analytics/status-overview")
def status_overview(principal: PrincipalDep):
    """Module 3: exact counts of ALL grant-visible index rows (not TOP 20 sample)."""
    def action(con, p):
        require_module(con, p, 3)
        cur = con.cursor()
        cur.execute("""
            SELECT m.MeetingStatus, COUNT_BIG(*) AS Total
            FROM AgentProduct.MeetingIndex m
            WHERE m.TenantID=?
              AND EXISTS(SELECT 1 FROM AgentProduct.MeetingGrant g
                         WHERE g.TenantID=m.TenantID AND g.MeetingID=m.MeetingID
                           AND g.SubjectID=?)
            GROUP BY m.MeetingStatus ORDER BY m.MeetingStatus
        """, str(p.tenant_id), p.subject)
        counts = [{"status": str(r[0]), "count": int(r[1])} for r in cur.fetchall()]
        cur.execute("""
            SELECT COUNT_BIG(*) AS TotalActions,
             COALESCE(SUM(CASE WHEN a.IsClosed=0 AND a.ProgressPercent<100
                               THEN CAST(1 AS bigint) ELSE CAST(0 AS bigint) END),0) AS OpenActions,
             COALESCE(SUM(CASE WHEN a.IsClosed=0 AND a.ProgressPercent<100
                                   AND a.DueAtUtc<SYSUTCDATETIME()
                               THEN CAST(1 AS bigint) ELSE CAST(0 AS bigint) END),0) AS OverdueActions
            FROM AgentProduct.ActionIndex a
            WHERE a.TenantID=? AND EXISTS(
             SELECT 1 FROM AgentProduct.MeetingGrant g
             WHERE g.TenantID=a.TenantID AND g.MeetingID=a.MeetingID AND g.SubjectID=?)
        """, str(p.tenant_id), p.subject)
        action_counts = cur.fetchone()
        return {"scope": "only explicitly granted fictional meeting/action-index rows",
                "total_visible_meetings": sum(item["count"] for item in counts),
                "status_breakdown": counts,
                "actions": {"total": int(action_counts[0]),
                            "open": int(action_counts[1]),
                            "overdue": int(action_counts[2])},
                "note": "Counts are scoped to user grants; no unsupported financial KPIs inferred."}
    _, result = _query(principal, action)
    return result


@app.get("/v1/monitoring/overdue")
def overdue_alerts(principal: PrincipalDep):
    """Module 4: on-demand read-only due-date alerts; not a running notification job."""
    def action(con, p):
        require_module(con, p, 4)
        cur = con.cursor()
        cur.execute("""
            SELECT TOP (50) a.MeetingID, a.ActionNo, a.ActionTitle,
                   a.OwnerUnit, a.DueAtUtc, a.ProgressPercent
            FROM AgentProduct.ActionIndex a
            WHERE a.TenantID=? AND a.DueAtUtc<SYSUTCDATETIME()
              AND a.ProgressPercent<100 AND a.IsClosed=0
              AND EXISTS(SELECT 1 FROM AgentProduct.MeetingGrant g
                         WHERE g.TenantID=a.TenantID AND g.MeetingID=a.MeetingID
                           AND g.SubjectID=?)
            ORDER BY a.DueAtUtc,a.MeetingID,a.ActionNo
        """, str(p.tenant_id), p.subject)
        rows = [{"meeting_id": int(r[0]), "action_no": str(r[1]),
                 "title": str(r[2]), "owner_unit": str(r[3]),
                 "due_at_utc": str(r[4]), "progress_percent": int(r[5])}
                for r in cur.fetchall()]
        return {"alerts": rows, "returned": len(rows), "max_returned": 50,
                "scope": "only explicitly granted fictional meetings",
                "note": "On-demand overdue preview only; no scheduled delivery or messages."}
    _, result = _query(principal, action)
    return result


# Opt-in loopback-only connected browser shell; NO auth bypass and NO routes
# under /v1/ are supplied by the portal. The actual API verifies every JWT.
from .connected_portal import router as connected_portal_router
app.include_router(connected_portal_router)


# NEW hierarchical-ACL routes keep the existing, previously tested v1 grants
# intact until controlled directory identity/meeting involvement migration.
# Every v2 request still uses the SAME verified JWT dependency and real SQL.
from .directory_api import make_router as make_directory_router
app.include_router(make_directory_router(_authenticated_principal))



# GodAdmin is a SEPARATE, narrowly authorized platform metadata/licensing
# control plane; its SQL account never receives customer meeting/doc SELECT.
from .godadmin_api import make_router as make_godadmin_router
app.include_router(make_godadmin_router(_authenticated_principal))
