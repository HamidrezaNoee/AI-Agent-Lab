"""Host-local GodAdmin setup UI, authenticated separately from tenant content.

Only configuration and read-only connection diagnostics. No customer login,
SQL schema mutation or licensing bypass is granted by this control plane.
"""
from __future__ import annotations

from collections import defaultdict, deque
from datetime import datetime,timezone
from ipaddress import ip_address
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit
import hmac
import os
import re
import secrets
import time

import httpx
from fastapi import APIRouter, HTTPException, Request, Depends
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from . import setup_console as setup

WEB=Path(__file__).resolve().parent/"web"/"admin"
router=APIRouter(prefix="/admin")
_sessions={}
_attempts=defaultdict(deque)

def _local(request:Request):
    # Docker Desktop maps host localhost through a private bridge gateway.
    # Host port MUST remain published on 127.0.0.1 only. Never expose this
    # admin console via a public reverse proxy until SSO/MFA review.
    origin=request.url.hostname
    if origin not in ("localhost","127.0.0.1","testserver"):
        raise HTTPException(403,"پنل نصب فقط از همان رایانه قابل دسترسی است.")
    remote=request.client.host if request.client else ""
    try:
        if origin!="testserver" and not (ip_address(remote).is_private or ip_address(remote).is_loopback):
            raise HTTPException(403,"ورود مدیریتی از شبکه عمومی مجاز نیست.")
    except ValueError:
        if origin!="testserver":
            raise HTTPException(403,"آدرس درخواست مجاز نیست.")
    return True

def _origin(request:Request):
    origin=request.headers.get("origin")
    expected=os.getenv("AVAN_ADMIN_ORIGIN","http://127.0.0.1:8188").rstrip("/")
    allowed={expected}
    if expected=="http://127.0.0.1:8188":
        allowed.add("http://localhost:8188")
    if origin and origin.rstrip("/") not in allowed:
        raise HTTPException(403,"منشأ درخواست معتبر نیست.")

def _prune():
    now=time.time()
    for sid,s in list(_sessions.items()):
        if s["expires"]<now:_sessions.pop(sid,None)

def _cookie(response,token:str):
    secure=os.getenv("AVAN_ADMIN_ORIGIN","http://127.0.0.1:8188").startswith("https://")
    response.set_cookie("avan_godadmin",token,httponly=True,secure=secure,
                        samesite="strict",path="/admin",max_age=1800)

def _required(request:Request):
    _local(request);_origin(request);_prune()
    sid=request.cookies.get("avan_godadmin","")
    row=_sessions.get(sid)
    if not row:raise HTTPException(401,"ورود GodAdmin لازم است.")
    if request.method in ("POST","PUT","PATCH","DELETE"):
        csrf=request.headers.get("X-AVAN-ADMIN-CSRF","")
        if not csrf or not hmac.compare_digest(row["csrf"],csrf):
            raise HTTPException(403,"توکن اعتبارسنجی فرم معتبر نیست.")
    row["expires"]=time.time()+1800
    return sid,row

def _ready(request:Request):
    sid,row=_required(request)
    state=setup.password_state()
    if not state["changed"] or not state["totp"] or not row.get("mfa"):
        raise HTTPException(403,"ابتدا رمز اولیه را تغییر دهید و احراز هویت دومرحله‌ای را فعال کنید.")
    return sid,row


@router.get("/")
def admin_home(request:Request):
    _local(request)
    return FileResponse(WEB/"index.html",media_type="text/html; charset=utf-8")

@router.get("/assets/app.css")
def admin_css(request:Request):
    _local(request)
    return FileResponse(WEB/"app.css",media_type="text/css; charset=utf-8")

@router.get("/assets/app.js")
def admin_js(request:Request):
    _local(request)
    return FileResponse(WEB/"app.js",media_type="text/javascript; charset=utf-8")

@router.get("/api/state")
def state(request:Request):
    _local(request)
    _prune()
    session=_sessions.get(request.cookies.get("avan_godadmin",""))
    p=setup.password_state()
    return {"authenticated":bool(session),"password_changed":p["changed"],
            "mfa_enrolled":p["totp"],
            "mfa_authenticated":bool(session and session.get("mfa")),
            "csrf":session["csrf"] if session else None,
            "configured":bool(setup.get_setting("mysql") and setup.get_setting("agent_sql") and setup.get_setting("oidc"))}

