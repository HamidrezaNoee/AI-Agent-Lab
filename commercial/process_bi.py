"""Cross-process BI over native PM metadata. No APP_DATA reads or workflow writes."""

from collections import Counter, defaultdict
from datetime import datetime, date, time, timezone
from statistics import median
from typing import Literal
from zoneinfo import ZoneInfo
from pydantic import BaseModel, ConfigDict, Field, model_validator
from .processmaker_store import query, ProductionAccessDenied, ProductionUnavailable
from .setup_console import get_setting
from .agent_tools import period_bounds

MAX_CASES = 20000
MAX_DELEGATIONS = 100000


class BIQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")
    process_uid: str | None = Field(None, pattern=r"^[a-fA-F0-9]{32}$")
    status: Literal["all", "DRAFT", "TO_DO", "COMPLETED", "CANCELLED", "PAUSED"] = "all"
    period: Literal[
        "all", "this_month", "last_month", "last_30_days", "last_7_days"
    ] = "last_30_days"
    start: date | None = None
    end: date | None = None
    offset: int = Field(0, ge=0, le=20000)
    limit: int = Field(30, ge=1, le=100)

    @model_validator(mode="after")
    def dates(self):
        if bool(self.start) != bool(self.end) or self.start and self.end <= self.start:
            raise ValueError(
                "Provide a valid inclusive start and exclusive end together"
            )
        return self


def native_time(value, tz):
    if not value or str(value).startswith("0000-"):
        return None
    try:
        result = (
            value if isinstance(value, datetime) else datetime.fromisoformat(str(value))
        )
        return (
            result.replace(tzinfo=tz)
            if result.tzinfo is None
            else result.astimezone(tz)
        )
    except ValueError:
        return None


def case_predicate(scope, args, now):
    where, parameters = ["1=1"], []
    tz = ZoneInfo(scope.get("timezone") or
                  (get_setting("mysql") or {}).get("timezone", "Asia/Tehran"))
    if scope["role"] != "SysAdmin":
        ids = sorted(scope["visible_uids"])
        if not ids or len(ids) > 500:
            raise ProductionAccessDenied("Invalid BI scope")
        placeholders = ",".join("%s" for _ in ids)
        where.append(
            "(a.APP_INIT_USER IN (" + placeholders + ") OR EXISTS "
            "(SELECT 1 FROM APP_DELEGATION acl WHERE acl.APP_UID=a.APP_UID AND acl.USR_UID IN ("
            + placeholders
            + ")))"
        )
        parameters += ids + ids
    if args.process_uid:
        where.append("a.PRO_UID=%s")
        parameters.append(args.process_uid)
    if args.status != "all":
        where.append("a.APP_STATUS=%s")
        parameters.append(args.status)
    if args.start:
        start = datetime.combine(args.start, time.min, tz)
        end = datetime.combine(args.end, time.min, tz)
    else:
        start, end = period_bounds(args.period, now)
    if start:
        where.append("a.APP_CREATE_DATE>=%s")
        parameters.append(start.astimezone(tz).replace(tzinfo=None))
    if end:
        where.append("a.APP_CREATE_DATE<%s")
        parameters.append(end.astimezone(tz).replace(tzinfo=None))
    return " AND ".join(where), parameters, tz


