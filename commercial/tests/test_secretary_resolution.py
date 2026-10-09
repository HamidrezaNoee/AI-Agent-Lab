import copy
import pytest

from commercial import secretary_resolution as resolution
from commercial import secretary_runtime as runtime
from commercial.tests.test_secretary_inbox import pack, task
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
        "MTG_MeetingEndTime":"16:00",
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
    "بله","بله همان است","آره همونه","مورد تاییده","مورد تاییده.","تأیید است","اوکی","بله administrator",
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
        "پیشنهاد مسئول را بررسی کن",task(pack,"minutes"),values,scope,
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


def test_legacy_history_reconstructs_pending_confirmation_without_model(pack,monkeypatch):
    scope=scope_with_people()
    values=minutes_values()
    question="اقدام 1: MTG_ActionOwnerUID را تعیین کنید."
    history=[
        {"role":"user","text":"ادمین"},
        {"role":"assistant","text":"برای مسئول اقدام ۱، «ادمین» را دریافت کردم؛ اما نام کاربری موجود در فهرست «administrator» است. لطفاً تأیید کنید منظور همین کاربر است."},
    ]
    monkeypatch.setattr(runtime,"extract",lambda *a,**kw:pytest.fail("legacy confirmation recovery must not call model"))
    result,questions,reply,intent,pending=runtime.converse(
        "بله همان است",task(pack,"minutes"),values,scope,
        questions=[question],pending_confirmation=None,history=history)
    assert result["MTG_Actions"]["1"]["MTG_ActionOwnerUID"]=="a"*32
    assert intent=="resolved" and pending is None
    assert question not in questions
    assert "administrator" in reply


def test_pending_confirmation_cannot_overwrite_newer_manual_edit(pack,monkeypatch):
    scope=scope_with_people()
    values=minutes_values()
    values["MTG_Actions"]["1"]["MTG_ActionOwnerUID"]="b"*32
    pending={
        "version":1,"kind":"set_identity",
        "field_path":"MTG_Actions.1.MTG_ActionOwnerUID",
        "value":"a"*32,"display":"administrator",
        "expected_value":"",
        "question":"اقدام 1: MTG_ActionOwnerUID را تعیین کنید.",
    }
    monkeypatch.setattr(runtime,"extract",lambda *a,**kw:pytest.fail("stale confirmation must not call model"))
    result,questions,reply,intent,next_pending=runtime.converse(
        "بله",task(pack,"minutes"),values,scope,
        questions=[pending["question"]],pending_confirmation=pending)
    assert result["MTG_Actions"]["1"]["MTG_ActionOwnerUID"]=="b"*32
    assert intent=="question" and next_pending is None
    assert "تغییر کرده" in reply


def test_expired_confirmation_cannot_mutate_draft(pack,monkeypatch):
    from datetime import datetime,timedelta,timezone
    scope=scope_with_people()
    values=minutes_values()
    pending={
        "version":1,"kind":"set_identity",
        "field_path":"MTG_Actions.1.MTG_ActionOwnerUID",
        "value":"a"*32,"display":"administrator",
        "expected_value":"",
        "question":"اقدام 1: MTG_ActionOwnerUID را تعیین کنید.",
        "expires_at":(datetime.now(timezone.utc)-timedelta(minutes=1)).isoformat(),
    }
    monkeypatch.setattr(runtime,"extract",lambda *a,**kw:pytest.fail("expired confirmation must not call model"))
    result,_,reply,intent,next_pending=runtime.converse(
        "بله همان است",task(pack,"minutes"),values,scope,
        questions=[pending["question"]],pending_confirmation=pending)
    assert result["MTG_Actions"]["1"]["MTG_ActionOwnerUID"]==""
    assert intent=="question" and next_pending is None
    assert "منقضی" in reply


