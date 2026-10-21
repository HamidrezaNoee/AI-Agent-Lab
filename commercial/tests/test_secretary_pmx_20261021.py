"""Guard the shipped AVAN PMX descriptors against the 2026-10-21 exports.

Raw customer PMX XML and trigger source must not be committed.
"""
from pathlib import Path
import json


ROOT = Path(__file__).resolve().parents[1]
REVIEW = ROOT.parent / "docs" / "processmaker" / "review-20261021.json"


def test_current_pmx_review_matches_shipped_seven_stage_contract():
    descriptor = json.loads((ROOT / "secretary_pack_reference.json").read_text(encoding="utf-8"))
    review = json.loads(REVIEW.read_text(encoding="utf-8"))
    assert review["review_date"] == "2026-10-21"
    assert review["live_verified"] is False
    assert {p["process_uid"] for p in review["processes"]} == {
        "f7f263ea31d8731d212820f220c65a48",
        "cd66870095907431106b6dd110e06fa7",
        "44896d94f59e4f9191b23f967cc5cd5b",
    }
    lookup = {p["process_uid"]: p for p in review["processes"]}
    for key in ("meeting", "action"):
        source = descriptor[key]
        current = lookup[source["process_uid"]]
        assert current["sha256"] == source["pmx_sha256"]
        assert {t["uid"]: t["sha256"] for t in current["triggers"]} == source["trigger_hashes"]
        assert {route["tas_uid"] for route in current["routes"]} <= {
            t["task_uid"] for t in source["stages"].values()
        }
    assert set(descriptor["stages"]) == {
        "invitation", "invitation_approval", "minutes", "minutes_approval",
        "monitoring", "action_execution", "action_review",
    }


def test_current_pmx_native_files_share_ids_and_preserve_notice_digest():
    descriptor = json.loads((ROOT / "secretary_pack_reference.json").read_text(encoding="utf-8"))
    stages = descriptor["stages"]
    assert (
        stages["minutes"]["fields"]["MTG002_MeetingAttachment"]["inp_doc_uid"]
        == stages["minutes_approval"]["fields"]["MTG002_MeetingAttachment"]["inp_doc_uid"]
        == "8069894396a958d0a5007d7087550366"
    )
    assert (
        stages["action_execution"]["fields"]["MTGA_EvidenceFile1"]["inp_doc_uid"]
        == stages["action_review"]["fields"]["MTGA_EvidenceFile1"]["inp_doc_uid"]
        == "6343078616ac0d6c53a98d9079721622"
    )
    assert descriptor["meeting"]["trigger_hashes"][
        "91931df32c7d442392b95defbf4b3677"
    ] == "599166f9cb7e09a0e60955936004e738058517ba5da2b3ab0791b723d0a0776f"
