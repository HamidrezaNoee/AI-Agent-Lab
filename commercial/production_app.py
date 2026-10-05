"""Operational AVAN: OIDC + SQL-authorized meeting analysis and secretary drafts.
MTG stays read-only. AI tools receive freshly authorized bounded snapshots;
local review drafts and monitoring observations are encrypted and audited.
"""
from __future__ import annotations
from datetime import datetime, timezone, timedelta
from contextlib import asynccontextmanager
from functools import lru_cache
from pathlib import Path
import base64, hashlib, hmac, json, os, secrets, time, threading
from urllib.parse import urlencode, urlsplit

import httpx
import jwt
from fastapi import FastAPI, HTTPException, Request, Depends, Query
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, Response
from pydantic import BaseModel, ConfigDict, Field
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .production_store import (
    EmployeeMappingRequired, ProductionAccessDenied, ProductionUnavailable,
    authorized_meetings_page, authorized_meeting_snapshot, open_production,
    verified_scope,
)
from .security import (
    AuthenticationFailed, ConfigurationFailed, VerifiedTokenAuthenticator,
)

@lru_cache(maxsize=8)
def _verifier(issuer:str,audience:str,jwks_url:str):
    return VerifiedTokenAuthenticator(issuer,audience,jwks_url)


ROOT=Path(__file__).resolve().parent/"web"/"production"
PROD_QUESTIONS=(
    "کدام اقدامات مصوب جلسات عقب‌افتاده‌اند؟",
    "مهم‌ترین موضوعات حل‌نشده این ماه چیست؟",
    "عملکرد واحدها در اجرای مصوبات چگونه بوده است؟",
    "کدام مدیر یا واحد بیشترین اقدامات باز را دارد؟",
    "اقدامات جلسه شماره مشخص در چه وضعیتی هستند؟",
    "مهم‌ترین ریسک‌های قابل مشاهده در جلسات اخیر چیست؟",
    "چه موضوعاتی در جلسات مختلف به‌صورت مکرر مطرح شده‌اند؟",
    "برای جلسه آینده چه مواردی باید در دستور جلسه قرار گیرد؟",
)
sessions={}
pending={}
_session_lock=threading.RLock()
SESSION_IDLE_SECONDS=600
SESSION_MAX_SECONDS=28800


@asynccontextmanager
async def production_lifespan(_app):
    # The control plane is deliberately independent of operational SQL/IdP.
    # First Docker start therefore succeeds without .env or live credentials.
    from .setup_console import initialize
    initialize()
    from .login_appearance import sync_public
    sync_public()
    import asyncio
    from .agent_monitor import worker as monitor_worker
    task=asyncio.create_task(monitor_worker())
    try:
        yield
    finally:
        task.cancel()
        try:await task
        except asyncio.CancelledError:pass


app=FastAPI(title="AVAN",docs_url=None,redoc_url=None,openapi_url=None,
            lifespan=production_lifespan)
from .setup_routes import router as godadmin_router
app.include_router(godadmin_router)
hosts=[h.strip() for h in os.getenv("AVAN_ALLOWED_HOSTS","localhost,127.0.0.1").split(",")
       if h.strip() and "*" not in h]
app.add_middleware(TrustedHostMiddleware,allowed_hosts=hosts or ["localhost"])


@app.middleware("http")
async def security_headers(request:Request,call_next):
    response=await call_next(request)
    response.headers["Cache-Control"]="no-store"
    response.headers["X-Content-Type-Options"]="nosniff"
    embedded_admin=request.url.path.startswith("/admin/")
    response.headers["X-Frame-Options"]="SAMEORIGIN" if embedded_admin else "DENY"
    response.headers["Referrer-Policy"]="no-referrer"
    response.headers["Content-Security-Policy"]=(
        "default-src 'none'; script-src 'self'; style-src 'self'; "
        "connect-src 'self'; media-src 'self' blob:; img-src 'self' data:; font-src 'self'; "
        "frame-src 'self'; form-action 'self'; base-uri 'none'; frame-ancestors "
        + ("'self'" if embedded_admin else "'none'")
    )
    return response


def _public_origin()->str:
    # Loopback origin is fixed by the deployment. External HTTPS deployments
    # require a separately reviewed reverse-proxy and secure-cookie design.
    value=os.getenv("AVAN_PUBLIC_ORIGIN","http://127.0.0.1:8188").rstrip("/")
    parsed=urlsplit(value)
    if parsed.scheme not in ("http","https") or not parsed.hostname or parsed.path not in ("","/"):
        raise ConfigurationFailed("Public origin must be configured exactly")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ConfigurationFailed("Invalid public origin")
    if parsed.scheme=="http" and parsed.hostname not in ("localhost","127.0.0.1"):
        raise ConfigurationFailed("HTTP origin allowed only on this machine")
    return value


def _oidc_config():
    from .setup_console import get_setting
    config=get_setting("oidc") or {}
    issuer=str(config.get("issuer","")).rstrip("/")
    audience=str(config.get("audience",""))
    jwks=str(config.get("jwks_url",""))
    client_id=str(config.get("client_id",""))
    client_secret=str(config.get("client_secret",""))
    origin=urlsplit(issuer)
    bundled_local=(os.getenv("AVAN_BUNDLED_IDP")=="1" and
                   origin.scheme=="http" and origin.hostname=="auth.localhost"
                   and origin.port==8181)
    if ((origin.scheme!="https" and not bundled_local) or
        config.get("jwks_url")!=issuer+"/protocol/openid-connect/certs" or
        not client_id or len(client_id)>256 or
        not 16<=len(client_secret)<=4096 or
        any(c in client_secret for c in (chr(13),chr(10)))):
        raise ConfigurationFailed("Secure OIDC realm settings not configured")
    verifier=_verifier(issuer,audience,jwks)
    return (issuer+"/protocol/openid-connect/auth",
            issuer+"/protocol/openid-connect/token",client_id,client_secret,
            verifier)


def _purge():
    now=time.time()
    for key,val in list(pending.items()):
        if val["expires"]<now:pending.pop(key,None)
    for key,val in list(sessions.items()):
        if val["expires"]<=now or val.get("idle_expires",val["expires"])<=now:
            sessions.pop(key,None)


def _cookie_options():
    return {"httponly":True,"secure":_public_origin().startswith("https://"),
            "samesite":"lax","path":"/"}


