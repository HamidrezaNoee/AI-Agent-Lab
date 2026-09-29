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
from .bpms_registry import SourceConfig

WEB=Path(__file__).resolve().parent/"web"/"admin"
router=APIRouter(prefix="/admin")
_sessions={}
_attempts=defaultdict(deque)
_pending_mfa={}

def _local(request:Request):
    # Before the organizational GodAdmin identity is bound, bootstrap remains
    # strictly host-local. After binding, the same OIDC/MFA-protected GodAdmin
    # may open the management surface inside the normal AVAN workspace.
    origin=request.url.hostname
    if setup.godadmin_identity():
        allowed={"localhost","127.0.0.1","testserver"}
        for raw in (os.getenv("AVAN_PUBLIC_ORIGIN",""),
                    os.getenv("AVAN_ADMIN_ORIGIN","")):
            try:
                host=urlsplit(raw).hostname
                if host:allowed.add(host)
            except ValueError:
                pass
        if origin not in allowed:
            raise HTTPException(403,"نشانی مدیریت سامانه مجاز نیست.")
        return True
    if origin not in ("localhost","127.0.0.1","testserver"):
        raise HTTPException(403,"راه‌اندازی اولیه فقط از همان رایانه قابل دسترسی است.")
    remote=request.client.host if request.client else ""
    try:
        if origin!="testserver" and not (ip_address(remote).is_private or ip_address(remote).is_loopback):
            raise HTTPException(403,"ورود مدیریتی اولیه از شبکه عمومی مجاز نیست.")
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
    if setup.godadmin_identity():
        public=os.getenv("AVAN_PUBLIC_ORIGIN","").rstrip("/")
        if public:allowed.add(public)
    if origin and origin.rstrip("/") not in allowed:
        raise HTTPException(403,"منشأ درخواست معتبر نیست.")

def _prune():
    now=time.time()
    for sid,s in list(_sessions.items()):
        if s["expires"]<now:_sessions.pop(sid,None)
    for token,s in list(_pending_mfa.items()):
        if s["expires"]<now:_pending_mfa.pop(token,None)

def _cookie(response,token:str):
    secure=os.getenv("AVAN_ADMIN_ORIGIN","http://127.0.0.1:8188").startswith("https://")
    response.set_cookie("avan_godadmin",token,httponly=True,secure=secure,
                        samesite="strict",path="/admin",max_age=1800)

def _turnstile_check(token:str,remote:str)->bool:
    from .turnstile import verify
    return verify(token,action="avan-bootstrap-login",remote_ip=remote)

def _required(request:Request):
    _local(request);_origin(request);_prune()
    if setup.godadmin_identity():
        from .production_app import _principal_for_request
        sid,row,principal=_principal_for_request(request)
        if not setup.is_godadmin(principal):
            raise HTTPException(403,"این حساب مجوز تنظیمات GodAdmin را ندارد.")
    else:
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
    if setup.godadmin_identity():
        return sid,row
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

@router.get("/api/captcha/config")
def captcha_config(request:Request):
    _local(request)
    from .turnstile import public_config,TurnstileUnavailable
    try:return public_config("avan-bootstrap-login")
    except TurnstileUnavailable:
        raise HTTPException(503,"سرویس ضدربات داخلی آوان در دسترس نیست.")

@router.get("/api/state")
def state(request:Request):
    _local(request)
    _prune()
    bound=bool(setup.godadmin_identity())
    if bound:
        try:
            _,session=_required(request)
        except HTTPException:
            session=None
    else:
        session=_sessions.get(request.cookies.get("avan_godadmin",""))
    p=setup.password_state()
    return {"authenticated":bool(session),"password_changed":p["changed"],
            "mfa_enrolled":p["totp"],
            "mfa_authenticated":bool(session and (bound or session.get("mfa"))),
            "csrf":session["csrf"] if session else None,
            "auth_mode":"oidc" if bound else "bootstrap",
            "configured":bool(setup.get_setting("mysql") and setup.get_setting("agent_sql") and setup.get_setting("oidc"))}

