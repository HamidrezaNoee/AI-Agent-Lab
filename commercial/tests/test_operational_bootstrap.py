"""Security acceptance checks for operational first-run GodAdmin.

Internal source checks only; no fictional company or MTG records are served to
customers and no external SQL, IdP, SMTP or ProcessMaker connection is made.
"""
import contextlib
import io
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from commercial import setup_console as setup
from commercial import setup_routes as routes


class GodAdminBootTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        root=Path(self.tmp.name)
        self.patches=[
            patch.object(setup,"ROOT",root),
            patch.object(setup,"SQLITE",root/"setup.sqlite3"),
            patch.object(setup,"KEYFILE",root/"setup.key"),
            patch.object(setup,"INITIAL",root/"initial-godadmin-password"),
            patch.object(setup,"PUBLIC",root/"license-public.pem"),
            patch.dict("os.environ",{"AVAN_PUBLIC_ORIGIN":"http://127.0.0.1:8188"}),
            patch.object(routes,"_local",return_value=True),
        ]
        for p in self.patches:p.start()
        routes._sessions.clear()
        routes._attempts.clear()
        setup.initialize()
        self.initial=setup.INITIAL.read_text(encoding="utf-8").strip()
        app=FastAPI()
        app.include_router(routes.router)
        self.client=TestClient(app,base_url="http://127.0.0.1:8188")

    def tearDown(self):
        self.client.close()
        for p in reversed(self.patches):p.stop()
        self.tmp.cleanup()

    def test_bootstrap_password_is_random_one_time_and_not_in_source_config(self):
        self.assertGreaterEqual(len(self.initial),24)
        self.assertTrue(setup.password_ok(self.initial))
        setup.initialize()
        self.assertEqual(setup.INITIAL.read_text(encoding="utf-8").strip(),self.initial)
        self.assertEqual(setup.SQLITE.stat().st_mode & 0o077,0)
        captured=io.StringIO()
        with contextlib.redirect_stdout(captured):
            setup.take_bootstrap()
        self.assertIn(self.initial,captured.getvalue())
        self.assertFalse(setup.INITIAL.exists())
        with contextlib.redirect_stdout(io.StringIO()) as other:
            setup.take_bootstrap()
        self.assertNotIn(self.initial,other.getvalue())

    def test_secret_settings_are_authenticated_and_encrypted_at_rest(self):
        denied=self.client.get("/admin/api/settings")
        self.assertEqual(denied.status_code,401)
        setup.put_setting("mysql",{"host":"host.docker.internal", "port":3306,
              "database":"wf_workflow","username":"avan_reader",
              "password":"unique-private-SQL-value",
              "tls":True})
        self.assertNotIn(b"unique-private-SQL-value",setup.SQLITE.read_bytes())
        self.assertEqual(setup.get_setting("mysql")["password"],
                         "unique-private-SQL-value")
        self.assertEqual(setup.masked_settings()["mysql"]["password"],"********")

    def test_initial_login_forces_password_rotation_and_mfa(self):
        response=self.client.post("/admin/api/login",json={
             "username":"godadmin","password":self.initial})
        self.assertEqual(response.status_code,200)
        self.assertFalse(response.json()["password_changed"])
        self.assertEqual(self.client.get("/admin/api/settings").status_code,403)
        csrf=response.json()["csrf"]
        rotated=self.client.post("/admin/api/change-password",
            headers={"X-AVAN-ADMIN-CSRF":csrf},json={
                "current":self.initial,
                "updated":"A-different-long-strong-passphrase-2026!"
            })
        self.assertEqual(rotated.status_code,200)
        self.assertFalse(setup.INITIAL.exists())
        self.assertFalse(setup.password_ok(self.initial))
        new_login=self.client.post("/admin/api/login",json={
            "username":"godadmin",
            "password":"A-different-long-strong-passphrase-2026!"
        })
        self.assertEqual(new_login.status_code,200)
        csrf=new_login.json()["csrf"]
        enrolled=self.client.post("/admin/api/totp/enrollment",
                      headers={"X-AVAN-ADMIN-CSRF":csrf},json={})
        self.assertEqual(enrolled.status_code,200)
        code=setup._totp(enrolled.json()["secret"],int(time.time()))
        confirmed=self.client.post("/admin/api/totp/confirm",
                      headers={"X-AVAN-ADMIN-CSRF":csrf},json={"code":code})
        self.assertEqual(confirmed.status_code,200)
        self.assertEqual(self.client.get("/admin/api/settings").status_code,401)
        self.assertEqual(self.client.post("/admin/api/login",json={
            "username":"godadmin","password":"A-different-long-strong-passphrase-2026!",
            "otp":"000000"}).status_code,401)
        signed=self.client.post("/admin/api/login",json={
            "username":"godadmin","password":"A-different-long-strong-passphrase-2026!",
            "otp":setup._totp(enrolled.json()["secret"],int(time.time()))
        })
        self.assertEqual(signed.status_code,200)
        self.assertEqual(self.client.get("/admin/api/settings").status_code,200)

    def test_csrf_and_failed_login_rate_limit(self):
        bad=self.client.post("/admin/api/login",json={
            "username":"godadmin","password":self.initial+"wrong"})
        self.assertEqual(bad.status_code,401)
        ok=self.client.post("/admin/api/login",json={
            "username":"godadmin","password":self.initial})
        self.assertEqual(ok.status_code,200)
        self.assertEqual(self.client.post("/admin/api/change-password",json={
            "current":self.initial,"updated":"Another-secure-16-char-value!"
        }).status_code,403)
        for _ in range(5):
            self.client.post("/admin/api/logout",json={},
                        headers={"X-AVAN-ADMIN-CSRF":"invalid"})
        self.assertEqual(self.client.get("/admin/api/settings").status_code,403)


if __name__=="__main__":
    unittest.main()

