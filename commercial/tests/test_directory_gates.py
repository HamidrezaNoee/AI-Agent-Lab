"""Offline authorization-gate regression for v2 directory & GodAdmin routes.

No external PM, SQL, OIDC or model. THIS IS NOT an end-to-end identity test.
"""
from contextlib import contextmanager
import unittest
import uuid
from unittest.mock import patch

from fastapi.testclient import TestClient
from commercial.api import app, _authenticated_principal
from commercial.security import Principal


class V2GateTests(unittest.TestCase):
    def setUp(self):
        self.principal=Principal(uuid.uuid4(),"not-linked")
        app.dependency_overrides[_authenticated_principal]=lambda:self.principal
        self.client=TestClient(app)

    def tearDown(self):
        self.client.close()
        app.dependency_overrides.clear()

    def test_missing_directory_link_fails_closed(self):
        # A valid bearer principal alone is insufficient. Membership and a
        # linked, active PM account must both be present in the same tenant.
        from commercial.sql_store import AccessDenied
        @contextmanager
        def fake_connection(principal):
            self.assertEqual(principal,self.principal)
            yield object()
        with (patch("commercial.directory_api.scoped_connection",fake_connection),
              patch("commercial.directory_api.authorization_snapshot",
                    return_value={"role":"Viewer"}),
              patch("commercial.directory_api.visible_directory_meetings",
                    side_effect=AccessDenied("unlinked"))):
            response=self.client.get("/v2/meetings/page")
        self.assertEqual(response.status_code,403)
        self.assertNotIn("unlinked",response.text)

    def test_unsigned_sysadmin_role_fails_before_sql_writes(self):
        with patch("commercial.directory_api.directory_admin_connection",
                   side_effect=AssertionError("Unexpected SQL write")):
            for endpoint,method,payload in (
                ("/v2/admin/processmaker/users/sync","post",{"deactivate_missing":False}),
                ("/v2/admin/directory/"+("a"*32)+"/role","put",{"role":"Manager"}),
                ("/v2/admin/branding","put",
                 {"company_name":"شرکت آزمایشی","primary_color":"#124A6C"}),
            ):
                with self.subTest(endpoint=endpoint):
                    res=getattr(self.client,method)(endpoint,json=payload)
                    self.assertEqual(res.status_code,403)

    def test_signed_sysadmin_role_is_not_sufficient_without_sql_role(self):
        self.principal=Principal(uuid.uuid4(),"fictional",frozenset({"SysAdmin"}))
        with patch("commercial.directory_api._active_member",
                   return_value=({"role":"Viewer"},"Expert")),patch(
                   "commercial.directory_api.directory_admin_connection",
                   side_effect=AssertionError("Unexpected admin SQL connection")):
            response=self.client.get("/v2/admin/system/connections")
        self.assertEqual(response.status_code,403)

    def test_password_reset_requires_both_signed_and_db_sysadmin(self):
        target = "/v2/admin/directory/" + ("a"*32) + "/send-password-update"
        with patch("commercial.directory_api.password_update_email",
                   side_effect=AssertionError("Unexpected external identity call")):
            self.assertEqual(self.client.post(target).status_code, 403)
            self.principal = Principal(uuid.uuid4(), "fictional",
                                       frozenset({"SysAdmin"}))
            with patch("commercial.directory_api._active_member",
                       return_value=({"role": "Viewer"}, "Expert")):
                self.assertEqual(self.client.post(target).status_code, 403)

    def test_unregistered_godadmin_is_not_automatically_provisioned(self):
        self.principal=Principal(uuid.uuid4(),"unregistered",frozenset({"GodAdmin"}))
        @contextmanager
        def fake_platform():
            class Cursor:
                def execute(self,*args):return self
                def fetchone(self):return (0,)
            class Con:
                def cursor(self):return Cursor()
            yield Con()
        with patch("commercial.godadmin_api.platform_connection",fake_platform):
            self.assertEqual(self.client.get("/v2/godadmin/status").status_code,403)
            self.assertEqual(self.client.get("/v2/godadmin/tenants").status_code,403)

    def test_ordinary_subject_cannot_read_platform_catalog(self):
        with patch("commercial.godadmin_api.platform_connection",
                   side_effect=AssertionError("Platform SQL should not be touched")):
            self.assertEqual(self.client.get("/v2/godadmin/tenants").status_code,403)
            self.assertEqual(self.client.post("/v2/godadmin/tenants",
                         json={"company_name":"مشتری نمونه"}).status_code,403)

    def test_letter_route_has_no_public_access_and_bounded_page(self):
        self.assertEqual(self.client.get("/v2/letters/page",
                                         params={"limit":51}).status_code,422)
        with patch("commercial.directory_api.scoped_connection",
                   side_effect=AssertionError("No query on invalid input")):
            self.assertEqual(self.client.get("/v2/letters/page",
                        params={"limit":0}).status_code,422)


if __name__=="__main__":
    unittest.main()