class Login(BaseModel):
    model_config=ConfigDict(extra="forbid")
    username:str=Field(min_length=1,max_length=40)
    password:str=Field(min_length=1,max_length=512)
    otp:str|None=Field(default=None,max_length=6)

@router.post("/api/login")
def login(request:Request,body:Login):
    _local(request);_origin(request);_prune()
    remote=request.client.host if request.client else "unknown"
    attempts=_attempts[remote]
    while attempts and attempts[0]<time.time()-900:attempts.popleft()
    if len(attempts)>=5:
        raise HTTPException(429,"تعداد تلاش‌های ورود بیش از حد مجاز است.")
    state=setup.password_state()
    valid=(hmac.compare_digest(body.username,"godadmin") and
           setup.password_ok(body.password))
    if valid and state["totp"]:
        valid=setup.totp_ok(body.otp or "")
    if not valid:
        attempts.append(time.time())
        setup.audit("GODADMIN_LOGIN_DENIED")
        raise HTTPException(401,"نام کاربری، رمز یا کد دومرحله‌ای معتبر نیست.")
    attempts.clear()
    token=secrets.token_urlsafe(48)
    _sessions[token]={"csrf":secrets.token_urlsafe(32),
                      "expires":time.time()+1800,"mfa":state["totp"]}
    response=JSONResponse({"authenticated":True,"password_changed":state["changed"],
                           "mfa_enrolled":state["totp"],
                           "csrf":_sessions[token]["csrf"]})
    _cookie(response,token)
    setup.audit("GODADMIN_LOGIN")
    return response

class NewPassword(BaseModel):
    model_config=ConfigDict(extra="forbid")
    current:str=Field(min_length=1,max_length=512)
    updated:str=Field(min_length=16,max_length=128)

@router.post("/api/change-password")
def change_password(body:NewPassword,session=Depends(_required)):
    try:setup.change_password(body.current,body.updated)
    except setup.SetupError:raise HTTPException(400,"رمز فعلی یا رمز جدید معتبر نیست.")
    # Revoke every previously issued session, including the current one.
    _sessions.clear()
    response=JSONResponse({"password_changed":True,"login_again":True})
    response.delete_cookie("avan_godadmin",path="/admin")
    return response

def _totp_setup_payload(secret:str)->dict:
    # Generate the QR locally. Never send a TOTP seed to a third-party QR API.
    from base64 import b64encode
    from urllib.parse import quote, urlencode
    import qrcode
    from qrcode.image.svg import SvgImage
    label=quote("AVAN:godadmin",safe="")
    parameters=urlencode({"secret":secret,"issuer":"AVAN","algorithm":"SHA1",
                           "digits":"6","period":"30"})
    provisioning_uri="otpauth://totp/"+label+"?"+parameters
    svg=qrcode.make(provisioning_uri,image_factory=SvgImage,box_size=8,border=4).to_string()
    return {"secret":secret,"account":"godadmin","issuer":"AVAN",
            "qr_data_uri":"data:image/svg+xml;base64,"+b64encode(svg).decode("ascii")}


@router.post("/api/totp/enrollment")
def totp_enrollment(session=Depends(_required)):
    try:secret=setup.totp_enrollment()
    except setup.SetupError:raise HTTPException(403,"ابتدا رمز اولیه را تغییر دهید.")
    return _totp_setup_payload(secret)


@router.post("/api/totp/rotate")
def totp_rotate(session=Depends(_required)):
    # Rotation is available only during enrollment. Previously issued
    # QR codes and manual setup keys immediately become invalid.
    from base64 import b32encode
    current=setup.password_state()
    if not current["changed"] or current["totp"]:
        raise HTTPException(403,"تولید کلید جدید فقط پیش از فعال‌سازی دومرحله‌ای مجاز است.")
    secret=b32encode(secrets.token_bytes(20)).decode("ascii").rstrip("=")
    with setup._db() as con:
        changed=con.execute(
            """UPDATE godadmin SET totp_secret=? WHERE username='godadmin'
               AND password_changed=1 AND totp_verified=0""",(secret,)
        ).rowcount
    if changed!=1:
        raise HTTPException(409,"لطفاً صفحه فعال‌سازی را دوباره باز کنید.")
    setup.audit("GODADMIN_MFA_PENDING_SECRET_ROTATED")
    return _totp_setup_payload(secret)


