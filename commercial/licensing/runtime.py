"""Signed license check for an authenticated tenant in the ISOLATED lab.

Pure ECDSA verifier lives in licensing.codec. This read-only integration ensures
a real license is bound to the tenant + installation fingerprint and seat count.
The old fictional 12/17 fixture lacks signed tokens: it remains lab-only and
must NEVER be used to claim a sellable, activated subscription.
"""
import os
import re
from pathlib import Path
from .licensing.codec import LicenseInvalid, verify_license
from .security import Principal
from .sql_store import AccessDenied, StoreUnavailable


def verify_current_tenant_license(con, principal: Principal) -> dict:
    installation = os.getenv("COMMERCIAL_INSTALLATION_ID", "")
    public_path = os.getenv("COMMERCIAL_LICENSE_PUBLIC_KEY_PATH", "")
    if not re.fullmatch(r"[0-9A-Fa-f]{64}", installation):
        raise StoreUnavailable("Stable installation fingerprint is not configured")
    if not public_path or not Path(public_path).is_file():
        raise StoreUnavailable("Verified LIMAK public license key is not configured")
    try:
        public_key = Path(public_path).read_bytes()
        if len(public_key)>10000:
            raise StoreUnavailable("Unexpected oversized license public key")
        cur=con.cursor()
        cur.execute("""
            SELECT LicenseToken,LicenseID,MaxActiveUsers,ModulesMask
            FROM AgentProduct.TenantLicense WHERE TenantID=?
        """,str(principal.tenant_id))
        row=cur.fetchone()
        if row is None:
            raise AccessDenied("Tenant has no signed license")
        cur.execute("""
            SELECT COUNT_BIG(*) FROM AgentProduct.Membership
            WHERE TenantID=? AND IsEnabled=1
        """,str(principal.tenant_id))
        active=int(cur.fetchone()[0])
        payload=verify_license(str(row[0]),public_key,
             tenant_id=str(principal.tenant_id),
             installation_id=installation,active_users=active)
        mask=sum(1<<(code-1) for code in payload["modules"])
        if (str(row[1]).lower()!=str(payload["license_id"]).lower()
            or int(row[2])!=payload["max_users"]
            or int(row[3])!=mask):
            raise AccessDenied("Stored licensed modules or seat cap do not match signature")
        return {"license_id":payload["license_id"],
                "tenant_id":payload["tenant_id"],
                "max_users":payload["max_users"],
                "active_users":active,
                "modules":payload["modules"],
                "expires_at":payload["expires_at"]}
    except LicenseInvalid as exc:
        raise AccessDenied("Commercial license invalid or expired") from exc
    except (ValueError, TypeError, KeyError) as exc:
        raise AccessDenied("Malformed tenant commercial license record") from exc


def require_signed_licensing_if_enabled(con, principal: Principal) -> None:
    # The existing repository ONLY supports isolated lab mode and explicitly
    # distinguishes its fictional subscription flags from signed licenses.
    # When an operator opts into commercial licensing, invalid/missing fails closed.
    if os.getenv("COMMERCIAL_REQUIRE_SIGNED_LICENSE")=="1":
        verify_current_tenant_license(con,principal)
