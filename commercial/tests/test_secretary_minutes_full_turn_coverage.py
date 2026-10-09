"""Regression tests for dense minutes turns: one message must be fully consumed."""
import copy,json
from types import SimpleNamespace
import pytest

from commercial import secretary_runtime as runtime
from commercial import secretary_coverage as coverage
from commercial import secretary_time
from commercial.tests.test_secretary_inbox import task
from commercial.tests.test_secretary_workflow import S


NOTES="""جلسه تشکیل شد

شرح مذاکرات : جلسه خوب بود و نرم فازار خوب بود

موضوعات خارچ از دستور : بررسی خرید api بود

مصوبات

1- برنامه استراتژی تدوین شود
2- برنامه فروش ساخته شود
3- برنامه خرید خارجی مصوب شود
4- برنامه مالی مصوب شود

اثدامات

مصوبه یک با مدیر استراتژی تا تاریخ 20 مهر وقت داره که تدوین کنه
مصوبه 2 با مدیر فروش که بتونه برنامه فروش رو بسازه تا تاریخ 20 مهر
مصوبه 2 برای مدیر حقوقی هم هست که برنامه فروش رو رریس و تایید کنه تا تاریخ 22 مهر
مصوبه 3 برای مدیر بازرگانی که بتونه سخت افزار بیاره از خارج از کشور تا تاریخ 25 مهر
مصوبه کار هم برای مدیر مالی که برنامه پرداخت مصوب کنه تا تاریخ 20 مهر

اولیت همه اقدامات بالاست .
"""

DECISIONS_QUOTE="""مصوبات

1- برنامه استراتژی تدوین شود
2- برنامه فروش ساخته شود
3- برنامه خرید خارجی مصوب شود
4- برنامه مالی مصوب شود"""

ACTIONS_QUOTE="""اثدامات

مصوبه یک با مدیر استراتژی تا تاریخ 20 مهر وقت داره که تدوین کنه
مصوبه 2 با مدیر فروش که بتونه برنامه فروش رو بسازه تا تاریخ 20 مهر
مصوبه 2 برای مدیر حقوقی هم هست که برنامه فروش رو رریس و تایید کنه تا تاریخ 22 مهر
مصوبه 3 برای مدیر بازرگانی که بتونه سخت افزار بیاره از خارج از کشور تا تاریخ 25 مهر
مصوبه کار هم برای مدیر مالی که برنامه پرداخت مصوب کنه تا تاریخ 20 مهر"""


PEOPLE=[
    ("mgr.strategy","مدیر استراتژی","استراتژی"),
    ("mgr.sales","مدیر فروش","فروش"),
    ("mgr.legal","مدیر حقوقی","حقوقی"),
    ("mgr.commercial","مدیر بازرگانی","بازرگانی"),
    ("mgr.finance","مدیر مالی","مالی"),
]


def minutes_scope():
    scope=copy.deepcopy(S)
    scope["directory"]={}
    for i,(username,position,unit) in enumerate(PEOPLE,1):
        scope["directory"][f"{i:032x}"]={
            "active":True,
            "username":username,
            "name":position,
            "position":position,
            "unit":unit,
        }
    return scope


def uid(scope,username):
    return next(k for k,v in scope["directory"].items() if v["username"]==username)


def final_values(scope):
    decisions={
        "1":{"MTG_DecisionNo":"D-001","MTG_DecisionText":"برنامه استراتژی تدوین شود"},
        "2":{"MTG_DecisionNo":"D-002","MTG_DecisionText":"برنامه فروش ساخته شود"},
        "3":{"MTG_DecisionNo":"D-003","MTG_DecisionText":"برنامه خرید خارجی مصوب شود"},
        "4":{"MTG_DecisionNo":"D-004","MTG_DecisionText":"برنامه مالی مصوب شود"},
    }
    specs=[
        ("D-001","تدوین برنامه استراتژی","mgr.strategy","مدیر استراتژی","1405/07/20"),
        ("D-002","ساخت برنامه فروش","mgr.sales","مدیر فروش","1405/07/20"),
        ("D-002","بازبینی و تایید برنامه فروش","mgr.legal","مدیر حقوقی","1405/07/22"),
        ("D-003","تهیه سخت افزار از خارج از کشور","mgr.commercial","مدیر بازرگانی","1405/07/25"),
        ("D-004","تصویب برنامه پرداخت","mgr.finance","مدیر مالی","1405/07/20"),
    ]
    actions={}
    for i,(decision,desc,username,position,due) in enumerate(specs,1):
        actions[str(i)]={
            "MTG_ActionDecisionNo":decision,
            "MTG_ActionNo":f"A-{i:03d}",
            "MTG_ActionDescription":desc,
            "MTG_ActionOwnerUID":uid(scope,username),
            "MTG_ActionOwnerPosition":position,
            "MTG_persiandate_ActionDueDateTime":due,
            "MTG_ActionPriority":"High",
        }
    return {
        "MTG_MeetingHeld":"Held",
        "MTG_NotHeldReason":"",
        "MTG_MeetingDiscussionSummary":"جلسه خوب بود و نرم فازار خوب بود",
        "MTG_ParkingLot":"بررسی خرید api بود",
        "MTG_Decisions":decisions,
        "MTG_Actions":actions,
    }


