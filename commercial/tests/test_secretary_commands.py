from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from commercial import secretary_commands as commands
from commercial import secretary_runtime as runtime
from commercial.tests.test_secretary_inbox import task


def scope():
    people = {}
    participants = {}
    for i, ch in enumerate("abcdefg", 1):
        uid = ch * 32
        people[uid] = {
            "active": True,
            "name": f"کاربر {i}",
            "username": f"user{i}",
            "position": f"سمت {i}",
        }
        participants[str(i)] = {
            "MTG_ParticipantUserUID": uid,
            "MTG_ParticipantPosition": f"سمت {i}",
            "MTG_AttendanceStatus": "Present" if i <= 6 else "Absent",
        }
    return {
        "tenant_id": "tenant",
        "source_id": "source",
        "external_user_id": "a" * 32,
        "role": "User",
        "license": {"modules": {2}},
        "directory": people,
    }, participants


def minutes_native():
    return {
        "MTG_MeetingTitle": "بررسی وضعیت AVAN",
        "MTG_Agenda": {
            "1": {"MTG_AgendaTitle": "وضعیت توسعه AVAN"},
            "2": {"MTG_AgendaTitle": "اتصال ProcessMaker"},
            "3": {"MTG_AgendaTitle": "برنامه فازبندی"},
            "4": {"MTG_AgendaTitle": "نیازمندی بازرگانی"},
            "5": {"MTG_AgendaTitle": "برنامه تحویل"},
        },
    }


def minutes_values(participants):
    return {
        "MTG_MeetingHeld": "",
        "MTG_MeetingDiscussionSummary": "جمع‌بندی توسعه و تحویل",
        "MTG_MeetingEndDateTime": "1405/07/20",
        "MTG_MeetingEndTime": "16:00",
        "MTG_PlannedActionEndTime": "17:00",
        "MTG_Participants": participants,
        "MTG_Decisions": {},
        "MTG_Actions": {},
    }


def test_explicit_random_five_attendees_creates_complete_actions_without_llm(pack, monkeypatch):
    s, participants = scope()
    values = minutes_values(participants)
    monkeypatch.setattr(
        runtime,
        "extract",
        lambda *a, **kw: pytest.fail("explicit batch command must not call the LLM"),
    )
    monkeypatch.setattr(commands, "_jalali_after_days", lambda days, now=None: "1405/07/18")

    text = (
        "وضعیت جلسه تشکیل شده و پنج نفر رو از کسایی که توی جلسه شرکت کردن "
        "به عنوان اقدام کننده‌ها بذار. براشون یک تسک رندوم assign کن و برای "
        "هر کدومشون از امروز پنج روز بهشون وقت بده."
    )
    result, questions, reply, intent, pending = runtime.converse(
        text, task(pack, "minutes", minutes_native()), values, s, questions=[]
    )

    assert result["MTG_MeetingHeld"] == "Held"
    assert len(result["MTG_Actions"]) == 5
    assert intent == "resolved"
    assert pending is None
    assert "5 اقدام" in reply
    owners = [row["MTG_ActionOwnerUID"] for row in result["MTG_Actions"].values()]
    assert len(set(owners)) == 5
    assert "g" * 32 not in owners
    decision_numbers = {
        row["MTG_DecisionNo"] for row in result["MTG_Decisions"].values()
    }
    for row in result["MTG_Actions"].values():
        assert row["MTG_persiandate_ActionDueDateTime"] == "1405/07/18"
        assert row["MTG_ActionPriority"] == "Normal"
        assert row["MTG_ActionDecisionNo"] in decision_numbers
        assert row["MTG_ActionDescription"]
    assert not any("MTG_ActionOwnerUID" in q for q in questions)


def test_all_attendees_command_uses_every_present_person(pack, monkeypatch):
    s, participants = scope()
    values = minutes_values(participants)
    values["MTG_MeetingHeld"] = "Held"
    monkeypatch.setattr(
        runtime,
        "extract",
        lambda *a, **kw: pytest.fail("all-attendees command must not call the LLM"),
    )
    monkeypatch.setattr(commands, "_jalali_after_days", lambda days, now=None: "1405/07/18")

    result, _, reply, intent, _ = runtime.converse(
        "برای هر کسی که توی جلسه شرکت کرده یک اقدام ایجاد کن و پنج روز مهلت بده.",
        task(pack, "minutes", minutes_native()),
        values,
        s,
    )

    assert intent == "resolved"
    assert len(result["MTG_Actions"]) == 6
    assert {row["MTG_ActionOwnerUID"] for row in result["MTG_Actions"].values()} == {
        ch * 32 for ch in "abcdef"
    }
    assert "6 اقدام" in reply


