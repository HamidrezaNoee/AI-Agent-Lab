"""Offline v2 management Q&A authorization and bound SQL tests; no external systems."""
from contextlib import contextmanager
from unittest.mock import patch
import unittest
from uuid import UUID

from fastapi.testclient import TestClient
from commercial.api import app, _authenticated_principal
from commercial.directory_questions import authorized_question_snapshot
from commercial.meeting_questions import QUESTIONS
from commercial.security import Principal
from commercial.sql_store import AccessDenied


class ActionCursor:
    def __init__(self, parent):
        self.parent=parent
        self.rows=[]
    def execute(self, statement,*values):
        self.parent.queries.append((statement,values))
        if "FROM AgentProduct.ActionIndex a" in statement:
            self.rows=[
                (900001,"A-001","پیگیری واردات","بازرگانی",
                 "2026-09-01T10:00:00Z",45,0)
            ]
        return self
    def fetchall(self):
        return self.rows


class ActionConnection:
    def __init__(self):
        self.queries=[]
    def cursor(self):
        return ActionCursor(self)


class DirectoryQuestionTests(unittest.TestCase):
    def setUp(self):
        self.p=Principal(UUID("11111111-1111-4111-8111-111111111111"),"lab-alice")

    def test_snapshot_reads_only_previous_v2_authorized_meetings(self):
        page={
            "meetings":[
                {"meeting_id":900001,"meeting_no":"LAB-900001","title":"نمونه",
                 "status":"InProgress"}
            ],
            "has_more":False,
            "next_cursor":None,
        }
        con=ActionConnection()
        with patch("commercial.directory_questions.visible_directory_meetings",
                   return_value=page) as allowed:
            records,complete=authorized_question_snapshot(con,self.p)
        self.assertTrue(complete)
        self.assertEqual(len(records),1)
        self.assertEqual(records[0]["actions"][0]["action_no"],"A-001")
        allowed.assert_called_once_with(con,self.p,before_id=None,limit=50)
        self.assertEqual(len(con.queries),1)
        query,values=con.queries[0]
        self.assertIn("a.TenantID=?",query)
        self.assertIn("a.MeetingID IN (?)",query)
        self.assertEqual(values,(str(self.p.tenant_id),900001))
        self.assertNotIn("lab-alice",query)
        self.assertIsNone(records[0]["meeting_date_utc"])
        self.assertIsNone(records[0]["risk"])

    def test_unexpected_action_meeting_fails_closed(self):
        con=ActionConnection()
        original=ActionCursor.execute
        def tampered(cursor,sql,*params):
            original(cursor,sql,*params)
            if "FROM AgentProduct.ActionIndex a" in sql:
                cursor.rows=[(900002,"A-1","secret","unit",
                              "2026-09-01T10:00:00Z",1,0)]
            return cursor
        with patch("commercial.directory_questions.visible_directory_meetings",
                   return_value={"meetings":[
                       {"meeting_id":900001,"meeting_no":"LAB-900001",
                        "title":"safe","status":"Open"}
                   ],"has_more":False}),patch.object(ActionCursor,"execute",tampered):
            with self.assertRaises(AccessDenied):
                authorized_question_snapshot(con,self.p)

    def test_unlinked_or_unlicensed_user_cannot_call_real_qa(self):
        app.dependency_overrides[_authenticated_principal]=lambda:self.p
        @contextmanager
        def fake_conn(principal):
            self.assertEqual(principal,self.p)
            yield object()
        try:
            with (patch("commercial.directory_api.scoped_connection",fake_conn),
                  patch("commercial.directory_api.authorization_snapshot",
                        return_value={"role":"Viewer"}),
                  patch("commercial.directory_api.directory_role",
                        return_value="Expert"),
                  patch("commercial.directory_api.require_module",
                        side_effect=AccessDenied("not purchased")) as gate,
                  patch("commercial.directory_api.authorized_question_snapshot",
                        side_effect=AssertionError("SQL data read before license"))):
                with TestClient(app) as client:
                    for question,code in ((QUESTIONS[0],4),(QUESTIONS[1],3),
                                          (QUESTIONS[7],2)):
                        with self.subTest(question=question):
                            response=client.post("/v2/assistant/ask",
                                                 json={"question":question})
                            self.assertEqual(response.status_code,403)
                    self.assertEqual(gate.call_count,3)
        finally:
            app.dependency_overrides.clear()

    def test_single_meeting_status_does_not_need_paid_module(self):
        app.dependency_overrides[_authenticated_principal]=lambda:self.p
        @contextmanager
        def fake_conn(principal):
            yield object()
        records=[{
            "meeting_id":900001,"meeting_no":"LAB-900001",
            "title":"نمونه","meeting_status":"InProgress",
            "meeting_date_utc":None,"risk":None,
            "actions":[{
                "action_no":"A-001","description":"کار نمونه",
                "owner_unit":"واحد نمونه","progress_percent":50,
                "due_at_utc":"2026-09-01T10:00:00Z","is_closed":False
            }]
        }]
        try:
            with (patch("commercial.directory_api.scoped_connection",fake_conn),
                  patch("commercial.directory_api.authorization_snapshot",
                        return_value={"role":"Viewer"}),
                  patch("commercial.directory_api.directory_role",
                        return_value="Expert"),
                  patch("commercial.directory_api.require_module",
                        side_effect=AssertionError("Base answer may not require paid module")),
                  patch("commercial.directory_api.authorized_question_snapshot",
                        return_value=(records,True))):
                with TestClient(app) as client:
                    response=client.post("/v2/assistant/ask",json={
                        "question":"اقدامات جلسه شماره LAB-900001 در چه وضعیتی هستند؟"
                    })
                    self.assertEqual(response.status_code,200)
                    body=response.json()
                    self.assertEqual(body["required_module"],1)
                    self.assertEqual(body["items"][0]["source"]["meeting_id"],900001)
                    self.assertEqual(body["tenant_id"],str(self.p.tenant_id))
                    self.assertTrue(body["read_only"])
                    self.assertFalse(body["model_used"])
        finally:
            app.dependency_overrides.clear()

    def test_unsigned_access_to_v2_question_endpoint_is_never_200(self):
        with TestClient(app) as client:
            self.assertIn(client.post("/v2/assistant/ask",
                json={"question":QUESTIONS[0]}).status_code,(401,503))
            self.assertIn(client.get("/v2/assistant/questions").status_code,(401,503))

    def test_client_supplied_subject_tenant_or_sql_is_rejected(self):
        app.dependency_overrides[_authenticated_principal]=lambda:self.p
        try:
            with TestClient(app) as client:
                for key in ("tenant_id","subject","sql"):
                    response=client.post("/v2/assistant/ask",
                        json={"question":QUESTIONS[0],key:"attacker"})
                    self.assertEqual(response.status_code,422)
        finally:
            app.dependency_overrides.clear()


if __name__=="__main__":
    unittest.main()
