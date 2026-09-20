"""ProcessMaker 3.x read-only identity sync into AgentProduct shadow directory.

Source credentials are operator-controlled environment variables. This adapter
reads PM users only; it NEVER reads/copies USR_PASSWORD and NEVER writes PM MySQL.
A separate IdP/Keycloak provisioner should own login/password/MFA identities.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
import os
import re
from .security import Principal
from .authorization_v2 import user_context
from .sql_store import AccessDenied

@dataclass(frozen=True)
class ProcessMakerUser:
    uid: str
    username: str
    first_name: str
    last_name: str
    email: str | None
    status: str

def _source_config():
    host=os.getenv("COMMERCIAL_PM_HOST","").strip()
    db=os.getenv("COMMERCIAL_PM_DATABASE","wf_workflow").strip()
    user=os.getenv("COMMERCIAL_PM_READONLY_USER","").strip()
    password=os.getenv("COMMERCIAL_PM_READONLY_PASSWORD","")
    port=int(os.getenv("COMMERCIAL_PM_PORT","3306"))
    if not host or not user or not password or not re.fullmatch(r"[A-Za-z0-9_]+",db):
        raise RuntimeError("ProcessMaker read-only source is not configured")
    if not 1<=port<=65535: raise RuntimeError("Invalid ProcessMaker port")
    return host,port,db,user,password

def read_processmaker_users(connection_factory=None):
    host,port,db,user,password=_source_config()
    if connection_factory is None:
        try: import pymysql
        except ImportError as exc: raise RuntimeError("Install PyMySQL for ProcessMaker sync") from exc
        connection_factory=lambda: pymysql.connect(
            host=host,port=port,user=user,password=password,database=db,
            charset="utf8mb4",cursorclass=pymysql.cursors.Cursor,
            connect_timeout=5,read_timeout=15,write_timeout=5,autocommit=True)
    con=connection_factory()
    try:
        cur=con.cursor()
        # Explicit columns: NEVER select USR_PASSWORD or other authentication secrets.
        cur.execute("""SELECT USR_UID,USR_USERNAME,USR_FIRSTNAME,USR_LASTNAME,
                             USR_EMAIL,USR_STATUS
                       FROM USERS
                       WHERE USR_USERNAME IS NOT NULL AND USR_USERNAME<>''""")
        rows=cur.fetchall()
        return [ProcessMakerUser(str(r[0]),str(r[1]),str(r[2] or ""),str(r[3] or ""),
                 str(r[4]) if r[4] else None,str(r[5] or "")) for r in rows]
    finally:
        con.close()

def sync_users(sql_con, principal: Principal, source_users: list[ProcessMakerUser]):
    ctx=user_context(sql_con,principal)
    if ctx["role"]!="SysAdmin":
        raise AccessDenied("Only SysAdmin can synchronize ProcessMaker users")
    cur=sql_con.cursor()
    cur.execute("""INSERT AgentProduct.SyncRun(TenantID,SourceSystem,Status)
                   OUTPUT inserted.SyncRunID VALUES(?,N'ProcessMaker',N'Running')""",
                str(principal.tenant_id))
    run_id=int(cur.fetchone()[0]);upserts=0
    try:
        for u in source_users:
            enabled=u.status.upper() in {"ACTIVE","1"}
            # Existing subject mapping is preserved. New PM users are shadow entries
            # pending IdP provisioning; PM username is NOT authentication authority.
            cur.execute("""SELECT SubjectID FROM AgentProduct.UserDirectory
              WHERE TenantID=? AND ProcessMakerUserUID=?""",
              str(principal.tenant_id),u.uid)
            row=cur.fetchone()
            if row:
                subject=row[0]
                cur.execute("""UPDATE AgentProduct.UserDirectory
                   SET ProcessMakerUsername=?,DisplayName=?,Email=?,IsEnabled=?,LastSyncedAtUtc=SYSUTCDATETIME()
                   WHERE TenantID=? AND SubjectID=?""",
                   u.username,(u.first_name+" "+u.last_name).strip() or u.username,
                   u.email,int(enabled),str(principal.tenant_id),subject)
                upserts+=1
            # Creation of Membership/IdP identity is intentionally NOT automatic:
            # SysAdmin reviews and provisions a login to avoid privilege escalation
            # from a source-system account.
        cur.execute("""UPDATE AgentProduct.SyncRun SET CompletedAtUtc=SYSUTCDATETIME(),
          Status=N'Succeeded',ReadCount=?,UpsertCount=? WHERE SyncRunID=? AND TenantID=?""",
          len(source_users),upserts,run_id,str(principal.tenant_id))
        sql_con.commit()
        return {"sync_run_id":run_id,"read":len(source_users),"updated":upserts,
                "new_unprovisioned":len(source_users)-upserts}
    except Exception as exc:
        sql_con.rollback()
        raise RuntimeError("ProcessMaker user sync failed") from exc
