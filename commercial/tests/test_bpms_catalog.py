from commercial import setup_console as setup
from unittest.mock import patch

from commercial import setup_routes as routes


def _store():
    return {
        "mysql":{
            "host":"host.docker.internal","port":3306,"database":"bitnami_pm",
            "username":"avan_reader","password":"mysql-secret","tls":False,
            "ca_pem":"","timezone":"Asia/Tehran","enabled":True,
        },
        "processmaker":{
            "base_url":"http://host.docker.internal:84","workspace":"workflow",
            "bearer_token":"access-token-value","oauth_client_id":"client-id",
            "oauth_client_secret":"oauth-secret","refresh_token":"refresh-token-value",
            "access_token_expires_at":4102444800,"token_managed":True,
        },
    }


def test_legacy_processmaker_is_migrated_to_unified_bpms_profile_without_exposing_secrets():
    data=_store()
    def get_setting(name):
        return data.get(name)
    def put_setting(name,value):
        data[name]=value
    with patch.object(routes.setup,"get_setting",side_effect=get_setting), \
         patch.object(routes.setup,"put_setting",side_effect=put_setting), \
         patch.object(routes.setup,"audit"), \
         patch("commercial.user_bpms_bindings.list_bindings",return_value=[]):
        state=routes._pm_profiles_state()
        assert len(state["profiles"])==1
        profile=state["profiles"][0]
        public=routes._pm_profile_public(profile,state["active_id"])
    assert public["engine"]=="processmaker"
    assert public["active"] is True
    assert public["mysql"]["has_password"] is True
    assert public["oauth"]["has_client_secret"] is True
    assert "password" not in public["mysql"]
    assert "oauth_client_secret" not in public["oauth"]
    assert "bearer_token" not in public["oauth"]
    assert data["processmaker_profiles"]["profiles"][0]["mysql"]["password"]=="mysql-secret"


def test_processmaker_profile_copy_keeps_secrets_server_side_and_is_inactive():
    data=_store()
    seed={
        "id":"a"*24,"name":"PM اصلی","engine":"processmaker",
        "mysql":data["mysql"],"api":data["processmaker"],
    }
    data["processmaker_profiles"]={"active_id":seed["id"],"profiles":[seed]}
    def get_setting(name):
        return data.get(name)
    def put_setting(name,value):
        data[name]=value
    with patch.object(routes.setup,"get_setting",side_effect=get_setting), \
         patch.object(routes.setup,"put_setting",side_effect=put_setting), \
         patch.object(routes.setup,"audit"):
        result=routes.bpms_catalog_copy(
            routes.BPMSCatalogCopy(connection_type="processmaker",id=seed["id"],name="PM کپی"),
            session=("sid",{})
        )
        state=data["processmaker_profiles"]
        copied=next(p for p in state["profiles"] if p["id"]==result["id"])
    assert result["active"] is False
    assert state["active_id"]==seed["id"]
    assert copied["mysql"]["password"]=="mysql-secret"
    assert copied["api"]["oauth_client_secret"]=="oauth-secret"
    assert copied["api"]["refresh_token"]=="refresh-token-value"


def test_processmaker_profile_save_tests_both_mysql_and_oauth_before_becoming_active():
    data={}
    def get_setting(name):
        return data.get(name)
    def put_setting(name,value):
        data[name]=value
    body=routes.PMProfileSave(
        name="PM تست",
        mysql_host="host.docker.internal",mysql_port=3306,
        mysql_database="bitnami_pm",mysql_username="avan_reader",
        mysql_password="mysql-secret",mysql_tls=False,mysql_timezone="Asia/Tehran",
        oauth_base_url="http://host.docker.internal:84",oauth_workspace="workflow",
        oauth_client_id="client-id",oauth_client_secret="oauth-secret",
        oauth_username="administrator",oauth_password="temporary-password",
        activate=True,
    )
    tokens={"access_token":"access-token-value","refresh_token":"refresh-token-value",
            "expires_in":3600,"token_type":"Bearer"}
    with patch.object(routes.setup,"get_setting",side_effect=get_setting), \
         patch.object(routes.setup,"put_setting",side_effect=put_setting), \
         patch.object(routes.setup,"audit"), \
         patch.object(routes,"_mysql_check",return_value={"connected":True}) as mysql_check, \
         patch.object(routes,"_pm_oauth_token",return_value=tokens), \
         patch.object(routes,"_pm_directory_check",return_value=200) as api_check:
        result=routes.bpms_processmaker_save(body,session=("sid",{}))
    assert result["saved"] is True and result["active"] is True
    assert mysql_check.called and api_check.called
    assert data["mysql"]["password"]=="mysql-secret"
    assert data["processmaker"]["oauth_client_secret"]=="oauth-secret"
    profile=data["processmaker_profiles"]["profiles"][0]
    assert "oauth_password" not in profile["api"]
    assert "oauth_username" not in profile["api"]


def test_deleting_active_processmaker_profile_clears_runtime_legacy_connection():
    data=_store()
    seed={
        "id":"b"*24,"name":"PM فعال","engine":"processmaker",
        "mysql":data["mysql"],"api":data["processmaker"],
    }
    data["processmaker_profiles"]={"active_id":seed["id"],"profiles":[seed]}
    def get_setting(name):
        return data.get(name)
    def put_setting(name,value):
        data[name]=value
    with patch.object(routes.setup,"get_setting",side_effect=get_setting), \
         patch.object(routes.setup,"put_setting",side_effect=put_setting), \
         patch.object(routes.setup,"audit"), \
         patch("commercial.user_bpms_bindings.list_bindings",return_value=[]):
        result=routes.bpms_catalog_delete(
            routes.BPMSCatalogRef(connection_type="processmaker",id=seed["id"]),
            session=("sid",{})
        )
    assert result["deleted"] is True
    assert data["mysql"]=={}
    assert data["processmaker"]=={}
    assert data["processmaker_profiles"]["active_id"] is None


def test_processmaker_profile_store_is_registered():
    assert "processmaker_profiles" in setup.ALLOWED_SETTINGS
