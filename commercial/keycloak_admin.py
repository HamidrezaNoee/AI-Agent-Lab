"""Fail-closed Keycloak password self-service action sender (isolated LAB only).

The tenant SysAdmin may request a Keycloak-generated UPDATE_PASSWORD email for
an existing VERIFIED directory-linked ordinary user. No plaintext password,
password hash, reset token or new role ever traverses this application.
Requires a narrowly scoped, short-lived operator-supplied Keycloak Admin token.
The service account must not possess realm-admin powers beyond authorized
user action email delivery in an isolated nonproduction realm.
"""
import json
import os
import re
import ssl
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit
from urllib.request import (
    Request, build_opener, HTTPSHandler, ProxyHandler, HTTPRedirectHandler
)
from uuid import UUID


class KeycloakUnavailable(Exception):
    pass


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, new_url):
        raise KeycloakUnavailable("Identity provider redirect refused")


def password_update_email(subject: str, *, opener=None) -> None:
    if (os.getenv("COMMERCIAL_KEYCLOAK_ADMIN_ENABLED") != "1"
        or os.getenv("COMMERCIAL_MODE") != "lab"
        or os.getenv("COMMERCIAL_SQL_DATABASE") != "EnterpriseProcess2_AI_Test"):
        raise KeycloakUnavailable("Keycloak account management disabled")
    try:
        keycloak_id = str(UUID(subject))
    except (TypeError, ValueError, AttributeError) as exc:
        raise KeycloakUnavailable("Target has no verified Keycloak UUID link") from exc

    admin_url = os.getenv("COMMERCIAL_KEYCLOAK_ADMIN_REALM_URL", "").rstrip("/")
    issuer_url = os.getenv("COMMERCIAL_OIDC_ISSUER", "").rstrip("/")
    bearer = os.getenv("COMMERCIAL_KEYCLOAK_ADMIN_TOKEN", "")
    admin, issuer = urlsplit(admin_url), urlsplit(issuer_url)
    # Explicit same-origin/same-realm binding blocks SSRF, realm crossover and
    # redirect-based token disclosure. Both URLs must be operator-configured.
    if (admin.scheme != "https" or issuer.scheme != "https"
        or admin.netloc != issuer.netloc
        or not re.fullmatch(r"/realms/[A-Za-z0-9_-]+", issuer.path)
        or admin.path != "/admin" + issuer.path
        or any((admin.username, admin.password, issuer.username,
                issuer.password, admin.query, issuer.query,
                admin.fragment, issuer.fragment))
        or not 8 <= len(bearer) <= 8192
        or any(x in bearer for x in "\r\n")):
        raise KeycloakUnavailable("Trusted Keycloak Admin realm/token not configured")

    url = admin_url + "/users/" + quote(keycloak_id, safe="") + "/execute-actions-email"
    request = Request(url, data=json.dumps(["UPDATE_PASSWORD"]).encode("utf-8"),
                      method="PUT", headers={
                          "Authorization": "Bearer " + bearer,
                          "Content-Type": "application/json",
                          "Accept": "application/json",
                      })
    client = opener if opener is not None else build_opener(
        ProxyHandler({}), _NoRedirect(),
        HTTPSHandler(context=ssl.create_default_context()))
    try:
        with client.open(request, timeout=8) as response:
            if response.status not in (200, 204):
                raise KeycloakUnavailable("Identity provider denied password update email")
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        # Never leak the service bearer, signed link, raw provider body or user
        # email via HTTP error details or the organization's audit log.
        raise KeycloakUnavailable("Identity provider password email unavailable") from exc