def _oidc_state_cookie_name(state:str)->str:
    # One cookie per authorization transaction prevents stale tabs, parallel
    # logins and cookies left by older AVAN builds from overwriting OIDC state.
    digest=hashlib.sha256(state.encode("utf-8")).hexdigest()[:24]
    return "avan_oidc_state_"+digest


OIDC_BROWSER_COOKIE="avan_oidc_browser"


def _new_oidc_browser_token()->str:
    return secrets.token_urlsafe(32)


def _valid_oidc_browser_token(value:str)->bool:
    return bool(value) and 32 <= len(value) <= 128 and all(
        ch.isalnum() or ch in "-_" for ch in value
    )


def _oidc_browser_hash(value:str)->str:
    return hashlib.sha256(value.encode("ascii")).hexdigest()


def _b64u(data:bytes)->str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _b64u_decode(value:str)->bytes:
    return base64.urlsafe_b64decode(value+"="*((4-len(value)%4)%4))


def _oidc_tx_encode(*,state:str,verifier:str,browser_hash:str,expires:float,secret:str)->str:
    payload=_b64u(json.dumps({
        "s":state,
        "v":verifier,
        "b":browser_hash,
        "e":int(expires),
    },separators=(",",":"),sort_keys=True).encode("utf-8"))
    signature=_b64u(hmac.new(
        secret.encode("utf-8"),
        ("avan-oidc-tx-v1."+payload).encode("ascii"),
        hashlib.sha256,
    ).digest())
    return payload+"."+signature


def _oidc_tx_decode(value:str,*,state:str,secret:str)->dict|None:
    try:
        payload,signature=value.split(".",1)
        expected=_b64u(hmac.new(
            secret.encode("utf-8"),
            ("avan-oidc-tx-v1."+payload).encode("ascii"),
            hashlib.sha256,
        ).digest())
        if not hmac.compare_digest(signature,expected):
            return None
        data=json.loads(_b64u_decode(payload))
        if (not isinstance(data,dict)
            or data.get("s")!=state
            or not isinstance(data.get("v"),str)
            or not 32<=len(data["v"])<=128
            or not isinstance(data.get("b"),str)
            or len(data["b"])!=64
            or not isinstance(data.get("e"),int)):
            return None
        return {
            "verifier":data["v"],
            "browser_hash":data["b"],
            "expires":float(data["e"]),
        }
    except (ValueError,TypeError,KeyError,json.JSONDecodeError):
        return None


def _principal_for_request(request:Request):
    _purge()
    session_id=request.cookies.get("avan_session","")
    with _session_lock:
        value=sessions.get(session_id)
        if not value or value.get("idle_expires",value["expires"])<=time.time():
            sessions.pop(session_id,None)
            raise HTTPException(status_code=401,detail="نشست ده‌دقیقه‌ای شما پایان یافته است؛ دوباره وارد شوید.")
        try:
            _,token_url,client_id,client_secret,authenticator=_oidc_config()
            if value.get("access_expires",0) <= time.time()+25:
                if value.get("refresh_token"):
                    with httpx.Client(timeout=8,follow_redirects=False,trust_env=False) as client:
                        result=client.post(token_url,data={
                            "grant_type":"refresh_token",
                            "refresh_token":value["refresh_token"],
                            "client_id":client_id,"client_secret":client_secret})
                    result.raise_for_status()
                    if len(result.content)>65000:raise AuthenticationFailed("Oversize refresh response")
                    tokens=result.json()
                elif value.get("monitor_delegated"):
                    from .agent_monitor import renew_for_session
                    tokens=renew_for_session(value)
                else:
                    raise AuthenticationFailed("No refresh token")
                access=tokens.get("access_token","")
                principal=authenticator.authenticate("Bearer "+access)
                if (principal.subject!=value.get("subject") or
                    str(principal.tenant_id)!=value.get("tenant_id")):
                    raise AuthenticationFailed("Refreshed identity changed")
                claims=jwt.decode(access,options={"verify_signature":False},algorithms=["RS256"])
                value["access_token"]=access
                value["access_expires"]=float(claims["exp"])
                if value.get("refresh_token"):
                    value["refresh_token"]=tokens.get("refresh_token") or value["refresh_token"]
                if tokens.get("id_token"):value["id_token"]=tokens["id_token"]
            else:
                principal=authenticator.authenticate("Bearer "+value["access_token"])
        except (ConfigurationFailed,AuthenticationFailed,httpx.HTTPError,ValueError,KeyError,TypeError):
            sessions.pop(session_id,None)
            raise HTTPException(status_code=401,detail="نشست شما معتبر نیست؛ دوباره وارد شوید.")
        # Automated monitoring requests do not count as human activity.
        if request.headers.get("X-AVAN-BACKGROUND")!="1":
            value["idle_expires"]=min(value["expires"],time.time()+SESSION_IDLE_SECONDS)
    return session_id,value,principal


@app.get("/health")
def health():
    # Process liveness only; never claim a live DB/IdP/license based on /health.
    return {"status":"up","service":"avan",
            "database_checked":False,"identity_checked":False}


@app.get("/api/ui-config")
def ui_config():
    from .setup_console import get_setting
    calendar=str((get_setting("ui") or {}).get("calendar","jalali")).lower()
    if calendar not in ("jalali","gregorian"):
        calendar="jalali"
    return {"calendar":calendar}


def _internal_security_secret()->str:
    path=Path(os.getenv("AVAN_SECURITY_BRIDGE_TOKEN_PATH",
                        "/run/secrets/avan_bff_client_secret"))
    try:
        value=path.read_text(encoding="utf-8").strip()
    except OSError:
        raise HTTPException(status_code=503,detail="Internal security bridge is not configured")
    if len(value)<16 or len(value)>4096 or any(ch in value for ch in "\r\n"):
        raise HTTPException(status_code=503,detail="Internal security bridge is not configured")
    return value


def _require_internal_security(request:Request):
    supplied=request.headers.get("X-AVAN-Internal-Token","")
    expected=_internal_security_secret()
    if not supplied or not hmac.compare_digest(supplied.encode(),expected.encode()):
        raise HTTPException(status_code=403,detail="Internal security bridge denied")


