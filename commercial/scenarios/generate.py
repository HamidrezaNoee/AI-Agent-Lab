"""Reproducible 1008 distinct automotive management scenarios, never real records."""

from datetime import date, datetime, timedelta, timezone
from itertools import product
import argparse
import hashlib
import json
from pathlib import Path

DOMAINS = [
    (
        "import",
        "واردات خودرو",
        "بازبینی برنامه ورود خودرو",
        "تطبیق سبد مدل با مجوز واردات",
        "اجرای برنامه ورود",
    ),
    (
        "procurement",
        "خرید خارجی",
        "مذاکره قیمت و شرایط تحویل",
        "ارزیابی پیش‌فاکتور تأمین‌کننده",
        "قطعی‌کردن سفارش خرید",
    ),
    (
        "supplier",
        "تأمین‌کنندگان",
        "ارزیابی ظرفیت تأمین‌کننده",
        "ممیزی کیفیت و ظرفیت خط",
        "تصویب تأمین‌کننده جایگزین",
    ),
    (
        "registration",
        "ثبت سفارش",
        "رفع نقص ثبت سفارش",
        "تطبیق تعرفه و مشخصات کالا",
        "اخذ تأیید ثبت سفارش",
    ),
    (
        "license",
        "مجوزها",
        "اخذ مجوز فنی و استاندارد",
        "تکمیل پرونده استاندارد مدل",
        "دریافت مجوز معتبر",
    ),
    (
        "currency",
        "تخصیص ارز",
        "تعیین تکلیف تخصیص ارز",
        "تطبیق مدارک بانکی سفارش",
        "آزادسازی پرداخت ارزی",
    ),
    (
        "contract",
        "قراردادها",
        "بازنگری تعهدات قرارداد",
        "تطبیق ضمانت‌ها و زمان تحویل",
        "ابلاغ الحاقیه قرارداد",
    ),
    (
        "shipping",
        "حمل بین‌المللی",
        "برنامه حمل محموله",
        "تطبیق رزرو کشتی و بارنامه",
        "تأیید برنامه بارگیری",
    ),
    (
        "logistics",
        "لجستیک",
        "توزیع و انتقال داخلی",
        "کنترل ظرفیت ناوگان حمل",
        "تحویل محموله به مقصد",
    ),
    (
        "customs",
        "گمرک",
        "رفع مانع ترخیص",
        "تطبیق اظهارنامه و اسناد محموله",
        "اخذ پروانه ترخیص",
    ),
    (
        "pdi",
        "PDI",
        "رفع نقص پیش از تحویل",
        "بازرسی نمونه خودروها",
        "آزادسازی خودرو برای تحویل",
    ),
    (
        "sales",
        "فروش",
        "برنامه تحویل قراردادهای فروش",
        "تطبیق تعهد فروش با موجودی",
        "اعلام برنامه تحویل مشتری",
    ),
    (
        "marketing",
        "بازاریابی",
        "ارزیابی کمپین جذب مشتری",
        "تحلیل کیفیت سرنخ‌ها",
        "اصلاح تخصیص بودجه کمپین",
    ),
    (
        "dealer",
        "نمایندگان",
        "ارتقای عملکرد شبکه نمایندگی",
        "بازبینی ظرفیت خدمات نماینده",
        "ابلاغ برنامه بهبود نماینده",
    ),
    (
        "aftersales",
        "خدمات پس از فروش",
        "کاهش زمان توقف خودرو",
        "تحلیل پرونده تعمیرات معوق",
        "بازگرداندن خودرو به مشتری",
    ),
    (
        "warranty",
        "گارانتی",
        "رسیدگی به ادعای گارانتی",
        "تطبیق خرابی با شرایط ضمانت",
        "تعیین تکلیف هزینه ضمانت",
    ),
    (
        "parts",
        "قطعات",
        "جبران کسری قطعه",
        "بازبینی موجودی و مصرف قطعه",
        "تأمین قطعات بحرانی",
    ),
    (
        "customer",
        "رضایت مشتری",
        "رسیدگی به شکایت مشتری",
        "تحلیل سابقه تماس و خدمت",
        "اجرای اقدام جبرانی مصوب",
    ),
    (
        "finance",
        "مالی",
        "کنترل جریان نقد پروژه",
        "تطبیق صورت‌وضعیت و تعهد پرداخت",
        "تصویب برنامه پرداخت",
    ),
    (
        "legal",
        "حقوقی",
        "حل اختلاف قراردادی",
        "جمع‌آوری مستندات تعهدات طرفین",
        "ارائه راهکار حل اختلاف",
    ),
    (
        "it_strategy",
        "IT و برنامه‌ریزی",
        "پایداری سامانه و برنامه عملیاتی",
        "تحلیل مغایرت داده و ظرفیت سامانه",
        "اجرای برنامه اصلاح مصوب",
    ),
]
ISSUES = [
    (
        "capacity",
        "کمبود ظرفیت عملیاتی",
        "ظرفیت تعهدشده با حجم واقعی کار سازگار نیست",
        "تقسیم اجرا به دو مرحله و تخصیص ظرفیت پشتیبان",
    ),
    (
        "document",
        "نقص مستندات",
        "یک مدرک کنترلی لازم هنوز تأیید نشده است",
        "تکمیل مدرک با تأیید واحد ذی‌صلاح قبل از ادامه",
    ),
    (
        "quality",
        "مغایرت کیفیت",
        "نتیجه کنترل نمونه با معیار پذیرش فاصله دارد",
        "توقف بخش مغایر و اجرای بازرسی مجدد نمونه",
    ),
    (
        "cash",
        "محدودیت نقدینگی",
        "موعد تعهد مالی با منابع نقد دردسترس هم‌زمان نیست",
        "اولویت‌بندی پرداخت و تأمین اعتبار مرحله‌ای",
    ),
    (
        "deadline",
        "تعارض موعدها",
        "زمان تعهد به ذی‌نفع زودتر از زمان قابل تحقق است",
        "ارائه برنامه جبرانی و تصویب موعد واقع‌بینانه",
    ),
    (
        "dependency",
        "وابستگی بین واحدها",
        "شروع فعالیت منوط به تحویل خروجی واحد دیگر است",
        "تعیین مالک وابستگی و نقطه کنترل تحویل",
    ),
    (
        "conflict",
        "تضاد گزارش‌ها",
        "دو گزارش برای یک موضوع اعداد متفاوت ارائه کرده‌اند",
        "تطبیق منبع و تأیید صورت تطبیق توسط دبیر",
    ),
    (
        "repeat",
        "تکرار مشکل",
        "مانع مشابه در جلسه قبلی مطرح شده اما علت رفع نشده است",
        "تحلیل علت و کنترل اثربخشی اقدام اصلاحی",
    ),
]
CONTEXTS = [
    (
        "ev",
        "خودروی برقی شهری",
        "شرکت فرضی آینده‌ران",
        "مسیر شانگهای ـ بندرعباس",
        "بازار ناوگان شهری",
        "برنامه رونمایی محصول جدید",
        36,
    ),
    (
        "hybrid",
        "کراس‌اوور هیبرید",
        "شرکت فرضی سبزحرکت",
        "مسیر گوانگژو ـ بوشهر",
        "بازار خرده‌فروشی",
        "تعهد تحویل پایان فصل",
        72,
    ),
    (
        "sedan",
        "سدان خانوادگی",
        "شرکت فرضی مهرخودرو",
        "مسیر بوسان ـ بندرعباس",
        "شبکه نمایندگی غرب",
        "افزایش ناگهانی تقاضا",
        124,
    ),
    (
        "van",
        "ون تجاری",
        "شرکت فرضی راه‌گستر",
        "مسیر استانبول ـ بازرگان",
        "مشتری سازمانی",
        "اجرای قرارداد ناوگان",
        28,
    ),
    (
        "truck",
        "کامیونت توزیع",
        "شرکت فرضی بارآفرین",
        "مسیر هامبورگ ـ بندر امام",
        "شبکه توزیع کالا",
        "راه‌اندازی مرکز خدمات جدید",
        45,
    ),
    (
        "suv",
        "شاسی‌بلند بنزینی",
        "شرکت فرضی کوه‌ران",
        "مسیر جبل‌علی ـ بندر لنگه",
        "نمایندگان جنوب",
        "کنترل هزینه در فصل کم‌تقاضا",
        63,
    ),
]
OUTCOMES = [
    "closed",
    "overdue",
    "no_report",
    "stalled",
    "awaiting_review",
    "rework",
    "blocked",
    "conflicting_progress",
]


