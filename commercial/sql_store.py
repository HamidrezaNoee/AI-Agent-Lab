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
    cur = con.cursor()
    cur.execute(
        """
        SELECT TOP(20) MeetingID,MeetingNo,MeetingTitle,MeetingStatus
        FROM AgentProduct.MeetingIndex
        WHERE TenantID=?
        ORDER BY MeetingID DESC
        """,
        str(principal.tenant_id),
    )
    return [
        {"meeting_id": int(row[0]), "meeting_no": row[1],
         "title": row[2], "status": row[3]}
        for row in cur.fetchall()
    ]
