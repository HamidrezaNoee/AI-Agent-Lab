"""Managed AVAN identity administration backed by the product Keycloak realm.

Authentication stays in Keycloak. AVAN never stores end-user passwords.
BPMS identities and permissions remain separate from AVAN identities.
"""

from __future__ import annotations

import argparse
import getpass
import os
from pathlib import Path
import re
from urllib.parse import urlsplit
from uuid import UUID

import httpx

from . import setup_console as setup


_USERNAME = re.compile(r"^[A-Za-z0-9_.@-]{3,80}$")
_EMAIL = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
_ROLES = {"Expert", "Manager", "SysAdmin", "GodAdmin"}


class IdentityError(ValueError):
    pass


def _realm_parts(issuer: str):
    issuer = str(issuer or "").rstrip("/")
    parts = urlsplit(issuer)
    if (
        parts.path != "/realms/avan"
        or parts.username
        or parts.password
        or parts.query
        or parts.fragment
    ):
        raise IdentityError("تنظیمات Realm هویت AVAN معتبر نیست.")
    local = (
        parts.scheme == "http"
        and parts.hostname in ("localhost", "127.0.0.1", "auth.localhost")
        and parts.port == 8181
    )
    if parts.scheme != "https" and not local:
        raise IdentityError("سرویس هویت خارج از محیط محلی باید HTTPS باشد.")
    return issuer, parts


