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
            capacity(tenant_id,company_name.strip(),
                     sum(bool(u.get("enabled")) for u in users)+1)
        except ProductionLicenseDenied as exc:
            raise ProvisioningDenied(str(exc)) from exc
        users.append({
            "subject":subject,
            "username":(user.get("username") or "").strip() or None,
            "email":user.get("email"),
            "name":user.get("name") or user.get("username") or subject,
            "department_name":department,
            "role":role,
            "manager_subject":manager_subject,
            "enabled":True,
            # Legacy compatibility only. BPMS status no longer controls AVAN account status.
            "pm_uid":None,
            "manager_pm_uid":None,
            "pm_active":False,
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
        "tenant_id":tenant_id,
    }


def approve_employee(
    *,
    tenant_id: str,
    subject: str,
    company_name: str,
    pm_uid: str,
    role: str,
    manager_pm_uid: str | None,
    department_name: str | None
):
    import uuid

    try:
        tenant_id = str(uuid.UUID(tenant_id))
    except (TypeError, ValueError, AttributeError):
        raise ProvisioningDenied("Verified tenant UUID required")
    if (
        not isinstance(company_name, str)
        or not 2 <= len(company_name.strip()) <= 200
        or not re.fullmatch(r"[0-9a-fA-F]{32}", pm_uid or "")
        or role not in ("Expert", "Manager", "SysAdmin")
    ):
        raise ProvisioningDenied("Unapproved company, PM user or organizational role")
    if department_name is not None and len(department_name.strip()) > 160:
        raise ProvisioningDenied("Department name is too long")
    department = department_name.strip() if department_name else None
    pm_uid = pm_uid.lower()
    if manager_pm_uid is not None:
        manager_pm_uid = manager_pm_uid.strip().lower() or None
        if manager_pm_uid and not re.fullmatch(r"[0-9a-f]{32}", manager_pm_uid):
            raise ProvisioningDenied("Invalid direct manager PM UID")
        if manager_pm_uid == pm_uid:
            raise ProvisioningDenied("User cannot manage themselves")
    user = find_pending(tenant_id, subject)
    if user is None:
        raise ProvisioningDenied(
            "OIDC user has not completed signed organizational login"
        )
    if role == "SysAdmin" and "SysAdmin" not in user["roles"]:
        raise ProvisioningDenied("SysAdmin must ALSO hold the signed IdP role")
    if not user["email_verified"] or not user["email"]:
        raise ProvisioningDenied("IdP email must be verified before staff mapping")
    directory = {u.pm_uid: u for u in _directory()}
    staff = directory.get(pm_uid)
    if staff is None or staff.status != "ACTIVE":
        raise ProvisioningDenied("Selected PM user is absent or inactive")
    if (
        not staff.email
        or staff.email.strip().casefold() != user["email"].strip().casefold()
    ):
        raise ProvisioningDenied(
            "Verified IdP email does not match the ProcessMaker employee"
        )
    with native_access.edit() as data:
        if data["tenant_id"] not in (None, tenant_id):
            raise ProvisioningDenied("Workspace already belongs to another company")
        if data["company_name"] not in (None, company_name.strip()):
            raise ProvisioningDenied("Company differs from existing tenant")
        users = data["users"]
        if manager_pm_uid and not any(
            u["pm_uid"] == manager_pm_uid and u["enabled"] and u["pm_active"]
            for u in users
        ):
            raise ProvisioningDenied("Direct manager must be approved and active")
        if any(u["subject"] == subject or u["pm_uid"] == pm_uid for u in users):
            raise ProvisioningDenied("OIDC or PM user already linked")
        data["tenant_id"] = tenant_id
        data["company_name"] = company_name.strip()
        from .production_license import capacity, ProductionLicenseDenied
        try:capacity(tenant_id,company_name.strip(),sum(u.get('enabled') and u.get('pm_active') for u in users)+1)
        except ProductionLicenseDenied as exc:raise ProvisioningDenied(str(exc)) from exc
        users.append(
            {
                "subject": subject,
                "pm_uid": pm_uid,
                "name": staff.display_name,
                "department_name": department,
                "role": role,
                "manager_pm_uid": manager_pm_uid,
                "enabled": True,
                "pm_active": True,
            }
        )
    finish_pending(tenant_id, subject)
    setup.audit("VERIFIED_STAFF_MAPPED_" + role.upper())
    return {
        "mapped": True,
        "company_name": company_name.strip(),
        "name": staff.display_name,
        "role": role,
        "tenant_id": tenant_id,
    }


def refresh_employee_statuses() -> dict:
    """Compatibility endpoint: refresh PM bindings, never AVAN account status."""
    from .user_bpms_bindings import (
        active_processmaker_source_id, refresh_source, BindingError
    )
    source_id=active_processmaker_source_id()
    if not source_id:
        raise ProvisioningDenied("No active ProcessMaker source")
    try:
        result=refresh_source(source_id)
    except BindingError as exc:
        raise ProvisioningDenied(str(exc)) from exc
    setup.audit("PM_BINDINGS_RECONCILED")
    return {
        "refreshed_active_users":result["active_bindings"],
        "disabled_unverified_users":0,
        "stale_bindings":result["stale_bindings"],
        "directory_users":result["directory_users"],
        "source":"per_source_bpms_binding_directory",
    }
