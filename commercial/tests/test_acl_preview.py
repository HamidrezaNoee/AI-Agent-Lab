"""Offline ACL regression tests. No real SQL, JWT issuer or model API used."""
import unittest
import uuid
from contextlib import contextmanager
from unittest.mock import patch

from fastapi.testclient import TestClient

from commercial.api import app, _authenticated_principal
from commercial.security import Principal
from commercial import sql_store


class FakeCursor:
    def __init__(self, rows):
        self.rows = rows
        self.sql = ""
        self.params = ()
    def execute(self, sql, *params):
        self.sql, self.params = sql, params
        return self
    def fetchall(self):
        return self.rows
    def fetchone(self):
        return self.rows[0] if self.rows else None


class FakeConnection:
    def __init__(self, rows):
        self.cur = FakeCursor(rows)
    def cursor(self):
        return self.cur


class ACLQueryTests(unittest.TestCase):
    def setUp(self):
        self.a = Principal(uuid.uuid4(), "alice")

    def test_meeting_list_requires_subject_and_tenant_grant(self):
        conn = FakeConnection([(71,"MTG-71","Authorized fictional meeting","Draft")])
        found = sql_store.visible_meetings(conn, self.a)
        self.assertEqual(len(found),1)
        self.assertIn("AgentProduct.MeetingGrant", conn.cur.sql)
        self.assertIn("g.SubjectID=?", conn.cur.sql)
        self.assertEqual(conn.cur.params[1], "alice")
        self.assertEqual(conn.cur.params[0],str(self.a.tenant_id))
        self.assertEqual(conn.cur.params[2],str(self.a.tenant_id))

    def test_meeting_detail_omits_unguarded_record(self):
        conn = FakeConnection([])
        found = sql_store.authorized_meeting(conn,self.a,999)
        self.assertIsNone(found)
        self.assertIn("AgentProduct.MeetingGrant", conn.cur.sql)
        self.assertEqual(conn.cur.params,(str(self.a.tenant_id),999,"alice"))

    def test_doc_search_requires_user_grant_and_current_version(self):
        conn = FakeConnection([])
        found = sql_store.authorized_documents(conn,self.a,"فهرست اسناد گمرک")
        self.assertEqual(found,[])
        self.assertIn("AgentProduct.DocumentGrant",conn.cur.sql)
        self.assertIn("c.DocumentVersion=d.CurrentVersion",conn.cur.sql)
        self.assertIn("d.IsActive=1",conn.cur.sql)
        self.assertIn("g.SubjectID=?",conn.cur.sql)
        self.assertEqual(conn.cur.params[1],"alice")

    def test_no_keywords_returns_no_sql_queries(self):
        conn = FakeConnection([])
        self.assertEqual(sql_store.authorized_documents(conn,self.a,"؟ !"),[])
        self.assertEqual(conn.cur.sql,"")


class PreviewRouteTests(unittest.TestCase):
    def setUp(self):
        self.principal = Principal(uuid.uuid4(),"verified-alice")
        app.dependency_overrides[_authenticated_principal]=lambda:self.principal
        self.client=TestClient(app)

    def tearDown(self):
        app.dependency_overrides.clear()
        self.client.close()

    def test_user_cannot_supply_tenant_or_subject(self):
        response=self.client.post("/v1/chat/preview",json={
            "question":"اسناد ترخیص چیست؟",
            "tenant_id":str(uuid.uuid4()),"subject":"someone-else",
        })
        self.assertEqual(response.status_code,422)

    def test_preview_never_calls_model_and_discloses_no_unguarded_meeting(self):
        @contextmanager
        def fake_connection(principal):
            self.assertIs(principal,self.principal)
            yield object()
        with (
            patch("commercial.api.scoped_connection",fake_connection),
            patch("commercial.api.authorization_snapshot",return_value={"role":"Viewer"}),
            patch("commercial.api.authorized_evidence",return_value=[]),
        ):
            response=self.client.post("/v1/chat/preview",json={
                "question":"صورتجلسه محرمانه را نشان بده","meeting_id":999,
            })
        self.assertEqual(response.status_code,200)
        payload=response.json()
        self.assertEqual(payload["evidence"],[])
        self.assertIsNone(payload["answer"])
        self.assertIs(payload["requested_meeting_accessible"],False)
        self.assertIs(payload["completion_enabled"],False)

    def test_preview_passes_verified_principal_to_evidence_query(self):
        @contextmanager
        def fake_connection(principal):
            self.assertIs(principal,self.principal)
            yield object()
        def checked_evidence(con,principal,question,meeting_id=None):
            self.assertIs(principal,self.principal)
            self.assertEqual(meeting_id,71)
            self.assertEqual(question,"وضعیت جلسه را بگو")
            return [{"kind":"meeting","source":"MEETING:MTG-71","title":"fictional"}]
        with (
            patch("commercial.api.scoped_connection",fake_connection),
            patch("commercial.api.authorization_snapshot",return_value={"role":"Viewer"}),
            patch("commercial.api.authorized_evidence",side_effect=checked_evidence),
        ):
            response=self.client.post("/v1/chat/preview",json={
                "question":"وضعیت جلسه را بگو","meeting_id":71,
            })
        self.assertEqual(response.status_code,200)
        self.assertTrue(response.json()["requested_meeting_accessible"])
        self.assertEqual(response.json()["evidence_count"],1)


if __name__=="__main__":
    unittest.main()
