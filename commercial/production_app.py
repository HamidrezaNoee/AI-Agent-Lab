"""Operational AVAN: OIDC + SQL-authorized meeting analysis and secretary drafts.
MTG stays read-only. AI tools receive freshly authorized bounded snapshots;
local review drafts and monitoring observations are encrypted and audited.
"""
from __future__ import annotations
from datetime import datetime, timezone, timedelta
from contextlib import asynccontextmanager
from functools import lru_cache
from pathlib import Path
import hashlib, hmac, os, secrets, time
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
    "مهم‌ترین موضوعات حل‌نشده این ماه شمسی چیست؟",
    "عملکرد واحدها در اجرای مصوبات چگونه بوده است؟",
    "کدام مدیر یا واحد بیشترین اقدامات باز را دارد؟",
    "اقدامات جلسه شماره مشخص در چه وضعیتی هستند؟",
    "مهم‌ترین ریسک‌های قابل مشاهده در جلسات اخیر چیست؟",
    "چه موضوعاتی در جلسات مختلف به‌صورت مکرر مطرح شده‌اند؟",
    "برای جلسه آینده چه مواردی باید در دستور جلسه قرار گیرد؟",
)
sessions={}
pending={}


@asynccontextmanager
async def production_lifespan(_app):
    # The control plane is deliberately independent of operational SQL/IdP.
    # First Docker start therefore succeeds without .env or live credentials.
    from .setup_console import initialize
    initialize()
    import asyncio
    from .agent_routes import monitor_worker
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
    response.headers["X-Frame-Options"]="DENY"
    response.headers["Referrer-Policy"]="no-referrer"
    response.headers["Content-Security-Policy"]=(
        "default-src 'none'; script-src 'self'; style-src 'self'; "
        "connect-src 'self'; img-src 'self' data:; font-src 'self'; "
        "form-action 'self'; base-uri 'none'; frame-ancestors 'none'"
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
        if val["expires"]<now:sessions.pop(key,None)


def _cookie_options():
    return {"httponly":True,"secure":_public_origin().startswith("https://"),
            "samesite":"lax","path":"/"}


def _principal_for_request(request:Request):
    _purge()
    session_id=request.cookies.get("avan_session","")
    value=sessions.get(session_id)
    if not value:
        raise HTTPException(status_code=401,detail="ورود سازمانی الزامی است.")
    try:
        _,_,_,_,authenticator=_oidc_config()
        principal=authenticator.authenticate("Bearer "+value["access_token"])
    except (ConfigurationFailed,AuthenticationFailed):
        sessions.pop(session_id,None)
        raise HTTPException(status_code=401,detail="نشست شما معتبر نیست؛ دوباره وارد شوید.")
    return session_id,value,principal


@app.get("/health")
def health():
    # Process liveness only; never claim a live DB/IdP/license based on /health.
    return {"status":"up","service":"avan",
            "database_checked":False,"identity_checked":False}


@app.get("/")
def home():
    from .setup_console import get_setting
    if not get_setting("mysql") or not get_setting("agent_sql") or not get_setting("oidc"):
        return RedirectResponse("/admin/",status_code=303)
    return FileResponse(ROOT/"index.html",media_type="text/html; charset=utf-8")


@app.get("/assets/app.css")
def css():
    return FileResponse(ROOT/"app.css",media_type="text/css; charset=utf-8")


@app.get("/assets/app.js")
def javascript():
    return FileResponse(ROOT/"app.js",media_type="text/javascript; charset=utf-8")


@app.get("/auth/login")
def login(request:Request):
    # OIDC state cookie is host-only. Normalize localhost to the configured
    # 127.0.0.1 redirect origin BEFORE setting it, otherwise the callback
    # cannot receive the cookie and valid authorization is rejected.
    if (_public_origin()=="http://127.0.0.1:8188"
        and request.url.hostname=="localhost"):
        return RedirectResponse("http://127.0.0.1:8188/auth/login",status_code=303)
    try:
        origin=_public_origin()
        authorization,_,client_id,_,_= _oidc_config()
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
    pending[state]={"verifier":verifier,"expires":time.time()+300}
    redirect_url=authorization+"?"+urlencode({
        "response_type":"code","client_id":client_id,
        "redirect_uri":origin+"/auth/callback",
        "scope":"openid profile email","state":state,
        "code_challenge":challenge,"code_challenge_method":"S256",
    })
    response=RedirectResponse(redirect_url,status_code=302)
    response.set_cookie("avan_login_state",state,max_age=300,**_cookie_options())
    return response


@app.get("/auth/callback")
def callback(request:Request,code:str|None=None,state:str|None=None):
    if not code or not state or not hmac.compare_digest(
        request.cookies.get("avan_login_state",""),state):
        raise HTTPException(status_code=401,detail="درخواست ورود معتبر نیست.")
    item=pending.pop(state,None)
    if item is None or item["expires"]<time.time():
        raise HTTPException(status_code=401,detail="مهلت ورود به پایان رسیده است.")
    # Distinct, safe failures are important here: an authorized Keycloak
    # identity can be pending enrollment, while a missing tenant claim, SQL
    # outage, or license problem must NOT masquerade as a wrong password.
    try:
        origin=_public_origin()
        _,token_url,client_id,client_secret,authenticator=_oidc_config()
    except ConfigurationFailed:
        raise HTTPException(status_code=503,
            detail="تنظیمات ورود سازمانی آوان کامل نیست؛ اتصال Keycloak در GodAdmin بررسی شود.")
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

    try:
        with open_production() as con:
            verified_scope(con,principal)
    except EmployeeMappingRequired:
        # No meeting read or organizational role is granted here. A verified
        # identity is staged for explicit GodAdmin + active PM user approval.
        from .pending_identities import stage
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
            # Signed access-token claims are a fallback only after successful
            # signature verification; never accept browser-submitted email.
            user_claims=claims
        stage(principal,name=str(user_claims.get("name") or
              claims.get("preferred_username") or principal.subject),
              email=user_claims.get("email")
                  if isinstance(user_claims.get("email"),str) else None,
              email_verified=user_claims.get("email_verified") is True)
        response=RedirectResponse("/auth/pending",status_code=303)
        response.delete_cookie("avan_login_state",path="/")
        return response
    except ProductionUnavailable:
        raise HTTPException(status_code=503,
            detail="حساب Keycloak تأیید شد اما اتصال عملیاتی SQL آوان برقرار نیست؛ تنظیمات SQL و ساختار AVAN در GodAdmin بررسی شود.")
    except ProductionAccessDenied:
        raise HTTPException(status_code=403,
            detail="هویت سازمانی تأیید شد اما دسترسی اطلاعات جلسات هنوز فعال نیست؛ وضعیت سازمان، نقش کاربر و لایسنس امضاشده آوان در GodAdmin بررسی شود.")
    except Exception:
        # Do not expose SQL exception strings, bearer tokens, user information
        # or operational table names through public identity endpoints.
        raise HTTPException(status_code=503,
            detail="دسترسی به داده‌های ProcessMaker تأیید نشد؛ اتصال MySQL و نگاشت کاربر را در GodAdmin بررسی کنید.")

    _purge()
    if len(sessions)>5000:
        raise HTTPException(status_code=503,detail="ظرفیت نشست‌ها تکمیل است.")
    session_id=secrets.token_urlsafe(48)
    csrf=secrets.token_urlsafe(32)
    sessions[session_id]={"access_token":access,"csrf":csrf,
                          "expires":min(float(exp),time.time()+3600)}
    response=RedirectResponse("/",status_code=303)
    response.set_cookie("avan_session",session_id,max_age=3600,**_cookie_options())
    response.delete_cookie("avan_login_state",path="/")
    return response


@app.get("/auth/pending")
def pending_approval():
    # No sensitive identity fields or access tokens are sent back to the user.
    return Response("""<!doctype html><html lang="fa" dir="rtl"><meta charset="utf-8">
    <title>آوان | تأیید دسترسی سازمانی</title>
    <body style="font-family:Tahoma,sans-serif;background:#f4f7fa;color:#153853;
                 max-width:650px;margin:12vh auto;padding:24px;line-height:2.2">
    <h1>درخواست دسترسی ثبت شد</h1>
    <p>هویت شما توسط سامانه سازمانی تأیید شد. پیش از مشاهده جلسات،
    مدیر سامانه باید ارتباط حساب شما با کاربر فعال ProcessMaker و
    مجوزهای سازمانی را تأیید کند.</p>
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
    if sid:sessions.pop(sid,None)
    response=JSONResponse({"signed_out":True})
    response.delete_cookie("avan_session",path="/")
    return response


def _authorized(request:Request):
    return _principal_for_request(request)


def _csrf(request:Request):
    sid,value,principal=_principal_for_request(request)
    got=request.headers.get("X-AVAN-CSRF","")
    if not got or not hmac.compare_digest(got,value["csrf"]):
        raise HTTPException(status_code=403,detail="توکن اعتبارسنجی درخواست معتبر نیست.")
    # Same-origin header when supplied by modern browsers; the random
    # server-bound CSRF value is required even if Origin is omitted.
    origin=request.headers.get("origin")
    if origin and origin!=_public_origin():
        raise HTTPException(status_code=403,detail="منشأ درخواست مجاز نیست.")
    return sid,value,principal


def _store_response(action, principal):
    try:
        with open_production() as con:
            scope=verified_scope(con,principal)
            return action(con,scope)
    except ProductionAccessDenied:
        raise HTTPException(status_code=403,detail="مجوز مشاهده این اطلاعات وجود ندارد.")
    except ProductionUnavailable:
        raise HTTPException(status_code=503,detail="ارتباط امن با اطلاعات سازمان برقرار نیست.")
    except HTTPException:
        raise
    except Exception:
        # DB schema drift, driver exceptions or locale configuration errors
        # must never echo SQL / identity / secrets back to the browser.
        raise HTTPException(status_code=503,
                            detail="داده‌های سازمانی قابل بازیابی نیستند؛ تنظیمات سرور بررسی شود.")


@app.get("/api/me")
def current_user(value=Depends(_authorized)):
    _,session,principal=value
    scope=_store_response(lambda con,scope:scope,principal)
    license_data=scope["license"]
    return {"name":scope["name"],"company":scope["company"],
            "role":scope["role"],"department":scope["department"],
            "csrf":session["csrf"],"subject":principal.subject,
            "modules":sorted(license_data["modules"]),
            "license_expires_at":license_data["expires_at"]}


@app.get("/api/questions")
def questions(value=Depends(_authorized)):
    _,_,principal=value
    _store_response(lambda con,scope:True,principal)
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


from .agent_storage import AgentStorageUnavailable

@app.exception_handler(AgentStorageUnavailable)
async def agent_storage_unavailable(request,exc):
    return JSONResponse(status_code=503,content={'detail':'بانک اختصاصی Agent در دسترس نیست؛ تنظیمات SQL Server آوان بررسی شود.'})
