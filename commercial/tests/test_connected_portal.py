"""Offline connected portal contract: no fake auth, no SQL, no actual OIDC call."""
import os
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from commercial.api import app


class ConnectedPortalTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.lab = {
            "COMMERCIAL_WEB_PORTAL_ENABLED": "1",
            "COMMERCIAL_MODE": "lab",
            "COMMERCIAL_SQL_DATABASE": "EnterpriseProcess2_AI_Test",
        }
        self.idp = {
            "COMMERCIAL_OIDC_ISSUER": "https://idp.example.test/tenant/",
            "COMMERCIAL_OIDC_AUDIENCE": "meeting-commercial-api",
            "COMMERCIAL_OIDC_JWKS_URL": "https://idp.example.test/tenant/jwks",
            "COMMERCIAL_OIDC_AUTHORIZATION_URL": "https://idp.example.test/authorize",
            "COMMERCIAL_OIDC_TOKEN_URL": "https://idp.example.test/oauth/token",
            "COMMERCIAL_OIDC_CLIENT_ID": "test-public-spa-client",
            "COMMERCIAL_OIDC_SCOPES": "openid profile",
        }

    def tearDown(self):
        self.client.close()

    def test_connected_portal_disabled_by_default(self):
        with patch.dict(os.environ, {"COMMERCIAL_WEB_PORTAL_ENABLED": "0"}):
            self.assertEqual(self.client.get("/portal/").status_code, 404)
            self.assertEqual(self.client.get("/portal/config").status_code, 404)

    def test_cannot_open_portal_against_operational_database(self):
        with patch.dict(os.environ, {**self.lab,
                                     "COMMERCIAL_SQL_DATABASE": "EnterpriseProcess2"}):
            self.assertEqual(self.client.get("/portal/").status_code, 404)

    def test_missing_idp_fails_closed_but_shell_can_explain(self):
        with patch.dict(os.environ, self.lab), patch.dict(
            os.environ, {
                "COMMERCIAL_OIDC_ISSUER": "",
                "COMMERCIAL_OIDC_AUDIENCE": "",
                "COMMERCIAL_OIDC_JWKS_URL": "",
                "COMMERCIAL_OIDC_AUTHORIZATION_URL": "",
                "COMMERCIAL_OIDC_TOKEN_URL": "",
                "COMMERCIAL_OIDC_CLIENT_ID": "",
            }
        ):
            self.assertEqual(self.client.get("/portal/").status_code, 200)
            config = self.client.get("/portal/config")
            self.assertEqual(config.status_code, 503)
            self.assertFalse(config.json()["ready"])
            self.assertNotIn("client_id", config.text)

    def test_config_requires_real_https_and_does_not_return_secrets(self):
        with patch.dict(os.environ, {**self.lab, **self.idp}):
            response = self.client.get("/portal/config")
            self.assertEqual(response.status_code, 200)
            value = response.json()
            self.assertIs(value["ready"], True)
            self.assertEqual(value["audience"], "meeting-commercial-api")
            self.assertEqual(value["client_id"], "test-public-spa-client")
            self.assertNotIn("private_key", value)
            self.assertNotIn("password", value)
            self.assertNotIn("secret", value)
            self.assertNotIn("token_origin", value)
            page = self.client.get("/portal/")
            self.assertEqual(page.status_code, 200)
            self.assertIn("https://idp.example.test", page.headers["content-security-policy"])
            self.assertIn("no-store", page.headers["cache-control"])
            self.assertIn("frame-ancestors 'none'", page.headers["content-security-policy"])
            self.assertEqual(self.client.get("/portal/portal.js").status_code, 200)
            self.assertIn("code_challenge_method", self.client.get("/portal/portal.js").text)

    def test_insecure_token_endpoint_disables_real_login(self):
        with patch.dict(os.environ, {**self.lab, **self.idp,
                                     "COMMERCIAL_OIDC_TOKEN_URL": "http://idp.example.test/token"}):
            self.assertEqual(self.client.get("/portal/config").status_code, 503)

    def test_connected_ui_does_not_bypass_protected_meeting_api(self):
        with patch.dict(os.environ, {**self.lab, **self.idp}):
            self.assertIn(self.client.get("/v1/meetings/page").status_code, (401, 410, 503))
            self.assertIn(self.client.get("/v1/modules").status_code, (401, 503))


if __name__ == "__main__":
    unittest.main()