class Totp(BaseModel):
    model_config=ConfigDict(extra="forbid")
    code:str=Field(min_length=6,max_length=6)

@router.post("/api/totp/confirm")
def totp_confirm(body:Totp,session=Depends(_required)):
    try:setup.confirm_totp(body.code)
    except setup.SetupError:raise HTTPException(403,"کد دومرحله‌ای نامعتبر است.")
    _sessions.clear()
    response=JSONResponse({"mfa_enrolled":True,"login_again":True})
    response.delete_cookie("avan_godadmin",path="/admin")
    return response

@router.post("/api/logout")
def logout(session=Depends(_required)):
    sid,_=session
    _sessions.pop(sid,None)
    response=JSONResponse({"signed_out":True})
    response.delete_cookie("avan_godadmin",path="/admin")
    return response

@router.get("/api/settings")
def settings(session=Depends(_ready)):
    return setup.masked_settings()


class MySQLConfig(BaseModel):
    model_config=ConfigDict(extra='forbid')
    host:str=Field(min_length=1,max_length=253,pattern=r'^[A-Za-z0-9_.:-]+$')
    port:int=Field(default=3306,ge=1,le=65535)
    database:str=Field(default='wf_workflow',pattern=r'^wf_[A-Za-z0-9_]{1,48}$')
    username:str=Field(min_length=1,max_length=128)
    password:str=Field(min_length=1,max_length=512)
    tls:bool=True
    ca_pem:str=Field(default='',max_length=16000)
    timezone:str=Field(default='Asia/Tehran',max_length=80)


def _mysql_check(body):
    from zoneinfo import ZoneInfo,ZoneInfoNotFoundError
    try:ZoneInfo(body.timezone)
    except (ZoneInfoNotFoundError,ValueError):raise HTTPException(422,"منطقه زمانی ProcessMaker معتبر نیست.")
    from .processmaker_store import open_production,query,ProductionUnavailable,MEETING_PROCESS,ACTION_PROCESS
    try:
        with open_production(body.model_dump()) as con:
            # Inspect only schema/metadata; never print connection details.
            query(con,'SELECT APP_UID,APP_NUMBER,APP_STATUS,APP_DATA FROM APPLICATION LIMIT 0')
            query(con,'SELECT u.USR_UID,u.USR_FIRSTNAME,u.USR_LASTNAME,u.USR_EMAIL,u.USR_STATUS,d.DEP_TITLE FROM USERS u LEFT JOIN DEPARTMENT d ON d.DEP_UID=u.DEP_UID LIMIT 0')
            query(con,'SELECT APP_INIT_USER,APP_CREATE_DATE,APP_FINISH_DATE FROM APPLICATION LIMIT 0')
            query(con,'SELECT DEL_INDEX,APP_UID,TAS_UID,USR_UID,DEL_THREAD_STATUS,DEL_DELEGATE_DATE,DEL_INIT_DATE,DEL_FINISH_DATE,DEL_TASK_DUE_DATE FROM APP_DELEGATION LIMIT 0')
            query(con,'SELECT TAS_UID,TAS_TITLE FROM TASK LIMIT 0')
            query(con,'SELECT PRO_TITLE FROM PROCESS LIMIT 0')
            rows=query(con,'SELECT PRO_UID FROM PROCESS WHERE PRO_UID IN (%s,%s)',(MEETING_PROCESS,ACTION_PROCESS))
            if len(rows)!=2:raise ProductionUnavailable('Both meeting processes must be imported')
        return {'connected':True,'source':'ProcessMaker/MySQL','read_only':True}
    except ProductionUnavailable:raise HTTPException(503,'اتصال فقط‌خواندنی MySQL یا دو فرایند جلسه قابل تأیید نیست.')

@router.post('/api/mysql/check')
def mysql_check(body:MySQLConfig,session=Depends(_ready)):
    return _mysql_check(body)

@router.post('/api/mysql/save')
def mysql_save(body:MySQLConfig,session=Depends(_ready)):
    result=_mysql_check(body)
    setup.put_setting('mysql',body.model_dump())
    return {**result,'saved':True}


class CompanyConfig(BaseModel):
    model_config=ConfigDict(extra="forbid")
    company_name:str=Field(min_length=2,max_length=200)


