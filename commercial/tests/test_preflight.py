"""Offline isolated deployment preflight tests; no SQL/PM/OIDC network calls."""
import tempfile
from pathlib import Path
import unittest
from commercial.preflight import assess_settings


class ReadinessTests(unittest.TestCase):
    def setUp(self):
        self.base = {
            "COMMERCIAL_MODE": "lab",
            "COMMERCIAL_SQL_DATABASE": "EnterpriseProcess2_AI_Test",
            "COMMERCIAL_V2_ONLY": "1",
            "COMMERCIAL_CHAT_ENABLED": "0",
            "COMMERCIAL_WEB_PORTAL_ENABLED": "1",
            "COMMERCIAL_SQL_SERVER": "lab-sql",
            "COMMERCIAL_SQL_USER": "AI_CommercialReader",
            "COMMERCIAL_SQL_PASSWORD": "private-test-value",
            "COMMERCIAL_DIRECTORY_SQL_USER": "AI_CommercialDirectoryAdmin",
            "COMMERCIAL_DIRECTORY_SQL_PASSWORD": "other-test-value",
            "COMMERCIAL_PLATFORM_SQL_USER": "AI_CommercialPlatformAdmin",
            "COMMERCIAL_PLATFORM_SQL_PASSWORD": "third-test-value",
            "COMMERCIAL_PM_SYNC_ENABLED": "1",
            "COMMERCIAL_PM_BASE_URL": "https://pm.example.test",
            "COMMERCIAL_PM_WORKSPACE": "workflow",
            "COMMERCIAL_PM_BEARER_TOKEN": "placeholder-private-token",
            "COMMERCIAL_OIDC_ISSUER": "https://idp.example.test/realm",
            "COMMERCIAL_OIDC_AUDIENCE": "meeting-api",
            "COMMERCIAL_OIDC_JWKS_URL": "https://idp.example.test/realm/keys",
        }

    def test_lab_isolation_is_mandatory(self):
        values = dict(self.base, COMMERCIAL_SQL_DATABASE="EnterpriseProcess")
        self.assertFalse(assess_settings(values)["isolated_database"])

    def test_old_data_routes_are_flagged(self):
        values = dict(self.base, COMMERCIAL_V2_ONLY="0")
        self.assertFalse(assess_settings(values)["hierarchy_content_gate"])

    def test_commercial_model_is_explicitly_disabled(self):
        values = dict(self.base, COMMERCIAL_CHAT_ENABLED="1")
        self.assertFalse(assess_settings(values)["external_chat_disabled"])

    def test_separate_admin_users_not_shared_with_reader(self):
        checks = assess_settings(self.base)
        self.assertTrue(checks["separate_directory_admin_configured"])
        self.assertTrue(checks["separate_platform_admin_configured"])
        values = dict(self.base, COMMERCIAL_DIRECTORY_SQL_USER="AI_CommercialReader")
        self.assertFalse(assess_settings(values)["separate_directory_admin_configured"])

    def test_https_oidc_and_local_font_checks(self):
        with tempfile.TemporaryDirectory() as folder:
            checks = assess_settings(self.base, font_root=folder)
            self.assertTrue(checks["oidc_https_metadata_configured"])
            self.assertFalse(checks["byekanplus_fonts_local"])
            for weight in ("regular","bold"):
                (Path(folder)/("byekanplus-"+weight+".ttf")).touch()
            self.assertTrue(assess_settings(self.base,font_root=folder)["byekanplus_fonts_local"])
        values = dict(self.base, COMMERCIAL_OIDC_JWKS_URL="http://untrusted.local/keys")
        self.assertFalse(assess_settings(values)["oidc_https_metadata_configured"])


if __name__ == "__main__":
    unittest.main()