class Login(BaseModel):
    model_config=ConfigDict(extra="forbid")
    username:str=Field(min_length=1,max_length=40)
    password:str=Field(min_length=1,max_length=512)
    captcha_token:str=Field(default="",max_length=12288)

def _complete_bootstrap_login(mfa:bool):
    token=secrets.token_urlsafe(48)
    _sessions[token]={"csrf":secrets.token_urlsafe(32),
                      "expires":time.time()+1800,"mfa":mfa}
    response=JSONResponse({"authenticated":True,"password_changed":setup.password_state()["changed"],
                           "mfa_enrolled":mfa,"csrf":_sessions[token]["csrf"]})
    _cookie(response,token)
    setup.audit("GODADMIN_LOGIN")
    return response

@router.post("/api/login")
def login(request:Request,body:Login):
    _local(request);_origin(request);_prune()
    if setup.godadmin_identity():
        raise HTTPException(403,"ورود GodAdmin با حساب سازمانی انجام می‌شود.")
    remote=request.client.host if request.client else "unknown"
    attempts=_attempts[remote]
    while attempts and attempts[0]<time.time()-900:attempts.popleft()
    if len(attempts)>=5:
        raise HTTPException(429,"تعداد تلاش‌های ورود بیش از حد مجاز است.")
    try:
        captcha_ok=_turnstile_check(body.captcha_token,remote)
    except Exception:
        # Fail closed: an unavailable anti-bot service never falls through
        # to password verification.
        setup.audit("CAPTCHA_SERVICE_UNAVAILABLE")
        raise HTTPException(503,"اعتبارسنجی ضدربات در دسترس نیست؛ چند لحظه دیگر دوباره تلاش کنید.")
    if not captcha_ok:
        attempts.append(time.time())
        setup.audit("CAPTCHA_LOGIN_DENIED")
        raise HTTPException(401,"اعتبارسنجی ضدربات نامعتبر یا منقضی شده است.")
    state=setup.password_state()
    valid=(hmac.compare_digest(body.username,"godadmin") and
           setup.password_ok(body.password))
    if not valid:
        attempts.append(time.time())
        setup.audit("GODADMIN_LOGIN_DENIED")
        raise HTTPException(401,"نام کاربری یا رمز معتبر نیست.")
    if state["totp"]:
        if len(_pending_mfa)>=1000:
            raise HTTPException(429,"تعداد درخواست‌های احراز هویت بیش از حد مجاز است.")
        # A previous bootstrap cookie must not make the pending OTP step authenticated.
        existing=request.cookies.get("avan_godadmin","")
        if existing:_sessions.pop(existing,None)
        challenge=secrets.token_urlsafe(48)
        _pending_mfa[challenge]={"remote":remote,"expires":time.time()+120,"tries":0}
        response=JSONResponse({"mfa_required":True,"challenge":challenge})
        if existing:response.delete_cookie("avan_godadmin",path="/admin")
        return response
    attempts.clear()
    return _complete_bootstrap_login(False)

class VerifyLoginOtp(BaseModel):
    model_config=ConfigDict(extra="forbid")
    challenge:str=Field(min_length=32,max_length=128)
    otp:str=Field(pattern=r"^[0-9]{6}$")

