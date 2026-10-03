from starlette.requests import Request

from commercial import production_app
from commercial import setup_console
from commercial import setup_routes


def _request(path="/"):
    return Request({
        "type":"http",
        "http_version":"1.1",
        "method":"GET",
        "scheme":"http",
        "path":path,
        "raw_path":path.encode(),
        "query_string":b"",
        "headers":[],
        "client":("127.0.0.1",50000),
        "server":("127.0.0.1",8188),
    })


def test_public_root_uses_keycloak_after_bootstrap_even_before_godadmin_binding(monkeypatch):
    production_app.sessions.clear()
    monkeypatch.setattr(setup_console,"godadmin_identity",lambda:None)
    monkeypatch.setattr(
        setup_console,
        "get_setting",
        lambda key: {"issuer":"http://auth.localhost:8181/realms/avan"} if key=="oidc" else None,
    )
    monkeypatch.setattr(
        setup_console,
        "password_state",
        lambda:{"changed":True,"totp":True},
    )
    monkeypatch.setattr(setup_routes,"bootstrap_workspace_session",lambda request:None)

    response=production_app.home(_request())
    assert response.status_code==303
    assert response.headers["location"]=="/auth/login"


def test_public_root_stays_on_local_admin_until_bootstrap_security_is_complete(monkeypatch):
    production_app.sessions.clear()
    monkeypatch.setattr(setup_console,"godadmin_identity",lambda:None)
    monkeypatch.setattr(
        setup_console,
        "get_setting",
        lambda key: {"issuer":"http://auth.localhost:8181/realms/avan"} if key=="oidc" else None,
    )
    monkeypatch.setattr(
        setup_console,
        "password_state",
        lambda:{"changed":False,"totp":False},
    )
    monkeypatch.setattr(setup_routes,"bootstrap_workspace_session",lambda request:None)

    response=production_app.home(_request())
    assert response.status_code==303
    assert response.headers["location"]=="/admin/"
