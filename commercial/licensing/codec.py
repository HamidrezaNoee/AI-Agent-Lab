"""LIMAK Meeting Agent — OFFLINE ECDSA P-256 license codec.

Same trust pattern as Organization Portal: signing private key stays with LIMAK;
customer product receives only the public key. This module DOES NOT install,
activate, or authorize a license by itself; server-side tenant binding, seat
limits and module gates must be checked separately.
"""
from base64 import urlsafe_b64decode, urlsafe_b64encode
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
import json
import re
import uuid

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec


class LicenseInvalid(Exception):
    pass


def _b64(data: bytes) -> str:
    return urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _unb64(text: str) -> bytes:
    if not isinstance(text, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,16000}", text):
        raise LicenseInvalid("Invalid license encoding")
    return urlsafe_b64decode(text + "=" * (-len(text) % 4))


def make_payload(*, tenant_id: str, installation_id: str, customer: str,
                 max_users: int, modules: list[int], expires_at: str | None,
                 issued_at: str | None = None) -> dict:
    try:
        tenant = str(uuid.UUID(tenant_id))
    except (TypeError, ValueError, AttributeError) as exc:
        raise LicenseInvalid("Invalid tenant ID") from exc
    if not re.fullmatch(r"[0-9A-Fa-f]{64}", installation_id or ""):
        raise LicenseInvalid("Installation ID must be a 64-character HEX fingerprint")
    if not isinstance(customer, str) or not 1 <= len(customer.strip()) <= 200:
        raise LicenseInvalid("Invalid customer")
    if type(max_users) is not int or not 1 <= max_users <= 100000:
        raise LicenseInvalid("Invalid maximum seats")
    if not isinstance(modules, list) or not modules or any(
        type(x) is not int or x not in (1, 2, 3, 4) for x in modules
    ) or 1 not in modules or len(set(modules)) != len(modules):
        raise LicenseInvalid("Licensed modules must uniquely include base module 1")
    now = datetime.now(timezone.utc)
    issued = issued_at or now.isoformat()
    try:
        issued_dt = datetime.fromisoformat(issued.replace("Z", "+00:00"))
        expiry_dt = (datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
                     if expires_at else None)
        if issued_dt.tzinfo is None or (expiry_dt is not None and expiry_dt.tzinfo is None):
            raise ValueError("Timezone required")
        if expiry_dt is not None and expiry_dt <= issued_dt:
            raise ValueError("Expiry must be after issuance")
    except (AttributeError, ValueError) as exc:
        raise LicenseInvalid("Invalid ISO-8601 license date") from exc
    return {"version": 1, "license_id": str(uuid.uuid4()),
            "tenant_id": tenant, "customer": customer.strip(),
            "installation_id": installation_id.upper(),
            "max_users": max_users, "modules": sorted(modules),
            "issued_at": issued, "expires_at": expires_at}


def sign_license(payload: dict, private_key) -> str:
    body = json.dumps(payload, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":")).encode("utf-8")
    signature = private_key.sign(body, ec.ECDSA(hashes.SHA256()))
    return _b64(body) + "." + _b64(signature)


def verify_license(token: str, public_key_pem: bytes, *,
                   tenant_id: str, installation_id: str,
                   active_users: int, now: datetime | None = None) -> dict:
    try:
        parts = token.split(".")
        if len(parts) != 2 or len(token) > 20000:
            raise LicenseInvalid("Invalid license token structure")
        raw, signature = _unb64(parts[0]), _unb64(parts[1])
        key = serialization.load_pem_public_key(public_key_pem)
        if not isinstance(key, ec.EllipticCurvePublicKey) or not isinstance(
            key.curve, ec.SECP256R1
        ):
            raise LicenseInvalid("Expected public ECDSA P-256 key")
        key.verify(signature, raw, ec.ECDSA(hashes.SHA256()))
        payload = json.loads(raw.decode("utf-8"))
        if not isinstance(payload, dict) or payload.get("version") != 1:
            raise LicenseInvalid("Unsupported license version")
        if (str(uuid.UUID(payload["tenant_id"])) != str(uuid.UUID(tenant_id)) or
            payload.get("installation_id") != installation_id.upper()):
            raise LicenseInvalid("License is bound to another tenant or installation")
        fields = ("customer", "max_users", "modules", "issued_at", "expires_at")
        if any(f not in payload for f in fields):
            raise LicenseInvalid("Incomplete license payload")
        # Revalidate signed business rules independently; do not trust the issuer UI.
        max_users = payload["max_users"]
        modules = payload["modules"]
        if type(max_users) is not int or not 1 <= max_users <= 100000:
            raise LicenseInvalid("Invalid licensed seat count")
        if type(active_users) is not int or active_users < 0 or active_users > max_users:
            raise LicenseInvalid("Active users exceed licensed seats")
        if (not isinstance(modules,list) or not modules or
            any(type(x) is not int or x not in (1,2,3,4) for x in modules) or
            len(set(modules)) != len(modules) or 1 not in modules):
            raise LicenseInvalid("Invalid licensed module list")
        current = now or datetime.now(timezone.utc)
        issued = datetime.fromisoformat(payload["issued_at"].replace("Z","+00:00"))
        expires_raw = payload["expires_at"]
        expires = (datetime.fromisoformat(expires_raw.replace("Z","+00:00"))
                   if expires_raw is not None else None)
        if issued.tzinfo is None or issued > current + timedelta(minutes=10):
            raise LicenseInvalid("Invalid or future license issuance")
        if expires is not None and (expires.tzinfo is None or expires <= current
                                    or expires <= issued):
            raise LicenseInvalid("License expired")
        if not isinstance(payload["customer"],str) or not payload["customer"].strip():
            raise LicenseInvalid("Invalid customer")
        return payload
    except LicenseInvalid:
        raise
    except (InvalidSignature, ValueError, TypeError, KeyError, UnicodeError) as exc:
        raise LicenseInvalid("Invalid license signature or payload") from exc
