"""Read-only AVAN queries over EnterpriseProcess2 operational MTG schema.

No lab DB, synthetic content, ProcessMaker workflow writes, arbitrary SQL,
ambient db_owner or SQL password fallback. Every content query starts from
the CURRENT verified OIDC -> AVAN tenant/user role+PM UID mapping.
"""
from __future__ import annotations
from contextlib import contextmanager
from datetime import datetime, timezone
import os
import re
from typing import Any
from .security import Principal
from . import setup_console as setup

DATABASE="EnterpriseProcess2"
LOGIN="AVAN_Reader"
MAX_MEETINGS=2000

class ProductionUnavailable(Exception): pass
class ProductionAccessDenied(Exception): pass


def _value(value: str) -> str:
    if not value or "\x00" in value or len(value)>1024:
        raise ProductionUnavailable("SQL production configuration incomplete")
    return "{"+value.replace("}","}}")+"}"


@contextmanager
def open_production():
    # Runtime SQL connection is configured from the GodAdmin UI and stored
    # encrypted in AVAN's own state volume. No customer SQL secret is required
    # in .env / Compose.
    # GodAdmin persists SQL settings in setup_console, not product_state.
    # Always use the SAME verified configuration that /admin/api/sql/save wrote.
    config=setup.get_setting("sql") or {}
    host=str(config.get("server") or "").strip()
    database=str(config.get("database") or "")
    username=str(config.get("username") or "")
    password=str(config.get("password") or "")
    trust=config.get("trust_server_certificate") is True
    if database!=DATABASE:
        raise ProductionUnavailable("Expected operational EnterpriseProcess2")
    if username.casefold()!=LOGIN.casefold():
        raise ProductionUnavailable("Dedicated read-only AVAN_Reader is required")
    if not host or not password:
        raise ProductionUnavailable("SQL Server connection is not configured")
    # The setup form accepts 'hostname,1433' OR 'host\\instance' OR a bare
    # hostname. Do not append a second port to a user-provided SQL endpoint.
    if any(c in host for c in (";", "{", "}", chr(0), chr(13), chr(10))):
        raise ProductionUnavailable("Invalid SQL Server endpoint")
    server=host if ("," in host or chr(92) in host) else host+",1433"
    try:
        import pyodbc
        pyodbc.pooling=False
        conn=pyodbc.connect(
            "DRIVER={ODBC Driver 17 for SQL Server};"+
            "SERVER="+_value(server)+";DATABASE="+DATABASE+";"+
            "UID="+_value(LOGIN)+";PWD="+_value(password)+";"+
            "Encrypt=yes;"+
            ("TrustServerCertificate=yes;" if trust else "TrustServerCertificate=no;")+
            "Connection Timeout=8;",
            timeout=8,autocommit=True
        )
    except Exception as exc:
        raise ProductionUnavailable("Operational SQL connection unavailable") from exc
    try:
        yield conn
    finally:
        conn.close()


def verified_scope(con, principal: Principal)->dict:
    """Never accept PM UID, role, tenant or company from an HTTP request."""
    if not isinstance(principal,Principal):
        raise ProductionAccessDenied("Verified identity required")
    cursor=con.cursor()
    # MTG source tables have NO TenantID column. This adapter deliberately
    # supports exactly ONE active company per EnterpriseProcess2 database.
    # Without this guard, two AVAN tenants could both see the same MTG rows.
    cursor.execute("SELECT COUNT_BIG(*) FROM AVAN.Tenant WHERE IsEnabled=1")
    row_count=cursor.fetchone()
    if row_count is None or int(row_count[0])!=1:
        raise ProductionAccessDenied("Operational MTG requires one active tenant per database")
    cursor.execute("""
        SELECT TOP (1) u.PMUserUID,u.DisplayName,u.DepartmentName,u.RoleCode,
               t.CompanyName
        FROM AVAN.UserAccess u JOIN AVAN.Tenant t ON t.TenantID=u.TenantID
        WHERE u.TenantID=? AND u.SubjectID=? AND
              u.IsEnabled=1 AND u.PMIsActive=1 AND t.IsEnabled=1
              AND u.PMVerifiedAtUTC>=DATEADD(DAY,-7,SYSUTCDATETIME())
    """,str(principal.tenant_id),principal.subject)
    row=cursor.fetchone()
    if not row:
        raise ProductionAccessDenied("Active linked ProcessMaker user not verified")
    role=str(row[3])
    if role=="SysAdmin" and "SysAdmin" not in principal.roles:
        raise ProductionAccessDenied("Signed SysAdmin role missing")
    if role not in ("Expert","Manager","SysAdmin"):
        raise ProductionAccessDenied("Unsupported organizational role")
    from .production_license import ProductionLicenseDenied, signed_entitlement
    try:
        license_data=signed_entitlement(
            con,tenant_id=str(principal.tenant_id),company_name=str(row[4])
        )
    except ProductionLicenseDenied as exc:
        raise ProductionAccessDenied("Signed commercial tenant license missing, invalid or expired") from exc
    return {"license":license_data,
            "pm_uid":str(row[0]).strip(),"name":str(row[1]),
            "department":str(row[2]) if row[2] else None,
            "role":role,"company":str(row[4]),
            "tenant_id":str(principal.tenant_id)}


