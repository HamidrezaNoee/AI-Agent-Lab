import json
from uuid import UUID
import httpx
import pytest
from commercial.identity_operator import create


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
