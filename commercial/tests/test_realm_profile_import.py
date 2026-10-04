"""Regression for the Keycloak 26.7.3 fresh-realm import failure.

Disabled unmanaged attributes are represented by an absent/null policy, not
the string DISABLED (which is not a member of UPConfig.UnmanagedAttributePolicy).
"""
import json
from pathlib import Path
import pytest

@pytest.mark.parametrize('filename', ['avan-realm.json', 'avan-realm-https.json'])
def test_profile_import_keeps_default_disabled_policy_and_managed_tenant(filename):
    realm = json.loads((Path(__file__).resolve().parents[2] / 'infra/keycloak' / filename).read_text())
    providers = realm['components']['org.keycloak.userprofile.UserProfileProvider']
    assert len(providers) == 1
    profile = json.loads(providers[0]['config']['kc.user.profile.config'][0])
    assert profile.get('unmanagedAttributePolicy') is None
    attributes = {item['name']: item for item in profile['attributes']}
    assert set(attributes) == {'username', 'email', 'firstName', 'lastName', 'tenant_id'}
    assert attributes['tenant_id']['permissions'] == {'view': ['admin'], 'edit': ['admin']}
    assert attributes['tenant_id']['multivalued'] is False
    assert all(item['permissions']['edit'] == ['admin'] for item in attributes.values())
