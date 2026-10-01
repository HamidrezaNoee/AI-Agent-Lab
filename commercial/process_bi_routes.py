from fastapi import Depends, HTTPException
from fastapi.responses import Response
from .process_bi import BIQuery, load
from .agent_reports import csv_cell


def register(app, csrf):
    @app.post("/api/bi/processes")
    def processes(body: BIQuery, value=Depends(csrf)):
        from .production_app import _store_response

        return _store_response(lambda con, scope: load(con, scope, body), value[2])

    @app.post("/api/bi/processes/export")
    def export(body: BIQuery, value=Depends(csrf)):
        import csv, io

        report = processes(body, value)
        out = io.StringIO(newline="")
        writer = csv.writer(out)
        writer.writerow(["پوشش", "کامل" if report["coverage_complete"] else "ناقص"])
        writer.writerow(
            [
                "فرایند",
                "کل",
                "باز",
                "تکمیل",
                "لغو",
                "پیش‌نویس",
                "وظایف تأخیردار",
                "میانگین چرخه (ساعت)",
            ]
        )
        for p in report["processes"]:
            writer.writerow(
                [
                    csv_cell(p[k])
                    for k in (
                        "title",
                        "total",
                        "open",
                        "completed",
                        "cancelled",
                        "draft",
                        "overdue_tasks",
                        "average_cycle_hours",
                    )
                ]
            )
        return Response(
            ("\ufeff" + out.getvalue()).encode("utf-8"),
            media_type="text/csv; charset=utf-8",
            headers={
                "Content-Disposition": 'attachment; filename="processmaker-bi.csv"'
            },
        )

    @app.post("/api/sources/{source_id}/bi/processes")
    def source_processes(source_id: str, body: BIQuery, value=Depends(csrf)):
        from .production_app import _source_store_response
        return _source_store_response(
            source_id,lambda con,scope:load(con,scope,body),value[2]
        )

    @app.post("/api/sources/{source_id}/bi/processes/export")
    def source_export(source_id: str, body: BIQuery, value=Depends(csrf)):
        import csv, io

        report=source_processes(source_id,body,value)
        out=io.StringIO(newline="")
        writer=csv.writer(out)
        writer.writerow(["پوشش","کامل" if report["coverage_complete"] else "ناقص"])
        writer.writerow([
            "فرایند","کل","باز","تکمیل","لغو","پیش‌نویس",
            "وظایف تأخیردار","میانگین چرخه (ساعت)"
        ])
        for p in report["processes"]:
            writer.writerow([csv_cell(p[k]) for k in (
                "title","total","open","completed","cancelled","draft",
                "overdue_tasks","average_cycle_hours"
            )])
        return Response(
            ("\ufeff"+out.getvalue()).encode("utf-8"),
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition":
                     'attachment; filename="processmaker-source-bi.csv"'},
        )

    from .agent_routes import Question, guard_model

    @app.post("/api/bi/ask")
    def ask(body: Question, value=Depends(csrf)):
        from .production_app import _store_response, _oidc_config
        from .process_bi import ProcessBITools
        from .meeting_agent import run_agent, run_slot
        from .agent_workspace import scope_stamp
        from . import agent_state

        principal = value[2]

        def work():
            with run_slot((str(principal.tenant_id), principal.subject)):
                initial = _store_response(lambda con, scope: scope, principal)
                if 3 not in initial["license"]["modules"]:
                    raise HTTPException(403, "ماژول BI در لایسنس فعال نیست.")

                def provider(args):
                    return _store_response(
                        lambda con, scope: load(
                            con, scope, args, include_access_ids=True
                        ),
                        principal,
                    )

                tools = ProcessBITools(provider)
                result = run_agent(body.question, tools)
                _oidc_config()[4].authenticate("Bearer " + value[1]["access_token"])
                current = _store_response(lambda con, scope: scope, principal)
                if scope_stamp(initial) != scope_stamp(current):
                    raise HTTPException(403, "دامنه دسترسی تغییر کرده است.")
                for args, old_ids in tools.access:
                    if not old_ids <= set(provider(args)["_case_uids"]):
                        raise HTTPException(
                            403,
                            "دسترسی پرونده‌ها تغییر کرده است؛ پرسش را دوباره اجرا کنید.",
                        )
                agent_state.audit(
                    current,
                    principal.subject,
                    "BI_AGENT_COMPLETED",
                    {"model": result["model"], **result["usage"]},
                )
                return {**result, "report_type": "process_bi"}

        return guard_model(work)
