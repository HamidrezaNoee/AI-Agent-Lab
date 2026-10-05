"""Per-user AVAN experience preferences, operation cancellation and support audit views."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from . import agent_storage
from .agent_workspace import user_key

DEFAULT_PREFERENCES={
    "secretary_auto_play_voice":False,
    "voice_auto_transcribe":True,
    "voice_auto_send":False,
}

_SAFE_DETAIL_KEYS={
    "request_id","path","method","status","page","source_id","operation","kind",
    "case_uid","stage","session_id","error","error_type","message","duration_ms",
    "result","filename","event","retryable",
}


class OperationCancelled(Exception):
    pass


def _scope(tenant_id):
    return {"tenant_id":str(tenant_id)}


def _preference_key(tenant_id,actor):
    return user_key("user_preferences",_scope(tenant_id),str(actor))


def preferences(tenant_id,actor):
    with agent_storage.transaction() as tx:
        saved=tx.get(_preference_key(tenant_id,actor),{})
    if not isinstance(saved,dict):saved={}
    result={**DEFAULT_PREFERENCES}
    for key in result:
        if key in saved:result[key]=bool(saved[key])
    # Sending voice without transcription is not a meaningful state.
    if not result["voice_auto_transcribe"]:result["voice_auto_send"]=False
    return result


def save_preferences(tenant_id,actor,values):
    data={key:bool(values.get(key,default)) for key,default in DEFAULT_PREFERENCES.items()}
    if not data["voice_auto_transcribe"]:data["voice_auto_send"]=False
    with agent_storage.transaction() as tx:
        tx.put(_preference_key(tenant_id,actor),data)
        tx.audit(str(tenant_id),str(actor),"USER_PREFERENCES_CHANGED",{
            "secretary_auto_play_voice":data["secretary_auto_play_voice"],
            "voice_auto_transcribe":data["voice_auto_transcribe"],
            "voice_auto_send":data["voice_auto_send"],
        })
    return data


def _clean_detail(detail):
    if not isinstance(detail,dict):return {}
    clean={}
    for key,value in detail.items():
        if key not in _SAFE_DETAIL_KEYS:continue
        if value is None or isinstance(value,(str,int,float,bool)):
            text=str(value) if not isinstance(value,(int,float,bool)) and value is not None else value
            clean[key]=text[:1000] if isinstance(text,str) else text
    return clean


def audit(tenant_id,actor,event,detail=None):
    code=str(event or "UNKNOWN").upper().replace("-","_")[:80]
    with agent_storage.transaction() as tx:
        tx.audit(str(tenant_id),str(actor),code,_clean_detail(detail or {}))


def logs(tenant_id,actor,role,*,limit=200,event=None):
    limit=max(1,min(int(limit),500))
    admin=role in ("SysAdmin","GodAdmin")
    con=agent_storage.connect()
    try:
        cur=con.cursor()
        params=[str(tenant_id)]
        where=["TenantID=?"]
        if not admin:
            where.append("ActorID=?");params.append(str(actor))
        if event:
            where.append("EventCode=?");params.append(str(event)[:80])
        sql=("SELECT TOP "+str(limit)+" EventID,TenantID,ActorID,EventCode,HappenedAt,Detail "
             "FROM dbo.AgentAudit WHERE "+" AND ".join(where)+" ORDER BY HappenedAt DESC,EventID DESC")
        rows=cur.execute(sql,*params).fetchall()
    finally:
        con.close()
    result=[]
    for row in rows:
        try:detail=json.loads(row[5]) if row[5] else {}
        except (ValueError,TypeError):detail={"message":"جزئیات لاگ قابل خواندن نیست."}
        result.append({
            "id":str(row[0]),"tenant_id":str(row[1]),"actor_id":str(row[2]),
            "event_code":str(row[3]),
            "happened_at":row[4].replace(tzinfo=timezone.utc).isoformat() if isinstance(row[4],datetime) and row[4].tzinfo is None else str(row[4]),
            "detail":_clean_detail(detail if isinstance(detail,dict) else {}),
        })
    return {"scope":"tenant" if admin else "self","logs":result,"limit":limit}


def _operation_key(tenant_id,actor,request_id):
    return user_key("operation:"+str(request_id),_scope(tenant_id),str(actor))


def start_operation(tenant_id,actor,request_id,kind,detail=None):
    if not request_id:return
    now=datetime.now(timezone.utc).isoformat()
    key=_operation_key(tenant_id,actor,request_id)
    with agent_storage.transaction() as tx:
        row=tx.get(key,{},lock=True)
        if row.get("state")=="cancelled":
            raise OperationCancelled("پردازش توسط کاربر متوقف شده است.")
        tx.put(key,{"state":"running","kind":str(kind)[:80],"started_at":now,"updated_at":now})
        tx.audit(str(tenant_id),str(actor),"SECRETARY_PROCESSING_STARTED",{
            "request_id":request_id,"kind":kind,**_clean_detail(detail or {})
        })


def cancel_operation(tenant_id,actor,request_id):
    now=datetime.now(timezone.utc).isoformat();key=_operation_key(tenant_id,actor,request_id)
    with agent_storage.transaction() as tx:
        row=tx.get(key,{},lock=True)
        row={**row,"state":"cancelled","updated_at":now}
        tx.put(key,row)
        tx.audit(str(tenant_id),str(actor),"SECRETARY_PROCESSING_CANCELLED",{
            "request_id":request_id,"kind":row.get("kind","secretary")
        })
    return {"cancelled":True,"request_id":request_id}


def ensure_active(tenant_id,actor,request_id):
    if not request_id:return
    with agent_storage.transaction() as tx:
        row=tx.get(_operation_key(tenant_id,actor,request_id),{})
    if row.get("state")=="cancelled":
        raise OperationCancelled("پردازش توسط کاربر متوقف شد؛ هیچ تغییری از این پاسخ ثبت نشد.")


def finish_operation(tenant_id,actor,request_id,state="completed",detail=None):
    if not request_id:return
    key=_operation_key(tenant_id,actor,request_id);now=datetime.now(timezone.utc).isoformat()
    with agent_storage.transaction() as tx:
        row=tx.get(key,{},lock=True)
        # Cancellation wins over late model completion.
        final_state="cancelled" if row.get("state")=="cancelled" else state
        tx.put(key,{**row,"state":final_state,"updated_at":now})
        event={
            "completed":"SECRETARY_PROCESSING_COMPLETED",
            "failed":"SECRETARY_PROCESSING_FAILED",
            "cancelled":"SECRETARY_PROCESSING_CANCELLED",
        }.get(final_state,"SECRETARY_PROCESSING_FINISHED")
        tx.audit(str(tenant_id),str(actor),event,{
            "request_id":request_id,"kind":row.get("kind","secretary"),**_clean_detail(detail or {})
        })
