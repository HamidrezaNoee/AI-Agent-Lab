"""Tenant-scoped identity administration. BPMS grants stay in user_bpms_bindings."""
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import urlsplit
from uuid import UUID
import os
import httpx
from fastapi import Depends,HTTPException
from pydantic import BaseModel,ConfigDict,Field
from . import setup_console as setup

class AccountError(ValueError):pass

class Directory:
    def __init__(self,client,issuer,secret,tenant):
        self.client=client;self.tenant=str(UUID(tenant))
        parts=urlsplit(issuer)
        if parts.path!='/realms/avan' or parts.username or parts.password or parts.query or parts.fragment:
            raise AccountError('تنظیمات سرویس کاربران معتبر نیست.')
        if parts.scheme!='https' and not (parts.scheme=='http' and parts.hostname in ('localhost','127.0.0.1','auth.localhost') and parts.port==8181):
            raise AccountError('نشانی سرویس کاربران امن نیست.')
        self.base=issuer.removesuffix('/realms/avan')+'/admin/realms/avan'
        r=client.post(issuer+'/protocol/openid-connect/token',data={'grant_type':'client_credentials','client_id':'avan-provisioner','client_secret':secret})
        if r.status_code!=200:raise AccountError('مجوز مدیریت کاربران دریافت نشد (HTTP '+str(r.status_code)+').')
        self.headers={'Authorization':'Bearer '+r.json()['access_token']}
    def call(self,method,path,**kwargs):
        r=self.client.request(method,self.base+path,headers=self.headers,**kwargs)
        if not 200<=r.status_code<300:raise AccountError('عملیات کاربر انجام نشد (HTTP '+str(r.status_code)+').')
        return r
    def allowed(self,user):
        return not user.get('serviceAccountClientId') and user.get('attributes',{}).get('tenant_id')==[self.tenant]
    def get(self,subject,*,missing_ok=False):
        subject=str(UUID(subject))
        response=self.client.request('GET',self.base+'/users/'+subject,headers=self.headers)
        if missing_ok and response.status_code==404:return None
        if response.status_code!=200:raise AccountError('دریافت کاربر انجام نشد (HTTP '+str(response.status_code)+').')
        user=response.json()
        if not self.allowed(user):raise AccountError('این حساب متعلق به سازمان انتخاب‌شده نیست.')
        return user
    def users(self):
        result=[]
        for offset in range(0,10000,100):
            rows=self.call('GET','/users',params={'first':offset,'max':100}).json()
            for u in rows:
                if self.allowed(u):result.append({'subject':u['id'],'username':u.get('username',''),'name':(' '.join([u.get('firstName',''),u.get('lastName','')])).strip(),'email':u.get('email',''),'identity_enabled':bool(u.get('enabled'))})
            if len(rows)<100:return {'users':result,'truncated':False}
        return {'users':result,'truncated':True}
    def update(self,subject,username,name,email):
        user=self.get(subject)
        first,_,last=name.strip().partition(' ')
        payload={'username':username,'firstName':first,'lastName':last,'email':email}
        if email!=user.get('email',''):payload['emailVerified']=False
        self.call('PUT','/users/'+str(UUID(subject)),json=payload)
    def password(self,subject,password,after_reset=None):
        self.get(subject)
        self.call('PUT','/users/'+str(UUID(subject))+'/reset-password',json={'type':'password','value':password,'temporary':True})
        if after_reset:after_reset()
        self.call('POST','/users/'+str(UUID(subject))+'/logout')

    def delete(self,subject,before_delete=None):
        self.get(subject,missing_ok=True)
        if before_delete:before_delete()
        response=self.client.request('DELETE',self.base+'/users/'+str(UUID(subject)),headers=self.headers)
        if response.status_code not in (204,404):
            raise AccountError('حذف هویت انجام نشد؛ دسترسی AVAN قطع شده است. دوباره حذف را انجام دهید (HTTP '+str(response.status_code)+').')

def revoke_sessions(subject):
    from .production_app import sessions,_session_lock
    with _session_lock:
        for sid,row in list(sessions.items()):
            if row.get('subject')==subject:sessions.pop(sid,None)

