"""Source-bound conversational secretary endpoints, using existing OIDC and CSRF."""
from fastapi import Depends,HTTPException
from pydantic import BaseModel,ConfigDict,Field
from . import secretary_workflow as flow
from .agent_routes import snapshot,guard_model,ensure_still_authorized
from .agent_workspace import RevisionConflict
from .meeting_agent import run_slot

class Turn(BaseModel):
 model_config=ConfigDict(extra='forbid')
 revision:int=Field(ge=1)
 text:str=Field(min_length=1,max_length=18000)
class Edit(BaseModel):
 model_config=ConfigDict(extra='forbid')
 revision:int=Field(ge=1)
 values:dict
class Send(BaseModel):
 model_config=ConfigDict(extra='forbid')
 revision:int=Field(ge=1)
 confirmed:bool

def register(app,authorized,csrf):
 base='/api/sources/{source_id}/secretary/workflows'
 def access(value,source_id):
  principal=value[2];scope,_,_=snapshot(principal,2,source_id=source_id)
  return principal,scope
 def run(fn):
  try:return guard_model(fn)
  except PermissionError:raise HTTPException(403,'این پرونده یا مرحله دبیر در دسترس شما نیست.')
  except RevisionConflict:raise HTTPException(409,'پرونده تغییر کرده یا ارسال شده است؛ دوباره بارگذاری کنید.')
  except ValueError as exc:raise HTTPException(422,str(exc))
 @app.get(base)
 def listing(source_id:str,value=Depends(authorized)):
  principal,scope=access(value,source_id)
  return run(lambda:{'workflows':flow.listing(scope,principal.subject),'contract':flow.live_forms(scope),'people':[{'uid':k,'name':v.get('name',k)} for k,v in scope['directory'].items() if v.get('active')]})
 @app.post(base)
 def create(source_id:str,value=Depends(csrf)):
  principal,scope=access(value,source_id)
  return run(lambda:flow.create(scope,principal.subject))
 @app.post(base+'/{identifier}/turn')
 def turn(source_id:str,identifier:str,body:Turn,value=Depends(csrf)):
  principal,scope=access(value,source_id)
  def work():
   with run_slot((str(principal.tenant_id),principal.subject)):
    row=flow.load(scope,principal.subject,identifier)
    if row['revision']!=body.revision:raise RevisionConflict()
    values,questions=flow.extract(body.text,row['stage'],row['values'],scope['directory'])
    ensure_still_authorized(principal,scope,[],2,source_id=source_id)
    return flow.update(scope,principal.subject,identifier,body.revision,values,questions)
  return run(work)
 @app.post(base+'/{identifier}/edit')
 def edit(source_id:str,identifier:str,body:Edit,value=Depends(csrf)):
  principal,scope=access(value,source_id)
  return run(lambda:flow.update(scope,principal.subject,identifier,body.revision,body.values))
 @app.post(base+'/{identifier}/submit')
 def submit(source_id:str,identifier:str,body:Send,value=Depends(csrf)):
  if not body.confirmed:raise HTTPException(422,'پیش‌نمایش جلسه را بازبینی و ارسال را تأیید کنید.')
  principal,scope=access(value,source_id)
  # Register delegated background polling before performing a remote mutation.
  from .agent_monitor import subscribe
  run(lambda:subscribe(scope,principal.subject,value[1],True,300))
  return run(lambda:flow.submit(scope,principal.subject,identifier,body.revision))
 @app.post(base+'/{identifier}/refresh')
 def refresh(source_id:str,identifier:str,value=Depends(csrf)):
  principal,scope=access(value,source_id)
  return run(lambda:flow.refresh(scope,principal.subject,identifier))
