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
 detail:dict={}


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
                  value=Depends(authorized)):
  principal,role=_identity(value)
  return ux.logs(str(principal.tenant_id),principal.subject,role,limit=limit,event=event)

 @app.post("/api/support/client-event")
 def client_event(body:ClientEvent,value=Depends(csrf)):
  principal,_=_identity(value)
  ux.audit(str(principal.tenant_id),principal.subject,body.event,body.detail)
  return {"saved":True}

 @app.post("/api/operations/{request_id}/cancel")
 def cancel_operation(request_id:str,value=Depends(csrf)):
  if len(request_id)<16 or len(request_id)>80 or not all(c.isalnum() or c in "-_" for c in request_id):
   raise HTTPException(422,"شناسه پردازش معتبر نیست.")
  principal,_=_identity(value)
  return ux.cancel_operation(str(principal.tenant_id),principal.subject,request_id)
