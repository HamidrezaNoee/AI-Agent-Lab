"""Task inbox and secretary tools; all writes retain current native assignment checks."""
import logging
from fastapi import Depends,HTTPException,Query,Request
from fastapi.responses import Response
from urllib.parse import unquote
from pydantic import BaseModel,ConfigDict,Field
from . import secretary_runtime as runtime,secretary_catalog as catalog,secretary_credentials as credentials,user_experience as ux
from .agent_workspace import RevisionConflict
from .agent_routes import guard_model
from .meeting_agent import run_slot
from .processmaker_store import ProductionUnavailable

logger=logging.getLogger(__name__)

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
 request_id:str|None=Field(None,min_length=16,max_length=80)
class Undo(BaseModel):
 model_config=ConfigDict(extra="forbid")
 revision:int=Field(ge=1)

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
   except ux.OperationCancelled as exc:raise HTTPException(409,str(exc))
   except ValueError as exc:raise HTTPException(422,str(exc))
  try:return guard_model(lambda:_source_store_response(source_id,read,value[2]))
  except PermissionError as exc:raise HTTPException(403,str(exc) or 'وظیفه در دسترس این حساب نیست.')
  except RevisionConflict:raise HTTPException(409,'وظیفه، پیش‌نویس یا تنظیم فرایند تغییر کرده است.')
  except ux.OperationCancelled as exc:raise HTTPException(409,str(exc))
  except ValueError as exc:raise HTTPException(422,str(exc))
 def operation_start(p,request_id,kind,detail=None):
  if request_id:ux.start_operation(str(p.tenant_id),p.subject,request_id,kind,detail or {})
 def operation_active(p,request_id):
  if request_id:ux.ensure_active(str(p.tenant_id),p.subject,request_id)
 def operation_finish(p,request_id,state='completed',detail=None):
  if not request_id:return True
  try:
   ux.finish_operation(str(p.tenant_id),p.subject,request_id,state,detail or {})
   return True
  except Exception:
   logger.exception("Secretary operation finalization failed request_id=%s state=%s",request_id,state)
   return False
 def header_request_id(request):
  value=str(request.headers.get('X-AVAN-Request-ID') or '').strip()
  if not value:return None
  if len(value)<16 or len(value)>80 or not all(c.isalnum() or c in '-_' for c in value):
   raise HTTPException(422,'شناسه پردازش معتبر نیست.')
  return value
 def scope(value,source_id):return access(value,source_id,lambda con,s,p:s)
 def native(value,source_id,ref):return access(value,source_id,lambda con,s,p:(s,runtime.task(con,s,ref.case_uid,ref.index,ref.pack_id)))
 def response(s,p,t,row):
  context={k:v for k,v in t['native'].items() if k in t['pack']['stages'][t['stage']]['fields'] and not any(x in k for x in ('File','Evidence','Json','History'))}
  assistant=runtime.assistant_state(row['values'],t,s,row.get('questions',[]))
  if row.get('reply'):assistant['message']=row['reply']
  draft={k:row.get(k,[] if k in ('questions','history','attachments') else None) for k in ('values','revision','status','questions','history','attachments','last_error','recovery','failure_phase','upstream_status','last_change','agent_receipt')}
  draft['can_undo']=runtime.journal.can_undo(row)
  if t.get('stage')=='minutes' and draft.get('status')=='reconciliation_required':
   # Old builds trapped FR-MTG-003 failures in reconciliation_required. The
   # rewritten minutes submit path safely re-runs the authoritative PM trigger.
   draft['status']='draft';draft['recovery']='';draft['failure_phase']=''
  elif runtime._route_recovery_row(row):
   draft['recovery']='route_only'
  draft['pending_confirmation']=runtime.resolution.safe_public_pending(row.get('pending_confirmation'))
  requiredness={'live':t['pack'].get('live_requiredness_available',True),
                'warning':t['pack'].get('live_requiredness_warning','')}
  return {'task':{k:t[k] for k in ('case_uid','index','pack_id','stage','title','number')},
          'draft':draft,
          'form':runtime.form(t),'context':context,'missing':assistant['missing'],'assistant':assistant,
          'requiredness':requiredness,
          'people':[{'uid':k,'name':v['name']} for k,v in s['directory'].items() if v['active']]}

 def committed_turn_response(s,p,t,row,text,submitted_revision):
  """Replay the persisted result when a previous identical turn already committed."""
  if int(row.get('revision') or 0)!=int(submitted_revision)+1:return None
  history=list(row.get('history') or [])
  if len(history)<2:return None
  user=history[-2] if isinstance(history[-2],dict) else {}
  assistant=history[-1] if isinstance(history[-1],dict) else {}
  if user.get('role')!='user' or assistant.get('role')!='assistant':return None
  if str(user.get('text') or '').strip()!=str(text or '').strip():return None
  return response(s,p,t,row)

 def public_session(row):
  public={k:v for k,v in row.items() if k not in ('actor','scope','pending_confirmation','_undo_checkpoint')}
  public['can_undo']=runtime.journal.can_undo(row)
  public['pending_confirmation']=runtime.resolution.safe_public_pending(row.get('pending_confirmation'))
  return public

 def session_response(s,p,row,t):
  assistant=runtime.assistant_state(row['values'],t,s,row.get('questions',[]))
  if row.get('reply'):assistant['message']=row['reply']
  requiredness={'live':t['pack'].get('live_requiredness_available',True),
                'warning':t['pack'].get('live_requiredness_warning','')}
  return {'session':public_session(row),
          'task':{'stage':'invitation','title':row['values'].get('MTG_MeetingTitle') or 'جلسه جدید'},
          'form':runtime.form(t),'missing':assistant['missing'],'assistant':assistant,
          'requiredness':requiredness,
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
  # Opening a task prepares only the native form. No recovery/verification flow
  # is allowed to block the minutes editor.
  access(value,source_id,lambda con,s,p:runtime.prepare(t,s,p.subject))
  return access(value,source_id,lambda con,s,p:response(
   s,p,(fresh:=runtime.task(con,s,body.case_uid,body.index,body.pack_id)),
   runtime.draft(s,p.subject,fresh)))
 @app.post(base+'/tasks/load')
 def load_task(source_id:str,body:Ref,value=Depends(csrf)):
  return access(value,source_id,lambda con,s,p:response(s,p,(t:=runtime.task(con,s,body.case_uid,body.index,body.pack_id)),runtime.draft(s,p.subject,t)))
 @app.post(base+'/tasks/{case_uid}/{index}/edit')
 def edit_task(source_id:str,case_uid:str,index:int,pack_id:str,body:Edit,value=Depends(csrf)):
  ref=Ref(case_uid=case_uid,index=index,pack_id=pack_id)
  return access(value,source_id,lambda con,s,p:response(s,p,(t:=runtime.task(con,s,case_uid,index,pack_id)),runtime.update(s,p.subject,t,body.revision,body.values,pending_confirmation=None)))
 @app.post(base+'/tasks/{case_uid}/{index}/undo')
 def undo_task(source_id:str,case_uid:str,index:int,pack_id:str,body:Undo,value=Depends(csrf)):
  Ref(case_uid=case_uid,index=index,pack_id=pack_id)
  return access(value,source_id,lambda con,s,p:response(s,p,(t:=runtime.task(con,s,case_uid,index,pack_id)),runtime.undo_task(s,p.subject,t,body.revision)))
 @app.post(base+'/tasks/{case_uid}/{index}/turn')
 def task_turn(source_id:str,case_uid:str,index:int,pack_id:str,body:Turn,value=Depends(csrf)):
  s,t=native(value,source_id,Ref(case_uid=case_uid,index=index,pack_id=pack_id));p=value[2]
  try:
   operation_start(p,body.request_id,'secretary_task_turn',{'case_uid':case_uid,'stage':t.get('stage'),'source_id':source_id,'pack_id':pack_id,'process_uid':runtime.process_for(t['pack'],t['stage'])})
   def model_run():
    # Workflow commands are deterministic. Never ask the language model whether
    # an explicit "send" command should advance a completed minutes task.
    if t.get('stage')=='minutes' and body.auto_advance and runtime.explicit_advance_intent(body.text,'minutes'):
     row=runtime.draft(s,p.subject,t)
     if row['revision']!=body.revision:raise RevisionConflict()
     pending=runtime.gaps(row['values'],t)
     if pending:
      first=str(pending[0].get('question') or 'موارد ناقص صورت‌جلسه را تکمیل کنید.')
      reply='هنوز '+str(len(pending))+' مورد برای تکمیل صورت‌جلسه باقی مانده است.\n\n'+first
      updated=runtime.update(
       s,p.subject,t,body.revision,row['values'],
       [str(x.get('question') or x) for x in pending],
       turn_text=body.text,reply=reply,pending_confirmation=None)
      return {'result':response(s,p,t,updated),'intent':'resolved','committed':True}
     bearer=credentials.token(s,p.subject)
     sent=runtime.advance_minutes_direct(
      str(p.tenant_id),p.subject,source_id,s['external_user_id'],
      case_uid,index,pack_id,bearer,revision=row['revision'],directory=s.get('directory',{}))
     return {'result':{'advanced':True,'status':sent['status'],'assistant':{
      'stage':'minutes','summary':'','missing':[],'can_submit':False,
      'message':'صورت‌جلسه به مرحله «تأیید صورت‌جلسه» ارسال شد.'
     }},'intent':'update','committed':True}
    with run_slot((str(p.tenant_id),p.subject)):
     row=runtime.draft(s,p.subject,t)
     replay=committed_turn_response(s,p,t,row,body.text,body.revision)
     if replay is not None:
      return {'result':replay,'intent':'replay','committed':True}
     if row['revision']!=body.revision:raise RevisionConflict()
     operation_active(p,body.request_id)
     turn_result=runtime.converse(
      body.text,t,row['values'],s,
      questions=row.get('questions',[]),
      pending_confirmation=row.get('pending_confirmation'),
      history=row.get('history',[]))
     operation_active(p,body.request_id)
     vals,questions,reply,intent,pending_confirmation=turn_result
     decision=runtime.apply_explicit_decision(body.text,t['stage'],vals) if intent=='update' else None
     workflow_intent=runtime.apply_explicit_workflow_intent(body.text,t['stage'],vals) if intent=='update' else None
     advance=runtime.explicit_advance_intent(body.text,t['stage'],workflow_intent) or bool(decision)
    def commit(con,fresh_scope,p2):
     operation_active(p,body.request_id)
     fresh=runtime.task(con,fresh_scope,case_uid,index,pack_id)
     updated=runtime.update(fresh_scope,p2.subject,fresh,body.revision,vals,questions,
      turn_text=body.text,reply=reply,pending_confirmation=pending_confirmation,agent_receipt=getattr(turn_result,'receipt',{}))
     assistant=runtime.assistant_state(updated['values'],fresh,fresh_scope,updated.get('questions',[]))
     operation_active(p,body.request_id)
     can_advance_now=not assistant['missing']
     if intent=='update' and body.auto_advance and advance and can_advance_now:
      if fresh['stage']=='minutes':
       bearer=credentials.token(fresh_scope,p2.subject)
       sent=runtime.advance_minutes_direct(
        str(p2.tenant_id),p2.subject,source_id,fresh_scope['external_user_id'],
        case_uid,index,pack_id,bearer,revision=updated['revision'],directory=fresh_scope.get('directory',{}))
      else:
       sent=runtime.submit(fresh_scope,p2.subject,fresh,updated['revision'])
      return {'advanced':True,'status':sent['status'],'assistant':{
       'stage':fresh['stage'],'summary':assistant['summary'],'missing':[],
       'can_submit':False,'message':'دستور صریح شما اجرا شد و پرونده به مرحله بعد فرایند منتقل شد.'
      }}
     return response(fresh_scope,p2,fresh,updated)
    return {'result':access(value,source_id,commit),'intent':intent,'committed':True}
   outcome=guard_model(model_run)
   result=outcome['result'];intent=outcome['intent']
   if intent=='resolved':
    event=('SECRETARY_AGENTIC_COMMAND_EXECUTED'
           if runtime.commands.command_kind(body.text,t.get('stage'))
           else 'SECRETARY_CONFIRMATION_RESOLVED')
    try:
     ux.audit(str(p.tenant_id),p.subject,event,{
      'case_uid':case_uid,'stage':t.get('stage'),'source_id':source_id,'pack_id':pack_id,
      'process_uid':runtime.process_for(t['pack'],t['stage']),'result':'deterministic'
     })
    except Exception:
     logger.exception("Secretary post-commit audit failed request_id=%s event=%s",body.request_id,event)
   operation_finish(p,body.request_id,'completed',{'case_uid':case_uid,'stage':t.get('stage'),'result':'idempotent_replay' if intent=='replay' else 'updated'})
   return result
  except ux.OperationCancelled as exc:
   operation_finish(p,body.request_id,'cancelled',{'case_uid':case_uid,'stage':t.get('stage')})
   raise HTTPException(409,str(exc))
  except HTTPException as exc:
   operation_finish(p,body.request_id,'failed',{'case_uid':case_uid,'stage':t.get('stage'),'status':exc.status_code,'error':str(exc.detail)})
   raise
  except RevisionConflict:
   operation_finish(p,body.request_id,'failed',{'case_uid':case_uid,'stage':t.get('stage'),'error':'revision_conflict'})
   raise HTTPException(409,'پیش‌نویس تغییر کرده است.')
  except ValueError as exc:
   operation_finish(p,body.request_id,'failed',{'case_uid':case_uid,'stage':t.get('stage'),'error':str(exc)})
   raise HTTPException(422,str(exc))
  except Exception as exc:
   operation_finish(p,body.request_id,'failed',{'case_uid':case_uid,'stage':t.get('stage'),'error_type':type(exc).__name__})
   raise
 @app.post(base+'/tasks/{case_uid}/{index}/attachment')
 async def task_attachment(source_id:str,case_uid:str,index:int,pack_id:str,request:Request,revision:int=Query(...,ge=1),value=Depends(csrf)):
  request_id=header_request_id(request);p=value[2]
  try:
   operation_start(p,request_id,'secretary_task_attachment',{'case_uid':case_uid,'source_id':source_id})
   text,meta=await read_upload(request)
   s,t=native(value,source_id,Ref(case_uid=case_uid,index=index,pack_id=pack_id))
   prompt='فایل «'+meta['name']+'» به عنوان داده کاربر ارائه شده است. فقط اطلاعات صریح مرتبط را استخراج کن.\n\n'+text
   def model_run():
    with run_slot((str(p.tenant_id),p.subject)):
     row=runtime.draft(s,p.subject,t)
     if row['revision']!=revision:raise RevisionConflict()
     operation_active(p,request_id)
     vals,questions=runtime.extract(prompt,t,row['values'],s,questions=row.get('questions',[]))
     operation_active(p,request_id)
    def commit(con,fresh_scope,p2):
     operation_active(p,request_id)
     fresh=runtime.task(con,fresh_scope,case_uid,index,pack_id)
     updated=runtime.update(fresh_scope,p2.subject,fresh,revision,vals,questions,
      turn_text='فایل: '+meta['name'],turn_source='file',attachment=meta,pending_confirmation=None)
     return response(fresh_scope,p2,fresh,updated)
    return access(value,source_id,commit)
   result=guard_model(model_run)
   operation_finish(p,request_id,'completed',{'case_uid':case_uid,'filename':meta.get('name'),'result':'attachment_processed'})
   return result
  except ux.OperationCancelled as exc:
   operation_finish(p,request_id,'cancelled',{'case_uid':case_uid})
   raise HTTPException(409,str(exc))
  except HTTPException as exc:
   operation_finish(p,request_id,'failed',{'case_uid':case_uid,'status':exc.status_code,'error':str(exc.detail)})
   raise
  except RevisionConflict:
   operation_finish(p,request_id,'failed',{'case_uid':case_uid,'error':'revision_conflict'})
   raise HTTPException(409,'پیش‌نویس تغییر کرده است.')
  except ValueError as exc:
   operation_finish(p,request_id,'failed',{'case_uid':case_uid,'error':str(exc)})
   raise HTTPException(422,str(exc))
  except Exception as exc:
   operation_finish(p,request_id,'failed',{'case_uid':case_uid,'error_type':type(exc).__name__})
   raise

 @app.post(base+'/tasks/{case_uid}/{index}/advance-minutes')
 def advance_minutes(source_id:str,case_uid:str,index:int,pack_id:str,body:Submit,value=Depends(csrf)):
  if not body.confirmed:raise HTTPException(422,'ارسال صورت‌جلسه را پس از بازبینی تأیید کنید.')
  Ref(case_uid=case_uid,index=index,pack_id=pack_id)
  principal=value[2]
  from .user_bpms_bindings import binding_for,directory_users
  binding=binding_for(principal.subject,source_id)
  if not binding:
   raise HTTPException(403,'این ProcessMaker به حساب AVAN شما Binding فعال ندارد.')
  external_user_id=str(binding.get('external_user_id') or '')
  if not external_user_id:
   raise HTTPException(403,'کاربر ProcessMaker متناظر این حساب مشخص نیست.')
  bearer=credentials.token_for_bound_source(str(principal.tenant_id),principal.subject,source_id)
  # Final direct routing must resolve action owners against a fresh
  # ProcessMaker USERS/DEPARTMENT snapshot, not a potentially stale cache.
  rows=directory_users(source_id,refresh=True)
  directory={
   str(u.get('external_user_id') or ''):{
    'active':bool(u.get('active')),
    'username':u.get('username') or '',
    'name':u.get('display_name') or u.get('username') or '',
    'position':u.get('position') or '',
    'unit':u.get('unit') or '',
   }
   for u in rows if u.get('external_user_id')
  }
  try:
   return runtime.advance_minutes_direct(
    str(principal.tenant_id),principal.subject,source_id,external_user_id,
    case_uid,index,pack_id,bearer,revision=body.revision,directory=directory)
  except PermissionError as exc:
   raise HTTPException(403,str(exc) or 'ارسال این صورت‌جلسه برای حساب فعلی مجاز نیست.')
  except RevisionConflict:
   raise HTTPException(409,'وظیفه ProcessMaker تغییر کرده است؛ کارتابل را تازه‌سازی کنید.')
  except ValueError as exc:
   raise HTTPException(422,str(exc))
  except ProductionUnavailable as exc:
   if str(exc) in ('ProcessMaker DynaForm metadata unavailable','Read-only ProcessMaker MySQL unavailable'):
    raise HTTPException(503,'تنظیم Required زنده ProcessMaker قابل خواندن نیست؛ دسترسی SELECT روی DYNAFORM را برای avan_reader بررسی کنید.')
   raise HTTPException(503,'اتصال خواندنی ProcessMaker در دسترس نیست.')

 @app.post(base+'/tasks/{case_uid}/{index}/submit')
 def send_task(source_id:str,case_uid:str,index:int,pack_id:str,body:Submit,value=Depends(csrf)):
  if not body.confirmed:raise HTTPException(422,'ارسال را بعد از بازبینی تأیید کنید.')
  Ref(case_uid=case_uid,index=index,pack_id=pack_id)
  return access(value,source_id,lambda con,s,p:runtime.submit(s,p.subject,runtime.task(con,s,case_uid,index,pack_id),body.revision))
 @app.post(base+'/tasks/{case_uid}/{index}/reconcile-route')
 def reconcile_task_route(source_id:str,case_uid:str,index:int,pack_id:str,body:Submit,value=Depends(csrf)):
  if not body.confirmed:raise HTTPException(422,'ادامه Route همین پرونده را صریحاً تأیید کنید.')
  Ref(case_uid=case_uid,index=index,pack_id=pack_id)
  return access(value,source_id,lambda con,s,p:runtime.reconcile_task_route(s,p.subject,runtime.task(con,s,case_uid,index,pack_id),body.revision))
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
  return access(value,source_id,lambda con,s,p:public_session(runtime.session_update(s,p.subject,identifier,body.revision,body.values,pending_confirmation=None)))
 @app.post(base+'/sessions/{identifier}/undo')
 def undo_session(source_id:str,identifier:str,body:Undo,value=Depends(csrf)):
  return access(value,source_id,lambda con,s,p:session_response(s,p,runtime.undo_session(s,p.subject,identifier,body.revision),runtime.session_load(s,p.subject,identifier)[1]))
 @app.post(base+'/sessions/{identifier}/turn')
 def session_turn(source_id:str,identifier:str,body:Turn,value=Depends(csrf)):
  principal=value[2]
  try:
   def snapshot(con,s,p):
    row,t=runtime.session_load(s,p.subject,identifier)
    if row['revision']!=body.revision:raise RevisionConflict()
    return s,row,t
   s,row,t=access(value,source_id,snapshot)
   operation_start(principal,body.request_id,'secretary_session_turn',{'session_id':identifier,'source_id':source_id,'pack_id':row['pack_id'],'process_uid':runtime.process_for(t['pack'],t['stage'])})
   def model_only():
    with run_slot((str(principal.tenant_id),principal.subject)):
     operation_active(principal,body.request_id)
     result=runtime.converse(
      body.text,t,row['values'],s,
      questions=row.get('questions',[]),
      pending_confirmation=row.get('pending_confirmation'),
      history=row.get('history',[]))
     operation_active(principal,body.request_id)
     return result
   turn_result=guard_model(model_only)
   vals,questions,reply,intent,pending_confirmation=turn_result
   def commit(con,fresh_scope,p):
    operation_active(principal,body.request_id)
    current,fresh_task=runtime.session_load(fresh_scope,p.subject,identifier)
    if current['revision']!=body.revision:raise RevisionConflict()
    updated=runtime.session_update(fresh_scope,p.subject,identifier,body.revision,vals,questions,
     turn_text=body.text,reply=reply,pending_confirmation=pending_confirmation,agent_receipt=getattr(turn_result,'receipt',{}))
    assistant=runtime.assistant_state(updated['values'],fresh_task,fresh_scope,updated.get('questions',[]))
    operation_active(principal,body.request_id)
    if intent=='update' and body.auto_advance and runtime.explicit_start_intent(body.text) and not assistant['missing']:
     sent=runtime.session_send(fresh_scope,p.subject,identifier,updated['revision'])
     return {'advanced':True,'status':sent['status'],'case_uid':sent.get('case_uid'),'assistant':{
      'stage':'invitation','summary':runtime.assistant_state(sent['values'],fresh_task,fresh_scope,[])['summary'],
      'missing':[],'can_submit':False,
      'message':'گام اول فرایند ایجاد شد و دعوت‌نامه برای بررسی رئیس جلسه ارسال شد.'
     }}
    return session_response(fresh_scope,p,updated,fresh_task)
   result=access(value,source_id,commit)
   if intent=='resolved':
    event=('SECRETARY_AGENTIC_COMMAND_EXECUTED'
           if runtime.commands.command_kind(body.text,t.get('stage'))
           else 'SECRETARY_CONFIRMATION_RESOLVED')
    ux.audit(str(principal.tenant_id),principal.subject,event,{
     'session_id':identifier,'source_id':source_id,'pack_id':row['pack_id'],
     'process_uid':runtime.process_for(t['pack'],t['stage']),'stage':t.get('stage'),'result':'deterministic'
    })
   operation_finish(principal,body.request_id,'completed',{'session_id':identifier,'result':'updated'})
   return result
  except ux.OperationCancelled as exc:
   operation_finish(principal,body.request_id,'cancelled',{'session_id':identifier})
   raise HTTPException(409,str(exc))
  except HTTPException as exc:
   operation_finish(principal,body.request_id,'failed',{'session_id':identifier,'status':exc.status_code,'error':str(exc.detail)})
   raise
  except RevisionConflict:
   operation_finish(principal,body.request_id,'failed',{'session_id':identifier,'error':'revision_conflict'})
   raise HTTPException(409,'پیش‌نویس تغییر کرده است.')
  except ValueError as exc:
   operation_finish(principal,body.request_id,'failed',{'session_id':identifier,'error':str(exc)})
   raise HTTPException(422,str(exc))
  except Exception as exc:
   operation_finish(principal,body.request_id,'failed',{'session_id':identifier,'error_type':type(exc).__name__})
   raise

 @app.post(base+'/sessions/{identifier}/attachment')
 async def session_attachment(source_id:str,identifier:str,request:Request,revision:int=Query(...,ge=1),value=Depends(csrf)):
  request_id=header_request_id(request);principal=value[2]
  try:
   operation_start(principal,request_id,'secretary_session_attachment',{'session_id':identifier,'source_id':source_id})
   text,meta=await read_upload(request)
   prompt='فایل «'+meta['name']+'» به عنوان داده کاربر ارائه شده است. فقط اطلاعات صریح مرتبط با دعوت‌نامه را استخراج کن.\n\n'+text
   def snapshot(con,s,p):
    row,t=runtime.session_load(s,p.subject,identifier)
    if row['revision']!=revision:raise RevisionConflict()
    return s,row,t
   s,row,t=access(value,source_id,snapshot)
   def model_only():
    with run_slot((str(principal.tenant_id),principal.subject)):
     operation_active(principal,request_id)
     result=runtime.extract(prompt,t,row['values'],s,questions=row.get('questions',[]))
     operation_active(principal,request_id)
     return result
   vals,questions=guard_model(model_only)
   def commit(con,fresh_scope,p):
    operation_active(principal,request_id)
    current,fresh_task=runtime.session_load(fresh_scope,p.subject,identifier)
    if current['revision']!=revision:raise RevisionConflict()
    updated=runtime.session_update(fresh_scope,p.subject,identifier,revision,vals,questions,
     turn_text='فایل: '+meta['name'],turn_source='file',attachment=meta,pending_confirmation=None)
    return session_response(fresh_scope,p,updated,fresh_task)
   result=access(value,source_id,commit)
   operation_finish(principal,request_id,'completed',{'session_id':identifier,'filename':meta.get('name'),'result':'attachment_processed'})
   return result
  except ux.OperationCancelled as exc:
   operation_finish(principal,request_id,'cancelled',{'session_id':identifier})
   raise HTTPException(409,str(exc))
  except HTTPException as exc:
   operation_finish(principal,request_id,'failed',{'session_id':identifier,'status':exc.status_code,'error':str(exc.detail)})
   raise
  except RevisionConflict:
   operation_finish(principal,request_id,'failed',{'session_id':identifier,'error':'revision_conflict'})
   raise HTTPException(409,'پیش‌نویس تغییر کرده است.')
  except ValueError as exc:
   operation_finish(principal,request_id,'failed',{'session_id':identifier,'error':str(exc)})
   raise HTTPException(422,str(exc))
  except Exception as exc:
   operation_finish(principal,request_id,'failed',{'session_id':identifier,'error_type':type(exc).__name__})
   raise

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
  return access(value,source_id,lambda con,s,p:public_session(runtime.session_send(s,p.subject,identifier,body.revision)))

 @app.post(base+'/sessions/{identifier}/reconcile')
 def reconcile_session(source_id:str,identifier:str,body:Submit,value=Depends(csrf)):
  if not body.confirmed:raise HTTPException(422,'ادامه همان پرونده ProcessMaker را صریحاً تأیید کنید.')
  return access(value,source_id,lambda con,s,p:public_session(runtime.session_reconcile(s,p.subject,identifier,body.revision)))
