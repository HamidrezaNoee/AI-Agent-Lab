"""Task inbox and secretary tools; all writes retain current native assignment checks."""
from fastapi import Depends,HTTPException,Query,Request
from fastapi.responses import Response
from urllib.parse import unquote
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
 auto_advance:bool=True
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
  assistant=runtime.assistant_state(row['values'],t,s,row.get('questions',[]))
  if row.get('reply'):assistant['message']=row['reply']
  return {'task':{k:t[k] for k in ('case_uid','index','pack_id','stage','title','number')},
          'draft':{k:row.get(k,[] if k in ('questions','history','attachments') else None) for k in ('values','revision','status','questions','history','attachments')},
          'form':runtime.form(t),'context':context,'missing':assistant['missing'],'assistant':assistant,
          'people':[{'uid':k,'name':v['name']} for k,v in s['directory'].items() if v['active']]}

 def session_response(s,p,row,t):
  assistant=runtime.assistant_state(row['values'],t,s,row.get('questions',[]))
  if row.get('reply'):assistant['message']=row['reply']
  return {'session':{k:v for k,v in row.items() if k not in ('actor','scope')},
          'task':{'stage':'invitation','title':row['values'].get('MTG_MeetingTitle') or 'جلسه جدید'},
          'form':runtime.form(t),'missing':assistant['missing'],'assistant':assistant,
          'people':[{'uid':k,'name':v['name']} for k,v in s['directory'].items() if v['active']]}

 async def read_upload(request):
  from . import secretary_uploads
  data=bytearray()
  async for chunk in request.stream():
   data.extend(chunk)
   if len(data)>secretary_uploads.MAX_BYTES:raise HTTPException(413,'حداکثر حجم فایل ۸ مگابایت است.')
  filename=unquote(request.headers.get('x-avan-filename','document'))
  try:return secretary_uploads.extract(bytes(data),filename,request.headers.get('content-type',''))
  except ValueError as exc:raise HTTPException(422,str(exc))
 @app.get(base+'/inbox')
 def inbox(source_id:str,pack_id:str|None=Query(None,pattern=r'^[0-9a-f]{24}$'),value=Depends(authorized)):
  def run(con,s,p):
   data=runtime.inbox(con,s,pack_id=pack_id)
   enabled={x['id'] for x in catalog.runtime_meeting_packs(s['source_id']) if x.get('adapter')=='meeting_v2'}
   sessions=[{'id':r['id'],'pack_id':r['pack_id'],'status':r['status'],'title':r['values'].get('MTG_MeetingTitle','جلسه جدید'),'case_uid':r['case_uid']} for r in runtime.sessions(s,p.subject) if (not pack_id or r['pack_id']==pack_id) and r['pack_id'] in enabled]
   return {**data,'oauth_connected':credentials.connected(s,p.subject),'sessions':sessions}
  return access(value,source_id,run)
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
    vals,questions,reply,intent=runtime.converse(body.text,t,row['values'],s,questions=row.get('questions',[]))
    decision=runtime.apply_explicit_decision(body.text,t['stage'],vals) if intent=='update' else None
    workflow_intent=runtime.apply_explicit_workflow_intent(body.text,t['stage'],vals) if intent=='update' else None
    advance=runtime.explicit_advance_intent(body.text,t['stage'],workflow_intent) or bool(decision)
   def commit(con,s,p):
    fresh=runtime.task(con,s,case_uid,index,pack_id)
    updated=runtime.update(s,p.subject,fresh,body.revision,vals,questions,turn_text=body.text,reply=reply)
    assistant=runtime.assistant_state(updated['values'],fresh,s,updated.get('questions',[]))
    if intent=='update' and body.auto_advance and advance and not assistant['missing']:
     sent=runtime.submit(s,p.subject,fresh,updated['revision'])
     return {'advanced':True,'status':sent['status'],'assistant':{
      'stage':fresh['stage'],'summary':assistant['summary'],'missing':[],
      'can_submit':False,'message':'دستور صریح شما اجرا شد و پرونده به مرحله بعد فرایند منتقل شد.'
     }}
    return response(s,p,fresh,updated)
   return access(value,source_id,commit)
  try:return guard_model(model_run)
  except RevisionConflict:raise HTTPException(409,'پیش‌نویس تغییر کرده است.')
  except ValueError as exc:raise HTTPException(422,str(exc))
 @app.post(base+'/tasks/{case_uid}/{index}/attachment')
 async def task_attachment(source_id:str,case_uid:str,index:int,pack_id:str,request:Request,revision:int=Query(...,ge=1),value=Depends(csrf)):
  text,meta=await read_upload(request)
  s,t=native(value,source_id,Ref(case_uid=case_uid,index=index,pack_id=pack_id));p=value[2]
  prompt='فایل «'+meta['name']+'» به عنوان داده کاربر ارائه شده است. فقط اطلاعات صریح مرتبط را استخراج کن.\n\n'+text
  def model_run():
   with run_slot((str(p.tenant_id),p.subject)):
    row=runtime.draft(s,p.subject,t)
    if row['revision']!=revision:raise RevisionConflict()
    vals,questions=runtime.extract(prompt,t,row['values'],s,questions=row.get('questions',[]))
   return access(value,source_id,lambda con,s,p:response(
    s,p,(fresh:=runtime.task(con,s,case_uid,index,pack_id)),
    runtime.update(s,p.subject,fresh,revision,vals,questions,turn_text='فایل: '+meta['name'],turn_source='file',attachment=meta)))
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
  original_scope=s
  def run():
   with run_slot((str(p.tenant_id),p.subject)):answer=assess(s,p.subject,t)
   return access(value,source_id,lambda con,s,p:answer if runtime.scope_stamp(s)==runtime.scope_stamp(original_scope) and catalog.get(s['source_id'],pack_id)['revision']==t['pack']['revision'] and runtime.native_stamp(runtime.task(con,s,case_uid,index,pack_id))==runtime.native_stamp(t) else (_ for _ in ()).throw(RevisionConflict()))
  try:return guard_model(run)
  except ValueError as exc:raise HTTPException(422,str(exc))
 @app.post(base+'/tasks/{case_uid}/{index}/speech')
 def speech(source_id:str,case_uid:str,index:int,pack_id:str,part:int=0,value=Depends(csrf)):
  Ref(case_uid=case_uid,index=index,pack_id=pack_id)
  def run(con,s,p):
   from .agent_voice import speak
   t=runtime.task(con,s,case_uid,index,pack_id);row=runtime.draft(s,p.subject,t)
   assistant=runtime.assistant_state(row['values'],t,s,row.get('questions',[]))
   text=(assistant.get('summary','')+'\n'+assistant.get('message','')).strip()
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
   return session_response(s,p,row,t)
  return access(value,source_id,run)
 @app.post(base+'/sessions/{identifier}/edit')
 def edit_session(source_id:str,identifier:str,body:Edit,value=Depends(csrf)):
  return access(value,source_id,lambda con,s,p:runtime.session_update(s,p.subject,identifier,body.revision,body.values))
 @app.post(base+'/sessions/{identifier}/turn')
 def session_turn(source_id:str,identifier:str,body:Turn,value=Depends(csrf)):
  principal=value[2]
  def run(con,s,p):
   row,t=runtime.session_load(s,p.subject,identifier)
   if row['revision']!=body.revision:raise RevisionConflict()
   with run_slot((str(principal.tenant_id),p.subject)):
    vals,questions,reply,intent=runtime.converse(body.text,t,row['values'],s,questions=row.get('questions',[]))
   def commit(con,s,p):
    current,t=runtime.session_load(s,p.subject,identifier)
    if current['revision']!=body.revision:raise RevisionConflict()
    updated=runtime.session_update(s,p.subject,identifier,body.revision,vals,questions,turn_text=body.text,reply=reply)
    assistant=runtime.assistant_state(updated['values'],t,s,updated.get('questions',[]))
    if intent=='update' and body.auto_advance and runtime.explicit_start_intent(body.text) and not assistant['missing']:
     sent=runtime.session_send(s,p.subject,identifier,updated['revision'])
     return {'advanced':True,'status':sent['status'],'case_uid':sent.get('case_uid'),'assistant':{
      'stage':'invitation','summary':runtime.assistant_state(sent['values'],t,s,[])['summary'],
      'missing':[],'can_submit':False,
      'message':'گام اول فرایند ایجاد شد و دعوت‌نامه برای بررسی رئیس جلسه ارسال شد.'
     }}
    return session_response(s,p,updated,t)
   # Revalidate source binding and revision after the external model call.
   return access(value,source_id,commit)
  return access(value,source_id,run)
 @app.post(base+'/sessions/{identifier}/attachment')
 async def session_attachment(source_id:str,identifier:str,request:Request,revision:int=Query(...,ge=1),value=Depends(csrf)):
  text,meta=await read_upload(request);principal=value[2]
  prompt='فایل «'+meta['name']+'» به عنوان داده کاربر ارائه شده است. فقط اطلاعات صریح مرتبط با دعوت‌نامه را استخراج کن.\n\n'+text
  def run(con,s,p):
   row,t=runtime.session_load(s,p.subject,identifier)
   if row['revision']!=revision:raise RevisionConflict()
   with run_slot((str(principal.tenant_id),p.subject)):
    vals,questions=runtime.extract(prompt,t,row['values'],s,questions=row.get('questions',[]))
   return access(value,source_id,lambda con,s,p:session_response(
    s,p,(runtime.session_update(s,p.subject,identifier,revision,vals,questions,
      turn_text='فایل: '+meta['name'],turn_source='file',attachment=meta)),runtime.session_load(s,p.subject,identifier)[1]))
  return access(value,source_id,run)

 @app.post(base+'/sessions/{identifier}/speech')
 def session_speech(source_id:str,identifier:str,part:int=0,value=Depends(csrf)):
  def run(con,s,p):
   from .agent_voice import speak
   row,t=runtime.session_load(s,p.subject,identifier)
   assistant=runtime.assistant_state(row['values'],t,s,row.get('questions',[]))
   text=(assistant.get('summary','')+'\n'+assistant.get('message','')).strip()
   with run_slot((str(p.tenant_id),p.subject)):data,count=speak({'clarification':text},part)
   return Response(data,media_type='audio/mpeg',headers={'Cache-Control':'no-store','X-AVAN-Audio-Parts':str(count)})
  return access(value,source_id,run)

 @app.post(base+'/sessions/{identifier}/submit')
 def send_session(source_id:str,identifier:str,body:Submit,value=Depends(csrf)):
  if not body.confirmed:raise HTTPException(422,'دعوت‌نامه را بازبینی و ارسال را تأیید کنید.')
  return access(value,source_id,lambda con,s,p:runtime.session_send(s,p.subject,identifier,body.revision))

 @app.post(base+'/sessions/{identifier}/reconcile')
 def reconcile_session(source_id:str,identifier:str,body:Submit,value=Depends(csrf)):
  if not body.confirmed:raise HTTPException(422,'ادامه همان پرونده ProcessMaker را صریحاً تأیید کنید.')
  return access(value,source_id,lambda con,s,p:runtime.session_reconcile(s,p.subject,identifier,body.revision))

