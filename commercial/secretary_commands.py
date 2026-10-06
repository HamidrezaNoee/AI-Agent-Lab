"""Explicit agentic commands for Smart Secretary meeting minutes.

This layer executes only user-requested draft operations that are safe to resolve
without asking the LLM to guess ProcessMaker identities. It is intentionally
narrow: batch action generation is allowed only when the user explicitly asks
AVAN to create/assign actions for meeting attendees.
"""
from __future__ import annotations

import copy
import hashlib
import random
import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import jdatetime

from . import secretary_resolution as resolution

_NUMBER_WORDS = {
    "یک": 1, "یکی": 1, "دو": 2, "سه": 3, "چهار": 4, "پنج": 5,
    "شش": 6, "هفت": 7, "هشت": 8, "نه": 9, "ده": 10,
    "یازده": 11, "دوازده": 12, "سیزده": 13, "چهارده": 14, "پانزده": 15,
    "شانزده": 16, "هفده": 17, "هجده": 18, "نوزده": 19, "بیست": 20,
}
_ACTION_NOUNS = ("اقدام", "تسک", "task")
_ACTION_VERBS = (
    "ایجاد", "بساز", "ساخت", "تعریف", "اختصاص", "assign", "اساین",
    "بذار", "قرار بده", "ثبت کن", "ایجاد کن",
)
_RANDOM_WORDS = ("رندوم", "تصادفی", "random")
_ALL_ATTENDEE_PHRASES = (
    "هر کسی که تو جلسه شرکت کرده",
    "هر کسی که توی جلسه شرکت کرده",
    "هر کسی که در جلسه شرکت کرده",
    "هر کس که تو جلسه شرکت کرده",
    "هر کس که توی جلسه شرکت کرده",
    "هر کس که در جلسه شرکت کرده",
    "همه حاضرین",
    "تمام حاضرین",
    "همه افراد حاضر",
    "تمام افراد حاضر",
    "برای هر حاضر",
    "برای همه حاضر",
)
_HELD_PHRASES = (
    "جلسه تشکیل شده",
    "جلسه تشکیل شد",
    "جلسه برگزار شده",
    "جلسه برگزار شد",
    "وضعیت جلسه تشکیل شده",
    "وضعیت جلسه تشکیل شد",
)
_TEMPLATES = (
    "پیگیری موارد باز و ارائه نتیجه درباره «{topic}»",
    "بررسی وضعیت و ارائه گزارش جمع‌بندی درباره «{topic}»",
    "تهیه فهرست اقدامات اجرایی مرتبط با «{topic}»",
    "هماهنگی موارد مرتبط و گزارش موانع درباره «{topic}»",
    "بررسی ریسک‌ها و پیشنهاد گام بعدی برای «{topic}»",
)


def _rows(value):
    if value in (None, ""):
        return []
    if isinstance(value, list):
        return [(str(i + 1), row) for i, row in enumerate(value) if isinstance(row, dict)]
    if isinstance(value, dict):
        keys = sorted(value, key=lambda x: int(x) if str(x).isdigit() else 10**9)
        return [(str(key), value[key]) for key in keys if isinstance(value[key], dict)]
    return []


def _number_after(pattern, text):
    match = re.search(pattern + r"\s*(\d+)", text)
    if match:
        return int(match.group(1))
    match = re.search(pattern + r"\s*(" + "|".join(map(re.escape, _NUMBER_WORDS)) + r")", text)
    return _NUMBER_WORDS.get(match.group(1)) if match else None


def _requested_count(text):
    match = re.search(r"\b(\d+)\s*نفر\b", text)
    if match:
        return int(match.group(1))
    match = re.search(r"\b(" + "|".join(map(re.escape, _NUMBER_WORDS)) + r")\s*نفر\b", text)
    return _NUMBER_WORDS.get(match.group(1)) if match else None


def _due_days(text):
    match = re.search(r"\b(\d+)\s*روز\b", text)
    if match:
        return int(match.group(1))
    match = re.search(r"\b(" + "|".join(map(re.escape, _NUMBER_WORDS)) + r")\s*روز\b", text)
    return _NUMBER_WORDS.get(match.group(1)) if match else None


def _jalali_after_days(days, now=None):
    instant = now or datetime.now(ZoneInfo("Asia/Tehran"))
    target = instant.date() + timedelta(days=int(days))
    return jdatetime.date.fromgregorian(date=target).strftime("%Y/%m/%d")


def _explicit_command(text):
    normalized = resolution.normalize_text(text)
    return (
        any(noun in normalized for noun in _ACTION_NOUNS)
        and any(verb in normalized for verb in _ACTION_VERBS)
        and (
            any(word in normalized for word in _RANDOM_WORDS)
            or _requested_count(normalized) is not None
            or any(phrase in normalized for phrase in _ALL_ATTENDEE_PHRASES)
        )
    )


