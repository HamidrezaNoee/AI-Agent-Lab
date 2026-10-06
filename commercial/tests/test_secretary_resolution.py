import copy
import pytest

from commercial import secretary_resolution as resolution
from commercial import secretary_runtime as runtime
from commercial.tests.test_secretary_inbox import task
from commercial.tests.test_secretary_workflow import S


def scope_with_people():
    scope=copy.deepcopy(S)
    scope["directory"]={
        "s"*32:{"active":True,"name":"دبیر","username":"secretary"},
        "c"*32:{"active":True,"name":"رئیس","username":"ceo"},
        "a"*32:{"active":True,"name":"مدیر سیستم","username":"administrator"},
        "b"*32:{"active":True,"name":"مدیر فروش","username":"mgr.sales"},
    }
    return scope


def minutes_values():
    return {
        "MTG_MeetingHeld":"Held",
        "MTG_MeetingDiscussionSummary":"جمع‌بندی جلسه",
        "MTG_MeetingEndDateTime":"1405/07/24",
        "MTG_PlannedActionEndTime":"17:00",
        "MTG_Decisions":{"1":{"MTG_DecisionNo":"D-001","MTG_DecisionText":"فایل برنامه واردات به‌روز شود"}},
        "MTG_Actions":{"1":{
            "MTG_ActionNo":"A-001",
            "MTG_ActionDescription":"به‌روزرسانی فایل برنامه واردات",
            "MTG_ActionOwnerUID":"",
            "MTG_persiandate_ActionDueDateTime":"1405/07/18",
            "MTG_ActionDecisionNo":"D-001",
        }},
    }


def test_pending_confirmation_is_built_from_unique_explicit_candidate(pack):
    scope=scope_with_people()
    values=minutes_values()
    gaps=runtime.gaps(values,task(pack,"minutes"))
    pending=resolution.propose_identity_confirmation(
        "برای مسئول اقدام ۱، نام کاربری موجود «administrator» است. لطفاً تأیید کنید منظور همین کاربر است.",
        values,gaps,scope["directory"])
    assert pending["field_path"]=="MTG_Actions.1.MTG_ActionOwnerUID"
    assert pending["value"]=="a"*32
    assert pending["display"]=="administrator"


@pytest.mark.parametrize("answer",[
    "بله","بله همان است","آره همونه","مورد تاییده","تأیید است","اوکی",
])
def test_short_affirmations_apply_pending_value_without_model(pack,monkeypatch,answer):
    scope=scope_with_people()
    values=minutes_values()
    pending={
        "version":1,"kind":"set_identity",
        "field_path":"MTG_Actions.1.MTG_ActionOwnerUID",
        "value":"a"*32,"display":"administrator",
        "question":"اقدام 1: MTG_ActionOwnerUID را تعیین کنید.",
    }
    monkeypatch.setattr(runtime,"extract",lambda *a,**kw:pytest.fail("confirmation must not call model"))
    result,questions,reply,intent,next_pending=runtime.converse(
        answer,task(pack,"minutes"),values,scope,
        questions=[pending["question"]],pending_confirmation=pending)
    assert result["MTG_Actions"]["1"]["MTG_ActionOwnerUID"]=="a"*32
    assert pending["question"] not in questions
    assert intent=="resolved"
    assert next_pending is None
    assert "administrator" in reply


def test_explicit_correction_overrides_pending_candidate_without_model(pack,monkeypatch):
    scope=scope_with_people()
    values=minutes_values()
    pending={
        "version":1,"kind":"set_identity",
        "field_path":"MTG_Actions.1.MTG_ActionOwnerUID",
        "value":"a"*32,"display":"administrator",
        "question":"اقدام 1: MTG_ActionOwnerUID را تعیین کنید.",
    }
    monkeypatch.setattr(runtime,"extract",lambda *a,**kw:pytest.fail("correction must not call model"))
    result,questions,reply,intent,next_pending=runtime.converse(
        "نه، mgr.sales",task(pack,"minutes"),values,scope,
        questions=[pending["question"]],pending_confirmation=pending)
    assert result["MTG_Actions"]["1"]["MTG_ActionOwnerUID"]=="b"*32
    assert intent=="resolved" and next_pending is None
    assert "mgr.sales" in reply


def test_admin_alias_can_resolve_only_known_unique_administrator(pack,monkeypatch):
    scope=scope_with_people()
    values=minutes_values()
    pending={
        "version":1,"kind":"set_identity",
        "field_path":"MTG_Actions.1.MTG_ActionOwnerUID",
        "value":"b"*32,"display":"mgr.sales",
        "question":"اقدام 1: MTG_ActionOwnerUID را تعیین کنید.",
    }
    monkeypatch.setattr(runtime,"extract",lambda *a,**kw:pytest.fail("direct identity must not call model"))
    result,_,reply,intent,_=runtime.converse(
        "ادمین",task(pack,"minutes"),values,scope,
        questions=[pending["question"]],pending_confirmation=pending)
    assert result["MTG_Actions"]["1"]["MTG_ActionOwnerUID"]=="a"*32
    assert intent=="resolved" and "administrator" in reply


