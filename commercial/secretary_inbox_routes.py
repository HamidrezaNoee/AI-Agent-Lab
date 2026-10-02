"""Task inbox and secretary tools; all writes retain current native assignment checks."""
from fastapi import Depends,HTTPException
from fastapi.responses import Response
from pydantic import BaseModel,ConfigDict,Field
from . import secretary_runtime as runtime,secretary_catalog as catalog,secretary_credentials as credentials
from .agent_workspace import RevisionConflict
from .agent_routes import guard_model
from .meeting_agent import run_slot

class Pack(BaseModel):
 model_config=ConfigDict(extra='forbid')
 pack_id:str=Field(pattern=r'^[0-9a-f]{24}$')
class Ref(Pack):
 case_uid:str=Field(pattern=r'^[a-zA-Z0-9]{32}$')
 index:int=Field(ge=1)
class Edit(BaseModel):
 model_config=ConfigDict(extra='forbid')
 revision:int=Field(ge=1)
 values:dict
class Turn(BaseModel):
 model_config=ConfigDict(extra='forbid')
 revision:int=Field(ge=1)
 text:str=Field(min_length=1,max_length=18000)
class Submit(BaseModel):
 model_config=ConfigDict(extra='forbid')
 revision:int=Field(ge=1)
 confirmed:bool
class Evidence(BaseModel):
 model_config=ConfigDict(extra='forbid')
 revision:int=Field(ge=1)
 doc_id:str=Field(pattern=r'^[a-zA-Z0-9]{32}$')
 version:int=Field(ge=1,le=100000)

class OAuth(BaseModel):
 model_config=ConfigDict(extra='forbid')
 username:str=Field(min_length=1,max_length=160)
 password:str=Field(min_length=1,max_length=512)
 client_id:str=Field(min_length=1,max_length=256)
 client_secret:str=Field(min_length=1,max_length=4096)

