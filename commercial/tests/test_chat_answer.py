"""Offline, fail-closed commercial /v1/chat/answer tests. SQL + provider mocked."""
from contextlib import contextmanager
import os
import types
import unittest
import uuid
from unittest.mock import patch

from fastapi.testclient import TestClient

from commercial.api import app, _authenticated_principal
from commercial.answer import AnswerResult, AnswerUnreliable
from commercial.quota import QuotaExceeded, Reservation
from commercial.security import Principal


class ChatAnswerTests(unittest.TestCase):
    def setUp(self):
        self.principal=Principal(uuid.uuid4(),"alice-test")
        app.dependency_overrides[_authenticated_principal]=lambda:self.principal
        self.client=TestClient(app)
        self.env=patch.dict(os.environ,{
            "COMMERCIAL_MODE":"lab",
            "COMMERCIAL_SQL_DATABASE":"EnterpriseProcess2_AI_Test",
            "COMMERCIAL_CHAT_ENABLED":"1",
            "OPENAI_API_KEY":"offline-fake-key-NOT-SENT",
        })
        self.env.start()
        self.evidence=[{"kind":"meeting","source":"MEETING:SIM-A-01",
                        "meeting_no":"SIM-A-01","title":"جلسه ساختگی","status":"Draft"}]
        self.reservation=Reservation(uuid.uuid4(),1,2)
        self.answer=AnswerResult(
            answer="جلسه ساختگی است. [MEETING:SIM-A-01]",
            claims=[{"text":"جلسه ساختگی است.","source":"MEETING:SIM-A-01"}],
            sources=["MEETING:SIM-A-01"],input_tokens=35,output_tokens=15,
            model="gpt-4.1-mini"
        )

    def tearDown(self):
        app.dependency_overrides.clear()
        self.client.close()
        self.env.stop()

    @contextmanager
    def fake_connection(self, principal):
        self.assertIs(principal,self.principal)
        yield object()

    def call(self, payload):
        return self.client.post("/v1/chat/answer",json=payload)

    def test_disabled_feature_returns_503_without_sql_or_model(self):
        with (
            patch.dict(os.environ,{"COMMERCIAL_CHAT_ENABLED":"0"}),
            patch("commercial.api.scoped_connection",side_effect=AssertionError("SQL touched")),
            patch("commercial.api.build_answer",side_effect=AssertionError("Model touched")),
        ):
            r=self.call({"question":"وضعیت جلسه چیست؟"})
        self.assertEqual(r.status_code,503)

    def test_no_evidence_does_not_reserve_or_call_provider(self):
        with (
            patch("commercial.api.scoped_connection",self.fake_connection),
            patch("commercial.api.authorization_snapshot",return_value={"role":"Viewer"}),
            patch("commercial.api.authorized_evidence",return_value=[]),
            patch("commercial.api.reserve_request",side_effect=AssertionError("Quota reserved")),
            patch("commercial.api.build_answer",side_effect=AssertionError("Model called")),
        ):
            r=self.call({"question":"مدرکی دارید؟"})
        self.assertEqual(r.status_code,200)
        self.assertEqual(r.json()["status"],"no_authorized_evidence")
        self.assertFalse(r.json()["charged_request"])

    def test_ungranted_meeting_is_not_disclosed_even_with_documents(self):
        with (
            patch("commercial.api.scoped_connection",self.fake_connection),
            patch("commercial.api.authorization_snapshot",return_value={"role":"Viewer"}),
            patch("commercial.api.authorized_evidence",return_value=[
                {"kind":"document","source":"DOC:TEST:v1:c1","excerpt":"text"}]),
            patch("commercial.api.reserve_request",side_effect=AssertionError("Quota reserved")),
        ):
            r=self.call({"question":"جلسه را پیدا کن","meeting_id":999})
        self.assertEqual(r.status_code,404)
        self.assertNotIn("DOC:TEST:v1:c1",r.text)

    def test_atomic_quota_exhaustion_prevents_model_call(self):
        with (
            patch("commercial.api.scoped_connection",self.fake_connection),
            patch("commercial.api.authorization_snapshot",return_value={"role":"Viewer"}),
            patch("commercial.api.authorized_evidence",return_value=self.evidence),
            patch("commercial.api.reserve_request",side_effect=QuotaExceeded()),
            patch("commercial.api.build_answer",side_effect=AssertionError("Model called")),
        ):
            r=self.call({"question":"وضعیت جلسه چیست؟","meeting_id":71})
        self.assertEqual(r.status_code,429)

    def test_success_reserves_and_finalizes_before_responding(self):
        seen=[]
        def reserved(con, principal, req_id, model):
            self.assertIs(principal,self.principal)
            self.assertEqual(model,"gpt-4.1-mini")
            seen.append(("reserve",req_id))
            return Reservation(req_id,1,2)
        def finalized(con, principal, req_id, completed, input_tokens=None, output_tokens=None):
            self.assertIs(principal,self.principal)
            self.assertTrue(completed)
            self.assertEqual((input_tokens,output_tokens),(35,15))
            self.assertEqual(req_id,seen[0][1])
            seen.append(("finalize",req_id))
        def answer(question,evidence):
            self.assertEqual(evidence,self.evidence)
            seen.append(("model",None))
            return self.answer
        with (
            patch("commercial.api.scoped_connection",self.fake_connection),
            patch("commercial.api.authorization_snapshot",return_value={"role":"Viewer"}),
            patch("commercial.api.authorized_evidence",return_value=self.evidence),
            patch("commercial.api.reserve_request",side_effect=reserved),
            patch("commercial.api.build_answer",side_effect=answer),
            patch("commercial.api.finalize_request",side_effect=finalized),
        ):
            r=self.call({"question":"وضعیت جلسه چیست؟","meeting_id":71})
        self.assertEqual(r.status_code,200)
        self.assertEqual([item[0] for item in seen],["reserve","model","finalize"])
        self.assertEqual(r.json()["sources"],["MEETING:SIM-A-01"])
        self.assertEqual(r.json()["quota"],{"used_this_month":1,"monthly_limit":2})
        self.assertTrue(r.json()["charged_request"])

    def test_model_failure_finalizes_failed_and_returns_502(self):
        seen=[]
        def finalized(con,principal,req_id,completed,input_tokens=None,output_tokens=None):
            seen.append((completed,input_tokens,output_tokens))
        with (
            patch("commercial.api.scoped_connection",self.fake_connection),
            patch("commercial.api.authorization_snapshot",return_value={"role":"Viewer"}),
            patch("commercial.api.authorized_evidence",return_value=self.evidence),
            patch("commercial.api.reserve_request",side_effect=lambda con,p,rid,m:Reservation(rid,1,2)),
            patch("commercial.api.build_answer",side_effect=AnswerUnreliable("Bad citation")),
            patch("commercial.api.finalize_request",side_effect=finalized),
        ):
            r=self.call({"question":"وضعیت جلسه چیست؟"})
        self.assertEqual(r.status_code,502)
        self.assertEqual(seen,[(False,None,None)])
        self.assertNotIn("Bad citation",r.text)

    def test_client_cannot_choose_tenant_or_model_or_sql(self):
        for key,value in (("tenant_id",str(uuid.uuid4())),("model","other"),("sql","SELECT * FROM MTG.Meeting")):
            with self.subTest(key=key):
                r=self.call({"question":"وضعیت جلسه چیست؟",key:value})
                self.assertEqual(r.status_code,422)


if __name__=="__main__":
    unittest.main()