@pytest.mark.parametrize("answer,uid",[
    ("administrator","a"*32),
    ("ادمین","a"*32),
    ("مسئول اقدام ۱ mgr.sales باشد","b"*32),
])
def test_direct_identity_answer_bypasses_model_without_pending(pack,monkeypatch,answer,uid):
    scope=scope_with_people()
    values=minutes_values()
    question="اقدام 1: MTG_ActionOwnerUID را تعیین کنید."
    monkeypatch.setattr(runtime,"extract",lambda *a,**kw:pytest.fail("direct identity must not call model"))
    result,questions,reply,intent,pending=runtime.converse(
        answer,task(pack,"minutes"),values,scope,
        questions=[question],pending_confirmation=None,history=[])
    assert result["MTG_Actions"]["1"]["MTG_ActionOwnerUID"]==uid
    assert question not in questions
    assert intent=="resolved" and pending is None


def test_identity_question_never_mutates_directly(pack,monkeypatch):
    scope=scope_with_people()
    values=minutes_values()
    called={"value":False}
    def fake_extract(*args,**kwargs):
        called["value"]=True
        return copy.deepcopy(values),["اقدام 1: MTG_ActionOwnerUID را تعیین کنید."],"آیا منظور administrator است؟","question"
    monkeypatch.setattr(runtime,"extract",fake_extract)
    result,_,reply,intent,pending=runtime.converse(
        "آیا administrator است؟",task(pack,"minutes"),values,scope,
        questions=["اقدام 1: MTG_ActionOwnerUID را تعیین کنید."])
    assert called["value"] is True
    assert result["MTG_Actions"]["1"]["MTG_ActionOwnerUID"]==""
    assert intent=="question"
    assert pending is not None
    assert pending["value"]=="a"*32


def test_question_mark_identity_phrase_never_becomes_direct_edit(pack,monkeypatch):
    scope=scope_with_people()
    values=minutes_values()
    called={"value":False}
    def fake_extract(*args,**kwargs):
        called["value"]=True
        return copy.deepcopy(values),["اقدام 1: MTG_ActionOwnerUID را تعیین کنید."],"بله، administrator یکی از گزینه‌های معتبر است.","question"
    monkeypatch.setattr(runtime,"extract",fake_extract)
    result,_,_,intent,_=runtime.converse(
        "مسئول اقدام ۱ administrator است؟",task(pack,"minutes"),values,scope,
        questions=["اقدام 1: MTG_ActionOwnerUID را تعیین کنید."])
    assert called["value"] is True
    assert result["MTG_Actions"]["1"]["MTG_ActionOwnerUID"]==""
    assert intent=="question"


def test_semantic_duplicate_owner_question_is_removed_after_confirmation(pack,monkeypatch):
    scope=scope_with_people()
    values=minutes_values()
    pending={
        "version":1,"kind":"set_identity",
        "field_path":"MTG_Actions.1.MTG_ActionOwnerUID",
        "value":"a"*32,"display":"administrator",
        "question":"اقدام 1: MTG_ActionOwnerUID را تعیین کنید.",
    }
    questions=[
        pending["question"],
        "لطفاً مسئول اصلی اقدام ۱ را مشخص کنید.",
        "سؤال دیگری باقی بماند",
    ]
    monkeypatch.setattr(runtime,"extract",lambda *a,**kw:pytest.fail("confirmation must not call model"))
    _,remaining,_,intent,_=runtime.converse(
        "بله همان است",task(pack,"minutes"),values,scope,
        questions=questions,pending_confirmation=pending)
    assert intent=="resolved"
    assert remaining==["سؤال دیگری باقی بماند"]


