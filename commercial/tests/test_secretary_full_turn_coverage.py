"""Regression coverage for dense invitation turns from the AVAN owner."""
import copy,json
from types import SimpleNamespace
import pytest

from commercial import secretary_runtime as runtime
from commercial import secretary_coverage as coverage
from commercial import secretary_time
from commercial.tests.test_secretary_inbox import task
from commercial.tests.test_secretary_workflow import S


NOTES="""شماره جلسه رو خودت تعیین کن اخرین شماره جلسه رو به علاوه یک کن
برای تاریخ 16 مهر 1405 ساعت 10:00 یک جلسه با عنوان «بررسی برنامه توسعه و استقرار AVAN» در اتاق جلسات طبقه 6 ساختمان مرکزی جردن برگزار کن.

هدف جلسه این است که وضعیت توسعه AVAN، مشکلات فعلی اتصال ProcessMaker و برنامه تحویل نسخه عملیاتی بررسی شود.

رئیس جلسه ceo باشد و دبیر جلسه administrator باشد.

شرکت‌کنندگان:
Administrator سمت مدیریت سامانه
Ceo مدیریت عامل
mgr.strategy به سمت مدیریت استراتژی
mgr.commercial به سمت مدیریت بازرگانی
mgr.foreign به سمت مدیر خرید خارجی
mgr.finance به سمت مدیر مالی
mgr.legal به سمت مدیر حقوقی
mgr.sales به سمت مدیر فروش
حضور همه واجب و همه به عنوان عضو هستند

دستور جلسه:
1- administrator وضعیت فعلی AVAN و دبیر هوشمند را در مدت 25 دقیقه ارائه کند. اقدام قبلیش به خودش مربوطه در خصوص توسعه بوده و موعدش 16 مهر 1405
2- mgr.strategy برنامه فازبندی توسعه را در مدت 15 دقیقه بررسی کند.
3- mgr.commercial نیازمندی‌های واحد بازرگانی را در مدت 10 دقیقه اعلام کند.
4- mgr.foreign مشکلات فرایند خرید خارجی را در مدت 10 دقیقه توضیح دهد.
5- mgr.finance ملاحظات مالی پروژه را در مدت 10 دقیقه بیان کند.

مدت برنامه‌ریزی‌شده جلسه تا تاریخ روز 26 مهر 1506 ساعت 17 باشد
"""


USERNAMES=[
    "administrator","ceo","mgr.strategy","mgr.commercial",
    "mgr.foreign","mgr.finance","mgr.legal","mgr.sales",
]


def dense_scope():
    scope=copy.deepcopy(S)
    scope["directory"]={}
    for i,username in enumerate(USERNAMES,1):
        uid=f"{i:032x}"
        scope["directory"][uid]={
            "active":True,
            "username":username,
            "name":username,
            "unit":"",
        }
    return scope


def uid(scope,username):
    return next(k for k,v in scope["directory"].items() if v["username"]==username)


def full_values(scope):
    participants={}
    positions=[
        "مدیریت سامانه","مدیریت عامل","مدیریت استراتژی","مدیریت بازرگانی",
        "مدیر خرید خارجی","مدیر مالی","مدیر حقوقی","مدیر فروش",
    ]
    for i,username in enumerate(USERNAMES,1):
        participants[str(i)]={
            "MTG_ParticipantUserUID":uid(scope,username),
            "MTG_ParticipantPosition":positions[i-1],
            "MTG_ParticipantRole":"Member",
            "MTG_ParticipantRequired":"1",
        }
    agenda_titles=[
        "وضعیت فعلی AVAN و دبیر هوشمند",
        "برنامه فازبندی توسعه",
        "نیازمندی‌های واحد بازرگانی",
        "مشکلات فرایند خرید خارجی",
        "ملاحظات مالی پروژه",
    ]
    presenters=["administrator","mgr.strategy","mgr.commercial","mgr.foreign","mgr.finance"]
    minutes=["25","15","10","10","10"]
    agenda={}
    for i in range(1,6):
        agenda[str(i)]={
            "MTG_AgendaNo":str(i),
            "MTG_AgendaTitle":agenda_titles[i-1],
            "MTG_AgendaPresenterUID":uid(scope,presenters[i-1]),
            "MTG_AgendaPlannedMinutes":minutes[i-1],
        }
    agenda["1"].update({
        "MTG_ExistingActionText":"توسعه",
        "MTG_ExistingOwnerUID":uid(scope,"administrator"),
        "MTG_persiandate_ExistingDueDate":"1405/07/16",
    })
    return {
        "MTG_MeetingTitle":"بررسی برنامه توسعه و استقرار AVAN",
        "MTG_Objective":"وضعیت توسعه AVAN، مشکلات فعلی اتصال ProcessMaker و برنامه تحویل نسخه عملیاتی بررسی شود.",
        "MTG_Location":"اتاق جلسات طبقه 6 ساختمان مرکزی جردن",
        "MTG_MeetingStartDateTime":"1405/07/16",
        "MTG_MeetingStartTime":"10:00",
        "MTG_ChairUserUID":uid(scope,"ceo"),
        "MTG_SecretaryUserUID":uid(scope,"administrator"),
        "MTG_Participants":participants,
        "MTG_Agenda":agenda,
    }


