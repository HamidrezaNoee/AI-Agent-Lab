"""JWT validation for the commercial gateway. No user-supplied tenant header is trusted.

The issuer signs access tokens. Tenant membership and role are separately checked
against the tenant-scoped SQL database on every protected request.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
import os
import re
import uuid
from urllib.parse import urlsplit

import jwt
from jwt import PyJWKClient


class AuthenticationFailed(Exception):
    pass


class ConfigurationFailed(Exception):
    pass


@dataclass(frozen=True)
class Principal:
    tenant_id: uuid.UUID
    subject: str


def _https_url(value: str, name: str) -> str:
    parsed = urlsplit(value or "")
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.fragment:
        raise ConfigurationFailed(f"{name} must be a configured HTTPS URL without credentials/fragment")
    return value.rstrip("/")


class VerifiedTokenAuthenticator:
    """Only construct using server-controlled configuration, never request parameters."""

    def __init__(self, issuer: str, audience: str, jwks_url: str, key_resolver=None):
        self.issuer = _https_url(issuer, "issuer")
        self.audience = audience.strip()
        self.jwks_url = _https_url(jwks_url, "JWKS")
        if not self.audience or len(self.audience) > 250:
            raise ConfigurationFailed("Missing or invalid token audience")
        # Resolver injection exists for OFFLINE tests only. Production uses trusted JWKS URL.
        self._resolve = key_resolver or PyJWKClient(
            self.jwks_url, cache_jwk_set=True, lifespan=300, timeout=4
        ).get_signing_key_from_jwt

    @classmethod
    def from_environment(cls):
        return cls(
            os.getenv("COMMERCIAL_OIDC_ISSUER", ""),
            os.getenv("COMMERCIAL_OIDC_AUDIENCE", ""),
            os.getenv("COMMERCIAL_OIDC_JWKS_URL", ""),
        )

    def authenticate(self, authorization: str | None) -> Principal:
        if not authorization or not re.fullmatch(r"Bearer [A-Za-z0-9._~+/-]{1,8192}={0,2}", authorization):
            raise AuthenticationFailed("Missing or malformed bearer token")
        token = authorization[7:]
        try:
            key = self._resolve(token)
            public_key = key.key if hasattr(key, "key") else key
            claims = jwt.decode(
                token, public_key, algorithms=["RS256"],
                issuer=self.issuer, audience=self.audience,
                options={"require": ["exp", "iat", "iss", "aud", "sub", "tenant_id"]},
                leeway=30,
            )
            subject = claims.get("sub")
            raw_tenant = claims.get("tenant_id")
            issued_at = claims.get("iat")
            expires_at = claims.get("exp")
            if not isinstance(subject, str) or not subject.strip() or len(subject) > 180:
                raise ValueError("Invalid subject")
            if not isinstance(raw_tenant, str) or not isinstance(issued_at, int) or not isinstance(expires_at, int):
                raise ValueError("Invalid tenant or token lifetime")
            if expires_at <= issued_at or expires_at - issued_at > 3600:
                raise ValueError("Access token lifetime must be at most 60 minutes")
            if issued_at > int(datetime.now(timezone.utc).timestamp()) + 30:
                raise ValueError("Token issued in the future")
            tenant_id = uuid.UUID(raw_tenant)
            if tenant_id.int == 0:
                raise ValueError("Empty tenant is not allowed")
        except Exception as exc:
            raise AuthenticationFailed("Invalid or expired access token") from exc
        return Principal(tenant_id=tenant_id, subject=subject)