class ManagedIdentityService:
    """Tenant-scoped Keycloak administrator used by every AVAN user operation."""

    def __init__(self, client: httpx.Client, issuer: str, secret: str, tenant: str):
        self.client = client
        self.tenant = str(UUID(str(tenant)))
        self.issuer, parts = _realm_parts(issuer)
        if not isinstance(secret, str) or len(secret.strip()) < 16:
            raise IdentityError("کلید داخلی مدیریت کاربران معتبر نیست.")
        self.base = parts.scheme + "://" + parts.netloc + "/admin/realms/avan"

        response = client.post(
            self.issuer + "/protocol/openid-connect/token",
            data={
                "grant_type": "client_credentials",
                "client_id": "avan-provisioner",
                "client_secret": secret.strip(),
            },
        )
        if response.status_code != 200:
            raise IdentityError(
                "مجوز مدیریت کاربران دریافت نشد (HTTP "
                + str(response.status_code)
                + ")."
            )
        try:
            token = response.json()["access_token"]
        except (ValueError, KeyError, TypeError) as exc:
            raise IdentityError("پاسخ سرویس هویت برای مدیریت کاربران معتبر نیست.") from exc
        self.headers = {"Authorization": "Bearer " + token}

    def call(self, method: str, path: str, **kwargs):
        response = self.client.request(
            method, self.base + path, headers=self.headers, **kwargs
        )
        if not 200 <= response.status_code < 300:
            raise IdentityError(
                "عملیات هویت انجام نشد (HTTP "
                + str(response.status_code)
                + ")."
            )
        return response

    def allowed(self, user: dict) -> bool:
        return (
            not user.get("serviceAccountClientId")
            and user.get("attributes", {}).get("tenant_id") == [self.tenant]
        )

    def get(self, subject: str, *, missing_ok: bool = False):
        subject = str(UUID(str(subject)))
        response = self.client.request(
            "GET", self.base + "/users/" + subject, headers=self.headers
        )
        if missing_ok and response.status_code == 404:
            return None
        if response.status_code != 200:
            raise IdentityError(
                "دریافت کاربر انجام نشد (HTTP "
                + str(response.status_code)
                + ")."
            )
        try:
            user = response.json()
        except ValueError as exc:
            raise IdentityError("پاسخ سرویس هویت برای کاربر معتبر نیست.") from exc
        if not self.allowed(user):
            raise IdentityError("این حساب متعلق به سازمان انتخاب‌شده نیست.")
        return user

    def users(self) -> dict:
        result = []
        for offset in range(0, 10000, 100):
            rows = self.call(
                "GET", "/users", params={"first": offset, "max": 100}
            ).json()
            if not isinstance(rows, list):
                raise IdentityError("فهرست کاربران سرویس هویت معتبر نیست.")
            for user in rows:
                if not self.allowed(user):
                    continue
                result.append(
                    {
                        "subject": user["id"],
                        "username": user.get("username", ""),
                        "name": (
                            " ".join(
                                [user.get("firstName", ""), user.get("lastName", "")]
                            )
                        ).strip(),
                        "email": user.get("email", ""),
                        "identity_enabled": bool(user.get("enabled")),
                    }
                )
            if len(rows) < 100:
                return {"users": result, "truncated": False}
        return {"users": result, "truncated": True}

    def create(
        self,
        username: str,
        email: str,
        name: str,
        role: str,
        password: str,
    ) -> str:
        username = str(username or "").strip()
        email = str(email or "").strip()
        name = str(name or "").strip()
        if not _USERNAME.fullmatch(username) or role not in _ROLES:
            raise IdentityError("نام کاربری یا نقش AVAN معتبر نیست.")
        if not _EMAIL.fullmatch(email):
            raise IdentityError("ایمیل کاربر معتبر نیست.")
        if not 2 <= len(name) <= 240:
            raise IdentityError("نام و نام خانوادگی کاربر معتبر نیست.")
        if not isinstance(password, str) or not 16 <= len(password) <= 128:
            raise IdentityError("رمز ورود باید بین ۱۶ تا ۱۲۸ نویسه باشد.")

        existing = self.call(
            "GET",
            "/users",
            params={"username": username, "exact": "true"},
        ).json()
        if existing:
            raise IdentityError(
                "این نام کاربری از قبل وجود دارد؛ رمز یا هویت حساب موجود به‌صورت خودکار تغییر نمی‌کند."
            )

        selected_role = (
            self.call("GET", "/roles/" + role).json() if role != "GodAdmin" else None
        )
        first, _, last = name.partition(" ")
        payload = {
            "username": username,
            "email": email,
            "emailVerified": True,
            # Keep the account disabled until tenant data and role assignment are
            # read back successfully.
            "enabled": False,
            "firstName": first,
            "lastName": last,
            "attributes": {"tenant_id": [self.tenant]},
            # AVAN policy: password entered by GodAdmin is immediately usable.
            # MFA remains optional and is asked only when an OTP credential exists.
            "requiredActions": [],
            "credentials": [
                {"type": "password", "value": password, "temporary": False}
            ],
        }
        created = self.call("POST", "/users", json=payload)
        location = created.headers.get("Location", "")
        try:
            subject = str(UUID(location.rstrip("/").split("/")[-1]))
        except (ValueError, IndexError) as exc:
            raise IdentityError("شناسه حساب ساخته‌شده از سرویس هویت دریافت نشد.") from exc

        user = self.call("GET", "/users/" + subject).json()
        if (
            user.get("attributes", {}).get("tenant_id") != [self.tenant]
            or str(user.get("username", "")).casefold() != username.casefold()
            or str(user.get("email", "")).casefold() != email.casefold()
        ):
            raise IdentityError(
                "حساب برای ایمنی غیرفعال ماند؛ tenant_id یا مشخصات هویت به‌درستی ثبت نشده است."
            )

        if selected_role is not None:
            self.call(
                "POST",
                "/users/" + subject + "/role-mappings/realm",
                json=[selected_role],
            )
        self.call("PUT", "/users/" + subject, json={"enabled": True})
        return subject

    def update(self, subject: str, username: str, name: str, email: str):
        username = str(username or "").strip()
        name = str(name or "").strip()
        email = str(email or "").strip()
        if not _USERNAME.fullmatch(username):
            raise IdentityError("نام کاربری معتبر نیست.")
        if not 2 <= len(name) <= 240:
            raise IdentityError("نام کاربر معتبر نیست.")
        if not _EMAIL.fullmatch(email):
            raise IdentityError("ایمیل کاربر معتبر نیست.")

        user = self.get(subject)
        first, _, last = name.partition(" ")
        payload = {
            "username": username,
            "firstName": first,
            "lastName": last,
            "email": email,
        }
        if email.casefold() != str(user.get("email", "")).casefold():
            payload["emailVerified"] = False
        self.call("PUT", "/users/" + str(UUID(str(subject))), json=payload)

    def password(self, subject: str, password: str, after_reset=None):
        if not isinstance(password, str) or not 16 <= len(password) <= 128:
            raise IdentityError("رمز ورود باید بین ۱۶ تا ۱۲۸ نویسه باشد.")
        subject = str(UUID(str(subject)))
        user = self.get(subject)
        self.call(
            "PUT",
            "/users/" + subject + "/reset-password",
            json={"type": "password", "value": password, "temporary": False},
        )

        # Repair accounts created by older AVAN builds. Those builds forced both
        # UPDATE_PASSWORD and CONFIGURE_TOTP even when the administrator wanted
        # a directly usable password and optional MFA. Existing OTP credentials
        # are NOT deleted; Keycloak's conditional OTP flow will still ask for
        # the second factor when an OTP credential actually exists.
        required = list(user.get("requiredActions") or [])
        cleaned = [
            action
            for action in required
            if action not in {"UPDATE_PASSWORD", "CONFIGURE_TOTP"}
        ]
        if cleaned != required:
            self.call(
                "PUT",
                "/users/" + subject,
                json={"requiredActions": cleaned, "enabled": True},
            )

        if after_reset:
            after_reset()
        # Resetting a password revokes Keycloak and AVAN sessions, but does not
        # remove an existing OTP credential.
        self.call("POST", "/users/" + subject + "/logout")

    def delete(self, subject: str, before_delete=None):
        subject = str(UUID(str(subject)))
        self.get(subject, missing_ok=True)
        if before_delete:
            before_delete()
        response = self.client.request(
            "DELETE", self.base + "/users/" + subject, headers=self.headers
        )
        if response.status_code not in (204, 404):
            raise IdentityError(
                "حذف هویت انجام نشد؛ دسترسی AVAN قطع شده است. دوباره حذف را انجام دهید (HTTP "
                + str(response.status_code)
                + ")."
            )


