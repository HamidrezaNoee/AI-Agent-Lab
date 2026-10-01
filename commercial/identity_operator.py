"""Host operator creates a NEW AVAN identity. BPMS bindings are separate."""

import argparse
import getpass
import os
from pathlib import Path
import re
from urllib.parse import urlsplit
from uuid import UUID
import httpx
from . import setup_console as setup


def create(client, issuer, secret, tenant, username, email, name, role, password):
    if not re.fullmatch(r"[A-Za-z0-9_.@-]{3,80}", username) or role not in (
        "Expert",
        "Manager",
        "SysAdmin",
        "GodAdmin",
    ):
        raise ValueError("Invalid account name or role")
    tenant = str(UUID(tenant))
    if len(password) < 12:
        raise ValueError("Temporary password needs at least 12 characters")
    parts = urlsplit(issuer)
    if (
        parts.path != "/realms/avan"
        or parts.query
        or parts.fragment
        or parts.username
        or parts.password
    ):
        raise ValueError("Expected the configured AVAN identity realm")
    if parts.scheme != "https" and not (
        parts.scheme == "http"
        and parts.hostname in ("localhost", "127.0.0.1", "auth.localhost")
        and parts.port == 8181
    ):
        raise ValueError("HTTPS is required outside the local bundled realm")

    def checked(method, url, **kwargs):
        r = client.request(method, url, **kwargs)
        if not 200 <= r.status_code < 300:
            raise ValueError(
                "Identity operation failed: HTTP "
                + str(r.status_code)
                + ". No automatic write retry."
            )
        return r

    token = checked(
        "POST",
        issuer + "/protocol/openid-connect/token",
        data={
            "grant_type": "client_credentials",
            "client_id": "avan-provisioner",
            "client_secret": secret,
        },
    ).json()["access_token"]
    base = parts.scheme + "://" + parts.netloc + "/admin/realms/avan"
    headers = {"Authorization": "Bearer " + token}
    users = checked(
        "GET",
        base + "/users",
        params={"username": username, "exact": "true"},
        headers=headers,
    ).json()
    if users:
        raise ValueError(
            "Account already exists; refusing to alter its password, role or identity"
        )
    # The installation owner is authorized by AVAN's exact-subject binding,
    # never by a realm-wide role that could be assigned outside the product.
    selected = (checked("GET", base + "/roles/" + role, headers=headers).json()
                if role != "GodAdmin" else None)
    first, _, last = name.strip().partition(" ")
    payload = {
        "username": username,
        "email": email,
        "emailVerified": True,
        "enabled": False,
        "firstName": first,
        "lastName": last,
        "attributes": {"tenant_id": [tenant]},
        "requiredActions": ["UPDATE_PASSWORD", "CONFIGURE_TOTP"],
        "credentials": [{"type": "password", "value": password, "temporary": True}],
    }
    created = checked("POST", base + "/users", json=payload, headers=headers)
    location = created.headers.get("Location", "")
    subject = str(UUID(location.rstrip("/").split("/")[-1]))
    # Read back managed tenant attributes before permitting login.
    user = checked("GET", base + "/users/" + subject, headers=headers).json()
    if (
        user.get("attributes", {}).get("tenant_id") != [tenant]
        or user.get("email", "").casefold() != email.casefold()
    ):
        raise ValueError(
            "Identity remains DISABLED: configure admin-only tenant_id in the realm user profile before recovery"
        )
    if selected is not None:
        checked(
            "POST",
            base + "/users/" + subject + "/role-mappings/realm",
            json=[selected],
            headers=headers,
        )
    checked("PUT", base + "/users/" + subject, json={"enabled": True}, headers=headers)
    return subject


def main():
    parser = argparse.ArgumentParser(
        description="Create a new AVAN identity; BPMS user binding is configured separately"
    )
    parser.add_argument("--username", required=True)
    parser.add_argument("--email", required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument(
        "--role", choices=["Expert", "Manager", "SysAdmin"], default="Expert"
    )
    args = parser.parse_args()
    company = setup.get_setting("company") or {}
    tenant = company.get("tenant_id")
    if not tenant:
        raise ValueError("Configure the AVAN organization first")
    config = setup.get_setting("oidc") or {}
    if not config.get("managed_by_product"):
        raise ValueError("Bundled identity configuration required")
    secret = (
        Path(
            os.getenv(
                "AVAN_PROVISIONER_CLIENT_SECRET_PATH",
                "/run/secrets/avan_provisioner_client_secret",
            )
        )
        .read_text()
        .strip()
    )
    password = getpass.getpass("Temporary password (not printed/stored by AVAN): ")
    if password != getpass.getpass("Repeat temporary password: "):
        raise ValueError("Passwords differ")
    with httpx.Client(timeout=15, follow_redirects=False, trust_env=False) as client:
        subject = create(
            client,
            config["issuer"],
            secret,
            tenant,
            args.username,
            args.email.strip(),
            args.name.strip(),
            args.role,
            password,
        )
    print(
        "AVAN identity created: "
        + subject
        + ". User must change password, enroll MFA and sign in. "
          "GodAdmin then approves the AVAN account and configures BPMS bindings separately."
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        raise SystemExit(
            str(exc)
            if isinstance(exc, ValueError)
            else "Identity creation stopped. Inspect the realm for a disabled or pending account before retrying."
        )
