"""Docker-host-only recovery of an existing bundled Keycloak account.

No HTTP route. Password input is hidden; OTP, roles, tenant and bindings are kept.
"""
import argparse
import getpass
import os
from pathlib import Path
import re
from uuid import UUID
import httpx
from . import setup_console as setup

BASE='http://keycloak:8080'

def recover(client, secret, username, password=None, expected_subject=None):
    if not re.fullmatch(r'[A-Za-z0-9_.@-]{3,80}',username):
        raise ValueError('Enter the exact AVAN identity username, not a BPMS username.')
    if password is not None and not 16<=len(password)<=128:
        raise ValueError('Temporary password must contain 16 to 128 characters.')
    def call(method,path,**kwargs):
        response=client.request(method,BASE+path,**kwargs)
        if not 200<=response.status_code<300:
            raise ValueError('Identity recovery stopped: HTTP '+str(response.status_code)+'. No automatic retry.')
        return response
    token=call('POST','/realms/avan/protocol/openid-connect/token',data={
        'grant_type':'client_credentials','client_id':'avan-provisioner','client_secret':secret
    }).json()['access_token']
    headers={'Authorization':'Bearer '+token}
    prefix='/admin/realms/avan'
    users=call('GET',prefix+'/users',params={'username':username,'exact':'true'},headers=headers).json()
    if len(users)!=1 or users[0].get('username')!=username:
        raise ValueError('Exactly one matching identity is required; no account changed.')
    subject=str(UUID(users[0]['id']))
    if expected_subject and subject!=str(UUID(expected_subject)):
        raise ValueError('Username does not match the bound GodAdmin; no account changed.')
    if not users[0].get('enabled'):
        raise ValueError('Account is disabled; this command does not enable disabled accounts.')
    if password is not None:
        call('PUT',prefix+'/users/'+subject+'/reset-password',headers=headers,
             json={'type':'password','value':password,'temporary':False})
        required=list(users[0].get('requiredActions') or [])
        cleaned=[x for x in required if x not in ('UPDATE_PASSWORD','CONFIGURE_TOTP')]
        if cleaned!=required:
            call('PUT',prefix+'/users/'+subject,headers=headers,
                 json={'requiredActions':cleaned,'enabled':True})
        call('POST',prefix+'/users/'+subject+'/logout',headers=headers)
    call('DELETE',prefix+'/attack-detection/brute-force/users/'+subject,headers=headers)
    return subject

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--username',required=True)
    parser.add_argument('--reset-password',action='store_true')
    args=parser.parse_args()
    config=setup.get_setting('oidc') or {}
    if not config.get('managed_by_product'):
        raise ValueError('Recovery is available only for the bundled AVAN realm.')
    secret=Path(os.getenv('AVAN_PROVISIONER_CLIENT_SECRET_PATH',
                          '/run/secrets/avan_provisioner_client_secret')).read_text().strip()
    password=None
    if args.reset_password:
        password=getpass.getpass('New login password (16+ characters): ')
        if password!=getpass.getpass('Repeat login password: '):
            raise ValueError('Passwords differ; no account changed.')
    bound=setup.godadmin_identity() or {}
    with httpx.Client(timeout=15,follow_redirects=False,trust_env=False) as client:
        recover(client,secret,args.username,password,bound.get('subject'))
    setup.audit('IDENTITY_HOST_PASSWORD_RECOVERY' if password else 'IDENTITY_HOST_UNLOCK')
    print('Account unlocked. Authenticator, roles, tenant and AVAN bindings were preserved.')
    if password:print('Sign in with the new password. Existing Authenticator credentials are preserved and remain conditional.')

if __name__=='__main__':
    try:main()
    except Exception as exc:
        raise SystemExit(str(exc) if isinstance(exc,ValueError) else 'Recovery unavailable; inspect service status. No secret printed.')
