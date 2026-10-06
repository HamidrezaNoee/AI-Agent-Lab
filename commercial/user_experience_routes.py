"""User-scoped preferences, support logs and cooperative cancellation routes."""
from __future__ import annotations
from fastapi import Depends,HTTPException,Query
from pydantic import BaseModel,ConfigDict,Field
from . import native_access,user_experience as ux
from .setup_console import is_godadmin


class Preferences(BaseModel):
 model_config=ConfigDict(extra="forbid")
 secretary_auto_play_voice:bool=False
 voice_auto_transcribe:bool=True
 voice_auto_send:bool=False


class ClientEvent(BaseModel):
 model_config=ConfigDict(extra="forbid")
 event:str=Field(min_length=1,max_length=80,pattern=r"^[A-Z0-9_\-]+$")
 detail:dict=Field(default_factory=dict)


class SelfPasswordChange(BaseModel):
 model_config=ConfigDict(extra="forbid")
 password:str=Field(min_length=16,max_length=128)
 confirmation:str=Field(min_length=16,max_length=128)


def _identity(value):
 principal=value[2]
 role="GodAdmin" if is_godadmin(principal) else None
 if role is None:
  try:
   data=native_access.read()
   stored=next((u for u in data.get("users",[]) if u.get("subject")==principal.subject and u.get("enabled")),None)
   role=(stored or {}).get("role") or "Expert"
  except Exception:
   role="Expert"
 return principal,role


def register(app,authorized,csrf):
 @app.get("/api/user/preferences")
 def get_preferences(value=Depends(authorized)):
  principal,_=_identity(value)
  return ux.preferences(str(principal.tenant_id),principal.subject)

 @app.post("/api/user/preferences")
 def set_preferences(body:Preferences,value=Depends(csrf)):
  principal,_=_identity(value)
  return ux.save_preferences(str(principal.tenant_id),principal.subject,body.model_dump())

 @app.get("/api/support/logs")
 def support_logs(limit:int=Query(200,ge=1,le=500),
                  event:str|None=Query(None,max_length=80),
                  actor_id:str|None=Query(None,max_length=128),
                  source_id:str|None=Query(None,max_length=128),
                  process_uid:str|None=Query(None,max_length=128),
                  case_uid:str|None=Query(None,max_length=128),
                  stage:str|None=Query(None,max_length=80),
                  request_id:str|None=Query(None,max_length=128),
                  q:str|None=Query(None,max_length=200),
                  value=Depends(authorized)):
  principal,role=_identity(value)
  result=ux.logs(str(principal.tenant_id),principal.subject,role,limit=limit,event=event,
                 actor_id=actor_id,source_id=source_id,process_uid=process_uid,
                 case_uid=case_uid,stage=stage,request_id=request_id,q=q)
  # Resolve opaque identity subjects to AVAN display names for admin support views.
  names={}
  try:
   data=native_access.read()
   for user in data.get("users",[]):
    subject=str(user.get("subject") or "")
    if subject:
     names[subject]=user.get("name") or user.get("username") or subject
  except Exception:
   names={}
  for item in result.get("logs",[]):
   item["actor_name"]=names.get(item["actor_id"],"شما" if item["actor_id"]==principal.subject else item["actor_id"])
  filters=result.get("filters") or {}
  filters["actors"]=[
   {"id":subject,"name":names.get(subject,"شما" if subject==principal.subject else subject)}
   for subject in filters.get("actors",[])
  ]
  result["filters"]=filters
  return result

 @app.post("/api/user/password")
 def change_own_password(body:SelfPasswordChange,value=Depends(csrf)):
  principal,_=_identity(value)
  if body.password!=body.confirmation:
   raise HTTPException(422,"تکرار رمز عبور با رمز جدید یکسان نیست.")
  from . import user_accounts
  with user_accounts.directory() as service:
   service.password(principal.subject,body.password,
                    lambda:user_accounts.revoke_sessions(principal.subject))
  ux.audit(str(principal.tenant_id),principal.subject,"USER_PASSWORD_CHANGED",
           {"result":"self_service"})
  return {"updated":True,"signed_out":True}

 @app.post("/api/support/client-event")
 def client_event(body:ClientEvent,value=Depends(csrf)):
  allowed={
   "API_ERROR","API_ACTION","NAVIGATE",
   "CLIENT_NETWORK_ERROR","CLIENT_REQUEST_ABORTED","CLIENT_UI_ERROR",
  }
  if body.event not in allowed:
   raise HTTPException(422,"نوع رویداد سمت کاربر مجاز نیست.")
  principal,_=_identity(value)
  ux.audit(str(principal.tenant_id),principal.subject,body.event,body.detail)
  return {"saved":True}

 @app.post("/api/operations/{request_id}/cancel")
 def cancel_operation(request_id:str,value=Depends(csrf)):
  if len(request_id)<16 or len(request_id)>80 or not all(c.isalnum() or c in "-_" for c in request_id):
   raise HTTPException(422,"شناسه پردازش معتبر نیست.")
  principal,_=_identity(value)
  result=ux.cancel_operation(str(principal.tenant_id),principal.subject,request_id)
  from .meeting_agent import cancel_run_slot
  result["slot_released"]=cancel_run_slot((str(principal.tenant_id),principal.subject))
  return result
