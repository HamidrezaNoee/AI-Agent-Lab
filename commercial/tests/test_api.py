"""Offline gateway route tests. No SQL, JWT provider or OpenAI network requests."""
import unittest
import uuid
from contextlib import contextmanager
from unittest.mock import patch

from fastapi.testclient import TestClient

from commercial.api import app, _authenticated_principal
from commercial.security import ConfigurationFailed, Principal
from commercial.sql_store import AccessDenied


class CommercialApiTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.principal = Principal(uuid.uuid4(), "offline-test-subject")

    def tearDown(self):
        app.dependency_overrides.clear()
        self.client.close()

    def test_health_does_not_reveal_tenant_data(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("tenant_id", response.text)

    def test_protected_endpoint_never_returns_data_without_valid_auth_configuration(self):
        # Server has no OIDC settings in offline test. Fail closed, not 200.
        with patch("commercial.api._verifier", side_effect=ConfigurationFailed("test misconfig")):
            response = self.client.get("/v1/meetings")
            self.assertEqual(response.status_code, 503)

    def test_authenticated_but_unsubscribed_user_is_denied(self):
        app.dependency_overrides[_authenticated_principal] = lambda: self.principal

        @contextmanager
        def fake_connection(principal):
            yield object()

        with (
            patch("commercial.api.scoped_connection", fake_connection),
            patch("commercial.api.authorization_snapshot", side_effect=AccessDenied()),
        ):
            response = self.client.get("/v1/me")
        self.assertEqual(response.status_code, 403)
        self.assertNotIn("test-user", response.text)

    def test_query_is_scoped_to_verified_principal(self):
        app.dependency_overrides[_authenticated_principal] = lambda: self.principal

        @contextmanager
        def fake_connection(principal):
            self.assertIs(principal, self.principal)
            yield object()

        def fake_visible(con, principal):
            self.assertIs(principal, self.principal)
            return [{"meeting_id": 1, "meeting_no": "ONLY-TENANT-A",
                     "title": "Synthetic", "status": "Draft"}]

        snapshot = {"role": "Viewer", "plan": "Trial", "expires_at_utc": "2099-01-01",
                    "monthly_request_limit": 100, "quota_enforced": False}
        with (
            patch("commercial.api.scoped_connection", fake_connection),
            patch("commercial.api.authorization_snapshot", return_value=snapshot),
            patch("commercial.api.visible_meetings", fake_visible),
        ):
            response = self.client.get("/v1/meetings")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["tenant_id"], str(self.principal.tenant_id))
        self.assertEqual(payload["returned"], 1)
        self.assertEqual(payload["meetings"][0]["meeting_no"], "ONLY-TENANT-A")


if __name__ == "__main__":
    unittest.main()