def is_explicit_batch_action_command(text, stage="minutes"):
    """Return True only for the narrow, explicit batch-action command surface."""
    return stage == "minutes" and _explicit_command(text)


def _meeting_was_explicitly_held(text):
    normalized = resolution.normalize_text(text)
    return any(phrase in normalized for phrase in _HELD_PHRASES)


def _active_attendees(values, scope):
    directory = scope.get("directory") or {}
    participant_rows = _rows(values.get("MTG_Participants"))
    explicit_status_exists = any(str(row.get("MTG_AttendanceStatus") or "").strip() for _, row in participant_rows)
    result = []
    seen = set()
    for row_number, row in participant_rows:
        uid = str(row.get("MTG_ParticipantUserUID") or "").strip()
        if not uid or uid in seen:
            continue
        person = directory.get(uid) or {}
        if not person.get("active"):
            continue
        status = str(row.get("MTG_AttendanceStatus") or "").strip()
        if explicit_status_exists and status != "Present":
            continue
        # When no attendance status has been captured yet, the minutes participant
        # list is the best available meeting-attendee set. Explicit Absent/Excused
        # rows are never selected once attendance capture has started.
        seen.add(uid)
        result.append((row_number, row, uid, person))
    return result


def _selection(attendees, count, random_requested, seed_material):
    if count is not None:
        count = max(0, min(int(count), len(attendees)))
    else:
        count = len(attendees)
    pool = list(attendees)
    if random_requested and len(pool) > 1:
        seed = int(hashlib.sha256(seed_material.encode("utf-8")).hexdigest(), 16)
        random.Random(seed).shuffle(pool)
    return pool[:count]


def _next_code(rows, field, prefix):
    highest = 0
    for _, row in _rows(rows):
        raw = str(row.get(field) or "")
        match = re.search(re.escape(prefix) + r"\s*-?\s*0*(\d+)", raw, re.I)
        if match:
            highest = max(highest, int(match.group(1)))
    return highest + 1


def _topics(values):
    agenda = []
    for number, row in _rows(values.get("MTG_Agenda")):
        title = str(row.get("MTG_AgendaTitle") or "").strip()
        if title:
            agenda.append((number, title))
    if agenda:
        return agenda
    title = str(values.get("MTG_MeetingTitle") or "موضوع جلسه").strip()
    return [("1", title or "موضوع جلسه")]


def _existing_decisions(values):
    result = []
    for key, row in _rows(values.get("MTG_Decisions")):
        no = str(row.get("MTG_DecisionNo") or "").strip()
        text = str(row.get("MTG_DecisionText") or "").strip()
        if no and text:
            result.append((key, row))
    return result


def _ensure_decisions(values, topics, needed):
    decisions = copy.deepcopy(values.get("MTG_Decisions")) if isinstance(values.get("MTG_Decisions"), dict) else {}
    existing = _existing_decisions({"MTG_Decisions": decisions})
    if existing:
        return decisions, [str(row["MTG_DecisionNo"]) for _, row in existing]

    next_number = _next_code(decisions, "MTG_DecisionNo", "D")
    decision_numbers = []
    topic_count = max(1, min(len(topics), needed))
    for offset in range(topic_count):
        agenda_no, topic = topics[offset % len(topics)]
        no = f"D-{next_number + offset:03d}"
        key = str(max([int(k) for k in decisions if str(k).isdigit()] + [0]) + 1)
        decisions[key] = {
            "MTG_DecisionNo": no,
            "MTG_DecisionAgendaNo": str(agenda_no),
            "MTG_DecisionText": f"پیگیری و ارائه نتیجه درباره «{topic}» در دستور کار قرار گیرد.",
            "MTG_DecisionRationale": "پیش‌نویس خودکار AVAN بر اساس دستور صریح کاربر؛ نیازمند بازبینی پیش از ارسال صورت‌جلسه.",
        }
        decision_numbers.append(no)
    return decisions, decision_numbers


def _position(participant_row, person):
    return str(
        participant_row.get("MTG_ParticipantPosition")
        or person.get("position")
        or person.get("title")
        or ""
    ).strip()


def _person_label(uid, person):
    return str(
        person.get("username")
        or person.get("avan_username")
        or person.get("name")
        or person.get("avan_name")
        or uid
    )


def _prune_questions(questions, values):
    result = []
    held = values.get("MTG_MeetingHeld") == "Held"
    for item in questions or ():
        text = str(item)
        normalized = resolution.normalize_text(text)
        if held and "وضعیت تشکیل جلسه" in normalized:
            continue
        if values.get("MTG_Actions") and (
            "mtg_action" in text.casefold()
            or re.search(r"اقدام\s*\d+", normalized)
        ):
            continue
        result.append(text)
    return result


