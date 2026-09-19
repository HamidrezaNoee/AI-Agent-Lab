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
from pydantic import BaseModel, ConfigDict, Field

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
    scoped_connection, visible_meetings, authorized_documents,
    authorized_evidence,
)

app = FastAPI(
    title="Commercial Agent — security foundation (LAB ONLY)",
    version="0.1.0",
    docs_url=None, redoc_url=None, openapi_url=None,
)


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
