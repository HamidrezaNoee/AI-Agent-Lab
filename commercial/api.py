"""Private commercial gateway FOUNDATION; not yet a customer-facing AI chat service.

OIDC access token -> verified tenant principal -> SQL membership/subscription
-> per-connection SQL RLS tenant context -> tenant-scoped meeting index.
No legacy MTG/AI lab tables or raw SQL endpoints are exposed.
"""
from functools import lru_cache
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field

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
