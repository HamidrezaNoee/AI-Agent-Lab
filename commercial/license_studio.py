"""Offline license issuer/validator compatible with the Organization Portal pattern.

ECDSA P-256. Private key remains ONLY with LIMAK. Customer installation receives
only the public key. This module has no private key or development bypass.
"""
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
import base64, hashlib, json, re, uuid

def _b64(data: bytes)->str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")
def _unb64(value:str)->bytes:
    return base64.urlsafe_b64decode(value+"="*((4-len(value)%4)%4))
def canonical(payload:dict)->bytes:
    return json.dumps(payload,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()

@dataclass(frozen=True)
class LicensePayload:
    license_id:str
    customer:str
    installation_id:str
    max_users:int
    issued_at:str
    expires_at:str|None
    edition:str
    features:list[str]

def installation_id(machine_fingerprint:str)->str:
    if not machine_fingerprint.strip(): raise ValueError("Empty machine fingerprint")
    return hashlib.sha256(("AI-Agent-Lab|"+machine_fingerprint.strip()).encode()).hexdigest().upper()

def issue(private_pem:bytes,customer:str,installation:str,max_users:int,
          expires_at:str|None,edition:str,features:list[str])->str:
    from cryptography.hazmat.primitives import hashes,serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    if not re.fullmatch(r"[0-9A-Fa-f]{64}",installation): raise ValueError("Invalid installation id")
    if not 1<=max_users<=100000: raise ValueError("Invalid user capacity")
    key=serialization.load_pem_private_key(private_pem,password=None)
    if not isinstance(key,ec.EllipticCurvePrivateKey): raise ValueError("ECDSA key required")
    payload=LicensePayload(uuid.uuid4().hex,customer.strip(),installation.upper(),max_users,
      datetime.now(timezone.utc).isoformat(),expires_at,edition.strip(),
      sorted(set(x.strip() for x in features if x.strip()),key=str.casefold))
    raw=canonical(asdict(payload));sig=key.sign(raw,ec.ECDSA(hashes.SHA256()))
    return "LIMAK-AIA1."+_b64(raw)+"."+_b64(sig)

def validate(public_pem:bytes,token:str,expected_installation:str)->LicensePayload:
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives import hashes,serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    parts=token.strip().split(".")
    if len(parts)!=3 or parts[0]!="LIMAK-AIA1": raise ValueError("Invalid license format")
    raw,sig=_unb64(parts[1]),_unb64(parts[2])
    key=serialization.load_pem_public_key(public_pem)
    try:key.verify(sig,raw,ec.ECDSA(hashes.SHA256()))
    except InvalidSignature as exc:raise ValueError("Invalid license signature") from exc
    data=json.loads(raw)
    payload=LicensePayload(**data)
    if payload.installation_id.upper()!=expected_installation.upper():
        raise ValueError("License belongs to another installation")
    if payload.expires_at:
        end=datetime.fromisoformat(payload.expires_at)
        if end.tzinfo is None: raise ValueError("License expiry must include timezone")
        if end<=datetime.now(timezone.utc): raise ValueError("License expired")
    return payload
