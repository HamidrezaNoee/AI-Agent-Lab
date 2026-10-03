"""Host-only switch to the existing local GodAdmin and remove other login identities."""
import argparse
import getpass
import os
from pathlib import Path
from uuid import UUID
import httpx
from . import setup_console as setup
from .identity_recovery import BASE

def human_accounts(client,headers):
    found=[];offset=0
    while True:
        r=client.get(BASE+'/admin/realms/avan/users',headers=headers,params={'first':offset,'max':100})
        if r.status_code!=200:raise ValueError('Cannot enumerate identities: HTTP '+str(r.status_code))
        rows=r.json()
        if not isinstance(rows,list):raise ValueError('Invalid identity response')
        for user in rows:
            # Do not remove infrastructure service accounts needed by AVAN.
            if user.get('serviceAccountClientId') or str(user.get('username','')).startswith('service-account-'):continue
            found.append(str(UUID(user['id'])))
        if len(rows)<100:break
        offset+=len(rows)
        if offset>10000:raise ValueError('Too many identities; stopped before deletion')
    return found

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--delete-other-accounts',action='store_true')
    args=parser.parse_args()
    state=setup.password_state()
    if not state['changed'] or not state['totp']:raise ValueError('Local GodAdmin must already have a permanent password and verified Authenticator')
    password=getpass.getpass('Password of the ORIGINAL local GodAdmin: ')
    otp=getpass.getpass('Authenticator code of the ORIGINAL local GodAdmin: ')
    if not setup.password_ok(password) or not setup.totp_ok(otp):raise ValueError('Local GodAdmin password or Authenticator is invalid; no account changed')
    accounts=[]
    with httpx.Client(timeout=15,follow_redirects=False,trust_env=False) as client:
        headers={}
        if args.delete_other_accounts:
            config=setup.get_setting('oidc') or {}
            if not config.get('managed_by_product'):raise ValueError('Account cleanup requires bundled identity service')
            secret=Path(os.getenv('AVAN_PROVISIONER_CLIENT_SECRET_PATH','/run/secrets/avan_provisioner_client_secret')).read_text().strip()
            r=client.post(BASE+'/realms/avan/protocol/openid-connect/token',data={'grant_type':'client_credentials','client_id':'avan-provisioner','client_secret':secret})
            if r.status_code!=200:raise ValueError('Identity authorization failed; no accounts changed')
            headers={'Authorization':'Bearer '+r.json()['access_token']}
            accounts=human_accounts(client,headers)
        # Restore access to the already existing local account before external deletion.
        setup.put_setting('godadmin_account',{'username':setup.godadmin_username(),'permanent':True})
        with setup._db() as con:
            con.execute("DELETE FROM settings WHERE name='godadmin_identity'")
        setup.audit('LOCAL_GODADMIN_RETAINED')
        deleted=0
        for subject in accounts:
            r=client.delete(BASE+'/admin/realms/avan/users/'+subject,headers=headers)
            if r.status_code not in (204,404):
                raise ValueError('Local GodAdmin retained; deleted '+str(deleted)+' identities, then stopped: HTTP '+str(r.status_code)+'. Restart AVAN. Re-run to finish.')
            deleted+=1
            with setup._db() as con:
                exists=con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='pending_identity'").fetchone()
                if exists:con.execute('DELETE FROM pending_identity WHERE subject=?',(subject,))
    print('Existing local GodAdmin retained; password and Authenticator unchanged.')
    print('Other Keycloak login identities deleted: '+str(deleted)+'. Infrastructure service accounts preserved.')
    print('ProcessMaker users, cases and business history were not deleted. Restart AVAN to revoke old application sessions.')

if __name__=='__main__':
    try:main()
    except Exception as exc:raise SystemExit(str(exc) if isinstance(exc,ValueError) else 'Operation stopped; inspect services. No secret printed.')