def model_assignments(scope,complete=True):
    values=final_values(scope)
    # Leave system identifiers/global priority to deterministic AVAN defaults.
    decisions=copy.deepcopy(values["MTG_Decisions"])
    for row in decisions.values():row.pop("MTG_DecisionNo")
    actions=copy.deepcopy(values["MTG_Actions"])
    for row in actions.values():
        # Model may legitimately return the explicit human role rather than a UID.
        row["MTG_ActionOwnerUID"]=row["MTG_ActionOwnerPosition"]
        row.pop("MTG_ActionNo")
        row.pop("MTG_ActionPriority")
        row.pop("MTG_ActionDecisionNo")
    fields=[
        runtime.legacy.Assignment(field="MTG_MeetingHeld",value_json='"Held"',quote="جلسه تشکیل شد"),
        runtime.legacy.Assignment(
            field="MTG_MeetingDiscussionSummary",
            value_json=json.dumps(values["MTG_MeetingDiscussionSummary"],ensure_ascii=False),
            quote="شرح مذاکرات : جلسه خوب بود و نرم فازار خوب بود"),
        runtime.legacy.Assignment(
            field="MTG_ParkingLot",
            value_json=json.dumps(values["MTG_ParkingLot"],ensure_ascii=False),
            quote="موضوعات خارچ از دستور : بررسی خرید api بود"),
        runtime.legacy.Assignment(
            field="MTG_Decisions",value_json=json.dumps(decisions,ensure_ascii=False),quote=DECISIONS_QUOTE),
        runtime.legacy.Assignment(
            field="MTG_Actions",value_json=json.dumps(actions,ensure_ascii=False),quote=ACTIONS_QUOTE),
    ]
    return fields if complete else fields[:1]


def test_dense_minutes_is_detected(pack):
    assert coverage.is_compound_minutes(NOTES,task(pack,"minutes"))
    assert coverage.is_compound_turn(NOTES,task(pack,"minutes"))


def test_dense_minutes_routes_past_status_command_to_full_extraction(pack,monkeypatch):
    scope=minutes_scope();values=final_values(scope)
    monkeypatch.setattr(secretary_time,"apply",lambda *a,**kw:pytest.fail("dense minutes must not stop in temporal.resolve"))
    monkeypatch.setattr(runtime.commands,"apply",lambda *a,**kw:pytest.fail("dense minutes must not stop at meeting_status command"))
    monkeypatch.setattr(runtime,"extract",lambda *a,**kw:(copy.deepcopy(values),[],"همه اطلاعات قابل استخراج صورت‌جلسه ثبت شد.","update"))
    result=runtime.converse(NOTES,task(pack,"minutes"),{},scope)
    assert result.receipt["tool"]=="draft.extract"
    assert result[0]["MTG_MeetingHeld"]=="Held"
    assert result[0]["MTG_MeetingDiscussionSummary"]
    assert len(result[0]["MTG_Decisions"])==4
    assert len(result[0]["MTG_Actions"])==5
    assert "شرح و جمع‌بندی مذاکرات جلسه را مشخص کنید" not in result[2]
    assert "اطلاعات این مرحله کامل است" in result[2]


def test_repeated_dense_minutes_after_status_only_still_extracts_rest(pack,monkeypatch):
    scope=minutes_scope();values=final_values(scope)
    current={"MTG_MeetingHeld":"Held","MTG_NotHeldReason":""}
    monkeypatch.setattr(runtime.commands,"apply",lambda *a,**kw:pytest.fail("status must not terminate repeated dense turn"))
    monkeypatch.setattr(runtime,"extract",lambda *a,**kw:(copy.deepcopy(values),[],"صورت‌جلسه کامل شد.","update"))
    result=runtime.converse(NOTES,task(pack,"minutes"),current,scope)
    assert result.receipt["tool"]=="draft.extract"
    assert result[0]["MTG_MeetingDiscussionSummary"]=="جلسه خوب بود و نرم فازار خوب بود"
    assert len(result[0]["MTG_Actions"])==5


def test_minutes_coverage_detects_partial_status_only(pack):
    scope=minutes_scope()
    values={"MTG_MeetingHeld":"Held"}
    issues=coverage.coverage_issues(
        NOTES,task(pack,"minutes"),values,model_assignments(scope,complete=False),scope["directory"])
    text="\n".join(issues)
    assert "شرح مذاکرات" in text
    assert "موضوعات خارج از دستور" in text
    assert "مصوبات" in text
    assert "اقدامات" in text
    assert "همه مصوبات" in text
    assert "همه اقدامات" in text


