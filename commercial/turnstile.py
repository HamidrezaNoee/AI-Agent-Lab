"""Cloudflare Turnstile verification for AVAN authentication surfaces.

The public site key is safe to expose in the browser. The secret key is read
from a Docker secret and is never returned by an AVAN API. Validation is
fail-closed: a network error, malformed response, expired/replayed token or
wrong action rejects authentication.
"""
from __future__ import annotations

from pathlib import Path
import os
import secrets

import httpx

SITEVERIFY_URL="https://challenges.cloudflare.com/turnstile/v0/siteverify"
TEST_SITE_KEY="1x00000000000000000000AA"
TEST_SECRET_KEY="1x0000000000000000000000000000000AA"
SITE_KEY_PATH=Path(os.getenv(
    "AVAN_TURNSTILE_SITE_KEY_PATH",
    "/run/secrets/avan_turnstile_site_key"))
SECRET_KEY_PATH=Path(os.getenv(
    "AVAN_TURNSTILE_SECRET_KEY_PATH",
    "/run/secrets/avan_turnstile_secret_key"))


class TurnstileUnavailable(RuntimeError):
    pass


def _read(path:Path,label:str)->str:
    try:
        value=path.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise TurnstileUnavailable(label+" is not configured") from exc
    if not value or len(value)>512 or any(c in value for c in "\r\n"):
        raise TurnstileUnavailable(label+" is invalid")
    return value


def credentials()->tuple[str,str]:
    site_key=_read(SITE_KEY_PATH,"Turnstile site key")
    secret_key=_read(SECRET_KEY_PATH,"Turnstile secret key")
    if production_required() and (
        site_key==TEST_SITE_KEY or secret_key==TEST_SECRET_KEY
    ):
        raise TurnstileUnavailable(
            "Cloudflare Turnstile production credentials are required")
    return site_key,secret_key


def production_required()->bool:
    return os.getenv("AVAN_TURNSTILE_REQUIRE_PRODUCTION","").strip().lower() in {
        "1","true","yes","on"
    }


def public_config(action:str)->dict:
    site_key,_=credentials()
    return {
        "provider":"cloudflare-turnstile",
        "site_key":site_key,
        "action":action,
        "theme":"dark",
        "size":"flexible",
        "managed":True,
    }


def verify(token:str,*,action:str,remote_ip:str|None=None)->bool:
    if not isinstance(token,str):
        return False
    token=token.strip()
    if not token or len(token)>2048 or any(c in token for c in "\r\n"):
        return False
    site_key,secret_key=credentials()
    payload={
        "secret":secret_key,
        "response":token,
        "idempotency_key":secrets.token_hex(16),
    }
    if remote_ip and len(remote_ip)<=64:
        payload["remoteip"]=remote_ip
    try:
        with httpx.Client(
            timeout=httpx.Timeout(6.0,connect=3.0),
            follow_redirects=False,
            trust_env=False,
        ) as client:
            response=client.post(
                SITEVERIFY_URL,
                data=payload,
                headers={
                    "Accept":"application/json",
                    "Content-Type":"application/x-www-form-urlencoded",
                },
            )
            if response.status_code!=200 or len(response.content)>16384:
                return False
            result=response.json()
    except (httpx.HTTPError,ValueError):
        return False
    if result.get("success") is not True:
        return False
    # Cloudflare test credentials intentionally return action="test".
    if site_key==TEST_SITE_KEY and secret_key==TEST_SECRET_KEY:
        return True
    return result.get("action")==action