def test_explicit_attendance_status_never_selects_absent_or_excused(pack):
    s, participants = scope()
    participants["6"]["MTG_AttendanceStatus"] = "Excused"
    values = minutes_values(participants)
    result = commands.apply(
        "پنج نفر از حاضرین را انتخاب کن و برایشان تسک تصادفی ایجاد کن و ۵ روز مهلت بده",
        values,
        task(pack, "minutes", minutes_native()),
        s,
        now=datetime(2026, 10, 6, 9, 0, tzinfo=ZoneInfo("Asia/Tehran")),
    )
    owners = {row["MTG_ActionOwnerUID"] for row in result["values"]["MTG_Actions"].values()}
    assert "f" * 32 not in owners
    assert "g" * 32 not in owners
    assert len(owners) == 5


def test_non_command_question_is_not_interpreted_as_batch_mutation(pack):
    s, participants = scope()
    values = minutes_values(participants)
    assert commands.apply(
        "اقدام‌های جلسه چه کسانی هستند؟",
        values,
        task(pack, "minutes", minutes_native()),
        s,
    ) is None


def test_no_attendee_returns_focused_clarification_without_fabricated_identity(pack):
    s, participants = scope()
    for row in participants.values():
        row["MTG_AttendanceStatus"] = "Absent"
    values = minutes_values(participants)
    result = commands.apply(
        "برای همه حاضرین یک اقدام ایجاد کن و پنج روز مهلت بده",
        values,
        task(pack, "minutes", minutes_native()),
        s,
    )
    assert result["intent"] == "question"
    assert not result["values"].get("MTG_Actions")
    assert "هیچ شرکت‌کننده فعال" in result["reply"]


def test_meeting_held_status_is_resolved_without_llm(pack, monkeypatch):
    s, participants = scope()
    values = minutes_values(participants)
    monkeypatch.setattr(
        runtime,
        "extract",
        lambda *a, **kw: pytest.fail("meeting status must not call the LLM"),
    )
    result, _, reply, intent, _ = runtime.converse(
        "جلسه تشکیل شد",
        task(pack, "minutes", minutes_native()),
        values,
        s,
        questions=["لطفاً وضعیت تشکیل جلسه را مشخص کنید."],
    )
    assert result["MTG_MeetingHeld"] == "Held"
    assert result["MTG_NotHeldReason"] == ""
    assert intent == "resolved"
    assert "جلسه تشکیل شد" in reply


def test_not_held_status_and_reason_are_applied_together(pack, monkeypatch):
    s, participants = scope()
    values = minutes_values(participants)
    monkeypatch.setattr(
        runtime,
        "extract",
        lambda *a, **kw: pytest.fail("meeting status must not call the LLM"),
    )
    result, questions, reply, intent, _ = runtime.converse(
        "جلسه تشکیل نشد به دلیل عدم حضور رئیس جلسه",
        task(pack, "minutes", minutes_native()),
        values,
        s,
        questions=[
            "لطفاً وضعیت تشکیل جلسه را مشخص کنید.",
            "لطفاً علت عدم تشکیل جلسه را مشخص کنید.",
        ],
    )
    assert result["MTG_MeetingHeld"] == "NotHeld"
    assert result["MTG_NotHeldReason"] == "عدم حضور رئیس جلسه"
    assert intent == "resolved"
    assert not questions
    assert "جلسه تشکیل نشد" in reply


