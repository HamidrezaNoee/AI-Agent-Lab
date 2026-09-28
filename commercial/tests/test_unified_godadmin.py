"""First-run promotion and server-side separation of platform and staff access."""
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient

from commercial import production_app as app,setup_console as setup,setup_routes as admin


TENANT="168418b2-8fa6-4414-a37f-83c9a26da332"
ISSUER="https://identity.example.com/realms/avan"


class Response:
    content=b"{}"
    def __init__(self,payload):self.payload=payload
    def raise_for_status(self):pass
    def json(self):return self.payload


class IdentityClient:
    def __init__(self,**_kwargs):pass
    def __enter__(self):return self
    def __exit__(self,*_args):pass
    def post(self,_url,data):
        subject=data["code"]
        return Response({"access_token":subject+"-token","id_token":"id",
                         "refresh_token":"refresh"})
    def get(self,_url,headers):
        subject=headers["Authorization"].split()[-1].removesuffix("-token")
        return Response({"sub":subject,"name":subject,
                         "email":subject+"@example.com","email_verified":True})


class Verifier:
    def authenticate(self,header):
        subject=header.split()[-1].removesuffix("-token")
        return SimpleNamespace(subject=subject,tenant_id=TENANT,roles=frozenset())


class UnifiedGodAdminTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        root=Path(self.tmp.name)
        self.patches=[
            patch.object(setup,"ROOT",root),patch.object(setup,"SQLITE",root/"setup.sqlite3"),
            patch.object(setup,"KEYFILE",root/"setup.key"),
            patch.object(setup,"INITIAL",root/"initial-godadmin-password"),
            patch.object(setup,"PUBLIC",root/"license-public.pem"),
            patch.object(admin,"_local",return_value=True),
            patch.object(app,"_oidc_config",return_value=("https://identity.example.com/auth",
                "https://identity.example.com/token","avan-bff","secret",Verifier())),
            patch.object(app.httpx,"Client",IdentityClient),
            patch.object(app.jwt,"decode",return_value={"exp":time.time()+1800}),
            patch.dict("os.environ",{"AVAN_PUBLIC_ORIGIN":"http://127.0.0.1:8188"}),
        ]
        for p in self.patches:p.start()
        setup.initialize()
        setup.put_setting("oidc",{"issuer":ISSUER})
        setup.put_setting("company",{"tenant_id":TENANT,"company_name":"ایران رور"})
        admin._sessions.clear();app.sessions.clear();app.pending.clear()
        self.client=TestClient(app.app,base_url="http://127.0.0.1:8188")

    def tearDown(self):
        self.client.close()
        admin._sessions.clear();app.sessions.clear();app.pending.clear()
        for p in reversed(self.patches):p.stop()
        self.tmp.cleanup()

    def oidc_login(self,subject):
        begin=self.client.get("/auth/login",follow_redirects=False)
        self.assertEqual(begin.status_code,302)
        state=next(reversed(app.pending))
        return self.client.get("/auth/callback",params={"code":subject,"state":state},
                               follow_redirects=False)

    def test_first_admin_binds_signed_identity_and_ordinary_user_is_denied(self):
        self.assertEqual(self.client.get("/",follow_redirects=False).headers["location"],"/admin/")
        self.assertEqual(self.client.get("/auth/login").status_code,403)
        self.assertEqual(self.client.get("/admin/api/settings").status_code,401)

        password=setup.INITIAL.read_text().strip()
        rotated="A-real-long-bootstrap-passphrase!"
        setup.change_password(password,rotated)
        secret=setup.totp_enrollment()
        code=setup._totp(secret,int(time.time()))
        setup.confirm_totp(code)

        # A signed account is staged, with no PM data or workspace session.
        self.assertEqual(self.oidc_login("operator").headers["location"],"/auth/pending")
        self.assertFalse(app.sessions)
        signed=self.client.post("/admin/api/login",json={"username":"godadmin",
                  "password":rotated,"otp":code})
        self.assertEqual(signed.status_code,200)
        csrf={"X-AVAN-ADMIN-CSRF":signed.json()["csrf"]}
        payload={"tenant_id":TENANT,"subject":"operator","otp":"000000"}
        self.assertEqual(self.client.post("/admin/api/identity/bind-godadmin",
                         json=payload,headers=csrf).status_code,403)
        payload["otp"]=setup._totp(secret,int(time.time()))
        self.assertEqual(self.client.post("/admin/api/identity/bind-godadmin",
                         json=payload,headers=csrf).status_code,200)
        self.assertEqual(setup.godadmin_identity()["subject"],"operator")
        self.assertEqual(self.client.post("/admin/api/login",json={"username":"godadmin",
                  "password":rotated,"otp":payload["otp"]}).status_code,403)
        self.assertEqual(self.client.get("/admin/api/settings").status_code,401)

        admitted=self.oidc_login("operator")
        self.assertEqual(admitted.headers["location"],"/")
        state=self.client.get("/admin/api/state").json()
        self.assertTrue(state["authenticated"])
        self.assertEqual(state["auth_mode"],"oidc")
        self.assertEqual(self.client.get("/admin/api/settings").status_code,200)
        self.assertTrue(self.client.get("/api/me").json()["is_godadmin"])
        self.assertEqual(self.client.get("/api/meetings").status_code,403)
        self.assertEqual(self.client.get("/",follow_redirects=False).status_code,200)
        self.assertEqual(self.client.post("/admin/api/bpms/connections/enabled",
                         json={"source_id":"a"*24,"enabled":False}).status_code,403)
        setup.put_setting("mysql",{"host":"database.example.com"})
        setup.put_setting("agent_sql",{"server":"local"})
        self.assertEqual(self.client.get("/",follow_redirects=False).status_code,200)

        # Even a forged browser session for an ordinary signed identity cannot
        # use admin endpoints or replace the bound owner.
        other=TestClient(app.app,base_url="http://127.0.0.1:8188")
        try:
            app.sessions["ordinary"]={"access_token":"employee-token","csrf":"csrf",
                "expires":time.time()+1800,"idle_expires":time.time()+600,
                "access_expires":time.time()+1500,"subject":"employee","tenant_id":TENANT}
            other.cookies.set("avan_session","ordinary")
            self.assertFalse(other.get("/admin/api/state").json()["authenticated"])
            self.assertEqual(other.get("/admin/api/settings").status_code,403)
            self.assertEqual(other.post("/admin/api/bpms/connections/enabled",
                             json={"source_id":"a"*24,"enabled":False},
                             headers={"X-AVAN-ADMIN-CSRF":"csrf"}).status_code,403)
        finally:
            other.close()
        signed_out=self.client.post("/auth/logout",headers={"X-AVAN-CSRF":state["csrf"]})
        self.assertEqual(signed_out.status_code,200)
        self.assertEqual(self.client.get("/admin/api/settings").status_code,401)

    def test_binding_requires_matching_issuer_and_host_recovery_unbinds(self):
        setup.bind_godadmin_identity(TENANT,"operator")
        self.assertTrue(setup.is_godadmin(SimpleNamespace(subject="operator",tenant_id=TENANT)))
        with self.assertRaises(setup.SetupError):
            setup.bind_godadmin_identity(TENANT,"another")
        setup.put_setting("oidc",{"issuer":"https://changed.example.com/realms/avan"})
        self.assertFalse(setup.is_godadmin(SimpleNamespace(subject="operator",tenant_id=TENANT)))
        setup.reset_from_docker_host()
        self.assertIsNone(setup.godadmin_identity())
        self.assertFalse(setup.password_state()["changed"])
        self.assertEqual(self.client.get("/auth/login").status_code,403)

    def test_bootstrap_can_create_unprivileged_identity_without_pm_mapping(self):
        password=setup.INITIAL.read_text().strip()
        setup.change_password(password,"A-different-long-strong-password!")
        seed=setup.totp_enrollment();otp=setup._totp(seed,int(time.time()))
        setup.confirm_totp(otp)
        setup.put_setting("oidc",{"issuer":ISSUER,"managed_by_product":True})
        key=setup.ROOT/"provisioner"
        key.write_text("a-secret-only-used-in-tests")
        login=self.client.post("/admin/api/login",json={"username":"godadmin",
               "password":"A-different-long-strong-password!","otp":otp})
        self.assertEqual(login.status_code,200)
        from commercial import identity_operator
        with patch.dict("os.environ",{"AVAN_PROVISIONER_CLIENT_SECRET_PATH":str(key)}), \
             patch.object(identity_operator,"create",return_value="signed-subject") as create:
            result=self.client.post("/admin/api/identity/create-godadmin-account",
                headers={"X-AVAN-ADMIN-CSRF":login.json()["csrf"]},
                json={"username":"owner","email":"owner@example.com","name":"Owner",
                      "password":"A-temporary-long-password!","otp":otp})
            self.assertEqual(result.status_code,200)
            self.assertEqual(create.call_args.args[-2],"GodAdmin")
        self.assertNotIn(b"A-temporary-long-password!",setup.SQLITE.read_bytes())
        self.assertIsNone(setup.godadmin_identity())


if __name__=="__main__":unittest.main()