@app.get("/internal/security/challenge")
def internal_security_challenge(request:Request,
                                action:str=Query(min_length=1,max_length=64)):
    _require_internal_security(request)
    from .turnstile import public_config,TurnstileUnavailable
    try:
        config=public_config(action)
    except TurnstileUnavailable:
        raise HTTPException(status_code=503,detail="AVAN anti-bot is unavailable")
    cloudflare=config.get("cloudflare") or {}
    local=config.get("local") if isinstance(config.get("local"),dict) else None
    payload={"action":action,"localAvailable":bool(local)}
    if local:
        payload.update(local)
    if cloudflare.get("enabled"):
        payload["turnstileSiteKey"]=str(cloudflare.get("site_key") or "")
        payload["turnstileTimeoutMs"]=int(cloudflare.get("timeout_ms") or 2500)
    return payload


class InternalSecurityVerify(BaseModel):
    model_config=ConfigDict(extra="forbid")
    action:str=Field(min_length=1,max_length=64,
                     pattern=r"^[a-z0-9][a-z0-9:_-]{0,63}$")
    envelope:str=Field(min_length=1,max_length=12288)


@app.post("/internal/security/verify")
def internal_security_verify(request:Request,body:InternalSecurityVerify):
    _require_internal_security(request)
    from .turnstile import verify
    return {"verified":bool(verify(body.envelope,action=body.action,remote_ip=None))}


@app.get("/")
def home(request:Request):
    from .setup_console import get_setting,godadmin_identity,password_state

    # /admin/ is the host-local bootstrap/maintenance surface. The public root
    # must never send an organizational user to that password verifier once the
    # identity service is ready, otherwise a valid Keycloak username/password is
    # misleadingly reported as a wrong local GodAdmin credential.
    if not godadmin_identity():
        from .setup_routes import bootstrap_workspace_session
        if bootstrap_workspace_session(request):
            return FileResponse(ROOT/"index.html",media_type="text/html; charset=utf-8")

        oidc=get_setting("oidc")
        bootstrap=password_state()
        if not oidc or not bootstrap["changed"] or not bootstrap["totp"]:
            return RedirectResponse("/admin/",status_code=303)

    if not get_setting("oidc"):
        return RedirectResponse("/admin/",status_code=303)

    _purge()
    if request.cookies.get("avan_session","") not in sessions:
        return RedirectResponse("/auth/login",status_code=303)
    return FileResponse(ROOT/"index.html",media_type="text/html; charset=utf-8")


@app.get("/assets/app.css")
def css():
    return FileResponse(ROOT/"app.css",media_type="text/css; charset=utf-8")


@app.get("/assets/app.js")
def javascript():
    return FileResponse(ROOT/"app.js",media_type="text/javascript; charset=utf-8")


@app.get("/assets/theme.css")
def theme_css():
    return FileResponse(ROOT/"theme.css",media_type="text/css; charset=utf-8")


@app.get("/assets/theme.js")
def theme_script():
    return FileResponse(ROOT/"theme.js",media_type="text/javascript; charset=utf-8")


@app.get("/assets/agent-login.webp")
def login_art():
    return FileResponse(ROOT/"agent-login.webp",media_type="image/webp")


@app.get("/assets/fonts/{name}")
def font_asset(name:str):
    if name not in ("YekanBakh-Regular.woff2", "YekanBakh-SemiBold.woff2", "YekanBakh-Bold.woff2"):
        raise HTTPException(status_code=404)
    return FileResponse(ROOT/"fonts"/name,media_type="font/woff2")


@app.get("/auth/login")
def login(request:Request):
    from .setup_console import get_setting,godadmin_identity
    if request.query_params.get('account')=='godadmin' and not godadmin_identity():
        return RedirectResponse('/admin/',status_code=303)
    # OIDC cookies are host-only. Always start authentication on the exact
    # configured public origin before setting browser/PKCE cookies. This covers
    # localhost, machine names, LAN IPs and reverse-proxy host aliases.
    origin=_public_origin()
    canonical=urlsplit(origin)
    request_host=(request.url.hostname or "").lower()
    canonical_host=(canonical.hostname or "").lower()
    request_port=request.url.port or (443 if request.url.scheme=="https" else 80)
    canonical_port=canonical.port or (443 if canonical.scheme=="https" else 80)
    if (request.url.scheme.lower()!=canonical.scheme.lower()
        or request_host!=canonical_host
        or request_port!=canonical_port):
        return RedirectResponse(origin+"/auth/login",status_code=303)
    from .setup_console import password_state
    first_run=password_state()
    if not first_run["changed"] or not first_run["totp"]:
        raise HTTPException(status_code=403,
                            detail="ابتدا GodAdmin باید راه‌اندازی اولیه و تأیید دومرحله‌ای را تکمیل کند.")
    try:
        authorization,_,client_id,client_secret,_= _oidc_config()
    except ConfigurationFailed:
        raise HTTPException(status_code=503,detail="سامانه هویت سازمانی تنظیم نشده است.")
    _purge()
    if len(pending)>3000:
        raise HTTPException(status_code=503,detail="ورود سازمانی موقتاً در دسترس نیست.")
    state=secrets.token_urlsafe(32)
    verifier=secrets.token_urlsafe(48)
    challenge=__import__("base64").urlsafe_b64encode(
        hashlib.sha256(verifier.encode("ascii")).digest()
    ).decode("ascii").rstrip("=")
    browser_token=request.cookies.get(OIDC_BROWSER_COOKIE,"")
    if not _valid_oidc_browser_token(browser_token):
        browser_token=_new_oidc_browser_token()
    pending[state]={
        "verifier":verifier,
        "expires":time.time()+300,
        "browser_hash":_oidc_browser_hash(browser_token),
    }
    redirect_url=authorization+"?"+urlencode({
        "response_type":"code","client_id":client_id,
        "redirect_uri":origin+"/auth/callback",
        "scope":"openid profile email","state":state,
        "prompt":"login",
        "code_challenge":challenge,"code_challenge_method":"S256",
    })
    response=RedirectResponse(redirect_url,status_code=302)
    # Remove the legacy fixed-name state cookie.  It could collide with a
    # previous tab/login.  The current transaction gets its own short-lived,
    # callback-scoped cookie.
    response.delete_cookie("avan_login_state",path="/")
    response.set_cookie(
        OIDC_BROWSER_COOKIE,
        browser_token,
        max_age=600,
        httponly=True,
        secure=_public_origin().startswith("https://"),
        samesite="lax",
        path="/",
    )
    # Persist a tamper-evident, HttpOnly OIDC transaction token in the browser.
    # RAM remains only an optimization: a container restart or another worker
    # can reconstruct the PKCE verifier and browser binding from this cookie.
    response.set_cookie(
        _oidc_state_cookie_name(state),
        _oidc_tx_encode(
            state=state,
            verifier=verifier,
            browser_hash=_oidc_browser_hash(browser_token),
            expires=time.time()+300,
            secret=client_secret,
        ),
        max_age=300,
        httponly=True,
        secure=_public_origin().startswith("https://"),
        samesite="lax",
        path="/",
    )
    return response