def test_dotted_username_with_spaces_resolves_against_latest_assistant_action(pack,monkeypatch):
    scope=scope_with_people()
    licensing_uid="c"*32
    scope["directory"][licensing_uid]={
        "active":True,
        "username":"mgr.licensing",
        "name":"مدیر مجوزات",
    }
    values=minutes_values()
    values["MTG_Actions"]["2"]={
        "MTG_ActionNo":"A-002",
        "MTG_ActionDescription":"تکمیل مدارک ثبت سفارش مدل HEV 2026",
        "MTG_ActionOwnerUID":"",
        "MTG_persiandate_ActionDueDateTime":"1405/07/18",
        "MTG_ActionDecisionNo":"D-001",
    }
    question1="مسئول اصلی اقدام A-001 را مشخص کنید."
    question2="مسئول اصلی اقدام A-002 را مشخص کنید."
    history=[
        {"role":"assistant","text":"فعلاً روی اقدام A-002 مانده‌ایم. مسئول اصلی A-002 چه کسی است؟ لطفاً نام دقیق یا UID را بفرمایید."}
    ]
    monkeypatch.setattr(runtime,"extract",lambda *a,**kw:pytest.fail("dotted username must not call model"))
    result,questions,reply,intent,pending=runtime.converse(
        "mgr .licensing",task(pack,"minutes"),values,scope,
        questions=[question1,question2],pending_confirmation=None,history=history)
    assert result["MTG_Actions"]["2"]["MTG_ActionOwnerUID"]==licensing_uid
    assert result["MTG_Actions"]["1"]["MTG_ActionOwnerUID"]==""
    assert question2 not in questions
    assert question1 in questions
    assert intent=="resolved" and pending is None
    assert "mgr.licensing" in reply


@pytest.mark.parametrize("typed",["mgr .licensing","mgr. licensing","mgr . licensing","MGR .LICENSING"])
def test_normalize_dotted_username_spacing(typed):
    assert resolution.normalize_text(typed)=="mgr.licensing"


def test_spoken_dotted_username_without_dot_is_unique_alias():
    scope=scope_with_people()
    uid="c"*32
    scope["directory"][uid]={"active":True,"username":"mgr.licensing","name":"مدیر مجوزات"}
    assert resolution.unique_person("mgr licensing",scope["directory"])==uid


def test_finance_manager_role_alias_resolves_current_action_without_model(pack,monkeypatch):
    scope=scope_with_people()
    finance_uid="f"*32
    scope["directory"][finance_uid]={
        "active":True,
        "username":"mgr.finance",
        "name":"کاربر مالی",
        "unit":"مالی",
        "position":"مدیر مالی",
    }
    values=minutes_values()
    values["MTG_Actions"]["2"]={
        "MTG_ActionNo":"A-002",
        "MTG_ActionDescription":"تکمیل مدارک",
        "MTG_ActionOwnerUID":"a"*32,
        "MTG_persiandate_ActionDueDateTime":"1405/07/18",
        "MTG_ActionDecisionNo":"D-001",
    }
    values["MTG_Actions"]["3"]={
        "MTG_ActionNo":"A-003",
        "MTG_ActionDescription":"تهیه برنامه پرداخت ارزی هفتگی",
        "MTG_ActionOwnerUID":"",
        "MTG_ActionOwnerPosition":"مدیر مالی",
        "MTG_persiandate_ActionDueDateTime":"1405/07/18",
        "MTG_ActionDecisionNo":"D-001",
    }
    history=[{"role":"assistant","text":"مسئول اصلی اقدام A-003 «تهیه برنامه پرداخت ارزی هفتگی» را مشخص کنید."}]
    monkeypatch.setattr(runtime,"extract",lambda *a,**kw:pytest.fail("known finance manager must not call model"))
    result,questions,reply,intent,pending=runtime.converse(
        "مدیر مالی",task(pack,"minutes"),values,scope,
        questions=["مسئول اصلی اقدام A-003 را مشخص کنید."],
        history=history,
    )
    assert result["MTG_Actions"]["3"]["MTG_ActionOwnerUID"]==finance_uid
    assert intent=="resolved" and pending is None
    assert "mgr.finance" in reply


def test_compact_persian_role_alias_is_exact_and_unique():
    directory={
        "f"*32:{"active":True,"username":"mgr.finance","unit":"مالی","position":"مدیر مالی"},
        "x"*32:{"active":True,"username":"finance01","unit":"مالی","position":"کارشناس مالی"},
    }
    assert resolution.unique_person("مدیرمالی",directory)=="f"*32
    assert resolution.unique_person("مدیر مالی",directory)=="f"*32


