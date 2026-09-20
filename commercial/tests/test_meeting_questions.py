"""Eight Persian management questions are real deterministic reports over fictional data.

No SQL, IdP, external model or ProcessMaker calls. Assertions use a fixed UTC
clock so overdue/this-month results do not depend on when CI is executed.
"""
from datetime import datetime, timezone
import json
from pathlib import Path
import unittest

from commercial.meeting_questions import QUESTIONS, _intent, answer_question
from commercial.demo_preview import app
from fastapi.testclient import TestClient

DATA=Path(__file__).resolve().parents[1] / "datasets" / "100_automotive_meeting_scenarios_FA.json"
NOW=datetime(2026,9,20,20,0,tzinfo=timezone.utc)


class PersianManagementQuestionsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.meetings=json.loads(DATA.read_text(encoding="utf-8"))["scenarios"]

    def ask(self, question, meetings=None, **kwargs):
        return answer_question(question, self.meetings if meetings is None else meetings,
                               now=NOW, **kwargs)

    def test_all_eight_questions_have_distinct_supported_intents(self):
        actual=[_intent(question) for question in QUESTIONS]
        self.assertEqual(actual,[
            "overdue_actions","monthly_unresolved","unit_performance",
            "owner_backlog","meeting_status","risks","recurring","next_agenda"
        ])

    def test_overdue_uses_utc_deadline_open_and_cites_real_sample_actions(self):
        result=self.ask(QUESTIONS[0])
        self.assertEqual(result["intent"],"overdue_actions")
        self.assertTrue(result["items"])
        for item in result["items"]:
            self.assertFalse(item["is_closed"])
            self.assertLess(item["progress_percent"],100)
            self.assertLess(datetime.fromisoformat(
                item["due_at_utc"].replace("Z","+00:00")),NOW)
            self.assertTrue(item["source"]["meeting_no"].startswith("LAB-"))
            self.assertTrue(item["source"]["action_no"].startswith("A-"))
        self.assertFalse(result["model_used"])

    def test_unresolved_this_month_filters_out_future_and_previous_month(self):
        sample=[
            dict(self.meetings[1],meeting_id=1,meeting_date_utc="2026-09-10T08:00:00Z"),
            dict(self.meetings[1],meeting_id=2,meeting_date_utc="2026-09-30T08:00:00Z"),
            dict(self.meetings[1],meeting_id=3,meeting_date_utc="2026-08-30T08:00:00Z"),
        ]
        result=self.ask(QUESTIONS[1],sample)
        self.assertEqual(result["intent"],"monthly_unresolved")
        self.assertEqual([x["source"]["meeting_id"] for x in result["items"]],[1])

    def test_unit_performance_and_open_owners_do_not_invent_manager_identity(self):
        performance=self.ask(QUESTIONS[2])
        owner=self.ask(QUESTIONS[3])
        self.assertTrue(performance["items"])
        self.assertTrue(owner["items"])
        self.assertTrue(any("مدیران ممکن نیست" in note for note in owner["notes"]))
        self.assertTrue(all("owner_unit" in item for item in owner["items"]))

    def test_specific_meeting_is_exact_and_does_not_fall_back_to_other_records(self):
        answer=self.ask(QUESTIONS[4])
        self.assertEqual(answer["intent"],"meeting_status")
        self.assertTrue(answer["items"])
        self.assertTrue(all(x["source"]["meeting_no"]=="LAB-910002" for x in answer["items"]))
        denied=self.ask("وضعیت اقدامات جلسه شماره LAB-999999 چیست؟")
        self.assertFalse(denied["items"])
        self.assertIn("پیدا نشد",denied["answer"])

    def test_missing_dates_and_risks_fail_informatively(self):
        record=dict(self.meetings[1],meeting_date_utc=None,risk=None)
        month=self.ask(QUESTIONS[1],[record])
        risk=self.ask(QUESTIONS[5],[record])
        self.assertIn("تاریخ تشکیل جلسات",month["answer"])
        self.assertFalse(risk["items"])
        self.assertIn("موجود نیست",risk["answer"])

    def test_recurring_titles_require_evidence_from_two_distinct_meetings(self):
        a=dict(self.meetings[1],meeting_id=1)
        b=dict(self.meetings[1],meeting_id=2)
        c=dict(self.meetings[2],meeting_id=3)
        result=self.ask(QUESTIONS[6],[a,b,c])
        self.assertEqual(len(result["items"]),2)
        self.assertEqual({x["source"]["meeting_id"] for x in result["items"]},{1,2})
        self.assertTrue(any("شباهت معنایی" in n for n in result["notes"]))

    def test_shared_title_keywords_are_labeled_as_lexical_not_semantic(self):
        left=dict(self.meetings[1],meeting_id=1,meeting_no="LAB-1",
                  title="تأخیر در تخصیص ارز")
        right=dict(self.meetings[2],meeting_id=2,meeting_no="LAB-2",
                   title="تأخیر در ترخیص")
        result=self.ask(QUESTIONS[6],[left,right])
        self.assertEqual(result["intent"],"recurring")
        self.assertTrue(result["items"])
        self.assertTrue(any("کلیدواژه" in item["text"] for item in result["items"]))
        self.assertTrue(any("هم‌پوشانی" in n for n in result["notes"]))
        self.assertEqual({i["source"]["meeting_id"] for i in result["items"]},{1,2})

    def test_future_agenda_is_draft_based_on_open_actions(self):
        result=self.ask(QUESTIONS[7])
        self.assertTrue(result["items"])
        self.assertTrue(any("تأیید" in n for n in result["notes"]))
        self.assertTrue(all(x["source"]["action_no"] for x in result["items"]))

    def test_absent_scope_never_invents_meetings_or_actions(self):
        for question in QUESTIONS:
            with self.subTest(question=question):
                result=self.ask(question,[])
                self.assertEqual(result["meetings_considered"],0)
                self.assertEqual(result["actions_considered"],0)
                self.assertEqual(result["sources"],[])

    def test_unrecognized_question_discloses_limited_coverage(self):
        result=self.ask("درباره حسابداری امروز توضیح کامل بده",[])
        self.assertEqual(result["intent"],"unsupported")
        self.assertEqual(result["suggested_questions"],list(QUESTIONS))

    def test_api_serves_all_questions_and_fictional_citations_only(self):
        with TestClient(app) as client:
            choices=client.get("/demo-questions")
            self.assertEqual(choices.status_code,200)
            self.assertEqual(len(choices.json()["questions"]),8)
            for question in QUESTIONS:
                result=client.post("/demo-ask",json={"question":question})
                self.assertEqual(result.status_code,200,question)
                body=result.json()
                self.assertTrue(body["synthetic"])
                self.assertFalse(body["model_used"])
                self.assertEqual(body["meetings_considered"],100)
                self.assertEqual(body["actions_considered"],300)
                self.assertLessEqual(len(body["items"]),10)
                self.assertEqual(body["sources"],
                                 [item["source"] for item in body["items"]])

    def test_demo_question_contract_rejects_untrusted_tenant_or_excess(self):
        with TestClient(app) as client:
            for payload in ({"question":"اقدامات عقب‌افتاده","tenant_id":"other"},
                            {"question":"a"*351},
                            {"question":""}):
                with self.subTest(payload=payload):
                    self.assertEqual(client.post("/demo-ask",json=payload).status_code,422)


if __name__=="__main__":
    unittest.main()
