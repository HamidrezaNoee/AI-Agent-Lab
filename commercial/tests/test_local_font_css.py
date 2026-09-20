"""Optional Persian font: no broken network requests when font files are absent."""
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from commercial.demo_preview import app as preview_app
from commercial.api import app as commercial_app
from commercial.local_font_css import installed_font_css


class OptionalFontTests(unittest.TestCase):
    def test_preview_emits_no_font_requests_if_files_missing(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch("commercial.local_font_css.ROOT", Path(folder)):
                with TestClient(preview_app) as client:
                    css = client.get("/preview.css")
                self.assertEqual(css.status_code, 200)
                self.assertNotIn("@font-face", css.text)
                self.assertNotIn("/preview-font-", css.text)
                self.assertNotIn("/portal/font/", css.text)
                self.assertIn("font-family:BYekanPlus,Tahoma", css.text)

    def test_only_existing_font_weight_is_advertised(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "web" / "fonts"
            target.mkdir(parents=True)
            (target / "byekanplus-regular.ttf").write_bytes(b"fictional-test-only")
            with patch("commercial.local_font_css.ROOT", Path(folder)):
                generated = installed_font_css("/preview-font-")
                self.assertIn("/preview-font-regular", generated)
                self.assertNotIn("/preview-font-bold", generated)
                self.assertNotIn("/portal/font/", generated)

    def test_connected_portal_css_has_no_preview_only_font_paths(self):
        import os
        env = {
            "COMMERCIAL_WEB_PORTAL_ENABLED": "1",
            "COMMERCIAL_MODE": "lab",
            "COMMERCIAL_SQL_DATABASE": "EnterpriseProcess2_AI_Test",
        }
        with tempfile.TemporaryDirectory() as folder:
            with patch.dict(os.environ, env), patch(
                "commercial.local_font_css.ROOT", Path(folder)
            ):
                with TestClient(commercial_app) as client:
                    css = client.get("/portal/portal.css")
                self.assertEqual(css.status_code, 200)
                self.assertNotIn("/preview-font-", css.text)
                self.assertNotIn("/portal/font/", css.text)


if __name__ == "__main__":
    unittest.main()
