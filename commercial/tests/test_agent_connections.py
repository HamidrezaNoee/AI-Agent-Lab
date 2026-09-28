"""Connection catalog guarantees for bundled and external Agent databases."""

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from commercial import agent_connections as connections
from commercial import bundled_sql
from commercial import setup_console as setup


@pytest.fixture()
def setup_state():
    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder)
        patches = [
            patch.object(setup, "ROOT", root),
            patch.object(setup, "SQLITE", root / "setup.sqlite3"),
            patch.object(setup, "KEYFILE", root / "setup.key"),
            patch.object(setup, "INITIAL", root / "initial-godadmin-password"),
            patch.object(setup, "PUBLIC", root / "license-public.pem"),
        ]
        for item in patches:
            item.start()
        try:
            setup.initialize()
            yield
        finally:
            for item in reversed(patches):
                item.stop()


def config(server, password="Aa1!application-secret"):
    return {
        "server": server,
        "database": "AVANAgent",
        "username": "AVAN_AgentApp",
        "password": password,
        "trust_server_certificate": True,
    }


def test_bundled_connection_is_first_default_and_password_is_masked(setup_state):
    connections.register_bundled(config("agent-sql,1433"))
    status = connections.public_status()
    assert status["active_id"] == "bundled"
    assert status["connections"] == [{
        "id": "bundled",
        "name": "SQL Server داخلی Docker",
        "managed": True,
        "active": True,
        "server": "agent-sql,1433",
        "database": "AVANAgent",
        "username": "AVAN_AgentApp",
        "trust_server_certificate": True,
        "password_configured": True,
    }]
    assert "Aa1!application-secret" not in str(status)
    assert setup.get_setting("agent_sql")["server"] == "agent-sql,1433"


def test_external_profile_can_switch_disconnect_and_delete(setup_state):
    connections.register_bundled(config("agent-sql,1433"))
    with patch("commercial.agent_install.check", return_value={"connected": True}):
        external_id = connections.save_external(
            name="SQL سازمان", config=config("sql.company.local,1433")
        )
        assert connections.check_saved(external_id)["connected"]
        assert connections.public_status()["active_id"] == "bundled"
        connections.activate(external_id)
        assert setup.get_setting("agent_sql")["server"] == "sql.company.local,1433"
        connections.disconnect()
        assert not setup.get_setting("agent_sql")
        connections.delete(external_id)
    assert [x["id"] for x in connections.public_status()["connections"]] == ["bundled"]


def test_bundled_or_active_connection_cannot_be_deleted(setup_state):
    connections.register_bundled(config("agent-sql,1433"))
    with pytest.raises(connections.ConnectionCatalogError):
        connections.delete("bundled")


def test_explicit_disconnect_survives_bundled_init_restart(setup_state):
    internal = config("agent-sql,1433")
    connections.register_bundled(internal)
    connections.disconnect()
    connections.register_bundled(internal)
    assert connections.public_status()["active_id"] is None
    assert not setup.get_setting("agent_sql")


def test_edit_preserves_external_password_when_blank(setup_state):
    connections.register_bundled(config("agent-sql,1433"))
    with patch("commercial.agent_install.check", return_value={"connected": True}):
        external_id = connections.save_external(
            name="SQL سازمان", config=config("old-sql,1433", "Aa1!kept-secret")
        )
        connections.save_external(
            connection_id=external_id,
            name="SQL سازمان جدید",
            config=config("old-sql,1433", ""),
        )
    stored = connections.read()["connections"][external_id]
    assert stored["config"]["password"] == "Aa1!kept-secret"
    assert stored["config"]["server"] == "old-sql,1433"


def test_edit_active_external_updates_the_database_used_by_agent(setup_state):
    connections.register_bundled(config("agent-sql,1433"))
    with patch("commercial.agent_install.check", return_value={"connected": True}):
        external_id=connections.save_external(name="SQL سازمان",config=config("old-sql,1433"))
        connections.activate(external_id)
        with pytest.raises(connections.ConnectionCatalogError):
            connections.save_external(name="SQL سازمان",connection_id=external_id,
                                      config=config("new-sql,1433",""))
        connections.save_external(name="SQL سازمان جدید",connection_id=external_id,
                                  config=config("new-sql,1433","Aa1!new-secret"))
    assert connections.public_status()["active_id"]==external_id
    assert setup.get_setting("agent_sql")["server"]=="new-sql,1433"
    assert setup.get_setting("agent_sql")["password"]=="Aa1!new-secret"


def test_bundled_bootstrap_provisions_and_activates_fresh_install(setup_state, tmp_path):
    secret = tmp_path / "sa-secret"
    secret.write_text("Avan1!StrongContainerSecret-2026", encoding="utf-8")
    internal = config("agent-sql,1433")
    with patch.dict("os.environ", {"AVAN_BUNDLED_SQL_SA_PASSWORD_PATH": str(secret)}), \
         patch.object(bundled_sql, "provision", return_value=internal) as provision:
        bundled_sql.bootstrap()
    assert provision.call_args.kwargs["reset_existing_login"] is True
    assert connections.public_status()["active_id"] == "bundled"


def test_bundled_bootstrap_does_not_replace_active_external(setup_state, tmp_path):
    secret = tmp_path / "sa-secret"
    secret.write_text("Avan1!StrongContainerSecret-2026", encoding="utf-8")
    with patch("commercial.agent_install.check", return_value={"connected": True}):
        external_id = connections.save_external(
            name="SQL سازمان", config=config("sql.company.local,1433")
        )
        connections.activate(external_id)
    with patch.dict("os.environ", {"AVAN_BUNDLED_SQL_SA_PASSWORD_PATH": str(secret)}), \
         patch.object(bundled_sql, "provision", return_value=config("agent-sql,1433")):
        bundled_sql.bootstrap()
    assert connections.public_status()["active_id"] == external_id
    assert setup.get_setting("agent_sql")["server"] == "sql.company.local,1433"
