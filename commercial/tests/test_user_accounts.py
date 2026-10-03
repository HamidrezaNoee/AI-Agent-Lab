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

@pytest.mark.parametrize('kind',['foreign','service','valid','missing','failure'])
def test_delete_checks_boundary_before_detaching_and_can_retry(kind):
    calls=[];events=[]
    def handle(request):
        calls.append(request)
        if request.url.path.endswith('/token'):return httpx.Response(200,json={'access_token':'token'})
        if request.method=='GET':
            if kind=='missing':return httpx.Response(404)
            user={'id':SUBJECT,'attributes':{'tenant_id':['other' if kind=='foreign' else TENANT]}}
            if kind=='service':user['serviceAccountClientId']='client'
            return httpx.Response(200,json=user)
        events.append('delete')
        return httpx.Response(500 if kind=='failure' else 404 if kind=='missing' else 204)
    api=Directory(httpx.Client(transport=httpx.MockTransport(handle)),'http://auth.localhost:8181/realms/avan','secret',TENANT)
    if kind in ('foreign','service','failure'):
        with pytest.raises(AccountError):api.delete(SUBJECT,lambda:events.append('detach'))
    else:api.delete(SUBJECT,lambda:events.append('detach'))
    assert events==([] if kind in ('foreign','service') else ['detach','delete'])

def test_delete_access_removes_only_target_tenant_and_clears_manager(monkeypatch):
    from contextlib import contextmanager
    from copy import deepcopy
    from commercial import agent_storage,user_accounts as accounts,user_bpms_bindings as bindings
    other='cccccccc-cccc-cccc-cccc-cccccccccccc'
    stored={'organization_access':{'tenant_id':TENANT,'users':[{'subject':SUBJECT},{'subject':other,'manager_subject':SUBJECT}]},bindings.STORE_KEY:{'version':1,'bindings':[{'tenant_id':TENANT,'avan_subject':SUBJECT},{'tenant_id':'other','avan_subject':SUBJECT},{'tenant_id':TENANT,'avan_subject':other}]}}
    class Tx:
        def get(self,key,default=None,**kwargs):return deepcopy(stored.get(key,default))
        def put(self,key,value):stored[key]=value
        def audit(self,*args):pass
    @contextmanager
    def transaction():yield Tx()
    monkeypatch.setattr(agent_storage,'transaction',transaction)
    accounts.remove_access(TENANT,SUBJECT)
    assert stored['organization_access']['users']==[{'subject':other,'manager_subject':None}]
    assert stored[bindings.STORE_KEY]['bindings']==[{'tenant_id':'other','avan_subject':SUBJECT},{'tenant_id':TENANT,'avan_subject':other}]

def test_delete_protects_admin_and_requires_authorization(monkeypatch):
    from fastapi import FastAPI,APIRouter,HTTPException
    from fastapi.testclient import TestClient
    from commercial import user_accounts as accounts,setup_console as setup
    state={'authorized':False,'subject':None}
    def ready():
        if not state['authorized']:raise HTTPException(401,'Unauthorized')
        return 'sid',{'subject':state['subject']}
    def forbidden():raise AssertionError('Provider must not be contacted')
    monkeypatch.setattr(accounts,'directory',forbidden)
    monkeypatch.setattr(setup,'godadmin_identity',lambda:{'subject':SUBJECT})
    app=FastAPI();router=APIRouter();accounts.register(router,ready);app.include_router(router)
    with TestClient(app) as client:
        assert client.post('/api/users/delete',json={'subject':SUBJECT}).status_code==401
        state['authorized']=True
        assert client.post('/api/users/delete',json={'subject':SUBJECT}).status_code==409
        monkeypatch.setattr(setup,'godadmin_identity',lambda:None)
        state['subject']=SUBJECT
        assert client.post('/api/users/delete',json={'subject':SUBJECT}).status_code==409
        assert client.post('/api/users/delete',json={'subject':'local-godadmin'}).status_code==422


def test_user_deletion_revokes_only_selected_sessions(monkeypatch):
    from commercial import production_app as app,user_accounts as accounts
    monkeypatch.setattr(app,'sessions',{'target':{'subject':SUBJECT},'other':{'subject':'someone-else'}})
    accounts.revoke_sessions(SUBJECT)
    assert app.sessions=={'other':{'subject':'someone-else'}}