def build(as_of=None):
    anchor = as_of or date.today()
    dataset_id = "AVAN-AUTO-1008-" + anchor.isoformat()
    scenarios = []
    for index, (domain, issue, context) in enumerate(
        product(DOMAINS, ISSUES, CONTEXTS), 1
    ):
        code, unit, agenda, investigate, execute = domain
        issue_code, issue_title, obstacle, decision = issue
        context_code, vehicle, company, route, market, constraint, base_qty = context
        sid = "AUTO-%04d" % index
        created = anchor - timedelta(days=20 + (index % 120))
        qty = base_qty + ((index * 17) % 53)
        title = f"{agenda}؛ {vehicle}؛ {issue_title}؛ {market}"
        owner = "owner_" + code
        roles = ["secretary", "chair", owner, "finance", "quality"]
        agenda_items = [
            agenda,
            f"{issue_title} در {route}",
            f"اثر تصمیم بر {constraint}",
        ]
        discussion = (
            f"در {company} وضعیت {qty} دستگاه {vehicle} برای {market} بررسی شد. "
            f"{obstacle}. موضوع در مسیر {route} و با قید {constraint} مطرح است. "
            f"واحد {unit} مسئول راستی‌آزمایی داده و ارائه برنامه اجرایی شد."
        )
        actions = []
        for number, (description, role) in enumerate(
            [
                (investigate, owner),
                ("تأیید منابع مالی و کنترل تعهدات مرتبط با " + vehicle, "finance"),
                (execute, owner),
                ("کنترل اثربخشی و تطبیق مستندات " + issue_title, "quality"),
            ],
            1,
        ):
            outcome = OUTCOMES[(index + number - 2) % len(OUTCOMES)]
            due = anchor + timedelta(
                days=2 if outcome == "blocked" else -(number + index % 13)
            )
            progress = {
                "closed": 100,
                "overdue": 40,
                "no_report": 0,
                "stalled": 50,
                "awaiting_review": 100,
                "rework": 65,
                "blocked": 15,
                "conflicting_progress": 100,
            }[outcome]
            action_no = "A-%03d" % number
            action_desc = f"{description} برای {qty} دستگاه {vehicle} در {company} با رعایت {constraint}"
            reports = (
                []
                if outcome == "no_report"
                else [
                    {
                        "submissionVersion": 1,
                        "submittedAt": str(anchor - timedelta(days=12)) + " 10:00:00",
                        "progressPercent": min(progress, 50),
                        "description": f"بررسی اولیه {issue_title} انجام شد؛ نیازمند {decision}.",
                        "evidence": [f"{sid}-{action_no}-initial.pdf"],
                    },
                    {
                        "submissionVersion": 2,
                        "submittedAt": str(
                            anchor - timedelta(days=9 if outcome == "stalled" else 1)
                        )
                        + " 11:00:00",
                        "progressPercent": progress,
                        "description": f"وضعیت {vehicle}: "
                        + (
                            "مدارک تکمیل شد"
                            if progress == 100
                            else f"{obstacle}؛ پیگیری ادامه دارد"
                        ),
                        "evidence": [f"{sid}-{action_no}-review.pdf"],
                    },
                ]
            )
            review_status = (
                "Closed"
                if outcome == "closed"
                else (
                    "Rework"
                    if outcome in ("rework", "conflicting_progress")
                    else "InProgress"
                )
            )
            reviews = (
                []
                if outcome in ("no_report", "awaiting_review")
                else [
                    {
                        "submissionVersion": 2,
                        "reviewedAt": str(anchor) + " 08:00:00",
                        "reviewStatus": review_status,
                        "progressPercent": (
                            60 if outcome == "conflicting_progress" else progress
                        ),
                        "comment": (
                            "گزارش صددرصد با شواهد تطبیق ندارد؛ تکمیل مستند لازم است"
                            if outcome == "conflicting_progress"
                            else (
                                "تأیید نتیجه و اختتام"
                                if outcome == "closed"
                                else "ادامه پیگیری با رفع مانع ثبت‌شده"
                            )
                        ),
                    }
                ]
            )
            actions.append(
                {
                    "action_no": action_no,
                    "decision_no": str(1 + (number - 1) % 2),
                    "description": action_desc,
                    "owner_role": role,
                    "unit": (
                        unit
                        if role == owner
                        else "مالی" if role == "finance" else "کنترل کیفیت"
                    ),
                    "start_date": str(created + timedelta(days=1)),
                    "due_date": str(due),
                    "priority": (
                        "High"
                        if issue_code in ("quality", "deadline", "conflict")
                        else "Normal"
                    ),
                    "outcome": outcome,
                    "progress_percent": progress,
                    "reports": reports,
                    "reviews": reviews,
                    "depends_on": (
                        [f"{sid}:A-001"]
                        if number == 3
                        else [f"{sid}:A-003"] if number == 4 else []
                    ),
                    "hypothetical_evidence": [
                        {
                            "name": f"{sid}-{action_no}-review.pdf",
                            "hypothetical": True,
                            "description": "مستند فرضی؛ فایل واقعی بارگذاری نشده است",
                        }
                    ],
                    "expected": {
                        "closed": outcome == "closed",
                        "effective_progress": (
                            60 if outcome == "conflicting_progress" else progress
                        ),
                        "overdue": outcome not in ("closed", "blocked"),
                        "missing_report": outcome == "no_report",
                    },
                }
            )
        scenarios.append(
            {
                "id": sid,
                "unique_signature": hashlib.sha256(
                    (code + "|" + issue_code + "|" + context_code).encode()
                ).hexdigest(),
                "domain": unit,
                "domain_code": code,
                "company": company,
                "vehicle": vehicle,
                "quantity": qty,
                "route": route,
                "market": market,
                "constraint": constraint,
                "issue_code": issue_code,
                "title": title,
                "date": str(created),
                "participants": roles,
                "agenda": agenda_items,
                "discussion": discussion,
                "decisions": [
                    decision,
                    f"گزارش پیشرفت {vehicle} همراه شاهد قابل تطبیق ارائه شود",
                ],
                "parking_lot": (
                    f"ارزیابی هزینه و ریسک ادامه {constraint}"
                    if issue_code in ("cash", "repeat", "dependency")
                    else ""
                ),
                "related_scenario": (
                    ("AUTO-%04d" % (index - 6)) if issue_code == "repeat" else None
                ),
                "actions": actions,
                "final_result": "اختتام فقط برای اقداماتی که بررسی دبیر Closed است؛ سایر اقدامات باز هستند.",
                "test_questions": [
                    f"وضعیت اقدامات جلسه {sid} چیست؟",
                    f"آیا گزارش صددرصد در {sid} به معنای اختتام است؟",
                ],
                "expected": {
                    "open": sum(not a["expected"]["closed"] for a in actions),
                    "closed": sum(a["expected"]["closed"] for a in actions),
                    "overdue": sum(a["expected"]["overdue"] for a in actions),
                },
            }
        )
    return {
        "schema_version": 1,
        "dataset_id": dataset_id,
        "synthetic": True,
        "as_of": str(anchor),
        "scenario_count": len(scenarios),
        "action_count": sum(len(s["actions"]) for s in scenarios),
        "roles": sorted({r for s in scenarios for r in s["participants"]}),
        "scenarios": scenarios,
    }


