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


def minutes_values(participants):
    return {
        "MTG_MeetingTitle": "بررسی وضعیت AVAN",
        "MTG_MeetingHeld": "",
        "MTG_MeetingDiscussionSummary": "جمع‌بندی توسعه و تحویل",
        "MTG_MeetingEndDateTime": "1405/07/20",
        "MTG_PlannedActionEndTime": "17:00",
        "MTG_Participants": participants,
        "MTG_Agenda": {
            "1": {"MTG_AgendaTitle": "وضعیت توسعه AVAN"},
            "2": {"MTG_AgendaTitle": "اتصال ProcessMaker"},
            "3": {"MTG_AgendaTitle": "برنامه فازبندی"},
            "4": {"MTG_AgendaTitle": "نیازمندی بازرگانی"},
            "5": {"MTG_AgendaTitle": "برنامه تحویل"},
        },
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
        text, task(pack, "minutes"), values, s, questions=[]
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
        task(pack, "minutes"),
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
        task(pack, "minutes"),
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
        task(pack, "minutes"),
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
        task(pack, "minutes"),
        s,
    )
    assert result["intent"] == "question"
    assert not result["values"].get("MTG_Actions")
    assert "هیچ شرکت‌کننده فعال" in result["reply"]