@router.post("/api/login/otp")
def verify_login_otp(request:Request,body:VerifyLoginOtp):
    _local(request);_origin(request);_prune()
    if setup.godadmin_identity():
        raise HTTPException(403,"ورود GodAdmin با حساب سازمانی انجام می‌شود.")
    remote=request.client.host if request.client else "unknown"
    attempts=_attempts[remote]
    while attempts and attempts[0]<time.time()-900:attempts.popleft()
    if len(attempts)>=5:raise HTTPException(429,"تعداد تلاش‌های ورود بیش از حد مجاز است.")
    entry=_pending_mfa.get(body.challenge)
    if (not entry or entry["remote"]!=remote or entry["expires"]<time.time() or
        not setup.password_state()["totp"]):
        attempts.append(time.time())
        raise HTTPException(401,"مهلت تأیید هویت پایان یافته است؛ دوباره وارد شوید.")
    if not setup.totp_ok(body.otp):
        attempts.append(time.time())
        entry["tries"]+=1
        if entry["tries"]>=3:_pending_mfa.pop(body.challenge,None)
        setup.audit("GODADMIN_LOGIN_DENIED")
        raise HTTPException(401,"کد Authenticator معتبر نیست؛ در صورت پایان مهلت، دوباره وارد شوید.")
    _pending_mfa.pop(body.challenge,None)
    attempts.clear()
    return _complete_bootstrap_login(True)

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
    _pending_mfa.clear()
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
    _pending_mfa.clear()
    response=JSONResponse({"mfa_enrolled":True,"login_again":True})
    response.delete_cookie("avan_godadmin",path="/admin")
    return response

@router.post("/api/logout")
def logout(session=Depends(_required)):
    if setup.godadmin_identity():
        raise HTTPException(409,"برای خروج از حساب سازمانی از خروج اصلی آوان استفاده کنید.")
    sid,_=session
    _sessions.pop(sid,None)
    response=JSONResponse({"signed_out":True})
    response.delete_cookie("avan_godadmin",path="/admin")
    return response

@router.get("/api/settings")
def settings(session=Depends(_ready)):
    return setup.masked_settings()


@router.get("/api/bpms/connections")
def bpms_connections(session=Depends(_ready)):
    from .bpms_registry import sources
    return {"sources":sources(),"processmaker_native_configured":bool(setup.get_setting("mysql"))}


@router.post("/api/bpms/connections/check")
def bpms_check(body:SourceConfig,session=Depends(_ready)):
    from .bpms_registry import check,BPMSUnavailable
    try:return check(body)
    except BPMSUnavailable as exc:raise HTTPException(503,str(exc))


@router.post("/api/bpms/connections/save")
def bpms_save(body:SourceConfig,session=Depends(_ready)):
    from .bpms_registry import save,BPMSUnavailable
    try:return save(body)
    except BPMSUnavailable as exc:raise HTTPException(503,str(exc))


class BPMSID(BaseModel):
    model_config=ConfigDict(extra="forbid")
    source_id:str=Field(pattern=r"^[0-9a-f]{24}$")


@router.post("/api/bpms/connections/delete")
def bpms_delete(body:BPMSID,session=Depends(_ready)):
    from .bpms_registry import delete,BPMSUnavailable
    try:return delete(body.source_id)
    except BPMSUnavailable as exc:raise HTTPException(404,str(exc))


class BPMSEnabled(BPMSID):
    enabled:bool


@router.post("/api/bpms/connections/enabled")
def bpms_enabled(body:BPMSEnabled,session=Depends(_ready)):
    from .bpms_registry import set_enabled,BPMSUnavailable
    try:return set_enabled(body.source_id,body.enabled)
    except BPMSUnavailable as exc:raise HTTPException(503,str(exc))


class GodAdminBinding(BaseModel):
    model_config=ConfigDict(extra="forbid")
    tenant_id:str=Field(min_length=1,max_length=80)
    subject:str=Field(min_length=1,max_length=255)
    otp:str=Field(min_length=6,max_length=6)

@router.post("/api/identity/bind-godadmin")
def bind_godadmin(body:GodAdminBinding,session=Depends(_ready)):
    if setup.godadmin_identity():
        raise HTTPException(409,"حساب GodAdmin قبلاً متصل شده است.")
    if not setup.totp_ok(body.otp):
        raise HTTPException(403,"کد جدید برنامه Authenticator معتبر نیست.")
    from .pending_identities import find,approve
    candidate=find(body.tenant_id,body.subject)
    company=setup.get_setting("company") or {}
    if not candidate or candidate["tenant_id"]!=company.get("tenant_id"):
        raise HTTPException(404,"حساب سازمانی تأییدشده در انتظار یافت نشد.")
    try:setup.bind_godadmin_identity(body.tenant_id,body.subject)
    except setup.SetupError:raise HTTPException(409,"اتصال این حساب ممکن نیست.")
    approve(body.tenant_id,body.subject)
    _sessions.clear()
    _pending_mfa.clear()
    response=JSONResponse({"bound":True,"login_url":"/auth/login"})
    response.delete_cookie("avan_godadmin",path="/admin")
    return response

