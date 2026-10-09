"""Cross-stage regression: dense turns must be consumed exhaustively in every AVAN secretary stage."""
import copy
from types import SimpleNamespace
import pytest

from commercial import secretary_runtime as runtime
from commercial import secretary_coverage as coverage
from commercial import secretary_time
from commercial.tests.test_secretary_inbox import task
from commercial.tests.test_secretary_workflow import S


CASES={
    "invitation_approval":{
        "notes":"""دعوت‌نامه را تأیید می‌کنم.
توضیحات رئیس: متن دعوت مناسب است.
تاریخ جلسه 20 مهر 1405 باشد.""",
        "values":{
            "MTG_InvitationApproval":"Approved",
            "MTG_InvitationChairComment":"متن دعوت مناسب است.",
            "MTG_MeetingStartDateTime":"1405/07/20",
        },
        "expected":{"MTG_InvitationApproval","MTG_InvitationChairComment","MTG_MeetingStartDateTime"},
    },
    "minutes_approval":{
        "notes":"""صورت‌جلسه را تأیید می‌کنم.
نظر رئیس: مصوبات و اقدامات قابل قبول است.
خلاصه مصوبات و اقدامات: چهار مصوبه و پنج اقدام تأیید شد.""",
        "values":{
            "MTG_MinutesApproval":"Approved",
            "MTG_ChairComment":"مصوبات و اقدامات قابل قبول است.",
            "MTG_ApprovalSummary":"چهار مصوبه و پنج اقدام تأیید شد.",
        },
        "expected":{"MTG_MinutesApproval","MTG_ChairComment","MTG_ApprovalSummary"},
    },
    "action_execution":{
        "notes":"""گزارش پیشرفت است.
پیشرفت 80 درصد است.
شرح اجرا: بخش اصلی کار انجام شد.
زمان صرف‌شده 90 دقیقه بود.""",
        "values":{
            "MTGA_SubmissionType":"ProgressUpdate",
            "MTGA_ProgressPercent":"80",
            "MTGA_ExecutionDescription":"بخش اصلی کار انجام شد.",
            "MTGA_ActualEffortMinutes":"90",
        },
        "expected":{"MTGA_SubmissionType","MTGA_ProgressPercent","MTGA_ExecutionDescription","MTGA_ActualEffortMinutes"},
    },
    "action_review":{
        "notes":"""اقدام برای اصلاح برگردد.
پیشرفت تأییدشده 60 درصد است.
نظر دبیر: مستند کامل نیست.
زمان واقعی 45 دقیقه تأیید می‌شود.""",
        "values":{
            "MTGA_ReviewStatus2":"Rework",
            "MTGA_SecretaryProgressPercent2":"60",
            "MTGA_SecretaryComment1":"مستند کامل نیست.",
            "MTGA_SecretaryActualEffortMinutes2":"45",
        },
        "expected":{"MTGA_ReviewStatus2","MTGA_SecretaryProgressPercent2","MTGA_SecretaryComment1","MTGA_SecretaryActualEffortMinutes2"},
    },
}


def monitoring_case():
    native={
        "MTG_ActionSummary":{
            "1":{
                "MTG_MonActionNo":"A-001",
                "MTG_MonDescription":"اقدام اول",
                "MTG_MonOwner":"mgr.strategy",
                "MTG_MonDueDate":"1405/07/20",
                "MTG_MonStatus":"Open",
                "MTG_MonProgress":"80",
                "MTG_MonActualCompletion":"",
                "MTG_MonChildCaseNo":"101",
            },
            "2":{
                "MTG_MonActionNo":"A-002",
                "MTG_MonDescription":"اقدام دوم",
                "MTG_MonOwner":"mgr.sales",
                "MTG_MonDueDate":"1405/07/22",
                "MTG_MonStatus":"Open",
                "MTG_MonProgress":"70",
                "MTG_MonActualCompletion":"",
                "MTG_MonChildCaseNo":"102",
            },
        }
    }
    values={
        "MTG_ClosingNote":"اقدام اول بسته و اقدام دوم برای اصلاح برگردانده شد.",
        "MTG_ActionSummary":{
            "1":{
                **native["MTG_ActionSummary"]["1"],
                "MTG_MonSecReviewStatus":"Closed",
                "MTG_MonSecProgress":"100",
            },
            "2":{
                **native["MTG_ActionSummary"]["2"],
                "MTG_MonSecReviewStatus":"Rework",
                "MTG_MonSecProgress":"70",
                "MTG_MonSecComment":"مدرک تکمیل شود.",
            },
        },
    }
    notes="""جمع‌بندی اختتام: اقدام اول بسته و اقدام دوم برای اصلاح برگردانده شد.
اقدام A-001 بسته شود و پیشرفت 100 درصد تأیید شود.
اقدام A-002 برای اصلاح برگردد، پیشرفت 70 درصد، نظر دبیر: مدرک تکمیل شود."""
    return notes,native,values


