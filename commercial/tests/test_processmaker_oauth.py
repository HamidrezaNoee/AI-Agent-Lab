import time
from unittest.mock import patch

from commercial import setup_routes as routes


def test_managed_config_does_not_store_processmaker_password():
    tokens={"access_token":"access-token-value","refresh_token":"refresh-token-value",
            "expires_in":3600,"token_type":"Bearer"}
    config=routes._pm_managed_config(
        "http://host.docker.internal:84","workflow","client-id","client-secret",tokens
    )
    assert config["token_managed"] is True
    assert config["bearer_token"]=="access-token-value"
    assert config["refresh_token"]=="refresh-token-value"
    assert config["oauth_client_secret"]=="client-secret"
    assert "password" not in config
    assert "username" not in config
    assert config["access_token_expires_at"]>time.time()


def test_oauth_connect_saves_tokens_after_directory_check_without_password():
    body=routes.PMOAuthConnect(
        base_url="http://host.docker.internal:84",
        workspace="workflow",
        client_id="client-id",
        client_secret="client-secret",
        username="administrator",
        password="temporary-password",
    )
    tokens={"access_token":"access-token-value","refresh_token":"refresh-token-value",
            "expires_in":3600,"token_type":"Bearer"}
    saved={}
    with patch.object(routes,"_pm_oauth_token",return_value=tokens) as issue, \
         patch.object(routes,"_pm_directory_check",return_value=200) as check, \
         patch.object(routes.setup,"put_setting",side_effect=lambda name,value:saved.update(value)), \
         patch.object(routes.setup,"audit"):
        result=routes.pm_oauth_connect(body,session=("sid",{}))
    assert result["saved"] is True
    assert result["password_stored"] is False
    assert result["refresh_token_stored"] is True
    assert saved["oauth_client_secret"]=="client-secret"
    assert saved["refresh_token"]=="refresh-token-value"
    assert "password" not in saved
    assert "username" not in saved
    payload=issue.call_args.args[2]
    assert payload["grant_type"]=="password"
    assert payload["username"]=="administrator"
    assert payload["password"]=="temporary-password"
    check.assert_called_once()


def test_oauth_connect_can_reuse_stored_client_secret():
    previous={
        "base_url":"http://host.docker.internal:84",
        "workspace":"workflow",
        "oauth_client_id":"client-id",
        "oauth_client_secret":"stored-secret",
    }
    body=routes.PMOAuthConnect(
        base_url=previous["base_url"],workspace="workflow",
        client_id="client-id",client_secret="",
        username="administrator",password="temporary-password",
    )
    tokens={"access_token":"new-access-token","refresh_token":"new-refresh-token",
            "expires_in":3600,"token_type":"Bearer"}
    with patch.object(routes.setup,"get_setting",return_value=previous), \
         patch.object(routes,"_pm_oauth_token",return_value=tokens) as issue, \
         patch.object(routes,"_pm_directory_check",return_value=200), \
         patch.object(routes.setup,"put_setting"), \
         patch.object(routes.setup,"audit"):
        routes.pm_oauth_connect(body,session=("sid",{}))
    assert issue.call_args.args[2]["client_secret"]=="stored-secret"


def test_refresh_rotates_refresh_token_and_persists_new_access_token():
    saved={
        "base_url":"http://host.docker.internal:84",
        "workspace":"workflow",
        "bearer_token":"old-access-token",
        "oauth_client_id":"client-id",
        "oauth_client_secret":"client-secret",
        "refresh_token":"old-refresh-token",
        "access_token_expires_at":time.time()-10,
        "token_managed":True,
    }
    tokens={"access_token":"new-access-token","refresh_token":"new-refresh-token",
            "expires_in":7200,"token_type":"Bearer"}
    written={}
    with patch.object(routes,"_pm_oauth_token",return_value=tokens) as issue, \
         patch.object(routes.setup,"put_setting",side_effect=lambda name,value:written.update(value)), \
         patch.object(routes.setup,"audit"):
        result=routes._pm_refresh_saved(saved)
    assert issue.call_args.args[2]["grant_type"]=="refresh_token"
    assert issue.call_args.args[2]["refresh_token"]=="old-refresh-token"
    assert result["bearer_token"]=="new-access-token"
    assert result["refresh_token"]=="new-refresh-token"
    assert written["refresh_token"]=="new-refresh-token"


def test_valid_saved_refreshes_before_expiry():
    saved={"token_managed":True,"access_token_expires_at":time.time()+20}
    refreshed={**saved,"bearer_token":"fresh","access_token_expires_at":time.time()+3600}
    with patch.object(routes,"_pm_refresh_saved",return_value=refreshed) as refresh:
        result=routes._pm_valid_saved(saved)
    refresh.assert_called_once_with(saved)
    assert result["bearer_token"]=="fresh"
