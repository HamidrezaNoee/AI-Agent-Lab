"""Compatibility client for AVAN's self-hosted anti-bot service.

The historical module name is kept to avoid breaking existing imports. Runtime
verification no longer calls Cloudflare: challenge creation and proof
verification happen inside the Docker network via the internal AVAN anti-bot
service.
"""
from __future__ import annotations

import os
import re

import httpx

ANTIBOT_URL=os.getenv("AVAN_ANTIBOT_URL","http://antibot:8090").rstrip("/")
_ACTION=re.compile(r"^[a-z0-9][a-z0-9:_-]{0,63}$")


class TurnstileUnavailable(RuntimeError):
    """Backward-compatible error name for anti-bot service unavailability."""


def _action(value:str)->str:
    if not isinstance(value,str) or not _ACTION.fullmatch(value):
        raise TurnstileUnavailable("Invalid anti-bot action")
    return value


def public_config(action:str)->dict:
    action=_action(action)
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


def verify(token:str,*,action:str,remote_ip:str|None=None)->bool:
    del remote_ip  # The bootstrap route already applies local-host and rate-limit checks.
    action=_action(action)
    if not isinstance(token,str):
        return False
    token=token.strip()
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
