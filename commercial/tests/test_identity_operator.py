import json
from uuid import UUID
import httpx
import pytest
from commercial.identity_operator import ManagedIdentityService,create


def test_new_identity_is_login_ready_only_after_tenant_and_role_are_confirmed():
    tenant = str(UUID(int=1))
    subject = str(UUID(int=2))
    calls = []
    payload = {}

    def respond(request):
        calls.append((request.method, request.url.path))
        if request.url.path.endswith("/token"):
            return httpx.Response(200, json={"access_token": "test"})
        if request.url.path.endswith("/roles/SysAdmin"):
            return httpx.Response(200, json={"id": "role", "name": "SysAdmin"})
        if request.url.path.endswith("/users"):
            if request.method == "GET":
                return httpx.Response(200, json=[])
            payload.update(json.loads(request.content))
            return httpx.Response(
                201,
                headers={
                    "Location": "https://auth.test/admin/realms/avan/users/" + subject
                },
            )
        if request.method == "GET":
            return httpx.Response(200, json=payload)
        return httpx.Response(204)

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        assert (
            create(
                client,
                "https://auth.test/realms/avan",
                "0123456789abcdef",
                tenant,
                "ardalan",
                "user@test.example",
                "کاربر سازمان",
                "SysAdmin",
                "temporary-password",
            )
            == subject
        )
    assert payload["enabled"] is False
    assert payload["requiredActions"] == []
    assert payload["credentials"] == [{
        "type": "password",
        "value": "temporary-password",
        "temporary": False,
    }]
    assert calls[-2][1].endswith("/role-mappings/realm") and calls[-1][0] == "PUT"


def test_existing_identity_cannot_be_overwritten():
    writes = []

    def respond(request):
        if request.url.path.endswith("/token"):
            return httpx.Response(200, json={"access_token": "test"})
        if request.method != "GET":
            writes.append(request)
        return httpx.Response(200, json=[{"id": "existing"}])

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        with pytest.raises(ValueError, match="از قبل وجود دارد"):
            create(
                client,
                "https://auth.test/realms/avan",
                "0123456789abcdef",
                str(UUID(int=1)),
                "user",
                "user@test.example",
                "User",
                "Expert",
                "temporary-password",
            )
    assert not writes


def test_existing_identity_role_comes_from_keycloak_realm_mapping():
    tenant=str(UUID(int=1))
    subject=str(UUID(int=2))
    def respond(request):
        if request.url.path.endswith('/token'):
            return httpx.Response(200,json={'access_token':'test'})
        if request.url.path.endswith('/users/'+subject):
            return httpx.Response(200,json={
                'id':subject,
                'username':'person',
                'attributes':{'tenant_id':[tenant]},
            })
        if request.url.path.endswith('/users/'+subject+'/role-mappings/realm'):
            return httpx.Response(200,json=[
                {'id':'offline','name':'offline_access'},
                {'id':'expert','name':'Expert'},
            ])
        return httpx.Response(404)
    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        service=ManagedIdentityService(
            client,'https://auth.test/realms/avan',
            '0123456789abcdef',tenant
        )
        assert service.avan_role(subject)=='Expert'


def test_existing_identity_with_ambiguous_avan_roles_is_rejected():
    tenant=str(UUID(int=1))
    subject=str(UUID(int=2))
    def respond(request):
        if request.url.path.endswith('/token'):
            return httpx.Response(200,json={'access_token':'test'})
        if request.url.path.endswith('/users/'+subject):
            return httpx.Response(200,json={
                'id':subject,
                'username':'person',
                'attributes':{'tenant_id':[tenant]},
            })
        if request.url.path.endswith('/users/'+subject+'/role-mappings/realm'):
            return httpx.Response(200,json=[
                {'id':'expert','name':'Expert'},
                {'id':'manager','name':'Manager'},
            ])
        return httpx.Response(404)
    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        service=ManagedIdentityService(
            client,'https://auth.test/realms/avan',
            '0123456789abcdef',tenant
        )
        with pytest.raises(ValueError,match='دقیقاً یک نقش'):
            service.avan_role(subject)



def test_role_change_replaces_only_avan_realm_role():
    tenant=str(UUID(int=1))
    subject=str(UUID(int=2))
    calls=[]

    def respond(request):
        calls.append(request)
        if request.url.path.endswith('/token'):
            return httpx.Response(200,json={'access_token':'test'})
        if request.url.path.endswith('/users/'+subject) and request.method=='GET':
            return httpx.Response(200,json={
                'id':subject,
                'username':'person',
                'attributes':{'tenant_id':[tenant]},
            })
        if request.url.path.endswith('/users/'+subject+'/role-mappings/realm') and request.method=='GET':
            return httpx.Response(200,json=[
                {'id':'offline','name':'offline_access'},
                {'id':'expert','name':'Expert'},
            ])
        if request.url.path.endswith('/roles/Manager'):
            return httpx.Response(200,json={'id':'manager','name':'Manager'})
        if request.url.path.endswith('/users/'+subject+'/role-mappings/realm'):
            return httpx.Response(204)
        return httpx.Response(404)

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        service=ManagedIdentityService(
            client,'https://auth.test/realms/avan',
            '0123456789abcdef',tenant
        )
        assert service.set_avan_role(subject,'Manager')=='Manager'

    import json
    deletes=[
        json.loads(req.content)
        for req in calls
        if req.method=='DELETE' and req.url.path.endswith('/role-mappings/realm')
    ]
    posts=[
        json.loads(req.content)
        for req in calls
        if req.method=='POST' and req.url.path.endswith('/role-mappings/realm')
    ]
    assert deletes==[[{'id':'expert','name':'Expert'}]]
    assert posts==[[{'id':'manager','name':'Manager'}]]