@router.post("/api/company/save")
def company_save(body:CompanyConfig,session=Depends(_ready)):
    import uuid
    current=setup.get_setting("company") or {}
    tenant_id=current.get("tenant_id")
    if tenant_id:
        try: tenant_id=str(uuid.UUID(str(tenant_id)))
        except ValueError: raise HTTPException(409,"شناسه سازمان ذخیره‌شده معتبر نیست.")
    else:
        tenant_id=str(uuid.uuid4())
    payload={"tenant_id":tenant_id,"company_name":body.company_name.strip()}
    setup.put_setting("company",payload)
    return {"saved":True,**payload}


@router.get("/api/company")
def company_get(session=Depends(_ready)):
    current=setup.get_setting("company") or {}
    return {"tenant_id":current.get("tenant_id"),
            "company_name":current.get("company_name")}


@router.get("/api/identity/status")
def identity_status(session=Depends(_ready)):
    config=setup.get_setting("oidc") or {}
    issuer=str(config.get("issuer","")).rstrip("/")
    managed=config.get("managed_by_product") is True
    if not managed:
        raise HTTPException(503,"زیرساخت هویت داخلی آوان آماده نیست.")
    try:
        with httpx.Client(timeout=7,follow_redirects=False,trust_env=False) as http:
            response=http.get(issuer+"/.well-known/openid-configuration")
            response.raise_for_status()
            data=response.json()
            if data.get("issuer")!=issuer:
                raise ValueError("issuer mismatch")
        return {"managed_by_product":True,"connected":True,
                "realm":"avan","issuer":issuer,
                "customer_secret_entry_required":False}
    except Exception:
        raise HTTPException(503,"سرویس هویت داخلی آوان در دسترس نیست.")


class PMConfig(BaseModel):
    model_config=ConfigDict(extra="forbid")
    base_url:str=Field(min_length=12,max_length=500)
    workspace:str=Field(min_length=1,max_length=48)
    bearer_token:str=Field(min_length=8,max_length=8192)

def _pm_check(config:PMConfig)->int:
    # This is a GET-only directory check. Admin tokens work too: user role
    # is not constrained or changed by AVAN.
    base=config.base_url.rstrip("/")
    parsed=urlsplit(base)
    if (not parsed.hostname or parsed.username or parsed.password or
        parsed.query or parsed.fragment or parsed.path not in ("","/") or
        not re.fullmatch(r"[A-Za-z0-9_-]{1,48}",config.workspace)):
        raise HTTPException(422,"نشانی اصلی ProcessMaker یا Workspace معتبر نیست.")
    local_lab_http=(os.getenv("AVAN_PM_ALLOW_LOCAL_HTTP")=="1" and
                    parsed.scheme=="http" and
                    parsed.hostname.lower()=="host.docker.internal" and
                    parsed.port==84)
    if parsed.scheme!="https" and not local_lab_http:
        raise HTTPException(422,"در نصب آزمایشی آدرس http://host.docker.internal:84 را وارد کنید؛ در نصب عملیاتی HTTPS الزامی است.")
    url=base+"/api/1.0/"+config.workspace+"/users"
    try:
        with httpx.Client(timeout=8,follow_redirects=False,trust_env=False) as http:
            response=http.get(url,params={"status":"all","start":0,"limit":1},
                              headers={"Authorization":"Bearer "+config.bearer_token,
                                       "Accept":"application/json"})
            if response.status_code in (401,403):
                raise HTTPException(401,"توکن ProcessMaker نامعتبر، منقضی یا فاقد مجوز مشاهده کاربران است؛ توکن تازه دریافت کنید.")
            if response.status_code!=200:
                raise HTTPException(503,"API کاربران ProcessMaker پاسخ HTTP "+str(response.status_code)+" داد؛ آدرس و Workspace را بررسی کنید.")
            if len(response.content)>20000 or not isinstance(response.json(),(list,dict)):
                raise HTTPException(502,"پاسخ API کاربران ProcessMaker معتبر نیست.")
        return response.status_code
    except httpx.RequestError:
        raise HTTPException(503,"اتصال شبکه یا گواهی TLS ProcessMaker قابل تأیید نیست؛ نشانی سرویس را بررسی کنید.")
    except ValueError:
        raise HTTPException(502,"پاسخ JSON کاربران ProcessMaker نامعتبر است.")


