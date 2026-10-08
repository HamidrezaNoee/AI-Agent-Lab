from starlette.requests import Request

from commercial import production_app
from commercial import setup_console
from commercial import setup_routes
import json
import pytest
from fastapi import HTTPException


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


@pytest.mark.parametrize('complete,oidc,expected', [(True,True,200),(False,True,401),(True,False,401)])
def test_organizational_user_in_stale_admin_form_never_uses_local_password(monkeypatch,complete,oidc,expected):
    setup_routes._attempts.clear()
    monkeypatch.setattr(setup_routes,'_local',lambda request:None)
    monkeypatch.setattr(setup_routes,'_origin',lambda request:None)
    monkeypatch.setattr(setup_routes,'_turnstile_check',lambda *args:True)
    monkeypatch.setattr(setup_console,'godadmin_identity',lambda:None)
    monkeypatch.setattr(setup_console,'godadmin_username',lambda:'godadmin')
    monkeypatch.setattr(setup_console,'password_state',lambda:{'changed':complete,'totp':complete})
    monkeypatch.setattr(setup_console,'get_setting',lambda key:{'issuer':'https://idp.example/realms/avan'} if key=='oidc' and oidc else None)
    monkeypatch.setattr(setup_console,'audit',lambda *args:None)
    monkeypatch.setattr(setup_console,'password_ok',lambda *args:pytest.fail('Must not check organizational password against GodAdmin'))
    before=set(setup_routes._sessions)
    body=setup_routes.Login(username='employee',password='preserve secret whitespace ',captcha_token='test')
    if expected==401:
        with pytest.raises(HTTPException) as exc:
            setup_routes.login(_request('/admin/api/login'),body)
        assert exc.value.status_code==401
    else:
        result=setup_routes.login(_request('/admin/api/login'),body)
        assert json.loads(result.body)=={'authenticated':False,'redirect':'/auth/login'}
        assert 'set-cookie' not in result.headers
        assert body.password not in result.body.decode()
    assert set(setup_routes._sessions)==before



def test_create_godadmin_identity_binds_immediately(monkeypatch,tmp_path):
    from commercial import identity_operator

    secret=tmp_path/"provisioner-secret"
    secret.write_text("x"*32,encoding="utf-8")
    monkeypatch.setenv("AVAN_PROVISIONER_CLIENT_SECRET_PATH",str(secret))
    monkeypatch.setattr(setup_console,"godadmin_identity",lambda:None)
    monkeypatch.setattr(setup_console,"totp_ok",lambda otp:otp=="123456")
    monkeypatch.setattr(
        setup_console,
        "get_setting",
        lambda key:
            {"tenant_id":"11111111-1111-1111-1111-111111111111"} if key=="company"
            else {
                "managed_by_product":True,
                "issuer":"http://auth.localhost:8181/realms/avan",
            } if key=="oidc"
            else None,
    )
    monkeypatch.setattr(identity_operator,"create",lambda *args:"22222222-2222-2222-2222-222222222222")
    bound=[]
    monkeypatch.setattr(setup_console,"bind_godadmin_identity",lambda tenant,subject:bound.append((tenant,subject)))
    monkeypatch.setattr(setup_console,"audit",lambda *args:None)
    setup_routes._sessions["old"]={"csrf":"x","expires":9999999999,"mfa":True}
    setup_routes._pending_mfa["old"]={"expires":9999999999}

    body=setup_routes.GodAdminAccount(
        username="godadmin",
        email="godadmin@example.com",
        name="God Admin",
        password="A-Strong-GodAdmin-Password-123",
        otp="123456",
    )
    response=setup_routes.create_godadmin_account(body,session=("local",{}))
    payload=json.loads(response.body)

    assert payload["created"] is True
    assert payload["bound"] is True
    assert payload["login_url"]=="/auth/login"
    assert bound==[(
        "11111111-1111-1111-1111-111111111111",
        "22222222-2222-2222-2222-222222222222",
    )]
    assert not setup_routes._sessions
    assert not setup_routes._pending_mfa
