"""Hierarchy and ProcessMaker management endpoints (ISOLATED LAB ONLY).

All content routes require REAL verified OIDC -> ACTIVE SQL membership -> linked,
active ProcessMaker directory identity. A signed Keycloak SysAdmin role alone is
NOT enough; privileged actions also require active DB SysAdmin and a separate
least-privilege SQL writer procedure. No browser/client can select tenant id.
"""
from dataclasses import asdict
import json
import os
import re

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field

from .admin_store import directory_admin_connection
from .directory_access import directory_role, visible_directory_meetings
from .processmaker_directory import PMSyncUnavailable, fetch_users, safe_preview
from .security import Principal
from .sql_store import AccessDenied, StoreUnavailable, authorization_snapshot, scoped_connection

router = APIRouter(prefix="/v2")


def _principal():
    # Injected at router construction below to avoid test-auth shortcuts.
    raise RuntimeError("Protected principal dependency not wired")


def _active_member(principal: Principal):
    try:
        with scoped_connection(principal) as con:
            member = authorization_snapshot(con, principal)
            role = directory_role(con, principal)
            return member, role
    except AccessDenied:
        raise HTTPException(status_code=403, detail="Linked active tenant membership required")
    except StoreUnavailable:
        raise HTTPException(status_code=503, detail="Isolated commercial store not configured")


def _sysadmin(principal: Principal):
    if "SysAdmin" not in principal.roles:
        raise HTTPException(status_code=403, detail="Signed SysAdmin role required")
    member, role = _active_member(principal)
    if member["role"] not in ("Admin", "Owner") or role != "SysAdmin":
        raise HTTPException(status_code=403, detail="Tenant SysAdmin permission denied")


def _uuid32(value: str) -> str:
    if not re.fullmatch(r"[0-9a-fA-F]{32}", value):
        raise HTTPException(status_code=422, detail="Invalid ProcessMaker user UID")
    return value.lower()