def _accessible_sql(scope:dict)->tuple[str,list]:
    # Inject only a role selected from fixed server-side AVAN.UserAccess values.
    # This scopes meeting visibility inside SQL, never after retrieving all MTG.
    if scope["role"]=="SysAdmin":
        return ("",[])
    if scope["role"]=="Expert":
        sql="""
            AND (
                m.ChairUserUID=? OR m.SecretaryUserUID=?
                OR EXISTS(SELECT 1 FROM MTG.MeetingParticipant p
                    WHERE p.MeetingID=m.MeetingID AND p.UserUID=?)
                OR EXISTS(SELECT 1 FROM MTG.ActionItem a
                    WHERE a.MeetingID=m.MeetingID AND a.OwnerUserUID=?)
            )
        """
        return sql,[scope["pm_uid"]]*4
    # Manager: direct/indirect reports are verified, enabled PM accounts in
    # THE SAME verified tenant. No global meeting visibility without involvement.
    sql="""
        AND EXISTS(
          SELECT 1 FROM (
             SELECT PMUserUID FROM Subtree
          ) staff
          WHERE m.ChairUserUID=staff.PMUserUID
             OR m.SecretaryUserUID=staff.PMUserUID
             OR EXISTS(SELECT 1 FROM MTG.MeetingParticipant p
                  WHERE p.MeetingID=m.MeetingID
                    AND p.UserUID=staff.PMUserUID)
             OR EXISTS(SELECT 1 FROM MTG.ActionItem a
                  WHERE a.MeetingID=m.MeetingID
                    AND a.OwnerUserUID=staff.PMUserUID)
        )
    """
    return sql,[]


def _manager_cte(scope:dict)->tuple[str,list]:
    if scope["role"]!="Manager":
        return "",[]
    return ("""
        ;WITH Subtree(PMUserUID,Depth,Trail) AS (
          SELECT u.PMUserUID,CAST(0 AS int),
                 CAST(N'/'+RTRIM(u.PMUserUID)+N'/' AS nvarchar(max))
          FROM AVAN.UserAccess u
          WHERE u.TenantID=? AND u.PMUserUID=?
            AND u.IsEnabled=1 AND u.PMIsActive=1
            AND u.PMVerifiedAtUTC>=DATEADD(DAY,-7,SYSUTCDATETIME())
          UNION ALL
          SELECT c.PMUserUID,p.Depth+1,
                 CAST(p.Trail+RTRIM(c.PMUserUID)+N'/' AS nvarchar(max))
          FROM AVAN.UserAccess c JOIN Subtree p
            ON c.ManagerPMUserUID=p.PMUserUID
          WHERE c.TenantID=? AND c.IsEnabled=1 AND c.PMIsActive=1
            AND c.PMVerifiedAtUTC>=DATEADD(DAY,-7,SYSUTCDATETIME())
            AND p.Depth<32
            AND CHARINDEX(N'/'+RTRIM(c.PMUserUID)+N'/',p.Trail)=0
        )
        """,[scope["tenant_id"],scope["pm_uid"],scope["tenant_id"]])


