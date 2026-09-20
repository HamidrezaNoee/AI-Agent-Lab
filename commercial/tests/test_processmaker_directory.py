"""Offline PM sync/role/identity tests: no PM network, SQL, secrets or IdP."""
import os
import unittest
from unittest.mock import patch
from commercial.processmaker_directory import PMUser, PMSyncUnavailable, clean_users, fetch_users, safe_preview

U1="a"*31+"1"
U2="a"*31+"2"


class PMDirectoryTests(unittest.TestCase):
    def test_legacy_password_and_privilege_fields_are_dropped(self):
        raw=[{"usr_uid":U1,"usr_username":"  car_user ","usr_firstname":"علی",
              "usr_lastname":"کاظمی","usr_email":"user@example.test",
              "usr_status":"ACTIVE","usr_password":"LEGACY-MD5-MUST-NEVER-STORE",
              "usr_role":"PROCESSMAKER_ADMIN"}]
        rows=clean_users(raw)
        self.assertEqual(rows,[PMUser(U1,"car_user","علی کاظمی","user@example.test","ACTIVE")])
        preview=str(safe_preview(rows))
        self.assertNotIn("LEGACY-MD5-MUST-NEVER-STORE",preview)
        self.assertNotIn("PROCESSMAKER_ADMIN",preview)
        self.assertEqual(safe_preview(rows)["active"],1)

    def test_malformed_status_uid_or_duplicate_are_denied(self):
        valid={"usr_uid":U1,"usr_username":"alice","usr_status":"ACTIVE"}
        for incoming in ([dict(valid,usr_uid="bad")],
                         [dict(valid,usr_status="SUPERADMIN")],
                         [valid,valid],
                         [{"usr_uid":U2,"usr_username":"","usr_status":"ACTIVE"}],
                         {"not":"a list"}):
            with self.subTest(incoming=incoming),self.assertRaises(PMSyncUnavailable):
                clean_users(incoming)

    def test_sync_is_disabled_by_default(self):
        with patch.dict(os.environ,{"COMMERCIAL_PM_SYNC_ENABLED":"0"}):
            with self.assertRaises(PMSyncUnavailable):
                fetch_users()

    def test_live_pm_url_requires_https_or_explicit_loopback(self):
        env={"COMMERCIAL_PM_SYNC_ENABLED":"1","COMMERCIAL_MODE":"lab",
             "COMMERCIAL_SQL_DATABASE":"EnterpriseProcess2_AI_Test"}
        with patch.dict(os.environ,env):
            for url in ("http://pm.example.test", "http://192.168.1.5",
                        "https://user:pass@pm.example.test"):
                with self.subTest(url=url),self.assertRaises(PMSyncUnavailable):
                    fetch_users(base_url=url,workspace="workflow",bearer="test-bearer-value")
            with self.assertRaises(PMSyncUnavailable):
                fetch_users(base_url="https://pm.example.test",workspace="../workflow",
                            bearer="test-bearer-value")


if __name__=="__main__":
    unittest.main()
