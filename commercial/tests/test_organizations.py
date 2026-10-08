from unittest.mock import patch

from commercial import setup_routes


LEGACY_TENANT="168418b2-8fa6-4414-a37f-83c9a26da332"


def _settings_store():
    return {
        "company":{
            "tenant_id":LEGACY_TENANT,
            "company_name":"Iran Rover",
        }
    }


def test_legacy_company_is_surfaced_as_primary_organization():
    store=_settings_store()
    with patch.object(setup_routes.setup,"get_setting",side_effect=store.get):
        result=setup_routes.organizations_get(session=True)
    assert result["primary_tenant_id"]==LEGACY_TENANT
    assert result["organizations"]==[
        {
            "tenant_id":LEGACY_TENANT,
            "company_name":"Iran Rover",
            "enabled":True,
            "is_primary":True,
            "created_utc":result["organizations"][0]["created_utc"],
            "updated_utc":result["organizations"][0]["updated_utc"],
        }
    ]


def test_create_edit_and_toggle_organization_preserves_tenant_id():
    store=_settings_store()

    def put(name,value):
        store[name]=value

    with patch.object(setup_routes.setup,"get_setting",side_effect=store.get),\
         patch.object(setup_routes.setup,"put_setting",side_effect=put),\
         patch.object(setup_routes.setup,"audit"):
        created=setup_routes.organization_save(
            setup_routes.OrganizationSave(
                company_name="TAV Company",enabled=True
            ),
            session=True,
        )
        new_id=created["tenant_id"]
        assert new_id!=LEGACY_TENANT
        assert store["company"]["tenant_id"]==LEGACY_TENANT
        assert len(store["organizations"]["organizations"])==2

        edited=setup_routes.organization_save(
            setup_routes.OrganizationSave(
                tenant_id=new_id,
                company_name="TAV Holding",
                enabled=False,
            ),
            session=True,
        )
        assert edited["tenant_id"]==new_id
        assert edited["company_name"]=="TAV Holding"
        assert edited["enabled"] is False

        enabled=setup_routes.organization_enabled(
            setup_routes.OrganizationEnabled(
                tenant_id=new_id,enabled=True
            ),
            session=True,
        )
        assert enabled=={"saved":True,"tenant_id":new_id,"enabled":True}

        result=setup_routes.organizations_get(session=True)
        row=next(x for x in result["organizations"] if x["tenant_id"]==new_id)
        assert row["company_name"]=="TAV Holding"
        assert row["enabled"] is True
        assert row["is_primary"] is False


def test_editing_primary_organization_keeps_tenant_and_updates_legacy_company():
    store=_settings_store()

    def put(name,value):
        store[name]=value

    with patch.object(setup_routes.setup,"get_setting",side_effect=store.get),\
         patch.object(setup_routes.setup,"put_setting",side_effect=put),\
         patch.object(setup_routes.setup,"audit"):
        updated=setup_routes.organization_save(
            setup_routes.OrganizationSave(
                tenant_id=LEGACY_TENANT,
                company_name="Iran Rover Holding",
                enabled=True,
            ),
            session=True,
        )

    assert updated["tenant_id"]==LEGACY_TENANT
    assert store["company"]=={
        "tenant_id":LEGACY_TENANT,
        "company_name":"Iran Rover Holding",
    }
