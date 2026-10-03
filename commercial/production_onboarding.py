"""AVAN account authorization and onboarding.

Identity authentication is handled by Keycloak. This module only creates the
tenant-scoped AVAN authorization record. BPMS identity bindings stay separate.
"""

from __future__ import annotations

import uuid

from . import native_access
from . import setup_console as setup
from .pending_identities import approve as finish_pending
from .pending_identities import find as find_pending


class ProvisioningDenied(Exception):
    pass


def _directory():
    """Legacy read-only ProcessMaker directory helper kept for compatibility."""
    from types import SimpleNamespace
    from .processmaker_store import (
        ProductionUnavailable,
        directory,
        open_production,
    )

    try:
        with open_production() as con:
            users = directory(con)
    except ProductionUnavailable as exc:
        raise ProvisioningDenied(
            "ProcessMaker MySQL directory unavailable"
        ) from exc
    return [
        SimpleNamespace(
            pm_uid=uid,
            display_name=user["name"],
            email=user["email"],
            status="ACTIVE" if user["active"] else "INACTIVE",
        )
        for uid, user in users.items()
    ]


def visible_pm_users() -> list[dict]:
    return [
        {
            "pm_uid": user.pm_uid,
            "name": user.display_name,
            "email": user.email,
            "status": user.status,
        }
        for user in _directory()
        if user.status == "ACTIVE"
    ]


def _tenant(value: str) -> str:
    try:
        return str(uuid.UUID(str(value)))
    except (TypeError, ValueError, AttributeError) as exc:
        raise ProvisioningDenied("Verified tenant UUID required") from exc


def _clean_role(role: str) -> str:
    if role not in ("Expert", "Manager", "SysAdmin"):
        raise ProvisioningDenied("Unapproved AVAN role")
    return role


def _add_access_record(
    *,
    tenant_id: str,
    subject: str,
    company_name: str,
    role: str,
    username: str | None,
    email: str | None,
    name: str | None,
    department_name: str | None = None,
    manager_subject: str | None = None,
    module_permissions: list[int] | None = None,
):
    """Create the AVAN authorization record for a verified identity."""

    tenant_id = _tenant(tenant_id)
    role = _clean_role(role)
    company_name = str(company_name or "").strip()
    subject = str(subject or "").strip()
    if not subject or len(subject) > 180:
        raise ProvisioningDenied("Verified identity subject required")
    if not 2 <= len(company_name) <= 200:
        raise ProvisioningDenied("Unapproved company")

    department = (
        str(department_name).strip() if department_name is not None else None
    )
    if department and len(department) > 160:
        raise ProvisioningDenied("Department name is too long")

    manager_subject = str(manager_subject or "").strip() or None
    if manager_subject == subject:
        raise ProvisioningDenied("User cannot manage themselves")

    username = str(username or "").strip() or None
    email = str(email or "").strip() or None
    display_name = str(name or "").strip() or username or subject

    with native_access.edit() as data:
        if data["tenant_id"] not in (None, tenant_id):
            raise ProvisioningDenied(
                "Workspace already belongs to another company"
            )
        if data["company_name"] not in (None, company_name):
            raise ProvisioningDenied(
                "Company differs from existing tenant"
            )

        users = data["users"]
        existing = next(
            (user for user in users if user.get("subject") == subject),
            None,
        )
        if existing:
            raise ProvisioningDenied("AVAN identity already exists")

        if manager_subject and not any(
            user.get("subject") == manager_subject and user.get("enabled")
            for user in users
        ):
            raise ProvisioningDenied(
                "Direct manager must be an active AVAN user"
            )

        data["tenant_id"] = tenant_id
        data["company_name"] = company_name

        from .production_license import (
            ProductionLicenseDenied,
            capacity,
        )

        try:
            licensed = capacity(
                tenant_id,
                company_name,
                sum(bool(user.get("enabled")) for user in users) + 1,
            )
        except ProductionLicenseDenied as exc:
            raise ProvisioningDenied(str(exc)) from exc

        licensed_modules = {
            int(value) for value in licensed.get("modules", ())
        }
        if module_permissions is None:
            requested = licensed_modules
        else:
            if (
                len(module_permissions) != len(set(module_permissions))
                or any(
                    not isinstance(value, int) or value not in (1, 2, 3, 4)
                    for value in module_permissions
                )
            ):
                raise ProvisioningDenied(
                    "AVAN module permission is invalid"
                )
            requested = set(module_permissions)
            if not requested <= licensed_modules:
                raise ProvisioningDenied(
                    "AVAN module permission is not licensed"
                )

        users.append(
            {
                "subject": subject,
                "username": username,
                "email": email,
                "name": display_name,
                "department_name": department,
                "role": role,
                "manager_subject": manager_subject,
                "module_permissions": sorted(requested),
                "enabled": True,
            }
        )

    return {
        "approved": True,
        "company_name": company_name,
        "subject": subject,
        "username": username,
        "name": display_name,
        "role": role,
        "modules": sorted(requested),
        "tenant_id": tenant_id,
    }