def apply(text, current, task, scope, *, questions=(), now=None):
    """Apply one explicit batch-action command to a minutes draft.

    Returns None when the message is not a supported explicit command.
    """
    if not is_explicit_batch_action_command(text, task.get("stage")):
        return None

    normalized = resolution.normalize_text(text)
    values = copy.deepcopy(current)
    if _meeting_was_explicitly_held(text):
        values["MTG_MeetingHeld"] = "Held"

    attendees = _active_attendees({**task.get("native", {}), **values}, scope)
    if not attendees:
        return {
            "values": values,
            "questions": list(questions),
            "intent": "question",
            "pending_confirmation": None,
            "reply": "برای ساخت اقدام، هنوز هیچ شرکت‌کننده فعال و قابل انتخابی در اطلاعات جلسه ندارم. ابتدا فهرست شرکت‌کنندگان/وضعیت حضور را تکمیل کنید.",
            "resolution": "batch_actions_no_attendees",
        }

    requested = _requested_count(normalized)
    all_requested = any(phrase in normalized for phrase in _ALL_ATTENDEE_PHRASES)
    if requested is None and not all_requested:
        requested = len(attendees)

    random_requested = any(word in normalized for word in _RANDOM_WORDS)
    seed_material = "|".join([
        str(values.get("MTG_MeetingNo") or ""),
        str(values.get("MTG_MeetingTitle") or ""),
        normalized,
        ",".join(uid for _, _, uid, _ in attendees),
    ])
    selected = _selection(attendees, requested, random_requested, seed_material)
    if not selected:
        return None

    days = _due_days(normalized)
    due_date = _jalali_after_days(days, now=now) if days is not None else ""
    topics = _topics({**task.get("native", {}), **values})
    had_decisions = bool(_existing_decisions(values))
    decisions, decision_numbers = _ensure_decisions(values, topics, len(selected))
    values["MTG_Decisions"] = decisions

    actions = copy.deepcopy(values.get("MTG_Actions")) if isinstance(values.get("MTG_Actions"), dict) else {}
    next_action = _next_code(actions, "MTG_ActionNo", "A")
    created = []
    for offset, (_, participant, uid, person) in enumerate(selected):
        topic_no, topic = topics[offset % len(topics)]
        template_index = offset
        if random_requested:
            digest = hashlib.sha256((seed_material + "|" + uid + "|" + str(offset)).encode("utf-8")).digest()
            template_index = digest[0] % len(_TEMPLATES)
        description = _TEMPLATES[template_index % len(_TEMPLATES)].format(topic=topic)
        decision_no = decision_numbers[offset % len(decision_numbers)]
        key = str(max([int(k) for k in actions if str(k).isdigit()] + [0]) + 1)
        action_no = f"A-{next_action + offset:03d}"
        row = {
            "MTG_ActionDecisionNo": decision_no,
            "MTG_ActionNo": action_no,
            "MTG_ActionDescription": description,
            "MTG_ActionOwnerUID": uid,
            "MTG_ActionOwnerPosition": _position(participant, person),
            "MTG_persiandate_ActionDueDateTime": due_date,
            "MTG_ActionPriority": "Normal",
        }
        actions[key] = row
        created.append((action_no, _person_label(uid, person), description))
    values["MTG_Actions"] = actions

    requested_count = requested if requested is not None else len(selected)
    shortage = requested_count is not None and requested_count > len(selected)
    mode = "به‌صورت انتخاب خودکار از حاضرین" if random_requested else "از حاضرین جلسه"
    reply = f"{len(created)} اقدام {mode} به پیش‌نویس اضافه شد."
    if days is not None:
        reply += f" مهلت همه اقدامات {days} روز از امروز، یعنی {due_date}، ثبت شد."
    if shortage:
        reply += f" فقط {len(selected)} شرکت‌کننده واجد شرایط در جلسه موجود بود؛ بیشتر از این تعداد انتخاب نشد."
    if not had_decisions:
        reply += " برای حفظ ارتباط معتبر اقدام‌ها با ProcessMaker، مصوبه‌های مرتبط نیز به‌صورت پیش‌نویس ساخته شدند."
    reply += "\n" + "\n".join(
        f"{action_no} · {owner}: {description}" for action_no, owner, description in created
    )
    reply += "\n\nاین‌ها پیش‌نویس هستند و قبل از ارسال صورت‌جلسه قابل ویرایش‌اند."

    return {
        "values": values,
        "questions": _prune_questions(questions, values),
        "intent": "resolved",
        "pending_confirmation": None,
        "reply": reply,
        "resolution": "batch_actions",
        "created_actions": len(created),
    }