@pytest.mark.parametrize("stage",list(CASES))
def test_every_non_minutes_dense_stage_is_detected(pack,stage):
    case=CASES[stage]
    t=task(pack,stage)
    requirements=coverage.explicit_field_requirements(case["notes"],t)
    fields={row["field"] for row in requirements}
    assert case["expected"] <= fields
    assert coverage.is_compound_turn(case["notes"],t)


def test_monitoring_dense_stage_is_detected(pack):
    notes,native,values=monitoring_case()
    t=task(pack,"monitoring",native)
    fields={row["field"] for row in coverage.explicit_field_requirements(notes,t)}
    assert {"MTG_ClosingNote","MTG_ActionSummary"} <= fields
    assert coverage.is_compound_turn(notes,t)
    contract=coverage.coverage_prompt(notes,t,{})
    assert contract["monitoring_action_count"]==2
    assert [x["action_no"] for x in contract["monitoring_actions"]]==["A-001","A-002"]


@pytest.mark.parametrize("stage",list(CASES))
def test_dense_stage_routes_directly_to_full_extraction(pack,monkeypatch,stage):
    case=CASES[stage]
    t=task(pack,stage)

    monkeypatch.setattr(secretary_time,"apply",lambda *a,**kw:pytest.fail("dense turn must bypass temporal.resolve"))
    monkeypatch.setattr(runtime.resolution,"resolve_direct_identity",lambda *a,**kw:pytest.fail("dense turn must bypass identity.resolve"))
    monkeypatch.setattr(runtime.commands,"apply",lambda *a,**kw:pytest.fail("dense turn must bypass draft.command"))
    monkeypatch.setattr(runtime,"extract",lambda *a,**kw:(copy.deepcopy(case["values"]),[],"همه اطلاعات صریح این پیام ثبت شد.","update"))

    result=runtime.converse(case["notes"],t,{},copy.deepcopy(S))
    assert result.receipt["tool"]=="draft.extract"
    for key,value in case["values"].items():
        assert result[0][key]==value


def test_dense_monitoring_routes_directly_to_full_extraction(pack,monkeypatch):
    notes,native,values=monitoring_case()
    t=task(pack,"monitoring",native)

    monkeypatch.setattr(secretary_time,"apply",lambda *a,**kw:pytest.fail("dense monitoring must bypass temporal.resolve"))
    monkeypatch.setattr(runtime.resolution,"resolve_direct_identity",lambda *a,**kw:pytest.fail("dense monitoring must bypass identity.resolve"))
    monkeypatch.setattr(runtime.commands,"apply",lambda *a,**kw:pytest.fail("dense monitoring must bypass draft.command"))
    monkeypatch.setattr(runtime,"extract",lambda *a,**kw:(copy.deepcopy(values),[],"پایش کامل ثبت شد.","update"))

    result=runtime.converse(notes,t,{},copy.deepcopy(S))
    assert result.receipt["tool"]=="draft.extract"
    assert result[0]["MTG_ClosingNote"]==values["MTG_ClosingNote"]
    assert len(result[0]["MTG_ActionSummary"])==2


@pytest.mark.parametrize("stage",list(CASES))
def test_cross_stage_coverage_rejects_first_field_only(pack,stage):
    case=CASES[stage]
    t=task(pack,stage)
    first=next(iter(case["expected"]))
    assignments=[SimpleNamespace(field=first)]
    values={first:case["values"][first]}
    issues=coverage.coverage_issues(case["notes"],t,values,assignments,{})
    assert issues,stage


def test_monitoring_coverage_rejects_missing_second_action(pack):
    notes,native,values=monitoring_case()
    t=task(pack,"monitoring",native)
    partial=copy.deepcopy(values)
    partial["MTG_ActionSummary"].pop("2")
    assignments=[SimpleNamespace(field="MTG_ClosingNote"),SimpleNamespace(field="MTG_ActionSummary")]
    issues=coverage.coverage_issues(notes,t,partial,assignments,{})
    text="\n".join(issues)
    assert "A-002" in text
    assert "جا افتاده" in text


def test_single_focused_field_stays_fast_path_eligible(pack):
    # The safeguard must not force every tiny answer through the LLM.
    assert not coverage.is_compound_turn("پیشرفت 80 درصد",task(pack,"action_execution"))
    assert not coverage.is_compound_turn("نظر دبیر: مدرک ناقص است",task(pack,"action_review"))