def test_manager_alias_strips_organizational_prefixes():
    directory={
        "f"*32:{"active":True,"username":"mgr.finance","unit":"امور مالی","position":""},
        "x"*32:{"active":True,"username":"finance01","unit":"امور مالی","position":"کارشناس مالی"},
    }
    assert resolution.unique_person("مدیر مالی",directory)=="f"*32


def test_stale_a_dash_owner_question_is_removed_after_resolution():
    scope=scope_with_people()
    values=minutes_values()
    values["MTG_Actions"]["6"]={
        "MTG_ActionNo":"A-006",
        "MTG_ActionDescription":"پیگیری لجستیک",
        "MTG_ActionOwnerUID":"",
        "MTG_persiandate_ActionDueDateTime":"1405/07/25",
        "MTG_ActionDecisionNo":"D-001",
    }
    pending={
        "field_path":"MTG_Actions.6.MTG_ActionOwnerUID",
        "question":"منظورتان از logestic کدام کاربر است؟ آیا مسئول اقدام A-006 همان logistics01 است؟",
    }
    questions=[
        "منظورتان از logestic کدام کاربر است؟ آیا مسئول اقدام A-006 همان logistics01 است؟"
    ]
    remaining=resolution._remove_resolved_questions(questions,pending)
    assert remaining==[]


def test_strict_identity_evidence_does_not_match_manager_from_unit_only():
    directory={
        "m"*32:{"active":True,"username":"mgr.commercial","name":"مدیر بازرگانی","unit":"بازرگانی","position":"مدیر بازرگانی"},
        "e"*32:{"active":True,"username":"commercial01","name":"کارشناس بازرگانی","unit":"بازرگانی","position":"کارشناس بازرگانی"},
    }
    assert resolution.strict_identity_mentions("کارشناس بازرگانی",directory)==["e"*32]
    assert resolution.strict_identity_mentions("مدیر بازرگانی",directory)==["m"*32]


def test_model_uid_evidence_cannot_map_expert_role_to_manager_by_unit_only():
    manager_uid="m"*32
    expert_uid="e"*32
    directory={
        manager_uid:{"active":True,"username":"mgr.commercial","name":"مدیر بازرگانی","unit":"بازرگانی","position":"مدیر بازرگانی"},
        expert_uid:{"active":True,"username":"commercial01","name":"کارشناس بازرگانی","unit":"بازرگانی","position":"کارشناس بازرگانی"},
    }
    spec={"label":"مسئول اصلی","type":"suggest","options":[]}
    resolved,issues=runtime.resolve_extracted_people(
        "MTG_ActionOwnerUID",manager_uid,spec,directory,evidence="کارشناس بازرگانی"
    )
    assert resolved==""
    assert issues
    resolved2,issues2=runtime.resolve_extracted_people(
        "MTG_ActionOwnerUID",expert_uid,spec,directory,evidence="کارشناس بازرگانی"
    )
    assert resolved2==expert_uid
    assert not issues2


def test_manager_logistics_never_resolves_to_logistics_expert():
    expert_uid="l"*32
    directory={
        expert_uid:{
            "active":True,
            "username":"logistics01",
            "name":"کارشناس لجستیک",
            "unit":"لجستیک",
            "position":"کارشناس لجستیک",
        }
    }
    assert resolution.unique_person("مدیر لجستیک",directory) is None
    spec={"label":"مسئول اصلی","type":"suggest","options":[]}
    resolved,issues=runtime.resolve_extracted_people(
        "MTG_ActionOwnerUID",expert_uid,spec,directory,evidence="منظورم مدیر لجستیک هست"
    )
    assert resolved==""
    assert issues


def test_slash_label_action_owner_question_targets_row():
    question="اقدامات مصوب / 1 / مسئول اصلی: نام یا سمت دقیق را بگویید."
    assert resolution._question_targets_path(
        question,"MTG_Actions.1.MTG_ActionOwnerUID")
    assert not resolution._question_targets_path(
        question,"MTG_Actions.2.MTG_ActionOwnerUID")
