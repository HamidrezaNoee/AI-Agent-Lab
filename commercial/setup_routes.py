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
from uuid import UUID
import hmac
import os
import re
import secrets
import time

import httpx
from fastapi import APIRouter, HTTPException, Request, Depends, Response
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
    # Remove the legacy /admin-scoped cookie before issuing the unified
    # workspace cookie. Otherwise browsers can send two cookies with the same
    # name and keep an upgraded installation on the old admin-only session.
    response.delete_cookie("avan_godadmin",path="/admin")
    response.set_cookie("avan_godadmin",token,httponly=True,secure=secure,
                        samesite="strict",path="/",max_age=1800)

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

def bootstrap_workspace_session(request:Request):
    """Return a fully-MFA bootstrap GodAdmin session for the unified shell.

    This grants system-management navigation only. It never creates an
    organizational Principal and therefore cannot authorize customer data.
    """
    if setup.godadmin_identity():
        return None
    _local(request);_prune()
    sid=request.cookies.get("avan_godadmin","")
    row=_sessions.get(sid)
    if not row:
        return None
    state=setup.password_state()
    if not state["changed"] or not state["totp"] or not row.get("mfa"):
        return None
    row["expires"]=time.time()+1800
    return sid,row



@router.get("/")
def admin_home(request:Request):
    _local(request)
    if setup.godadmin_identity() and request.query_params.get("embedded")!="1":
        from fastapi.responses import RedirectResponse
        return RedirectResponse("/",status_code=303)
    return FileResponse(WEB/"index.html",media_type="text/html; charset=utf-8")

@router.get("/assets/app.css")
def admin_css(request:Request):
    _local(request)
    return FileResponse(WEB/"app.css",media_type="text/css; charset=utf-8")

@router.get("/assets/app.js")
def admin_js(request:Request):
    _local(request)
    return FileResponse(WEB/"app.js",media_type="text/javascript; charset=utf-8")

@router.get("/assets/login-scene.js")
def admin_login_scene_js(request:Request):
    _local(request)
    return FileResponse(WEB/"login-scene.js",media_type="text/javascript; charset=utf-8")


@router.get("/assets/login-scene.css")
def admin_login_scene_css(request:Request):
    _local(request)
    return FileResponse(WEB/"login-scene.css",media_type="text/css; charset=utf-8")

_LOGIN_SCENE_DATA={"boardroom-v5.webp","globe-v5.webp"}

@router.get("/assets/scene-data/{name}")
def admin_login_scene_data(name:str,request:Request):
    _local(request)
    if name not in _LOGIN_SCENE_DATA:
        raise HTTPException(404,"Login scene asset not found")
    return FileResponse(WEB/"scene-data"/name,media_type="image/webp",
                        headers={"Cache-Control":"public, max-age=86400"})


@router.get("/help/")
def admin_help(request:Request):
    _local(request)
    return FileResponse(WEB/"help.html",media_type="text/html; charset=utf-8")


@router.get("/assets/help.css")
def admin_help_css(request:Request):
    _local(request)
    return FileResponse(WEB/"help.css",media_type="text/css; charset=utf-8")


@router.get("/assets/help.js")
def admin_help_js(request:Request):
    _local(request)
    return FileResponse(WEB/"help.js",media_type="text/javascript; charset=utf-8")


@router.get("/api/captcha/config")
def captcha_config(request:Request):
    _local(request)
    from .turnstile import public_config,TurnstileUnavailable
    try:return public_config("avan-bootstrap-login")
    except TurnstileUnavailable:
        raise HTTPException(503,"سرویس ضدربات داخلی آوان در دسترس نیست.")

