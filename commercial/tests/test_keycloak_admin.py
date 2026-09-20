"""Offline Keycloak account-action tests: no HTTP, SQL, email or real credentials."""
import os
from uuid import UUID
import unittest
from unittest.mock import patch

from commercial.keycloak_admin import KeycloakUnavailable, password_update_email

TARGET = "22222222-2222-4222-8222-222222222222"
BASE = {
    "COMMERCIAL_MODE": "lab",
    "COMMERCIAL_SQL_DATABASE": "EnterpriseProcess2_AI_Test",
    "COMMERCIAL_KEYCLOAK_ADMIN_ENABLED": "1",
    "COMMERCIAL_OIDC_ISSUER": "https://idp.example.test/realms/meeting",
    "COMMERCIAL_KEYCLOAK_ADMIN_REALM_URL":
        "https://idp.example.test/admin/realms/meeting",
    "COMMERCIAL_KEYCLOAK_ADMIN_TOKEN": "synthetic-private-value",
}


class Response:
    status = 204
    def __enter__(self): return self
    def __exit__(self, *args): return False


class Opener:
    def __init__(self):
        self.requests = []
    def open(self, request, timeout):
        self.requests.append((request, timeout))
        return Response()


class KeycloakPasswordActionTests(unittest.TestCase):
    def test_default_disabled_never_calls_network(self):
        with patch.dict(os.environ,
                        {**BASE, "COMMERCIAL_KEYCLOAK_ADMIN_ENABLED": "0"}):
            with self.assertRaises(KeycloakUnavailable):
                password_update_email(TARGET, opener=Opener())

    def test_no_test_database_no_admin_action(self):
        with patch.dict(os.environ,
                        {**BASE, "COMMERCIAL_SQL_DATABASE": "EnterpriseProcess"}):
            with self.assertRaises(KeycloakUnavailable):
                password_update_email(TARGET, opener=Opener())

    def test_non_uuid_identity_cannot_be_reset(self):
        with patch.dict(os.environ, BASE):
            with self.assertRaises(KeycloakUnavailable):
                password_update_email("lab-alice", opener=Opener())

    def test_realm_or_origin_mismatch_refused(self):
        for url in (
            "https://evil.example/admin/realms/meeting",
            "https://idp.example.test/admin/realms/another",
            "http://idp.example.test/admin/realms/meeting",
            "https://idp.example.test/admin/realms/meeting?token=bad",
        ):
            with self.subTest(url=url), patch.dict(os.environ, {
                **BASE,"COMMERCIAL_KEYCLOAK_ADMIN_REALM_URL":url
            }):
                with self.assertRaises(KeycloakUnavailable):
                    password_update_email(TARGET, opener=Opener())

    def test_valid_admin_action_emails_without_password(self):
        sender=Opener()
        with patch.dict(os.environ,BASE):
            result=password_update_email(TARGET,opener=sender)
        self.assertIsNone(result)
        self.assertEqual(len(sender.requests),1)
        req,timeout=sender.requests[0]
        self.assertEqual(req.get_method(),"PUT")
        self.assertTrue(req.full_url.endswith(
            "/users/"+TARGET+"/execute-actions-email"))
        self.assertEqual(req.data,b'["UPDATE_PASSWORD"]')
        self.assertNotIn(b'"password":', req.data.lower())  # Only required-action name; no password value.
        self.assertEqual(timeout,8)
        self.assertEqual(req.get_header("Authorization"),
                         "Bearer synthetic-private-value")


if __name__ == "__main__":
    unittest.main()