def test_assign_action_owners_from_unique_role_or_unit_without_llm(pack, monkeypatch):
    s, participants = scope()
    s["directory"]["a"*32]["position"] = "کارشناس بازرگانی"
    s["directory"]["a"*32]["unit"] = "بازرگانی"
    s["directory"]["b"*32]["position"] = "کارشناس مجوزات"
    s["directory"]["b"*32]["unit"] = "مجوزات"
    values = minutes_values(participants)
    values["MTG_MeetingHeld"] = "Held"
    values["MTG_Decisions"] = {"1":{"MTG_DecisionNo":"D-001","MTG_DecisionText":"پیگیری شود"}}
    values["MTG_Actions"] = {
        "1":{"MTG_ActionNo":"A-001","MTG_ActionDescription":"پیگیری خرید",
             "MTG_ActionOwnerPosition":"کارشناس بازرگانی","MTG_ActionDecisionNo":"D-001",
             "MTG_persiandate_ActionDueDateTime":"1405/07/20"},
        "2":{"MTG_ActionNo":"A-002","MTG_ActionDescription":"تکمیل مجوز",
             "MTG_ActionOwnerPosition":"کارشناس مجوزات","MTG_ActionDecisionNo":"D-001",
             "MTG_persiandate_ActionDueDateTime":"1405/07/20"},
    }
    monkeypatch.setattr(runtime,"extract",lambda *a,**kw:pytest.fail("role assignment must not call the LLM"))
    result,questions,reply,intent,_=runtime.converse(
        "با توجه به سمت‌هایی که در اقدامات گذاشتی آدم‌های مرتبط با اون سمت‌ها رو پیدا کن و بهشون وصل کن",
        task(pack,"minutes",minutes_native()),values,s,
        questions=["مسئول اصلی اقدام A-001 را مشخص کنید.","مسئول اصلی اقدام A-002 را مشخص کنید."],
    )
    assert intent=="resolved"
    assert result["MTG_Actions"]["1"]["MTG_ActionOwnerUID"]=="a"*32
    assert result["MTG_Actions"]["2"]["MTG_ActionOwnerUID"]=="b"*32
    assert not questions
    assert "2 مسئول اقدام" in reply


def test_role_assignment_keeps_ambiguous_matches_unassigned(pack):
    s,participants=scope()
    s["directory"]["a"*32]["unit"]="مجوزات"
    s["directory"]["b"*32]["unit"]="مجوزات"
    values=minutes_values(participants)
    values["MTG_MeetingHeld"]="Held"
    values["MTG_Actions"]={"1":{"MTG_ActionNo":"A-001","MTG_ActionDescription":"پیگیری مجوز","MTG_ActionOwnerPosition":"کارشناس مجوزات"}}
    result=commands.apply("مسئول اقدام را بر اساس سمت افراد مرتبط پیدا کن و بهش وصل کن",
                          values,task(pack,"minutes",minutes_native()),s)
    assert not result["values"]["MTG_Actions"]["1"].get("MTG_ActionOwnerUID")
    assert result["questions"]
    assert "چند کاربر" in result["questions"][0]


def test_batch_command_reuses_existing_unowned_actions_before_creating_new_ones(pack, monkeypatch):
    s,participants=scope()
    values=minutes_values(participants)
    values["MTG_MeetingHeld"]="Held"
    values["MTG_Decisions"]={"1":{"MTG_DecisionNo":"D-001","MTG_DecisionText":"پیگیری شود"}}
    values["MTG_Actions"]={
        str(i):{
            "MTG_ActionNo":f"A-{i:03d}",
            "MTG_ActionDescription":f"اقدام موجود {i}",
            "MTG_ActionDecisionNo":"D-001",
            "MTG_persiandate_ActionDueDateTime":"1405/07/30",
        } for i in range(1,7)
    }
    monkeypatch.setattr(commands,"_jalali_after_days",lambda days,now=None:"1405/07/18")
    result=commands.apply(
        "برای هر کسی که توی جلسه شرکت کرده یک اقدام ایجاد کن و پنج روز مهلت بده",
        values,task(pack,"minutes",minutes_native()),s,
    )
    actions=result["values"]["MTG_Actions"]
    assert len(actions)==6
    assert result["reused_actions"]==6
    assert result["created_actions"]==0
    assert all(row.get("MTG_ActionOwnerUID") for row in actions.values())
    assert all(row["MTG_persiandate_ActionDueDateTime"]=="1405/07/18" for row in actions.values())
    assert "اقدام تکراری نساختم" in result["reply"]


