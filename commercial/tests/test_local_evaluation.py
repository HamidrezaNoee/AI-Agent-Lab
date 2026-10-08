from uuid import uuid4
from unittest.mock import patch
import pytest

from commercial.production_license import (
    capacity, signed_entitlement, ProductionLicenseDenied,
)

TENANT = str(uuid4())


def enable(monkeypatch):
    monkeypatch.setenv('AVAN_LOCAL_EVALUATION', '1')
    monkeypatch.setenv('AVAN_PM_ALLOW_LOCAL_HTTP', '1')
    monkeypatch.setenv('AVAN_PUBLIC_ORIGIN', 'http://127.0.0.1:8188')


def test_local_install_works_without_license_but_keeps_user_limit(monkeypatch):
    enable(monkeypatch)
    with patch('commercial.native_access.seats', return_value=1):
        entitlement = signed_entitlement(None, tenant_id=TENANT, company_name='آزمایش')
    assert entitlement['mode'] == 'local_evaluation'
    assert entitlement['modules'] == frozenset((1, 2, 3, 4))
    assert capacity(TENANT, 'آزمایش', 10)['max_users'] == 10
    with pytest.raises(ProductionLicenseDenied):
        capacity(TENANT, 'آزمایش', 11)


def test_evaluation_requires_real_organization(monkeypatch):
    enable(monkeypatch)
    for tenant, name in (('bad', 'org'), (TENANT, '')):
        with pytest.raises(ProductionLicenseDenied):
            capacity(tenant, name, 0)


def test_normal_or_network_install_does_not_accept_evaluation(monkeypatch):
    enable(monkeypatch)
    monkeypatch.setenv('AVAN_PUBLIC_ORIGIN', 'https://app.example.com')
    with pytest.raises(ProductionLicenseDenied):
        capacity(TENANT, 'آزمایش', 1)
    monkeypatch.setenv('AVAN_PUBLIC_ORIGIN', 'http://127.0.0.1:8188')
    monkeypatch.delenv('AVAN_PM_ALLOW_LOCAL_HTTP')
    with pytest.raises(ProductionLicenseDenied):
        capacity(TENANT, 'آزمایش', 1)
    monkeypatch.setenv('AVAN_PM_ALLOW_LOCAL_HTTP', '1')
    monkeypatch.delenv('AVAN_LOCAL_EVALUATION')
    with pytest.raises(ProductionLicenseDenied):
        capacity(TENANT, 'آزمایش', 1)
