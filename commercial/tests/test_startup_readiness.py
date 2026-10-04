"""Exercise the actual Bash probe against HTTP responses, without Keycloak."""
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
import subprocess
from threading import Thread
import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]

@pytest.mark.parametrize('status,ready', [(200, True), (503, False), (404, False), (500, False), (302, False)])
def test_realm_probe_waits_for_successful_discovery(status, ready):
    requests = []
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            requests.append(self.path)
            self.send_response(status)
            self.end_headers()
        def log_message(self, *args):
            pass
    server = HTTPServer(('127.0.0.1', 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        services = yaml.safe_load((ROOT / 'compose.yaml').read_text())['services']
        probe = services['keycloak']['healthcheck']['test']
        command = probe[3].replace('$$', '$').replace('/8080', '/' + str(server.server_port))
        result = subprocess.run(probe[1:3] + [command], timeout=5, capture_output=True)
        assert (result.returncode == 0) is ready
        assert requests == ['/realms/avan/.well-known/openid-configuration']
        assert services['avan']['depends_on']['keycloak']['condition'] == 'service_healthy'
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