def load(con, scope, args, now=None, include_access_ids=False):
    if 3 not in scope["license"]["modules"]:
        raise ProductionAccessDenied("BI module not licensed")
    now = now or datetime.now(timezone.utc)
    where, params, tz = case_predicate(scope, args, now)
    cases = query(
        con,
        "SELECT a.APP_UID,a.APP_NUMBER,a.PRO_UID,a.APP_STATUS,a.APP_INIT_USER,"
        "a.APP_CREATE_DATE,a.APP_FINISH_DATE,p.PRO_TITLE FROM APPLICATION a "
        "JOIN PROCESS p ON p.PRO_UID=a.PRO_UID WHERE "
        + where
        + " ORDER BY a.APP_NUMBER DESC LIMIT 20001",
        params,
    )
    complete = len(cases) <= MAX_CASES
    cases = cases[:MAX_CASES]
    delegations = []
    for start in range(0, len(cases), 250):
        ids = [r[0] for r in cases[start : start + 250]]
        batch = query(
            con,
            "SELECT d.APP_UID,d.DEL_INDEX,d.TAS_UID,d.USR_UID,d.DEL_THREAD_STATUS,"
            "d.DEL_DELEGATE_DATE,d.DEL_INIT_DATE,d.DEL_FINISH_DATE,d.DEL_TASK_DUE_DATE,t.TAS_TITLE "
            "FROM APP_DELEGATION d LEFT JOIN TASK t ON t.TAS_UID=d.TAS_UID WHERE d.APP_UID IN ("
            + ",".join("%s" for _ in ids)
            + ") ORDER BY d.APP_UID,d.DEL_INDEX LIMIT 100001",
            ids,
        )
        if len(batch) + len(delegations) > MAX_DELEGATIONS:
            raise ProductionUnavailable(
                "BI delegation bound exceeded; narrow date range"
            )
        delegations.extend(batch)
    result = summarize(cases, delegations, scope, args, now, tz, complete)
    if include_access_ids:
        result["_case_uids"] = [r[0] for r in cases]
    return result


def summarize(cases, delegations, scope, args, now, tz, complete=True):
    indexed = {r[0]: r for r in cases}
    processes, tasks, owners = {}, {}, {}
    statuses = Counter()
    monthly = Counter()
    cycles = []
    malformed = 0
    open_cases = {r[0] for r in cases if r[3] == "TO_DO"}
    for row in cases:
        uid, number, process, status, creator, created, finished, title = row
        bucket = processes.setdefault(
            process,
            {
                "process_uid": process,
                "title": title or process,
                "total": 0,
                "open": 0,
                "completed": 0,
                "cancelled": 0,
                "draft": 0,
                "overdue_tasks": 0,
                "cycles": [],
            },
        )
        bucket["total"] += 1
        statuses[status] += 1
        key = {
            "TO_DO": "open",
            "COMPLETED": "completed",
            "CANCELLED": "cancelled",
            "DRAFT": "draft",
        }.get(status)
        if key:
            bucket[key] += 1
        c, f = native_time(created, tz), native_time(finished, tz)
        if c:
            import jdatetime

            monthly[jdatetime.date.fromgregorian(date=c.date()).strftime("%Y/%m")] += 1
        if status == "COMPLETED":
            if c and f and f >= c:
                hours = (f - c).total_seconds() / 3600
                cycles.append(hours)
                bucket["cycles"].append(hours)
            else:
                malformed += 1
    open_tasks = overdue = unstarted = 0
    for row in delegations:
        uid, index, task, owner, state, delegated, started, finished, due, title = row
        if uid not in indexed:
            continue
        process = indexed[uid][2]
        bucket = tasks.setdefault(
            (process, task),
            {
                "process_uid": process,
                "task_uid": task,
                "title": title or task,
                "open": 0,
                "overdue": 0,
                "completed": 0,
                "durations": [],
                "waits": [],
            },
        )
        start, end, initial, deadline = [
            native_time(v, tz) for v in (started, finished, delegated, due)
        ]
        if start and end and end >= start:
            bucket["completed"] += 1
            bucket["durations"].append((end - start).total_seconds() / 3600)
        if initial and start and start >= initial:
            bucket["waits"].append((start - initial).total_seconds() / 3600)
        # Closed/cancelled/paused/draft cases cannot produce current overdue work.
        if state != "OPEN" or uid not in open_cases or end:
            continue
        open_tasks += 1
        bucket["open"] += 1
        person = scope.get("directory", {}).get(owner, {})
        workload = owners.setdefault(
            owner,
            {
                "owner_uid": owner,
                "name": person.get("name") or "مسئول ثبت نشده",
                "unit": person.get("unit") or "واحد ثبت نشده",
                "open": 0,
                "overdue": 0,
            },
        )
        workload["open"] += 1
        if start is None:
            unstarted += 1
        if deadline and deadline < now:
            overdue += 1
            bucket["overdue"] += 1
            workload["overdue"] += 1
            processes[process]["overdue_tasks"] += 1

    def average(xs):
        return round(sum(xs) / len(xs), 2) if xs else None

    for p in processes.values():
        p["average_cycle_hours"] = average(p.pop("cycles"))
    for t in tasks.values():
        t["average_work_hours"] = average(t.pop("durations"))
        t["average_wait_hours"] = average(t.pop("waits"))
    detail = [
        {
            "case_uid": r[0],
            "case_number": r[1],
            "process_uid": r[2],
            "status": r[3],
            "created_at": (
                native_time(r[5], tz).isoformat() if native_time(r[5], tz) else None
            ),
            "finished_at": (
                native_time(r[6], tz).isoformat() if native_time(r[6], tz) else None
            ),
            "process_title": r[7],
        }
        for r in cases
    ]
    return {
        "as_of_utc": now.isoformat(),
        "coverage_complete": complete,
        "metrics": {
            "cases": len(cases),
            "open_cases": len(open_cases),
            "completed_cases": statuses["COMPLETED"],
            "open_tasks": open_tasks,
            "overdue_tasks": overdue,
            "unstarted_tasks": unstarted,
            "average_cycle_hours": average(cycles),
            "median_cycle_hours": round(median(cycles), 2) if cycles else None,
            "missing_cycle_dates": malformed,
        },
        "statuses": dict(statuses),
        "monthly": [{"month": k, "count": v} for k, v in sorted(monthly.items())],
        "processes": sorted(
            processes.values(), key=lambda p: (-p["total"], p["process_uid"])
        ),
        "tasks": sorted(
            tasks.values(), key=lambda t: (-t["overdue"], -t["open"], t["task_uid"])
        )[:200],
        "owners": sorted(owners.values(), key=lambda o: (-o["open"], o["owner_uid"]))[
            :200
        ],
        "rows": detail[args.offset : args.offset + args.limit],
        "has_more": len(detail) > args.offset + args.limit,
        "notes": [
            "مبنای دوره، تاریخ ایجاد پرونده است. تأخیر بر اساس موعد ثبت‌شده وظیفه محاسبه می‌شود.",
            "دسترسی عمومی BI بر اساس ایجاد یا مشارکت در پرونده و سلسله‌مراتب مصوب آوان است.",
            "این گزارش شامل شاخص‌های مشترک گردش کار است؛ معنای فیلدهای تخصصی هر فرایند خودکار حدس زده نمی‌شود.",
        ],
    }


