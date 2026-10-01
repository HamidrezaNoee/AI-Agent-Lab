"""Durable multi-BPMS monitoring with one delegated OIDC credential per AVAN user.

The credential belongs to the AVAN identity, while scheduling/status belongs to
individual BPMS source subscriptions. Refresh-token rotation therefore happens
under one actor lock and can safely serve several source subscriptions.
"""

import asyncio
import hashlib
import threading
import time
from contextlib import contextmanager

from . import agent_storage
from .agent_workspace import user_key
from .security import AuthenticationFailed, ConfigurationFailed

INDEX="monitor_jobs"
_LOCKS=[threading.Lock() for _ in range(64)]


@contextmanager
def locked(key):
    lock=_LOCKS[int(hashlib.sha256(key.encode()).hexdigest(),16)%len(_LOCKS)]
    with lock:
        yield


def _source_id(scope):
    return str(scope.get("source_id") or "default")


def _job_key(scope,actor):
    # Deliberately actor-scoped, not source-scoped: one rotating delegated
    # credential serves all of this AVAN user's BPMS subscriptions.
    return user_key("monitor_job",scope,actor)


def binding():
    from .production_app import _oidc_config
    _,endpoint,client_id,_,_=_oidc_config()
    return hashlib.sha256((endpoint+"\n"+client_id).encode()).hexdigest()


def _public_subscription(subscription):
    if not subscription:
        return {"enabled":False}
    return {k:subscription.get(k) for k in (
        "enabled","interval_seconds","next_run","last_run","last_count",
        "last_error","expires_at","source_id"
    )}


def _normalise(job,fallback_source=None):
    """Accept pre-multi-source jobs without granting them to a named source."""
    if not isinstance(job,dict):
        job={}
    subscriptions=job.get("subscriptions")
    if not isinstance(subscriptions,dict):
        subscriptions={}
        if job.get("enabled"):
            sid=str(fallback_source or "default")
            subscriptions[sid]={
                "source_id":sid,
                "enabled":True,
                "interval_seconds":int(job.get("interval_seconds") or 300),
                "next_run":float(job.get("next_run") or 0),
                "last_run":job.get("last_run"),
                "last_count":job.get("last_count"),
                "last_error":job.get("last_error"),
                "expires_at":job.get("expires_at"),
            }
    job["subscriptions"]=subscriptions
    job["enabled"]=any(bool(s.get("enabled")) for s in subscriptions.values()
                       if isinstance(s,dict))
    return job


def public(job,source_id="default"):
    job=_normalise(job)
    return _public_subscription(job["subscriptions"].get(str(source_id)))


def status(scope,actor):
    key=_job_key(scope,actor)
    sid=_source_id(scope)
    with agent_storage.transaction() as tx:
        job=_normalise(tx.get(key),sid)
    return public(job,sid)


def subscribe(scope,actor,session,enabled,interval=300):
    sid=_source_id(scope)
    key=_job_key(scope,actor)
    now=time.time()
    with locked(key),agent_storage.transaction() as tx:
        job=_normalise(tx.get(key,{},lock=True),sid)
        subscriptions=job["subscriptions"]
        current_binding=binding()

        if enabled:
            fresh=session.get("refresh_token")
            if not fresh and job.get("binding")!=current_binding:
                raise ValueError("تنظیمات ورود تغییر کرده است؛ دوباره وارد شوید.")
            credential=fresh or job.get("refresh_token")
            if (not credential or not isinstance(credential,str)
                    or len(credential)>16000):
                raise ValueError(
                    "برای فعال‌سازی پایش پس‌زمینه یک بار دوباره وارد حساب سازمانی شوید."
                )
            ids=tx.get(INDEX,[])
            if len(ids)>=1000 and key not in ids:
                raise ValueError("ظرفیت پایش تکمیل است.")
            job.update({
                "tenant_id":str(scope["tenant_id"]),
                "actor":actor,
                "refresh_token":credential,
                "binding":current_binding,
                "expires_at":now+30*86400,
            })
            subscriptions[sid]={
                "source_id":sid,
                "enabled":True,
                "interval_seconds":interval,
                "next_run":0,
                "last_run":subscriptions.get(sid,{}).get("last_run"),
                "last_count":subscriptions.get(sid,{}).get("last_count"),
                "last_error":None,
                "expires_at":now+30*86400,
            }
        else:
            current=dict(subscriptions.get(sid) or {"source_id":sid})
            current.update({"enabled":False,"last_count":None})
            subscriptions[sid]=current

        job["subscriptions"]=subscriptions
        job["enabled"]=any(bool(s.get("enabled")) for s in subscriptions.values())
        if not job["enabled"]:
            if session.get("monitor_delegated") and job.get("refresh_token"):
                session["refresh_token"]=job["refresh_token"]
                session.pop("monitor_delegated",None)
            job["refresh_token"]=None

        tx.put(key,job)
        ids=tx.get(INDEX,[],lock=True)
        tx.put(INDEX,[x for x in ids if x!=key]+([key] if job["enabled"] else []))
        tx.audit(str(scope["tenant_id"]),actor,"MONITOR_SUBSCRIPTION",{
            "status":"enabled" if enabled else "disabled",
            "source_id":sid,
        })

    if job["enabled"]:
        session["monitor_delegated"]=True
        session["tenant_id"]=str(scope["tenant_id"])
        session["subject"]=actor
        session.pop("refresh_token",None)
    return public(job,sid)


