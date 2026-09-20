"""Legacy API content quarantine regression (in-process, no real IdP/SQL)."""
import os
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from commercial.api import app


class LegacyContentQuarantineTests(unittest.TestCase):
    def test_old_content_routes_closed_when_hierarchy_enabled(self):
        with patch.dict(os.environ, {"COMMERCIAL_V2_ONLY": "1"}):
            with TestClient(app) as client:
                for path in (
                    "/v1/meetings", "/v1/meetings/page", "/v1/knowledge/search?q=sample",
                    "/v1/chat/preview", "/v1/chat/answer",
                    "/v1/secretary/preparation/900001",
                    "/v1/analytics/status-overview", "/v1/monitoring/overdue",
                ):
                    request = client.post(path, json={"question": "sample"}) if path.startswith("/v1/chat/") else client.get(path)
                    self.assertEqual(request.status_code, 410, path)
                    self.assertEqual(request.headers.get("cache-control"), "no-store")
                # The v2 routes remain independently JWT and directory protected.
                self.assertIn(client.get("/v2/meetings/page").status_code, (401, 503))
                # v1 identity + module catalog do not leak meeting content, still require JWT.
                self.assertIn(client.get("/v1/modules").status_code, (401, 503))
                self.assertIn(client.get("/v1/me").status_code, (401, 503))

    def test_historical_v1_fixture_tests_remain_opt_in(self):
        with patch.dict(os.environ, {"COMMERCIAL_V2_ONLY": "0"}):
            with TestClient(app) as client:
                self.assertNotEqual(client.get("/v1/meetings").status_code, 410)


if __name__ == "__main__":
    unittest.main()
