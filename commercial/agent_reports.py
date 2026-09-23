"""Deterministic, permission-scoped report and spreadsheet-safe CSV export."""

import csv
import io
from .agent_tools import ActionQuery, MeetingTools


def report(rows, scope, complete, arguments):
    tools = MeetingTools(rows, complete=complete, modules=scope["license"]["modules"])
    result = tools.execute("analyze_actions", arguments.model_dump())
    if arguments.group_by != "none":
        detail = tools.actions(arguments.model_copy(update={"group_by": "none"}))
        result.update({k: detail[k] for k in ("rows", "has_more", "next_offset")})
    return result


def csv_cell(value):
    if value is None:
        return ""
    text = str(value)
    # Spreadsheet programs also interpret formulas after whitespace/control chars.
    if text.lstrip().startswith(("=", "+", "-", "@")) or text.startswith(
        ("\t", "\r", "\n")
    ):
        return "'" + text
    return text


def export_csv(rows, scope, complete, arguments):
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer)
    writer.writerow(
        ["پوشش گزارش", "کامل" if complete else "ناقص؛ فقط داده‌های بازیابی‌شده"]
    )
    writer.writerow(
        [
            "شماره جلسه",
            "شماره اقدام",
            "شرح",
            "مسئول",
            "واحد",
            "وضعیت",
            "پیشرفت",
            "موعد",
            "روز تأخیر",
        ]
    )
    offset = 0
    while True:
        page = report(
            rows,
            scope,
            complete,
            arguments.model_copy(update={"offset": offset, "limit": 30, "group_by": "none"}),
        )
        for row in page["rows"]:
            writer.writerow(
                [
                    csv_cell(v)
                    for v in [
                        row["source"]["meeting_no"],
                        row["source"]["action_no"],
                        row["description"],
                        row["owner_name"],
                        row["unit"],
                        row["status"],
                        row["progress_percent"],
                        row["due_at_utc"],
                        row["overdue_days"],
                    ]
                ]
            )
        if not page["has_more"]:
            break
        offset += 30
        if offset > 20000:
            raise ValueError("Export bound exceeded")
    return ("\ufeff" + buffer.getvalue()).encode("utf-8")
