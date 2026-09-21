"""Offline-signature-gated commercial entitlement for operational AVAN.

Issuer's PRIVATE key never enters this process or Docker. Only a trusted
public ECDSA P-256 key verifies a tenant+installation+seat+module-bound token.
A tenant with no installed valid license cannot read meeting content.
"""
from pathlib import Path
import os
import re

from .licensing.codec import LicenseInvalid, verify_license


class ProductionLicenseDenied(Exception):
    pass


def signed_entitlement(con, *, tenant_id: str, company_name: str) -> dict:
    from .setup_console import PUBLIC, get_setting
    install=get_setting("installation") or {}
    installation=install.get("installation_id","")
    public=PUBLIC
    if not re.fullmatch(r"[0-9a-fA-F]{64}",installation):
        raise ProductionLicenseDenied("Installation fingerprint not configured")
    if not public.is_file() or public.stat().st_size>10000:
        raise ProductionLicenseDenied("Pinned publisher public key unavailable")
    cur=con.cursor()
    # An activated license is stored in the encrypted independent AVAN
    # control-plane. Existing centrally DBA-installed license remains a
    # read-only fallback. No DB writes or service account privilege escalation.
    local=get_setting("license") or {}
    token=(local.get("token") if local.get("tenant_id")==tenant_id else None)
    if not token:
        cur.execute("SELECT LicenseToken FROM AVAN.License WHERE TenantID=?",tenant_id)
        row=cur.fetchone()
        token=str(row[0]) if row and row[0] else None
    if not token:
        raise ProductionLicenseDenied("No signed tenant license")
    cur.execute("""
        SELECT COUNT_BIG(*) FROM AVAN.UserAccess
        WHERE TenantID=? AND IsEnabled=1 AND PMIsActive=1
    """,tenant_id)
    used=int(cur.fetchone()[0])
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
    }
