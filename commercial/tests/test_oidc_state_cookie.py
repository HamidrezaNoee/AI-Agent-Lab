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


def _configure_login(monkeypatch):
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


def _login(monkeypatch,cookie=""):
    _configure_login(monkeypatch)
    response=production_app.login(_request(cookie=cookie))
    assert response.status_code==302
    state=parse_qs(urlsplit(response.headers["location"]).query)["state"][0]
    set_cookies=[
        value.decode("latin-1")
        for name,value in response.raw_headers
        if name.lower()==b"set-cookie"
    ]
    return response,state,set_cookies


def _cookie_value(set_cookies,name):
    row=next(value for value in set_cookies if value.startswith(name+"="))
    return row.split(";",1)[0].split("=",1)[1]


def test_oidc_state_cookie_name_is_transaction_scoped():
    first=production_app._oidc_state_cookie_name("state-one")
    second=production_app._oidc_state_cookie_name("state-two")
    assert first.startswith("avan_oidc_state_")
    assert second.startswith("avan_oidc_state_")
    assert first != second
    assert first == production_app._oidc_state_cookie_name("state-one")


def test_login_binds_state_to_stable_browser_token(monkeypatch):
    production_app.pending.clear()
    _,state,set_cookies=_login(monkeypatch)
    cookie_name=production_app._oidc_state_cookie_name(state)
    browser_token=_cookie_value(
        set_cookies,
        production_app.OIDC_BROWSER_COOKIE,
    )

    browser_cookie=next(
        value for value in set_cookies
        if value.startswith(production_app.OIDC_BROWSER_COOKIE+"=")
    )
    assert "Path=/" in browser_cookie
    assert "HttpOnly" in browser_cookie
    assert any(
        value.startswith(cookie_name+"=") and "Path=/" in value
        for value in set_cookies
    )
    assert production_app.pending[state]["browser_hash"] == (
        production_app._oidc_browser_hash(browser_token)
    )

    def broken_config():
        raise ConfigurationFailed("stop after browser/state validation")

    monkeypatch.setattr(production_app,"_oidc_config",broken_config)
    request=_request(
        "/auth/callback",
        cookie=(
            f"{production_app.OIDC_BROWSER_COOKIE}={browser_token}; "
            f"{cookie_name}={state}"
        ),
    )
    with pytest.raises(HTTPException) as exc:
        production_app.callback(request,code="dummy-code",state=state)
    # 503 proves browser/state binding passed and callback reached OIDC config.
    assert exc.value.status_code==503


def test_callback_rejects_wrong_browser_even_with_matching_state_cookie(monkeypatch):
    production_app.pending.clear()
    _,state,set_cookies=_login(monkeypatch)
    cookie_name=production_app._oidc_state_cookie_name(state)
    request=_request(
        "/auth/callback",
        cookie=(
            f"{production_app.OIDC_BROWSER_COOKIE}="
            f"{production_app._new_oidc_browser_token()}; "
            f"{cookie_name}={state}"
        ),
    )
    with pytest.raises(HTTPException) as exc:
        production_app.callback(request,code="dummy-code",state=state)
    assert exc.value.status_code==401
    assert exc.value.detail=="درخواست ورود معتبر نیست."


def test_parallel_logins_reuse_browser_token_without_state_collision(monkeypatch):
    production_app.pending.clear()
    _,first_state,first_cookies=_login(monkeypatch)
    browser_token=_cookie_value(
        first_cookies,
        production_app.OIDC_BROWSER_COOKIE,
    )
    _,second_state,second_cookies=_login(
        monkeypatch,
        cookie=f"{production_app.OIDC_BROWSER_COOKIE}={browser_token}",
    )

    assert first_state != second_state
    assert _cookie_value(
        second_cookies,
        production_app.OIDC_BROWSER_COOKIE,
    ) == browser_token
    expected=production_app._oidc_browser_hash(browser_token)
    assert production_app.pending[first_state]["browser_hash"]==expected
    assert production_app.pending[second_state]["browser_hash"]==expected
