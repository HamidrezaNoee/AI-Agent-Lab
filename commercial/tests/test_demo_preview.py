"""Offline HTTP preview checks; no SQL, token, model, payment or network calls."""
import unittest
from fastapi.testclient import TestClient
from commercial.demo_preview import app
from commercial.api import app as secured_api


class DemoPreviewTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()

    def test_preview_shell_is_rtl_and_explicitly_fictional(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn('lang="fa" dir="rtl"', response.text)
        self.assertIn("پیش‌نمایش", response.text)
        self.assertIn("no-store", response.headers["cache-control"])
        self.assertIn("default-src 'none'", response.headers["content-security-policy"])
        self.assertIn("DENY", response.headers["x-frame-options"])

    def test_demo_dataset_has_100_cases_300_actions_and_no_real_data(self):
        response = self.client.get("/demo-data")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIs(data["synthetic"], True)
        self.assertEqual(data["count"], 100)
        self.assertEqual(len(data["scenarios"]), 100)
        self.assertEqual(sum(len(c["actions"]) for c in data["scenarios"]), 300)
        self.assertTrue(all("ساختگی" in c["organization"]
                            for c in data["scenarios"]))

    def test_synthetic_preview_does_not_expose_real_api(self):
        self.assertEqual(self.client.get("/v1/meetings").status_code, 404)
        self.assertEqual(self.client.get("/v1/modules").status_code, 404)
        self.assertEqual(self.client.get("/v1/me").status_code, 404)
        self.assertEqual(self.client.get("/health").json()["real_login"], False)

    def test_static_files_exist_and_no_external_libs_or_auth_shortcut(self):
        style = self.client.get("/preview.css")
        script = self.client.get("/preview.js")
        self.assertEqual(style.status_code, 200)
        self.assertEqual(script.status_code, 200)
        self.assertIn(".module-grid", style.text)
        self.assertIn("function monitoring", script.text)
        self.assertNotIn("dependency_overrides", script.text)
        self.assertNotIn("COMMERCIAL_SQL_PASSWORD", script.text)
        self.assertNotIn("OPENAI_API_KEY", script.text)

    def test_protected_commercial_api_is_not_changed_by_demo_preview(self):
        # A separate app: the existing commercial API still requires real IdP config.
        with TestClient(secured_api) as client:
            self.assertIn(client.get("/v1/meetings").status_code, (401, 503))
            self.assertIn(client.get("/v1/modules").status_code, (401, 503))


if __name__ == "__main__":
    unittest.main()