class ProcessBITools:
    """A fixed BI query tool for ad-hoc questions; no model-generated SQL."""

    def __init__(self, provider):
        self.provider = provider
        self.meetings = []
        self.complete = True
        self.modules = {1, 3}
        self.now = datetime.now(timezone.utc)
        self.evidence = {}
        self.trace = []
        self.access = []

    def definitions(self):
        return [
            {
                "type": "function",
                "name": "analyze_processes",
                "strict": False,
                "description": "Read native ProcessMaker workflow BI across authorized processes: case counts, statuses, task delays, monthly trends, unit/person workload and cycle times. Filter by process UID and case creation dates. No business-form fields are inferred. Dates: custom start/end YYYY-MM-DD (end exclusive), named months are Jalali.",
                "parameters": BIQuery.model_json_schema(),
            }
        ]

    def execute(self, name, raw):
        if name != "analyze_processes":
            raise ValueError("Unknown BI tool")
        args = BIQuery.model_validate(raw)
        result = self.provider(args)
        self.access.append((args, set(result.pop("_case_uids", []))))
        self.complete = self.complete and result["coverage_complete"]
        key = "T:" + str(len(self.trace) + 1)
        # Bound model context; totals cover the full authorized retrieval.
        result["processes"] = result["processes"][:50]
        result["tasks"] = result["tasks"][:30]
        result["owners"] = result["owners"][:30]
        self.evidence[key] = {
            "id": key,
            "title": "گزارش فرایندهای ProcessMaker",
            "result": result,
        }
        self.trace.append(
            {"tool": name, "source_id": key, "filters": args.model_dump(mode="json")}
        )
        return {"source_id": key, **result}
