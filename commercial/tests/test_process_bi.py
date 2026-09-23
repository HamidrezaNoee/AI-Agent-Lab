from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from unittest.mock import patch
import pytest
from commercial.process_bi import BIQuery, case_predicate, summarize, load
from commercial.tests.test_production_agent import SCOPE


def test_bi_visibility_is_exact_membership_and_parameters_are_bound():
    scope = {**SCOPE, "visible_uids": {"a" * 32}}
    with patch(
        "commercial.process_bi.get_setting", return_value={"timezone": "Asia/Tehran"}
    ):
        sql, args, tz = case_predicate(
            scope, BIQuery(period="all"), datetime.now(timezone.utc)
        )
    assert "EXISTS" in sql and "APP_INIT_USER IN" in sql
    assert "a" * 32 not in sql and args == ["a" * 32, "a" * 32]
    with pytest.raises(Exception):
        BIQuery(process_uid="' OR 1=1")
    with pytest.raises(Exception):
        BIQuery(start="2026-09-22")


def test_bi_parallel_tasks_do_not_inflate_cases_and_closed_cases_not_overdue():
    cases = [
        ("c1", 1, "p", "TO_DO", "u", "2026-09-01 09:00:00", None, "فرایند"),
        (
            "c2",
            2,
            "p",
            "COMPLETED",
            "u",
            "2026-09-01 09:00:00",
            "2026-09-03 09:00:00",
            "فرایند",
        ),
    ]
    delegations = [
        (
            "c1",
            1,
            "t1",
            "u",
            "OPEN",
            "2026-09-01 09:00:00",
            None,
            None,
            "2026-09-02 00:00:00",
            "بررسی",
        ),
        (
            "c1",
            2,
            "t2",
            "u",
            "OPEN",
            "2026-09-01 09:00:00",
            None,
            None,
            "2026-10-02 00:00:00",
            "تأیید",
        ),
        (
            "c2",
            1,
            "t1",
            "u",
            "OPEN",
            "2026-09-01 09:00:00",
            None,
            None,
            "2026-09-02 00:00:00",
            "بررسی",
        ),
    ]
    r = summarize(
        cases,
        delegations,
        SCOPE,
        BIQuery(),
        datetime(2026, 9, 22, tzinfo=timezone.utc),
        ZoneInfo("Asia/Tehran"),
    )
    assert (
        r["metrics"]["cases"] == 2
        and r["metrics"]["open_tasks"] == 2
        and r["metrics"]["overdue_tasks"] == 1
    )
    assert r["metrics"]["average_cycle_hours"] == 48
    assert len(r["rows"]) == 2 and r["owners"][0]["open"] == 2


def test_bi_does_not_read_case_payload_or_unlicensed_data():
    with patch("commercial.process_bi.query") as q:
        with pytest.raises(Exception):
            load(None, {**SCOPE, "license": {"modules": [1]}}, BIQuery())
        q.assert_not_called()
    with patch("commercial.process_bi.query", return_value=[]) as q, patch(
        "commercial.process_bi.get_setting", return_value={}
    ):
        load(None, {**SCOPE, "role": "SysAdmin"}, BIQuery())
        assert "APP_DATA" not in q.call_args.args[1]


def test_bi_agent_calls_typed_tool_and_returns_verified_evidence():
    from commercial.process_bi import ProcessBITools
    from commercial.meeting_agent import run_agent
    from commercial.tests.test_production_agent import fake_client, response, final

    def provider(args):
        assert args.period == "all"
        return {
            "_case_uids": ["authorized-case"],
            "coverage_complete": True,
            "metrics": {"cases": 7},
            "processes": [],
            "tasks": [],
            "owners": [],
        }

    tools = ProcessBITools(provider)
    client = fake_client(
        [
            response(call=("analyze_processes", {"period": "all"})),
            response(answer=final()),
        ]
    )
    result = run_agent("وضعیت همه فرایندها چیست؟", tools, client=client, model="test")
    assert result["evidence"][0]["result"]["metrics"]["cases"] == 7
    assert tools.access[0][1] == {"authorized-case"}
    assert "_case_uids" not in str(result["evidence"])
    with pytest.raises(ValueError):
        tools.execute("execute_sql", {})