def authorized_meetings_page(con,scope:dict,*,cursor:int|None=None,limit:int=50):
    if not isinstance(limit,int) or not 1<=limit<=50:
        raise ValueError("Invalid meeting page size")
    if cursor is not None and (not isinstance(cursor,int) or cursor<=0):
        raise ValueError("Invalid meeting cursor")
    cte,head=_manager_cte(scope)
    clause,tail=_accessible_sql(scope)
    sql=cte+"""
      SELECT TOP (51) m.MeetingID,m.MeetingNo,m.MeetingTitle,
            m.Status,m.MeetingStartDateTime,m.ParkingLot,
            m.DiscussionSummary
      FROM MTG.Meeting m WHERE 1=1
    """
    params=list(head)
    if cursor is not None:
        sql+=" AND m.MeetingID<?"
        params.append(cursor)
    sql+=clause+" ORDER BY m.MeetingID DESC"
    if cte:sql+=" OPTION (MAXRECURSION 32)"
    params+=tail
    cur=con.cursor()
    cur.execute(sql,*params)
    rows=cur.fetchall()
    more=len(rows)>limit
    meetings=[{
      "meeting_id":int(r[0]),"meeting_no":str(r[1]),
      "title":str(r[2]),"meeting_status":str(r[3]),
      "meeting_date_utc":str(r[4]) if r[4] else None,
      "risk":None,  # ParkingLot is a discussion parking lot, not a risk register.
      "discussion":str(r[6]) if r[6] else None,
      "actions":[]
    } for r in rows[:limit]]
    return {"meetings":meetings,"has_more":more,
            "next_cursor":meetings[-1]["meeting_id"] if more and meetings else None}


def authorized_meeting_snapshot(con,scope:dict,*,maximum:int=MAX_MEETINGS):
    """Bounded meeting/action snapshot; source tables are never changed."""
    if not 1<=maximum<=MAX_MEETINGS:
        raise ValueError("Invalid authorized snapshot limit")
    current=None
    records=[]
    complete=True
    while len(records)<maximum:
        page=authorized_meetings_page(con,scope,cursor=current,
                   limit=min(50,maximum-len(records)))
        records.extend(page["meetings"])
        if not page["has_more"]:
            break
        new_cursor=page["next_cursor"]
        if not new_cursor or (current is not None and new_cursor>=current):
            raise ProductionUnavailable("Unstable operational meeting page")
        current=new_cursor
    else:
        complete=False
    by_id={m["meeting_id"]:m for m in records}
    identifiers=list(by_id)
    # Action IDs originate ONLY from SQL-authorized meeting pages; never from
    # the question text or a client-provided list.
    count=0
    for i in range(0,len(identifiers),35):
        chunk=identifiers[i:i+35]
        placeholders=",".join("?" for _ in chunk)
        cur=con.cursor()
        cur.execute("""
          SELECT a.MeetingID,a.ActionNo,a.ActionDescription,
                 a.OwnerUserUID,a.OwnerName,a.OwnerPosition,
                 a.DueDateTime,a.ProgressPercent,a.SecretaryProgressPercent,
                 a.Status,a.ClosedAt,owner.DepartmentName
          FROM MTG.ActionItem a
          LEFT JOIN AVAN.UserAccess owner ON owner.TenantID=?
             AND owner.PMUserUID=a.OwnerUserUID AND owner.IsEnabled=1
          WHERE a.MeetingID IN ("""+placeholders+""")
          ORDER BY a.MeetingID,a.ActionItemID
        """,scope["tenant_id"],*chunk)
        for r in cur.fetchall():
            identifier=int(r[0])
            if identifier not in by_id or identifier not in chunk:
                raise ProductionAccessDenied("Action is outside authorized meeting scope")
            count+=1
            if count>20000:
                raise ProductionUnavailable("Action snapshot exceeds safe limit")
            status=str(r[9])
            # "Completed" may be an owner submission/review state, not
            # secretary-authorized workflow closure. Only an actual ClosedAt
            # or the explicit Closed state counts as closed.
            closed=bool(r[10]) or status.casefold()=="closed"
            by_id[identifier]["actions"].append({
              "action_no":str(r[1] or "بدون شماره"),
              "description":str(r[2]),"owner_uid":str(r[3]).strip(),
              "owner_name":str(r[4] or "نامشخص"),
              "owner_position":str(r[5] or ""),
              "owner_unit":str(r[11] or "واحد ثبت نشده"),
              "due_at_utc":str(r[6]) if r[6] else None,
              "progress_percent":int(r[8] if r[8] is not None else r[7]),
              "is_closed":closed,"status":status,
            })
    return records,complete
