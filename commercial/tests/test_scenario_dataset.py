from pathlib import Path
from datetime import date, datetime, timezone
from unittest.mock import patch
import json
import httpx
import phpserialize
import pytest
from commercial.scenarios.generate import build, validate
from commercial.scenarios.processmaker_import import (
    Importer,
    parent_variables,
    child_variables,
)
from commercial import processmaker_store
from commercial.agent_tools import MeetingTools, ActionQuery


@pytest.fixture(scope="module")
def dataset():
    return build(date(2026, 9, 22))


def mapping_for(dataset):
    return {role: ("%032x" % (i + 1)) for i, role in enumerate(dataset["roles"])}


def test_all_1008_scenarios_are_unique_and_complete(dataset):
    result = validate(dataset)
    assert (
        result["scenarios"] == 1008
        and result["actions"] == 4032
        and result["domains"] == 21
    )
    assert len(result["outcomes"]) == 8
    for scenario in dataset["scenarios"]:
        assert all(
            int(a["decision_no"]) <= len(scenario["decisions"])
            for a in scenario["actions"]
        )
        assert all(
            a["hypothetical_evidence"][0]["hypothetical"] for a in scenario["actions"]
        )


def test_entire_dataset_passes_native_parser_and_expected_management_metrics(dataset):
    mapping = mapping_for(dataset)
    scope = {
        "role": "SysAdmin",
        "directory": {u: {"name": role, "unit": role} for role, u in mapping.items()},
        "staff": {},
    }
    total = {"open": 0, "closed": 0, "overdue": 0}
    for number, scenario in enumerate(dataset["scenarios"], 1):
        parent_uid = "%032x" % (100000 + number)
        parent = parent_variables(dataset, scenario, mapping)
        p = (parent_uid, number, "DRAFT", phpserialize.dumps(parent))
        children = []
        for index, action in enumerate(scenario["actions"], 1):
            variables = child_variables(
                dataset, scenario, action, mapping, {"app_uid": parent_uid}
            )
            children.append(
                (
                    "%032x" % (200000 + number * 4 + index),
                    10000 + number * 4 + index,
                    "DRAFT",
                    phpserialize.dumps(variables),
                    scenario["date"] + " 00:00:00",
                )
            )
        with patch.object(processmaker_store, "query", side_effect=[[p], children]):
            rows, complete = processmaker_store.authorized_meeting_snapshot(None, scope)
        result = MeetingTools(
            rows, now=datetime(2026, 9, 22, 12, tzinfo=timezone.utc)
        ).actions(ActionQuery())
        for key in total:
            assert result["metrics"][key] == scenario["expected"][key], (
                scenario["id"],
                key,
                result["metrics"],
            )
            total[key] += result["metrics"][key]
    assert total["closed"] == 504 and total["open"] == 3528 and total["overdue"] == 3024


def test_import_resume_does_not_duplicate_and_parent_map_is_native(dataset, tmp_path):
    remote = {}
    calls = []

    def respond(request):
        calls.append(request.method + " " + request.url.path)
        if request.method == "POST":
            body = json.loads(request.content)
            n = len(remote) + 1
            key = "%032x" % n
            remote[key] = body["variables"][0]
            return httpx.Response(200, json={"app_uid": key, "app_number": n})
        key = request.url.path.split("/cases/")[1].split("/")[0]
        if request.method == "GET":
            return httpx.Response(200, json=remote[key])
        remote[key].update(json.loads(request.content))
        return httpx.Response(200)

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        importer = Importer(
            client,
            "https://pm.test/api/1.0/test",
            dataset,
            tmp_path / "checkpoint.json",
            mapping_for(dataset),
        )
        importer.run(dataset["scenarios"][:1])
        Importer(
            client,
            "https://pm.test/api/1.0/test",
            dataset,
            tmp_path / "checkpoint.json",
            mapping_for(dataset),
        ).run(dataset["scenarios"][:1])
    assert len(remote) == 5 and sum(c.startswith("POST") for c in calls) == 5
    parent = remote["%032x" % 1]
    assert len(json.loads(parent["MTG_ActionCaseMapJson"])) == 4
    assert not any("route-case" in c or "execute-trigger" in c for c in calls)


def test_ambiguous_create_stops_without_automatic_retry(dataset, tmp_path):
    calls = []

    def timeout(request):
        calls.append(request)
        raise httpx.ReadTimeout("timeout")

    with httpx.Client(transport=httpx.MockTransport(timeout)) as client:
        importer = Importer(
            client,
            "https://pm.test/api/1.0/test",
            dataset,
            tmp_path / "checkpoint.json",
            mapping_for(dataset),
        )
        with pytest.raises(httpx.ReadTimeout):
            importer.run(dataset["scenarios"][:1])
        with pytest.raises(ValueError, match="Ambiguous"):
            importer.run(dataset["scenarios"][:1])
    assert len(calls) == 1


def test_concurrent_importer_is_blocked_and_lock_released(tmp_path):
    from commercial.scenarios.processmaker_import import checkpoint_lock

    path = tmp_path / "checkpoint.json"
    with checkpoint_lock(path):
        with pytest.raises(ValueError, match="Another importer"):
            with checkpoint_lock(path):
                pass
    with checkpoint_lock(path):
        pass
    assert not Path(str(path) + ".lock").exists()
