from contextlib import contextmanager

import pytest
from fastapi import HTTPException

from commercial import production_onboarding
from commercial import setup_routes
from commercial import user_accounts


TENANT = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
SUBJECT = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"


class FakeIdentity:
    def __init__(self):
        self.created = []
        self.deleted = []

    def create(self, username, email, name, role, password):
        self.created.append((username, email, name, role, password))
        return SUBJECT

    def delete(self, subject):
        self.deleted.append(subject)


def _body():
    return setup_routes.AvanIdentityCreate(
        username="person",
        email="person@example.com",
        name="Person User",
        role="Expert",
        temporary_password="strong-password-123",
    )


def _settings(key):
    if key == "company":
        return {"tenant_id": TENANT, "company_name": "Test Company"}
    if key == "oidc":
        return {"managed_by_product": True}
    return None


def test_admin_created_user_is_identity_and_avan_authorized_in_one_operation(monkeypatch):
    service = FakeIdentity()

    @contextmanager
    def directory():
        yield service

    monkeypatch.setattr(setup_routes.setup, "get_setting", _settings)
    monkeypatch.setattr(setup_routes.setup, "audit", lambda *_: None)
    monkeypatch.setattr(user_accounts, "directory", directory)

    seen = {}

    def register_managed_identity(**kwargs):
        seen.update(kwargs)
        return {"modules": [1, 2]}

    monkeypatch.setattr(
        production_onboarding,
        "register_managed_identity",
        register_managed_identity,
    )

    result = setup_routes.create_avan_identity(
        _body(), session=("sid", {"subject": "godadmin"})
    )

    assert service.created == [
        (
            "person",
            "person@example.com",
            "Person User",
            "Expert",
            "strong-password-123",
        )
    ]
    assert service.deleted == []
    assert seen["subject"] == SUBJECT
    assert seen["tenant_id"] == TENANT
    assert result["created"] is True
    assert result["authorized"] is True
    assert result["password_temporary"] is False
    assert result["mfa_required"] is False
    assert result["next_step"] == "sign_in"


def test_failed_avan_authorization_rolls_back_new_identity(monkeypatch):
    service = FakeIdentity()

    @contextmanager
    def directory():
        yield service

    monkeypatch.setattr(setup_routes.setup, "get_setting", _settings)
    monkeypatch.setattr(setup_routes.setup, "audit", lambda *_: None)
    monkeypatch.setattr(user_accounts, "directory", directory)

    def deny(**_kwargs):
        raise production_onboarding.ProvisioningDenied("license capacity reached")

    monkeypatch.setattr(production_onboarding, "register_managed_identity", deny)

    with pytest.raises(HTTPException) as exc:
        setup_routes.create_avan_identity(
            _body(), session=("sid", {"subject": "godadmin"})
        )

    assert exc.value.status_code == 409
    assert service.deleted == [SUBJECT]