@app.get("/auth/callback")
def callback(request:Request,code:str|None=None,state:str|None=None):
    if not code or not state or len(state)>512:
        raise HTTPException(status_code=401,detail="درخواست ورود معتبر نیست.")
    cookie_name=_oidc_state_cookie_name(state)
    # Distinct, safe failures are important here: an authorized Keycloak
    # identity can be pending enrollment, while a missing tenant claim, SQL
    # outage, or license problem must NOT masquerade as a wrong password.
    try:
        origin=_public_origin()
        _,token_url,client_id,client_secret,authenticator=_oidc_config()
    except ConfigurationFailed:
        raise HTTPException(status_code=503,
            detail="تنظیمات ورود سازمانی آوان کامل نیست؛ اتصال Keycloak در GodAdmin بررسی شود.")

    item=pending.pop(state,None)
    if item is None:
        item=_oidc_tx_decode(
            request.cookies.get(cookie_name,""),
            state=state,
            secret=client_secret,
        )
    if item is None or item["expires"]<time.time():
        # A stale browser tab, a pre-deployment callback, or a transaction older
        # than five minutes cannot be safely resumed because PKCE is one-time.
        # Start a fresh authorization flow instead of leaving the user on a JSON
        # dead-end. The current transaction cookie is cleared first.
        response=RedirectResponse(
            origin+"/auth/login?reauth=expired",
            status_code=303,
        )
        response.delete_cookie(cookie_name,path="/")
        response.delete_cookie("avan_login_state",path="/")
        response.headers["Cache-Control"]="no-store"
        return response
    browser_token=request.cookies.get(OIDC_BROWSER_COOKIE,"")
    browser_hash=item.get("browser_hash","")
    if (not _valid_oidc_browser_token(browser_token)
        or not browser_hash
        or not hmac.compare_digest(
            _oidc_browser_hash(browser_token),
            browser_hash,
        )):
        raise HTTPException(status_code=401,detail="درخواست ورود معتبر نیست.")
    try:
        with httpx.Client(timeout=8,follow_redirects=False,trust_env=False) as client:
            token_response=client.post(token_url,data={
                "grant_type":"authorization_code","code":code,
                "client_id":client_id,"client_secret":client_secret,
                "redirect_uri":origin+"/auth/callback",
                "code_verifier":item["verifier"],
            })
        token_response.raise_for_status()
        data=token_response.json()
        access=data.get("access_token","")
        principal=authenticator.authenticate("Bearer "+access)
        # Read claims only after the SAME token has passed signature, issuer,
        # audience, lifetime and tenant verification by the authenticator.
        claims=jwt.decode(access,options={"verify_signature":False},
                          algorithms=["RS256"])
        exp=claims["exp"]
    except AuthenticationFailed:
        raise HTTPException(status_code=403,
            detail="ورود Keycloak انجام شد، اما توکن سازمانی معتبر نیست. در Realm avan ویژگی tenant_id کاربر، نگاشت آن در توکن، Issuer و Audience را بررسی کنید.")
    except httpx.HTTPStatusError:
        raise HTTPException(status_code=502,
            detail="Keycloak درخواست تبادل کد ورود را رد کرد؛ تنظیمات Client avan-bff و آدرس بازگشت بررسی شود.")
    except (httpx.RequestError,ConfigurationFailed):
        raise HTTPException(status_code=503,
            detail="اتصال داخلی آوان به سرویس هویت Keycloak برقرار نیست.")
    except (ValueError,KeyError,TypeError):
        raise HTTPException(status_code=502,
            detail="پاسخ سرویس هویت Keycloak معتبر نیست.")

    from .setup_console import get_setting
    configured_company=get_setting("company") or {}
    configured_tenant=configured_company.get("tenant_id")
    if not configured_tenant:
        raise HTTPException(status_code=503,
            detail="شناسه سازمان در پنل GodAdmin ذخیره نشده است؛ ابتدا مشخصات سازمان را ثبت کنید.")
    if str(principal.tenant_id)!=str(configured_tenant).lower():
        raise HTTPException(status_code=403,
            detail="شناسه سازمان امضاشده حساب Keycloak با سازمان ثبت‌شده در GodAdmin برابر نیست؛ ویژگی tenant_id حساب ardalan را بررسی کنید.")

    from .setup_console import godadmin_identity,is_godadmin
    bound=godadmin_identity()
    platform_admin=bool(bound and is_godadmin(principal))
    if not bound and not _organization_login_ready():
        # Setup owner selects this already signature-verified identity in the
        # admin console. Until then no OIDC user obtains an application session.
        _stage_verified_identity(principal,claims,access)
        response=RedirectResponse("/auth/pending",status_code=303)
        response.delete_cookie(cookie_name,path="/")
        response.delete_cookie("avan_login_state",path="/")
        return response

    # AVAN account authorization is independent from every BPMS binding.
    # Project the bound organizational GodAdmin into the same authorization
    # store used by all operational users. This lets GodAdmin receive explicit
    # BPMS bindings and inherit every module allowed by the organization license
    # without changing the platform GodAdmin role itself.
    from . import native_access
    from .agent_storage import AgentStorageUnavailable
    if platform_admin:
        try:
            native_access.ensure_godadmin_user(
                subject=principal.subject,
                tenant_id=str(principal.tenant_id),
                company_name=configured_company.get("company_name") or "آوان",
                username=claims.get("preferred_username") if isinstance(claims.get("preferred_username"),str) else None,
                name=claims.get("name") if isinstance(claims.get("name"),str) else "GodAdmin",
            )
        except AgentStorageUnavailable:
            pass
    try:
        organization=native_access.read()
    except AgentStorageUnavailable:
        if not platform_admin:
            raise HTTPException(status_code=503,
                detail="بانک داخلی AVAN در دسترس نیست؛ مدیر سامانه باید اتصال Agent DB را بررسی کند.")
        organization={"tenant_id":str(principal.tenant_id),
                      "company_name":"آوان","users":[]}
    stored=next((u for u in organization.get("users",[])
                 if u.get("subject")==principal.subject),None)
    if not stored and not platform_admin:
        _stage_verified_identity(principal,claims,access)
        response=RedirectResponse("/auth/pending",status_code=303)
        response.delete_cookie(cookie_name,path="/")
        response.delete_cookie("avan_login_state",path="/")
        return response
    if stored and not stored.get("enabled"):
        raise HTTPException(status_code=403,detail="حساب AVAN توسط مدیر سامانه غیرفعال شده است.")
    if stored and organization.get("tenant_id")!=str(principal.tenant_id):
        raise HTTPException(status_code=403,detail="حساب AVAN متعلق به این سازمان نیست.")
    if stored and stored.get("role")=="SysAdmin" and "SysAdmin" not in principal.roles:
        raise HTTPException(status_code=403,detail="نقش مدیر سیستم در سرویس هویت تأیید نشده است.")

    if stored:
        preferred=claims.get("preferred_username")
        email=claims.get("email")
        name=claims.get("name")
        # Refresh descriptive AVAN identity claims only; never touch BPMS bindings.
        with native_access.edit() as org:
            target=next((u for u in org.get("users",[])
                         if u.get("subject")==principal.subject),None)
            if target:
                if isinstance(preferred,str) and preferred.strip():
                    target["username"]=preferred.strip()[:180]
                if isinstance(email,str) and email.strip():
                    target["email"]=email.strip()[:240]
                if isinstance(name,str) and name.strip():
                    target["name"]=name.strip()[:250]

    if stored and not platform_admin:
        from .production_license import entitlement,ProductionLicenseDenied
        try:
            entitlement(tenant_id=organization["tenant_id"],
                        company_name=organization["company_name"])
        except ProductionLicenseDenied:
            raise HTTPException(status_code=403,
                detail="لایسنس AVAN برای این سازمان معتبر نیست.")

    _purge()
    if len(sessions)>5000:
        raise HTTPException(status_code=503,detail="ظرفیت نشست‌ها تکمیل است.")
    session_id=secrets.token_urlsafe(48)
    csrf=secrets.token_urlsafe(32)
    sessions[session_id]={"access_token":access,"csrf":csrf,
                          "expires":time.time()+SESSION_MAX_SECONDS,
                          "idle_expires":time.time()+SESSION_IDLE_SECONDS,
                          "access_expires":float(exp),
                          "subject":principal.subject,"tenant_id":str(principal.tenant_id),
                          "id_token":data.get("id_token"),
                          "refresh_token":data.get("refresh_token")}
    response=RedirectResponse("/",status_code=303)
    response.set_cookie("avan_session",session_id,max_age=SESSION_MAX_SECONDS,**_cookie_options())
    response.delete_cookie(cookie_name,path="/")
    response.delete_cookie("avan_login_state",path="/")
    return response


