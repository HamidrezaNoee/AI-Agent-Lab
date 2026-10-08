from urllib.parse import parse_qs, urlsplit

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from commercial import production_app
from commercial import setup_console
from commercial.security import ConfigurationFailed


def _request(path="/auth/login", *, cookie="", host="127.0.0.1:8188", scheme="http"):
    headers=[(b"host",host.encode("ascii"))]
    if cookie:
        headers.append((b"cookie", cookie.encode("latin-1")))
    hostname,_,port=host.partition(":")
    return Request({
        "type":"http",
        "http_version":"1.1",
        "method":"GET",
        "scheme":scheme,
        "path":path,
        "raw_path":path.encode(),
        "query_string":b"",
        "headers":headers,
        "client":("127.0.0.1",50000),
        "server":(hostname,int(port or (443 if scheme=="https" else 80))),
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


def test_login_binds_state_to_signed_transaction_cookie(monkeypatch):
    production_app.pending.clear()
    _,state,set_cookies=_login(monkeypatch)
    cookie_name=production_app._oidc_state_cookie_name(state)
    browser_token=_cookie_value(
        set_cookies,
        production_app.OIDC_BROWSER_COOKIE,
    )
    transaction=_cookie_value(set_cookies,cookie_name)

    browser_cookie=next(
        value for value in set_cookies
        if value.startswith(production_app.OIDC_BROWSER_COOKIE+"=")
    )
    tx_cookie=next(
        value for value in set_cookies
        if value.startswith(cookie_name+"=")
    )
    assert "Path=/" in browser_cookie and "HttpOnly" in browser_cookie
    assert "Path=/" in tx_cookie and "HttpOnly" in tx_cookie

    decoded=production_app._oidc_tx_decode(
        transaction,
        state=state,
        secret="x"*32,
    )
    assert decoded is not None
    assert decoded["browser_hash"]==production_app._oidc_browser_hash(browser_token)
    assert decoded["verifier"]==production_app.pending[state]["verifier"]


def test_callback_survives_restart_using_signed_pkce_cookie(monkeypatch):
    production_app.pending.clear()
    _,state,set_cookies=_login(monkeypatch)
    cookie_name=production_app._oidc_state_cookie_name(state)
    browser_token=_cookie_value(
        set_cookies,
        production_app.OIDC_BROWSER_COOKIE,
    )
    transaction=_cookie_value(set_cookies,cookie_name)

    # Simulate AVAN container restart / another worker.
    production_app.pending.clear()

    class Client:
        def __init__(self,*args,**kwargs): pass
        def __enter__(self): return self
        def __exit__(self,*args): pass
        def post(self,*args,**kwargs):
            raise production_app.httpx.ConnectError("stop after transaction recovery")

    monkeypatch.setattr(production_app.httpx,"Client",Client)
    request=_request(
        "/auth/callback",
        cookie=(
            f"{production_app.OIDC_BROWSER_COOKIE}={browser_token}; "
            f"{cookie_name}={transaction}"
        ),
    )
    with pytest.raises(HTTPException) as exc:
        production_app.callback(request,code="dummy-code",state=state)
    # 503 means the signed transaction was recovered after RAM loss and the
    # callback reached the token endpoint instead of expiring locally.
    assert exc.value.status_code==503


def test_callback_rejects_wrong_browser_with_valid_signed_transaction(monkeypatch):
    production_app.pending.clear()
    _,state,set_cookies=_login(monkeypatch)
    cookie_name=production_app._oidc_state_cookie_name(state)
    transaction=_cookie_value(set_cookies,cookie_name)
    production_app.pending.clear()

    request=_request(
        "/auth/callback",
        cookie=(
            f"{production_app.OIDC_BROWSER_COOKIE}="
            f"{production_app._new_oidc_browser_token()}; "
            f"{cookie_name}={transaction}"
        ),
    )
    with pytest.raises(HTTPException) as exc:
        production_app.callback(request,code="dummy-code",state=state)
    assert exc.value.status_code==401
    assert exc.value.detail=="درخواست ورود معتبر نیست."


def test_callback_recovers_from_tampered_or_stale_transaction_cookie(monkeypatch):
    production_app.pending.clear()
    _,state,set_cookies=_login(monkeypatch)
    cookie_name=production_app._oidc_state_cookie_name(state)
    browser_token=_cookie_value(set_cookies,production_app.OIDC_BROWSER_COOKIE)
    transaction=_cookie_value(set_cookies,cookie_name)
    production_app.pending.clear()

    bad=transaction[:-1]+("A" if transaction[-1]!="A" else "B")
    request=_request(
        "/auth/callback",
        cookie=(
            f"{production_app.OIDC_BROWSER_COOKIE}={browser_token}; "
            f"{cookie_name}={bad}"
        ),
    )
    response=production_app.callback(request,code="dummy-code",state=state)
    assert response.status_code==303
    assert response.headers["location"].endswith("/auth/login?reauth=expired")
    assert response.headers["cache-control"]=="no-store"


def test_login_canonicalizes_any_non_public_host_before_setting_oidc_cookies(monkeypatch):
    _configure_login(monkeypatch)
    response=production_app.login(_request(host="workstation.local:8188"))
    assert response.status_code==303
    assert response.headers["location"]=="http://127.0.0.1:8188/auth/login"
    assert not [
        value for name,value in response.raw_headers
        if name.lower()==b"set-cookie"
    ]


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