def test_minutes_system_defaults_fill_codes_links_unique_owners_and_priority(pack):
    scope=minutes_scope()
    parsed=model_assignments(scope)
    values={}
    for a in parsed:
        value=json.loads(a.value_json)
        value,_=runtime.resolve_extracted_people(
            a.field,runtime.normalize(value),runtime.form(task(pack,"minutes"))[a.field],
            scope["directory"],evidence=a.quote,current=None)
        values[a.field]=value
    values=coverage.apply_system_defaults(NOTES,task(pack,"minutes"),values,scope["directory"])
    assert [x["MTG_DecisionNo"] for _,x in sorted(values["MTG_Decisions"].items())]==[
        "D-001","D-002","D-003","D-004"]
    assert [x["MTG_ActionNo"] for _,x in sorted(values["MTG_Actions"].items())]==[
        "A-001","A-002","A-003","A-004","A-005"]
    assert [x["MTG_ActionDecisionNo"] for _,x in sorted(values["MTG_Actions"].items())]==[
        "D-001","D-002","D-002","D-003","D-004"]
    assert all(x["MTG_ActionPriority"]=="High" for x in values["MTG_Actions"].values())
    assert values["MTG_Actions"]["1"]["MTG_ActionOwnerUID"]==uid(scope,"mgr.strategy")
    assert values["MTG_Actions"]["5"]["MTG_ActionOwnerUID"]==uid(scope,"mgr.finance")


def test_minutes_partial_model_answer_retries_for_full_coverage(pack):
    scope=minutes_scope();calls=[];budgets=[]
    partial=runtime.ConversationExtraction(
        intent="update",reply="وضعیت جلسه ثبت شد.",
        assignments=model_assignments(scope,complete=False),questions=[])
    complete=runtime.ConversationExtraction(
        intent="update",reply="تمام اطلاعات صریح صورت‌جلسه ثبت شد.",
        assignments=model_assignments(scope,complete=True),questions=[])
    def parse(**kwargs):
        calls.append(json.loads(kwargs["input"][1]["content"]))
        budgets.append(kwargs["max_output_tokens"])
        return SimpleNamespace(status="completed",output_parsed=partial if len(calls)==1 else complete)
    values,questions,reply,intent=runtime.extract(
        NOTES,task(pack,"minutes"),{},scope,
        client=SimpleNamespace(responses=SimpleNamespace(parse=parse)),
        model="fixture",with_reply=True)
    assert len(calls)==2
    assert budgets==[7000,7000]
    assert calls[1]["coverage_failures"]
    assert values["MTG_MeetingHeld"]=="Held"
    assert values["MTG_ParkingLot"]=="بررسی خرید api بود"
    assert len(values["MTG_Decisions"])==4
    assert len(values["MTG_Actions"])==5
    assert values["MTG_Actions"]["5"]["MTG_ActionDecisionNo"]=="D-004"
    assert all(row["MTG_ActionPriority"]=="High" for row in values["MTG_Actions"].values())
    assert not questions
    assert intent=="update"


def test_minutes_question_misclassification_is_retried(pack):
    scope=minutes_scope()
    wrong=runtime.ConversationExtraction(
        intent="question",
        reply="لطفاً شرح و جمع‌بندی مذاکرات جلسه را مشخص کنید.",
        assignments=[],questions=[])
    complete=runtime.ConversationExtraction(
        intent="update",reply="تمام اطلاعات ثبت شد.",
        assignments=model_assignments(scope),questions=[])
    calls=[]
    def parse(**kwargs):
        calls.append(1)
        return SimpleNamespace(status="completed",output_parsed=wrong if len(calls)==1 else complete)
    values,questions,reply,intent=runtime.extract(
        NOTES,task(pack,"minutes"),{},scope,
        client=SimpleNamespace(responses=SimpleNamespace(parse=parse)),
        model="fixture",with_reply=True)
    assert len(calls)==2
    assert values["MTG_MeetingDiscussionSummary"]
    assert len(values["MTG_Actions"])==5
    assert intent=="update"


def test_real_typos_and_fourth_decision_reference_are_understood(pack):
    scope=minutes_scope()
    contract=coverage.coverage_prompt(NOTES,task(pack,"minutes"),scope["directory"])
    assert contract["decision_count"]==4
    assert contract["action_count"]==5
    assert contract["all_actions_priority"]=="High"
    assert [x["decision_index"] for x in contract["actions"]]==["1","2","2","3","4"]
    assert "موضوعات خارج از دستور" in contract["explicit_fields"]


def test_unique_persian_role_resolves_inside_action_grid(pack):
    scope=minutes_scope()
    spec=runtime.form(task(pack,"minutes"))["MTG_Actions"]
    raw={"1":{
        "MTG_ActionDescription":"تدوین برنامه استراتژی",
        "MTG_ActionOwnerUID":"مدیر استراتژی",
        "MTG_ActionOwnerPosition":"مدیر استراتژی",
    }}
    resolved,questions=runtime.resolve_extracted_people(
        "MTG_Actions",raw,spec,scope["directory"],
        evidence="مصوبه یک با مدیر استراتژی تا تاریخ 20 مهر وقت داره که تدوین کنه",
        current=None)
    assert resolved["1"]["MTG_ActionOwnerUID"]==uid(scope,"mgr.strategy")
    assert questions==[]
