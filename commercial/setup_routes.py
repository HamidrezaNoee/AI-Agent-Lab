"""Host-local GodAdmin setup UI, authenticated separately from tenant content.

Only configuration and read-only connection diagnostics. No customer login,
SQL schema mutation or licensing bypass is granted by this control plane.
"""
from __future__ import annotations

from collections import defaultdict, deque
from datetime import datetime,timezone
from ipaddress import ip_address
from pathlib import Path
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
    expected=os.getenv("AVAN_PUBLIC_ORIGIN","http://127.0.0.1:8188").rstrip("/")
    if origin and origin.rstrip("/")!=expected:
        raise HTTPException(403,"منشأ درخواست معتبر نیست.")

def _prune():
    now=time.time()
    for sid,s in list(_sessions.items()):
        if s["expires"]<now:_sessions.pop(sid,None)

def _cookie(response,token:str):
    secure=os.getenv("AVAN_PUBLIC_ORIGIN","http://127.0.0.1:8188").startswith("https://")
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
            "configured":bool(setup.get_setting("sql") and setup.get_setting("oidc"))}

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

@router.post("/api/totp/enrollment")
def totp_enrollment(session=Depends(_required)):
    try:secret=setup.totp_enrollment()
    except setup.SetupError:raise HTTPException(403,"ابتدا رمز اولیه را تغییر دهید.")
    return {"secret":secret,"account":"godadmin","issuer":"AVAN"}

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


class SqlConfig(BaseModel):
    model_config=ConfigDict(extra="forbid")
    server:str=Field(min_length=1,max_length=250)
    database:str="EnterpriseProcess2"
    username:str="AVAN_Reader"
    password:str=Field(min_length=1,max_length=255)
    trust_server_certificate:bool=False

def _sql_connect(body:SqlConfig):
    if body.database!="EnterpriseProcess2" or body.username.casefold()!="avan_reader":
        raise HTTPException(422,"فقط EnterpriseProcess2 و حساب AVAN_Reader مجاز است.")
    if any(c in body.server for c in ";{}\x00\r\n") or not body.server.strip():
        raise HTTPException(422,"نام SQL Server معتبر نیست.")
    from .production_store import _value
    import pyodbc
    try:
        con=pyodbc.connect(
            "DRIVER={ODBC Driver 17 for SQL Server};"+
            "SERVER="+_value(body.server)+";DATABASE=EnterpriseProcess2;"+
            "UID={AVAN_Reader};PWD="+_value(body.password)+";"+
            "Encrypt=yes;TrustServerCertificate="+
            ("yes" if body.trust_server_certificate else "no")+";Connection Timeout=8;",
            timeout=8,autocommit=True,
        )
        cur=con.cursor()
        cur.execute("SELECT DB_NAME(),OBJECT_ID(N'MTG.Meeting',N'U'),OBJECT_ID(N'AVAN.UserAccess',N'U')")
        info=cur.fetchone()
        return con,info
    except Exception:
        raise HTTPException(503,
            "اتصال SQL برقرار نشد. حساب محدود، پورت، گواهی TLS و اسکریپت‌های دیتابیس بررسی شوند.")

@router.post("/api/sql/check")
def sql_check(body:SqlConfig,session=Depends(_ready)):
    con,info=_sql_connect(body)
    try:
        if str(info[0])!="EnterpriseProcess2" or info[1] is None:
            raise HTTPException(409,"ساختار جداول MTG در بانک مورد انتظار وجود ندارد.")
        return {"connected":True,"database":str(info[0]),
                "mtg_present":info[1] is not None,
                "avan_schema_present":info[2] is not None}
    finally:con.close()

@router.post("/api/sql/save")
def sql_save(body:SqlConfig,session=Depends(_ready)):
    con,info=_sql_connect(body)
    try:
        if str(info[0])!="EnterpriseProcess2" or info[1] is None:
            raise HTTPException(409,"جداول اصلی MTG باید پیش از ذخیره موجود باشند.")
        setup.put_setting("sql",body.model_dump())
    finally:con.close()
    return {"saved":True,"database":"EnterpriseProcess2"}


class OidcConfig(BaseModel):
    model_config=ConfigDict(extra="forbid")
    issuer:str=Field(min_length=12,max_length=400)
    audience:str=Field(min_length=1,max_length=250)
    jwks_url:str=Field(min_length=12,max_length=500)
    client_id:str=Field(min_length=1,max_length=250)
    client_secret:str=Field(min_length=16,max_length=4096)