def remove_access(tenant,subject):
    # One AVAN SQL transaction removes grants and all BPMS links. No BPMS writes.
    from . import agent_storage,native_access,user_bpms_bindings as bindings
    with agent_storage.transaction() as tx:
        data=tx.get('organization_access',dict(native_access.EMPTY),lock=True)
        if data.get('tenant_id')==tenant:
            data['users']=[u for u in data.get('users',[]) if u.get('subject')!=subject]
            for user in data['users']:
                if user.get('manager_subject')==subject:user['manager_subject']=None
            tx.put('organization_access',data)
        state=bindings._state(tx,lock=True)
        state['bindings']=[b for b in state['bindings'] if not (b.get('tenant_id')==tenant and b.get('avan_subject')==subject)]
        tx.put(bindings.STORE_KEY,state)
        tx.audit(tenant,'GodAdmin','USER_ACCESS_REMOVED',{'subject':subject})

@contextmanager
def directory():
    config=setup.get_setting('oidc') or {};company=setup.get_setting('company') or {}
    try:
        if not config.get('managed_by_product'):raise AccountError('سرویس کاربران تنظیم نشده است.')
        secret=Path(os.getenv('AVAN_PROVISIONER_CLIENT_SECRET_PATH','/run/secrets/avan_provisioner_client_secret')).read_text().strip()
        with httpx.Client(timeout=15,follow_redirects=False,trust_env=False) as client:
            yield Directory(client,config['issuer'],secret,company['tenant_id'])
    except (AccountError,ValueError) as exc:raise HTTPException(409,str(exc)) from exc
    except (httpx.HTTPError,OSError,KeyError) as exc:raise HTTPException(503,'سرویس مدیریت کاربران در دسترس نیست.') from exc

class Profile(BaseModel):
    model_config=ConfigDict(extra='forbid')
    subject:UUID
    username:str=Field(min_length=3,max_length=80,pattern=r'^[A-Za-z0-9_.@-]+$')
    name:str=Field(min_length=2,max_length=240)
    email:str=Field(max_length=240,pattern=r'^[^\s@]+@[^\s@]+\.[^\s@]+$')

class Password(BaseModel):
    model_config=ConfigDict(extra='forbid')
    subject:UUID
    password:str=Field(min_length=16,max_length=128)

class Delete(BaseModel):
    model_config=ConfigDict(extra='forbid')
    subject:UUID

def register(router,ready):
    @router.get('/api/users/identities')
    def identities(session=Depends(ready)):
        with directory() as service:return service.users()
    @router.post('/api/users/profile')
    def profile(body:Profile,session=Depends(ready)):
        if not body.name.strip():raise HTTPException(422,'نام کاربر خالی است.')
        with directory() as service:service.update(str(body.subject),body.username,body.name,body.email)
        setup.audit('USER_PROFILE_UPDATED')
        return {'updated':True}
    @router.post('/api/users/password')
    def password(body:Password,session=Depends(ready)):
        with directory() as service:service.password(str(body.subject),body.password,lambda:revoke_sessions(str(body.subject)))
        setup.audit('USER_PASSWORD_RESET')
        return {'updated':True,'temporary':True}

    @router.post('/api/users/delete')
    def delete(body:Delete,session=Depends(ready)):
        subject=str(body.subject)
        bound=setup.godadmin_identity() or {}
        if subject in (bound.get('subject'),session[1].get('subject')):
            raise HTTPException(409,'حذف حساب اصلی یا حساب جاری مجاز نیست.')
        with directory() as service:
            # Validate tenant/service-account boundaries before any local mutation.
            # Missing identities allow retry after an interrupted deletion.
            def detach():
                remove_access(service.tenant,subject)
                revoke_sessions(subject)
            service.delete(subject,detach)
            with setup._db() as con:
                exists=con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='pending_identity'").fetchone()
                if exists:con.execute('DELETE FROM pending_identity WHERE tenant_id=? AND subject=?',(service.tenant,subject))
        setup.audit('USER_DELETED')
        return {'deleted':True,'subject':subject}