def _stage_verified_identity(principal,claims:dict,access:str):
    from .pending_identities import stage
    from .setup_console import get_setting
    user_claims=claims
    issuer=(get_setting("oidc") or {}).get("issuer","").rstrip("/")
    try:
        with httpx.Client(timeout=7,follow_redirects=False,
                          trust_env=False) as http:
            userinfo_response=http.get(
               issuer+"/protocol/openid-connect/userinfo",
               headers={"Authorization":"Bearer "+access,
                        "Accept":"application/json"})
            userinfo_response.raise_for_status()
            if len(userinfo_response.content)>20000:
                raise ValueError("OIDC UserInfo too large")
            received=userinfo_response.json()
            if received.get("sub")!=principal.subject:
                raise AuthenticationFailed("UserInfo subject mismatch")
            user_claims=received
    except AuthenticationFailed:
        raise HTTPException(status_code=403,
            detail="شناسه حساب در پاسخ سرویس هویت با حساب امضاشده برابر نیست.")
    except (httpx.HTTPError,ValueError,TypeError):
        # Only verified access-token claims may be used as a fallback.
        user_claims=claims
    preferred=user_claims.get("preferred_username")
    if not isinstance(preferred,str) or not preferred.strip():
        preferred=claims.get("preferred_username")
    stage(principal,
          username=preferred.strip() if isinstance(preferred,str) and preferred.strip() else None,
          name=str(user_claims.get("name") or preferred or principal.subject),
          email=user_claims.get("email")
              if isinstance(user_claims.get("email"),str) else None,
          email_verified=user_claims.get("email_verified") is True)


@app.get("/auth/pending")
def pending_approval():
    # No sensitive identity fields or access tokens are sent back to the user.
    return Response("""<!doctype html><html lang="fa" dir="rtl"><meta charset="utf-8">
    <title>آوان | تأیید دسترسی سازمانی</title>
    <body style="font-family:Tahoma,sans-serif;background:#f4f7fa;color:#153853;
                 max-width:650px;margin:12vh auto;padding:24px;line-height:2.2">
    <h1>درخواست دسترسی ثبت شد</h1>
    <p>هویت شما توسط سامانه سازمانی تأیید شد. مدیر سامانه ابتدا حساب
    و مجوزهای AVAN را تأیید می‌کند؛ اتصال شما به هر BPMS به‌صورت جداگانه
    در بخش سازمان و دسترسی انجام می‌شود.</p>
    <a href="/">بازگشت به آوان</a></body></html>""",
                    media_type="text/html; charset=utf-8")


