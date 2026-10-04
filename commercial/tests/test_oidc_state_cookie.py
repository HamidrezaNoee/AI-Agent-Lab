from urllib.parse import parse_qs, urlsplit

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from commercial import production_app
from commercial import setup_console
from commercial.security import ConfigurationFailed


def _request(path="/auth/login", *, cookie=""):
    headers=[]
    if cookie:
        headers.append((b"cookie", cookie.encode("latin-1")))
    return Request({
        "type":"http",
        "http_version":"1.1",
        "method":"GET",
        "scheme":"http",
        "path":path,
        "raw_path":path.encode(),
        "query_string":b"",
        "headers":headers,
        "client":("127.0.0.1",50000),
        "server":("127.0.0.1",8188),
    })


def test_oidc_state_cookie_name_is_transaction_scoped():
    first=production_app._oidc_state_cookie_name("state-one")
    second=production_app._oidc_state_cookie_name("state-two")
    assert first.startswith("avan_oidc_state_")
    assert second.startswith("avan_oidc_state_")
    assert first != second
    assert first == production_app._oidc_state_cookie_name("state-one")


def test_login_uses_callback_scoped_state_cookie_and_ignores_stale_legacy(monkeypatch):
    production_app.pending.clear()
    monkeypatch.setattr(
        setup_console,
        "password_state",
        lambda:{"changed":True,"totp":True},
    )
    monkeypatch.setattr(
        production_app,
        "_oidc_config",
        lambda:(
            "http://auth.localhost:8181/realms/avan/protocol/openid-connect/auth",
            "http://auth.localhost:8181/realms/avan/protocol/openid-connect/token",
            "avan-bff",
            "x"*32,
            object(),
        ),
    )

    response=production_app.login(_request())
    assert response.status_code==302
    location=response.headers["location"]
    state=parse_qs(urlsplit(location).query)["state"][0]
    cookie_name=production_app._oidc_state_cookie_name(state)

    set_cookies=[
        value.decode("latin-1")
        for name,value in response.raw_headers
        if name.lower()==b"set-cookie"
    ]
    assert any(
        value.startswith(cookie_name+"=") and "Path=/auth/callback" in value
        for value in set_cookies
    )
    assert any(
        value.startswith("avan_login_state=") and "Max-Age=0" in value
        for value in set_cookies
    )

    def broken_config():
        raise ConfigurationFailed("stop after state validation")

    monkeypatch.setattr(production_app,"_oidc_config",broken_config)
    request=_request(
        "/auth/callback",
        cookie=f"avan_login_state=stale; {cookie_name}={state}",
    )
    with pytest.raises(HTTPException) as exc:
        production_app.callback(request,code="dummy-code",state=state)
    # 503 proves the request passed the OIDC state-cookie guard and reached
    # configuration handling; the stale legacy cookie did not break it.
    assert exc.value.status_code==503