def renewed_identity(job,return_tokens=False):
    import httpx
    from .production_app import _oidc_config

    _,endpoint,client_id,secret,verifier=_oidc_config()
    if binding()!=job["binding"]:
        raise AuthenticationFailed("Identity configuration changed")
    with httpx.Client(timeout=10,follow_redirects=False,trust_env=False) as client:
        response=client.post(endpoint,data={
            "grant_type":"refresh_token",
            "refresh_token":job["refresh_token"],
            "client_id":client_id,
            "client_secret":secret,
        })
    if response.status_code in (400,401,403):
        raise AuthenticationFailed("Delegation revoked or expired")
    response.raise_for_status()
    if len(response.content)>65000:
        raise AuthenticationFailed("Invalid identity response")
    data=response.json()
    principal=verifier.authenticate("Bearer "+data.get("access_token",""))
    if (str(principal.tenant_id)!=job["tenant_id"]
            or principal.subject!=job["actor"]):
        raise AuthenticationFailed("Delegation identity changed")
    refresh=data.get("refresh_token") or job["refresh_token"]
    if not isinstance(refresh,str) or len(refresh)>16000:
        raise AuthenticationFailed("Invalid delegated credential")
    return (principal,refresh,data) if return_tokens else (principal,refresh)


def renew_for_session(session):
    scope={"tenant_id":session["tenant_id"]}
    key=_job_key(scope,session["subject"])
    with locked(key):
        with agent_storage.transaction() as tx:
            job=_normalise(tx.get(key))
        if (not job.get("enabled") or not job.get("refresh_token")
                or job.get("expires_at",0)<=time.time()):
            raise AuthenticationFailed("Monitoring credential unavailable")
        principal,refresh,tokens=renewed_identity(job,return_tokens=True)
        if (principal.subject!=session["subject"]
                or str(principal.tenant_id)!=session["tenant_id"]):
            raise AuthenticationFailed("Monitoring identity changed")
        job["refresh_token"]=refresh
        with agent_storage.transaction() as tx:
            tx.put(key,job)
        return tokens


def end_session_delegation(session):
    if not session.get("monitor_delegated"):
        return
    scope={"tenant_id":session["tenant_id"]}
    key=_job_key(scope,session["subject"])
    with locked(key),agent_storage.transaction() as tx:
        job=_normalise(tx.get(key,{},lock=True))
        for subscription in job["subscriptions"].values():
            if isinstance(subscription,dict):
                subscription.update(enabled=False,last_error="login_required")
        job.update(enabled=False,refresh_token=None)
        tx.put(key,job)
        ids=tx.get(INDEX,[],lock=True)
        tx.put(INDEX,[value for value in ids if value!=key])


def _disable_all(job,error_code):
    for subscription in job.get("subscriptions",{}).values():
        if isinstance(subscription,dict) and subscription.get("enabled"):
            subscription.update(enabled=False,last_count=None,last_error=error_code)
    job.update(enabled=False,refresh_token=None)


def run_job(key,now=None):
    from fastapi import HTTPException
    from .agent_routes import monitor_for

    now=time.time() if now is None else now
    with locked(key):
        with agent_storage.transaction() as tx:
            job=_normalise(tx.get(key))
        if not job or not job.get("enabled"):
            return

        due=[
            (sid,sub) for sid,sub in job["subscriptions"].items()
            if isinstance(sub,dict) and sub.get("enabled")
            and float(sub.get("next_run") or 0)<=now
        ]
        if not due:
            return

        try:
            if job.get("expires_at",0)<=now:
                raise AuthenticationFailed("Delegation expired")
            principal,refresh=renewed_identity(job)
            job["refresh_token"]=refresh
            # Persist token rotation before any BPMS read.
            with agent_storage.transaction() as tx:
                tx.put(key,job)
        except (AuthenticationFailed,ConfigurationFailed):
            _disable_all(job,"login_required")
            due=[]
        except Exception:
            for _,sub in due:
                sub.update(last_count=None,last_error="source_unavailable",
                           next_run=now+300)
            due=[]

        for sid,sub in due:
            source_arg=None if sid=="default" else sid
            try:
                result=monitor_for(principal,source_arg)
                sub.update({
                    "last_count":result["total"],
                    "last_error":None,
                    "last_run":now,
                    "next_run":now+int(sub["interval_seconds"]),
                    "expires_at":job.get("expires_at"),
                })
            except HTTPException as exc:
                denied=exc.status_code in (401,403)
                sub.update({
                    "last_count":None,
                    "last_error":"access_denied" if denied else "source_unavailable",
                    "next_run":now+300,
                })
                if denied:
                    sub["enabled"]=False
            except Exception:
                sub.update(last_count=None,last_error="source_unavailable",
                           next_run=now+300)

        job["enabled"]=any(bool(s.get("enabled"))
                           for s in job.get("subscriptions",{}).values()
                           if isinstance(s,dict))
        with agent_storage.transaction() as tx:
            tx.put(key,job)
            if not job["enabled"]:
                ids=tx.get(INDEX,[],lock=True)
                tx.put(INDEX,[x for x in ids if x!=key])
                tx.audit(job.get("tenant_id",""),job.get("actor",""),
                         "MONITOR_SUSPENDED",{"error_code":"no_active_subscription"})


def tick():
    from .setup_console import get_setting
    if not get_setting("agent_sql"):
        return
    with agent_storage.transaction() as tx:
        ids=tx.get(INDEX,[])
    for key in ids[:1000]:
        run_job(key)


async def worker():
    import logging
    from starlette.concurrency import run_in_threadpool
    while True:
        await asyncio.sleep(30)
        try:
            await run_in_threadpool(tick)
        except Exception:
            logging.getLogger(__name__).warning("Monitoring database unavailable")