def register_managed_identity(
    *,
    tenant_id: str,
    subject: str,
    company_name: str,
    username: str,
    email: str,
    name: str,
    role: str,
    module_permissions: list[int] | None = None,
):
    """Authorize a user explicitly created by an authenticated AVAN GodAdmin.

    No pending-login round trip is required because the administrator has
    already created the exact Keycloak identity and selected its AVAN role.
    """

    result = _add_access_record(
        tenant_id=tenant_id,
        subject=subject,
        company_name=company_name,
        username=username,
        email=email,
        name=name,
        role=role,
        module_permissions=module_permissions,
    )
    setup.audit("AVAN_MANAGED_USER_CREATED_" + role.upper())
    return result


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
    """Approve a user who arrived through a verified external OIDC login."""

    tenant_id = _tenant(tenant_id)
    role = _clean_role(role)
    user = find_pending(tenant_id, subject)
    if user is None:
        raise ProvisioningDenied(
            "OIDC user has not completed signed organizational login"
        )
    if role == "SysAdmin" and "SysAdmin" not in user["roles"]:
        raise ProvisioningDenied(
            "SysAdmin must ALSO hold the signed IdP role"
        )
    if not user["email_verified"] or not user["email"]:
        raise ProvisioningDenied(
            "IdP email must be verified before AVAN account approval"
        )

    result = _add_access_record(
        tenant_id=tenant_id,
        subject=subject,
        company_name=company_name,
        username=user.get("username"),
        email=user.get("email"),
        name=user.get("name") or user.get("username") or subject,
        role=role,
        department_name=department_name,
        manager_subject=manager_subject,
        module_permissions=module_permissions,
    )
    finish_pending(tenant_id, subject)
    setup.audit("AVAN_USER_APPROVED_" + role.upper())
    return result


def approve_employee(**_kwargs):
    """Removed compatibility path: AVAN approval never creates a BPMS mapping."""
    raise ProvisioningDenied(
        "Legacy ProcessMaker-coupled onboarding is disabled. "
        "Approve the AVAN account first, then create an explicit per-BPMS binding."
    )


def refresh_employee_statuses() -> dict:
    """Compatibility endpoint: refresh all ProcessMaker binding sources."""

    from .user_bpms_bindings import (
        BindingError,
        refresh_source,
        source_catalog,
    )

    sources = [
        source
        for source in source_catalog()
        if source.get("engine") == "processmaker" and source.get("enabled")
    ]
    if not sources:
        raise ProvisioningDenied("No ProcessMaker source is configured")

    active = stale = directory_users = 0
    refreshed = []
    for source in sources:
        try:
            result = refresh_source(source["id"])
        except BindingError as exc:
            raise ProvisioningDenied(str(exc)) from exc
        active += result["active_bindings"]
        stale += result["stale_bindings"]
        directory_users += result["directory_users"]
        refreshed.append(source["id"])

    setup.audit("PM_BINDINGS_RECONCILED")
    return {
        "refreshed_active_users": active,
        "disabled_unverified_users": 0,
        "stale_bindings": stale,
        "directory_users": directory_users,
        "refreshed_sources": refreshed,
        "source": "all_processmaker_binding_directories",
    }
