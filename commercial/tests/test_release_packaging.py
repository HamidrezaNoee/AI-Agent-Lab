"""Check production COPY inputs and first boot outside the source checkout."""
import fnmatch
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys


def test_production_copy_layout_imports_and_boots_without_customer_databases(tmp_path):
    root=Path(__file__).resolve().parents[2]
    patterns=[x.strip() for x in (root/'.dockerignore').read_text().splitlines() if x.strip() and not x.startswith('#')]
    for line in (root/'commercial/Dockerfile.production').read_text().splitlines():
        if not line.startswith('COPY '):continue
        source,target=line.split()[-2:]
        source_path=root/source
        assert source_path.exists(),source
        # Catch broad filename exclusions, including the former *secret* rule
        # that unintentionally excluded secretary_agent.py.
        assert not any(fnmatch.fnmatch(source,p) for p in patterns),source
        dest=tmp_path/target.removeprefix('/app/')
        dest.parent.mkdir(parents=True,exist_ok=True)
        if source_path.is_dir():shutil.copytree(source_path,dest,dirs_exist_ok=True)
        else:shutil.copy2(source_path,dest)
    code="from commercial.setup_console import initialize,get_setting; initialize(); from commercial.production_app import app; assert app.title=='AVAN'; assert not get_setting('agent_sql'); from commercial.identity_operator import create; print('COPY layout boot OK')"
    env={**os.environ,'PYTHONPATH':str(tmp_path),'AVAN_STATE_DIR':str(tmp_path/'state'),
         'AVAN_BFF_CLIENT_SECRET_PATH':str(tmp_path/'absent-secret')}
    subprocess.run([sys.executable,'-c',code],cwd=tmp_path,env=env,check=True,capture_output=True)


def test_realm_tenant_is_admin_only_and_https_has_exact_callback():
    root=Path(__file__).resolve().parents[2]
    for filename in ('avan-realm.json','avan-realm-https.json'):
        realm=json.loads((root/'infra/keycloak'/filename).read_text())
        config=realm['components']['org.keycloak.userprofile.UserProfileProvider'][0]['config']
        profile=json.loads(config['kc.user.profile.config'][0])
        tenant=next(x for x in profile['attributes'] if x['name']=='tenant_id')
        assert tenant['permissions']['edit']==['admin']
        if filename.endswith('https.json'):
            bff=next(x for x in realm['clients'] if x['clientId']=='avan-bff')
            assert bff['redirectUris']==['${AVAN_PUBLIC_ORIGIN}/auth/callback']
    gateway=(root/'infra/caddy/Caddyfile').read_text()
    assert 'respond @admin 404' in gateway