@app.post("/auth/logout")
def logout(request:Request):
    sid=request.cookies.get("avan_session","")
    current=sessions.get(sid)
    origin=request.headers.get("origin")
    csrf=request.headers.get("X-AVAN-CSRF","")
    if current and (not csrf or not hmac.compare_digest(csrf,current["csrf"])
                    or (origin and origin!=_public_origin())):
        raise HTTPException(status_code=403,detail="درخواست خروج معتبر نیست.")
    if sid:
        with _session_lock:
            # A deliberate sign-out invalidates every workspace tab/session
            # of this account, not only the cookie on the current tab.
            if current and current.get("subject") and current.get("tenant_id"):
                for key,value in list(sessions.items()):
                    if (value.get("subject")==current["subject"] and
                        value.get("tenant_id")==current["tenant_id"]):
                        sessions.pop(key,None)
            else:
                sessions.pop(sid,None)
    if current and current.get("monitor_delegated"):
        try:
            from .agent_monitor import end_session_delegation
            end_session_delegation(current)
        except Exception:
            # Session is already revoked locally; the IdP logout remains available.
            pass
    logout_url=None
    if current:
        try:
            _,_,client_id,_,_=_oidc_config()
            from .setup_console import get_setting
            issuer=(get_setting("oidc") or {}).get("issuer","").rstrip("/")
            if issuer and current.get("id_token"):
                logout_url=issuer+"/protocol/openid-connect/logout?"+urlencode({
                    "id_token_hint":current["id_token"],"client_id":client_id,
                    "post_logout_redirect_uri":_public_origin()+"/auth/signed-out"})
        except (ConfigurationFailed,ValueError):
            pass
    response=JSONResponse({"signed_out":True,"logout_url":logout_url})
    response.delete_cookie("avan_session",path="/")
    response.delete_cookie("avan_godadmin",path="/admin")
    return response


@app.get("/auth/signed-out")
def signed_out():
    return RedirectResponse("/",status_code=303)


def _organization_login_ready():
    from . import setup_console as setup
    if setup.godadmin_identity():return True
    state=setup.password_state()
    return state["changed"] and state["totp"]


def _authorized(request:Request):
    from .setup_console import godadmin_identity
    value=_principal_for_request(request)
    if not _organization_login_ready():
        raise HTTPException(status_code=403,detail="راه‌اندازی GodAdmin هنوز تکمیل نشده است.")
    # GodAdmin is a platform capability, not an automatic data entitlement.
    # Organization routes still pass through verified_scope(), so a GodAdmin
    # account sees customer data only when it is also explicitly mapped as an
    # active licensed organization user.
    return value


def _csrf(request:Request):
    from .setup_console import godadmin_identity
    sid,value,principal=_principal_for_request(request)
    if not _organization_login_ready():
        raise HTTPException(status_code=403,detail="راه‌اندازی GodAdmin هنوز تکمیل نشده است.")
    got=request.headers.get("X-AVAN-CSRF","")
    if not got or not hmac.compare_digest(got,value["csrf"]):
        raise HTTPException(status_code=403,detail="توکن اعتبارسنجی درخواست معتبر نیست.")
    # Same-origin header when supplied by modern browsers; the random
    # server-bound CSRF value is required even if Origin is omitted.
    origin=request.headers.get("origin")
    if origin and origin!=_public_origin():
        raise HTTPException(status_code=403,detail="منشأ درخواست مجاز نیست.")
    return sid,value,principal


def _platform_authorized(request:Request):
    from .setup_console import is_godadmin,godadmin_identity
    value=_principal_for_request(request)
    if not godadmin_identity():
        raise HTTPException(status_code=403,detail="راه‌اندازی GodAdmin هنوز تکمیل نشده است.")
    if not is_godadmin(value[2]):
        raise HTTPException(status_code=403,detail="این بخش ویژه GodAdmin است.")
    return value


def _platform_csrf(request:Request):
    sid,value,principal=_platform_authorized(request)
    got=request.headers.get("X-AVAN-CSRF","")
    if not got or not hmac.compare_digest(got,value["csrf"]):
        raise HTTPException(status_code=403,detail="توکن اعتبارسنجی درخواست معتبر نیست.")
    origin=request.headers.get("origin")
    if origin and origin!=_public_origin():
        raise HTTPException(status_code=403,detail="منشأ درخواست مجاز نیست.")
    return sid,value,principal


@app.post("/auth/heartbeat")
def heartbeat(value=Depends(_csrf)):
    return {"active":True,"idle_seconds":SESSION_IDLE_SECONDS}


def _store_response(action, principal):
    """Compatibility path for unscoped ProcessMaker endpoints.

    AVAN never chooses a global/active BPMS for a user. These legacy endpoints
    are available only when the signed AVAN account has exactly one active
    ProcessMaker binding. Multi-BPMS users must use /api/sources/{source_id}/...
    so the external identity is always explicit.
    """
    from .user_bpms_bindings import (
        default_processmaker_source_id,processmaker_bindings_for
    )
    from .agent_storage import AgentStorageUnavailable
    try:
        bindings=processmaker_bindings_for(principal.subject)
        source_id=default_processmaker_source_id(principal.subject)
    except AgentStorageUnavailable:
        bindings=[];source_id=None
    if not bindings:
        raise HTTPException(
            status_code=403,
            detail="هیچ ProcessMaker فعالی به این حساب AVAN متصل نیست."
        )
    if not source_id:
        raise HTTPException(
            status_code=409,
            detail="چند ProcessMaker به این حساب متصل است؛ BPMS موردنظر را انتخاب کنید."
        )
    return _source_store_response(source_id,action,principal)

