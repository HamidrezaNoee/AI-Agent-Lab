"""Per-bound-user PM OAuth grants; never store a ProcessMaker password."""
import hashlib,json,time
from . import agent_storage
from .agent_workspace import source_user_key,scope_stamp
from .user_bpms_bindings import processmaker_profile
from .setup_routes import _pm_oauth_token
from fastapi import HTTPException

def endpoint_stamp(api):return hashlib.sha256(json.dumps([api.get('base_url'),api.get('workspace')]).encode()).hexdigest()
def grant_key(scope,actor):return source_user_key('secretary_oauth',scope,actor)

def connect(scope,actor,username,password,client_id,client_secret,expected_username):
 if username!=expected_username:raise PermissionError('OAuth account must equal the active BPMS binding')
 api=processmaker_profile(scope['source_id'])['api']
 tokens=_pm_oauth_token(api['base_url'],api['workspace'],{'grant_type':'password','client_id':client_id,'client_secret':client_secret,'username':username,'password':password,'scope':'*'})
 if not tokens.get('refresh_token'):raise ValueError('OAuth باید Refresh Token برگرداند.')
 with agent_storage.transaction() as tx:
  tx.put(grant_key(scope,actor),{'scope':scope_stamp(scope),'endpoint':endpoint_stamp(api),'client_id':client_id,'client_secret':client_secret,
   'access_token':tokens['access_token'],'refresh_token':tokens['refresh_token'],'expires_at':time.time()+tokens['expires_in']})
  tx.audit(scope['tenant_id'],actor,'SECRETARY_OAUTH_CONNECTED',{'source_id':scope['source_id']})
 return {'connected':True}

def token(scope,actor):
 api=processmaker_profile(scope['source_id'])['api']
 with agent_storage.transaction() as tx:
  row=tx.get(grant_key(scope,actor),lock=True)
  if not row or row['scope']!=scope_stamp(scope) or row['endpoint']!=endpoint_stamp(api):raise HTTPException(409,'ابتدا مجوز اجرای فرایند حساب BPMS خود را در کارتابل متصل کنید.')
  if row['expires_at']<time.time()+90:
   tokens=_pm_oauth_token(api['base_url'],api['workspace'],{'grant_type':'refresh_token','client_id':row['client_id'],'client_secret':row['client_secret'],'refresh_token':row['refresh_token']})
   row.update(access_token=tokens['access_token'],refresh_token=tokens.get('refresh_token') or row['refresh_token'],expires_at=time.time()+tokens['expires_in']);tx.put(grant_key(scope,actor),row)
  return row['access_token']

def connected(scope,actor):
 with agent_storage.transaction() as tx:row=tx.get(grant_key(scope,actor))
 api=processmaker_profile(scope['source_id'])['api']
 return bool(row and row['scope']==scope_stamp(scope) and row['endpoint']==endpoint_stamp(api))

def disconnect(scope,actor):
 with agent_storage.transaction() as tx:tx.put(grant_key(scope,actor),None)
 return {'connected':False}