class GodAdminAccount(BaseModel):
    model_config=ConfigDict(extra="forbid")
    username:str=Field(min_length=3,max_length=80,pattern=r"^[A-Za-z0-9_.@-]+$")
    email:str=Field(min_length=5,max_length=250,pattern=r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
    name:str=Field(min_length=2,max_length=200)
    password:str=Field(min_length=16,max_length=128)
    otp:str=Field(min_length=6,max_length=6)

@router.post("/api/identity/create-godadmin-account")
def create_godadmin_account(body:GodAdminAccount,session=Depends(_ready)):
    if setup.godadmin_identity():
        raise HTTPException(409,"GodAdmin قبلاً ثبت شده است.")
    if not setup.totp_ok(body.otp):
        raise HTTPException(403,"کد جدید برنامه Authenticator معتبر نیست.")
    company=setup.get_setting("company") or {}
    config=setup.get_setting("oidc") or {}
    if not company.get("tenant_id") or config.get("managed_by_product") is not True:
        raise HTTPException(409,"ابتدا سازمان و هویت داخلی آوان را آماده کنید.")
    from .identity_operator import create
    secret_path=Path(os.getenv("AVAN_PROVISIONER_CLIENT_SECRET_PATH",
                            "/run/secrets/avan_provisioner_client_secret"))
    try:
        secret=secret_path.read_text(encoding="utf-8").strip()
        if len(secret)<16:raise ValueError("Invalid service credentials")
        with httpx.Client(timeout=15,follow_redirects=False,trust_env=False) as client:
            subject=create(client,config["issuer"],secret,company["tenant_id"],
                           body.username,body.email,body.name,"GodAdmin",body.password)
    except (OSError,KeyError,httpx.HTTPError):
        raise HTTPException(503,"ساخت حساب در سرویس هویت داخلی انجام نشد.")
    except ValueError:
        raise HTTPException(409,"ساخت حساب ممکن نیست؛ نام کاربری، سازمان یا وضعیت سرویس هویت را بررسی کنید.")
    setup.audit("GODADMIN_OIDC_ACCOUNT_CREATED_PENDING_BIND")
    return {"created":True,"subject":subject,
            "next":"با حساب تازه وارد شوید؛ رمز موقت را تغییر دهید و کد دومرحله‌ای را فعال کنید، سپس حساب را در این پنل تأیید کنید."}


class MySQLConfig(BaseModel):
    model_config=ConfigDict(extra='forbid')
    host:str=Field(min_length=1,max_length=253,pattern=r'^[A-Za-z0-9_.:-]+$')
    port:int=Field(default=3306,ge=1,le=65535)
    database:str=Field(default='wf_workflow',pattern=r'^(?:wf_[A-Za-z0-9_]{1,48}|bitnami_pm)$')
    username:str=Field(min_length=1,max_length=128)
    password:str=Field(min_length=1,max_length=512)
    tls:bool=True
    ca_pem:str=Field(default='',max_length=16000)
    timezone:str=Field(default='Asia/Tehran',max_length=80)
    enabled:bool=True


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


@router.post('/api/mysql/check-saved')
def mysql_check_saved(session=Depends(_ready)):
    saved=setup.get_setting('mysql') or {}
    if not saved:raise HTTPException(404,'اتصال MySQL هنوز ذخیره نشده است.')
    return _mysql_check(MySQLConfig.model_validate(saved))

@router.post('/api/mysql/save')
def mysql_save(body:MySQLConfig,session=Depends(_ready)):
    result=_mysql_check(body)
    setup.put_setting('mysql',body.model_dump())
    return {**result,'saved':True}


class ConnectionEnabled(BaseModel):
    model_config=ConfigDict(extra='forbid')
    enabled:bool


@router.post('/api/mysql/enabled')
def mysql_enabled(body:ConnectionEnabled,session=Depends(_ready)):
    saved=setup.get_setting('mysql') or {}
    if not saved:raise HTTPException(404,'اتصال MySQL هنوز ثبت نشده است.')
    if body.enabled:
        _mysql_check(MySQLConfig.model_validate({**saved,'enabled':True}))
    setup.put_setting('mysql',{**saved,'enabled':body.enabled})
    return {'enabled':body.enabled}


class RemoveConnection(BaseModel):
    model_config=ConfigDict(extra='forbid')
    confirmation:Literal['REMOVE_MYSQL_SOURCE','REMOVE_PM_API','REMOVE_AI_KEY']


@router.post('/api/mysql/remove')
def mysql_remove(body:RemoveConnection,session=Depends(_ready)):
    if body.confirmation!='REMOVE_MYSQL_SOURCE':raise HTTPException(422,'تأیید حذف اتصال MySQL معتبر نیست.')
    setup.put_setting('mysql',{})
    return {'deleted':True}


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
                    parsed.port in (84, 443))
    if parsed.scheme!="https" and not local_lab_http:
        raise HTTPException(422,"در نصب آزمایشی آدرس http://host.docker.internal:443 یا :84 را مطابق پورت واقعی ProcessMaker وارد کنید؛ در نصب عملیاتی HTTPS الزامی است.")
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


