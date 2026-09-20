"""Offline optional-module and 100-scenario integrity tests (no live SQL/IdP/LLM)."""
import json
import unittest
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch
from uuid import UUID

from fastapi.testclient import TestClient
from commercial.api import app, _authenticated_principal
from commercial.modules import modules_snapshot, require_module
from commercial.security import Principal
from commercial.sql_store import AccessDenied


class Cursor:
    def __init__(self, rows):
        self.rows = rows
        self.sql = ""
        self.params = ()
    def execute(self, sql, *args):
        self.sql, self.params = sql, args
        return self
    def fetchall(self):
        return self.rows
    def fetchone(self):
        return self.rows[0] if self.rows else None


class Connection:
    def __init__(self, rows):
        self.cur = Cursor(rows)
    def cursor(self):
        return self.cur


class ModuleSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.principal = Principal(UUID("11111111-1111-4111-8111-111111111111"), "lab-alice")
        self.future = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=5)

    def test_missing_module_row_is_off_and_unlicensed(self):
        connection = Connection([])
        values = modules_snapshot(connection, self.principal)
        self.assertEqual([m["active"] for m in values], [True, False, False, False])
        self.assertEqual(connection.cur.params, (str(self.principal.tenant_id),))
        with self.assertRaises(AccessDenied):
            require_module(connection, self.principal, 2)

    def test_only_licensed_and_enabled_module_is_active(self):
        connection = Connection([(2, 1, 1, self.future),
                                 (3, 1, 0, self.future),
                                 (4, 0, 1, self.future)])
        states = {m["module_code"]: m for m in modules_snapshot(connection, self.principal)}
        self.assertTrue(states[2]["active"])
        self.assertFalse(states[3]["active"])
        self.assertFalse(states[4]["active"])
        require_module(connection, self.principal, 2)
        with self.assertRaises(AccessDenied):
            require_module(connection, self.principal, 3)

    def test_expired_license_denies_even_if_enabled(self):
        old = datetime.now(timezone.utc) - timedelta(minutes=1)
        connection = Connection([(2, 1, 1, old)])
        self.assertFalse(modules_snapshot(connection, self.principal)[1]["active"])
        with self.assertRaises(AccessDenied):
            require_module(connection, self.principal, 2)


class ModuleRouteTests(unittest.TestCase):
    def setUp(self):
        self.principal = Principal(UUID("11111111-1111-4111-8111-111111111111"), "lab-alice")
        app.dependency_overrides[_authenticated_principal] = lambda: self.principal
        self.client = TestClient(app)
        self.conn = Connection([])

    def tearDown(self):
        self.client.close()
        app.dependency_overrides.clear()

    @contextmanager
    def fake_connection(self, principal):
        self.assertIs(principal, self.principal)
        yield self.conn

    def test_viewer_cannot_toggle_module_even_if_purchased(self):
        with (patch("commercial.api.scoped_connection", self.fake_connection),
              patch("commercial.api.authorization_snapshot", return_value={"role": "Viewer"}),
              patch("commercial.api.set_module_enabled",
                    side_effect=AssertionError("Viewer wrote module flag"))):
            result = self.client.put("/v1/admin/modules/3", json={"enabled": True})
        self.assertEqual(result.status_code, 403)

    def test_admin_cannot_toggle_unlicensed_module(self):
        states = [{"module_code": x, "licensed": False} for x in (1, 2, 3, 4)]
        with (patch("commercial.api.scoped_connection", self.fake_connection),
              patch("commercial.api.authorization_snapshot", return_value={"role": "Admin"}),
              patch("commercial.api.modules_snapshot", return_value=states),
              patch("commercial.api.set_module_enabled",
                    side_effect=AssertionError("Unlicensed module wrote flag"))):
            result = self.client.put("/v1/admin/modules/4", json={"enabled": True})
        self.assertEqual(result.status_code, 403)

    def test_disabled_module_blocks_analytics_before_query(self):
        with (patch("commercial.api.scoped_connection", self.fake_connection),
              patch("commercial.api.authorization_snapshot", return_value={"role": "Viewer"}),
              patch("commercial.api.require_module", side_effect=AccessDenied("disabled"))):
            result = self.client.get("/v1/analytics/status-overview")
        self.assertEqual(result.status_code, 403)
        self.assertEqual(self.conn.cur.sql, "")


class DatasetIntegrityTests(unittest.TestCase):
    def test_all_100_scenarios_have_unique_ids_and_300_actions(self):
        path = Path(__file__).resolve().parents[1] / "datasets" / "100_automotive_meeting_scenarios_FA.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        cases = data["scenarios"]
        self.assertTrue(data["synthetic"])
        self.assertEqual(data["count"], 100)
        self.assertEqual(len(cases), 100)
        self.assertEqual(len({c["meeting_id"] for c in cases}), 100)
        self.assertEqual(len({c["title"] for c in cases}), 100)
        self.assertEqual(sum(len(c["actions"]) for c in cases), 300)
        self.assertEqual({c["fictional_tenant"] for c in cases},
                         {"11111111-1111-4111-8111-111111111111"})
        for case in cases:
            for field in ("initial_request", "preparation", "resolution",
                          "risk", "secretary_followup", "next_meeting_topic"):
                self.assertTrue(case[field], (case["scenario_id"], field))
            self.assertEqual(len(set(a["action_no"] for a in case["actions"])), 3)
            self.assertTrue(all(0 <= a["progress_percent"] <= 100
                                for a in case["actions"]))


if __name__ == "__main__":
    unittest.main()
