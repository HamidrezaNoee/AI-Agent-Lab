from unittest.mock import patch

from commercial import setup_routes


def test_identity_status_is_safe_when_internal_oidc_is_not_ready():
    settings={"oidc":{"managed_by_product":True}}
    identity={
        "tenant_id":"168418b2-8fa6-4414-a37f-83c9a26da332",
        "subject":"godadmin-subject",
        "issuer":"https://id.example/realms/avan",
    }
    with patch.object(setup_routes.setup,"get_setting",side_effect=settings.get),\
         patch.object(setup_routes.setup,"godadmin_identity",return_value=identity):
        result=setup_routes.identity_status(session=True)
    assert result["connected"] is False
    assert result["managed_by_product"] is True
    assert result["godadmin_bound"] is True
    assert result["godadmin_subject"]=="godadmin-subject"
    assert result["godadmin_tenant_id"]==identity["tenant_id"]
    assert "secret" not in result


def test_identity_status_never_requires_customer_secret_entry():
    settings={"oidc":{"managed_by_product":False}}
    with patch.object(setup_routes.setup,"get_setting",side_effect=settings.get),\
         patch.object(setup_routes.setup,"godadmin_identity",return_value=None):
        result=setup_routes.identity_status(session=True)
    assert result["connected"] is False
    assert result["godadmin_bound"] is False
    assert result["customer_secret_entry_required"] is False
