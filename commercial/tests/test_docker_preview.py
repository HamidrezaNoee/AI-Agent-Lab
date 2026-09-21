"""Docker deployment configuration regression without requiring Docker Desktop."""
from pathlib import Path
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from commercial.demo_preview import app

ROOT=Path(__file__).resolve().parents[2]

class DockerPreviewTests(unittest.TestCase):
    def test_compose_binds_only_host_loopback_and_never_mounts_secrets(self):
        source=(ROOT/"compose.yaml").read_text(encoding="utf-8")
        self.assertIn('127.0.0.1:8090:8090',source)
        self.assertIn('commercial/Dockerfile.preview',source)
        self.assertNotIn('COMMERCIAL_SQL_PASSWORD',source)
        self.assertNotIn('OPENAI_API_KEY',source)
        self.assertNotIn('COMMERCIAL_PM_BEARER_TOKEN',source)
        self.assertIn('read_only: true',source)
        self.assertIn('cap_drop:',source)

    def test_image_is_nonroot_and_installs_only_preview_deps(self):
        dockerfile=(ROOT/"commercial"/"Dockerfile.preview").read_text(encoding="utf-8")
        requirements=(ROOT/"commercial"/"requirements-preview.txt").read_text(encoding="utf-8")
        self.assertIn('USER 10001:10001',dockerfile)
        self.assertIn('requirements-preview.txt',dockerfile)
        for unwanted in ('pyodbc','OPENAI_API_KEY','COMMERCIAL_SQL_PASSWORD'):
            self.assertNotIn(unwanted,requirements)
        self.assertIn('commercial.demo_preview:app',dockerfile)

    def test_optional_connected_lab_is_loopback_only_and_v2_only(self):
        compose=(ROOT/"compose.connected-lab.yaml").read_text(encoding="utf-8")
        dockerfile=(ROOT/"commercial"/"Dockerfile.connected-lab").read_text(encoding="utf-8")
        ignore=(ROOT/".dockerignore").read_text(encoding="utf-8")
        self.assertIn("127.0.0.1:8088:8088",compose)
        self.assertIn("EnterpriseProcess2_AI_Test",compose)
        self.assertIn('COMMERCIAL_V2_ONLY: "1"',compose)
        self.assertIn('COMMERCIAL_CHAT_ENABLED: "0"',compose)
        self.assertIn("COMMERCIAL_PORTAL_DOCKER:",compose)
        self.assertNotIn("COMMERCIAL_SQL_PASSWORD:",compose)
        self.assertNotIn("COMMERCIAL_OIDC_CLIENT_SECRET:",compose)
        self.assertIn("msodbcsql17",dockerfile)
        self.assertIn("USER 10001:10001",dockerfile)
        self.assertIn(".env.*",ignore)
        self.assertIn("**/*.ttf",ignore)

    def test_docker_private_gateway_requires_explicit_mode_and_localhost_host(self):
        async def docker_bridge_client(scope, receive, send):
            changed=dict(scope)
            if scope["type"]=="http":
                changed["client"]=("172.19.0.1",1234)
            await app(changed,receive,send)

        def check(host, enabled):
            with patch.dict("os.environ",
                            {"COMMERCIAL_PREVIEW_DOCKER":"1" if enabled else "0"}):
                with TestClient(docker_bridge_client,base_url="http://"+host) as client:
                    return client.get("/health").status_code

        self.assertEqual(check("127.0.0.1:8090",False),403)
        self.assertEqual(check("127.0.0.1:8090",True),200)
        self.assertIn(check("external.example.test:8090",True),(400,403))
        with TestClient(app) as client:
            self.assertEqual(client.get("/health").status_code,200)


if __name__=="__main__":
    unittest.main()
