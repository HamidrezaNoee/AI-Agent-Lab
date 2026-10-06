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
_ROLE_ASSIGN_PHRASES = (
    "بر اساس سمت", "براساس سمت", "با توجه به سمت", "از روی سمت",
    "مرتبط با اون سمت", "مرتبط با آن سمت", "آدمهای مرتبط با",
    "آدم های مرتبط با", "افراد مرتبط با", "مسئول ها رو پیدا",
    "مسئول‌ها رو پیدا", "مسئولان را پیدا", "بهشون وصل کن",
    "به آنها وصل کن", "بهشون اختصاص بده",
)
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
_NOT_HELD_PHRASES = (
    "جلسه تشکیل نشد",
    "جلسه تشکیل نشده",
    "جلسه برگزار نشد",
    "جلسه برگزار نشده",
    "وضعیت جلسه تشکیل نشد",
    "وضعیت جلسه تشکیل نشده",
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


def _hour_value(text):
    match=re.search(r"\b(\d{1,2})(?::([0-5]\d))?\b",text)
    if match:
        hour=int(match.group(1));minute=int(match.group(2) or 0)
        if 0<=hour<=23:return hour,minute
    for word,value in _NUMBER_WORDS.items():
        if 1<=value<=12 and re.search(r"\b"+re.escape(word)+r"\b",text):
            return value,0
    return None


def _clock_from_text(text):
    normalized=resolution.normalize_text(text)
    if not any(x in normalized for x in ("ساعت","صبح","ظهر","بعد از ظهر","عصر","شب")):
        return None
    parsed=_hour_value(normalized)
    if not parsed:return None
    hour,minute=parsed
    if any(x in normalized for x in ("بعد از ظهر","عصر","شب")) and 1<=hour<12:hour+=12
    if "ظهر" in normalized and hour==12:hour=12
    if "صبح" in normalized and hour==12:hour=0
    return f"{hour:02d}:{minute:02d}"


def _planning_window_command(text):
    normalized=resolution.normalize_text(text)
    days=_due_days(normalized)
    relative=days is not None and any(x in normalized for x in ("آینده","دیگه","بعد","بگذار","بذار","قرار بده","مهلت"))
    return relative or _clock_from_text(normalized) is not None


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


def _meeting_status(text):
    normalized = resolution.normalize_text(text)
    if any(phrase in normalized for phrase in _NOT_HELD_PHRASES):
        return "NotHeld"
    if any(phrase in normalized for phrase in _HELD_PHRASES):
        return "Held"
    return None


def _role_assignment_command(text):
    normalized = resolution.normalize_text(text)
    return (
        any(phrase in normalized for phrase in _ROLE_ASSIGN_PHRASES)
        and any(word in normalized for word in ("سمت", "مسئول", "اقدام", "مرتبط"))
    )


def command_kind(text, stage="minutes"):
    if stage != "minutes":
        return None
    if _role_assignment_command(text):
        return "role_assignment"
    if _explicit_command(text):
        return "batch_actions"
    if _meeting_status(text):
        return "meeting_status"
    if _planning_window_command(text):
        return "planning_window"
    return None


def _meeting_was_explicitly_held(text):
    return _meeting_status(text) == "Held"


def _not_held_reason(text):
    raw = str(text or "").strip()
    for marker in ("به دلیل", "به علت", "علت:", "علت "):
        if marker in raw:
            reason = raw.split(marker, 1)[1].strip(" .،؛:")
            if reason:
                return reason[:4000]
    return ""


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


def _match_role_candidates(target, directory):
    """Find active people whose unit/title/name best matches an explicit action role."""
    target_norm = resolution.normalize_text(target)
    if not target_norm:
        return []
    target_tokens = {x for x in target_norm.split() if len(x) > 1}
    scored = []
    for uid, person in (directory or {}).items():
        if not person.get("active"):
            continue
        fields = [
            person.get("position"), person.get("title"), person.get("unit"),
            person.get("department"), person.get("department_name"),
            person.get("name"), person.get("display_name"),
            person.get("avan_name"), person.get("username"), person.get("avan_username"),
        ]
        best = 0
        for raw in fields:
            value = resolution.normalize_text(raw)
            if not value:
                continue
            if value == target_norm:
                best = max(best, 100)
                continue
            if value in target_norm or target_norm in value:
                best = max(best, 88)
            tokens = {x for x in value.split() if len(x) > 1}
            common = target_tokens & tokens
            if common:
                coverage = len(common) / max(1, min(len(target_tokens), len(tokens)))
                best = max(best, round(50 + 35 * coverage))
        if best >= 70:
            scored.append((best, str(uid), person))
    scored.sort(key=lambda x: (-x[0], _person_label(x[1], x[2]).casefold(), x[1]))
    if not scored:
        return []
    top = scored[0][0]
    return [row for row in scored if row[0] == top]


def _assign_action_owners_by_role(values, scope):
    actions = copy.deepcopy(values.get("MTG_Actions")) if isinstance(values.get("MTG_Actions"), dict) else {}
    assigned, unresolved = [], []
    for key, row in _rows(actions):
        if row.get("MTG_ActionOwnerUID"):
            continue
        target = str(row.get("MTG_ActionOwnerPosition") or "").strip()
        action_no = str(row.get("MTG_ActionNo") or ("ردیف " + key))
        description = str(row.get("MTG_ActionDescription") or "").strip()
        if not target:
            unresolved.append((action_no, description, "سمت مسئول برای این اقدام ثبت نشده است."))
            continue
        matches = _match_role_candidates(target, scope.get("directory") or {})
        if len(matches) == 1:
            _, uid, person = matches[0]
            row["MTG_ActionOwnerUID"] = uid
            assigned.append((action_no, target, uid, _person_label(uid, person)))
        elif len(matches) > 1:
            names = "، ".join(_person_label(uid, person) for _, uid, person in matches[:5])
            unresolved.append((action_no, description, "برای سمت «" + target + "» چند کاربر هم‌امتیاز پیدا شد: " + names))
        else:
            unresolved.append((action_no, description, "برای سمت «" + target + "» کاربر فعال یکتا پیدا نشد."))
    return actions, assigned, unresolved


def _prune_questions(questions, values):
    result = []
    status = values.get("MTG_MeetingHeld")
    for item in questions or ():
        text = str(item)
        normalized = resolution.normalize_text(text)
        if status in ("Held", "NotHeld") and "وضعیت تشکیل جلسه" in normalized:
            continue
        if status == "NotHeld" and values.get("MTG_NotHeldReason") and (
            "علت عدم تشکیل" in normalized or "mtg_notheldreason" in text.casefold()
        ):
            continue
        if values.get("MTG_MeetingEndDateTime") and (
            "تاریخ پایان برنامه" in normalized or "mtg_meetingenddatetime" in text.casefold()
        ):
            continue
        if values.get("MTG_PlannedActionEndTime") and (
            "ساعت پایان برنامه" in normalized or "mtg_plannedactionendtime" in text.casefold()
        ):
            continue
        if values.get("MTG_Actions") and (
            "mtg_action" in text.casefold()
            or re.search(r"اقدام\s*\d+", normalized)
        ):
            continue
        result.append(text)
    return result


def apply(text, current, task, scope, *, questions=(), now=None):
    """Apply one explicit deterministic command to a minutes draft."""
    kind = command_kind(text, task.get("stage"))
    if not kind:
        return None

    normalized = resolution.normalize_text(text)
    values = copy.deepcopy(current)
    status = _meeting_status(text)
    if status == "Held":
        values["MTG_MeetingHeld"] = "Held"
        values["MTG_NotHeldReason"] = ""
    elif status == "NotHeld":
        values["MTG_MeetingHeld"] = "NotHeld"
        reason = _not_held_reason(text)
        if reason:
            values["MTG_NotHeldReason"] = reason

    if kind == "meeting_status":
        label = "جلسه تشکیل شد" if status == "Held" else "جلسه تشکیل نشد"
        return {
            "values": values,
            "questions": _prune_questions(questions, values),
            "intent": "resolved",
            "pending_confirmation": None,
            "reply": "وضعیت جلسه روی «" + label + "» ثبت شد.",
            "resolution": "meeting_status",
        }

    if kind == "planning_window":
        days=_due_days(normalized)
        clock=_clock_from_text(normalized)
        changed=[]
        if days is not None:
            planned_date=_jalali_after_days(days,now=now)
            values["MTG_MeetingEndDateTime"]=planned_date
            changed.append("تاریخ پایان برنامه‌ریزی روی "+planned_date)
        if clock:
            values["MTG_PlannedActionEndTime"]=clock
            changed.append("ساعت پایان برنامه‌ریزی روی "+clock)
        return {
            "values":values,
            "questions":_prune_questions(questions,values),
            "intent":"resolved",
            "pending_confirmation":None,
            "reply":" و ".join(changed)+" تنظیم شد.",
            "resolution":"planning_window",
        }

    if kind == "role_assignment":
        actions, assigned, unresolved = _assign_action_owners_by_role(values, scope)
        values["MTG_Actions"] = actions
        remaining = _prune_questions(questions, values)
        # Replace stale raw owner questions with focused ambiguity questions only.
        remaining = [
            q for q in remaining
            if "مسئول اصلی اقدام" not in resolution.normalize_text(q)
            and "mtg_actionowneruid" not in str(q).casefold()
        ]
        remaining.extend(reason for _, _, reason in unresolved)
        if assigned:
            lines = [
                action_no + " · " + role + " ← " + person
                for action_no, role, _, person in assigned
            ]
            reply = str(len(assigned)) + " مسئول اقدام با تطبیق سمت/واحد کاربران فعال BPMS ثبت شد.\n" + "\n".join(lines)
        else:
            reply = "برای اقدام‌های بدون مسئول، تطبیق یکتای قابل اتکا از روی سمت/واحد پیدا نشد."
        if unresolved:
            reply += "\n\n" + str(len(unresolved)) + " مورد هنوز مبهم است؛ فقط همین موارد نیاز به تعیین دستی دارند."
        else:
            reply += "\n\nهمه اقدام‌های دارای سمت مشخص، مسئول یکتا گرفتند."
        return {
            "values": values,
            "questions": list(dict.fromkeys(remaining)),
            "intent": "resolved",
            "pending_confirmation": None,
            "reply": reply,
            "resolution": "role_assignment",
            "assigned_owners": len(assigned),
        }

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
    unowned = [key for key,row in _rows(actions) if not row.get("MTG_ActionOwnerUID")]
    changed = []
    created_count = 0
    reused_count = 0
    action_number_cursor = next_action
    for offset, (_, participant, uid, person) in enumerate(selected):
        topic_no, topic = topics[offset % len(topics)]
        template_index = offset
        if random_requested:
            digest = hashlib.sha256((seed_material + "|" + uid + "|" + str(offset)).encode("utf-8")).digest()
            template_index = digest[0] % len(_TEMPLATES)
        generated_description = _TEMPLATES[template_index % len(_TEMPLATES)].format(topic=topic)
        decision_no = decision_numbers[offset % len(decision_numbers)]
        if unowned:
            key = unowned.pop(0)
            row = actions[key]
            reused_count += 1
        else:
            key = str(max([int(k) for k in actions if str(k).isdigit()] + [0]) + 1)
            row = {}
            actions[key] = row
            created_count += 1
        if not row.get("MTG_ActionNo"):
            row["MTG_ActionNo"] = f"A-{action_number_cursor:03d}"
            action_number_cursor += 1
        if not row.get("MTG_ActionDescription"):
            row["MTG_ActionDescription"] = generated_description
        if not row.get("MTG_ActionDecisionNo"):
            row["MTG_ActionDecisionNo"] = decision_no
        row["MTG_ActionOwnerUID"] = uid
        row["MTG_ActionOwnerPosition"] = _position(participant, person) or str(row.get("MTG_ActionOwnerPosition") or "")
        if due_date:
            row["MTG_persiandate_ActionDueDateTime"] = due_date
        row["MTG_ActionPriority"] = str(row.get("MTG_ActionPriority") or "Normal")
        changed.append((str(row["MTG_ActionNo"]), _person_label(uid, person), str(row["MTG_ActionDescription"])))
    values["MTG_Actions"] = actions

    requested_count = requested if requested is not None else len(selected)
    shortage = requested_count is not None and requested_count > len(selected)
    mode = "به‌صورت انتخاب خودکار از حاضرین" if random_requested else "از حاضرین جلسه"
    if reused_count and created_count:
        reply = f"{reused_count} اقدام موجود {mode} مسئول گرفت و {created_count} اقدام جدید برای نفرات باقی‌مانده ساخته شد."
    elif reused_count:
        reply = f"{reused_count} اقدام موجود {mode} به افراد انتخاب‌شده تخصیص داده شد؛ اقدام تکراری نساختم."
    else:
        reply = f"{created_count} اقدام {mode} به پیش‌نویس اضافه شد."
    if days is not None:
        reply += f" مهلت اقدامات انتخاب‌شده {days} روز از امروز، یعنی {due_date}، ثبت شد."
    if shortage:
        reply += f" فقط {len(selected)} شرکت‌کننده واجد شرایط در جلسه موجود بود؛ بیشتر از این تعداد انتخاب نشد."
    if not had_decisions:
        reply += " برای حفظ ارتباط معتبر اقدام‌ها با ProcessMaker، مصوبه‌های مرتبط نیز به‌صورت پیش‌نویس ساخته شدند."
    if changed:
        reply += "\n" + "\n".join(
            f"{action_no} · {owner}: {description}" for action_no, owner, description in changed
        )
    reply += "\n\nاین تغییرات فقط در پیش‌نویس است و تا ارسال صریح صورت‌جلسه هیچ Case اقدامی ایجاد نمی‌شود."

    return {
        "values": values,
        "questions": _prune_questions(questions, values),
        "intent": "resolved",
        "pending_confirmation": None,
        "reply": reply,
        "resolution": "batch_actions",
        "created_actions": created_count,
        "reused_actions": reused_count,
    }