def test_negative_confirmation_does_not_mutate_draft(pack,monkeypatch):
    scope=scope_with_people()
    values=minutes_values()
    before=copy.deepcopy(values)
    pending={
        "version":1,"kind":"set_identity",
        "field_path":"MTG_Actions.1.MTG_ActionOwnerUID",
        "value":"a"*32,"display":"administrator",
        "question":"اقدام 1: MTG_ActionOwnerUID را تعیین کنید.",
    }
    monkeypatch.setattr(runtime,"extract",lambda *a,**kw:pytest.fail("negative answer must not call model"))
    result,questions,reply,intent,next_pending=runtime.converse(
        "نه این نیست",task(pack,"minutes"),values,scope,
        questions=[pending["question"]],pending_confirmation=pending)
    assert result==before
    assert questions==[pending["question"]]
    assert intent=="question" and next_pending is None
    assert "شخص درست" in reply


def test_stale_candidate_is_never_confirmed(pack,monkeypatch):
    scope=scope_with_people()
    scope["directory"]["a"*32]["active"]=False
    values=minutes_values()
    pending={
        "version":1,"kind":"set_identity",
        "field_path":"MTG_Actions.1.MTG_ActionOwnerUID",
        "value":"a"*32,"display":"administrator",
        "question":"اقدام 1: MTG_ActionOwnerUID را تعیین کنید.",
    }
    monkeypatch.setattr(runtime,"extract",lambda *a,**kw:pytest.fail("stale confirmation must not call model"))
    result,questions,reply,intent,next_pending=runtime.converse(
        "بله",task(pack,"minutes"),values,scope,
        questions=[pending["question"]],pending_confirmation=pending)
    assert result["MTG_Actions"]["1"]["MTG_ActionOwnerUID"]==""
    assert intent=="question" and next_pending is None
    assert "دیگر" in reply


def test_multiple_missing_owners_require_explicit_row_reference(pack):
    scope=scope_with_people()
    values=minutes_values()
    values["MTG_Actions"]["2"]={
        "MTG_ActionNo":"A-002","MTG_ActionDescription":"پیگیری مالی",
        "MTG_ActionOwnerUID":"","MTG_persiandate_ActionDueDateTime":"1405/07/18",
        "MTG_ActionDecisionNo":"D-001",
    }
    gaps=runtime.gaps(values,task(pack,"minutes"))
    assert resolution.propose_identity_confirmation(
        "کاربر administrator را تأیید کنید.",values,gaps,scope["directory"]) is None
    pending=resolution.propose_identity_confirmation(
        "مسئول اقدام ۲ همان کاربر administrator است؛ تأیید کنید.",values,gaps,scope["directory"])
    assert pending["field_path"]=="MTG_Actions.2.MTG_ActionOwnerUID"


def test_model_generated_confirmation_becomes_structured_pending_state(pack,monkeypatch):
    scope=scope_with_people()
    values=minutes_values()
    def fake_extract(*args,**kwargs):
        return copy.deepcopy(values),["اقدام 1: MTG_ActionOwnerUID را تعیین کنید."],(
            "برای مسئول اقدام ۱، نام کاربری موجود «administrator» است. "
            "لطفاً تأیید کنید منظور همین کاربر است."
        ),"update"
    monkeypatch.setattr(runtime,"extract",fake_extract)
    result,questions,reply,intent,pending=runtime.converse(
        "ادمین",task(pack,"minutes"),values,scope,
        questions=["اقدام 1: MTG_ActionOwnerUID را تعیین کنید."])
    assert result==values and intent=="update"
    assert pending["field_path"]=="MTG_Actions.1.MTG_ActionOwnerUID"
    assert pending["display"]=="administrator"


def test_confirmation_intent_is_not_generic_update_to_prevent_accidental_advance(pack,monkeypatch):
    scope=scope_with_people()
    values=minutes_values()
    pending={
        "version":1,"kind":"set_identity",
        "field_path":"MTG_Actions.1.MTG_ActionOwnerUID",
        "value":"a"*32,"display":"administrator",
        "question":"اقدام 1: MTG_ActionOwnerUID را تعیین کنید.",
    }
    monkeypatch.setattr(runtime,"extract",lambda *a,**kw:pytest.fail("confirmation must not call model"))
    _,_,_,intent,_=runtime.converse(
        "بله",task(pack,"minutes"),values,scope,
        questions=[pending["question"]],pending_confirmation=pending)
    assert intent=="resolved"
