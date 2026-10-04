from copy import deepcopy
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, Mock
from types import SimpleNamespace as NS
from uuid import UUID
import json
import pytest
from fastapi.testclient import TestClient
from fastapi import HTTPException
from commercial.tests.test_production_agent import (
    state_dir,
    SCOPE,
    records,
    draft_data,
    NOW,
)
from commercial import (
    agent_workspace as workspace,
    agent_state,
    agent_monitor,
    agent_voice,
    agent_storage,
)
from commercial import agent_routes, production_app as web
from commercial.secretary_agent import (
    MinutesDraft,
    validate_edit,
    processmaker_export,
    candidate_owners,
)
from commercial.agent_reports import export_csv, csv_cell
from commercial.agent_tools import ActionQuery
from commercial.security import Principal, AuthenticationFailed


def test_conversation_survives_session_and_revocation_hides_every_answer(state_dir):
    answer = {
        "claims": [{"text": "authorized result", "kind": "fact", "sources": ["T:1"]}]
    }
    key, turn = workspace.save_turn(
        SCOPE, "actor", None, "پرسش درباره جلسه", answer, {1, 2}
    )
    web.sessions.clear()
    row = workspace.conversation(SCOPE, "actor", key, {1, 2})
    assert (
        row["turns"][0]["id"] == turn
        and "scope" not in workspace.public_conversation(row)["turns"][0]
    )
    for scope, actor, allowed in [
        (SCOPE, "other", {1, 2}),
        (SCOPE, "actor", {1}),
        ({**SCOPE, "role": "Manager"}, "actor", {1, 2}),
    ]:
        with pytest.raises(PermissionError):
            workspace.conversation(scope, actor, key, allowed)
    assert not any(
        b"authorized result" in value for value in state_dir["payloads"].values()
    )
    workspace.delete_conversation(SCOPE, "actor", key)
    assert workspace.conversations(SCOPE, "actor", {1, 2}) == []


def test_draft_edit_optimistic_revision_and_approved_immutability(state_dir):
    key = agent_state.save_draft(SCOPE, "actor", 1, draft_data())
    updated = agent_state.update_draft(
        SCOPE, "actor", key, {1}, {**draft_data(), "summary": "edited"}, 1
    )
    assert updated["revision"] == 2
    with pytest.raises(workspace.RevisionConflict):
        agent_state.approve_draft(SCOPE, "actor", key, {1}, 1)
    agent_state.approve_draft(SCOPE, "actor", key, {1}, 2)
    with pytest.raises(workspace.RevisionConflict):
        agent_state.update_draft(SCOPE, "actor", key, {1}, draft_data(), 2)
    assert agent_state.reopen_draft(SCOPE, "actor", key, {1}, 2)["revision"] == 3
    assert len(agent_state.list_drafts(SCOPE, "actor", {1})) == 1
    assert agent_state.list_drafts(SCOPE, "actor", {2}) == []


def test_editor_validates_quotes_owners_dates_and_native_export():
    data = draft_data()
    data["source_notes"] = "مصوب شد مجوز را پیگیری کند"
    candidates = [{"uid": "p1", "name": "مسئول"}]
    draft = MinutesDraft.model_validate(
        {k: data[k] for k in ("summary", "actions", "questions")}
    )
    draft.actions[0].needs_clarification = False
    draft.actions[0].priority = "urgent"
    payload = validate_edit(draft, data, candidates)
    meeting = records()[0]
    meeting["actions"][0]["action_no"] = "A-001"
    out = processmaker_export({"id": "draft", "payload": payload}, meeting, candidates)
    assert (
        out["operation"] == "append_after_review"
        and out["registration_status"] == "not_registered"
    )
    row = out["rows"]["1"]
    assert row["MTG_ActionNo"] == "A-002"
    assert row["MTG_ActionPriority"] == "High" and row[
        "MTG_persiandate_ActionDueDateTime"
    ].startswith("1405/")
    draft.actions[0].source_quote = "invented"
    with pytest.raises(ValueError):
        validate_edit(draft, data, candidates)
    with pytest.raises(ValueError):
        processmaker_export({"id": "draft", "payload": payload}, meeting, [])


def test_secretary_can_propose_participants_before_any_actions_exist():
    meeting = {"actions": [], "participant_uids": ["a", "b"]}
    scope = {
        "directory": {
            "a": {"name": "A", "active": True},
            "b": {"name": "B", "active": False},
        }
    }
    assert candidate_owners(meeting, scope) == [{"uid": "a", "name": "A", "unit": None}]


