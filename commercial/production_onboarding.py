"""Audited GodAdmin staff onboarding without customer data or workflow writes.

Only a subject obtained from a SIGNATURE-VERIFIED OIDC login can be linked.
Only an ACTIVE ProcessMaker user from the current read-only PM directory with
the same verified employee email can be linked. Company and user writes use
the separate AVAN_ConfigWriter credential, which has NO MTG rights.
"""
from contextlib import contextmanager
import re
import os
from urllib.parse import urlsplit

import httpx

from . import setup_console as setup
from .pending_identities import find as find_pending, approve as finish_pending
from .production_store import _value


class ProvisioningDenied(Exception): pass


def _directory():
    from .processmaker_directory import clean_users,PMSyncUnavailable
    config=setup.get_setting("processmaker") or {}
    base=str(config.get("base_url","")).rstrip("/")
    space=str(config.get("workspace",""))
    bearer=str(config.get("bearer_token",""))
    origin=urlsplit(base)
    local_lab_http=(os.getenv("AVAN_PM_ALLOW_LOCAL_HTTP")=="1" and
                    origin.scheme=="http" and
                    origin.hostname=="host.docker.internal" and origin.port==84)
    if (not (origin.scheme=="https" or local_lab_http) or
        origin.username or origin.password or origin.query or origin.fragment or
        origin.path not in ("","/") or not origin.hostname or
        not re.fullmatch(r"[A-Za-z0-9_-]{1,48}",space) or
        not 8<=len(bearer)<=8192 or any(x in bearer for x in ("\r","\n"))):
        raise ProvisioningDenied("ProcessMaker directory is not configured or token is missing")
    result=[]
    seen=set()
    try:
        with httpx.Client(timeout=12,follow_redirects=False,trust_env=False) as client:
            for start in range(0,5000,100):
                response=client.get(
                    base+"/api/1.0/"+space+"/users",
                    params={"status":"all","start":start,"limit":100},
                    headers={"Authorization":"Bearer "+bearer,
                             "Accept":"application/json"})
                response.raise_for_status()
                if len(response.content)>1048576:
                    raise ProvisioningDenied("ProcessMaker directory response too large")
                batch=clean_users(response.json())
                for user in batch:
                    if user.pm_uid in seen:
                        raise ProvisioningDenied("Duplicate PM user identity")
                    seen.add(user.pm_uid)
                    result.append(user)
                if len(batch)<100:
                    return result
    except (httpx.HTTPError,ValueError,PMSyncUnavailable) as exc:
        raise ProvisioningDenied("Read-only ProcessMaker user directory unavailable") from exc
    raise ProvisioningDenied("ProcessMaker directory exceeded approved 5000-user limit")


def visible_pm_users()->list[dict]:
    return [{"pm_uid":u.pm_uid,"name":u.display_name,
             "email":u.email,"status":u.status}
            for u in _directory() if u.status=="ACTIVE"]


