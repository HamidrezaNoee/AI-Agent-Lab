"""Isolated commercial SQL access; this lab intentionally never reads MTG/AI test tables.

A verified JWT gives tenant ID, but the DATABASE decides membership, role and
subscription. SQL Row-Level Security additionally filters every AgentProduct row.
A separate least-privilege SQL login is required; do not reuse AI_MeetingAgent.
"""
from contextlib import contextmanager
import os

from .security import Principal

class AccessDenied(Exception):
    pass

class StoreUnavailable(Exception):
    pass


def _safe_braced(value: str) -> str:
    # ODBC connection-string attributes may contain semicolons/braces in secrets.
    if not value or "\x00" in value:
        raise StoreUnavailable("Missing or invalid commercial database setting")
    return "{" + value.replace("}", "}}") + "}"


@contextmanager
def scoped_connection(principal: Principal):
    if not isinstance(principal, Principal):
        raise AccessDenied("Verified principal required")
    if os.getenv("COMMERCIAL_MODE") != "lab":
        raise StoreUnavailable("Commercial production database is NOT enabled")
    if os.getenv("COMMERCIAL_SQL_DATABASE") != "EnterpriseProcess2_AI_Test":
        raise StoreUnavailable("Only isolated synthetic lab database is allowed")
    server = os.getenv("COMMERCIAL_SQL_SERVER", "")
    sql_user = os.getenv("COMMERCIAL_SQL_USER", "")
    sql_password = os.getenv("COMMERCIAL_SQL_PASSWORD", "")
    if sql_user.lower() in {"ai_meetingagent", "sa", ""}:
        raise StoreUnavailable("Use an independent least-privilege commercial SQL login")
    # pyodbc pooling disabled before first connection in this dedicated API process.
    import pyodbc
    pyodbc.pooling = False
    cs = (
        "DRIVER={ODBC Driver 17 for SQL Server};"
        f"SERVER={_safe_braced(server)};"
        "DATABASE=EnterpriseProcess2_AI_Test;"
        f"UID={_safe_braced(sql_user)};PWD={_safe_braced(sql_password)};"
        "Encrypt=yes;TrustServerCertificate=yes;Connection Timeout=8;"
    )
    con = pyodbc.connect(cs, timeout=8, autocommit=True)
    try:
        cur = con.cursor()
        cur.execute(
            "EXEC sys.sp_set_session_context @key=N'AgentTenantID', "
            "@value=?, @read_only=1",
            str(principal.tenant_id),
        )
        yield con
    finally:
        con.close()


def authorization_snapshot(con, principal: Principal) -> dict:
    """Fail closed unless membership, tenant AND subscription are all active."""
    cur = con.cursor()
    cur.execute(
        """
        SELECT TOP (1) mb.RoleCode, sb.PlanCode, sb.ExpiresAtUtc,
               sb.MonthlyRequestLimit
        FROM AgentProduct.Membership mb
        JOIN AgentProduct.Tenant tn ON tn.TenantID=mb.TenantID
        JOIN AgentProduct.Subscription sb ON sb.TenantID=mb.TenantID
        WHERE mb.TenantID=? AND mb.SubjectID=?
          AND mb.IsEnabled=1 AND tn.IsEnabled=1 AND sb.IsActive=1
          AND sb.ExpiresAtUtc > SYSUTCDATETIME()
        """,
        str(principal.tenant_id), principal.subject,
    )
    row = cur.fetchone()
    if row is None:
        raise AccessDenied("No active tenant membership and subscription")
    return {
        "role": str(row[0]),
        "plan": str(row[1]),
        "expires_at_utc": str(row[2]),
        "monthly_request_limit": int(row[3]),
        "quota_enforced": False,  # Usage metering/atomic quotas are NOT implemented.
    }


