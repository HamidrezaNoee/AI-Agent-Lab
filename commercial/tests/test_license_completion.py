from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from types import SimpleNamespace as NS
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
import pytest
from commercial.tests.test_production_agent import state_dir, SCOPE
from commercial import (
    setup_console as setup,
    native_access,
    production_onboarding as onboard,
)
from commercial.licensing.codec import make_payload, sign_license
from commercial.licensing.studio import expiry, issue, create_signer
from commercial.production_license import capacity, ProductionLicenseDenied


def install_license(seats=1, days=30):
    key = ec.generate_private_key(ec.SECP256R1())
    setup.PUBLIC.write_bytes(
        key.public_key().public_bytes(
            serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
        )
    )
    setup.put_setting("installation", {"installation_id": "A" * 64})
    now = datetime.now(timezone.utc)
    payload = make_payload(
        tenant_id=SCOPE["tenant_id"],
        installation_id="A" * 64,
        customer="org",
        max_users=seats,
        modules=[1, 2, 3, 4],
        issued_at=(now - timedelta(days=2)).isoformat(),
        expires_at=(now + timedelta(days=days)).isoformat(),
    )
    setup.put_setting(
        "license",
        {"tenant_id": SCOPE["tenant_id"], "token": sign_license(payload, key)},
    )


def test_license_term_and_seat_boundary(state_dir):
    install_license()
    assert capacity(SCOPE["tenant_id"], "org", 1)["max_users"] == 1
    with pytest.raises(ProductionLicenseDenied):
        capacity(SCOPE["tenant_id"], "org", 2)
    install_license(days=-1)
    with pytest.raises(ProductionLicenseDenied):
        capacity(SCOPE["tenant_id"], "org", 0)
    assert datetime.fromisoformat(expiry(30)) > datetime.now(timezone.utc) + timedelta(
        days=29
    )
    with pytest.raises(ValueError):
        expiry(0)


def test_enrollment_at_capacity_is_atomic_and_existing_access_remains_valid(state_dir):
    install_license()
    with native_access.edit() as data:
        data.update(
            {
                "tenant_id": SCOPE["tenant_id"],
                "company_name": "org",
                "users": [
                    {
                        "subject": "old",
                        "pm_uid": "a" * 32,
                        "enabled": True,
                        "pm_active": True,
                    }
                ],
            }
        )
    pending = {"roles": [], "email_verified": True, "email": "verified@example.test"}
    staff = NS(
        pm_uid="b" * 32,
        status="ACTIVE",
        email="verified@example.test",
        display_name="Test",
    )
    with patch.object(onboard, "find_pending", return_value=pending), patch.object(
        onboard, "_directory", return_value=[staff]
    ):
        with pytest.raises(onboard.ProvisioningDenied):
            onboard.approve_employee(
                tenant_id=SCOPE["tenant_id"],
                subject="new",
                company_name="org",
                pm_uid="b" * 32,
                role="Expert",
                manager_pm_uid=None,
                department_name=None,
            )
    assert len(native_access.read()["users"]) == 1
    assert capacity(SCOPE["tenant_id"], "org", 1)["max_users"] == 1


def test_publisher_cli_uses_encrypted_keys_and_issues_a_valid_term_license(tmp_path):
    private = tmp_path / "private.pem"
    public = tmp_path / "public.pem"
    out = tmp_path / "license.txt"
    create_signer(str(private), str(public), "issuer-test-password")
    assert b"ENCRYPTED PRIVATE KEY" in private.read_bytes()
    result = issue(
        private_path=str(private),
        output_path=str(out),
        password="issuer-test-password",
        tenant_id=SCOPE["tenant_id"],
        installation_id="A" * 64,
        customer="org",
        max_users=25,
        modules=[1, 3],
        expires_at=expiry(90),
    )
    assert result["max_users"] == 25 and out.is_file()
    with pytest.raises(ValueError):
        create_signer(str(private), str(public), "issuer-test-password")


def test_https_customer_origin_keeps_admin_loopback_origin_and_cookie():
    from fastapi import HTTPException
    from starlette.requests import Request
    from starlette.responses import Response
    from commercial import setup_routes
    from unittest.mock import patch

    def request(origin):
        return Request(
            {
                "type": "http",
                "method": "POST",
                "path": "/admin/api/login",
                "headers": [(b"origin", origin.encode())],
                "server": ("127.0.0.1", 8188),
                "scheme": "http",
                "client": ("127.0.0.1", 1),
            }
        )

    with patch.dict(
        "os.environ",
        {
            "AVAN_PUBLIC_ORIGIN": "https://agent.example.org",
            "AVAN_ADMIN_ORIGIN": "http://127.0.0.1:8188",
        },
    ):
        setup_routes._origin(request("http://127.0.0.1:8188"))
        with pytest.raises(HTTPException):
            setup_routes._origin(request("https://agent.example.org"))
        response = Response()
        setup_routes._cookie(response, "test")
        assert "Secure" not in response.headers["set-cookie"]
