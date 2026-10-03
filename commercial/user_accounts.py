"""Tenant-scoped AVAN user administration.

Authentication is owned by the managed Keycloak realm. AVAN stores only
authorization, sessions and BPMS bindings; it never stores user passwords.
"""

from contextlib import contextmanager
from pathlib import Path
from uuid import UUID
import os

import httpx
from fastapi import Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from . import setup_console as setup
from .identity_operator import IdentityError, ManagedIdentityService


# Backward-compatible names used by tests and older internal imports.
AccountError = IdentityError
Directory = ManagedIdentityService


def revoke_sessions(subject):
    from .production_app import sessions, _session_lock

    with _session_lock:
        for sid, row in list(sessions.items()):
            if row.get("subject") == subject:
                sessions.pop(sid, None)


def remove_access(tenant, subject):
    # One AVAN SQL transaction removes grants and all BPMS links. No BPMS writes.
    from . import agent_storage, native_access, user_bpms_bindings as bindings

    with agent_storage.transaction() as tx:
        data = tx.get("organization_access", dict(native_access.EMPTY), lock=True)
        if data.get("tenant_id") == tenant:
            data["users"] = [
                u for u in data.get("users", []) if u.get("subject") != subject
            ]
            for user in data["users"]:
                if user.get("manager_subject") == subject:
                    user["manager_subject"] = None
            tx.put("organization_access", data)

        state = bindings._state(tx, lock=True)
        state["bindings"] = [
            b
            for b in state["bindings"]
            if not (
                b.get("tenant_id") == tenant
                and b.get("avan_subject") == subject
            )
        ]
        tx.put(bindings.STORE_KEY, state)
        tx.audit(tenant, "GodAdmin", "USER_ACCESS_REMOVED", {"subject": subject})


@contextmanager
def directory():
    """Yield the one managed identity service used by every user operation."""

    config = setup.get_setting("oidc") or {}
    company = setup.get_setting("company") or {}
    try:
        if not config.get("managed_by_product"):
            raise IdentityError("سرویس کاربران داخلی AVAN تنظیم نشده است.")
        if not company.get("tenant_id"):
            raise IdentityError("ابتدا سازمان AVAN را ثبت کنید.")

        secret = Path(
            os.getenv(
                "AVAN_PROVISIONER_CLIENT_SECRET_PATH",
                "/run/secrets/avan_provisioner_client_secret",
            )
        ).read_text().strip()

        with httpx.Client(
            timeout=15, follow_redirects=False, trust_env=False
        ) as client:
            yield ManagedIdentityService(
                client, config["issuer"], secret, company["tenant_id"]
            )
    except (IdentityError, ValueError) as exc:
        raise HTTPException(409, str(exc)) from exc
    except (httpx.HTTPError, OSError, KeyError) as exc:
        raise HTTPException(
            503, "سرویس مدیریت کاربران در دسترس نیست."
        ) from exc


class Profile(BaseModel):
    model_config = ConfigDict(extra="forbid")
    subject: UUID
    username: str = Field(
        min_length=3, max_length=80, pattern=r"^[A-Za-z0-9_.@-]+$"
    )
    name: str = Field(min_length=2, max_length=240)
    email: str = Field(
        max_length=240, pattern=r"^[^\s@]+@[^\s@]+\.[^\s@]+$"
    )


class Password(BaseModel):
    model_config = ConfigDict(extra="forbid")
    subject: UUID
    password: str = Field(min_length=16, max_length=128)


class Delete(BaseModel):
    model_config = ConfigDict(extra="forbid")
    subject: UUID


def register(router, ready):
    @router.get("/api/users/identities")
    def identities(session=Depends(ready)):
        with directory() as service:
            return service.users()

    @router.post("/api/users/profile")
    def profile(body: Profile, session=Depends(ready)):
        if not body.name.strip():
            raise HTTPException(422, "نام کاربر خالی است.")
        with directory() as service:
            service.update(
                str(body.subject), body.username, body.name, body.email
            )
        setup.audit("USER_PROFILE_UPDATED")
        return {"updated": True}

    @router.post("/api/users/password")
    def password(body: Password, session=Depends(ready)):
        subject = str(body.subject)
        with directory() as service:
            service.password(
                subject,
                body.password,
                lambda: revoke_sessions(subject),
            )
        setup.audit("USER_PASSWORD_RESET")
        return {
            "updated": True,
            "temporary": False,
            "login_ready": True,
        }

    @router.post("/api/users/delete")
    def delete(body: Delete, session=Depends(ready)):
        subject = str(body.subject)
        bound = setup.godadmin_identity() or {}
        if subject in (bound.get("subject"), session[1].get("subject")):
            raise HTTPException(
                409, "حذف حساب اصلی یا حساب جاری مجاز نیست."
            )

        with directory() as service:
            # Validate tenant/service-account boundaries before local mutation.
            # A missing identity still allows safe retry after interrupted deletion.
            def detach():
                remove_access(service.tenant, subject)
                revoke_sessions(subject)

            service.delete(subject, detach)
            with setup._db() as con:
                exists = con.execute(
                    "SELECT 1 FROM sqlite_master "
                    "WHERE type='table' AND name='pending_identity'"
                ).fetchone()
                if exists:
                    con.execute(
                        "DELETE FROM pending_identity "
                        "WHERE tenant_id=? AND subject=?",
                        (service.tenant, subject),
                    )

        setup.audit("USER_DELETED")
        return {"deleted": True, "subject": subject}
