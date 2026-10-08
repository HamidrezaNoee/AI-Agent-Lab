import httpx
import pytest
from commercial.identity_recovery import recover

UID='aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa'

def client_for(calls,enabled=True):
    def handle(request):
        calls.append(request)
        if request.url.path.endswith('/token'):return httpx.Response(200,json={'access_token':'private'})
        if request.url.path.endswith('/users'):return httpx.Response(200,json=[{'id':UID,'username':'newgod','enabled':enabled}])
        return httpx.Response(204)
    return httpx.Client(transport=httpx.MockTransport(handle))

def test_unlock_does_not_change_credentials_or_binding():
    calls=[]
    with client_for(calls) as client:assert recover(client,'secret','newgod',expected_subject=UID)==UID
    assert [r.method for r in calls]==['POST','GET','DELETE']
    assert calls[-1].url.path.endswith('/brute-force/users/'+UID)

def test_password_recovery_sets_permanent_password_revokes_sessions_keeps_existing_otp():
    calls=[]
    with client_for(calls) as client:recover(client,'secret','newgod','secure-password-123',UID)
    assert [r.method for r in calls]==['POST','GET','PUT','POST','DELETE']
    assert calls[2].url.path.endswith('/reset-password')
    assert b'"temporary":false' in calls[2].content
    assert all('/credentials/' not in r.url.path for r in calls)

def test_wrong_bound_identity_cannot_be_recovered():
    calls=[]
    with client_for(calls) as client,pytest.raises(ValueError,match='bound GodAdmin'):
        recover(client,'secret','newgod',expected_subject='bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb')
    assert len(calls)==2

def test_disabled_identity_is_not_enabled():
    calls=[]
    with client_for(calls,False) as client,pytest.raises(ValueError,match='disabled'):
        recover(client,'secret','newgod')
    assert len(calls)==2


def test_password_recovery_clears_only_legacy_forced_actions():
    calls=[]
    def handle(request):
        calls.append(request)
        if request.url.path.endswith('/token'):
            return httpx.Response(200,json={'access_token':'private'})
        if request.url.path.endswith('/users'):
            return httpx.Response(200,json=[{
                'id':UID,'username':'newgod','enabled':True,
                'requiredActions':['UPDATE_PASSWORD','CONFIGURE_TOTP','VERIFY_EMAIL']
            }])
        return httpx.Response(204)
    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        recover(client,'secret','newgod','secure-password-123',UID)
    import json
    repair=next(
        r for r in calls
        if r.method=='PUT' and r.url.path.endswith('/users/'+UID)
    )
    assert json.loads(repair.content)=={
        'requiredActions':['VERIFY_EMAIL'],
        'enabled':True,
    }