@router.post("/api/processmaker/check-saved")
def pm_check_saved(session=Depends(_ready)):
    saved=setup.get_setting("processmaker") or {}
    if not saved:raise HTTPException(404,"اتصال ProcessMaker هنوز ذخیره نشده است.")
    _pm_check(PMConfig.model_validate(saved))
    return {"connected":True,"directory_request":"GET"}

@router.post("/api/processmaker/save")
def pm_save(body:PMConfig,session=Depends(_ready)):
    _pm_check(body)
    setup.put_setting("processmaker",body.model_dump())
    return {"saved":True,"note":"اتصال تأیید شد؛ همگام‌سازی کاربران هنوز به تأیید هویت‌نامه و سیاست ابطال دسترسی نیاز دارد."}


@router.post("/api/processmaker/remove")
def pm_remove(body:RemoveConnection,session=Depends(_ready)):
    if body.confirmation!='REMOVE_PM_API':raise HTTPException(422,'تأیید حذف اتصال API معتبر نیست.')
    setup.put_setting('processmaker',{})
    return {'deleted':True}

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


@router.post('/api/ai/remove')
def ai_remove(body:RemoveConnection,session=Depends(_ready)):
    if body.confirmation!='REMOVE_AI_KEY':raise HTTPException(422,'تأیید حذف کلید معتبر نیست.')
    config=setup.get_setting('ai') or {}
    setup.put_setting('ai',{**config,'enabled':False,'voice_enabled':False,'api_key':''})
    return {'deleted':True}

class AgentSqlConfig(BaseModel):
    model_config=ConfigDict(extra='forbid')
    server:str=Field(min_length=1,max_length=253)
    database:str=Field(default='AVANAgent',pattern=r'^AVANAgent$')
    username:str=Field(default='AVAN_AgentApp',pattern=r'^AVAN_AgentApp$')
    password:str=Field(min_length=1,max_length=512)
    trust_server_certificate:bool=False

class AgentConnectionSave(BaseModel):
    model_config=ConfigDict(extra='forbid')
    connection_id:str|None=Field(default=None,max_length=24,pattern=r'^(?:[a-f0-9]{24}|legacy)$')
    name:str=Field(min_length=1,max_length=100)
    server:str=Field(min_length=1,max_length=253)
    password:str=Field(default='',max_length=512)
    trust_server_certificate:bool=False

