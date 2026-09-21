"""Operational AVAN application: external OIDC BFF -> read-only MTG reporting.

This is NOT commercial.demo_preview or commercial.api. No synthetic dataset,
old /v1 endpoints, raw JWT in JavaScript, local passwords or database writes.
A customer-visible page is served only after external IdP login; ALL meeting
records are checked against the current signed identity + AVAN.UserAccess.
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

from .meeting_questions import answer_question, _intent
from .production_store import (
    ProductionAccessDenied, ProductionUnavailable, authorized_meetings_page,
    authorized_meeting_snapshot, open_production, verified_scope,
)
from .security import (
    AuthenticationFailed, ConfigurationFailed, VerifiedTokenAuthenticator,
)

@lru_cache(maxsize=1)
def _verifier():
    return VerifiedTokenAuthenticator.from_environment()


ROOT=Path(__file__).resolve().parent/"web"/"production"
PROD_QUESTIONS=(
    "کدام اقدامات مصوب جلسات عقب‌افتاده‌اند؟",
    "مهم‌ترین موضوعات حل‌نشده این ماه شمسی چیست؟",
    "عملکرد واحدها در اجرای مصوبات چگونه بوده است؟",
    "کدام مدیر یا واحد بیشترین اقدامات باز را دارد؟",
    "اقدامات جلسه شماره مشخص در چه وضعیتی هستند؟",
    "مهم‌ترین ریسک‌های ثبت‌شده در جلسات اخیر چیست؟",
    "چه موضوعاتی در جلسات مختلف به‌صورت مکرر مطرح شده‌اند؟",
    "برای جلسه آینده چه مواردی باید در دستور جلسه قرار گیرد؟",
)
sessions={}
pending={}


@asynccontextmanager
async def production_lifespan(_app):
    # Refuse to start an operational container with placeholder credentials,
    # the wrong database, missing issuer material or an untrusted origin.
    import re
    if os.getenv("AVAN_SQL_DATABASE")!="EnterpriseProcess2" or (
        os.getenv("AVAN_SQL_USER","").casefold()!="avan_reader"
    ):
        raise RuntimeError("AVAN requires dedicated EnterpriseProcess2 read-only connection")
    for name in ("AVAN_SQL_SERVER","AVAN_SQL_PASSWORD",
                 "AVAN_OIDC_CLIENT_SECRET","COMMERCIAL_OIDC_CLIENT_ID"):
        value=os.getenv(name,"").strip()
        if not value or value.startswith(("SET_","YOUR_","REPLACE_")):
            raise RuntimeError("Required operational configuration is incomplete: "+name)
    if not re.fullmatch(r"[0-9a-fA-F]{64}",os.getenv("AVAN_INSTALLATION_ID","")):
        raise RuntimeError("Stable licensed installation fingerprint missing")
    _public_origin()
    _oidc_config()
    from .production_license import signed_entitlement
    from pathlib import Path
    if not Path(os.getenv("AVAN_LICENSE_PUBLIC_KEY_PATH","/missing")).is_file():
        raise RuntimeError("Pinned publisher public license key is missing")
    yield


app=FastAPI(title="AVAN",docs_url=None,redoc_url=None,openapi_url=None,
            lifespan=production_lifespan)
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
    value=os.getenv("AVAN_PUBLIC_ORIGIN","").rstrip("/")
    parsed=urlsplit(value)
    if parsed.scheme not in ("http","https") or not parsed.hostname or parsed.path not in ("","/"):
        raise ConfigurationFailed("Public origin must be configured exactly")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ConfigurationFailed("Invalid public origin")
    if parsed.scheme=="http" and parsed.hostname not in ("localhost","127.0.0.1"):
        raise ConfigurationFailed("HTTP origin allowed only on this machine")
    return value


def _oidc_config():
    issuer=os.getenv("COMMERCIAL_OIDC_ISSUER","").rstrip("/")
    auth=os.getenv("COMMERCIAL_OIDC_AUTHORIZATION_URL","")
    token=os.getenv("COMMERCIAL_OIDC_TOKEN_URL","")
    client_id=os.getenv("COMMERCIAL_OIDC_CLIENT_ID","")
    client_secret=os.getenv("AVAN_OIDC_CLIENT_SECRET","")
    verifier=_verifier()
    origin=urlsplit(issuer)
    if (origin.scheme!="https" or
        auth!=issuer+"/protocol/openid-connect/auth" or
        token!=issuer+"/protocol/openid-connect/token" or
        not client_id or len(client_id)>256 or
        not 16<=len(client_secret)<=4096 or
        any(c in client_secret for c in "\r\n")):
        raise ConfigurationFailed("Confidential OIDC client/issuer not configured")
    return auth,token,client_id,client_secret,verifier


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
    return FileResponse(ROOT/"index.html",media_type="text/html; charset=utf-8")


@app.get("/assets/app.css")
def css():
    return FileResponse(ROOT/"app.css",media_type="text/css; charset=utf-8")


@app.get("/assets/app.js")
def javascript():
    return FileResponse(ROOT/"app.js",media_type="text/javascript; charset=utf-8")


@app.get("/auth/login")
def login():
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
        "scope":"openid profile","state":state,
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
    try:
        origin=_public_origin()
        _,token_url,client_id,client_secret,authenticator=_oidc_config()
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
        # A valid IdP subject is not enough: linked and recently verified
        # ProcessMaker user, tenant and organization role must be active.
        with open_production() as con:
            verified_scope(con,principal)
        exp=jwt.decode(access,options={"verify_signature":False},
                       algorithms=["RS256"])["exp"]
    except (httpx.HTTPError,ValueError,KeyError,TypeError,
            AuthenticationFailed,ConfigurationFailed,
            ProductionUnavailable,ProductionAccessDenied) as exc:
        raise HTTPException(status_code=403,
            detail="ورود به پنل مجاز نیست؛ ارتباط هویت و کاربر فعال سازمان بررسی شود.") from exc
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


class Question(BaseModel):
    model_config=ConfigDict(extra="forbid")
    question:str=Field(min_length=3,max_length=350)


def _month_start(now_utc:datetime)->datetime:
    # Operational MTG DATETIME2 is assumed company-local Asia/Tehran.
    # The SQL deployment guide requires verifying this before enabling.
    import jdatetime
    from zoneinfo import ZoneInfo
    tz=ZoneInfo(os.getenv("AVAN_DATA_TIMEZONE","Asia/Tehran"))
    local=now_utc.astimezone(tz)
    jalali=jdatetime.datetime.fromgregorian(datetime=local)
    gregorian=jdatetime.date(jalali.year,jalali.month,1).togregorian()
    return datetime(gregorian.year,gregorian.month,gregorian.day,
                    tzinfo=tz).astimezone(timezone.utc)


def _normalise_dates(records:list[dict])->None:
    from zoneinfo import ZoneInfo
    tz=ZoneInfo(os.getenv("AVAN_DATA_TIMEZONE","Asia/Tehran"))
    for m in records:
        for obj,key in [(m,"meeting_date_utc")]+[
            (a,"due_at_utc") for a in m["actions"]
        ]:
            raw=obj.get(key)
            if raw is None:continue
            date=datetime.fromisoformat(str(raw).replace("Z","+00:00"))
            if date.tzinfo is None:date=date.replace(tzinfo=tz)
            obj[key]=date.astimezone(timezone.utc).isoformat()


@app.post("/api/ask")
def ask(body:Question,value=Depends(_csrf)):
    _,_,principal=value
    def compute(con,scope):
        intent=_intent(body.question)
        required={
            "overdue_actions":4,"next_agenda":2,
            "monthly_unresolved":3,"unit_performance":3,
            "owner_backlog":3,"risks":3,"recurring":3,
        }.get(intent,1)
        if required not in scope["license"]["modules"]:
            raise ProductionAccessDenied("Purchased module not enabled")
        rows,complete=authorized_meeting_snapshot(con,scope)
        _normalise_dates(rows)
        now=datetime.now(timezone.utc)
        answer=answer_question(
            body.question,rows,now=now,data_scope="MTG operational records "
            "visible under verified organization access",
            coverage_complete=complete,
            month_start_utc=_month_start(now),
            calendar_label="شمسی به وقت تهران",
        )
        answer["company"]=scope["company"]
        answer["role"]=scope["role"]
        answer["read_only"]=True
        if answer["intent"]=="risks":
            answer["notes"].append(
              "جدول MTG.Meeting فیلد ریسک ساختاریافته ندارد. "
              "ParkingLot ریسک تلقی نمی‌شود و به جای آن گزارش نشده است."
            )
        return answer
    return _store_response(compute,principal)
