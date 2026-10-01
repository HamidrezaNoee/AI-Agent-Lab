"""Read-only connector boundaries and GodAdmin separation from PM data."""
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from commercial import bpms_registry,platform_agent,production_app,setup_console,setup_routes


TENANT="168418b2-8fa6-4414-a37f-83c9a26da332"
TOKEN="0123456789-secret-token"
CONFIG={"name":"External BPMS","base_url":"https://bpms.example.org",
        "bearer_token":TOKEN,"enabled":True}


def test_adapter_requires_https_and_rejects_direct_loopback():
    for url in ("http://bpms.example.org","https://127.0.0.1",
                "https://localhost","https://bpms.example.org:7777",
                "https://username:secret@bpms.example.org"):
        with pytest.raises(ValidationError):bpms_registry.SourceConfig(**{**CONFIG,"base_url":url})


def test_source_save_masks_token_and_checks_tenant_before_persisting():
    settings={"company":{"tenant_id":TENANT}}
    with patch.object(setup_console,"get_setting",side_effect=settings.get),\
         patch.object(setup_console,"put_setting",side_effect=lambda k,v:settings.__setitem__(k,v)),\
         patch.object(bpms_registry,"_request",return_value={"schema_version":1,"tenant_id":TENANT}) as fetch:
        saved=bpms_registry.save(bpms_registry.SourceConfig(**CONFIG))
        assert saved["saved"]
        assert bpms_registry.sources()[0]["has_token"]
        assert TOKEN not in str(bpms_registry.sources())
        assert fetch.call_args[0][1]=="/avan/v1/identity"
        assert bpms_registry.signature()==platform_agent.scope(SimpleNamespace(tenant_id=TENANT))["visible_uids"][0]
        candidate=bpms_registry.SourceConfig(id=saved["id"],**{**CONFIG,"bearer_token":""})
        bpms_registry.save(candidate)
        assert settings["bpms_connections"]["sources"][0]["bearer_token"]==TOKEN
        with pytest.raises(bpms_registry.BPMSUnavailable):
            bpms_registry.save(bpms_registry.SourceConfig(id=saved["id"],
                **{**CONFIG,"base_url":"https://new.example.org","bearer_token":""}))
        fetch.return_value={"schema_version":1,"tenant_id":"different"}
        with pytest.raises(bpms_registry.BPMSUnavailable):bpms_registry.save(candidate)


def test_source_disable_reenable_and_delete_preserve_isolation():
    settings={"company":{"tenant_id":TENANT}}
    with patch.object(setup_console,"get_setting",side_effect=settings.get),\
         patch.object(setup_console,"put_setting",side_effect=lambda k,v:settings.__setitem__(k,v)),\
         patch.object(bpms_registry,"identity",return_value={"connected":True}) as verify:
        source_id=bpms_registry.save(bpms_registry.SourceConfig(**CONFIG))["id"]
        assert verify.call_count==1
        first=bpms_registry.signature()
        assert bpms_registry.set_enabled(source_id,False)=={"id":source_id,"enabled":False}
        assert verify.call_count==1  # disabling works while the remote BPMS is offline
        assert bpms_registry.signature()!=first
        assert bpms_registry.sources()[0]["has_token"]
        with pytest.raises(bpms_registry.BPMSUnavailable):
            bpms_registry.report(bpms_registry.BIRequest(source_id=source_id))
        verify.side_effect=bpms_registry.BPMSUnavailable("unavailable")
        with pytest.raises(bpms_registry.BPMSUnavailable):bpms_registry.set_enabled(source_id,True)
        assert bpms_registry.sources()[0]["enabled"] is False
        verify.side_effect=None
        assert bpms_registry.set_enabled(source_id,True)["enabled"] is True
        assert verify.call_count==3
        assert bpms_registry.delete(source_id)=={"deleted":True}
        assert bpms_registry.sources()==[]


def test_saved_processmaker_checks_use_server_secrets_without_browser_echo():
    settings={"mysql":{"host":"host.docker.internal","port":3306,"database":"bitnami_pm",
                       "username":"avan_reader","password":"secret","tls":False,
                       "timezone":"Asia/Tehran"},
              "processmaker":{"base_url":"https://pm.example.org","workspace":"workflow",
                              "bearer_token":"secret-token"}}
    app=production_app.app
    app.dependency_overrides[setup_routes._ready]=lambda:True
    try:
        with patch.object(setup_console,"get_setting",side_effect=settings.get),\
             patch.object(setup_routes,"_mysql_check",return_value={"connected":True}) as mysql,\
             patch.object(setup_routes,"_pm_directory_check",return_value=200) as pm:
            client=TestClient(app,base_url="http://127.0.0.1:8188")
            try:
                assert client.post("/admin/api/mysql/check-saved").json()=={"connected":True}
                assert mysql.call_args.args[0].password=="secret"
                assert client.post("/admin/api/processmaker/check-saved").json()["connected"]
                assert pm.call_args.args==("https://pm.example.org","workflow","secret-token")
            finally:client.close()
    finally:app.dependency_overrides.clear()