def test_progress_question_reports_human_next_gap_without_llm(pack, monkeypatch):
    s,participants=scope()
    values=minutes_values(participants)
    values["MTG_MeetingHeld"]="Held"
    values["MTG_Decisions"]={"1":{"MTG_DecisionNo":"D-001","MTG_DecisionText":"پیگیری شود"}}
    values["MTG_Actions"]={"1":{
        "MTG_ActionNo":"A-002","MTG_ActionDescription":"تکمیل مدارک",
        "MTG_ActionDecisionNo":"D-001","MTG_persiandate_ActionDueDateTime":"1405/07/25",
    }}
    monkeypatch.setattr(runtime,"extract",lambda *a,**kw:pytest.fail("progress question must not call LLM"))
    result,_,reply,intent,_=runtime.converse(
        "کجا گیریم؟",task(pack,"minutes",minutes_native()),values,s
    )
    assert result==values
    assert intent=="question"
    assert "مسئول اصلی اقدام A-002" in reply
    assert "MTG_ActionOwnerUID" not in reply



def test_minutes_locked_plan_fields_are_not_deterministic_commands(pack):
    s,participants=scope()
    values=minutes_values(participants)
    task_row=task(pack,"minutes",minutes_native())
    assert commands.command_kind("برای ده روز آینده بگذار","minutes",[]) is None
    assert commands.command_kind("ساعت پایان جلسه 17:00","minutes",[]) is None
    assert "MTG_MeetingEndDateTime" not in runtime.FIELDS["minutes"]
    assert "MTG_MeetingEndTime" not in runtime.FIELDS["minutes"]
    assert "MTG_PlannedActionEndTime" not in runtime.FIELDS["minutes"]


def test_minutes_gap_list_never_asks_locked_plan_fields(pack):
    s,participants=scope()
    values=minutes_values(participants)
    values["MTG_MeetingHeld"]="Held"
    values["MTG_MeetingEndDateTime"]=""
    values["MTG_MeetingEndTime"]=""
    values["MTG_PlannedActionEndTime"]=""
    pending=runtime.gaps(values,task(pack,"minutes",minutes_native()))
    fields={x["field"] for x in pending}
    assert "MTG_MeetingEndDateTime" not in fields
    assert "MTG_MeetingEndTime" not in fields
    assert "MTG_PlannedActionEndTime" not in fields


def test_all_present_attendees_can_receive_one_attendance_time_command(pack):
    s,participants=scope()
    values=minutes_values(participants)
    values["MTG_MeetingHeld"]="Held"
    for i,row in values["MTG_Participants"].items():
        row["MTG_AttendanceStatus"]="Present" if i!="3" else "Excused"
        row["MTG_AttendanceTime"]=""
    task_row=task(pack,"minutes",minutes_native())
    result=commands.apply("ساعت حضور همه حاضرها 17:00 بود",values,task_row,s,questions=[
        "ساعت حضور شرکت‌کننده حاضر ردیف 1 را به صورت HH:mm اعلام کنید.",
        "ساعت حضور شرکت‌کننده حاضر ردیف 2 را به صورت HH:mm اعلام کنید.",
    ])
    assert result["resolution"]=="attendance_time"
    assert result["values"]["MTG_Participants"]["1"]["MTG_AttendanceTime"]=="17:00"
    assert result["values"]["MTG_Participants"]["2"]["MTG_AttendanceTime"]=="17:00"
    assert result["values"]["MTG_Participants"]["3"]["MTG_AttendanceTime"]==""
    assert not result["questions"]


def test_all_present_with_time_fills_attendance_in_one_command(pack):
    s,participants=scope()
    values=minutes_values(participants)
    for row in values["MTG_Participants"].values():
        row["MTG_AttendanceStatus"]=""
        row["MTG_AttendanceTime"]=""
    result=commands.apply(
        "همه شرکت‌کنندگان حاضر بودند و ساعت حضور همه 17:00 بود",
        values,task(pack,"minutes",minutes_native()),s,questions=[]
    )
    assert result["resolution"]=="all_present"
    for row in result["values"]["MTG_Participants"].values():
        assert row["MTG_AttendanceStatus"]=="Present"
        assert row["MTG_AttendanceTime"]=="17:00"