def register(app,authorized,csrf):
 base='/api/sources/{source_id}/secretary'
 def access(value,source_id,fn):
  from .production_app import _source_store_response
  def read(con,scope):
   if 2 not in scope['license']['modules']:raise HTTPException(403,'ماژول دبیر برای این حساب فعال نیست.')
   try:return fn(con,scope,value[2])
   except PermissionError as exc:raise HTTPException(403,str(exc) or 'وظیفه در دسترس نیست.')
   except RevisionConflict:raise HTTPException(409,'وظیفه یا پیش‌نویس تغییر کرده است.')
   except ValueError as exc:raise HTTPException(422,str(exc))
  try:return guard_model(lambda:_source_store_response(source_id,read,value[2]))
  except PermissionError as exc:raise HTTPException(403,str(exc) or 'وظیفه در دسترس این حساب نیست.')
  except RevisionConflict:raise HTTPException(409,'وظیفه، پیش‌نویس یا تنظیم فرایند تغییر کرده است.')
  except ValueError as exc:raise HTTPException(422,str(exc))
 def scope(value,source_id):return access(value,source_id,lambda con,s,p:s)
 def native(value,source_id,ref):return access(value,source_id,lambda con,s,p:(s,runtime.task(con,s,ref.case_uid,ref.index,ref.pack_id)))
 def response(s,p,t,row):
  context={k:v for k,v in t['native'].items() if k in t['pack']['stages'][t['stage']]['fields'] and not any(x in k for x in ('File','Evidence','Json','History'))}
  return {'task':{k:t[k] for k in ('case_uid','index','pack_id','stage','title','number')},'draft':{k:row[k] for k in ('values','revision','status','questions')},'form':runtime.form(t),'context':context,'missing':runtime.gaps(row['values'],t),'people':[{'uid':k,'name':v['name']} for k,v in s['directory'].items() if v['active']]}
 @app.get(base+'/inbox')
 def inbox(source_id:str,value=Depends(authorized)):
  return access(value,source_id,lambda con,s,p:{**runtime.inbox(con,s),'oauth_connected':credentials.connected(s,p.subject),'sessions':[{'id':r['id'],'pack_id':r['pack_id'],'status':r['status'],'title':r['values'].get('MTG_MeetingTitle','جلسه جدید'),'case_uid':r['case_uid']} for r in runtime.sessions(s,p.subject)]})
 @app.post(base+'/notifications/{identifier}/read')
 def read_notice(source_id:str,identifier:str,value=Depends(csrf)):
  return access(value,source_id,lambda con,s,p:runtime.acknowledge(s,identifier))
 @app.post(base+'/oauth/connect')
 def oauth(source_id:str,body:OAuth,value=Depends(csrf)):
  def run(con,s,p):
   from .processmaker_store import query
   rows=query(con,'SELECT USR_USERNAME FROM USERS WHERE USR_UID=%s AND USR_STATUS=%s',(s['external_user_id'],'ACTIVE'))
   if len(rows)!=1:raise PermissionError('کاربر فعال BPMS پیدا نشد.')
   return credentials.connect(s,p.subject,body.username,body.password,body.client_id,body.client_secret,str(rows[0][0]))
  return access(value,source_id,run)
 @app.post(base+'/oauth/disconnect')
 def disconnect(source_id:str,value=Depends(csrf)):
  return access(value,source_id,lambda con,s,p:credentials.disconnect(s,p.subject))
 @app.post(base+'/subscribe')
 def subscribe(source_id:str,value=Depends(csrf)):
  from .agent_monitor import subscribe as monitor_subscribe
  return access(value,source_id,lambda con,s,p:monitor_subscribe(s,p.subject,value[1],True,60))
 @app.post(base+'/tasks/open')
 def open_task(source_id:str,body:Ref,value=Depends(csrf)):
  s,t=native(value,source_id,body)
  # BEFORE triggers are an explicit preparation tool, not a side effect of GET.
  access(value,source_id,lambda con,s,p:runtime.prepare(t,s,p.subject))
  return access(value,source_id,lambda con,s,p:response(s,p,(fresh:=runtime.task(con,s,body.case_uid,body.index,body.pack_id)),runtime.draft(s,p.subject,fresh)))
 @app.post(base+'/tasks/load')
 def load_task(source_id:str,body:Ref,value=Depends(csrf)):
  return access(value,source_id,lambda con,s,p:response(s,p,(t:=runtime.task(con,s,body.case_uid,body.index,body.pack_id)),runtime.draft(s,p.subject,t)))
 @app.post(base+'/tasks/{case_uid}/{index}/edit')
 def edit_task(source_id:str,case_uid:str,index:int,pack_id:str,body:Edit,value=Depends(csrf)):
  ref=Ref(case_uid=case_uid,index=index,pack_id=pack_id)
  return access(value,source_id,lambda con,s,p:response(s,p,(t:=runtime.task(con,s,case_uid,index,pack_id)),runtime.update(s,p.subject,t,body.revision,body.values)))
 @app.post(base+'/tasks/{case_uid}/{index}/turn')
 def task_turn(source_id:str,case_uid:str,index:int,pack_id:str,body:Turn,value=Depends(csrf)):
  s,t=native(value,source_id,Ref(case_uid=case_uid,index=index,pack_id=pack_id));p=value[2]
  def model_run():
   with run_slot((str(p.tenant_id),p.subject)):
    row=runtime.draft(s,p.subject,t)
    if row['revision']!=body.revision:raise RevisionConflict()
    vals,questions=runtime.extract(body.text,t,row['values'],s,questions=row.get('questions',[]))
    return access(value,source_id,lambda con,s,p:response(s,p,(fresh:=runtime.task(con,s,case_uid,index,pack_id)),runtime.update(s,p.subject,fresh,body.revision,vals,questions)))
  try:return guard_model(model_run)
  except RevisionConflict:raise HTTPException(409,'پیش‌نویس تغییر کرده است.')
  except ValueError as exc:raise HTTPException(422,str(exc))
 @app.post(base+'/tasks/{case_uid}/{index}/submit')
 def send_task(source_id:str,case_uid:str,index:int,pack_id:str,body:Submit,value=Depends(csrf)):
  if not body.confirmed:raise HTTPException(422,'ارسال را بعد از بازبینی تأیید کنید.')
  Ref(case_uid=case_uid,index=index,pack_id=pack_id)
  return access(value,source_id,lambda con,s,p:runtime.submit(s,p.subject,runtime.task(con,s,case_uid,index,pack_id),body.revision))
 @app.post(base+'/tasks/{case_uid}/{index}/documents')
 def documents(source_id:str,case_uid:str,index:int,pack_id:str,value=Depends(csrf)):
  from .secretary_evidence import native_documents
  Ref(case_uid=case_uid,index=index,pack_id=pack_id)
  return access(value,source_id,lambda con,s,p:{'documents':native_documents(runtime.task(con,s,case_uid,index,pack_id),s,p.subject)})
 @app.post(base+'/tasks/{case_uid}/{index}/evidence')
 def evidence(source_id:str,case_uid:str,index:int,pack_id:str,body:Evidence,value=Depends(csrf)):
  from .secretary_evidence import read_native,retain
  s,t=native(value,source_id,Ref(case_uid=case_uid,index=index,pack_id=pack_id))
  doc=access(value,source_id,lambda con,s,p:read_native(t,s,p.subject,body.doc_id,body.version))
  return access(value,source_id,lambda con,s,p:retain(s,p.subject,runtime.task(con,s,case_uid,index,pack_id),body.revision,doc))
 @app.post(base+'/tasks/{case_uid}/{index}/advice')
 def advice(source_id:str,case_uid:str,index:int,pack_id:str,value=Depends(csrf)):
  from .secretary_evidence import assess
  s,t=native(value,source_id,Ref(case_uid=case_uid,index=index,pack_id=pack_id));p=value[2]
  def run():
   with run_slot((str(p.tenant_id),p.subject)):answer=assess(s,p.subject,t)
   return access(value,source_id,lambda con,s,p:answer if runtime.native_stamp(runtime.task(con,s,case_uid,index,pack_id))==runtime.native_stamp(t) else (_ for _ in ()).throw(RevisionConflict()))
  try:return guard_model(run)
  except ValueError as exc:raise HTTPException(422,str(exc))
 @app.post(base+'/tasks/{case_uid}/{index}/speech')
 def speech(source_id:str,case_uid:str,index:int,pack_id:str,part:int=0,value=Depends(csrf)):
  Ref(case_uid=case_uid,index=index,pack_id=pack_id)
  def run(con,s,p):
   from .agent_voice import speak
   import json
   t=runtime.task(con,s,case_uid,index,pack_id);row=runtime.draft(s,p.subject,t)
   allowed=t['pack']['stages'][t['stage']]['fields']
   text='\n'.join(str(allowed.get(k,{}).get('label') or k)+': '+(json.dumps(v,ensure_ascii=False) if isinstance(v,dict) else str(v)) for k,v in {**t['native'],**row['values']}.items() if k in allowed and not any(x in k for x in ('File','Evidence','History','Json')))
   with run_slot((str(p.tenant_id),p.subject)):data,count=speak({'clarification':text},part)
   return Response(data,media_type='audio/mpeg',headers={'Cache-Control':'no-store','X-AVAN-Audio-Parts':str(count)})
  return access(value,source_id,run)
 @app.post(base+'/tasks/{case_uid}/{index}/followup')
 def followup(source_id:str,case_uid:str,index:int,pack_id:str,value=Depends(csrf)):
  Ref(case_uid=case_uid,index=index,pack_id=pack_id)
  return access(value,source_id,lambda con,s,p:runtime.followup(s,p.subject,runtime.task(con,s,case_uid,index,pack_id)))
 @app.post(base+'/sessions')
 def new(source_id:str,body:Pack,value=Depends(csrf)):
  return access(value,source_id,lambda con,s,p:runtime.session_create(s,p.subject,body.pack_id))
 @app.get(base+'/sessions/{identifier}')
 def load_session(source_id:str,identifier:str,value=Depends(authorized)):
  def run(con,s,p):
   row,t=runtime.session_load(s,p.subject,identifier)
   return {'session':{k:v for k,v in row.items() if k not in ('actor','scope')},'form':runtime.form(t),'missing':runtime.gaps(row['values'],t),'people':[{'uid':k,'name':v['name']} for k,v in s['directory'].items() if v['active']]}
  return access(value,source_id,run)
 @app.post(base+'/sessions/{identifier}/edit')
 def edit_session(source_id:str,identifier:str,body:Edit,value=Depends(csrf)):
  return access(value,source_id,lambda con,s,p:runtime.session_update(s,p.subject,identifier,body.revision,body.values))
 @app.post(base+'/sessions/{identifier}/turn')
 def session_turn(source_id:str,identifier:str,body:Turn,value=Depends(csrf)):
  def run(con,s,p):
   row,t=runtime.session_load(s,p.subject,identifier)
   if row['revision']!=body.revision:raise RevisionConflict()
   with run_slot((str(p.tenant_id),p.subject)):vals,questions=runtime.extract(body.text,t,row['values'],s,questions=row.get('questions',[]))
   # Separate source scope revalidation after the external model call.
   return access(value,source_id,lambda con,s,p:runtime.session_update(s,p.subject,identifier,body.revision,vals,questions))
  return access(value,source_id,run)
 @app.post(base+'/sessions/{identifier}/submit')
 def send_session(source_id:str,identifier:str,body:Submit,value=Depends(csrf)):
  if not body.confirmed:raise HTTPException(422,'دعوت‌نامه را بازبینی و ارسال را تأیید کنید.')
  return access(value,source_id,lambda con,s,p:runtime.session_send(s,p.subject,identifier,body.revision))