def _oidc_check(config:OidcConfig):
    issuer=config.issuer.rstrip("/")
    u=urlsplit(issuer)
    cert=urlsplit(config.jwks_url)
    if (u.scheme!="https" or not u.hostname or u.username or u.password
        or u.query or u.fragment or not re.fullmatch(r"/realms/[A-Za-z0-9_-]+",u.path)
        or cert.scheme!="https" or cert.netloc!=u.netloc
        or config.jwks_url!=issuer+"/protocol/openid-connect/certs"):
        raise HTTPException(422,"آدرس‌های هویت باید HTTPS و متعلق به یک Realm مورد تأیید باشند.")
    discovery=issuer+"/.well-known/openid-configuration"
    try:
        with httpx.Client(timeout=7,follow_redirects=False,trust_env=False) as http:
            response=http.get(discovery)
            response.raise_for_status()
            if len(response.content)>40000:raise ValueError("Oversize discovery response")
            data=response.json()
            if (data.get("issuer")!=issuer or
                data.get("authorization_endpoint")!=issuer+"/protocol/openid-connect/auth" or
                data.get("token_endpoint")!=issuer+"/protocol/openid-connect/token" or
                data.get("jwks_uri")!=config.jwks_url):
                raise ValueError("IdP metadata realm mismatch")
            keys=http.get(config.jwks_url)
            keys.raise_for_status()
            if len(keys.content)>200000 or not isinstance(keys.json().get("keys"),list):
                raise ValueError("JWKS keys not present")
    except Exception:
        raise HTTPException(503,"تأیید امن تنظیمات Realm و کلیدهای امضای هویت انجام نشد.")
    return issuer

@router.post("/api/oidc/check")
def oidc_check(body:OidcConfig,session=Depends(_ready)):
    issuer=_oidc_check(body)
    return {"connected":True,"issuer":issuer}

@router.post("/api/oidc/save")
def oidc_save(body:OidcConfig,session=Depends(_ready)):
    issuer=_oidc_check(body)
    payload=body.model_dump()
    payload["issuer"]=issuer
    setup.put_setting("oidc",payload)
    return {"saved":True,"issuer":issuer}

class PMConfig(BaseModel):
    model_config=ConfigDict(extra="forbid")
    base_url:str=Field(min_length=12,max_length=500)
    workspace:str=Field(min_length=1,max_length=48)
    bearer_token:str=Field(min_length=8,max_length=8192)

def _pm_check(config:PMConfig)->int:
    base=config.base_url.rstrip("/")
    parsed=urlsplit(base)
    if (parsed.scheme!="https" or not parsed.hostname or
        parsed.username or parsed.password or parsed.query or parsed.fragment or
        not re.fullmatch("[A-Za-z0-9_-]{1,48}",config.workspace)):
        raise HTTPException(422,"اتصال ProcessMaker باید HTTPS و Workspace معتبر داشته باشد.")
    url=base+"/api/1.0/"+config.workspace+"/users?status=all&start=0&limit=1"
    try:
        with httpx.Client(timeout=8,follow_redirects=False,trust_env=False) as http:
            response=http.get(url,headers={"Authorization":"Bearer "+config.bearer_token,
                                           "Accept":"application/json"})
            response.raise_for_status()
            if len(response.content)>20000 or not isinstance(response.json(),(list,dict)):
                raise ValueError("Unexpected ProcessMaker directory response")
        return response.status_code
    except Exception:
        raise HTTPException(503,"دسترسی فقط‌خواندنی به کاربران ProcessMaker تأیید نشد.")

@router.post("/api/processmaker/check")
def pm_check(body:PMConfig,session=Depends(_ready)):
    _pm_check(body)
    return {"connected":True,"read_only":True}

@router.post("/api/processmaker/save")
def pm_save(body:PMConfig,session=Depends(_ready)):
    _pm_check(body)
    setup.put_setting("processmaker",body.model_dump())
    return {"saved":True,"note":"اتصال تأیید شد؛ همگام‌سازی کاربران هنوز به تأیید هویت‌نامه و سیاست ابطال دسترسی نیاز دارد."}

class PublicKey(BaseModel):
    model_config=ConfigDict(extra="forbid")
    pem:str=Field(min_length=100,max_length=10000)

@router.post("/api/license/public-key")
def public_key(body:PublicKey,session=Depends(_ready)):
    try:setup.install_public_pem(body.pem.encode("ascii"))
    except (setup.SetupError,UnicodeEncodeError):
        raise HTTPException(400,"کلید عمومی ناشر باید ECDSA P-256 و معتبر باشد.")
    return {"saved":True,"private_key_imported":False}