def make_router(principal_dependency):
    """Construct routes with the SAME commercial.api._authenticated_principal."""
    from fastapi import Depends
    from typing import Annotated
    auth = Annotated[Principal, Depends(principal_dependency)]
    protected = APIRouter(prefix="/v2")

    @protected.get("/me/directory")
    def whoami(principal: auth):
        member, role = _active_member(principal)
        return {"tenant_id": str(principal.tenant_id), "subject": principal.subject,
                "org_role": role, "membership_role": member["role"],
                "scope": "self-and-org-subtree" if role=="Expert" else "tenant"}

    @protected.get("/meetings/page")
    def meetings_page(
        principal: auth,
        cursor: int | None = Query(None,gt=0),
        limit: int = Query(20,ge=1,le=50),
    ):
        try:
            with scoped_connection(principal) as con:
                authorization_snapshot(con,principal)
                page = visible_directory_meetings(con,principal,before_id=cursor,limit=limit)
                return {"tenant_id":str(principal.tenant_id),**page,
                        "data_scope":"isolated-tenant-directory-index-only"}
        except AccessDenied:
            raise HTTPException(status_code=403,detail="Tenant or directory access denied")
        except StoreUnavailable:
            raise HTTPException(status_code=503,detail="Commercial lab store unavailable")

    @protected.get("/admin/processmaker/users/preview")
    def preview_pm(principal: auth):
        _sysadmin(principal)
        try:
            snapshot=fetch_users()
        except PMSyncUnavailable:
            raise HTTPException(status_code=503,detail="Read-only ProcessMaker user list unavailable")
        return {"tenant_id":str(principal.tenant_id),**safe_preview(snapshot)}

    class SyncRequest(BaseModel):
        model_config = ConfigDict(extra="forbid")
        deactivate_missing: bool = False

    @protected.post("/admin/processmaker/users/sync")
    def sync_pm(body: SyncRequest,principal: auth):
        _sysadmin(principal)
        try:
            users = fetch_users()
            if not users:  # Do not turn an empty or wrong workspace into deletions.
                raise PMSyncUnavailable("No users returned")
            payload = json.dumps([asdict(x) for x in users], ensure_ascii=False,
                                 separators=(",", ":"))
            if len(payload.encode("utf-16-le"))>10485760:
                raise PMSyncUnavailable("Snapshot exceeds database safety limit")
            with directory_admin_connection(principal) as con:
                cur=con.cursor()
                cur.execute("""
                    EXEC AgentProduct.SyncProcessMakerUsers
                    @TenantID=?,@ActorSubjectID=?,@UsersJson=?,
                    @ExpectedCount=?,@DeactivateMissing=?
                """,str(principal.tenant_id),principal.subject,payload,
                    len(users),int(body.deactivate_missing))
                row=cur.fetchone()
                return {"seen":int(row[0]),"new_disabled_unbound":int(row[1]),
                        "existing_profiles":int(row[2]),"missing_from_source":int(row[3]),
                        "marked_inactive":int(row[4]),
                        "identities_auto_linked":False,"roles_auto_granted":False,
                        "notice":"Only the complete user-profile snapshot was synced. No passwords or privileges copied."}
        except (PMSyncUnavailable,StoreUnavailable):
            raise HTTPException(status_code=503,detail="Controlled ProcessMaker sync unavailable")
        except Exception:
            # SQL role/tenant/duplicate/check failures MUST NOT disclose secrets or
            # return success. Check only test DBA-side diagnostic logs.
            raise HTTPException(status_code=409,detail="Directory synchronization refused")

    class ManagerChange(BaseModel):
        model_config=ConfigDict(extra="forbid")
        manager_pm_uid: str | None = Field(default=None,min_length=32,max_length=32)

    @protected.put("/admin/directory/{pm_uid}/manager")
    def set_manager(pm_uid:str,body:ManagerChange,principal:auth):
        _sysadmin(principal)
        target=_uuid32(pm_uid)
        manager=_uuid32(body.manager_pm_uid) if body.manager_pm_uid else None
        try:
            with directory_admin_connection(principal) as con:
                cur=con.cursor()
                cur.execute("""
                    EXEC AgentProduct.SetOrgManager
                      @TenantID=?,@ActorSubjectID=?,@PMUserUID=?,@ManagerPMUserUID=?
                """,str(principal.tenant_id),principal.subject,target,manager)
                row=cur.fetchone()
            return {"pm_uid":str(row[0]),"manager_pm_uid":str(row[1]) if row[1] else None,
                    "tenant_id":str(principal.tenant_id)}
        except (StoreUnavailable,):
            raise HTTPException(status_code=503,detail="Directory writer not configured")
        except Exception:
            raise HTTPException(status_code=409,detail="Reporting line change refused")

    class OrgRoleChange(BaseModel):
        model_config=ConfigDict(extra="forbid")
        role: str = Field(pattern="^(Expert|Manager)$")

    @protected.put("/admin/directory/{pm_uid}/role")
    def set_role(pm_uid:str,body:OrgRoleChange,principal:auth):
        _sysadmin(principal)
        target=_uuid32(pm_uid)
        try:
            with directory_admin_connection(principal) as con:
                cur=con.cursor()
                cur.execute("""
                    EXEC AgentProduct.SetOrgRole
                      @TenantID=?,@ActorSubjectID=?,@PMUserUID=?,@OrgRole=?
                """,str(principal.tenant_id),principal.subject,target,body.role)
                row=cur.fetchone()
            return {"pm_uid":str(row[0]),"org_role":str(row[1]),
                    "tenant_id":str(principal.tenant_id)}
        except StoreUnavailable:
            raise HTTPException(status_code=503,detail="Directory writer not configured")
        except Exception:
            raise HTTPException(status_code=409,detail="Organization role change refused")
    return protected
