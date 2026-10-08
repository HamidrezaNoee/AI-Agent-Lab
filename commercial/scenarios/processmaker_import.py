"""Operator-run test importer. Dry-run by default; resumable, never routes cases."""

import argparse
from contextlib import contextmanager
from datetime import date
import getpass
import hashlib
import json
import os
from pathlib import Path
import re
from urllib.parse import urlsplit
import httpx
import jdatetime
from .generate import validate

PARENT_PROCESS = "f7f263ea31d8731d212820f220c65a48"
CHILD_PROCESS = "cd66870095907431106b6dd110e06fa7"
PARENT_TASK = "4a6419a60141d7d36001ba9344db4eac"
CHILD_TASK = "473bb4e227460a3ea6ac0f2cbf8ef8d4"


def uid(value):
    if not isinstance(value, str) or not re.fullmatch(r"[a-fA-F0-9]{32}", value):
        raise ValueError("A real 32-character ProcessMaker UID is required")
    return value


def jalali(value):
    return jdatetime.date.fromgregorian(date=date.fromisoformat(value)).strftime(
        "%Y/%m/%d"
    )


def parent_variables(dataset, scenario, mapping):
    actions = {
        str(i): {
            "MTG_ActionDecisionNo": a["decision_no"],
            "MTG_ActionNo": a["action_no"],
            "MTG_ActionDescription": a["description"],
            "MTG_ActionOwnerUID": mapping[a["owner_role"]],
            "MTG_ActionOwnerPosition": a["unit"],
            "MTG_persiandate_ActionDueDateTime": jalali(a["due_date"]),
            "MTG_ActionPriority": a["priority"],
        }
        for i, a in enumerate(scenario["actions"], 1)
    }
    return {
        "AVAN_TestDatasetID": dataset["dataset_id"],
        "AVAN_TestRecordKey": scenario["id"],
        "AVAN_IsSynthetic": True,
        "AVAN_ScenarioMetadata": json.dumps(scenario, ensure_ascii=False),
        "MTG_MeetingNo": scenario["id"],
        "MTG_MeetingTitle": "[آزمایشی] " + scenario["title"],
        "MTG_MeetingStartDateTime": scenario["date"],
        "MTG_persiandate_MeetingStartDateTime": jalali(scenario["date"]),
        "MTG_MeetingStartTime": "09:00",
        "MTG_MeetingEndTime": "10:30",
        "MTG_ChairUserUID": mapping["chair"],
        "MTG_SecretaryUserUID": mapping["secretary"],
        "MTG_MeetingStatus": "Open",
        "MTG_MinutesApproval": "Approved",
        "MTG_MeetingDiscussionSummary": scenario["discussion"],
        "MTG_ParkingLot": scenario["parking_lot"],
        "MTG_Participants": {
            str(i): {
                "MTG_ParticipantUserUID": mapping[r],
                "MTG_ParticipantPosition": r,
                "MTG_ParticipantRole": "Member",
                "MTG_ParticipantRequired": "1",
                "MTG_AttendanceStatus": "Present",
            }
            for i, r in enumerate(scenario["participants"], 1)
        },
        "MTG_Agenda": {
            str(i): {
                "MTG_AgendaNo": str(i),
                "MTG_AgendaTitle": t,
                "MTG_AgendaDescription": t,
                "MTG_AgendaPresenterUID": mapping["secretary"],
                "MTG_AgendaPlannedMinutes": "30",
            }
            for i, t in enumerate(scenario["agenda"], 1)
        },
        "MTG_Decisions": {
            str(i): {
                "MTG_DecisionNo": str(i),
                "MTG_DecisionAgendaNo": "1",
                "MTG_DecisionText": t,
                "MTG_DecisionRationale": scenario["constraint"],
            }
            for i, t in enumerate(scenario["decisions"], 1)
        },
        "MTG_Actions": actions,
        "MTG_ActionCaseMapJson": "{}",
    }


