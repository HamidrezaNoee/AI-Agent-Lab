"""Offline JWT gateway tests. No live SQL, no API calls, no real credentials."""
import time
import unittest
import uuid

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa

from commercial.security import (
    AuthenticationFailed, ConfigurationFailed, VerifiedTokenAuthenticator,
)

ISSUER = "https://issuer.example.test/org/"
AUDIENCE = "meeting-commercial-api"
JWKS = "https://issuer.example.test/org/keys"


class SecurityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        cls.public_key = cls.private_key.public_key()
        cls.authenticator = VerifiedTokenAuthenticator(
            ISSUER, AUDIENCE, JWKS, key_resolver=lambda _: cls.public_key
        )
        cls.tenant = str(uuid.uuid4())

    def token(self, **changes):
        now = int(time.time())
        claims = {
            "iss": ISSUER, "aud": AUDIENCE, "sub": "test-user-a",
            "tenant_id": self.tenant, "iat": now, "exp": now + 300,
        }
        claims.update(changes)
        return jwt.encode(claims, self.private_key, algorithm="RS256")

    def test_valid_token_returns_verified_tenant_and_subject(self):
        result = self.authenticator.authenticate("Bearer " + self.token())
        self.assertEqual(str(result.tenant_id), self.tenant)
        self.assertEqual(result.subject, "test-user-a")

    def test_no_bearer_fails_closed(self):
        with self.assertRaises(AuthenticationFailed):
            self.authenticator.authenticate(None)

    def test_unsigned_payload_change_fails_signature(self):
        token = self.token()
        header, payload, signature = token.split(".")
        import base64
        import json
        data = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
        data["tenant_id"] = str(uuid.uuid4())
        fake_body = base64.urlsafe_b64encode(
            json.dumps(data, separators=(",", ":")).encode()
        ).decode().rstrip("=")
        tampered = ".".join([header, fake_body, signature])
        with self.assertRaises(AuthenticationFailed):
            self.authenticator.authenticate("Bearer " + tampered)

    def test_expired_token_fails(self):
        now = int(time.time())
        with self.assertRaises(AuthenticationFailed):
            self.authenticator.authenticate(
                "Bearer " + self.token(iat=now-500, exp=now-100)
            )

    def test_wrong_issuer_and_audience_fail(self):
        for changes in ({"iss": "https://attacker.example/"}, {"aud": "other-api"}):
            with self.subTest(changes=changes):
                with self.assertRaises(AuthenticationFailed):
                    self.authenticator.authenticate("Bearer " + self.token(**changes))

    def test_overlong_access_token_lifetime_fails(self):
        now = int(time.time())
        with self.assertRaises(AuthenticationFailed):
            self.authenticator.authenticate(
                "Bearer " + self.token(iat=now, exp=now+7200)
            )

    def test_missing_and_nil_tenant_fail(self):
        for tenant in (None, str(uuid.UUID(int=0)), "not-a-uuid"):
            with self.subTest(tenant=tenant):
                with self.assertRaises(AuthenticationFailed):
                    self.authenticator.authenticate(
                        "Bearer " + self.token(tenant_id=tenant)
                    )

    def test_untrusted_oidc_config_fails(self):
        for issuer, jwks in (("http://issuer.test", JWKS),
                             (ISSUER, "http://localhost/keys")):
            with self.assertRaises(ConfigurationFailed):
                VerifiedTokenAuthenticator(issuer, AUDIENCE, jwks)


if __name__ == "__main__":
    unittest.main()
