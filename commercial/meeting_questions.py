"""Evidence-first, deterministic Persian meeting questions for synthetic review.

No LLM, hidden SQL, guessing, or ProcessMaker writes. Each answer is computed
only from records already authorized by the caller. Missing dates/risks/owner
identities are disclosed instead of invented. Source IDs link to meeting rows.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone, timedelta
import re
from typing import Iterable

QUESTIONS = (
    "کدام اقدامات مصوب جلسات عقب‌افتاده‌اند؟",
    "مهم‌ترین موضوعات حل‌نشده این ماه چیست؟",
    "عملکرد واحدها در اجرای مصوبات چگونه بوده است؟",
    "کدام مدیر یا واحد بیشترین اقدامات باز را دارد؟",
    "اقدامات جلسه شماره LAB-910002 در چه وضعیتی هستند؟",
    "مهم‌ترین ریسک‌های قابل مشاهده در جلسات اخیر چیست؟",
    "چه موضوعاتی در جلسات مختلف به‌صورت مکرر مطرح شده‌اند؟",
    "برای جلسه آینده چه مواردی باید در دستور جلسه قرار گیرد؟",
)

def _date(value):
    if not value:
        return None
    if isinstance(value, datetime):
        dt = value
    else:
        try:
            dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except (ValueError, TypeError):
            return None
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)


def _open(action: dict) -> bool:
    return not bool(action.get("is_closed")) and int(action.get("progress_percent") or 0) < 100


def _source(meeting: dict, action: dict | None = None) -> dict:
    return {
        "meeting_id": int(meeting["meeting_id"]),
        "meeting_no": str(meeting["meeting_no"]),
        "action_no": str(action["action_no"]) if action else None,
        "title": str(meeting["title"]),
    }


def _entry(meeting: dict, action: dict | None = None, *, detail: str | None = None) -> dict:
    result = {"source": _source(meeting, action)}
    result["text"] = detail if detail is not None else (
        str(action.get("description") or action.get("title") or "اقدام بدون عنوان")
        if action else str(meeting["title"])
    )
    if action is not None:
        result.update({
            "owner_unit": str(action.get("owner_unit") or "نامشخص"),
            "progress_percent": int(action.get("progress_percent") or 0),
            "due_at_utc": str(action.get("due_at_utc") or ""),
            "is_closed": bool(action.get("is_closed")),
        })
    return result


def _meeting_number(question: str) -> str | None:
    # A meeting number is meaningful only when explicitly referring to a
    # meeting. It is never interpreted as SQL or a user-specified tenant.
    value = re.search(r"(?:جلسه\s*(?:شماره\s*)?|شماره\s*جلسه\s*)(LAB-\d+|\d{1,12})",
                      question, re.IGNORECASE)
    return value.group(1).upper() if value else None


def _intent(question: str) -> str:
    q = question.strip().replace("ي", "ی").replace("ك", "ک")
    if (_meeting_number(q) or
        ("اقدام" in q and "جلسه" in q and
         any(part in q for part in ("وضعیت", "شماره", "همین جلسه")))):
        return "meeting_status"
    if any(s in q for s in ("دستور جلسه", "جلسه آینده", "جلسه بعد", "جلسه آتی")):
        return "next_agenda"
    if any(s in q for s in ("ریسک", "مخاطر", "تهدید")):
        return "risks"
    if any(s in q for s in ("تکرار", "مکرر", "پرتکرار", "چند جلسه")):
        return "recurring"
    if any(s in q for s in ("بیشترین اقدامات باز", "بیشترین اقدام باز", "کدام مدیر", "کدام واحد")):
        return "owner_backlog"
    if any(s in q for s in ("عملکرد", "کارایی", "نرخ انجام")):
        return "unit_performance"
    if any(s in q for s in ("حل‌نشده", "حل نشده", "این ماه", "ماه جاری")):
        return "monthly_unresolved"
    if any(s in q for s in ("عقب‌افتاده", "عقب افتاده", "تاخیر", "تأخیر", "سررسید", "موعد گذشته")):
        return "overdue_actions"
    return "unsupported"


def _line(caption, amount, unit="") -> str:
    return f"{caption}: {amount}{(' ' + unit) if unit else ''}"


def answer_question(question: str, meetings: Iterable[dict], *,
                    now: datetime | None = None,
                    data_scope: str = "fictional-local-preview",
                    coverage_complete: bool = True) -> dict:
    """Return grounded answer and at most ten clickable/inspectable sources.

    Caller MUST fetch only already authorized meetings. This function does not
    authenticate and must never be wired to an unrestricted SQL table.
    """
    if not isinstance(question, str) or not 3 <= len(question.strip()) <= 350:
        raise ValueError("Question must contain 3..350 characters")
    instant = _date(now) or datetime.now(timezone.utc)
    records = list(meetings)
    if len(records) > 2000:
        raise ValueError("Unbounded meeting scope")
    if len({int(m["meeting_id"]) for m in records}) != len(records):
        raise ValueError("Duplicate meeting records in authorized scope")
    intent = _intent(question)
    actions = [(m, a) for m in records for a in m.get("actions", [])]
    if len(actions) > 20000:
        raise ValueError("Unbounded action scope")

    result = {
        "question": question.strip(), "intent": intent, "answer": "",
        "items": [], "sources": [], "as_of_utc": instant.isoformat(),
        "meetings_considered": len(records), "actions_considered": len(actions),
        "coverage_complete": bool(coverage_complete), "data_scope": data_scope,
        "model_used": False, "notes": [],
    }
    items = result["items"]
    notes = result["notes"]

    def add(m, a=None, *, detail=None):
        if len(items) < 10:
            items.append(_entry(m, a, detail=detail))

    overdue = [(m, a) for m, a in actions if _open(a)
               and _date(a.get("due_at_utc")) is not None
               and _date(a["due_at_utc"]) < instant]
    overdue.sort(key=lambda pair: _date(pair[1]["due_at_utc"]))
    open_actions = [(m, a) for m, a in actions if _open(a)]

    if intent == "overdue_actions":
        for m, a in overdue: add(m, a)
        result["answer"] = (
            f"تا زمان بررسی، {len(overdue)} اقدام باز با موعد گذشته در {len(records)} "
            "جلسه موجود در دامنه داده قابل مشاهده است."
            if overdue else "در داده‌های قابل مشاهده، اقدام باز با موعد گذشته پیدا نشد."
        )
        notes.append("عقب‌افتادگی = موعد گذشته + پیشرفت کمتر از ۱۰۰٪ + بسته‌نبودن؛ موعدها برحسب UTC سنجیده شده‌اند.")

    elif intent == "monthly_unresolved":
        start = instant.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        monthly = [m for m in records if _date(m.get("meeting_date_utc"))
                   and start <= _date(m["meeting_date_utc"]) <= instant]
        missing_dates = sum(not _date(m.get("meeting_date_utc")) for m in records)
        if not monthly and missing_dates:
            result["answer"] = "تاریخ تشکیل جلسات در نمایه فعلی ثبت نشده است؛ تعیین موضوعات حل‌نشده این ماه ممکن نیست."
            notes.append("برای این پرسش، تاریخ واقعی تشکیل جلسه و وضعیت باز مصوبات باید وارد نمایه مجاز شوند.")
        else:
            ranked = []
            for m in monthly:
                pending = [a for a in m.get("actions", []) if _open(a)]
                if not pending: continue
                late = sum(_date(a.get("due_at_utc")) is not None and
                           _date(a["due_at_utc"]) < instant for a in pending)
                ranked.append((late, len(pending), m))
            ranked.sort(key=lambda x: (-x[0], -x[1], int(x[2]["meeting_id"])))
            for late, count, m in ranked:
                add(m, detail=f"{m['title']} — {count} اقدام باز، {late} اقدام دارای تأخیر")
            result["answer"] = (f"در ماه جاری تا زمان بررسی، {len(ranked)} جلسه دارای اقدام باز در "
                                f"{len(monthly)} جلسه تاریخ‌دارِ قابل مشاهده یافت شد."
                                if ranked else
                                "در جلسات تاریخ‌دار این ماه که قابل مشاهده‌اند، اقدام باز ثبت نشده است.")
            notes.append("«این ماه» در این نسخه به ماه میلادی UTC اشاره دارد، نه ماه شمسی سازمان. «مهم‌ترین» فقط ترتیب بر اساس تعداد اقدامات تأخیردار و سپس باز است؛ اهمیت تجاری ارزیابی نشده است.")
            if missing_dates:
                notes.append(f"{missing_dates} جلسه به علت نداشتن تاریخ تشکیل، در نتیجه ماه جاری قابل طبقه‌بندی نبود.")

    elif intent == "unit_performance":
        groups = defaultdict(lambda: {"total": 0, "done": 0, "open": 0, "overdue": 0})
        for m, a in actions:
            group = groups[str(a.get("owner_unit") or "واحد نامشخص")]
            group["total"] += 1
            if _open(a):
                group["open"] += 1
                if (m, a) in overdue: group["overdue"] += 1
            else:
                group["done"] += 1
        ranked = sorted(groups.items(), key=lambda pair: (-pair[1]["overdue"], -pair[1]["open"], pair[0]))
        for unit, g in ranked[:10]:
            evidence = next(((m, a) for m, a in actions if
                             str(a.get("owner_unit") or "واحد نامشخص") == unit), None)
            if evidence:
                add(*evidence, detail=(f"{unit}: {g['done']} انجام‌شده/غیرباز، "
                     f"{g['open']} باز، {g['overdue']} تأخیردار، از {g['total']} اقدام"))
        result["answer"] = (f"خلاصه وضعیت اجرای {len(actions)} اقدام در {len(groups)} واحد "
                             "در دامنه جلسات قابل مشاهده آماده شد." if groups else
                             "اقدامی با واحد مسئول در دامنه داده قابل مشاهده ثبت نشده است.")
        notes.append("پیشرفت ۱۰۰٪ یا بسته‌شدن به‌عنوان «غیرباز» شمرده شده؛ تأیید کیفیت یا انجام واقعی از داده‌ها قابل نتیجه‌گیری نیست.")

    elif intent == "owner_backlog":
        counts = Counter(str(a.get("owner_unit") or "واحد نامشخص") for m, a in open_actions)
        ranked = counts.most_common()
        for unit, count in ranked[:10]:
            evidence = next((pair for pair in open_actions if
                             str(pair[1].get("owner_unit") or "واحد نامشخص") == unit), None)
            if evidence: add(*evidence, detail=f"{unit}: {count} اقدام باز")
        result["answer"] = (f"در دامنه مجاز، {len(open_actions)} اقدام باز وجود دارد. "
            + (f"در سطح واحد، «{ranked[0][0]}» با {ranked[0][1]} اقدام باز بیشترین تعداد را دارد."
               if ranked else "هیچ واحدی اقدام باز ثبت‌شده ندارد."))
        notes.append("شناسه فردِ مسئول یا مدیر هر اقدام در داده‌های موجود نیست؛ رتبه‌بندی مدیران ممکن نیست و فقط واحد مسئول گزارش می‌شود.")

    elif intent == "meeting_status":
        requested = _meeting_number(question)
        if not requested:
            result["answer"] = "برای وضعیت اقدامات، شماره دقیق جلسه را مانند LAB-910002 در پرسش بنویسید."
        else:
            match = next((m for m in records if
                          str(m["meeting_no"]).upper() == requested or
                          str(m["meeting_id"]) == requested), None)
            if match is None:
                result["answer"] = ("جلسه با این شماره در دامنه داده قابل مشاهده پیدا نشد؛ "
                                    "ممکن است وجود نداشته باشد یا کاربر مجوز مشاهده آن را نداشته باشد.")
            else:
                target = match.get("actions", [])
                for a in target: add(match, a)
                opened = sum(_open(a) for a in target)
                late = sum(_open(a) and _date(a.get("due_at_utc")) is not None
                           and _date(a["due_at_utc"]) < instant for a in target)
                result["answer"] = (f"جلسه {match['meeting_no']} با موضوع «{match['title']}»: "
                  f"{len(target)} اقدام؛ {opened} اقدام باز و {late} اقدام با موعد گذشته.")
                if not target: notes.append("هیچ اقدام نمایه‌شده‌ای برای این جلسه وجود ندارد.")

    elif intent == "risks":
        recent = [m for m in records if _date(m.get("meeting_date_utc"))
                  and _date(m["meeting_date_utc"]) <= instant
                  and _date(m["meeting_date_utc"]) >= instant - timedelta(days=30)
                  and m.get("risk")]
        recent.sort(key=lambda m: _date(m["meeting_date_utc"]), reverse=True)
        for m in recent:
            add(m, detail=str(m["risk"]))
        result["answer"] = (f"در ۳۰ روز گذشته، {len(recent)} جلسه دارای متن ریسک ثبت‌شده در "
                            "دامنه قابل مشاهده یافت شد." if recent else
                            "در نمایه قابل مشاهده، ریسک ثبت‌شده و تاریخ‌دار برای ۳۰ روز اخیر موجود نیست.")
        notes.append("تنها ریسک‌های صریحاً ثبت‌شده در منبع گزارش می‌شوند؛ شدت، احتمال و اولویت بدون داده قابل تعیین نیست.")

    elif intent == "recurring":
        groups = defaultdict(list)
        for m in records:
            key = " ".join(str(m["title"]).replace("ي","ی").replace("ك","ک").split()).casefold()
            groups[key].append(m)
        recurring = [group for group in groups.values() if len(group) >= 2]
        recurring.sort(key=lambda group: (-len(group), str(group[0]["title"])))
        for group in recurring[:10]:
            for m in group[:min(2,10-len(items))]:
                add(m, detail=f"موضوع تکراری «{m['title']}» در {len(group)} جلسه")
        result["answer"] = (f"{len(recurring)} عنوان جلسه با تکرار صریح در دامنه مجاز پیدا شد."
                            if recurring else
                            "عنوان یکسانِ تکرارشده‌ای در جلسات قابل مشاهده پیدا نشد.")
        notes.append("تکرار فقط با یکسان‌بودن عنوان پس از یکسان‌سازی حروف/فاصله تشخیص داده می‌شود؛ شباهت معنایی موضوعات هنوز تحلیل نشده است.")

    elif intent == "next_agenda":
        pending_by_meeting = []
        for m in records:
            pending = [a for a in m.get("actions",[]) if _open(a)]
            if not pending:continue
            due = [a for a in pending if _date(a.get("due_at_utc"))]
            earliest = min((_date(a["due_at_utc"]) for a in due), default=instant)
            pending_by_meeting.append((earliest, m, pending))
        pending_by_meeting.sort(key=lambda t: (t[0],int(t[1]["meeting_id"])))
        for _, m, pending in pending_by_meeting[:10]:
            add(m, pending[0], detail=(f"مرور «{m['title']}» و تعیین تکلیف "
                 f"{len(pending)} اقدام باز؛ بررسی مدارک، مسئول و موعد"))
        result["answer"] = (
            f"برای دستور جلسه بعد، پیگیری مصوبات باز {len(pending_by_meeting)} جلسه قابل مشاهده "
            "بر اساس قدیمی‌ترین موعد پیشنهاد می‌شود."
            if pending_by_meeting else
            "در داده‌های قابل مشاهده اقدام بازی برای پیشنهاد دستور جلسه بعد پیدا نشد.")
        notes.append("این پیشنهاد صرفاً پیش‌نویس مبتنی بر موعد و وضعیت اقدامات است؛ دبیر یا رئیس باید اهمیت واقعی و دستور جلسه نهایی را تأیید کند.")

    else:
        result["answer"] = ("این پرسش در نسخه فعلی جزو هشت الگوی تحلیلی پشتیبانی‌شده نیست. "
                            "یکی از پرسش‌های پیشنهادی را انتخاب کنید.")
        result["suggested_questions"] = list(QUESTIONS)

    result["sources"] = [item["source"] for item in items]
    if not result["coverage_complete"]:
        notes.append("نمایه یا تعداد جلسات بازیابی‌شده کامل نیست؛ نتیجه فقط به داده‌های در دسترس محدود است.")
    return result
