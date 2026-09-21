"""Explicit DBA-approved, additive installation from GodAdmin UI.

DBA credentials are never written to AVAN state, logs, .env or the browser
after submission. Fixed, publisher-reviewed SQL scripts only: the API does not
accept arbitrary SQL or user-supplied script paths. Only the operational
EnterpriseProcess2 name is valid; MTG tables are never dropped or modified.
"""
from __future__ import annotations
from pathlib import Path
import re
import secrets

from .production_store import _value
from . import setup_console as setup

SQL_ROOT=Path(__file__).resolve().parent/"sql"
REQUIRED={
 "Meeting":("MeetingID","MeetingNo","MeetingTitle","MeetingStartDateTime",
            "Status","PMCaseUID","ChairUserUID","SecretaryUserUID",
            "DiscussionSummary","ParkingLot"),
 "MeetingParticipant":("MeetingID","UserUID"),
 "ActionItem":("ActionItemID","MeetingID","ActionNo","ActionDescription",
               "OwnerUserUID","OwnerName","OwnerPosition","DueDateTime",
               "Status","ProgressPercent","SecretaryProgressPercent","ClosedAt"),
 "Decision":("MeetingID","DecisionText"),
}

class InstallationDenied(Exception):pass

def _dba_connect(server:str,username:str,password:str,trust_certificate:bool):
    if (not server or any(c in server for c in ";{}\x00\r\n") or
        not username or any(c in username for c in ";{}\x00\r\n") or
        username.casefold()=="avan_reader" or not password):
        raise InstallationDenied("DBA credentials or SQL Server address invalid")
    import pyodbc
    try:
        con=pyodbc.connect(
          "DRIVER={ODBC Driver 17 for SQL Server};"+
          "SERVER="+_value(server)+";DATABASE=EnterpriseProcess2;"+
          "UID="+_value(username)+";PWD="+_value(password)+";"+
          "Encrypt=yes;TrustServerCertificate="+
          ("yes" if trust_certificate else "no")+";Connection Timeout=8;",
          timeout=8,autocommit=True,
        )
        return con
    except Exception as exc:
        raise InstallationDenied("Cannot authenticate to operational SQL with supplied DBA account") from exc

def _inventory(con):
    cur=con.cursor()
    cur.execute("SELECT DB_NAME(),IS_SRVROLEMEMBER('sysadmin')")
    db=cur.fetchone()
    if not db or str(db[0])!="EnterpriseProcess2":
        raise InstallationDenied("Unexpected database; EnterpriseProcess2 required")
    cur.execute("""
      SELECT t.name,c.name
      FROM sys.tables t JOIN sys.schemas s ON s.schema_id=t.schema_id
      JOIN sys.columns c ON c.object_id=t.object_id
      WHERE s.name=N'MTG' AND t.name IN(N'Meeting',N'MeetingParticipant',
                      N'ActionItem',N'Decision')
    """)
    found={(str(r[0]),str(r[1])) for r in cur.fetchall()}
    missing=[name+"."+col for name,cols in REQUIRED.items()
             for col in cols if (name,col) not in found]
    cur.execute("SELECT OBJECT_ID(N'AVAN.UserAccess',N'U'),OBJECT_ID(N'AVAN.License',N'U')")
    avan=cur.fetchone()
    return {"database":"EnterpriseProcess2","required_columns_missing":missing,
            "avan_tables_present":bool(avan and avan[0] and avan[1]),
            "has_server_dba_permission":bool(db[1])}

def inspect(server:str,username:str,password:str,trust_certificate:bool):
    con=_dba_connect(server,username,password,trust_certificate)
    try:return _inventory(con)
    finally:con.close()

def _batches(filename:str):
    if filename not in ("PRODUCTION_EnterpriseProcess2_01_AVAN_additive.sql",
                        "PRODUCTION_EnterpriseProcess2_02_reader_grants.sql",
                        "PRODUCTION_EnterpriseProcess2_05_config_writer_grants.sql"):
        raise InstallationDenied("Unapproved migration name")
    code=(SQL_ROOT/filename).read_text(encoding="utf-8")
    if "USE [EnterpriseProcess2]" not in code or "DROP TABLE" in code.upper():
        raise InstallationDenied("Migration source does not match approved additive plan")
    return [chunk.strip() for chunk in re.split(r"(?im)^\s*GO\s*(?:--[^\n]*)?$",code)
            if chunk.strip()]

def _execute_script(con,filename:str):
    for batch in _batches(filename):
        con.cursor().execute(batch)

def _create_login(con,name:str):
    if name not in ("AVAN_Reader","AVAN_ConfigWriter"):
        raise InstallationDenied("Unapproved SQL login")
    cur=con.cursor()
    cur.execute("SELECT SUSER_ID(?)",name)
    if cur.fetchone()[0] is not None:
        return None
    password=secrets.token_urlsafe(40)
    # Only internal fixed identifier and cryptographic ASCII, no caller SQL.
    if not re.fullmatch(r"[A-Za-z0-9_-]{40,80}",password):
        raise InstallationDenied("Unable to provision restricted SQL login")
    cur.execute("USE [master]")
    cur.execute("CREATE LOGIN ["+name+"] WITH PASSWORD='"+password+"', CHECK_POLICY=ON")
    cur.execute("USE [EnterpriseProcess2]")
    return password