def test_report_rejects_wrong_tenant_and_oversized_page():
    source={**CONFIG,"id":"a"*24,"kind":"avan-rest-v1"}
    payload={"schema_version":1,"tenant_id":TENANT,"as_of_utc":"2026-09-28T12:00:00Z",
             "coverage_complete":True,
             "metrics":{"cases":1,"open_cases":1,"completed_cases":0,"open_tasks":1,"overdue_tasks":0},
             "processes":[],"rows":[],"statuses":{}}
    with patch.object(setup_console,"get_setting",side_effect={
        "company":{"tenant_id":TENANT},"bpms_connections":{"sources":[source]}}.get),\
         patch.object(bpms_registry,"_request",return_value=payload) as fetch:
        r=bpms_registry.report(bpms_registry.BIRequest(source_id="a"*24))
        assert r["metrics"]["cases"]==1
        assert fetch.call_args[0][1]=="/avan/v1/bi/processes"
        payload["tenant_id"]="wrong"
        with pytest.raises(bpms_registry.BPMSUnavailable):bpms_registry.report(bpms_registry.BIRequest(source_id="a"*24))
        payload["tenant_id"]=TENANT
        payload["rows"]=[{"case_uid":str(i),"case_number":str(i),"process_uid":"p",
                          "process_title":"فرایند","status":"TO_DO"} for i in range(31)]
        with pytest.raises(bpms_registry.BPMSUnavailable):bpms_registry.report(bpms_registry.BIRequest(source_id="a"*24,limit=30))


def test_platform_endpoint_is_godadmin_only_and_pm_endpoint_stays_blocked():
    principal=SimpleNamespace(subject="admin",tenant_id=TENANT)
    session={"csrf":"secret","access_token":"jwt"}
    service=production_app.app
    with patch.object(setup_console,"godadmin_identity",return_value={"subject":"admin"}),\
         patch.object(setup_console,"is_godadmin",side_effect=lambda p:p.subject=="admin"),\
         patch.object(production_app,"_principal_for_request",return_value=("session",session,principal)),\
         patch.object(setup_console,"get_setting",side_effect={"ai":{},"company":{"tenant_id":TENANT}}.get):
        with TestClient(service,base_url="http://127.0.0.1:8188") as client:
            status=client.get("/api/platform/status")
            assert status.status_code==200
            assert status.json()["processmaker_access"] is False
            assert client.get("/api/meetings").status_code==403
            with patch.object(setup_console,"is_godadmin",return_value=False):
                assert client.get("/api/platform/status").status_code==403


def test_godadmin_assistant_works_without_processmaker_connection():
    principal=SimpleNamespace(subject="admin",tenant_id=TENANT)
    session={"csrf":"secret","access_token":"jwt"}
    verifier=SimpleNamespace(authenticate=lambda _:principal)
    with patch.object(setup_console,"godadmin_identity",return_value={"subject":"admin"}),\
         patch.object(setup_console,"is_godadmin",return_value=True),\
         patch.object(production_app,"_principal_for_request",return_value=("session",session,principal)),\
         patch.object(production_app,"_oidc_config",return_value=(None,None,None,None,verifier)),\
         patch.object(setup_console,"get_setting",side_effect={"company":{"tenant_id":TENANT}}.get),\
         patch.object(platform_agent,"answer",return_value={"answer":"راهنمای اتصال", "claims":[],"notes":[]}),\
         patch("commercial.agent_workspace.save_turn",return_value=("conversation","turn")),\
         patch.object(production_app,"open_production",side_effect=AssertionError("PM read was attempted")):
        with TestClient(production_app.app,base_url="http://127.0.0.1:8188") as client:
            response=client.post("/api/platform/ask",json={"question":"روش اتصال چیست؟"},
                                 headers={"X-AVAN-CSRF":"secret"})
            assert response.status_code==200,response.text
            assert response.json()["answer"]=="راهنمای اتصال"
            assert client.post("/api/platform/ask",json={"question":"روش اتصال چیست؟"}).status_code==403
