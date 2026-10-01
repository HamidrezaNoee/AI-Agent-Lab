"""Turnstile validation is fail-closed and never depends on live Cloudflare in CI."""
import tempfile
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from commercial import turnstile


class FakeResponse:
    status_code=200
    content=b'{}'
    def __init__(self,payload):
        import json
        self._payload=payload
        self.content=json.dumps(payload).encode()
    def json(self):return self._payload


class FakeClient:
    payload={"success":True,"action":"avan-bootstrap-login"}
    def __init__(self,*_args,**_kwargs):pass
    def __enter__(self):return self
    def __exit__(self,*_args):pass
    def post(self,*_args,**_kwargs):return FakeResponse(self.payload)


@pytest.fixture
def keys():
    with tempfile.TemporaryDirectory() as tmp:
        site=Path(tmp)/"site"
        secret=Path(tmp)/"secret"
        site.write_text("real-site-key",encoding="utf-8")
        secret.write_text("real-secret-key",encoding="utf-8")
        with patch.object(turnstile,"SITE_KEY_PATH",site), \
             patch.object(turnstile,"SECRET_KEY_PATH",secret):
            yield site,secret


def test_valid_server_side_token_requires_expected_action(keys):
    with patch.object(turnstile.httpx,"Client",FakeClient):
        assert turnstile.verify(json.dumps({"provider":"cloudflare-turnstile","token":"valid-token"}),action="avan-bootstrap-login",remote_ip="127.0.0.1")
        FakeClient.payload={"success":True,"action":"another-action"}
        assert not turnstile.verify(json.dumps({"provider":"cloudflare-turnstile","token":"valid-token"}),action="avan-bootstrap-login")
        FakeClient.payload={"success":True,"action":"avan-bootstrap-login"}


def test_failed_or_malformed_tokens_fail_closed(keys):
    with patch.object(turnstile.httpx,"Client",FakeClient):
        FakeClient.payload={"success":False,"error-codes":["invalid-input-response"]}
        assert not turnstile.verify(json.dumps({"provider":"cloudflare-turnstile","token":"bad-token"}),action="avan-bootstrap-login")
        assert not turnstile.verify("",action="avan-bootstrap-login")
        assert not turnstile.verify("x"*2049,action="avan-bootstrap-login")
        FakeClient.payload={"success":True,"action":"avan-bootstrap-login"}


def test_https_production_refuses_cloudflare_test_keys(keys):
    site,secret=keys
    site.write_text(turnstile.TEST_SITE_KEY,encoding="utf-8")
    secret.write_text(turnstile.TEST_SECRET_KEY,encoding="utf-8")
    with patch.dict("os.environ",{"AVAN_TURNSTILE_REQUIRE_PRODUCTION":"1"}):
        assert turnstile._cloudflare_credentials() is None