def child_variables(dataset, scenario, action, mapping, parent):
    last = action["reports"][-1] if action["reports"] else {}
    review = action["reviews"][-1] if action["reviews"] else {}
    return {
        "AVAN_TestDatasetID": dataset["dataset_id"],
        "AVAN_TestRecordKey": scenario["id"] + ":" + action["action_no"],
        "AVAN_IsSynthetic": True,
        "MTGA_ParentCaseUID": parent["app_uid"],
        "MTGA_ActionNo": action["action_no"],
        "MTGA_ActionDescription": action["description"],
        "MTGA_OwnerUserUID": mapping[action["owner_role"]],
        "MTGA_SecretaryUserUID": mapping["secretary"],
        "MTGA_DueDateTime": jalali(action["due_date"]),
        "MTGA_Priority": action["priority"],
        "MTGA_ProgressPercent": action["progress_percent"],
        "MTGA_LastSubmittedAt": last.get("submittedAt", ""),
        "MTGA_LastReviewedAt": review.get("reviewedAt", ""),
        "MTGA_ReviewStatus": review.get("reviewStatus", ""),
        "MTGA_SecretaryProgressPercent": review.get("progressPercent", ""),
        "MTGA_SubmissionHistoryJson": json.dumps(action["reports"], ensure_ascii=False),
        "MTGA_ReviewHistoryJson": json.dumps(action["reviews"], ensure_ascii=False),
        "MTGA_ContextMeetingNo": scenario["id"],
        "MTGA_ContextMeetingTitle": scenario["title"],
        "MTGA_ContextDiscussionSummary": scenario["discussion"],
        "MTGA_ContextParkingLot": scenario["parking_lot"],
    }


class Importer:
    def __init__(self, client, base, dataset, checkpoint, mapping):
        self.client, self.base, self.dataset, self.path, self.mapping = (
            client,
            base,
            dataset,
            Path(checkpoint),
            mapping,
        )
        stamp = hashlib.sha256(
            json.dumps(dataset, sort_keys=True, ensure_ascii=False).encode()
        ).hexdigest()
        expected = {"base": base, "dataset_sha256": stamp, "mapping": mapping}
        self.state = (
            json.loads(self.path.read_text())
            if self.path.exists()
            else {**expected, "records": {}}
        )
        if any(self.state.get(k) != v for k, v in expected.items()):
            raise ValueError(
                "Checkpoint belongs to different data, target, or user mapping"
            )

    def save(self):
        temp = self.path.with_suffix(".tmp")
        with temp.open("w", encoding="utf-8") as f:
            json.dump(self.state, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp, self.path)

    def request(self, method, path, **kwargs):
        response = self.client.request(method, self.base + path, **kwargs)
        if not 200 <= response.status_code < 300:
            # Avoid echoing remote credentials/error bodies. No automatic POST retry.
            raise ValueError(
                "ProcessMaker request failed: HTTP " + str(response.status_code)
            )
        return response.json() if response.content.strip() else {}

    def verify(self, key, app_uid):
        data = self.request("GET", "/cases/" + uid(app_uid) + "/variables")
        if (
            data.get("AVAN_TestDatasetID") != self.dataset["dataset_id"]
            or data.get("AVAN_TestRecordKey") != key
        ):
            raise ValueError("Remote case marker mismatch; refusing overwrite")
        return data

    def create(self, key, process, task, user, variables):
        previous = self.state["records"].get(key)
        if previous:
            if previous.get("status") == "pending":
                raise ValueError(
                    "Ambiguous prior create for "
                    + key
                    + ". Reconcile its case UID with --resolve before retrying."
                )
            self.verify(key, previous["app_uid"])
            return previous
        self.state["records"][key] = {"status": "pending"}
        self.save()
        data = self.request(
            "POST",
            "/cases/impersonate",
            json={
                "pro_uid": process,
                "tas_uid": task,
                "usr_uid": user,
                "variables": [variables],
            },
        )
        result = {
            "status": "created",
            "app_uid": uid(data["app_uid"]),
            "app_number": int(data["app_number"]),
        }
        self.state["records"][key] = result
        self.save()
        return result

    def resolve(self, key, app_uid):
        if self.state["records"].get(key, {}).get("status") != "pending":
            raise ValueError("Only a pending record can be reconciled")
        data = self.verify(key, app_uid)
        case = self.request("GET", "/cases/" + uid(app_uid))
        number = case.get("app_number") or case.get("APP_NUMBER")
        if not number:
            raise ValueError("Could not confirm case number")
        self.state["records"][key] = {
            "status": "created",
            "app_uid": app_uid,
            "app_number": int(number),
        }
        self.save()

    def run(self, scenarios):
        for scenario in scenarios:
            key = scenario["id"]
            variables = parent_variables(self.dataset, scenario, self.mapping)
            parent = self.create(
                key, PARENT_PROCESS, PARENT_TASK, self.mapping["secretary"], variables
            )
            actions = {}
            for action in scenario["actions"]:
                child = self.create(
                    key + ":" + action["action_no"],
                    CHILD_PROCESS,
                    CHILD_TASK,
                    self.mapping[action["owner_role"]],
                    child_variables(
                        self.dataset, scenario, action, self.mapping, parent
                    ),
                )
                actions[action["action_no"]] = {
                    "caseUid": child["app_uid"],
                    "caseNumber": child["app_number"],
                }
            self.verify(key, parent["app_uid"])
            self.request(
                "PUT",
                "/cases/" + parent["app_uid"] + "/variable?del_index=1",
                json={"MTG_ActionCaseMapJson": json.dumps(actions)},
            )
            self.state["records"][key]["linked"] = True
            self.save()
            print(key + " imported and linked (DRAFT, synthetic histories)")