def create(client, issuer, secret, tenant, username, email, name, role, password):
    """Compatibility wrapper used by CLI/tests and older deployment scripts."""
    return ManagedIdentityService(client, issuer, secret, tenant).create(
        username, email, name, role, password
    )


def main():
    parser = argparse.ArgumentParser(
        description="Create an AVAN-native identity; BPMS bindings are configured separately"
    )
    parser.add_argument("--username", required=True)
    parser.add_argument("--email", required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument(
        "--role", choices=["Expert", "Manager", "SysAdmin"], default="Expert"
    )
    args = parser.parse_args()

    company = setup.get_setting("company") or {}
    config = setup.get_setting("oidc") or {}
    tenant = company.get("tenant_id")
    if not tenant:
        raise IdentityError("ابتدا سازمان AVAN را ثبت کنید.")
    if not config.get("managed_by_product"):
        raise IdentityError("سرویس هویت داخلی AVAN فعال نیست.")

    secret = Path(
        os.getenv(
            "AVAN_PROVISIONER_CLIENT_SECRET_PATH",
            "/run/secrets/avan_provisioner_client_secret",
        )
    ).read_text().strip()
    password = getpass.getpass("Login password (not printed/stored by AVAN): ")
    if password != getpass.getpass("Repeat login password: "):
        raise IdentityError("تکرار رمز عبور یکسان نیست.")

    with httpx.Client(timeout=15, follow_redirects=False, trust_env=False) as client:
        subject = create(
            client,
            config["issuer"],
            secret,
            tenant,
            args.username,
            args.email,
            args.name,
            args.role,
            password,
        )
    print(
        "AVAN identity created: "
        + subject
        + ". The configured password is ready for login. MFA is optional and BPMS bindings are separate."
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        raise SystemExit(
            str(exc)
            if isinstance(exc, (IdentityError, ValueError))
            else "Identity creation stopped. Inspect the AVAN identity service before retrying."
        )