@router.post("/api/processmaker/check")
def pm_check(body:PMConfig,session=Depends(_ready)):
    _pm_check(body)
    return {"connected":True,"directory_request":"GET","account_role_not_restricted":True}

@router.post("/api/processmaker/save")
def pm_save(body:PMConfig,session=Depends(_ready)):
    _pm_check(body)
    setup.put_setting("processmaker",body.model_dump())
    return {"saved":True,"note":"اتصال تأیید شد؛ همگام‌سازی کاربران هنوز به تأیید هویت‌نامه و سیاست ابطال دسترسی نیاز دارد."}

@router.get("/api/users/pending")
def pending_staff(session=Depends(_ready)):
    from .pending_identities import list_pending
    return {"pending":list_pending()}

@router.get("/api/processmaker/users")
def processmaker_users(session=Depends(_ready)):
    from .production_onboarding import ProvisioningDenied,visible_pm_users
    try:return {"users":visible_pm_users()}
    except ProvisioningDenied:
        raise HTTPException(503,"فهرست کاربران فعال ProcessMaker قابل دریافت نیست.")

@router.post("/api/processmaker/refresh-users")
def refresh_processmaker_users(session=Depends(_ready)):
    from .production_onboarding import ProvisioningDenied,refresh_employee_statuses
    try:return refresh_employee_statuses()
    except ProvisioningDenied:
        raise HTTPException(503,
            "تازه‌سازی امن کاربران انجام نشد؛ هیچ دسترسی کاربری تغییر نکرد.")


class StaffApproval(BaseModel):
    model_config=ConfigDict(extra="forbid")
    tenant_id:str=Field(min_length=36,max_length=36)
    subject:str=Field(min_length=1,max_length=180)
    company_name:str=Field(min_length=2,max_length=200)
    pm_uid:str=Field(min_length=32,max_length=32)
    role:str=Field(min_length=6,max_length=8)
    manager_pm_uid:str|None=Field(default=None,max_length=32)
    department_name:str|None=Field(default=None,max_length=160)

@router.post("/api/users/approve")
def approve_staff(body:StaffApproval,session=Depends(_ready)):
    from .production_onboarding import ProvisioningDenied,approve_employee
    try:return approve_employee(
        tenant_id=body.tenant_id,subject=body.subject,
        company_name=body.company_name,pm_uid=body.pm_uid,
        role=body.role,manager_pm_uid=body.manager_pm_uid,
        department_name=body.department_name)
    except ProvisioningDenied as exc:
        # The exception contains only server-defined validation messages; no
        # SQL driver errors, passwords, PM tokens or raw IdP access token.
        raise HTTPException(409,str(exc))


class PublicKey(BaseModel):
    model_config=ConfigDict(extra="forbid")
    pem:str=Field(min_length=100,max_length=10000)

@router.post("/api/license/public-key")
def public_key(body:PublicKey,session=Depends(_ready)):
    # The trusted publisher fingerprint is provisioned by the software
    # PUBLISHER, outside the customer-admin UI. Otherwise a customer GodAdmin
    # could replace the verifier key and self-issue arbitrary licenses.
    import hashlib
    pin_file=Path(__file__).parent/"licensing"/"publisher-key.sha256"
    if not pin_file.is_file():
        raise HTTPException(503,"کلید مرجع ناشر باید در نسخه معتبر نرم‌افزار نصب شود.")
    pin=pin_file.read_text(encoding="ascii").strip().lower()
    if not re.fullmatch(r"[0-9a-f]{64}",pin):
        raise HTTPException(503,"اثر انگشت کلید مرجع ناشر معتبر نیست.")
    try:raw=body.pem.replace("\r\n","\n").strip().encode("ascii")
    except UnicodeEncodeError:raise HTTPException(400,"کلید عمومی ناشر معتبر نیست.")
    if not hmac.compare_digest(hashlib.sha256(raw).hexdigest(),pin):
        raise HTTPException(403,"کلید عمومی با امضای مرجع ناشر این نسخه تطبیق ندارد.")
    try:setup.install_public_pem(raw)
    except setup.SetupError:
        raise HTTPException(400,"کلید عمومی ناشر باید ECDSA P-256 و معتبر باشد.")
    return {"saved":True,"private_key_imported":False}