def assignments_for(values):
    quotes={
        "MTG_MeetingTitle":"با عنوان «بررسی برنامه توسعه و استقرار AVAN»",
        "MTG_Objective":"هدف جلسه این است که وضعیت توسعه AVAN، مشکلات فعلی اتصال ProcessMaker و برنامه تحویل نسخه عملیاتی بررسی شود.",
        "MTG_Location":"در اتاق جلسات طبقه 6 ساختمان مرکزی جردن برگزار کن",
        "MTG_MeetingStartDateTime":"برای تاریخ 16 مهر 1405 ساعت 10:00",
        "MTG_MeetingStartTime":"ساعت 10:00",
        "MTG_ChairUserUID":"رئیس جلسه ceo باشد",
        "MTG_SecretaryUserUID":"دبیر جلسه administrator باشد",
        "MTG_Participants":"شرکت‌کنندگان:",
        "MTG_Agenda":"دستور جلسه:",
    }
    return [
        runtime.legacy.Assignment(field=field,value_json=json.dumps(value,ensure_ascii=False),quote=quotes[field])
        for field,value in values.items()
    ]


def test_dense_invitation_goes_to_full_extraction_not_temporal(pack,monkeypatch):
    scope=dense_scope();values=full_values(scope)
    monkeypatch.setattr(secretary_time,"apply",lambda *a,**kw:pytest.fail("dense invitation must not terminate in temporal.resolve"))
    monkeypatch.setattr(runtime,"extract",lambda *a,**kw:(copy.deepcopy(values),[],"همه اطلاعات قابل استخراج پیام ثبت شد.","update"))
    result=runtime.converse(NOTES,task(pack,"invitation"),{},scope)
    assert result.receipt["tool"]=="draft.extract"
    assert result[0]["MTG_MeetingTitle"]=="بررسی برنامه توسعه و استقرار AVAN"
    assert len(result[0]["MTG_Participants"])==8
    assert len(result[0]["MTG_Agenda"])==5


def test_dense_invitation_is_detected_as_compound(pack):
    assert coverage.is_compound_invitation(NOTES,task(pack,"invitation"))


def test_coverage_detects_every_major_omission(pack):
    scope=dense_scope();t=task(pack,"invitation")
    values={"MTG_MeetingStartDateTime":"1405/07/16"}
    assignments=[runtime.legacy.Assignment(
        field="MTG_MeetingStartDateTime",value_json='"1405/07/16"',quote="16 مهر 1405")]
    issues=coverage.coverage_issues(NOTES,t,values,assignments,scope["directory"])
    text="\n".join(issues)
    assert "عنوان جلسه" in text
    assert "مکان جلسه" in text
    assert "رئیس جلسه" in text
    assert "دبیر جلسه" in text
    assert "شرکت‌کننده" in text
    assert "دستور جلسه" in text


def test_complete_dense_invitation_satisfies_coverage(pack):
    scope=dense_scope();values=full_values(scope)
    issues=coverage.coverage_issues(
        NOTES,task(pack,"invitation"),values,assignments_for(values),scope["directory"])
    assert issues==[]


def test_model_partial_first_answer_is_retried_until_full_coverage(pack):
    scope=dense_scope();values=full_values(scope);calls=[]
    partial=runtime.ConversationExtraction(
        intent="update",reply="تاریخ ثبت شد.",
        assignments=[runtime.legacy.Assignment(
            field="MTG_MeetingStartDateTime",value_json='"1405/07/16"',quote="16 مهر 1405")],
        questions=[])
    complete=runtime.ConversationExtraction(
        intent="update",reply="همه اطلاعات قابل استخراج پیام ثبت شد.",
        assignments=assignments_for(values),questions=[])
    def parse(**kwargs):
        calls.append(json.loads(kwargs["input"][1]["content"]))
        return SimpleNamespace(status="completed",output_parsed=partial if len(calls)==1 else complete)
    client=SimpleNamespace(responses=SimpleNamespace(parse=parse))
    extracted,questions,reply,intent=runtime.extract(
        NOTES,task(pack,"invitation"),{},scope,client=client,model="fixture",with_reply=True)
    assert len(calls)==2
    assert calls[1]["coverage_failures"]
    assert extracted["MTG_MeetingTitle"]=="بررسی برنامه توسعه و استقرار AVAN"
    assert len(extracted["MTG_Participants"])==8
    assert len(extracted["MTG_Agenda"])==5
    assert questions==[]
    assert intent=="update"


def test_coverage_requires_member_required_position_presenter_and_minutes(pack):
    scope=dense_scope();values=full_values(scope)
    broken=copy.deepcopy(values)
    broken["MTG_Participants"]["3"].pop("MTG_ParticipantPosition")
    broken["MTG_Participants"]["4"]["MTG_ParticipantRole"]="Guest"
    broken["MTG_Participants"]["5"]["MTG_ParticipantRequired"]="0"
    broken["MTG_Agenda"]["2"].pop("MTG_AgendaPresenterUID")
    broken["MTG_Agenda"]["3"].pop("MTG_AgendaPlannedMinutes")
    issues=coverage.coverage_issues(
        NOTES,task(pack,"invitation"),broken,assignments_for(values),scope["directory"])
    text="\n".join(issues)
    assert "سمت" in text
    assert "عضو" in text
    assert "الزام حضور" in text
    assert "ارائه‌دهنده" in text
    assert "مدت دستور جلسه" in text
