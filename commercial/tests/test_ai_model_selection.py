from types import SimpleNamespace
from unittest.mock import Mock
import pytest
from fastapi import HTTPException
from commercial import setup_routes as routes

def test_model_list_sorted_deduplicated_without_settings_mutation(monkeypatch):
 client=Mock()
 client.models.list.return_value=[SimpleNamespace(id='z'),SimpleNamespace(id='a'),SimpleNamespace(id='z')]
 monkeypatch.setattr(routes,'_ai_probe_client',lambda body:client)
 put=Mock();monkeypatch.setattr(routes.setup,'put_setting',put)
 assert routes.ai_models(routes.AIModelProbe(),session={})=={'models':['a','z'],'compatibility_verified':False}
 put.assert_not_called();client.close.assert_called_once()

def test_probe_checks_unsaved_model_without_persisting(monkeypatch):
 client=Mock();monkeypatch.setattr(routes,'_ai_probe_client',lambda body:client)
 put=Mock();monkeypatch.setattr(routes.setup,'put_setting',put)
 result=routes.ai_probe(routes.AIModelProbe(model='future-model'),session={})
 client.models.retrieve.assert_called_once_with('future-model')
 assert result['generation_tested'] is False
 put.assert_not_called();client.close.assert_called_once()

def test_provider_errors_never_expose_key(monkeypatch):
 client=Mock();client.models.list.side_effect=RuntimeError('secret-key')
 monkeypatch.setattr(routes,'_ai_probe_client',lambda body:client)
 with pytest.raises(HTTPException) as err:routes.ai_models(routes.AIModelProbe(),session={})
 assert 'secret-key' not in str(err.value.detail)
 client.close.assert_called_once()

def test_save_model_preserves_existing_key(monkeypatch):
 monkeypatch.setattr(routes.setup,'get_setting',lambda _: {'api_key':'old-key-1234567890'})
 put=Mock();monkeypatch.setattr(routes.setup,'put_setting',put)
 routes.ai_save(routes.AIConfig(enabled=True,model='future-model'),session={})
 assert put.call_args.args[1]['api_key']=='old-key-1234567890'
 assert put.call_args.args[1]['model']=='future-model'