def apply(*,server:str,username:str,password:str,trust_certificate:bool,
          backup_confirmed:bool,confirmation:str,reader_existing_password:str|None,
          writer_existing_password:str|None):
    if not backup_confirmed or confirmation!="EnterpriseProcess2":
        raise InstallationDenied("Verified backup and exact database confirmation required")
    con=_dba_connect(server,username,password,trust_certificate)
    generated=None
    try:
        inventory=_inventory(con)
        if inventory["required_columns_missing"]:
            raise InstallationDenied("Live MTG schema differs: "+", ".join(
                inventory["required_columns_missing"][:12]))
        if not inventory["has_server_dba_permission"]:
            raise InstallationDenied("DBA sysadmin privilege is required for initial SQL login provisioning")
        # Never create a second login or migrate data if an existing account
        # has an unknown password; otherwise a partial install might strand
        # freshly generated credentials after the request fails.
        cur=con.cursor()
        cur.execute("""SELECT SUSER_ID(N'AVAN_Reader'),
                              SUSER_ID(N'AVAN_ConfigWriter')""")
        existing=cur.fetchone()
        if (existing and ((existing[0] is not None and not reader_existing_password)
              or (existing[1] is not None and not writer_existing_password))):
            raise InstallationDenied(
                "Provide approved passwords for BOTH existing AVAN SQL accounts before applying changes"
            )
        _execute_script(con,"PRODUCTION_EnterpriseProcess2_01_AVAN_additive.sql")
        generated=_create_login(con,"AVAN_Reader")
        generated_writer=_create_login(con,"AVAN_ConfigWriter")
        _execute_script(con,"PRODUCTION_EnterpriseProcess2_02_reader_grants.sql")
        _execute_script(con,"PRODUCTION_EnterpriseProcess2_05_config_writer_grants.sql")
        reader_password=generated or reader_existing_password
        writer_password=generated_writer or writer_existing_password
        if not reader_password or not writer_password:
            raise InstallationDenied("Existing Reader/ConfigWriter login requires its own approved password")
        # Verify actual low-privilege login before persisting its secret.
        import pyodbc
        read_con=pyodbc.connect(
            "DRIVER={ODBC Driver 17 for SQL Server};"+
            "SERVER="+_value(server)+";DATABASE=EnterpriseProcess2;"+
            "UID={AVAN_Reader};PWD="+_value(reader_password)+";"+
            "Encrypt=yes;TrustServerCertificate="+
            ("yes" if trust_certificate else "no")+";Connection Timeout=8;",
            timeout=8,autocommit=True,
        )
        try:
            read_cur=read_con.cursor()
            read_cur.execute("SELECT DB_NAME(),OBJECT_ID(N'AVAN.UserAccess',N'U')")
            checked=read_cur.fetchone()
            if not checked or str(checked[0])!="EnterpriseProcess2" or checked[1] is None:
                raise InstallationDenied("Reader cannot access operational AVAN objects")
        finally:read_con.close()
        # Validate actual writer rights without inserting a customer, user,
        # role, process instance or any real meeting data.
        admin_con=pyodbc.connect(
            "DRIVER={ODBC Driver 17 for SQL Server};"+
            "SERVER="+_value(server)+";DATABASE=EnterpriseProcess2;"+
            "UID={AVAN_ConfigWriter};PWD="+_value(writer_password)+";"+
            "Encrypt=yes;TrustServerCertificate="+
            ("yes" if trust_certificate else "no")+";Connection Timeout=8;",
            timeout=8,autocommit=True,
        )
        try:
            admin_cur=admin_con.cursor()
            admin_cur.execute("""SELECT
               HAS_PERMS_BY_NAME(N'AVAN.UserAccess',N'OBJECT',N'INSERT'),
               HAS_PERMS_BY_NAME(N'MTG.Meeting',N'OBJECT',N'UPDATE')""")
            privileges=admin_cur.fetchone()
            if not privileges or privileges[0]!=1 or privileges[1] not in (0,None):
                raise InstallationDenied("SQL config writer privileges are incorrect")
        finally:admin_con.close()
        setup.put_setting("sql",{
            "server":server,"database":"EnterpriseProcess2",
            "username":"AVAN_Reader","password":reader_password,
            "writer_username":"AVAN_ConfigWriter","writer_password":writer_password,
            "trust_server_certificate":trust_certificate,
        })
        setup.audit("ADDITIVE_AVAN_SQL_MIGRATION_APPLIED")
        return {"database":"EnterpriseProcess2","migration_applied":True,
                "dedicated_reader_ready":True,"dedicated_config_writer_ready":True,
                "sql_credentials_stored_encrypted":True}
    except InstallationDenied:
        raise
    except Exception as exc:
        raise InstallationDenied(
           "SQL upgrade was interrupted. Inspect AVAN tables and SQL login before retrying; never delete MTG.") from exc
    finally:con.close()