def _source_store_response(source_id, action, principal):
    """Execute a read only against the exact ProcessMaker source bound to the AVAN user."""
    from .user_bpms_bindings import (
        binding_for,processmaker_profile,BindingError
    )
    if not binding_for(principal.subject,source_id):
        raise HTTPException(status_code=403,detail="این BPMS به حساب AVAN شما متصل نیست.")
    try:
        profile=processmaker_profile(source_id)
        with open_production(config=profile["mysql"]) as con:
            scope=verified_scope(con,principal,source_id=source_id)
            from .process_context import scoped
            scope=scoped(scope)
            return action(con,scope)
    except BindingError:
        raise HTTPException(status_code=404,detail="اتصال ProcessMaker پیدا نشد.")
    except EmployeeMappingRequired as exc:
        reason=str(exc)
        details={
            "Organization is not mapped":"حساب AVAN به سازمان این اتصال BPMS تعلق ندارد.",
            "Active AVAN account required":"حساب AVAN شما فعال نیست؛ مدیر سامانه باید وضعیت کاربر را بررسی کند.",
            "Select an explicitly bound ProcessMaker source; unscoped access is unavailable":"این حساب به ProcessMaker انتخاب‌شده Binding فعال ندارد.",
            "Active ProcessMaker binding required":"Binding ثبت شده است اما کاربر متناظر در ProcessMaker فعال/قابل تطبیق نیست؛ از «دسترسی‌ها» اتصال کاربر را Refresh یا دوباره Bind کنید.",
        }
        raise HTTPException(status_code=403,detail=details.get(reason,"اتصال هویت AVAN به کاربر ProcessMaker برای این BPMS کامل نیست."))
    except ProductionAccessDenied as exc:
        reason=str(exc)
        details={
            "Role not authorized":"نقش فعلی AVAN برای این عملیات BPMS معتبر نیست؛ نقش کاربر و نشست ورود را بررسی کنید.",
            "GodAdmin identity is not bound":"هویت GodAdmin سازمانی کامل متصل نشده است.",
            "Valid license required":"لایسنس AVAN برای دسترسی به این BPMS معتبر نیست.",
            "Hierarchy depth exceeded":"ساختار مدیر/کارمند بیش از حد مجاز عمق دارد و باید اصلاح شود.",
            "ProcessMaker source is not available":"اتصال ProcessMaker انتخاب‌شده فعال یا قابل استفاده نیست.",
            "آداپتور تحلیلی این فرایند نصب نشده است.":"فرایند انتخاب‌شده فقط کارتابل عمومی دارد و Context تخصصی دستیار برای آن نصب نشده است؛ دستیار در سطح BPMS اجرا می‌شود.",
            "آداپتور یا مجوز این فرایند فعال نیست.":"آداپتور یا مجوز فرایند انتخاب‌شده فعال نیست؛ انتخاب فرایند را تازه‌سازی کنید.",
            "قرارداد بسته فرایندی معتبر نیست.":"تعریف فرایند انتخاب‌شده ناقص است و باید در مدیریت سامانه بازبینی شود.",
        }
        raise HTTPException(status_code=403,detail=details.get(reason,"مجوز مشاهده اطلاعات این BPMS وجود ندارد."))
    except ProductionUnavailable:
        raise HTTPException(status_code=503,detail="ارتباط با ProcessMaker انتخاب‌شده برقرار نیست.")
    except HTTPException:
        raise


def _source_capabilities(source:dict,modules)->list[str]:
    """Return only user-facing capabilities implemented for this BPMS source.

    AVAN roles remain independent.  A capability appears only when the source
    type supports a user-scoped route and the organization license enables the
    corresponding AVAN module.
    """
    available=["overview"]
    if source.get("engine")=="processmaker":
        if 1 in modules:available.extend(["meetings","assistant"])
        if 2 in modules:available.append("secretary")
        if 3 in modules:available.extend(["bi","reports"])
        if 4 in modules:available.append("monitor")
    return available


@app.get("/api/me")
def current_user(request:Request):
    from .setup_console import get_setting,is_godadmin,godadmin_identity
    if not godadmin_identity():
        from .setup_routes import bootstrap_workspace_session
        bootstrap=bootstrap_workspace_session(request)
        if bootstrap:
            _,session=bootstrap
            company=get_setting("company") or {}
            return {"name":"GodAdmin","company":company.get("company_name") or "آوان",
                    "role":"GodAdmin","department":"مدیریت سامانه",
                    "csrf":session["csrf"],"subject":"bootstrap-godadmin",
                    "modules":[],"is_godadmin":True,"bootstrap_mode":True,
                    "platform_access":False,"workspace_navigation":False,
                    "workspace_access":False,"workspace_degraded":True,
                    "bpms_sources":[],"source_navigation":False,
                    "license_expires_at":None,"license_mode":"bootstrap"}

    _,session,principal=_principal_for_request(request)
    godadmin=is_godadmin(principal)

    from . import native_access
    from .agent_storage import AgentStorageUnavailable
    if godadmin:
        company=get_setting("company") or {}
        try:
            native_access.ensure_godadmin_user(
                subject=principal.subject,
                tenant_id=str(principal.tenant_id),
                company_name=company.get("company_name") or "آوان",
                username=None,
                name="GodAdmin",
            )
        except AgentStorageUnavailable:
            pass
    try:
        data=native_access.read()
    except AgentStorageUnavailable:
        if not godadmin:
            raise HTTPException(status_code=503,detail="بانک داخلی AVAN در دسترس نیست.")
        data={"tenant_id":str(principal.tenant_id),"company_name":None,"users":[]}
    stored=next((u for u in data.get("users",[])
                 if u.get("subject")==principal.subject and u.get("enabled")),None)

    if not stored:
        if godadmin:
            company=get_setting("company") or {}
            return {"name":"GodAdmin","company":company.get("company_name") or "آوان",
                    "role":"GodAdmin","department":"مدیریت سامانه",
                    "csrf":session["csrf"],"subject":principal.subject,
                    "modules":[1,3],"is_godadmin":True,"bootstrap_mode":False,
                    "platform_access":True,"workspace_navigation":False,
                    "workspace_access":False,"workspace_degraded":True,
                    "bpms_sources":[],"source_navigation":False,
                    "license_expires_at":None,"license_mode":"platform"}
        raise HTTPException(status_code=403,detail="حساب AVAN هنوز توسط مدیر سامانه تأیید نشده است.")

    if data.get("tenant_id")!=str(principal.tenant_id):
        raise HTTPException(status_code=403,detail="حساب AVAN متعلق به این سازمان نیست.")
    if stored.get("role")=="SysAdmin" and "SysAdmin" not in principal.roles:
        raise HTTPException(status_code=403,detail="نقش مدیر سیستم در سرویس هویت تأیید نشده است.")

    from .production_license import entitlement,ProductionLicenseDenied
    try:
        license_data=entitlement(tenant_id=data["tenant_id"],company_name=data["company_name"])
    except ProductionLicenseDenied:
        if godadmin:
            return {"name":stored.get("name") or stored.get("username") or "GodAdmin",
                    "username":stored.get("username"),
                    "company":data.get("company_name") or "آوان",
                    "role":"GodAdmin","department":"مدیریت سامانه",
                    "csrf":session["csrf"],"subject":principal.subject,
                    "modules":[1,3],"is_godadmin":True,"bootstrap_mode":False,
                    "platform_access":True,"workspace_navigation":False,
                    "workspace_access":False,"workspace_degraded":True,
                    "bpms_sources":[],"source_navigation":False,
                    "license_expires_at":None,"license_mode":"platform"}
        raise HTTPException(status_code=403,detail="لایسنس AVAN برای این سازمان معتبر نیست.")

    effective_modules=native_access.effective_modules(stored,license_data["modules"])
    from .user_bpms_bindings import list_bindings,source_catalog
    catalog={x["id"]:x for x in source_catalog()}
    active_bindings=[]
    for binding in list_bindings(principal.subject):
        source=catalog.get(binding.get("source_id"))
        if not source or not source.get("enabled") or binding.get("status")!="active":
            continue
        active_bindings.append({
            "source_id":source["id"],"source_name":source["name"],
            "engine":source["engine"],"connection_type":source["connection_type"],
            "external_user_id":binding.get("external_user_id"),
            "external_username":binding.get("external_username"),
            "external_display_name":binding.get("external_display_name"),
            "capabilities":_source_capabilities(source,effective_modules),
        })

    processmaker_bindings=[b for b in active_bindings if b.get("engine")=="processmaker"]
    # Old generic workspace routes remain only for the unambiguous one-PM case.
    # With multiple BPMS bindings, navigation is entirely source-specific.
    legacy_workspace=len(processmaker_bindings)==1

    return {"name":stored.get("name") or stored.get("username") or principal.subject,
            "username":stored.get("username"),
            "company":data["company_name"],
            "role":stored.get("role"),"department":stored.get("department_name"),
            "csrf":session["csrf"],"subject":principal.subject,
            "modules":sorted(effective_modules),
            "license_expires_at":license_data["expires_at"],
            "license_mode":license_data.get("mode","licensed"),
            "is_godadmin":godadmin,"bootstrap_mode":False,
            "platform_access":godadmin,
            "workspace_navigation":legacy_workspace,
            "workspace_access":bool(active_bindings),
            "workspace_degraded":not bool(active_bindings),
            "bpms_sources":active_bindings,
            "source_navigation":bool(active_bindings)}


