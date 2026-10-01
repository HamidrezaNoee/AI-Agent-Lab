"""Offline-signature-gated commercial entitlement for operational AVAN.

Issuer's PRIVATE key never enters this process or Docker. Only a trusted
public ECDSA P-256 key verifies a tenant+installation+seat+module-bound token.
A tenant with no installed valid license cannot read meeting content.
"""
from pathlib import Path
import os
import re
import uuid

from .licensing.codec import LicenseInvalid, verify_license


class ProductionLicenseDenied(Exception):
    pass


def local_evaluation_enabled():
    """Localhost-only evaluation; the normal compose file never enables it."""
    return (os.getenv('AVAN_LOCAL_EVALUATION') == '1'
            and os.getenv('AVAN_PM_ALLOW_LOCAL_HTTP') == '1'
            and os.getenv('AVAN_PUBLIC_ORIGIN') == 'http://127.0.0.1:8188')


def _evaluation_entitlement(tenant_id, company_name, active_users):
    try:
        uuid.UUID(str(tenant_id))
    except (TypeError, ValueError, AttributeError) as exc:
        raise ProductionLicenseDenied('Organization is not configured') from exc
    if not str(company_name or '').strip() or not 0 <= active_users <= 10:
        raise ProductionLicenseDenied('Evaluation user capacity exceeded')
    return {'modules': frozenset((1, 2, 3, 4)), 'max_users': 10,
            'active_users': active_users, 'expires_at': None,
            'license_id': 'LOCAL-EVALUATION', 'mode': 'local_evaluation'}


def entitlement(*, tenant_id: str, company_name: str) -> dict:
    """Verify AVAN entitlement without requiring any BPMS connection."""
    if local_evaluation_enabled():
        from .native_access import seats
        return _evaluation_entitlement(tenant_id, company_name, seats(tenant_id))
    from .setup_console import PUBLIC, get_setting
    install=get_setting("installation") or {}
    installation=install.get("installation_id","")
    public=PUBLIC
    if not re.fullmatch(r"[0-9a-fA-F]{64}",installation):
        raise ProductionLicenseDenied("Installation fingerprint not configured")
    if not public.is_file() or public.stat().st_size>10000:
        raise ProductionLicenseDenied("Pinned publisher public key unavailable")
    from .native_access import seats
    local=get_setting('license') or {}
    token=local.get('token') if local.get('tenant_id')==tenant_id else None
    if not token:raise ProductionLicenseDenied('No signed tenant license')
    used=seats(tenant_id)
    try:
        payload=verify_license(
            token,public.read_bytes(),tenant_id=tenant_id,
            installation_id=installation,active_users=used,
        )
    except LicenseInvalid as exc:
        raise ProductionLicenseDenied("Invalid signed entitlement") from exc
    if payload["customer"].strip()!=company_name.strip():
        raise ProductionLicenseDenied("Signed license customer differs from company")
    return {
        "modules":frozenset(int(x) for x in payload["modules"]),
        "max_users":int(payload["max_users"]),
        "active_users":used,
        "expires_at":payload["expires_at"],
        "license_id":payload["license_id"],
        "mode":"licensed",
    }


def signed_entitlement(con, *, tenant_id: str, company_name: str) -> dict:
    # Backward-compatible call site; entitlement is AVAN-native and BPMS-independent.
    return entitlement(tenant_id=tenant_id,company_name=company_name)



def capacity(tenant_id, company_name, active_users):
    """Verify the next seat count inside the locked organization update."""
    if local_evaluation_enabled():
        return _evaluation_entitlement(tenant_id, company_name, active_users)
    from .setup_console import get_setting, PUBLIC
    local=get_setting('license') or {}
    installation=(get_setting('installation') or {}).get('installation_id','')
    if local.get('tenant_id')!=tenant_id or not PUBLIC.is_file():
        raise ProductionLicenseDenied('Activate a signed license before enabling users')
    try:
        payload=verify_license(local.get('token',''),PUBLIC.read_bytes(),tenant_id=tenant_id,
            installation_id=installation,active_users=active_users)
        if payload['customer'].strip()!=company_name.strip():raise LicenseInvalid('Company mismatch')
        return payload
    except LicenseInvalid as exc:
        raise ProductionLicenseDenied('License expired or licensed seat count exceeded') from exc