def visible_meetings(con, principal: Principal) -> list[dict]:
    """Only resources with an EXPLICIT user grant; tenant RLS is a second boundary."""
    cur = con.cursor()
    cur.execute(
        """
        SELECT TOP (20) m.MeetingID, m.MeetingNo, m.MeetingTitle, m.MeetingStatus
        FROM AgentProduct.MeetingIndex AS m
        JOIN AgentProduct.MeetingGrant AS g
          ON g.TenantID=m.TenantID AND g.MeetingID=m.MeetingID
        WHERE m.TenantID=? AND g.SubjectID=? AND g.TenantID=?
        ORDER BY m.MeetingID DESC
        """,
        str(principal.tenant_id), principal.subject, str(principal.tenant_id),
    )
    return [
        {"meeting_id": int(row[0]), "meeting_no": row[1],
         "title": row[2], "status": row[3]}
        for row in cur.fetchall()
    ]


def authorized_meeting(con, principal: Principal, meeting_id: int) -> dict | None:
    """No matching explicit grant -> no meeting data; do not disclose existence."""
    if meeting_id <= 0:
        return None
    cur = con.cursor()
    cur.execute(
        """
        SELECT TOP (1) m.MeetingID, m.MeetingNo, m.MeetingTitle, m.MeetingStatus
        FROM AgentProduct.MeetingIndex m
        JOIN AgentProduct.MeetingGrant g
          ON g.TenantID=m.TenantID AND g.MeetingID=m.MeetingID
        WHERE m.TenantID=? AND m.MeetingID=? AND g.SubjectID=?
        """,
        str(principal.tenant_id), meeting_id, principal.subject,
    )
    row=cur.fetchone()
    if row is None:
        return None
    return {"kind":"meeting","source":f"MEETING:{row[1]}",
            "meeting_id":int(row[0]),"meeting_no":row[1],
            "title":row[2],"status":row[3]}


def _literal_like(value: str) -> str:
    return "%" + value.replace("[", "[[]").replace("%", "[%]").replace("_", "[_]") + "%"


def authorized_documents(con, principal: Principal, query: str, limit: int = 5) -> list[dict]:
    """Read-only keyword evidence, scoped by BOTH tenant RLS and per-user doc grant.

    Never accept tenant ID/subject or arbitrary SQL from the question.
    This small indexed-test MVP does NOT claim vector/semantic search.
    """
    import re
    terms = []
    for term in re.findall(r"[^\\W_]{3,}", query, flags=re.UNICODE):
        if term not in terms:
            terms.append(term)
        if len(terms)>=4:
            break
    if not terms:
        return []
    limit = min(max(int(limit), 1), 5)
    search_clause = " OR ".join(
        "(c.ChunkText LIKE ? OR d.DocumentTitle LIKE ?)" for _ in terms
    )
    params = [str(principal.tenant_id), principal.subject]
    for term in terms:
        params.extend([_literal_like(term), _literal_like(term)])
    cur=con.cursor()
    cur.execute(
        """
        SELECT TOP (200) d.DocumentID,d.DocumentTitle,d.CurrentVersion,
          c.ChunkNo,CONVERT(nvarchar(1200),c.ChunkText) AS Excerpt
        FROM AgentProduct.DocumentIndex d
        JOIN AgentProduct.DocumentGrant g
          ON g.TenantID=d.TenantID AND g.DocumentID=d.DocumentID
        JOIN AgentProduct.DocumentChunk c
          ON c.TenantID=d.TenantID AND c.DocumentID=d.DocumentID
         AND c.DocumentVersion=d.CurrentVersion
        WHERE d.TenantID=? AND g.SubjectID=? AND d.IsActive=1
          AND (""" + search_clause + """)
        ORDER BY d.DocumentID,c.ChunkNo
        """,
        *params,
    )
    rows=cur.fetchall()
    # Hard limit on evidence; no arbitrary unlimited document export.
    return [
        {"kind":"document",
         "source":f"DOC:{row[0]}:v{row[2]}:c{row[3]}",
         "document_id":str(row[0]),"title":row[1],
         "version":int(row[2]),"chunk_no":int(row[3]),
         "excerpt":row[4]}
        for row in rows[:limit]
    ]


def authorized_evidence(con, principal: Principal, question: str,
                        meeting_id: int | None = None) -> list[dict]:
    """Collect bounded evidence before ANY future LLM API invocation."""
    results=[]
    if meeting_id is not None:
        meeting=authorized_meeting(con,principal,meeting_id)
        if meeting is not None:
            results.append(meeting)
    results.extend(authorized_documents(con, principal, question, limit=5))
    return results