def validate(dataset):
    rows = dataset["scenarios"]
    assert len(rows) > 1000 and dataset["synthetic"] is True
    for field in ("id", "unique_signature", "title", "discussion"):
        assert len({s[field] for s in rows}) == len(rows), "Duplicate " + field
    ids = {s["id"] for s in rows}
    for s in rows:
        assert len(s["actions"]) == 4 and (
            not s["related_scenario"] or s["related_scenario"] in ids
        )
        for a in s["actions"]:
            assert a["owner_role"] in s["participants"]
            assert date.fromisoformat(a["start_date"]) <= date.fromisoformat(
                a["due_date"]
            )
            assert all(d.split(":")[0] in ids for d in a["depends_on"])
            assert [r["submissionVersion"] for r in a["reports"]] == (
                [] if not a["reports"] else [1, 2]
            )
    return {
        "scenarios": len(rows),
        "actions": sum(len(s["actions"]) for s in rows),
        "unique_titles": len({s["title"] for s in rows}),
        "domains": len({s["domain"] for s in rows}),
        "outcomes": sorted({a["outcome"] for s in rows for a in s["actions"]}),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    parser.add_argument("--as-of", type=date.fromisoformat)
    args = parser.parse_args()
    data = build(args.as_of)
    result = validate(data)
    Path(args.out).write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
