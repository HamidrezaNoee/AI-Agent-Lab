import httpx
import pytest
from commercial.user_accounts import Directory,AccountError

TENANT='aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa'
SUBJECT='bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb'

def service(calls,foreign=False):
    def handle(request):
        calls.append(request)
        if request.url.path.endswith('/token'):return httpx.Response(200,json={'access_token':'secret'})
        if request.method=='GET':return httpx.Response(200,json={'id':SUBJECT,'email':'old@example.com','attributes':{'tenant_id':['other' if foreign else TENANT]}})
        return httpx.Response(204)
    return Directory(httpx.Client(transport=httpx.MockTransport(handle)),'http://auth.localhost:8181/realms/avan','secret',TENANT)

def test_other_tenant_cannot_be_edited_or_reset():
    for action in ('profile','password'):
        calls=[];api=service(calls,True)
        with pytest.raises(AccountError):
            if action=='profile':api.update(SUBJECT,'person','Person','p@example.com')
            else:api.password(SUBJECT,'long-password-1234')
        assert not any(r.method in ('PUT','DELETE') for r in calls)

def test_email_edit_removes_verification_without_changing_roles():
    import json
    calls=[];api=service(calls)
    api.update(SUBJECT,'person','Person Name','new@example.com')
    body=json.loads(calls[-1].content)
    assert body['emailVerified'] is False
    assert 'attributes' not in body and 'realmRoles' not in body and 'enabled' not in body

def test_temporary_password_revokes_keycloak_sessions_preserves_otp():
    calls=[];api=service(calls)
    api.password(SUBJECT,'long-password-1234')
    assert calls[-2].url.path.endswith('/reset-password')
    assert calls[-1].url.path.endswith('/logout')
    assert not any('/credentials/' in r.url.path for r in calls)

def test_local_admin_does_not_block_ordinary_authorized_sessions(monkeypatch):
    from commercial import production_app as app,setup_console as setup
    from starlette.requests import Request
    monkeypatch.setattr(setup,'godadmin_identity',lambda:None)
    monkeypatch.setattr(setup,'get_setting',lambda key:{'permanent':True} if key=='godadmin_account' else None)
    monkeypatch.setattr(setup,'password_state',lambda:{'changed':True,'totp':True})
    value=('session',{'csrf':'token'},object())
    monkeypatch.setattr(app,'_principal_for_request',lambda request:value)
    assert app._authorized(Request({'type':'http','method':'GET','path':'/api/me','headers':[]}))==value
    monkeypatch.setattr(setup,'password_state',lambda:{'changed':True,'totp':False})
    with pytest.raises(Exception) as exc:app._authorized(Request({'type':'http','method':'GET','path':'/api/me','headers':[]}))
    assert exc.value.status_code==403