@contextmanager
def checkpoint_lock(checkpoint):
    lock = Path(str(checkpoint) + ".lock")
    try:
        fd = os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        raise ValueError(
            "Another importer may be running. Verify it has stopped before removing "
            + str(lock)
        )
    try:
        with os.fdopen(fd, "w") as handle:
            handle.write(str(os.getpid()))
        yield
    finally:
        lock.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(
        description="AVAN isolated-test ProcessMaker importer; dry-run by default"
    )
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--mapping", required=True)
    parser.add_argument("--base-url")
    parser.add_argument("--workspace")
    parser.add_argument("--checkpoint", default="avan-import-checkpoint.json")
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--confirm-test-workspace")
    parser.add_argument("--allow-http", action="store_true")
    parser.add_argument(
        "--resolve", help="Reconcile an ambiguous KEY=APP_UID; no new case is created"
    )
    args = parser.parse_args()
    dataset = json.loads(Path(args.dataset).read_text(encoding="utf-8-sig"))
    validate(dataset)
    mapping = json.loads(Path(args.mapping).read_text(encoding="utf-8-sig"))
    if set(dataset["roles"]) - set(mapping):
        raise ValueError("Missing role mapping")
    for role in dataset["roles"]:
        uid(mapping[role])
    if not 1 <= args.limit <= len(dataset["scenarios"]):
        raise ValueError("Invalid scenario limit")
    scenarios = dataset["scenarios"][: args.limit]
    print(
        f'Plan: {len(scenarios)} meetings + {sum(len(s["actions"]) for s in scenarios)} action cases. No routing, explicit trigger calls or real evidence upload.'
    )
    if not args.apply:
        return
    if args.confirm_test_workspace != args.workspace or not re.fullmatch(
        r"[A-Za-z0-9_-]{1,48}", args.workspace or ""
    ):
        raise ValueError("Confirm the exact isolated test workspace before applying")
    parts = urlsplit(args.base_url or "")
    if (
        not parts.hostname
        or parts.username
        or parts.password
        or parts.query
        or parts.fragment
        or parts.path not in ("", "/")
        or parts.scheme not in ("https", "http")
        or parts.scheme == "http"
        and not args.allow_http
    ):
        raise ValueError(
            "Use a trusted HTTPS base URL; legacy HTTP needs explicit --allow-http"
        )
    token = os.environ.get("AVAN_PM_TEST_TOKEN") or getpass.getpass(
        "Test ProcessMaker OAuth access token: "
    )
    if not 8 <= len(token) <= 16000 or any(c in token for c in "\r\n"):
        raise ValueError("Invalid token")
    base = args.base_url.rstrip("/") + "/api/1.0/" + args.workspace
    with checkpoint_lock(args.checkpoint), httpx.Client(
        timeout=30,
        follow_redirects=False,
        trust_env=False,
        headers={"Authorization": "Bearer " + token},
    ) as client:
        importer = Importer(client, base, dataset, args.checkpoint, mapping)
        if args.resolve:
            key, app_uid = args.resolve.split("=", 1)
            importer.resolve(key, app_uid)
        else:
            importer.run(scenarios)


if __name__ == "__main__":
    try:
        main()
    except (ValueError, httpx.HTTPError, KeyError) as exc:
        raise SystemExit(
            "Import stopped. Check checkpoint and the selected test environment. "
            + str(exc)
            if isinstance(exc, ValueError)
            else "Import stopped; remote outcome may be uncertain. Keep checkpoint and reconcile before retry."
        )