@router.get("/api/state")
def state(request:Request,response:Response):
    _local(request)
    _prune()
    bound=bool(setup.godadmin_identity())
    if bound:
        try:
            _,session=_required(request)
        except HTTPException:
            session=None
    else:
        sid=request.cookies.get("avan_godadmin","")
        session=_sessions.get(sid)
        if session and sid:
            # Transparent migration for browsers that still hold the legacy
            # /admin-scoped cookie from older AVAN builds.
            _cookie(response,sid)
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
    local_username=hmac.compare_digest(body.username.encode(),setup.godadmin_username().encode())
    if not local_username and state['changed'] and state['totp'] and setup.get_setting('oidc'):
        # A stale /admin/ tab is not the organizational password verifier.
        # Do not issue a session or forward the submitted password to the IdP.
        return JSONResponse({'authenticated':False,'redirect':'/auth/login'})
    valid=(local_username and
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
        if existing:
            response.delete_cookie("avan_godadmin",path="/")
            response.delete_cookie("avan_godadmin",path="/admin")
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

class GodAdminCredentials(BaseModel):
    model_config=ConfigDict(extra='forbid')
    username:str=Field(min_length=3,max_length=40,pattern=r'^[A-Za-z0-9_.@-]+$')
    current:str=Field(min_length=1,max_length=512)
    updated:str=Field(default='',max_length=128)
    otp:str=Field(pattern=r'^[0-9]{6}$')

@router.post('/api/identity/godadmin-credentials')
def godadmin_credentials(body:GodAdminCredentials,session=Depends(_ready)):
    try:setup.update_godadmin_account(body.username,body.current,body.updated,body.otp)
    except setup.SetupError:raise HTTPException(400,'نام کاربری، رمز فعلی، رمز جدید یا کد Authenticator معتبر نیست؛ اگر هویت سازمانی متصل است ابتدا انتقال محلی را انجام دهید.')
    _sessions.clear();_pending_mfa.clear()
    response=JSONResponse({'updated':True,'login_again':True})
    response.delete_cookie('avan_godadmin',path='/');response.delete_cookie('avan_godadmin',path='/admin')
    return response

@router.post("/api/change-password")
def change_password(body:NewPassword,session=Depends(_required)):
    try:setup.change_password(body.current,body.updated)
    except setup.SetupError:raise HTTPException(400,"رمز فعلی یا رمز جدید معتبر نیست.")
    # Revoke every previously issued session, including the current one.
    _sessions.clear()
    _pending_mfa.clear()
    response=JSONResponse({"password_changed":True,"login_again":True})
    response.delete_cookie("avan_godadmin",path="/")
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
    response.delete_cookie("avan_godadmin",path="/")
    response.delete_cookie("avan_godadmin",path="/admin")
    return response

@router.post("/api/logout")
def logout(session=Depends(_required)):
    if setup.godadmin_identity():
        raise HTTPException(409,"برای خروج از حساب سازمانی از خروج اصلی آوان استفاده کنید.")
    sid,_=session
    _sessions.pop(sid,None)
    response=JSONResponse({"signed_out":True})
    response.delete_cookie("avan_godadmin",path="/")
    response.delete_cookie("avan_godadmin",path="/admin")
    return response

@router.get("/api/heartbeat")
def admin_heartbeat(session=Depends(_ready)):
    return {"active":True}

@router.get("/api/settings")
def settings(session=Depends(_ready)):
    return setup.masked_settings()


class AppearanceElement(BaseModel):
    model_config=ConfigDict(extra="forbid")
    id:str=Field(min_length=1,max_length=40)
    enabled:bool=True
    title:str=Field(min_length=1,max_length=80)
    subtitle:str=Field(default="",max_length=140)
    description:str=Field(default="",max_length=600)
    tags:list[str]=Field(default_factory=list,max_length=8)
    svg:str=Field(min_length=1,max_length=5000)
    accent:str=Field(default="#63ECFF",min_length=7,max_length=7)
    radius:float=1.2
    ellipse:float=0.7
    angle:float=0.0
    speed:float=0.00015
    size:int=0
    hover_scale:float=0.0
    glow:float=1.0
    opacity:float=1.0
    card_side:str=Field(default="auto",max_length=10)
    label_mode:str=Field(default="inherit",max_length=12)


class AppearanceConfig(BaseModel):
    model_config=ConfigDict(extra="forbid")
    version:int=5
    background_image:str=Field(default="",max_length=8_000_000)
    background_fit:str=Field(default="cover",max_length=20)
    background_position_x:float=50
    background_position_y:float=50
    background_brightness:float=1.12
    background_contrast:float=1.08
    background_saturation:float=1.08
    background_blur:float=0.0
    background_dim:float=0.03
    overlay_color:str=Field(default="#031522",min_length=7,max_length=7)
    overlay_opacity:float=0.05
    background_parallax:float=6.0
    globe_image:str=Field(default="",max_length=8_000_000)
    globe_visible:bool=True
    globe_x:float=29.0
    globe_y:float=44.0
    globe_scale:float=1.22
    globe_opacity:float=1.0
    globe_brightness:float=1.32
    globe_contrast:float=1.10
    globe_saturation:float=1.22
    globe_hue:float=0.0
    globe_glow:float=1.30
    globe_wobble:float=1.0
    globe_rotation_speed:float=1.0
    globe_point_density:float=1.0
    globe_point_size:float=1.0
    globe_point_opacity:float=1.0
    node_size:int=70
    node_opacity:float=1.0
    node_border_width:float=1.0
    node_glow:float=1.0
    hover_scale:float=1.24
    hover_duration:int=180
    hover_mode:str=Field(default="card",max_length=20)
    pause_on_hover:bool=True
    login_auto_collapse:bool=False
    show_orbits:bool=True
    show_idle_cards:bool=True
    orbit_speed:float=0.22
    orbit_mode:str=Field(default="orbit",max_length=10)
    orbit_line_width:float=1.15
    orbit_opacity:float=0.78
    orbit_glow:float=1.0
    orbit_primary:str=Field(default="#50EAF7",min_length=7,max_length=7)
    orbit_secondary:str=Field(default="#FF7053",min_length=7,max_length=7)
    card_width:int=176
    card_opacity:float=0.94
    elements:list[AppearanceElement]=Field(default_factory=list,max_length=12)


@router.get("/api/appearance/public")
def appearance_public(request:Request):
    _local(request)
    from .login_appearance import current
    return current()


@router.get("/api/appearance")
def appearance_get(session=Depends(_ready)):
    from .login_appearance import current
    return current()


@router.post("/api/appearance/save")
def appearance_save(body:AppearanceConfig,session=Depends(_ready)):
    from .login_appearance import save,AppearanceError
    try:return save(body.model_dump())
    except AppearanceError as exc:raise HTTPException(422,str(exc))


@router.post("/api/appearance/reset")
def appearance_reset(session=Depends(_ready)):
    from .login_appearance import reset
    return reset()


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


def _require_source_without_user_bindings(source_id:str):
    """Do not orphan AVAN↔BPMS identity mappings by deleting their source."""
    from .user_bpms_bindings import list_bindings
    try:
        bindings=[b for b in list_bindings() if b.get("source_id")==source_id]
    except Exception:
        raise HTTPException(503,"وضعیت اتصال کاربران قابل بررسی نیست؛ حذف BPMS متوقف شد.")
    if bindings:
        raise HTTPException(
            409,
            "این BPMS هنوز به کاربر AVAN متصل است؛ ابتدا همه Bindingهای آن را در «سازمان و دسترسی» قطع کنید."
        )


@router.post("/api/bpms/connections/delete")
def bpms_delete(body:BPMSID,session=Depends(_ready)):
    _require_source_without_user_bindings(body.source_id)
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
    response.delete_cookie("avan_godadmin",path="/")
    response.delete_cookie("avan_godadmin",path="/admin")
    return response

class GodAdminAccount(BaseModel):
    model_config=ConfigDict(extra="forbid")
    username:str=Field(min_length=3,max_length=80,pattern=r"^[A-Za-z0-9_.@-]+$")
    email:str=Field(min_length=3,max_length=240,pattern=r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
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
    try:
        setup.bind_godadmin_identity(company["tenant_id"],subject)
    except setup.SetupError:
        raise HTTPException(409,"حساب سازمانی ساخته شد اما اتصال GodAdmin کامل نشد؛ وضعیت هویت را بررسی کنید.")
    _sessions.clear()
    _pending_mfa.clear()
    setup.audit("GODADMIN_OIDC_ACCOUNT_CREATED_AND_BOUND")
    response=JSONResponse({
        "created":True,
        "bound":True,
        "subject":subject,
        "login_url":"/auth/login",
        "next":"انتقال GodAdmin به هویت سازمانی کامل شد. از ورود مشترک آوان استفاده کنید."
    })
    response.delete_cookie("avan_godadmin",path="/")
    response.delete_cookie("avan_godadmin",path="/admin")
    return response


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


class OrganizationSave(BaseModel):
    model_config=ConfigDict(extra="forbid")
    tenant_id:str|None=Field(default=None,max_length=36)
    company_name:str=Field(min_length=2,max_length=200)
    enabled:bool=True


class OrganizationEnabled(BaseModel):
    model_config=ConfigDict(extra="forbid")
    tenant_id:str=Field(min_length=36,max_length=36)
    enabled:bool


def _organizations_state()->dict:
    """Read the AVAN organization registry and surface legacy company as row zero.

    The legacy single-company setting remains the compatibility organization until
    tenant-scoped users/licenses/BPMS connections are fully migrated.
    """
    import uuid
    raw=setup.get_setting("organizations") or {}
    rows=raw.get("organizations") if isinstance(raw,dict) else None
    rows=[dict(x) for x in rows if isinstance(x,dict)] if isinstance(rows,list) else []
    primary=raw.get("primary_tenant_id") if isinstance(raw,dict) else None
    legacy=setup.get_setting("company") or {}
    legacy_id=legacy.get("tenant_id")
    legacy_name=legacy.get("company_name")
    if legacy_id and not any(x.get("tenant_id")==legacy_id for x in rows):
        try:legacy_id=str(uuid.UUID(str(legacy_id)))
        except ValueError:legacy_id=None
        if legacy_id:
            now=datetime.now(timezone.utc).isoformat()
            rows.insert(0,{
                "tenant_id":legacy_id,
                "company_name":str(legacy_name or "سازمان فعلی")[:200],
                "enabled":True,
                "created_utc":now,
                "updated_utc":now,
            })
            primary=primary or legacy_id
    if not primary and rows:
        primary=rows[0].get("tenant_id")
    return {"primary_tenant_id":primary,"organizations":rows}


def _save_organizations(state:dict)->None:
    setup.put_setting("organizations",{
        "primary_tenant_id":state.get("primary_tenant_id"),
        "organizations":state.get("organizations") or [],
    })


@router.get("/api/organizations")
def organizations_get(session=Depends(_ready)):
    state=_organizations_state()
    return {
        "primary_tenant_id":state.get("primary_tenant_id"),
        "organizations":[
            {
                "tenant_id":row.get("tenant_id"),
                "company_name":row.get("company_name"),
                "enabled":bool(row.get("enabled",True)),
                "is_primary":row.get("tenant_id")==state.get("primary_tenant_id"),
                "created_utc":row.get("created_utc"),
                "updated_utc":row.get("updated_utc"),
            }
            for row in state["organizations"]
        ],
    }


@router.post("/api/organizations/save")
def organization_save(body:OrganizationSave,session=Depends(_ready)):
    import uuid
    state=_organizations_state()
    rows=state["organizations"]
    now=datetime.now(timezone.utc).isoformat()
    name=body.company_name.strip()
    if len(name)<2:
        raise HTTPException(422,"نام رسمی سازمان باید حداقل دو کاراکتر باشد.")
    if body.tenant_id:
        try:tenant_id=str(uuid.UUID(body.tenant_id))
        except ValueError:raise HTTPException(422,"Tenant ID سازمان معتبر نیست.")
        row=next((x for x in rows if x.get("tenant_id")==tenant_id),None)
        if not row:raise HTTPException(404,"سازمان پیدا نشد.")
        row["company_name"]=name
        row["enabled"]=body.enabled
        row["updated_utc"]=now
        created=False
    else:
        tenant_id=str(uuid.uuid4())
        rows.append({
            "tenant_id":tenant_id,
            "company_name":name,
            "enabled":body.enabled,
            "created_utc":now,
            "updated_utc":now,
        })
        if not state.get("primary_tenant_id"):
            state["primary_tenant_id"]=tenant_id
        created=True

    # Preserve the original single-tenant runtime contract until the remaining
    # stores are tenant-scoped. Editing the compatibility organization updates it.
    if tenant_id==state.get("primary_tenant_id"):
        setup.put_setting("company",{"tenant_id":tenant_id,"company_name":name})
    _save_organizations(state)
    setup.audit("ORGANIZATION_CREATED" if created else "ORGANIZATION_UPDATED")
    return {"saved":True,"created":created,"tenant_id":tenant_id,
            "company_name":name,"enabled":body.enabled,
            "is_primary":tenant_id==state.get("primary_tenant_id")}


@router.post("/api/organizations/enabled")
def organization_enabled(body:OrganizationEnabled,session=Depends(_ready)):
    import uuid
    try:tenant_id=str(uuid.UUID(body.tenant_id))
    except ValueError:raise HTTPException(422,"Tenant ID سازمان معتبر نیست.")
    state=_organizations_state()
    row=next((x for x in state["organizations"] if x.get("tenant_id")==tenant_id),None)
    if not row:raise HTTPException(404,"سازمان پیدا نشد.")
    row["enabled"]=body.enabled
    row["updated_utc"]=datetime.now(timezone.utc).isoformat()
    _save_organizations(state)
    setup.audit("ORGANIZATION_ENABLED" if body.enabled else "ORGANIZATION_DISABLED")
    return {"saved":True,"tenant_id":tenant_id,"enabled":body.enabled}


# Backward-compatible single-company endpoints. New UI uses /api/organizations.
@router.post("/api/company/save")
def company_save(body:CompanyConfig,session=Depends(_ready)):
    state=_organizations_state()
    primary=state.get("primary_tenant_id")
    saved=organization_save(OrganizationSave(
        tenant_id=primary,company_name=body.company_name,enabled=True
    ),session) if primary else organization_save(OrganizationSave(
        company_name=body.company_name,enabled=True
    ),session)
    return {"saved":True,"tenant_id":saved["tenant_id"],
            "company_name":saved["company_name"]}


@router.get("/api/company")
def company_get(session=Depends(_ready)):
    state=_organizations_state()
    primary=state.get("primary_tenant_id")
    current=next((x for x in state["organizations"] if x.get("tenant_id")==primary),None)
    return {"tenant_id":current.get("tenant_id") if current else None,
            "company_name":current.get("company_name") if current else None}


@router.get("/api/identity/status")
def identity_status(session=Depends(_ready)):
    config=setup.get_setting("oidc") or {}
    issuer=str(config.get("issuer","")).rstrip("/")
    managed=config.get("managed_by_product") is True
    identity=setup.godadmin_identity() or {}
    public={
        "managed_by_product":managed,
        "connected":False,
        "realm":"avan",
        "issuer":issuer or None,
        "protocol":"OIDC",
        "mfa":"TOTP / Authenticator",
        "godadmin_bound":bool(identity),
        "godadmin_username":setup.godadmin_username(),
        "godadmin_local":not bool(identity),
        "godadmin_subject":identity.get("subject"),
        "godadmin_tenant_id":identity.get("tenant_id"),
        "customer_secret_entry_required":False,
    }
    if not managed:
        return {**public,"detail":"زیرساخت هویت داخلی آوان آماده نیست."}
    if not issuer:
        return {**public,"detail":"OIDC Issuer تنظیم نشده است."}
    try:
        with httpx.Client(timeout=7,follow_redirects=False,trust_env=False) as http:
            response=http.get(issuer+"/.well-known/openid-configuration")
            response.raise_for_status()
            data=response.json()
            if data.get("issuer")!=issuer:
                raise ValueError("issuer mismatch")
        return {**public,"connected":True,"detail":None}
    except Exception:
        return {**public,"detail":"سرویس هویت داخلی آوان در دسترس نیست."}


class PMConfig(BaseModel):
    model_config=ConfigDict(extra="forbid")
    base_url:str=Field(min_length=12,max_length=500)
    workspace:str=Field(min_length=1,max_length=48)
    bearer_token:str=Field(default="",max_length=8192)
    oauth_client_id:str=Field(default="",max_length=256)
    oauth_client_secret:str=Field(default="",max_length=4096)
    refresh_token:str=Field(default="",max_length=8192)
    access_token_expires_at:float|None=None
    token_managed:bool=False


class PMOAuthConnect(BaseModel):
    model_config=ConfigDict(extra="forbid")
    base_url:str=Field(min_length=12,max_length=500)
    workspace:str=Field(min_length=1,max_length=48)
    client_id:str=Field(min_length=1,max_length=256)
    client_secret:str=Field(default="",max_length=4096)
    username:str=Field(min_length=1,max_length=160)
    password:str=Field(min_length=1,max_length=512)


def _pm_target(base_url:str,workspace:str)->tuple[str,str]:
    base=base_url.rstrip("/")
    parsed=urlsplit(base)
    if (not parsed.hostname or parsed.username or parsed.password or
        parsed.query or parsed.fragment or parsed.path not in ("","/") or
        not re.fullmatch(r"[A-Za-z0-9_-]{1,48}",workspace)):
        raise HTTPException(422,"نشانی اصلی ProcessMaker یا Workspace معتبر نیست.")
    local_lab_http=(os.getenv("AVAN_PM_ALLOW_LOCAL_HTTP")=="1" and
                    parsed.scheme=="http" and
                    parsed.hostname.lower()=="host.docker.internal" and
                    parsed.port in (84,443))
    if parsed.scheme!="https" and not local_lab_http:
        raise HTTPException(422,"در نصب آزمایشی آدرس http://host.docker.internal:443 یا :84 را مطابق پورت واقعی ProcessMaker وارد کنید؛ در نصب عملیاتی HTTPS الزامی است.")
    return base,workspace


def _pm_directory_check(base_url:str,workspace:str,access_token:str)->int:
    base,workspace=_pm_target(base_url,workspace)
    if (not isinstance(access_token,str) or len(access_token.strip())<8 or
        len(access_token)>8192 or any(c in access_token for c in ("\r","\n","\x00"))):
        raise HTTPException(422,"توکن ProcessMaker معتبر نیست.")
    url=base+"/api/1.0/"+workspace+"/users"
    try:
        with httpx.Client(timeout=8,follow_redirects=False,trust_env=False) as http:
            response=http.get(url,params={"status":"all","start":0,"limit":1},
                              headers={"Authorization":"Bearer "+access_token.strip(),
                                       "Accept":"application/json"})
            if response.status_code in (401,403):
                raise HTTPException(401,"توکن ProcessMaker نامعتبر، منقضی یا فاقد مجوز مشاهده کاربران است.")
            if response.status_code!=200:
                raise HTTPException(503,"API کاربران ProcessMaker پاسخ HTTP "+str(response.status_code)+" داد؛ آدرس و Workspace را بررسی کنید.")
            if len(response.content)>20000 or not isinstance(response.json(),(list,dict)):
                raise HTTPException(502,"پاسخ API کاربران ProcessMaker معتبر نیست.")
        return response.status_code
    except httpx.RequestError:
        raise HTTPException(503,"اتصال شبکه یا گواهی TLS ProcessMaker قابل تأیید نیست؛ نشانی سرویس را بررسی کنید.")
    except ValueError:
        raise HTTPException(502,"پاسخ JSON کاربران ProcessMaker نامعتبر است.")


def _pm_oauth_token(base_url:str,workspace:str,payload:dict)->dict:
    base,workspace=_pm_target(base_url,workspace)
    url=base+"/"+workspace+"/oauth2/token"
    try:
        with httpx.Client(timeout=10,follow_redirects=False,trust_env=False) as http:
            response=http.post(url,data=payload,headers={
                "Accept":"application/json",
                "Content-Type":"application/x-www-form-urlencoded",
            })
            if response.status_code in (400,401,403):
                raise HTTPException(401,"ProcessMaker اطلاعات OAuth یا حساب کاربری را نپذیرفت؛ Client ID، Client Secret، نام کاربری و رمز را بررسی کنید.")
            if response.status_code!=200:
                raise HTTPException(503,"Token Endpoint پروسس‌میکر پاسخ HTTP "+str(response.status_code)+" داد.")
            if len(response.content)>32768:
                raise HTTPException(502,"پاسخ OAuth پروسس‌میکر بیش از حد بزرگ است.")
            result=response.json()
    except httpx.RequestError:
        raise HTTPException(503,"اتصال آوان به Token Endpoint پروسس‌میکر برقرار نیست.")
    except ValueError:
        raise HTTPException(502,"پاسخ OAuth پروسس‌میکر JSON معتبر نیست.")
    access=result.get("access_token")
    refresh=result.get("refresh_token")
    if (not isinstance(access,str) or not 8<=len(access)<=8192 or
        any(c in access for c in ("\r","\n","\x00"))):
        raise HTTPException(502,"ProcessMaker access_token معتبر برنگرداند.")
    if refresh is not None and (not isinstance(refresh,str) or len(refresh)>8192 or
                                any(c in refresh for c in ("\r","\n","\x00"))):
        raise HTTPException(502,"ProcessMaker refresh_token معتبر برنگرداند.")
    try:expires=max(30,min(int(result.get("expires_in") or 86400),31536000))
    except (TypeError,ValueError):expires=86400
    return {"access_token":access,"refresh_token":refresh or "",
            "expires_in":expires,"token_type":str(result.get("token_type") or "Bearer")}


def _pm_managed_config(base_url:str,workspace:str,client_id:str,client_secret:str,
                       tokens:dict,previous_refresh:str="")->dict:
    refresh=tokens.get("refresh_token") or previous_refresh
    if not refresh:
        raise HTTPException(502,"ProcessMaker refresh_token برنگرداند؛ برای تمدید خودکار باید Refresh Token فعال باشد.")
    return {
        "base_url":base_url.rstrip("/"),
        "workspace":workspace,
        "bearer_token":tokens["access_token"],
        "oauth_client_id":client_id,
        "oauth_client_secret":client_secret,
        "refresh_token":refresh,
        "access_token_expires_at":time.time()+int(tokens["expires_in"]),
        "token_managed":True,
    }


def _pm_refresh_saved(saved:dict)->dict:
    if not saved.get("token_managed"):
        raise HTTPException(409,"این اتصال با توکن دستی ثبت شده است؛ یک‌بار اتصال OAuth خودکار را انجام دهید.")
    client_id=str(saved.get("oauth_client_id") or "")
    client_secret=str(saved.get("oauth_client_secret") or "")
    refresh=str(saved.get("refresh_token") or "")
    if not client_id or not client_secret or not refresh:
        raise HTTPException(409,"اطلاعات تمدید خودکار ProcessMaker کامل نیست؛ اتصال OAuth را دوباره انجام دهید.")
    tokens=_pm_oauth_token(saved["base_url"],saved["workspace"],{
        "grant_type":"refresh_token",
        "client_id":client_id,
        "client_secret":client_secret,
        "refresh_token":refresh,
    })
    updated=_pm_managed_config(saved["base_url"],saved["workspace"],
                               client_id,client_secret,tokens,refresh)
    setup.put_setting("processmaker",updated)
    setup.audit("PROCESSMAKER_OAUTH_TOKEN_REFRESHED")
    return updated


def _pm_valid_saved(saved:dict)->dict:
    if not saved:
        raise HTTPException(404,"اتصال ProcessMaker هنوز ذخیره نشده است.")
    if saved.get("token_managed"):
        try:expires=float(saved.get("access_token_expires_at") or 0)
        except (TypeError,ValueError):expires=0
        if expires<=time.time()+90:
            return _pm_refresh_saved(saved)
    return saved


def _pm_check(config:PMConfig)->int:
    return _pm_directory_check(config.base_url,config.workspace,config.bearer_token)


@router.post("/api/processmaker/check")
def pm_check(body:PMConfig,session=Depends(_ready)):
    _pm_check(body)
    return {"connected":True,"directory_request":"GET",
            "account_role_not_restricted":True}


@router.post("/api/processmaker/check-saved")
def pm_check_saved(session=Depends(_ready)):
    saved=setup.get_setting("processmaker") or {}
    saved=_pm_valid_saved(saved)
    try:
        _pm_directory_check(saved["base_url"],saved["workspace"],saved.get("bearer_token",""))
    except HTTPException as exc:
        if exc.status_code==401 and saved.get("token_managed"):
            saved=_pm_refresh_saved(saved)
            _pm_directory_check(saved["base_url"],saved["workspace"],saved["bearer_token"])
        else:
            raise
    return {"connected":True,"directory_request":"GET",
            "token_managed":bool(saved.get("token_managed")),
            "expires_at":saved.get("access_token_expires_at")}


@router.post("/api/processmaker/save")
def pm_save(body:PMConfig,session=Depends(_ready)):
    _pm_check(body)
    setup.put_setting("processmaker",{
        "base_url":body.base_url.rstrip("/"),
        "workspace":body.workspace,
        "bearer_token":body.bearer_token,
        "token_managed":False,
    })
    return {"saved":True,"token_managed":False,
            "note":"توکن دستی ذخیره شد؛ برای تمدید خودکار از اتصال OAuth استفاده کنید."}


@router.post("/api/processmaker/oauth-connect")
def pm_oauth_connect(body:PMOAuthConnect,session=Depends(_ready)):
    client_secret=body.client_secret.strip()
    if not client_secret:
        previous=setup.get_setting("processmaker") or {}
        same=(str(previous.get("base_url","")).rstrip("/")==body.base_url.rstrip("/") and
              previous.get("workspace")==body.workspace and
              previous.get("oauth_client_id")==body.client_id)
        if same:
            client_secret=str(previous.get("oauth_client_secret") or "")
    if not client_secret:
        raise HTTPException(422,"Client Secret لازم است؛ فقط برای اتصال OAuth قبلی با همین Client ID می‌تواند خالی بماند.")
    tokens=_pm_oauth_token(body.base_url,body.workspace,{
        "grant_type":"password",
        "scope":"*",
        "client_id":body.client_id,
        "client_secret":client_secret,
        "username":body.username,
        "password":body.password,
    })
    config=_pm_managed_config(body.base_url,body.workspace,
                              body.client_id,client_secret,tokens)
    _pm_directory_check(config["base_url"],config["workspace"],config["bearer_token"])
    setup.put_setting("processmaker",config)
    setup.audit("PROCESSMAKER_OAUTH_CONNECTED")
    return {"saved":True,"connected":True,"token_managed":True,
            "expires_at":config["access_token_expires_at"],
            "password_stored":False,"refresh_token_stored":True}


@router.post("/api/processmaker/oauth-refresh")
def pm_oauth_refresh(session=Depends(_ready)):
    saved=setup.get_setting("processmaker") or {}
    refreshed=_pm_refresh_saved(saved)
    _pm_directory_check(refreshed["base_url"],refreshed["workspace"],
                        refreshed["bearer_token"])
    return {"connected":True,"token_managed":True,
            "expires_at":refreshed["access_token_expires_at"]}


@router.post("/api/processmaker/remove")
def pm_remove(body:RemoveConnection,session=Depends(_ready)):
    if body.confirmation!='REMOVE_PM_API':raise HTTPException(422,'تأیید حذف اتصال API معتبر نیست.')
    setup.put_setting('processmaker',{})
    return {'deleted':True}

class PMProfileSave(BaseModel):
    model_config=ConfigDict(extra="forbid")
    id:str|None=Field(default=None,pattern=r"^[0-9a-f]{24}$")
    name:str=Field(min_length=2,max_length=100)
    mysql_host:str=Field(min_length=1,max_length=253,pattern=r"^[A-Za-z0-9_.:-]+$")
    mysql_port:int=Field(default=3306,ge=1,le=65535)
    mysql_database:str=Field(default="bitnami_pm",pattern=r"^(?:wf_[A-Za-z0-9_]{1,48}|bitnami_pm)$")
    mysql_username:str=Field(min_length=1,max_length=128)
    mysql_password:str=Field(default="",max_length=512)
    mysql_tls:bool=False
    mysql_ca_pem:str=Field(default="",max_length=16000)
    mysql_timezone:str=Field(default="Asia/Tehran",max_length=80)
    oauth_base_url:str=Field(min_length=12,max_length=500)
    oauth_workspace:str=Field(min_length=1,max_length=48)
    oauth_client_id:str=Field(min_length=1,max_length=256)
    oauth_client_secret:str=Field(default="",max_length=4096)
    oauth_username:str=Field(default="",max_length=160)
    oauth_password:str=Field(default="",max_length=512)
    activate:bool=True


class BPMSCatalogRef(BaseModel):
    model_config=ConfigDict(extra="forbid")
    connection_type:Literal["processmaker","adapter"]
    id:str=Field(pattern=r"^[0-9a-f]{24}$")


class BPMSCatalogCopy(BPMSCatalogRef):
    name:str|None=Field(default=None,min_length=2,max_length=100)


def _pm_profiles_state()->dict:
    raw=setup.get_setting("processmaker_profiles") or {}
    profiles=raw.get("profiles") if isinstance(raw,dict) else None
    active_id=raw.get("active_id") if isinstance(raw,dict) else None
    if not isinstance(profiles,list):
        profiles=[]
    clean=[p for p in profiles if isinstance(p,dict) and
           re.fullmatch(r"[0-9a-f]{24}",str(p.get("id",""))) and
           isinstance(p.get("name"),str)]
    if not clean:
        legacy_mysql=setup.get_setting("mysql") or {}
        legacy_api=setup.get_setting("processmaker") or {}
        if legacy_mysql or legacy_api:
            identifier=secrets.token_hex(12)
            clean=[{"id":identifier,"name":"ProcessMaker اصلی",
                    "engine":"processmaker","mysql":legacy_mysql,"api":legacy_api}]
            active_id=identifier
            setup.put_setting("processmaker_profiles",
                              {"active_id":active_id,"profiles":clean})
            setup.audit("PROCESSMAKER_PROFILE_MIGRATED")
    if active_id and not any(p["id"]==active_id for p in clean):
        active_id=None
    return {"active_id":active_id,"profiles":clean}


def _pm_profiles_write(state:dict)->None:
    setup.put_setting("processmaker_profiles",{
        "active_id":state.get("active_id"),
        "profiles":state.get("profiles",[])
    })


def _pm_profile_public(profile:dict,active_id:str|None)->dict:
    mysql=profile.get("mysql") or {}
    api=profile.get("api") or {}
    return {
        "id":profile["id"],"name":profile["name"],
        "connection_type":"processmaker","engine":"processmaker",
        "active":profile["id"]==active_id,
        "mysql":{"host":mysql.get("host"),"port":mysql.get("port",3306),
                 "database":mysql.get("database"),"username":mysql.get("username"),
                 "tls":bool(mysql.get("tls")),"timezone":mysql.get("timezone","Asia/Tehran"),
                 "has_password":bool(mysql.get("password")),
                 "has_ca":bool(mysql.get("ca_pem"))},
        "oauth":{"base_url":api.get("base_url"),"workspace":api.get("workspace"),
                 "client_id":api.get("oauth_client_id"),
                 "token_managed":bool(api.get("token_managed")),
                 "expires_at":api.get("access_token_expires_at"),
                 "has_client_secret":bool(api.get("oauth_client_secret")),
                 "has_refresh_token":bool(api.get("refresh_token"))},
    }


def _pm_profile_activate(state:dict,profile:dict)->None:
    mysql=dict(profile.get("mysql") or {})
    api=dict(profile.get("api") or {})
    if not mysql or not api:
        raise HTTPException(409,"اتصال ProcessMaker کامل نیست.")
    setup.put_setting("mysql",mysql)
    setup.put_setting("processmaker",api)
    state["active_id"]=profile["id"]
    _pm_profiles_write(state)


def _pm_profile_refresh(profile:dict,state:dict)->dict:
    api=dict(profile.get("api") or {})
    if not api.get("token_managed"):
        raise HTTPException(409,"این اتصال ProcessMaker تمدید خودکار OAuth ندارد.")
    client_id=str(api.get("oauth_client_id") or "")
    client_secret=str(api.get("oauth_client_secret") or "")
    refresh=str(api.get("refresh_token") or "")
    if not client_id or not client_secret or not refresh:
        raise HTTPException(409,"اطلاعات Refresh Token این اتصال کامل نیست.")
    tokens=_pm_oauth_token(api["base_url"],api["workspace"],{
        "grant_type":"refresh_token","client_id":client_id,
        "client_secret":client_secret,"refresh_token":refresh,
    })
    updated=_pm_managed_config(api["base_url"],api["workspace"],
                               client_id,client_secret,tokens,refresh)
    profile["api"]=updated
    state["profiles"]=[profile if p["id"]==profile["id"] else p
                       for p in state["profiles"]]
    if state.get("active_id")==profile["id"]:
        setup.put_setting("processmaker",updated)
    _pm_profiles_write(state)
    setup.audit("PROCESSMAKER_PROFILE_TOKEN_REFRESHED")
    return profile


def _pm_profile_test(profile:dict,state:dict)->dict:
    mysql=profile.get("mysql") or {}
    api=profile.get("api") or {}
    if not mysql or not api:
        raise HTTPException(409,"تنظیمات اتصال ProcessMaker کامل نیست.")
    _mysql_check(MySQLConfig.model_validate(mysql))
    if api.get("token_managed"):
        try:expires=float(api.get("access_token_expires_at") or 0)
        except (TypeError,ValueError):expires=0
        if expires<=time.time()+90:
            profile=_pm_profile_refresh(profile,state)
            api=profile["api"]
    try:
        _pm_directory_check(api["base_url"],api["workspace"],api.get("bearer_token",""))
    except HTTPException as exc:
        if exc.status_code==401 and api.get("token_managed"):
            profile=_pm_profile_refresh(profile,state)
            api=profile["api"]
            _pm_directory_check(api["base_url"],api["workspace"],api["bearer_token"])
        else:
            raise
    return {"connected":True,"mysql":True,"oauth":True,
            "active":state.get("active_id")==profile["id"],
            "expires_at":api.get("access_token_expires_at")}


def _pm_refresh_config(api:dict)->dict:
    client_id=str(api.get("oauth_client_id") or "")
    client_secret=str(api.get("oauth_client_secret") or "")
    refresh=str(api.get("refresh_token") or "")
    if not client_id or not client_secret or not refresh:
        raise HTTPException(409,"اطلاعات Refresh Token این اتصال کامل نیست.")
    tokens=_pm_oauth_token(api["base_url"],api["workspace"],{
        "grant_type":"refresh_token","client_id":client_id,
        "client_secret":client_secret,"refresh_token":refresh,
    })
    return _pm_managed_config(api["base_url"],api["workspace"],
                              client_id,client_secret,tokens,refresh)


def _pm_profile_from_body(body:PMProfileSave,state:dict)->dict:
    previous=next((p for p in state["profiles"] if p["id"]==body.id),None) if body.id else None
    identifier=body.id or secrets.token_hex(12)
    if body.id and not previous:
        raise HTTPException(404,"اتصال ProcessMaker برای ویرایش پیدا نشد.")

    previous_mysql=(previous or {}).get("mysql") or {}
    mysql_password=body.mysql_password
    mysql_same=(previous_mysql.get("host")==body.mysql_host and
                int(previous_mysql.get("port") or 3306)==body.mysql_port and
                previous_mysql.get("database")==body.mysql_database and
                previous_mysql.get("username")==body.mysql_username)
    if not mysql_password and mysql_same:
        mysql_password=str(previous_mysql.get("password") or "")
    if not mysql_password:
        raise HTTPException(422,"رمز MySQL برای اتصال جدید یا تغییر مقصد لازم است.")
    mysql={
        "host":body.mysql_host,"port":body.mysql_port,
        "database":body.mysql_database,"username":body.mysql_username,
        "password":mysql_password,"tls":body.mysql_tls,
        "ca_pem":body.mysql_ca_pem or str(previous_mysql.get("ca_pem") or ""),
        "timezone":body.mysql_timezone,"enabled":True,
    }
    _mysql_check(MySQLConfig.model_validate(mysql))

    previous_api=(previous or {}).get("api") or {}
    same_oauth=(str(previous_api.get("base_url") or "").rstrip("/")==body.oauth_base_url.rstrip("/") and
                previous_api.get("workspace")==body.oauth_workspace and
                previous_api.get("oauth_client_id")==body.oauth_client_id)
    client_secret=body.oauth_client_secret.strip()
    if not client_secret and same_oauth:
        client_secret=str(previous_api.get("oauth_client_secret") or "")

    username=body.oauth_username.strip()
    password=body.oauth_password
    if bool(username)!=bool(password):
        raise HTTPException(422,"برای ساخت Token، نام کاربری و رمز ProcessMaker را با هم وارد کنید.")

    if username and password:
        if not client_secret:
            raise HTTPException(422,"Client Secret برای دریافت Token لازم است.")
        tokens=_pm_oauth_token(body.oauth_base_url,body.oauth_workspace,{
            "grant_type":"password","scope":"*",
            "client_id":body.oauth_client_id,
            "client_secret":client_secret,
            "username":username,"password":password,
        })
        api=_pm_managed_config(body.oauth_base_url,body.oauth_workspace,
                               body.oauth_client_id,client_secret,tokens)
    else:
        if not previous_api or not same_oauth:
            raise HTTPException(422,"برای اتصال جدید یا تغییر OAuth، نام کاربری و رمز ProcessMaker را وارد کنید.")
        api=dict(previous_api)
        if client_secret:
            api["oauth_client_secret"]=client_secret
        if api.get("token_managed"):
            try:expires=float(api.get("access_token_expires_at") or 0)
            except (TypeError,ValueError):expires=0
            if expires<=time.time()+90:
                api=_pm_refresh_config(api)

    try:
        _pm_directory_check(api["base_url"],api["workspace"],api.get("bearer_token",""))
    except HTTPException as exc:
        if exc.status_code==401 and api.get("token_managed"):
            api=_pm_refresh_config(api)
            _pm_directory_check(api["base_url"],api["workspace"],api["bearer_token"])
        else:
            raise
    return {"id":identifier,"name":body.name.strip(),
            "engine":"processmaker","mysql":mysql,"api":api}


@router.get("/api/bpms/catalog")
def bpms_catalog(session=Depends(_ready)):
    from .bpms_registry import sources
    state=_pm_profiles_state()
    native=[_pm_profile_public(p,state.get("active_id")) for p in state["profiles"]]
    adapters=[{**row,"connection_type":"adapter",
               "engine":row.get("engine","other"),"active":bool(row.get("enabled"))}
              for row in sources()]
    return {"connections":native+adapters,
            "types":[
                {"id":"processmaker","label":"ProcessMaker","native":True},
                {"id":"camunda","label":"Camunda","native":False},
                {"id":"appian","label":"Appian","native":False},
                {"id":"uipath","label":"UiPath","native":False},
                {"id":"servicenow","label":"ServiceNow","native":False},
                {"id":"other","label":"سایر / AVAN REST v1","native":False},
            ]}


@router.post("/api/bpms/processmaker/check")
def bpms_processmaker_check(body:PMProfileSave,session=Depends(_ready)):
    state=_pm_profiles_state()
    profile=_pm_profile_from_body(body,state)
    return {"connected":True,"mysql":True,"oauth":True,
            "name":profile["name"],"password_stored":False}


@router.post("/api/bpms/processmaker/save")
def bpms_processmaker_save(body:PMProfileSave,session=Depends(_ready)):
    state=_pm_profiles_state()
    if not body.id and len(state["profiles"])>=12:
        raise HTTPException(409,"حداکثر ۱۲ اتصال ProcessMaker قابل ثبت است.")
    profile=_pm_profile_from_body(body,state)
    state["profiles"]=[p for p in state["profiles"] if p["id"]!=profile["id"]]+[profile]
    if body.activate or state.get("active_id")==profile["id"]:
        _pm_profile_activate(state,profile)
    else:
        _pm_profiles_write(state)
    setup.audit("PROCESSMAKER_PROFILE_SAVED")
    return {"saved":True,"id":profile["id"],
            "active":state.get("active_id")==profile["id"]}


@router.post("/api/bpms/catalog/test")
def bpms_catalog_test(body:BPMSCatalogRef,session=Depends(_ready)):
    if body.connection_type=="processmaker":
        state=_pm_profiles_state()
        profile=next((p for p in state["profiles"] if p["id"]==body.id),None)
        if not profile:raise HTTPException(404,"اتصال ProcessMaker پیدا نشد.")
        return _pm_profile_test(profile,state)
    from .bpms_registry import check_saved,BPMSUnavailable
    try:return check_saved(body.id)
    except BPMSUnavailable as exc:raise HTTPException(503,str(exc))


@router.post("/api/bpms/catalog/copy")
def bpms_catalog_copy(body:BPMSCatalogCopy,session=Depends(_ready)):
    if body.connection_type=="processmaker":
        state=_pm_profiles_state()
        source=next((p for p in state["profiles"] if p["id"]==body.id),None)
        if not source:raise HTTPException(404,"اتصال ProcessMaker پیدا نشد.")
        if len(state["profiles"])>=12:raise HTTPException(409,"حداکثر تعداد اتصال ProcessMaker ثبت شده است.")
        copied={**source,"id":secrets.token_hex(12),
                "name":(body.name or (source["name"]+" - کپی")).strip(),
                "mysql":dict(source.get("mysql") or {}),
                "api":dict(source.get("api") or {})}
        state["profiles"].append(copied);_pm_profiles_write(state)
        setup.audit("PROCESSMAKER_PROFILE_COPIED")
        return {"saved":True,"id":copied["id"],"active":False}
    from .bpms_registry import copy_source,BPMSUnavailable
    try:return copy_source(body.id,body.name)
    except BPMSUnavailable as exc:raise HTTPException(409,str(exc))


@router.post("/api/bpms/catalog/delete")
def bpms_catalog_delete(body:BPMSCatalogRef,session=Depends(_ready)):
    _require_source_without_user_bindings(body.id)
    if body.connection_type=="processmaker":
        state=_pm_profiles_state()
        source=next((p for p in state["profiles"] if p["id"]==body.id),None)
        if not source:raise HTTPException(404,"اتصال ProcessMaker پیدا نشد.")
        state["profiles"]=[p for p in state["profiles"] if p["id"]!=body.id]
        if state.get("active_id")==body.id:
            state["active_id"]=None
            setup.put_setting("mysql",{})
            setup.put_setting("processmaker",{})
        _pm_profiles_write(state);setup.audit("PROCESSMAKER_PROFILE_DELETED")
        return {"deleted":True}
    from .bpms_registry import delete,BPMSUnavailable
    try:return delete(body.id)
    except BPMSUnavailable as exc:raise HTTPException(404,str(exc))


@router.post("/api/bpms/processmaker/activate")
def bpms_processmaker_activate(body:BPMSCatalogRef,session=Depends(_ready)):
    if body.connection_type!="processmaker":
        raise HTTPException(422,"نوع اتصال برای فعال‌سازی بومی معتبر نیست.")
    state=_pm_profiles_state()
    profile=next((p for p in state["profiles"] if p["id"]==body.id),None)
    if not profile:raise HTTPException(404,"اتصال ProcessMaker پیدا نشد.")
    _pm_profile_test(profile,state)
    _pm_profile_activate(state,profile)
    setup.audit("PROCESSMAKER_PROFILE_ACTIVATED")
    return {"activated":True,"id":body.id}


@router.get("/api/bpms/processmaker/profile/{profile_id}")
def bpms_processmaker_profile(profile_id:str,session=Depends(_ready)):
    if not re.fullmatch(r"[0-9a-f]{24}",profile_id):
        raise HTTPException(422,"شناسه اتصال معتبر نیست.")
    state=_pm_profiles_state()
    profile=next((p for p in state["profiles"] if p["id"]==profile_id),None)
    if not profile:raise HTTPException(404,"اتصال ProcessMaker پیدا نشد.")
    return _pm_profile_public(profile,state.get("active_id"))

@router.get("/api/users/pending")
def pending_staff(session=Depends(_ready)):
    from .pending_identities import list_pending
    return {"pending":list_pending()}

@router.get("/api/processmaker/users")
def processmaker_users(session=Depends(_ready)):
    raise HTTPException(
        410,
        "این API تک-ProcessMaker منسوخ شده است؛ فهرست کاربر را از BPMS انتخاب‌شده در «سازمان و دسترسی» دریافت کنید."
    )

@router.post("/api/processmaker/refresh-users")
def refresh_processmaker_users(session=Depends(_ready)):
    raise HTTPException(
        410,
        "همگام‌سازی سراسری ProcessMaker منسوخ شده است؛ هر BPMS را جداگانه از Binding همان Source همگام‌سازی کنید."
    )


class AvanIdentityCreate(BaseModel):
    model_config=ConfigDict(extra="forbid")
    username:str=Field(min_length=3,max_length=80,pattern=r"^[A-Za-z0-9_.@-]+$")
    email:str=Field(min_length=3,max_length=240,pattern=r"^[^@ ]+@[^@ ]+[.][^@ ]+$")
    name:str=Field(min_length=2,max_length=240)
    role:Literal["Expert","Manager","SysAdmin"]="Expert"
    # Kept for API compatibility; this is now a permanent login password.
    temporary_password:str=Field(min_length=16,max_length=128)


@router.post("/api/users/create-identity")
def create_avan_identity(body:AvanIdentityCreate,session=Depends(_ready)):
    company=setup.get_setting("company") or {}
    tenant=company.get("tenant_id")
    company_name=(company.get("company_name") or "").strip()
    config=setup.get_setting("oidc") or {}
    if not tenant or not company_name:
        raise HTTPException(409,"ابتدا اطلاعات سازمان را کامل ثبت کنید.")
    if not config.get("managed_by_product"):
        raise HTTPException(
            409,
            "ساخت کاربر از داخل AVAN فقط با سرویس هویت داخلی آوان انجام می‌شود."
        )

    from .user_accounts import directory
    from .production_onboarding import (
        ProvisioningDenied,
        register_managed_identity,
    )

    subject=None
    with directory() as service:
        subject=service.create(
            body.username,
            body.email.strip(),
            body.name.strip(),
            body.role,
            body.temporary_password,
        )
        try:
            access=register_managed_identity(
                tenant_id=tenant,
                subject=subject,
                company_name=company_name,
                username=body.username,
                email=body.email.strip(),
                name=body.name.strip(),
                role=body.role,
            )
        except ProvisioningDenied as exc:
            try:
                service.delete(subject)
            except Exception:
                setup.audit("AVAN_USER_CREATE_ROLLBACK_FAILED")
                raise HTTPException(
                    500,
                    "هویت کاربر ساخته شد اما ثبت دسترسی AVAN و Rollback کامل نشد؛ "
                    "قبل از تلاش مجدد حساب را از بخش کاربران بررسی کنید."
                ) from exc
            raise HTTPException(409,str(exc)) from exc
        except Exception as exc:
            try:
                service.delete(subject)
            except Exception:
                setup.audit("AVAN_USER_CREATE_ROLLBACK_FAILED")
            raise HTTPException(
                503,
                "ثبت دسترسی AVAN کامل نشد؛ هویت نیمه‌کاره Rollback شد."
            ) from exc

    setup.audit("AVAN_IDENTITY_CREATED_"+body.role.upper())
    return {
        "created":True,
        "authorized":True,
        "subject":subject,
        "username":body.username,
        "name":body.name.strip(),
        "role":body.role,
        "modules":access["modules"],
        "password_temporary":False,
        "mfa_required":False,
        "next_step":"sign_in",
    }


class ManagedIdentityActivation(BaseModel):
    model_config=ConfigDict(extra="forbid")
    subject:UUID


@router.post("/api/users/activate-managed")
def activate_managed_identity(body:ManagedIdentityActivation,session=Depends(_ready)):
    company=setup.get_setting("company") or {}
    tenant=company.get("tenant_id")
    company_name=(company.get("company_name") or "").strip()
    if not tenant or not company_name:
        raise HTTPException(409,"ابتدا اطلاعات سازمان را کامل ثبت کنید.")

    from .user_accounts import directory
    from .production_onboarding import (
        ProvisioningDenied,
        register_managed_identity,
    )

    subject=str(body.subject)
    with directory() as service:
        user=service.get(subject)
        if not user.get("enabled"):
            raise HTTPException(409,"هویت Keycloak این کاربر غیرفعال است.")
        if user.get("emailVerified") is not True:
            raise HTTPException(409,"ایمیل هویت Keycloak این کاربر هنوز تأیید نشده است.")
        role=service.avan_role(subject)
        username=str(user.get("username") or "").strip()
        email=str(user.get("email") or "").strip()
        name=(" ".join([
            str(user.get("firstName") or "").strip(),
            str(user.get("lastName") or "").strip(),
        ])).strip() or username
        try:
            access=register_managed_identity(
                tenant_id=tenant,
                subject=subject,
                company_name=company_name,
                username=username,
                email=email,
                name=name,
                role=role,
            )
        except ProvisioningDenied as exc:
            raise HTTPException(409,str(exc)) from exc

    setup.audit("AVAN_EXISTING_IDENTITY_ACTIVATED_"+role.upper())
    return {
        "activated":True,
        "subject":subject,
        "username":username,
        "role":role,
        "modules":access["modules"],
    }


class StaffApproval(BaseModel):
    model_config=ConfigDict(extra="forbid")
    tenant_id:str=Field(min_length=36,max_length=36)
    subject:str=Field(min_length=1,max_length=180)
    company_name:str=Field(min_length=2,max_length=200)
    role:str=Field(min_length=6,max_length=8)
    manager_subject:str|None=Field(default=None,max_length=180)
    department_name:str|None=Field(default=None,max_length=160)
    modules:list[int]|None=Field(default=None,max_length=4)

@router.post("/api/users/approve")
def approve_staff(body:StaffApproval,session=Depends(_ready)):
    from .production_onboarding import ProvisioningDenied,approve_avan_user
    try:return approve_avan_user(
        tenant_id=body.tenant_id,subject=body.subject,
        company_name=body.company_name,role=body.role,
        manager_subject=body.manager_subject,
        department_name=body.department_name,
        module_permissions=body.modules)
    except ProvisioningDenied as exc:
        raise HTTPException(409,str(exc))


def _binding_admin_actor(session)->str:
    try:
        row=session[1]
        if isinstance(row,dict):
            value=row.get("subject") or row.get("username")
            if isinstance(value,str) and value.strip():
                return value.strip()[:180]
    except (IndexError,TypeError):
        pass
    return "bootstrap-godadmin"


class UserBpmsBindingSave(BaseModel):
    model_config=ConfigDict(extra="forbid")
    subject:str=Field(min_length=1,max_length=180)
    source_id:str=Field(pattern=r"^[0-9a-f]{24}$")
    external_user_id:str=Field(min_length=1,max_length=128)
    match_method:Literal["manual","username_suggestion","email_suggestion",
                         "display_name_suggestion"]="manual"


class UserBpmsUsernameBindingSave(BaseModel):
    model_config=ConfigDict(extra="forbid")
    subject:str=Field(min_length=1,max_length=180)
    source_id:str=Field(pattern=r"^[0-9a-f]{24}$")
    external_username:str=Field(min_length=1,max_length=120)


class UserBpmsBindingRef(BaseModel):
    model_config=ConfigDict(extra="forbid")
    subject:str=Field(min_length=1,max_length=180)
    source_id:str=Field(pattern=r"^[0-9a-f]{24}$")


class UserBpmsSourceRef(BaseModel):
    model_config=ConfigDict(extra="forbid")
    source_id:str=Field(pattern=r"^[0-9a-f]{24}$")


@router.get("/api/user-bindings/sources")
def user_binding_sources(session=Depends(_ready)):
    from .user_bpms_bindings import source_catalog
    return {"sources":source_catalog()}


@router.get("/api/user-bindings/list")
def user_binding_list(subject:str|None=None,session=Depends(_ready)):
    if subject is not None and not 1<=len(subject)<=180:
        raise HTTPException(422,"شناسه کاربر AVAN معتبر نیست.")
    from .user_bpms_bindings import list_bindings
    return {"bindings":list_bindings(subject)}


@router.get("/api/user-bindings/directory")
def user_binding_directory(subject:str,source_id:str,session=Depends(_ready)):
    if not 1<=len(subject)<=180 or not re.fullmatch(r"[0-9a-f]{24}",source_id or ""):
        raise HTTPException(422,"کاربر یا BPMS معتبر نیست.")
    from .user_bpms_bindings import BindingError,directory_users,suggestions
    try:
        users=directory_users(source_id)
        suggested=suggestions(subject,source_id,users)
        return {"source":suggested["source"],
                "suggestions":suggested["suggestions"],
                "users":users}
    except BindingError as exc:
        raise HTTPException(409,str(exc))


@router.post("/api/user-bindings/bind")
def user_binding_save(body:UserBpmsBindingSave,session=Depends(_ready)):
    from .user_bpms_bindings import BindingError,bind
    try:
        return {"binding":bind(subject=body.subject,source_id=body.source_id,
                               external_user_id=body.external_user_id,
                               match_method=body.match_method,
                               approved_by=_binding_admin_actor(session))}
    except BindingError as exc:
        raise HTTPException(409,str(exc))


@router.post("/api/user-bindings/bind-username")
def user_binding_save_by_username(body:UserBpmsUsernameBindingSave,session=Depends(_ready)):
    from .user_bpms_bindings import BindingError,bind_by_username
    try:
        return {"binding":bind_by_username(
            subject=body.subject,
            source_id=body.source_id,
            external_username=body.external_username,
            approved_by=_binding_admin_actor(session),
        )}
    except BindingError as exc:
        raise HTTPException(409,str(exc))


@router.post("/api/user-bindings/unbind")
def user_binding_remove(body:UserBpmsBindingRef,session=Depends(_ready)):
    from .user_bpms_bindings import BindingError,unbind
    try:return unbind(subject=body.subject,source_id=body.source_id,
                      approved_by=_binding_admin_actor(session))
    except BindingError as exc:raise HTTPException(409,str(exc))


@router.post("/api/user-bindings/refresh")
def user_binding_refresh(body:UserBpmsSourceRef,session=Depends(_ready)):
    from .user_bpms_bindings import BindingError,refresh_source
    try:return refresh_source(body.source_id,approved_by=_binding_admin_actor(session))
    except BindingError as exc:raise HTTPException(409,str(exc))


@router.post("/api/user-bindings/migrate-legacy")
def user_binding_migrate_legacy(session=Depends(_ready)):
    from .user_bpms_bindings import migrate_legacy_processmaker_bindings
    return migrate_legacy_processmaker_bindings()


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
    fields=('subject','username','email','name','role','department_name',
            'manager_subject','module_permissions','enabled')
    return {'users':[{k:u.get(k) for k in fields} for u in data['users']]}


class UserModules(BaseModel):
    model_config=ConfigDict(extra='forbid')
    subject:str=Field(min_length=1,max_length=180)
    modules:list[int]=Field(default_factory=list,max_length=4)


@router.post('/api/users/modules')
def user_modules(body:UserModules,session=Depends(_ready)):
    from . import native_access
    from .production_license import entitlement,ProductionLicenseDenied
    requested=set(body.modules)
    if len(requested)!=len(body.modules) or any(
        not isinstance(x,int) or x not in (1,2,3,4) for x in body.modules
    ):
        raise HTTPException(422,'مجوز ماژول AVAN معتبر نیست.')
    with native_access.edit() as data:
        user=next((u for u in data['users'] if u.get('subject')==body.subject),None)
        if not user:raise HTTPException(404,'کاربر AVAN ثبت نشده است.')
        try:
            licensed=entitlement(tenant_id=data['tenant_id'],company_name=data['company_name'])
        except ProductionLicenseDenied:
            raise HTTPException(409,'لایسنس معتبر برای تغییر دسترسی ماژول لازم است.')
        allowed=set(int(x) for x in licensed['modules'])
        if not requested<=allowed:
            raise HTTPException(409,'یک یا چند ماژول انتخاب‌شده در لایسنس سازمان فعال نیست.')
        user['module_permissions']=sorted(requested)
    setup.audit('AVAN_USER_MODULE_PERMISSIONS_UPDATED')
    return {'saved':True,'subject':body.subject,'modules':sorted(requested)}


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
            used=sum(u.get('subject')!=body.subject and u.get('enabled')
                     for u in data['users'])+1
            try:capacity(data['tenant_id'],data['company_name'],used)
            except ProductionLicenseDenied:
                raise HTTPException(409,'اعتبار زمانی یا ظرفیت لایسنس اجازه فعال‌سازی نمی‌دهد.')
        user['enabled']=body.enabled
    return {'saved':True,'enabled':body.enabled}



# Secretary packs are configured only on the existing authenticated management surface.
class SecretaryPackSave(BaseModel):
    model_config=ConfigDict(extra='forbid')
    source_id:str=Field(pattern=r'^[0-9a-f]{24}$')
    meeting_pmx:str=Field(min_length=20,max_length=2500000)
    action_pmx:str=Field(min_length=20,max_length=2500000)
    id:str|None=Field(None,pattern=r'^[0-9a-f]{24}$')
    revision:int|None=Field(None,ge=1)
    enabled:bool=True
    monitor_lead_minutes:int=Field(1440,ge=0,le=43200)
    action_lead_minutes:int=Field(60,ge=0,le=43200)

@router.get('/api/secretary/processes/{source_id}')
def secretary_processes(source_id:str,session=Depends(_ready)):
    from .secretary_catalog import discover,packs
    from .user_bpms_bindings import BindingError
    try:return {'processes':discover(source_id),'packs':packs(source_id)}
    except BindingError:raise HTTPException(404,'اتصال BPMS پیدا نشد.')
    except Exception:raise HTTPException(503,'فرایندهای این اتصال قابل دریافت نیستند.')

@router.post('/api/secretary/packs/save')
def secretary_pack_save(body:SecretaryPackSave,session=Depends(_ready)):
    from .secretary_catalog import compile_pack,verify_installed,save
    try:
        pack=compile_pack(body.meeting_pmx,body.action_pmx)
        verify_installed(body.source_id,pack)
        return save(body.source_id,pack,_binding_admin_actor(session),identifier=body.id,revision=body.revision,
                    enabled=body.enabled,monitor_lead_minutes=body.monitor_lead_minutes,action_lead_minutes=body.action_lead_minutes)
    except ValueError as exc:raise HTTPException(422,str(exc))


class NativeProcessConnect(BaseModel):
    model_config=ConfigDict(extra='forbid')
    source_id:str=Field(pattern=r'^[0-9a-f]{24}$')
    process_uid:str=Field(pattern=r'^[a-f0-9]{32}$')

@router.post('/api/process-workspace/connect')
def connect_native_process(body:NativeProcessConnect,session=Depends(_ready)):
    from .secretary_catalog import discover,save
    found=next((p for p in discover(body.source_id) if p['process_uid']==body.process_uid),None)
    if not found:raise HTTPException(404,'فرایند در این اتصال نصب نیست.')
    try:return save(body.source_id,{'adapter':'native_tasks_v1','process':found},_binding_admin_actor(session))
    except ValueError as exc:raise HTTPException(422,str(exc))

class ProcessPackEnabled(BaseModel):
    model_config=ConfigDict(extra='forbid')
    source_id:str=Field(pattern=r'^[0-9a-f]{24}$')
    pack_id:str=Field(pattern=r'^[0-9a-f]{24}$')
    revision:int=Field(ge=1)
    enabled:bool

@router.post('/api/process-workspace/enabled')
def process_pack_enabled(body:ProcessPackEnabled,session=Depends(_ready)):
    from .secretary_catalog import packs,save
    pack=next((p for p in packs(body.source_id) if p['id']==body.pack_id),None)
    if not pack:raise HTTPException(404,'بسته فرایند پیدا نشد.')
    try:return save(body.source_id,pack,_binding_admin_actor(session),identifier=body.pack_id,revision=body.revision,
                    enabled=body.enabled,monitor_lead_minutes=pack['monitor_lead_minutes'],action_lead_minutes=pack['action_lead_minutes'])
    except ValueError as exc:raise HTTPException(409,str(exc))


from .user_accounts import register as register_user_accounts
register_user_accounts(router,_ready)