class LicenseActivation(BaseModel):
    model_config=ConfigDict(extra="forbid")
    tenant_id:str=Field(min_length=36,max_length=36)
    token:str=Field(min_length=100,max_length=20000)

@router.post("/api/license/activate")
def activate_license(body:LicenseActivation,session=Depends(_ready)):
    from uuid import UUID
    from .licensing.codec import LicenseInvalid,verify_license
    from .production_store import open_production,ProductionUnavailable
    try:tenant_id=str(UUID(body.tenant_id))
    except (ValueError,TypeError):
        raise HTTPException(422,"شناسه UUID سازمان معتبر نیست.")
    if not setup.PUBLIC.is_file():
        raise HTTPException(503,"ابتدا کلید عمومی معتبر ناشر باید نصب شود.")
    installation=(setup.get_setting("installation") or {}).get("installation_id","")
    try:
        from . import native_access
        data=native_access.read()
        configured=setup.get_setting('company') or {}
        if configured.get('tenant_id')!=tenant_id or data.get('tenant_id') not in (None,tenant_id):
            raise HTTPException(404,'سازمان فعال با این شناسه ثبت نشده است.')
        tenant=(data.get('company_name') or configured.get('company_name'),)
        used=native_access.seats(tenant_id)
        payload=verify_license(body.token,setup.PUBLIC.read_bytes(),
            tenant_id=tenant_id,installation_id=installation,
            active_users=used)
        if payload["customer"].strip()!=str(tenant[0]).strip():
            raise HTTPException(403,"نام مشتری در لایسنس با سازمان ثبت‌شده یکسان نیست.")
        setup.put_setting("license",{"tenant_id":tenant_id,"token":body.token})
        return {"activated":True,"license_id":payload["license_id"],
                "active_users":used,"max_users":payload["max_users"],
                "modules":payload["modules"],"expires_at":payload["expires_at"]}
    except LicenseInvalid:
        raise HTTPException(403,"امضای لایسنس، شناسه نصب، سقف کاربران یا تاریخ اعتبار مجاز نیست.")
    except ProductionUnavailable:
        raise HTTPException(503,"اتصال امن به بانک عملیاتی برقرار نیست.")




class AIConfig(BaseModel):
    model_config=ConfigDict(extra='forbid')
    enabled:bool=False
    model:str=Field(default='gpt-4.1-mini',min_length=1,max_length=100,pattern=r'^[a-zA-Z0-9_.:-]+$')
    api_key:str=Field(default='',max_length=1024)
    voice_enabled:bool=False
    transcription_model:Literal['gpt-4o-mini-transcribe','gpt-4o-transcribe','whisper-1']='gpt-4o-mini-transcribe'
    speech_model:Literal['gpt-4o-mini-tts','tts-1','tts-1-hd']='gpt-4o-mini-tts'
    voice:Literal['alloy','coral','onyx','nova','shimmer']='alloy'


@router.post('/api/ai/save')
def ai_save(body:AIConfig,session=Depends(_ready)):
    config=body.model_dump()
    previous=setup.get_setting('ai') or {}
    if not config['api_key'] or config['api_key']=='********':config['api_key']=previous.get('api_key','')
    if config['enabled'] and len(config['api_key'].strip())<16:
        raise HTTPException(422,'کلید API معتبر وارد کنید.')
    if any(c in config['api_key'] for c in ('\r','\n','\x00')):
        raise HTTPException(422,'کلید API معتبر نیست.')
    setup.put_setting('ai',config)
    return {'saved':True,'enabled':config['enabled'],'model':config['model']}


@router.post('/api/ai/check')
def ai_check(session=Depends(_ready)):
    from .meeting_agent import configured_client,AgentUnavailable
    try:
        client,model=configured_client()
        try:
            # Verifies model visibility and auth without sending organizational data.
            client.models.retrieve(model)
        finally:client.close()
    except Exception:
        raise HTTPException(503,'اتصال یا دسترسی به مدل تأیید نشد؛ کلید، مدل و ارتباط اینترنت بررسی شود.')
    setup.audit('AI_CONNECTION_CHECKED')
    return {'connected':True,'model':model,'generation_tested':False}