def test_durable_monitor_rotates_token_and_stops_on_revocation(state_dir):
    principal = Principal(UUID(SCOPE["tenant_id"]), "actor")
    session = {"refresh_token": "sensitive-token"}
    with patch.object(agent_monitor, "binding", return_value="bound"):
        public = agent_monitor.subscribe(SCOPE, "actor", session, True)
    assert (
        public["enabled"]
        and "refresh_token" not in public
        and "refresh_token" not in session
    )
    key = workspace.user_key("monitor_job", SCOPE, "actor")
    with patch.object(
        agent_monitor, "renewed_identity", return_value=(principal, "rotated")
    ) as renew, patch.object(agent_routes, "monitor_for", return_value={"total": 5}):
        agent_monitor.run_job(key, now=100)
    assert (
        renew.call_count == 1
        and agent_monitor.status(SCOPE, "actor")["last_count"] == 5
    )
    with patch.object(
        agent_monitor, "renewed_identity", side_effect=AuthenticationFailed("revoked")
    ), patch.object(agent_routes, "monitor_for") as read:
        agent_monitor.run_job(key, now=500)
        read.assert_not_called()
    state = agent_monitor.status(SCOPE, "actor")
    assert not state["enabled"] and state["last_error"] == "login_required"
    with agent_storage.transaction() as tx:
        assert tx.get(key)["refresh_token"] is None


def test_monitor_revalidates_mapping_and_handles_transient_failure(state_dir):
    session = {"refresh_token": "refresh"}
    with patch.object(agent_monitor, "binding", return_value="bound"):
        agent_monitor.subscribe(SCOPE, "actor", session, True)
    key = workspace.user_key("monitor_job", SCOPE, "actor")
    principal = Principal(UUID(SCOPE["tenant_id"]), "actor")
    with patch.object(
        agent_monitor, "renewed_identity", return_value=(principal, "rotated")
    ), patch.object(agent_routes, "monitor_for", side_effect=HTTPException(503)):
        agent_monitor.run_job(key, now=100)
    assert agent_monitor.status(SCOPE, "actor")["enabled"]
    with agent_storage.transaction() as tx:
        assert tx.get(key)["refresh_token"] == "rotated"
    with patch.object(
        agent_monitor, "renewed_identity", return_value=(principal, "rotated2")
    ), patch.object(agent_routes, "monitor_for", side_effect=HTTPException(403)):
        agent_monitor.run_job(key, now=500)
    assert not agent_monitor.status(SCOPE, "actor")["enabled"]


def test_monitor_old_refresh_not_forwarded_to_changed_identity_provider(state_dir):
    with patch.object(agent_monitor, "binding", return_value="old"):
        agent_monitor.subscribe(SCOPE, "actor", {"refresh_token": "refresh"}, True)
    with patch.object(agent_monitor, "binding", return_value="new"), pytest.raises(
        ValueError
    ):
        agent_monitor.subscribe(SCOPE, "actor", {}, True)


def test_alert_acknowledgement_is_actor_scoped_and_deduplicated(state_dir):
    alert = {"kind": "overdue", "source": {"id": "M:1:A:1"}}
    result = agent_state.alert_status(SCOPE, "actor", {"alerts": [deepcopy(alert)]})
    key = result["alerts"][0]["id"]
    agent_state.acknowledge(SCOPE, "actor", key)
    again = agent_state.alert_status(SCOPE, "actor", {"alerts": [deepcopy(alert)]})
    assert again["alerts"][0]["acknowledged"]
    assert not agent_state.alert_status(SCOPE, "other", {"alerts": [deepcopy(alert)]})[
        "alerts"
    ][0]["acknowledged"]


def test_csv_exports_all_filtered_rows_and_neutralizes_formulas():
    rows = records()
    rows[0]["actions"][0]["description"] = '  =HYPERLINK("bad")'
    result = export_csv(rows, SCOPE, False, ActionQuery(limit=1, group_by="unit")).decode("utf-8-sig")
    assert "'  =HYPERLINK" in result and "ناقص" in result and "A-4" in result
    for bad in ["=2+3", "+1", "-1", "@SUM(A1)", "\t=4", "   =7"]:
        assert csv_cell(bad).startswith("'")


def test_voice_validates_bytes_and_uses_sdk_without_writing_audio(state_dir):
    from commercial import setup_console as setup

    setup.put_setting("ai", {"voice_enabled": True})
    client = Mock()
    client.audio.transcriptions.create.return_value = NS(text="سؤال فارسی")
    data = b"\x1aE\xdf\xa3" + b"0" * 20
    with patch.object(agent_voice, "configured_client", return_value=(client, "test")):
        assert agent_voice.transcribe(data, "audio/webm") == "سؤال فارسی"
    assert client.audio.transcriptions.create.call_args.kwargs["language"] == "fa"
    client.close.assert_called_once()
    with pytest.raises(Exception):
        agent_voice.audio_format(b"fake" * 8, "audio/webm")
    # Current browser compatibility detects actual audio bytes when MIME is absent/wrong.
    assert agent_voice.audio_format(data, "text/plain") == ("webm", "audio/webm")
    parts = agent_voice.speech_parts(
        {"claims": [{"kind": "analysis", "text": "ا" * 7000}], "notes": []}
    )
    assert len(parts) == 3 and max(map(len, parts)) <= 3000


