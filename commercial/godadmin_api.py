"""Verified GodAdmin control-plane endpoints, isolated TEST only.

Requires BOTH a trusted, signed Keycloak GodAdmin realm role AND an explicitly
registered, enabled PlatformOperator subject in SQL. GodAdmin has platform
metadata/tenant/license rights, NOT a wildcard grant to meetings or letters.
This router is inert until the dedicated platform SQL login and public signing
key are independently provisioned. Never publish on an internet-facing host.
"""
from datetime import datetime, timezone
import os
from pathlib import Path
import re
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from .licensing.codec import LicenseInvalid, verify_license
from .platform_store import platform_connection
from .security import Principal
from .sql_store import StoreUnavailable

def make_router(principal_dependency):
    auth=Annotated[Principal,Depends(principal_dependency)]
    router=APIRouter(prefix="/v2/godadmin")

    def godadmin(principal: Principal):
        if "GodAdmin" not in principal.roles:
            raise HTTPException(status_code=403,detail="Verified GodAdmin role required")
        try:
            with platform_connection() as con:
                cur=con.cursor()
                cur.execute("EXEC AgentProduct.IsPlatformOperator @SubjectID=?",principal.subject)
                row=cur.fetchone()
                if row is None or not bool(row[0]):
                    raise HTTPException(status_code=403,detail="GodAdmin is not a registered platform operator")
        except StoreUnavailable:
            raise HTTPException(status_code=503,detail="GodAdmin control plane not configured")

    @router.get("/status")
    def status(principal:auth):
        godadmin(principal)
        return {"platform_operator":True,"subject":principal.subject,
                "scope":"platform-metadata-and-signed-licensing-only",
                "customer_meetings_access":False,
                "configuration_mode":"isolated-lab"}

    @router.get("/tenants")
    def tenants(principal:auth):
        godadmin(principal)
        try:
            with platform_connection() as con:
                cur=con.cursor()
                cur.execute("EXEC AgentProduct.GetPlatformTenants @SubjectID=?",principal.subject)
                rows=cur.fetchall()
            return {"tenants":[{"tenant_id":str(r[0]),"company_name":str(r[1]),
                                "enabled":bool(r[2]),
                                "license_id":str(r[3]) if r[3] else None,
                                "updated_at_utc":str(r[4])} for r in rows],
                    "note":"Metadata only; no meeting or letter content returned"}
        except StoreUnavailable:
            raise HTTPException(status_code=503,detail="GodAdmin platform SQL unavailable")

    class NewTenant(BaseModel):
        model_config=ConfigDict(extra="forbid")
        company_name:str=Field(min_length=2,max_length=200)

    @router.post("/tenants")
    def create_tenant(body:NewTenant,principal:auth):
        godadmin(principal)
        tenant_id=uuid.uuid4()
        try:
            with platform_connection(tenant_id) as con:
                cur=con.cursor()
                cur.execute("""
                  EXEC AgentProduct.CreatePlatformTenant
                   @SubjectID=?,@TenantID=?,@TenantName=?
                """,principal.subject,str(tenant_id),body.company_name.strip())
                row=cur.fetchone()
            return {"tenant_id":str(row[0]),"company_name":body.company_name.strip(),
                    "enabled":False,"licensed":False,
                    "note":"Created disabled. No users, roles or content automatically imported."}
        except StoreUnavailable:
            raise HTTPException(status_code=503,detail="GodAdmin platform SQL unavailable")
        except Exception:
            raise HTTPException(status_code=409,detail="Tenant creation denied")

    class LicenseActivation(BaseModel):
        model_config=ConfigDict(extra="forbid")
        token:str=Field(min_length=100,max_length=16000)

    @router.post("/tenants/{tenant_id}/license")
    def activate_license(tenant_id:uuid.UUID,body:LicenseActivation,principal:auth):
        godadmin(principal)
        public_path=os.getenv("COMMERCIAL_LICENSE_PUBLIC_KEY_PATH","")
        installation=os.getenv("COMMERCIAL_INSTALLATION_ID","")
        if (not public_path or not Path(public_path).is_file()
            or not re.fullmatch(r"[0-9a-fA-F]{64}",installation)):
            raise HTTPException(status_code=503,detail="Pinned license public key or installation ID missing")
        try:
            public=Path(public_path).read_bytes()
            if len(public)>10000:
                raise ValueError("Oversized key")
            with platform_connection(tenant_id) as con:
                cur=con.cursor()
                cur.execute("EXEC AgentProduct.GetTenantLicenseSeatCount @SubjectID=?,@TenantID=?",
                            principal.subject,str(tenant_id))
                row=cur.fetchone()
                seats=int(row[0])
                payload=verify_license(body.token,public,tenant_id=str(tenant_id),
                         installation_id=installation,active_users=seats)
                mask=sum(1<<(code-1) for code in payload["modules"])
                issued=datetime.fromisoformat(payload["issued_at"].replace("Z","+00:00"))
                expiry=(datetime.fromisoformat(payload["expires_at"].replace("Z","+00:00"))
                        if payload["expires_at"] else None)
                cur.execute("""
                 EXEC AgentProduct.ActivateSignedLicense
                   @SubjectID=?,@TenantID=?,@LicenseID=?,@InstallationID=?,
                   @LicenseToken=?,@MaxActiveUsers=?,@ModulesMask=?,
                   @IssuedAtUtc=?,@ExpiresAtUtc=?
                """,principal.subject,str(tenant_id),payload["license_id"],
                    installation.upper(),body.token,payload["max_users"],mask,
                    issued.astimezone(timezone.utc).replace(tzinfo=None),
                    expiry.astimezone(timezone.utc).replace(tzinfo=None) if expiry else None)
                row=cur.fetchone()
            return {"tenant_id":str(row[0]),"license_id":str(row[1]),
                    "modules":payload["modules"],"max_users":payload["max_users"],
                    "expires_at":payload["expires_at"],
                    "note":"Signature and binding checked; activation audited in isolated lab."}
        except LicenseInvalid:
            raise HTTPException(status_code=403,detail="Invalid, expired or incorrectly bound license")
        except (StoreUnavailable,OSError,ValueError):
            raise HTTPException(status_code=503,detail="License validation or platform store unavailable")
        except Exception:
            raise HTTPException(status_code=409,detail="Signed license activation refused")
    return router
