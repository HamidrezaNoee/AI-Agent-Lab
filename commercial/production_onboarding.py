"""Audited GodAdmin staff onboarding without customer data or workflow writes.

Only a subject obtained from a SIGNATURE-VERIFIED OIDC login can be linked.
Only an ACTIVE ProcessMaker user from the current read-only MySQL directory with
the same verified employee email can be linked. Company and identity approvals stay encrypted in the dedicated AVANAgent database.
"""

from contextlib import contextmanager
import re
import os
from urllib.parse import urlsplit

import httpx

from . import setup_console as setup
from .pending_identities import find as find_pending, approve as finish_pending
from . import native_access


class ProvisioningDenied(Exception):
    pass


def _directory():
    from types import SimpleNamespace
    from .processmaker_store import open_production, directory, ProductionUnavailable

    try:
        with open_production() as con:
            users = directory(con)
    except ProductionUnavailable as exc:
        raise ProvisioningDenied("ProcessMaker MySQL directory unavailable") from exc
    return [
        SimpleNamespace(
            pm_uid=uid,
            display_name=u["name"],
            email=u["email"],
            status="ACTIVE" if u["active"] else "INACTIVE",
        )
        for uid, u in users.items()
    ]


def visible_pm_users() -> list[dict]:
    return [
        {
            "pm_uid": u.pm_uid,
            "name": u.display_name,
            "email": u.email,
            "status": u.status,
        }
        for u in _directory()
        if u.status == "ACTIVE"
    ]


def approve_avan_user(
    *,
    tenant_id: str,
    subject: str,
    company_name: str,
    role: str,
    department_name: str | None = None,
    manager_subject: str | None = None,
    module_permissions: list[int] | None = None,
):
    """Approve an AVAN account without coupling it to any BPMS identity."""
    import uuid

    try:
        tenant_id = str(uuid.UUID(tenant_id))
    except (TypeError, ValueError, AttributeError):
        raise ProvisioningDenied("Verified tenant UUID required")
    if (
        not isinstance(company_name, str)
        or not 2 <= len(company_name.strip()) <= 200
        or role not in ("Expert", "Manager", "SysAdmin")
    ):
        raise ProvisioningDenied("Unapproved company or AVAN role")
    if department_name is not None and len(department_name.strip()) > 160:
        raise ProvisioningDenied("Department name is too long")
    department = department_name.strip() if department_name else None
    user = find_pending(tenant_id, subject)
    if user is None:
        raise ProvisioningDenied("OIDC user has not completed signed organizational login")
    if role == "SysAdmin" and "SysAdmin" not in user["roles"]:
        raise ProvisioningDenied("SysAdmin must ALSO hold the signed IdP role")
    if not user["email_verified"] or not user["email"]:
        raise ProvisioningDenied("IdP email must be verified before AVAN account approval")
    manager_subject=(manager_subject or "").strip() or None
    if manager_subject==subject:
        raise ProvisioningDenied("User cannot manage themselves")

    with native_access.edit() as data:
        if data["tenant_id"] not in (None, tenant_id):
            raise ProvisioningDenied("Workspace already belongs to another company")
        if data["company_name"] not in (None, company_name.strip()):
            raise ProvisioningDenied("Company differs from existing tenant")
        users=data["users"]
        if any(u.get("subject")==subject for u in users):
            raise ProvisioningDenied("AVAN identity already exists")
        if manager_subject and not any(
            u.get("subject")==manager_subject and u.get("enabled") for u in users
        ):
            raise ProvisioningDenied("Direct manager must be an active AVAN user")
        data["tenant_id"]=tenant_id
        data["company_name"]=company_name.strip()
        from .production_license import capacity, ProductionLicenseDenied
        try:
            licensed=capacity(tenant_id,company_name.strip(),
                              sum(bool(u.get("enabled")) for u in users)+1)
        except ProductionLicenseDenied as exc:
            raise ProvisioningDenied(str(exc)) from exc
        licensed_modules={int(x) for x in licensed.get("modules",())}
        requested=(licensed_modules if module_permissions is None
                   else {int(x) for x in module_permissions
                         if isinstance(x,int) and x in (1,2,3,4)})
        if module_permissions is not None and (
            len(requested)!=len(set(module_permissions))
            or any(not isinstance(x,int) or x not in (1,2,3,4)
                    for x in module_permissions)
            or not requested<=licensed_modules
        ):
            raise ProvisioningDenied("AVAN module permission is invalid or not licensed")
        users.append({
            "subject":subject,
            "username":(user.get("username") or "").strip() or None,
            "email":user.get("email"),
            "name":user.get("name") or user.get("username") or subject,
            "department_name":department,
            "role":role,
            "manager_subject":manager_subject,
            "module_permissions":sorted(requested),
            "enabled":True,
        })
    finish_pending(tenant_id,subject)
    setup.audit("AVAN_USER_APPROVED_"+role.upper())
    return {
        "approved":True,
        "company_name":company_name.strip(),
        "subject":subject,
        "username":user.get("username"),
        "name":user.get("name") or user.get("username") or subject,
        "role":role,
        "modules":sorted(requested),
        "tenant_id":tenant_id,
    }


def approve_employee(**_kwargs):
    """Removed compatibility path: AVAN account approval must never create a BPMS mapping."""
    raise ProvisioningDenied(
        "Legacy ProcessMaker-coupled onboarding is disabled. "
        "Approve the AVAN account first, then create an explicit per-BPMS binding."
    )

def refresh_employee_statuses() -> dict:
    """Compatibility endpoint: refresh all configured ProcessMaker binding sources."""
    from .user_bpms_bindings import source_catalog,refresh_source,BindingError
    sources=[s for s in source_catalog()
             if s.get("engine")=="processmaker" and s.get("enabled")]
    if not sources:
        raise ProvisioningDenied("No ProcessMaker source is configured")
    active=stale=directory_users=0
    refreshed=[]
    for source in sources:
        try:
            result=refresh_source(source["id"])
        except BindingError as exc:
            raise ProvisioningDenied(str(exc)) from exc
        active+=result["active_bindings"]
        stale+=result["stale_bindings"]
        directory_users+=result["directory_users"]
        refreshed.append(source["id"])
    setup.audit("PM_BINDINGS_RECONCILED")
    return {
        "refreshed_active_users":active,
        "disabled_unverified_users":0,
        "stale_bindings":stale,
        "directory_users":directory_users,
        "refreshed_sources":refreshed,
        "source":"all_processmaker_binding_directories",
    }