def test_new_routes_enforce_auth_before_any_provider_call():
    with TestClient(web.app, base_url="http://127.0.0.1:8188") as client:
        for path in ["/api/conversations", "/api/secretary/drafts", "/api/meetings/1"]:
            assert client.get(path).status_code == 401
        for path, body in [
            ("/api/bi/processes", {}),
            ("/api/reports/actions", {}),
            ("/api/voice/speech", {"conversation_id": "x", "turn_id": "y"}),
        ]:
            assert client.post(path, json=body).status_code == 401
        assert (
            client.post(
                "/api/voice/transcribe",
                content=b"x" * 32,
                headers={"content-type": "audio/webm"},
            ).status_code
            == 401
        )


def test_grouped_report_still_provides_action_detail_rows():
    from commercial.agent_reports import report
    result=report(records(),SCOPE,True,ActionQuery(group_by='unit',limit=2))
    assert result['groups'] and len(result['rows'])==2 and result['has_more']


def test_monitor_delegated_token_rotates_for_workspace_and_ends_on_logout(state_dir):
    session = {"refresh_token": "first-credential"}
    with patch.object(agent_monitor, "binding", return_value="bound"):
        agent_monitor.subscribe(SCOPE, "actor", session, True)
    assert session["monitor_delegated"] and "refresh_token" not in session
    principal = Principal(UUID(SCOPE["tenant_id"]), "actor")
    result = (principal, "rotated-credential", {"access_token": "new-access"})
    with patch.object(agent_monitor, "renewed_identity", return_value=result):
        assert agent_monitor.renew_for_session(session)["access_token"] == "new-access"
    key = workspace.user_key("monitor_job", SCOPE, "actor")
    with agent_storage.transaction() as tx:
        assert tx.get(key)["refresh_token"] == "rotated-credential"
    agent_monitor.end_session_delegation(session)
    with agent_storage.transaction() as tx:
        job = tx.get(key)
        assert not job["enabled"] and job["refresh_token"] is None


def test_drafts_and_alerts_are_isolated_between_bpms_sources(state_dir):
    other={**SCOPE,"source_id":"b"*24,"external_user_id":"p1"}
    draft=agent_state.save_draft(SCOPE,"actor",1,draft_data())
    with pytest.raises(PermissionError):
        agent_state.get_draft(other,"actor",draft,{1})
    assert agent_state.list_drafts(other,"actor",{1})==[]

    alert={"kind":"overdue","source":{"id":"M:1:A:1"}}
    first=agent_state.alert_status(SCOPE,"actor",{"alerts":[deepcopy(alert)]})
    identifier=first["alerts"][0]["id"]
    agent_state.acknowledge(SCOPE,"actor",identifier)
    second=agent_state.alert_status(other,"actor",{"alerts":[deepcopy(alert)]})
    assert second["alerts"][0]["id"]==identifier
    assert not second["alerts"][0]["acknowledged"]


def test_monitor_keeps_independent_source_subscriptions_under_one_credential(state_dir):
    first={**SCOPE,"source_id":"a"*24}
    second={**SCOPE,"source_id":"b"*24}
    session={"refresh_token":"shared-rotating-credential"}
    with patch.object(agent_monitor,"binding",return_value="bound"):
        a=agent_monitor.subscribe(first,"actor",session,True,300)
        b=agent_monitor.subscribe(second,"actor",session,True,900)
    assert a["enabled"] and b["enabled"]
    assert "refresh_token" not in session
    assert agent_monitor.status(first,"actor")["interval_seconds"]==300
    assert agent_monitor.status(second,"actor")["interval_seconds"]==900

    key=workspace.user_key("monitor_job",first,"actor")
    with agent_storage.transaction() as tx:
        job=tx.get(key)
    assert set(job["subscriptions"])=={"a"*24,"b"*24}
    assert job["enabled"] is True

    with patch.object(agent_monitor,"binding",return_value="bound"):
        agent_monitor.subscribe(first,"actor",session,False,300)
    assert not agent_monitor.status(first,"actor")["enabled"]
    assert agent_monitor.status(second,"actor")["enabled"]
    assert session.get("monitor_delegated") is True

