"""Disabling operational sources fails closed without deleting source databases."""
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from commercial import processmaker_store,production_app,setup_console,setup_routes


@pytest.fixture
def admin_settings(tmp_path):
    root=Path(tmp_path)
    names={"ROOT":root,"SQLITE":root/"setup.sqlite3","KEYFILE":root/"setup.key",
           "INITIAL":root/"initial-godadmin-password","PUBLIC":root/"license-public.pem"}
    patches=[patch.object(setup_console,key,value) for key,value in names.items()]
    for item in patches:item.start()
    setup_console.initialize()
    app=production_app.app
    old_overrides=dict(app.dependency_overrides)
    app.dependency_overrides[setup_routes._ready]=lambda:True
    try:yield TestClient(app,base_url="http://127.0.0.1:8188")
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(old_overrides)
        for item in reversed(patches):item.stop()


def test_mysql_disable_enable_and_remove_are_scoped_to_saved_config(admin_settings):
    setup_console.put_setting("mysql",{"host":"host.docker.internal","port":3306,
        "database":"bitnami_pm","username":"avan_reader","password":"kept-secret",
        "tls":False,"timezone":"Asia/Tehran"})
    client=admin_settings
    assert client.post("/admin/api/mysql/enabled",json={"enabled":False}).status_code==200
    saved=setup_console.get_setting("mysql")
    assert saved["password"]=="kept-secret" and saved["enabled"] is False
    with pytest.raises(processmaker_store.ProductionUnavailable):
        with processmaker_store.open_production():pass
    with patch.object(setup_routes,"_mysql_check",side_effect=HTTPException(503,"offline")):
        assert client.post("/admin/api/mysql/enabled",json={"enabled":True}).status_code==503
    assert setup_console.get_setting("mysql")["enabled"] is False
    with patch.object(setup_routes,"_mysql_check",return_value={"connected":True}) as check:
        assert client.post("/admin/api/mysql/enabled",json={"enabled":True}).json()["enabled"]
        assert check.call_args.args[0].password=="kept-secret"
    assert setup_console.get_setting("mysql")["enabled"] is True
    assert client.post("/admin/api/mysql/remove",json={"confirmation":"REMOVE_AI_KEY"}).status_code==422
    assert client.post("/admin/api/mysql/remove",json={"confirmation":"REMOVE_MYSQL_SOURCE"}).json()["deleted"]
    assert setup_console.get_setting("mysql")=={}


def test_singleton_pm_api_and_ai_secrets_can_be_removed(admin_settings):
    setup_console.put_setting("processmaker",{"base_url":"https://pm.example.org",
         "workspace":"workflow","bearer_token":"sample-token"})
    setup_console.put_setting("ai",{"enabled":True,"voice_enabled":True,
         "api_key":"sample-ai-secret","model":"gpt-4.1-mini"})
    client=admin_settings
    assert client.post("/admin/api/processmaker/remove",
         json={"confirmation":"REMOVE_PM_API"}).json()["deleted"]
    assert setup_console.get_setting("processmaker")=={}
    assert client.post("/admin/api/ai/remove",json={"confirmation":"REMOVE_AI_KEY"}).json()["deleted"]
    saved=setup_console.get_setting("ai")
    assert saved["api_key"]=="" and not saved["enabled"] and not saved["voice_enabled"]