@app.get("/api/questions")
def questions(value=Depends(_authorized)):
    _,_,principal=value
    _store_response(lambda con,scope:True,principal)
    return {"questions":PROD_QUESTIONS}


@app.get("/api/sources/{source_id}/questions")
def source_questions(source_id:str,value=Depends(_authorized)):
    _,_,principal=value
    def read(_con,scope):
        if 1 not in scope["license"]["modules"]:
            raise ProductionAccessDenied("Meetings module not licensed")
        return True
    _source_store_response(source_id,read,principal)
    return {"questions":PROD_QUESTIONS}


@app.get("/api/meetings")
def meetings(value=Depends(_authorized),
             cursor:int|None=Query(None,gt=0),
             limit:int=Query(30,ge=1,le=50)):
    _,_,principal=value
    def read(con,scope):
        page=authorized_meetings_page(con,scope,cursor=cursor,limit=limit)
        return {"meetings":page["meetings"],"next_cursor":page["next_cursor"],
                "has_more":page["has_more"]}
    return _store_response(read,principal)


@app.get("/api/sources/{source_id}/meetings")
def source_meetings(source_id:str,value=Depends(_authorized),
                    cursor:int|None=Query(None,gt=0),
                    limit:int=Query(30,ge=1,le=50)):
    _,_,principal=value
    def read(con,scope):
        if 1 not in scope["license"]["modules"]:
            raise ProductionAccessDenied("Meetings module not licensed")
        page=authorized_meetings_page(con,scope,cursor=cursor,limit=limit)
        return {"source_id":source_id,"source_name":scope.get("source_name"),
                "meetings":page["meetings"],"next_cursor":page["next_cursor"],
                "has_more":page["has_more"]}
    return _source_store_response(source_id,read,principal)


@app.get("/api/sources/{source_id}/meetings/{meeting_id}")
def source_meeting_detail(source_id:str,meeting_id:int,value=Depends(_authorized)):
    _,_,principal=value
    def read(con,scope):
        if 1 not in scope["license"]["modules"]:
            raise ProductionAccessDenied("Meetings module not licensed")
        rows,complete=authorized_meeting_snapshot(con,scope,meeting_id=meeting_id)
        _normalise_dates(rows)
        if not rows:raise HTTPException(404,detail="جلسه در این BPMS در دسترس نیست.")
        return {"source_id":source_id,"coverage_complete":complete,**rows[0]}
    return _source_store_response(source_id,read,principal)


def _normalise_dates(records:list[dict])->None:
    from zoneinfo import ZoneInfo
    tz=ZoneInfo(os.getenv("AVAN_DATA_TIMEZONE","Asia/Tehran"))
    for m in records:
        for obj,key in [(m,"meeting_date_utc")]+[
            (a,key) for a in m["actions"] for key in ("due_at_utc","last_submission_at_utc","created_at_utc","closed_at_utc")
        ]:
            raw=obj.get(key)
            if raw is None:continue
            date=datetime.fromisoformat(str(raw).replace("Z","+00:00"))
            if date.tzinfo is None:date=date.replace(tzinfo=tz)
            obj[key]=date.astimezone(timezone.utc).isoformat()


from .agent_routes import register as register_agent_routes
register_agent_routes(app,_authorized,_csrf)
from .process_bi_routes import register as register_bi_routes
register_bi_routes(app,_csrf)
from .process_case_graph_routes import register as register_process_case_graph_routes
register_process_case_graph_routes(app,_csrf)
from .platform_routes import register as register_platform_routes
register_platform_routes(app,_platform_authorized,_platform_csrf)


from .agent_storage import AgentStorageUnavailable

@app.exception_handler(AgentStorageUnavailable)
async def agent_storage_unavailable(request,exc):
    return JSONResponse(status_code=503,content={'detail':'بانک اختصاصی Agent در دسترس نیست؛ تنظیمات SQL Server آوان بررسی شود.'})


# Configured native task inbox replaces legacy owner-only workflow writes.

from .secretary_inbox_routes import register as register_secretary_inbox
register_secretary_inbox(app,_authorized,_csrf)

from .process_workspace import register as register_process_workspaces
register_process_workspaces(app,_authorized)

from .process_context import install as install_process_context
install_process_context(app)