class AgentSqlConfig(BaseModel):
    model_config=ConfigDict(extra='forbid')
    server:str=Field(min_length=1,max_length=253)
    database:str=Field(default='AVANAgent',pattern=r'^AVANAgent$')
    username:str=Field(default='AVAN_AgentApp',pattern=r'^AVAN_AgentApp$')
    password:str=Field(min_length=1,max_length=512)
    trust_server_certificate:bool=False

class AgentDatabaseInstall(BaseModel):
    model_config=ConfigDict(extra='forbid')
    server:str=Field(min_length=1,max_length=253)
    username:str=Field(min_length=1,max_length=128)
    password:str=Field(min_length=1,max_length=512)
    trust_server_certificate:bool=False
    confirmation:str=Field(pattern=r'^AVANAgent$')

@router.post('/api/agent-db/prepare')
def prepare_agent_database(body:AgentDatabaseInstall,session=Depends(_ready)):
    from .agent_install import prepare,InstallationDenied
    try:return prepare(**body.model_dump())
    except InstallationDenied:raise HTTPException(409,'نصب بانک اختصاصی انجام نشد؛ نام تأیید، مجوز نصب یا وجود حساب قبلی را بررسی کنید.')
    except Exception:raise HTTPException(503,'نصب بانک اختصاصی Agent ناموفق بود؛ اتصال و مجوز حساب نصب بررسی شود.')

@router.post('/api/agent-db/check')
def check_agent_database(body:AgentSqlConfig,session=Depends(_ready)):
    from .agent_install import check
    try:return check(body.model_dump())
    except Exception:raise HTTPException(503,'اتصال یا سطح دسترسی بانک اختصاصی Agent معتبر نیست.')

@router.post('/api/agent-db/save')
def save_agent_database(body:AgentSqlConfig,session=Depends(_ready)):
    result=check_agent_database(body,session)
    setup.put_setting('agent_sql',body.model_dump())
    return {**result,'saved':True}


@router.get('/api/license/status')
def license_status(session=Depends(_ready)):
    from . import native_access
    from .production_license import capacity, ProductionLicenseDenied
    company=setup.get_setting('company') or {}
    tenant=company.get('tenant_id')
    used=native_access.seats(tenant) if tenant else 0
    try:
        payload=capacity(tenant,company.get('company_name',''),used)
        expiry=payload['expires_at']
        days=max(0,(datetime.fromisoformat(expiry.replace('Z','+00:00'))-datetime.now(timezone.utc)).days) if expiry else None
        return {'valid':True,'active_users':used,'max_users':payload['max_users'],'remaining_seats':payload['max_users']-used,
                'expires_at':expiry,'remaining_days':days,'modules':payload['modules'],'license_id':payload['license_id']}
    except ProductionLicenseDenied:
        return {'valid':False,'active_users':used,'reason':'لایسنس فعال نیست، منقضی شده یا ظرفیت کاربران رعایت نشده است.'}


@router.get('/api/users/mapped')
def mapped_users(session=Depends(_ready)):
    from . import native_access
    data=native_access.read()
    return {'users':[{k:u.get(k) for k in ('subject','pm_uid','name','role','department_name','enabled','pm_active')} for u in data['users']]}


class UserEnabled(BaseModel):
    model_config=ConfigDict(extra='forbid')
    subject:str=Field(min_length=1,max_length=180)
    enabled:bool


@router.post('/api/users/enabled')
def user_enabled(body:UserEnabled,session=Depends(_ready)):
    from . import native_access
    from .production_license import capacity,ProductionLicenseDenied
    with native_access.edit() as data:
        user=next((u for u in data['users'] if u['subject']==body.subject),None)
        if not user:raise HTTPException(404,'کاربر ثبت نشده است.')
        if body.enabled:
            from .production_onboarding import _directory
            active=any(u.pm_uid==user['pm_uid'] and u.status=='ACTIVE' for u in _directory())
            if not active:raise HTTPException(409,'کاربر ProcessMaker فعال نیست.')
            used=sum(u['subject']!=body.subject and u.get('enabled') and u.get('pm_active') for u in data['users'])+1
            try:capacity(data['tenant_id'],data['company_name'],used)
            except ProductionLicenseDenied:raise HTTPException(409,'اعتبار زمانی یا ظرفیت لایسنس اجازه فعال‌سازی نمی‌دهد.')
            user['pm_active']=True
        user['enabled']=body.enabled
    return {'saved':True,'enabled':body.enabled}