class AgentConnectionSelect(BaseModel):
    model_config=ConfigDict(extra='forbid')
    connection_id:str=Field(min_length=1,max_length=24,pattern=r'^(?:bundled|[a-f0-9]{24}|legacy)$')

class AgentConnectionDisconnect(BaseModel):
    model_config=ConfigDict(extra='forbid')
    confirmation:str=Field(pattern=r'^DISCONNECT$')

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
    from .agent_connections import save_external,activate
    connection_id=save_external(name='SQL Server خارجی '+body.server,
        config=body.model_dump())
    activate(connection_id)
    return {**result,'saved':True,'connection_id':connection_id}


@router.get('/api/agent-db/connections')
def agent_database_connections(session=Depends(_ready)):
    from .agent_connections import public_status
    return public_status()


@router.post('/api/agent-db/connections/save')
def save_agent_database_connection(body:AgentConnectionSave,session=Depends(_ready)):
    from .agent_connections import save_external,ConnectionCatalogError
    config={'server':body.server,'database':'AVANAgent','username':'AVAN_AgentApp',
        'password':body.password,'trust_server_certificate':body.trust_server_certificate}
    try:
        connection_id=save_external(name=body.name,config=config,
            connection_id=body.connection_id)
        return {'saved':True,'connection_id':connection_id,'active':False}
    except ConnectionCatalogError as exc:
        detail=('برای تغییر نشانی SQL Server رمز تازهٔ AVAN_AgentApp را وارد کنید.'
                if 'requires a new' in str(exc) else 'اتصال قابل ذخیره یا ویرایش نیست.')
        raise HTTPException(409,detail)
    except Exception:
        raise HTTPException(503,'اتصال جدید معتبر نیست؛ نشانی، رمز، TLS و ساختار AVANAgent بررسی شود.')


@router.post('/api/agent-db/connections/activate')
def activate_agent_database_connection(body:AgentConnectionSelect,session=Depends(_ready)):
    from .agent_connections import activate,ConnectionCatalogError
    try:
        row=activate(body.connection_id)
        return {'activated':True,'connection_id':body.connection_id,'name':row.get('name')}
    except ConnectionCatalogError:
        raise HTTPException(404,'اتصال انتخاب‌شده وجود ندارد.')
    except Exception:
        raise HTTPException(503,'اتصال انتخاب‌شده در دسترس یا دارای سطح دسترسی معتبر نیست.')


@router.post('/api/agent-db/connections/check')
def check_saved_agent_database_connection(body:AgentConnectionSelect,session=Depends(_ready)):
    from .agent_connections import check_saved,ConnectionCatalogError
    try:
        result=check_saved(body.connection_id)
        return {**result,'connection_id':body.connection_id}
    except ConnectionCatalogError:
        raise HTTPException(404,'اتصال انتخاب‌شده وجود ندارد.')
    except Exception:
        raise HTTPException(503,'اتصال انتخاب‌شده در دسترس یا دارای سطح دسترسی معتبر نیست.')


@router.post('/api/agent-db/connections/disconnect')
def disconnect_agent_database_connection(body:AgentConnectionDisconnect,session=Depends(_ready)):
    from .agent_connections import disconnect
    disconnect()
    return {'disconnected':True}


@router.post('/api/agent-db/connections/delete')
def delete_agent_database_connection(body:AgentConnectionSelect,session=Depends(_ready)):
    from .agent_connections import delete,ConnectionCatalogError
    try:delete(body.connection_id)
    except ConnectionCatalogError:
        raise HTTPException(409,'اتصال داخلی یا اتصال فعال قابل حذف نیست؛ ابتدا اتصال دیگری را فعال کنید.')
    return {'deleted':True,'connection_id':body.connection_id}


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
                'expires_at':expiry,'remaining_days':days,'modules':payload['modules'],'license_id':payload['license_id'],
                'mode':payload.get('mode','licensed')}
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
