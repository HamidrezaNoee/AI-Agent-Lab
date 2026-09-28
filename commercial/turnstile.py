"""Hybrid AVAN anti-bot verification.

Primary: Cloudflare Turnstile Managed.
Fallback: self-hosted ALTCHA-compatible proof-of-work in the internal Docker network.

The browser receives only the public Turnstile site key and the signed local
challenge. Secrets remain server-side. Cloudflare failures never make the login
surface unavailable because the browser can fall back to the local challenge.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

import httpx

ANTIBOT_URL=os.getenv("AVAN_ANTIBOT_URL","http://antibot:8090").rstrip("/")
SITEVERIFY_URL="https://challenges.cloudflare.com/turnstile/v0/siteverify"
SITE_KEY_PATH=Path(os.getenv(
    "AVAN_TURNSTILE_SITE_KEY_PATH",
    "/run/secrets/avan_turnstile_site_key",
))
SECRET_KEY_PATH=Path(os.getenv(
    "AVAN_TURNSTILE_SECRET_KEY_PATH",
    "/run/secrets/avan_turnstile_secret_key",
))
TEST_SITE_KEY="1x00000000000000000000AA"
TEST_SECRET_KEY="1x0000000000000000000000000000000AA"
_ACTION=re.compile(r"^[a-z0-9][a-z0-9:_-]{0,63}$")


class TurnstileUnavailable(RuntimeError):
    """Raised when neither the primary nor the local anti-bot can be prepared."""


def _action(value:str)->str:
    if not isinstance(value,str) or not _ACTION.fullmatch(value):
        raise TurnstileUnavailable("Invalid anti-bot action")
    return value


def _read_optional(path:Path)->str:
    try:
        value=path.read_text(encoding="utf-8").strip()
    except OSError:
        return ""
    if not value or len(value)>512 or any(c in value for c in "\r\n"):
        return ""
    return value


def _production_required()->bool:
    return os.getenv("AVAN_TURNSTILE_REQUIRE_PRODUCTION","").strip().lower() in {
        "1","true","yes","on"
    }


def _cloudflare_credentials()->tuple[str,str]|None:
    site=_read_optional(SITE_KEY_PATH)
    secret=_read_optional(SECRET_KEY_PATH)
    if not site or not secret:
        return None
    if _production_required() and (site==TEST_SITE_KEY or secret==TEST_SECRET_KEY):
        return None
    return site,secret


def _local_challenge(action:str)->dict:
    try:
        with httpx.Client(
            timeout=httpx.Timeout(4.0,connect=2.0),
            follow_redirects=False,
            trust_env=False,
        ) as client:
            response=client.get(
                ANTIBOT_URL+"/v1/challenge",
                params={"action":action},
                headers={"Accept":"application/json"},
            )
            response.raise_for_status()
            if len(response.content)>8192:
                raise TurnstileUnavailable("Anti-bot response is too large")
            result=response.json()
    except (httpx.HTTPError,ValueError) as exc:
        raise TurnstileUnavailable("Self-hosted anti-bot service is unavailable") from exc
    required=("provider","algorithm","challenge","maxNumber","salt","signature","action")
    if not isinstance(result,dict) or any(not result.get(k) for k in required):
        raise TurnstileUnavailable("Self-hosted anti-bot challenge is invalid")
    if result.get("provider")!="altcha-self-hosted" or result.get("action")!=action:
        raise TurnstileUnavailable("Self-hosted anti-bot challenge mismatch")
    if result.get("algorithm")!="SHA-256":
        raise TurnstileUnavailable("Unsupported anti-bot algorithm")
    try:
        maximum=int(result.get("maxNumber"))
    except (TypeError,ValueError) as exc:
        raise TurnstileUnavailable("Invalid anti-bot difficulty") from exc
    if maximum<1000 or maximum>250000:
        raise TurnstileUnavailable("Invalid anti-bot difficulty")
    return result


def public_config(action:str)->dict:
    action=_action(action)
    credentials=_cloudflare_credentials()
    try:
        local=_local_challenge(action)
    except TurnstileUnavailable:
        local=None
    if not credentials and local is None:
        raise TurnstileUnavailable("No anti-bot provider is available")
    cloudflare={
        "enabled":bool(credentials),
        "site_key":credentials[0] if credentials else "",
        "action":action,
        "timeout_ms":2500,
        "theme":"dark",
        "managed":True,
    }
    return {
        "provider":"hybrid",
        "mode":"cloudflare-primary-altcha-fallback",
        "cloudflare":cloudflare,
        "local":local,
    }


def _verify_cloudflare(token:str,action:str,remote_ip:str|None)->bool:
    credentials=_cloudflare_credentials()
    if not credentials:
        return False
    site_key,secret_key=credentials
    if not token or len(token)>4096 or any(c in token for c in "\r\n"):
        return False
    payload={"secret":secret_key,"response":token}
    if remote_ip and len(remote_ip)<=64:
        payload["remoteip"]=remote_ip
    try:
        with httpx.Client(
            timeout=httpx.Timeout(5.0,connect=2.5),
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
    if not isinstance(result,dict) or result.get("success") is not True:
        return False
    if site_key==TEST_SITE_KEY and secret_key==TEST_SECRET_KEY:
        return True
    return result.get("action")==action


def _verify_local(token:str,action:str)->bool:
    if not token or len(token)>8192 or any(c in token for c in "\r\n"):
        return False
    try:
        with httpx.Client(
            timeout=httpx.Timeout(4.0,connect=2.0),
            follow_redirects=False,
            trust_env=False,
        ) as client:
            response=client.post(
                ANTIBOT_URL+"/v1/verify",
                json={"payload":token,"action":action},
                headers={"Accept":"application/json"},
            )
            if response.status_code!=200 or len(response.content)>8192:
                return False
            result=response.json()
    except (httpx.HTTPError,ValueError):
        return False
    return isinstance(result,dict) and result.get("verified") is True


def verify(token:str,*,action:str,remote_ip:str|None=None)->bool:
    action=_action(action)
    if not isinstance(token,str):
        return False
    token=token.strip()
    if not token or len(token)>12288 or any(c in token for c in "\r\n"):
        return False
    try:
        envelope=json.loads(token)
    except ValueError:
        return False
    if not isinstance(envelope,dict):
        return False
    provider=envelope.get("provider")
    value=envelope.get("token")
    if not isinstance(value,str):
        return False
    if provider=="cloudflare-turnstile":
        return _verify_cloudflare(value,action,remote_ip)
    if provider=="altcha-self-hosted":
        return _verify_local(value,action)
    return False
