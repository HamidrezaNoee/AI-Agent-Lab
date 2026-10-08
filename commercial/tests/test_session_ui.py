"""Actual workspace idle timeout, token rotation and sign-out regression."""
from types import SimpleNamespace
from unittest.mock import patch
from uuid import UUID

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from commercial import production_app as app
from commercial.security import Principal


ACTOR = Principal(UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"), "user-1")


def browser_request(path="/api/me", headers=None):
    pairs = [(b"cookie", b"avan_session=session-1")]
    pairs += [(k.lower().encode(), v.encode()) for k, v in (headers or {}).items()]
    return Request({"type": "http", "method": "GET", "path": path,
                    "headers": pairs, "scheme": "http", "server": ("127.0.0.1", 8188)})


@pytest.fixture
def active_session(monkeypatch):
    clock = {"now": 1000.0}
    monkeypatch.setattr(app.time, "time", lambda: clock["now"])
    token_calls = []

    class Identity:
        def authenticate(self, header):
            token_calls.append(header)
            return ACTOR

    monkeypatch.setattr(app, "_oidc_config", lambda: ("auth", "token", "avan-bff", "secret", Identity()))
    monkeypatch.setattr(app.jwt, "decode", lambda *_args, **_kwargs: {"exp": clock["now"] + 300})
    app.pending.clear()
    app.sessions.clear()
    app.sessions["session-1"] = {
        "access_token": "first", "access_expires": 1300,
        "expires": 1000 + 28800, "idle_expires": 1600,
        "refresh_token": "first-refresh", "id_token": "id-token",
        "csrf": "csrf", "tenant_id": str(ACTOR.tenant_id), "subject": ACTOR.subject,
    }
    yield clock, token_calls
    app.sessions.clear()


def test_renewed_access_does_not_end_workspace_at_five_minutes(active_session, monkeypatch):
    clock, tokens = active_session

    class Response:
        content = b"{\"access_token\":\"fresh\"}"

        def raise_for_status(self):
            pass

        def json(self):
            return {"access_token": "fresh", "refresh_token": "rotated", "id_token": "new-id"}

    class Client:
        def __init__(self, **_kw):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            pass

        def post(self, _url, data):
            assert data["refresh_token"] == "first-refresh"
            return Response()

    monkeypatch.setattr(app.httpx, "Client", Client)
    clock["now"] = 1280
    app._principal_for_request(browser_request())
    assert app.sessions["session-1"]["refresh_token"] == "rotated"
    assert app.sessions["session-1"]["idle_expires"] == 1880
    assert tokens[-1] == "Bearer fresh"


def test_background_poll_does_not_extend_idle_and_exact_timeout_expires(active_session):
    clock, _ = active_session
    clock["now"] = 1200
    app._principal_for_request(browser_request(headers={"X-AVAN-BACKGROUND": "1"}))
    assert app.sessions["session-1"]["idle_expires"] == 1600
    clock["now"] = 1600
    with pytest.raises(HTTPException) as err:
        app._principal_for_request(browser_request())
    assert err.value.status_code == 401
    assert not app.sessions


def test_sign_out_revokes_all_local_sessions_and_removes_cookie(active_session, monkeypatch):
    clock, _ = active_session
    second = dict(app.sessions["session-1"])
    app.sessions["session-2"] = second
    monkeypatch.setattr(app, "_public_origin", lambda: "http://127.0.0.1:8188")
    with patch("commercial.setup_console.get_setting", return_value={"issuer": "http://auth.localhost:8181/realms/avan"}):
        response = app.logout(browser_request("/auth/logout", {"X-AVAN-CSRF": "csrf"}))
    assert response.status_code == 200
    assert not app.sessions
    assert "avan_session=" in response.headers["set-cookie"]
    assert b"post_logout_redirect_uri" in response.body


def test_five_palettes_and_bundled_local_fonts_exist():
    from pathlib import Path
    root = Path(app.ROOT)
    css = (root / "theme.css").read_text()
    for theme in ("light", "dark", "green", "blue", "red"):
        assert theme == "light" or "data-theme='" + theme + "'" in css
    for weight in ("Regular", "SemiBold", "Bold"):
        assert (root / "fonts" / ("YekanBakh-" + weight + ".woff2")).is_file()
    assert app.font_asset("YekanBakh-Bold.woff2").media_type == "font/woff2"
    with pytest.raises(HTTPException):
        app.font_asset("../setup.key")
