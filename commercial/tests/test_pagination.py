"""Offline keyset pagination regression; SQL and identities are mocked here."""
import unittest
from contextlib import contextmanager
from unittest.mock import patch
from uuid import UUID

from fastapi.testclient import TestClient
from commercial.api import app, _authenticated_principal
from commercial.security import Principal
from commercial.authorization_v2 import visible_meetings_v2


class Cursor:
    def __init__(self, rows):
        self.rows = rows
        self.sql = ""
        self.params = None
    def execute(self, sql, *params):
        self.sql, self.params = sql, params
        return self
    def fetchall(self):
        return self.rows


class Connection:
    def __init__(self, rows):
        self.cur = Cursor(rows)
    def cursor(self):
        return self.cur


class PaginationTests(unittest.TestCase):
    def setUp(self):
        self.principal = Principal(UUID("11111111-1111-4111-8111-111111111111"), "lab-alice")

    def test_page_stays_tenant_and_user_scoped(self):
        rows = [(900010 - i, f"M-{i}", f"Test title {i}", "Draft") for i in range(12)]
        conn = Connection(rows)
        data = visible_meetings_v2(conn, self.principal, before_id=910000, limit=10)
        self.assertEqual(len(data["meetings"]), 10)
        self.assertEqual(data["next_cursor"], 900001)
        self.assertTrue(data["has_more"])
        self.assertIn("AgentProduct.MeetingGrant", conn.cur.sql)
        self.assertIn("g.SubjectID=?", conn.cur.sql)
        self.assertIn("m.TenantID=?", conn.cur.sql)
        self.assertIn("m.MeetingID<?", conn.cur.sql)
        self.assertEqual(conn.cur.params,
                         (str(self.principal.tenant_id), 910000, "lab-alice"))
        self.assertNotIn("910000", conn.cur.sql)  # values must be bound, not interpolated

    def test_first_page_has_no_cursor_predicate(self):
        conn = Connection([(900001, "A-001", "test", "Draft")])
        data = visible_meetings_v2(conn, self.principal, limit=20)
        self.assertEqual(data["meetings"][0]["meeting_id"], 900001)
        self.assertIsNone(data["next_cursor"])
        self.assertFalse(data["has_more"])
        self.assertNotIn("m.MeetingID<?", conn.cur.sql)
        self.assertEqual(conn.cur.params,
                         (str(self.principal.tenant_id), "lab-alice"))

    def test_out_of_range_rejected_before_sql(self):
        for n in (0, 51, -1):
            with self.assertRaises(ValueError):
                visible_meetings_v2(Connection([]), self.principal, limit=n)
        with self.assertRaises(ValueError):
            visible_meetings_v2(Connection([]), self.principal, before_id=-1)

    def test_route_requires_existing_principal_and_bounded_query(self):
        app.dependency_overrides[_authenticated_principal] = lambda:self.principal
        @contextmanager
        def fake_conn(principal):
            self.assertEqual(principal, self.principal)
            yield Connection([(900001, "A-001", "test", "Draft")])
        try:
            with (patch("commercial.api.scoped_connection", fake_conn),
                  patch("commercial.api.authorization_snapshot",
                        return_value={"role":"Viewer"})):
                with TestClient(app) as client:
                    valid = client.get("/v1/meetings/page", params={"limit":20})
                    self.assertEqual(valid.status_code, 200)
                    self.assertEqual(valid.json()["meetings"][0]["meeting_id"], 900001)
                    self.assertEqual(client.get("/v1/meetings/page",
                                                params={"limit":51}).status_code,422)
                    self.assertEqual(client.get("/v1/meetings/page",
                                                params={"cursor":-1}).status_code,422)
        finally:
            app.dependency_overrides.clear()


if __name__=="__main__":
    unittest.main()
