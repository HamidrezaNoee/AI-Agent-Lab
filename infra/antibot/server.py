"""AVAN self-hosted anti-bot service backed by ALTCHA proof-of-work.

The service is internal to the Docker network. Browsers never receive the HMAC
secret and no third-party CAPTCHA endpoint is contacted at runtime.
"""
from __future__ import annotations

import base64
import datetime as dt
import json
import os
import re
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from altcha import create_challenge_v1, verify_solution_v1

HOST = "0.0.0.0"
PORT = int(os.getenv("AVAN_ANTIBOT_PORT", "8090"))
SECRET_PATH = Path(os.getenv(
    "AVAN_ANTIBOT_SECRET_PATH",
    "/run/secrets/avan_antibot_hmac_key",
))
MAX_NUMBER = int(os.getenv("AVAN_ANTIBOT_MAX_NUMBER", "75000"))
TTL_SECONDS = int(os.getenv("AVAN_ANTIBOT_TTL_SECONDS", "120"))
_ACTION = re.compile(r"^[a-z0-9][a-z0-9:_-]{0,63}$")
_used: dict[str, float] = {}
_lock = threading.Lock()


def _secret() -> str:
    value = SECRET_PATH.read_text(encoding="utf-8").strip()
    if len(value) < 32 or len(value) > 512 or any(c in value for c in "\r\n"):
        raise RuntimeError("Invalid AVAN anti-bot secret")
    return value


def _prune_used(now: float) -> None:
    for key, expires in list(_used.items()):
        if expires <= now:
            _used.pop(key, None)


def _new_challenge(action: str) -> dict:
    if not _ACTION.fullmatch(action):
        raise ValueError("invalid action")
    expires = dt.datetime.now(dt.timezone.utc) + dt.timedelta(seconds=TTL_SECONDS)
    jti = os.urandom(18).hex()
    challenge = create_challenge_v1(
        algorithm="SHA-256",
        max_number=MAX_NUMBER,
        salt_length=16,
        hmac_key=_secret(),
        expires=expires,
        params={"action": action, "jti": jti},
    )
    return {
        "provider": "altcha-self-hosted",
        "action": action,
        "expiresIn": TTL_SECONDS,
        **challenge.to_dict(),
    }


def _decode_payload(payload: str) -> dict:
    if not isinstance(payload, str) or not payload or len(payload) > 8192:
        raise ValueError("invalid payload")
    raw = base64.b64decode(payload, validate=True)
    if len(raw) > 4096:
        raise ValueError("payload too large")
    value = json.loads(raw.decode("utf-8"))
    if not isinstance(value, dict):
        raise ValueError("invalid payload")
    return value


def _verify(payload: str, action: str) -> tuple[bool, str]:
    if not _ACTION.fullmatch(action):
        return False, "invalid action"
    try:
        decoded = _decode_payload(payload)
        salt = str(decoded.get("salt", ""))
        parts = salt.split("?", 1)
        params = urllib.parse.parse_qs(parts[1] if len(parts) == 2 else "")
        payload_action = (params.get("action") or [""])[0]
        jti = (params.get("jti") or [""])[0]
        exp_raw = (params.get("expires") or ["0"])[0]
        expires = float(exp_raw)
    except (ValueError, TypeError, json.JSONDecodeError, UnicodeDecodeError):
        return False, "invalid payload"
    if payload_action != action or not re.fullmatch(r"[0-9a-f]{36}", jti):
        return False, "challenge mismatch"
    now = time.time()
    if expires <= now:
        return False, "expired"
    with _lock:
        _prune_used(now)
        if jti in _used:
            return False, "replayed"
    verified, error = verify_solution_v1(payload, _secret(), check_expires=True)
    if not verified:
        return False, error or "invalid solution"
    with _lock:
        _prune_used(now)
        if jti in _used:
            return False, "replayed"
        _used[jti] = expires
    return True, ""


class Handler(BaseHTTPRequestHandler):
    server_version = "AVAN-AntiBot/1.0"

    def log_message(self, _format: str, *_args: object) -> None:
        return

    def _json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        parsed = urllib.parse.urlsplit(self.path)
        if parsed.path == "/health":
            self._json(200, {"ok": True, "provider": "altcha-self-hosted"})
            return
        if parsed.path != "/v1/challenge":
            self._json(404, {"error": "not found"})
            return
        action = (urllib.parse.parse_qs(parsed.query).get("action") or [""])[0]
        try:
            self._json(200, _new_challenge(action))
        except (OSError, RuntimeError):
            self._json(503, {"error": "anti-bot service is not configured"})
        except ValueError:
            self._json(400, {"error": "invalid action"})

    def do_POST(self) -> None:
        if urllib.parse.urlsplit(self.path).path != "/v1/verify":
            self._json(404, {"error": "not found"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = 0
        if length <= 0 or length > 12288:
            self._json(400, {"verified": False, "error": "invalid request"})
            return
        try:
            body = json.loads(self.rfile.read(length).decode("utf-8"))
            payload = body.get("payload", "")
            action = body.get("action", "")
            verified, error = _verify(payload, action)
        except (ValueError, TypeError, json.JSONDecodeError, UnicodeDecodeError, OSError, RuntimeError):
            self._json(400, {"verified": False, "error": "invalid request"})
            return
        self._json(200 if verified else 400, {
            "verified": verified,
            "error": error or None,
        })


if __name__ == "__main__":
    _secret()
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
