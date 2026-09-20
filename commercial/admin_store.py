"""Narrow, separate TEST-only SQL connection for approved directory writes.

The ordinary commercial Reader account NEVER receives directory INSERT/UPDATE,
database ownership or SQL sysadmin. This admin connection may only call audited
owner-executing stored procedures granted to AI_CommercialDirectoryAdmin.
Credentials are server-side, never exposed to browser or ProcessMaker.
"""
from contextlib import contextmanager
import os
from .security import Principal
from .sql_store import AccessDenied, StoreUnavailable, _safe_braced


@contextmanager
def directory_admin_connection(principal: Principal):
    if not isinstance(principal, Principal):
        raise AccessDenied("Verified principal required")
    if os.getenv("COMMERCIAL_MODE") != "lab" or (
        os.getenv("COMMERCIAL_SQL_DATABASE") != "EnterpriseProcess2_AI_Test"
    ):
        raise StoreUnavailable("Directory admin is TEST only")
    name = os.getenv("COMMERCIAL_DIRECTORY_SQL_USER", "")
    password = os.getenv("COMMERCIAL_DIRECTORY_SQL_PASSWORD", "")
    if name.lower() != "ai_commercialdirectoryadmin" or not password:
        raise StoreUnavailable("Dedicated directory admin SQL account is not configured")
    import pyodbc
    pyodbc.pooling = False
    conn = pyodbc.connect(
        "DRIVER={ODBC Driver 17 for SQL Server};"
        f"SERVER={_safe_braced(os.getenv('COMMERCIAL_SQL_SERVER',''))};"
        "DATABASE=EnterpriseProcess2_AI_Test;"
        f"UID={_safe_braced(name)};PWD={_safe_braced(password)};"
        "Encrypt=yes;TrustServerCertificate=yes;Connection Timeout=8;",
        timeout=8, autocommit=True,
    )
    try:
        conn.cursor().execute(
            "EXEC sys.sp_set_session_context @key=N'AgentTenantID',@value=?,@read_only=1",
            str(principal.tenant_id),
        )
        yield conn
    finally:
        conn.close()
