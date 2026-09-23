"""Durable, delegated monitoring. Fresh signed OIDC identity on every run."""

import asyncio
import hashlib
import threading
import time
import secrets
from contextlib import contextmanager
from . import agent_storage
from .agent_workspace import user_key
from .security import AuthenticationFailed, ConfigurationFailed

INDEX = "monitor_jobs"
_LOCKS = [threading.Lock() for _ in range(64)]


@contextmanager
def locked(key):
    # Fixed-size striped locks; one production worker, no unbounded lock registry.
    lock = _LOCKS[int(hashlib.sha256(key.encode()).hexdigest(), 16) % len(_LOCKS)]
    with lock:
        yield


def binding():
    from .production_app import _oidc_config

    _, endpoint, client_id, _, _ = _oidc_config()
    return hashlib.sha256((endpoint + "\n" + client_id).encode()).hexdigest()


def public(job):
    return (
        {
            k: job.get(k)
            for k in (
                "enabled",
                "interval_seconds",
                "next_run",
                "last_run",
                "last_count",
                "last_error",
                "expires_at",
            )
        }
        if job
        else {"enabled": False}
    )


def status(scope, actor):
    with agent_storage.transaction() as tx:
        return public(tx.get(user_key("monitor_job", scope, actor)))


def subscribe(scope, actor, session, enabled, interval=300):
    key = user_key("monitor_job", scope, actor)
    with locked(key), agent_storage.transaction() as tx:
        job = tx.get(key, {}, lock=True)
        if enabled:
            fresh = session.get("refresh_token")
            current_binding = binding()
            if not fresh and job.get("binding") != current_binding:
                raise ValueError("تنظیمات ورود تغییر کرده است؛ دوباره وارد شوید.")
            credential = fresh or job.get("refresh_token")
            if (
                not credential
                or not isinstance(credential, str)
                or len(credential) > 16000
            ):
                raise ValueError(
                    "برای فعال‌سازی پایش پس‌زمینه یک بار دوباره وارد حساب سازمانی شوید."
                )
            if len(tx.get(INDEX, [])) >= 1000 and key not in tx.get(INDEX, []):
                raise ValueError("ظرفیت پایش تکمیل است.")
            job.update(
                {
                    "tenant_id": scope["tenant_id"],
                    "actor": actor,
                    "refresh_token": credential,
                    "binding": current_binding,
                    "enabled": True,
                    "interval_seconds": interval,
                    "next_run": 0,
                    "last_error": None,
                    # Bounded delegation, never an indefinite authority grant.
                    "expires_at": time.time() + 30 * 86400,
                }
            )
        else:
            job.update({"enabled": False, "refresh_token": None, "last_count": None})
        tx.put(key, job)
        ids = tx.get(INDEX, [], lock=True)
        tx.put(INDEX, [x for x in ids if x != key] + ([key] if enabled else []))
        tx.audit(
            scope["tenant_id"],
            actor,
            "MONITOR_SUBSCRIPTION",
            {"status": "enabled" if enabled else "disabled"},
        )
    if enabled:
        session.pop("refresh_token", None)  # Only the job may rotate this credential.
    return public(job)


def renewed_identity(job):
    import httpx
    from .production_app import _oidc_config

    _, endpoint, client_id, secret, verifier = _oidc_config()
    if binding() != job["binding"]:
        raise AuthenticationFailed("Identity configuration changed")
    with httpx.Client(timeout=10, follow_redirects=False, trust_env=False) as client:
        response = client.post(
            endpoint,
            data={
                "grant_type": "refresh_token",
                "refresh_token": job["refresh_token"],
                "client_id": client_id,
                "client_secret": secret,
            },
        )
    if response.status_code in (400, 401, 403):
        raise AuthenticationFailed("Delegation revoked or expired")
    response.raise_for_status()
    if len(response.content) > 65000:
        raise AuthenticationFailed("Invalid identity response")
    data = response.json()
    principal = verifier.authenticate("Bearer " + data.get("access_token", ""))
    if (
        str(principal.tenant_id) != job["tenant_id"]
        or principal.subject != job["actor"]
    ):
        raise AuthenticationFailed("Delegation identity changed")
    refresh = data.get("refresh_token") or job["refresh_token"]
    if not isinstance(refresh, str) or len(refresh) > 16000:
        raise AuthenticationFailed("Invalid delegated credential")
    return principal, refresh


def run_job(key, now=None):
    from fastapi import HTTPException
    from .agent_routes import monitor_for

    now = time.time() if now is None else now
    with locked(key):
        with agent_storage.transaction() as tx:
            job = tx.get(key)
        if not job or not job.get("enabled") or job.get("next_run", 0) > now:
            return
        try:
            if job.get("expires_at", 0) <= now:
                raise AuthenticationFailed("Delegation expired")
            principal, refresh = renewed_identity(job)
            job["refresh_token"] = refresh
            # Persist rotation before accessing PM so transient PM failure cannot
            # strand a successfully rotated identity credential.
            with agent_storage.transaction() as tx:
                tx.put(key, job)
            result = monitor_for(principal)
            job.update(
                {
                    "last_count": result["total"],
                    "last_error": None,
                    "last_run": now,
                    "next_run": now + job["interval_seconds"],
                }
            )
        except (AuthenticationFailed, ConfigurationFailed):
            job.update(
                {
                    "enabled": False,
                    "refresh_token": None,
                    "last_count": None,
                    "last_error": "login_required",
                }
            )
        except HTTPException as exc:
            job.update(
                {
                    "last_count": None,
                    "last_error": (
                        "access_denied"
                        if exc.status_code in (401, 403)
                        else "source_unavailable"
                    ),
                    "next_run": now + 300,
                }
            )
            if exc.status_code in (401, 403):
                job.update({"enabled": False, "refresh_token": None})
        except Exception:
            job.update(
                {
                    "last_count": None,
                    "last_error": "source_unavailable",
                    "next_run": now + 300,
                }
            )
        with agent_storage.transaction() as tx:
            tx.put(key, job)
            if not job["enabled"]:
                ids = tx.get(INDEX, [], lock=True)
                tx.put(INDEX, [x for x in ids if x != key])
                tx.audit(
                    job["tenant_id"],
                    job["actor"],
                    "MONITOR_SUSPENDED",
                    {"error_code": job["last_error"]},
                )


def tick():
    from .setup_console import get_setting

    if not get_setting("agent_sql"):
        return
    with agent_storage.transaction() as tx:
        ids = tx.get(INDEX, [])
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