@contextmanager
def writer_connection():
    config=setup.get_setting("sql") or {}
    if (config.get("database")!="EnterpriseProcess2"
        or config.get("writer_username")!="AVAN_ConfigWriter" or
        not config.get("writer_password")):
        raise ProvisioningDenied("Restricted AVAN configuration writer unavailable")
    import pyodbc
    try:
        connection=pyodbc.connect(
            "DRIVER={ODBC Driver 17 for SQL Server};"+
            "SERVER="+_value(str(config["server"]))+";DATABASE=EnterpriseProcess2;"+
            "UID={AVAN_ConfigWriter};PWD="+_value(str(config["writer_password"]))+";"+
            "Encrypt=yes;TrustServerCertificate="+
            ("yes" if config.get("trust_server_certificate") else "no")+
            ";Connection Timeout=8;",
            timeout=8,autocommit=False)
    except Exception as exc:
        raise ProvisioningDenied("AVAN writer connection unavailable") from exc
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def approve_employee(*,tenant_id:str,subject:str,company_name:str,
                     pm_uid:str,role:str,manager_pm_uid:str|None,
                     department_name:str|None):
    import uuid
    try:tenant_id=str(uuid.UUID(tenant_id))
    except (TypeError,ValueError,AttributeError):
        raise ProvisioningDenied("Verified tenant UUID required")
    if (not isinstance(company_name,str) or not 2<=len(company_name.strip())<=200
        or not re.fullmatch(r"[0-9a-fA-F]{32}",pm_uid or "")
        or role not in ("Expert","Manager","SysAdmin")):
        raise ProvisioningDenied("Unapproved company, PM user or organizational role")
    if department_name is not None and len(department_name.strip())>160:
        raise ProvisioningDenied("Department name is too long")
    department=department_name.strip() if department_name else None
    pm_uid=pm_uid.lower()
    if manager_pm_uid is not None:
        manager_pm_uid=manager_pm_uid.strip().lower() or None
        if manager_pm_uid and not re.fullmatch(r"[0-9a-f]{32}",manager_pm_uid):
            raise ProvisioningDenied("Invalid direct manager PM UID")
        if manager_pm_uid==pm_uid:
            raise ProvisioningDenied("User cannot manage themselves")
    user=find_pending(tenant_id,subject)
    if user is None:
        raise ProvisioningDenied("OIDC user has not completed signed organizational login")
    if role=="SysAdmin" and "SysAdmin" not in user["roles"]:
        raise ProvisioningDenied("SysAdmin must ALSO hold the signed IdP role")
    if not user["email_verified"] or not user["email"]:
        raise ProvisioningDenied("IdP email must be verified before staff mapping")
    directory={u.pm_uid:u for u in _directory()}
    staff=directory.get(pm_uid)
    if staff is None or staff.status!="ACTIVE":
        raise ProvisioningDenied("Selected PM user is absent or inactive")
    if not staff.email or staff.email.strip().casefold()!=user["email"].strip().casefold():
        raise ProvisioningDenied("Verified IdP email does not match the ProcessMaker employee")
    with writer_connection() as con:
        cur=con.cursor()
        cur.execute("SELECT TenantID,CompanyName FROM AVAN.Tenant WHERE IsEnabled=1")
        active=cur.fetchall()
        if any(str(row[0]).lower()!=tenant_id.lower() for row in active):
            raise ProvisioningDenied("MTG database already belongs to another active company")
        cur.execute("SELECT CompanyName FROM AVAN.Tenant WHERE TenantID=?",tenant_id)
        existing=cur.fetchone()
        if existing is not None and str(existing[0]).strip()!=company_name.strip():
            raise ProvisioningDenied("Company name differs from existing signed tenant")
        if existing is None:
            cur.execute("INSERT AVAN.Tenant(TenantID,CompanyName,IsEnabled) VALUES (?,?,1)",
                        tenant_id,company_name.strip())
        else:
            cur.execute("UPDATE AVAN.Tenant SET IsEnabled=1 WHERE TenantID=?",tenant_id)
        if manager_pm_uid:
            cur.execute("""SELECT COUNT_BIG(*) FROM AVAN.UserAccess
                WHERE TenantID=? AND PMUserUID=? AND IsEnabled=1 AND PMIsActive=1""",
                tenant_id,manager_pm_uid)
            if int(cur.fetchone()[0])!=1:
                raise ProvisioningDenied("Direct manager must be previously approved and active")
        cur.execute("""SELECT COUNT_BIG(*) FROM AVAN.UserAccess
            WHERE TenantID=? AND (SubjectID=? OR PMUserUID=?)""",
            tenant_id,subject,pm_uid)
        if int(cur.fetchone()[0])!=0:
            raise ProvisioningDenied("This OIDC or PM user is already linked")
        cur.execute("""INSERT AVAN.UserAccess(
            TenantID,SubjectID,PMUserUID,DisplayName,DepartmentName,RoleCode,
            ManagerPMUserUID,IsEnabled,PMIsActive,PMVerifiedAtUTC)
            VALUES(?,?,?,?,?,?,?,1,1,SYSUTCDATETIME())""",
            tenant_id,subject,pm_uid,staff.display_name,
            department,role,manager_pm_uid)
    finish_pending(tenant_id,subject)
    setup.audit("VERIFIED_STAFF_MAPPED_"+role.upper())
    return {"mapped":True,"company_name":company_name.strip(),
            "name":staff.display_name,"role":role,"tenant_id":tenant_id}


def refresh_employee_statuses()->dict:
    """Conservative, full-snapshot PM reconciliation initiated by GodAdmin.

    Refresh verification time for currently approved ACTIVE accounts. Any PM
    user removed/deactivated since the last COMPLETE read-only snapshot is
    disabled in AVAN immediately. Never auto-reactivate a disabled account.
    A failed/incomplete PM API call cannot alter any database user.
    """
    directory={u.pm_uid:u for u in _directory()}
    refreshed=0
    disabled=0
    with writer_connection() as con:
        cur=con.cursor()
        cur.execute("""SELECT TenantID,PMUserUID,IsEnabled,PMIsActive
                       FROM AVAN.UserAccess""")
        rows=cur.fetchall()
        for row in rows:
            tenant=str(row[0])
            pm_uid=str(row[1]).strip().lower()
            active=directory.get(pm_uid)
            if active is not None and active.status=="ACTIVE":
                if bool(row[2]):
                    cur.execute("""UPDATE AVAN.UserAccess
                         SET PMIsActive=1,PMVerifiedAtUTC=SYSUTCDATETIME()
                         WHERE TenantID=? AND PMUserUID=? AND IsEnabled=1""",
                         tenant,pm_uid)
                    refreshed+=1
            else:
                if bool(row[2]) or bool(row[3]):
                    cur.execute("""UPDATE AVAN.UserAccess
                         SET PMIsActive=0,IsEnabled=0
                         WHERE TenantID=? AND PMUserUID=?""",tenant,pm_uid)
                    disabled+=1
    setup.audit("PM_STATUS_RECONCILED")
    return {"refreshed_active_users":refreshed,
            "disabled_unverified_users":disabled,
            "source":"complete_read_only_processmaker_directory"}
