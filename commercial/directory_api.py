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

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field

from .admin_store import directory_admin_connection
from .branding_assets import MAX_PNG_BYTES, logo_response, store_png
from .directory_access import (directory_role, visible_directory_meetings,
    visible_hierarchy_letters, directory_meeting_access, directory_action_report,
    directory_meeting_status_report)
from .processmaker_directory import PMSyncUnavailable, fetch_users, safe_preview
from .keycloak_admin import KeycloakUnavailable, password_update_email
from .security import Principal
from .modules import require_module
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

    @protected.get("/secretary/preparation/{meeting_id}")
    def prepare_hierarchy_meeting(meeting_id: int, principal: auth):
        """Module 2 read-only manager/subtree agenda, no ProcessMaker writes."""
        if meeting_id<=0:raise HTTPException(status_code=422,detail="Invalid meeting ID")
        try:
            with scoped_connection(principal) as con:
                authorization_snapshot(con,principal)
                require_module(con,principal,2)
                meeting=directory_meeting_access(con,principal,meeting_id)
                if meeting is None:
                    raise HTTPException(status_code=404,detail="Meeting not found")
                cur=con.cursor()
                cur.execute("""
                  SELECT TOP (20) ActionNo,ActionTitle,OwnerUnit,DueAtUtc,
                                  ProgressPercent,IsClosed
                  FROM AgentProduct.ActionIndex
                  WHERE TenantID=? AND MeetingID=?
                  ORDER BY DueAtUtc,ActionNo
                """,str(principal.tenant_id),meeting_id)
                actions=[{"action_no":str(r[0]),"title":str(r[1]),
                          "owner_unit":str(r[2]),"due_at_utc":str(r[3]),
                          "progress_percent":int(r[4]),"is_closed":bool(r[5])}
                         for r in cur.fetchall()]
                agenda=(["مرور اقدامات باز و مصوبات جلسه"]+
                        [f"پیگیری {a['action_no']}: {a['title']}" for a in actions
                         if not a["is_closed"] and a["progress_percent"]<100][:5]+
                        ["تعیین مسئول، موعد و معیار پذیرش با تأیید دبیر"])
                return {"meeting":meeting,"actions":actions,"draft_agenda":agenda,
                        "processmaker_write_performed":False,
                        "human_approval_required":True,
                        "note":"Read-only test index; not automatically generated minutes or an official resolution."}
        except AccessDenied:
            raise HTTPException(status_code=403,detail="Module or tenant access denied")
        except StoreUnavailable:
            raise HTTPException(status_code=503,detail="Isolated store unavailable")

    @protected.get("/analytics/action-overview")
    def action_overview(principal: auth):
        try:
            with scoped_connection(principal) as con:
                authorization_snapshot(con,principal)
                require_module(con,principal,3)
                meetings=directory_meeting_status_report(con,principal)
                actions=directory_action_report(con,principal)
                return {**meetings,"actions":actions["actions"],
                        "data_scope":"authorized synthetic tenant/directory indexes"}
        except AccessDenied:
            raise HTTPException(status_code=403,detail="Module or hierarchy access denied")
        except StoreUnavailable:
            raise HTTPException(status_code=503,detail="Isolated store unavailable")

    @protected.get("/monitoring/overdue")
    def overdue_hierarchy(principal: auth):
        try:
            with scoped_connection(principal) as con:
                authorization_snapshot(con,principal)
                require_module(con,principal,4)
                result=directory_action_report(con,principal,overdue_only=True)
                result["note"]="On-demand test alert list only; no notification dispatched."
                return result
        except AccessDenied:
            raise HTTPException(status_code=403,detail="Module or hierarchy access denied")
        except StoreUnavailable:
            raise HTTPException(status_code=503,detail="Isolated store unavailable")

    @protected.get("/letters/page")
    def letter_page(
        principal: auth,
        cursor: str | None = Query(default=None,min_length=1,max_length=100),
        limit: int = Query(default=20,ge=1,le=50),
    ):
        """Metadata only: restricted ordinary subordinate letters and explicit
        confidential grants, NEVER raw content or automatic GodAdmin bypass.
        """
        try:
            with scoped_connection(principal) as con:
                authorization_snapshot(con,principal)
                values=visible_hierarchy_letters(
                    con,principal,before_id=cursor,limit=limit
                )
                return {"tenant_id":str(principal.tenant_id),**values}
        except AccessDenied:
            raise HTTPException(status_code=403,detail="Tenant or letter access denied")
        except StoreUnavailable:
            raise HTTPException(status_code=503,detail="Letter index unavailable")

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

    @protected.post("/admin/directory/{pm_uid}/send-password-update")
    def request_password_update(pm_uid: str, principal: auth):
        """Trigger Keycloak's own password-update EMAIL, never set a password.

        Requires verified external SysAdmin + current SQL SysAdmin, and an
        ACTIVE, UUID-linked ordinary user in the SAME tenant. A PM username or
        email alone cannot identify an account eligible for a reset.
        """
        _sysadmin(principal)
        target = _uuid32(pm_uid)
        try:
            with scoped_connection(principal) as con:
                authorization_snapshot(con, principal)
                cur = con.cursor()
                cur.execute("""
                    SELECT TOP (1) d.SubjectID
                    FROM AgentProduct.DirectoryUser d
                    JOIN AgentProduct.Membership m
                      ON m.TenantID=d.TenantID AND m.SubjectID=d.SubjectID
                    WHERE d.TenantID=? AND d.PMUserUID=?
                      AND d.IsEnabled=1 AND d.PMStatus='ACTIVE'
                      AND d.OrgRole IN('Expert','Manager')
                      AND m.IsEnabled=1 AND m.RoleCode IN('Analyst','Viewer')
                """, str(principal.tenant_id), target)
                row = cur.fetchone()
            if row is None:
                raise HTTPException(status_code=404, detail="Eligible linked user not found")
            password_update_email(str(row[0]))
            return {"status": "sent_to_identity_provider",
                    "password_or_reset_token_returned": False,
                    "note": "Keycloak sends the action email; no password or link is returned by this API."}
        except (AccessDenied,):
            raise HTTPException(status_code=403, detail="Tenant access denied")
        except (StoreUnavailable, KeycloakUnavailable):
            raise HTTPException(status_code=503, detail="Secure account action unavailable")

    @protected.get("/admin/directory/users")
    def directory_users(principal: auth):
        _sysadmin(principal)
        try:
            with scoped_connection(principal) as con:
                authorization_snapshot(con,principal)
                cur=con.cursor()
                cur.execute("""
                    SELECT TOP (500) PMUserUID,PMUserName,DisplayName,
                      PMStatus,SubjectID,ManagerPMUserUID,OrgRole,IsEnabled
                    FROM AgentProduct.DirectoryUser
                    WHERE TenantID=? ORDER BY DisplayName,PMUserUID
                """,str(principal.tenant_id))
                rows=cur.fetchall()
            return {"tenant_id":str(principal.tenant_id),
                    "users":[{
                      "pm_uid":str(r[0]),"username":str(r[1]),
                      "display_name":str(r[2]),"pm_status":str(r[3]),
                      "linked_subject":str(r[4]) if r[4] else None,
                      "manager_pm_uid":str(r[5]) if r[5] else None,
                      "org_role":str(r[6]),"enabled":bool(r[7])
                    } for r in rows],"returned":len(rows),"max_returned":500,
                    "source":"ProcessMaker whitelist-only; reporting lines and roles assigned manually"}
        except (AccessDenied,StoreUnavailable):
            raise HTTPException(status_code=503,detail="Isolated directory store unavailable")

    @protected.get("/admin/system/connections")
    def configured_connections(principal: auth):
        _sysadmin(principal)
        return {
            "commercial_sql": {
                "configured":bool(os.getenv("COMMERCIAL_SQL_SERVER")
                                  and os.getenv("COMMERCIAL_SQL_USER")),
                "database":"EnterpriseProcess2_AI_Test",
                "login_name":os.getenv("COMMERCIAL_SQL_USER","") or None,
                "credentials_exposed":False,
                "editable_in_browser":False,
            },
            "processmaker": {
                "configured":bool(os.getenv("COMMERCIAL_PM_BASE_URL")
                     and os.getenv("COMMERCIAL_PM_WORKSPACE")
                     and os.getenv("COMMERCIAL_PM_BEARER_TOKEN")),
                "workspace":os.getenv("COMMERCIAL_PM_WORKSPACE","") or None,
                "sync_enabled":os.getenv("COMMERCIAL_PM_SYNC_ENABLED")=="1",
                "bearer_exposed":False,
                "editable_in_browser":False,
            },
            "notice":"Secrets/SQL hosts are operator-managed until encrypted vault-based configuration is reviewed.",
        }

    @protected.get("/branding")
    def branding(principal: auth):
        try:
            with scoped_connection(principal) as con:
                authorization_snapshot(con,principal)
                cur=con.cursor()
                cur.execute("""
                  SELECT TOP (1) CompanyDisplayName,PrimaryColor,LogoAssetPath
                  FROM AgentProduct.TenantBranding WHERE TenantID=?
                """,str(principal.tenant_id))
                row=cur.fetchone()
                if row is None:
                    raise HTTPException(status_code=503,detail="Tenant branding is not configured")
                return {"company_name":str(row[0]),"primary_color":str(row[1]),
                        "logo_available":bool(row[2]),
                        "tenant_id":str(principal.tenant_id)}
        except (AccessDenied,StoreUnavailable):
            raise HTTPException(status_code=403,detail="Tenant branding unavailable")

    class BrandingChange(BaseModel):
        model_config=ConfigDict(extra="forbid")
        company_name:str=Field(min_length=2,max_length=200)
        primary_color:str=Field(pattern=r"^#[0-9A-Fa-f]{6}$")

    @protected.put("/admin/branding")
    def set_branding(body:BrandingChange,principal:auth):
        _sysadmin(principal)
        try:
            with directory_admin_connection(principal) as con:
                cur=con.cursor()
                cur.execute("""
                  EXEC AgentProduct.SetTenantBranding
                    @TenantID=?,@ActorSubjectID=?,@CompanyDisplayName=?,@PrimaryColor=?
                """,str(principal.tenant_id),principal.subject,
                    body.company_name.strip(),body.primary_color.upper())
                row=cur.fetchone()
            return {"company_name":str(row[0]),"primary_color":str(row[1]),
                    "tenant_id":str(principal.tenant_id),
                    "logo_available":False,"notice":"Company name/theme updated; image upload is separate."}
        except StoreUnavailable:
            raise HTTPException(status_code=503,detail="Tenant admin writer not configured")
        except Exception:
            raise HTTPException(status_code=409,detail="Branding update refused")

    @protected.get("/branding/logo")
    def read_tenant_logo(principal: auth):
        """Authenticated, private tenant asset. No public third-party hosting."""
        try:
            with scoped_connection(principal) as con:
                authorization_snapshot(con,principal)
                cur=con.cursor()
                cur.execute("""
                    SELECT TOP (1) LogoAssetPath FROM AgentProduct.TenantBranding
                    WHERE TenantID=?
                """,str(principal.tenant_id))
                row=cur.fetchone()
                if row is None or not row[0]:
                    raise HTTPException(status_code=404,detail="Tenant logo not configured")
                return logo_response(str(row[0]))
        except AccessDenied:
            raise HTTPException(status_code=403,detail="Tenant logo access denied")
        except StoreUnavailable:
            raise HTTPException(status_code=503,detail="Tenant store unavailable")

    @protected.put("/admin/branding/logo")
    async def upload_tenant_logo(request: Request,principal: auth):
        """Raw image/png, <=256KiB, DB-audited, loopback lab only."""
        _sysadmin(principal)
        if request.headers.get("content-type","").split(";")[0].strip().lower()!="image/png":
            raise HTTPException(status_code=415,detail="Only PNG logo uploads are accepted")
        if request.headers.get("content-length"):
            try:
                if int(request.headers["content-length"])>MAX_PNG_BYTES:
                    raise HTTPException(status_code=413,detail="Logo too large")
            except ValueError:
                raise HTTPException(status_code=422,detail="Invalid upload length")
        chunks=[]
        total=0
        async for piece in request.stream():
            total+=len(piece)
            if total>MAX_PNG_BYTES:
                raise HTTPException(status_code=413,detail="Logo too large")
            chunks.append(piece)
        name,file=store_png(b"".join(chunks))
        try:
            with directory_admin_connection(principal) as con:
                cur=con.cursor()
                cur.execute("""
                  EXEC AgentProduct.SetTenantLogo
                    @TenantID=?,@ActorSubjectID=?,@LogoFileName=?
                """,str(principal.tenant_id),principal.subject,name)
                row=cur.fetchone()
            return {"logo_available":True,"tenant_id":str(principal.tenant_id),
                    "logo_url":"/v2/branding/logo",
                    "note":"Private authenticated tenant PNG stored and audited"}
        except Exception:
            file.unlink(missing_ok=True)
            raise HTTPException(status_code=409,detail="Tenant logo update refused")

    return protected
