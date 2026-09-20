"""Dedicated PLATFORM control-plane connection, not the meeting/document reader.

Registered GodAdmin gets metadata/issuer procedures only. Do not grant this
account SELECT on AgentProduct.MeetingIndex, DocumentChunk or operational MTG.
"""
from contextlib import contextmanager
import os
from uuid import UUID
from .sql_store import StoreUnavailable, _safe_braced


@contextmanager
def platform_connection(target_tenant: UUID | None = None):
    if (os.getenv("COMMERCIAL_MODE")!="lab"
        or os.getenv("COMMERCIAL_SQL_DATABASE")!="EnterpriseProcess2_AI_Test"):
        raise StoreUnavailable("Platform control is LAB-only")
    name=os.getenv("COMMERCIAL_PLATFORM_SQL_USER","")
    password=os.getenv("COMMERCIAL_PLATFORM_SQL_PASSWORD","")
    if name.lower()!="ai_commercialplatformadmin" or not password:
        raise StoreUnavailable("Dedicated platform SQL login is not configured")
    import pyodbc
    pyodbc.pooling=False
    con=pyodbc.connect(
        "DRIVER={ODBC Driver 17 for SQL Server};"
        f"SERVER={_safe_braced(os.getenv('COMMERCIAL_SQL_SERVER',''))};"
        "DATABASE=EnterpriseProcess2_AI_Test;"
        f"UID={_safe_braced(name)};PWD={_safe_braced(password)};"
        "Encrypt=yes;TrustServerCertificate=yes;Connection Timeout=8;",
        timeout=8,autocommit=True,
    )
    try:
        if target_tenant is not None:
            con.cursor().execute(
                "EXEC sys.sp_set_session_context @key=N'AgentTenantID',@value=?,@read_only=1",
                str(target_tenant),
            )
        yield con
    finally:
        con.close()
