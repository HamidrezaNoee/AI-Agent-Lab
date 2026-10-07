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
    "result","filename","event","retryable","code","model","question_hash","coverage_complete",
    "input_tokens","output_tokens","total_tokens","meeting_id","action_id","pack_id",
    "revision","del_index","process_uid","provider","secretary_auto_play_voice",
    "voice_auto_transcribe","voice_auto_send",
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


def logs(tenant_id,actor,role,*,limit=200,event=None,actor_id=None,
         source_id=None,process_uid=None,case_uid=None,stage=None,request_id=None,q=None):
    """Return tenant/user scoped audit rows with operational filters.

    JSON predicates run inside the tenant/actor authorization boundary before
    the result limit, so old matching cases remain searchable. Only safe detail
    fields are returned; malformed legacy JSON is treated as an empty object.
    """
    limit=max(1,min(int(limit),500))
    admin=role in ("SysAdmin","GodAdmin")
    con=agent_storage.connect()
    try:
        cur=con.cursor()
        params=[str(tenant_id)]
        where=["TenantID=?"]
        if not admin:
            where.append("ActorID=?");params.append(str(actor))
        elif actor_id:
            where.append("ActorID=?");params.append(str(actor_id))
        if event:
            where.append("EventCode=?");params.append(str(event)[:80])
        # Filter before TOP: an older matching case must not disappear behind
        # unrelated recent traffic. CASE protects legacy malformed JSON rows.
        safe_json="CASE WHEN ISJSON(Detail)=1 THEN Detail ELSE N'{}' END"
        def detail_value(key):return "JSON_VALUE("+safe_json+", '$."+key+"')"
        for key,value in (("source_id",source_id),("process_uid",process_uid),
                          ("case_uid",case_uid),("stage",stage),("request_id",request_id)):
            if not str(value or "").strip():continue
            value=str(value).strip()
            if key=="process_uid":
                where.append("("+detail_value(key)+"=? OR "+detail_value("pack_id")+"=?)")
                params.extend([value,value])
            else:
                where.append(detail_value(key)+"=?");params.append(value)
        if str(q or "").strip():
            searchable=["EventCode","ActorID"]+[detail_value(key) for key in
                ("message","error","path","source_id","process_uid","case_uid","stage","request_id")]
            where.append("CHARINDEX(LOWER(?),LOWER(CONCAT("+",N' ',".join(searchable)+")))>0")
            params.append(str(q).strip())
        fetch_limit=limit+1
        sql=("SELECT TOP "+str(fetch_limit)+" EventID,TenantID,ActorID,EventCode,HappenedAt,Detail "
             "FROM dbo.AgentAudit WHERE "+" AND ".join(where)+" ORDER BY HappenedAt DESC,EventID DESC")
        rows=cur.execute(sql,*params).fetchall()
    finally:
        con.close()

    parsed=[]
    filter_values={"actors":set(),"sources":set(),"processes":set(),"stages":set()}
    for row in rows:
        try:detail=json.loads(row[5]) if row[5] else {}
        except (ValueError,TypeError):detail={"message":"جزئیات لاگ قابل خواندن نیست."}
        if not isinstance(detail,dict):detail={}
        clean=_clean_detail(detail)
        item={
            "id":str(row[0]),"tenant_id":str(row[1]),"actor_id":str(row[2]),
            "event_code":str(row[3]),
            "happened_at":row[4].replace(tzinfo=timezone.utc).isoformat() if isinstance(row[4],datetime) and row[4].tzinfo is None else str(row[4]),
            "detail":clean,
        }
        filter_values["actors"].add(item["actor_id"])
        if clean.get("source_id"):filter_values["sources"].add(str(clean["source_id"]))
        process_value=clean.get("process_uid") or clean.get("pack_id")
        if process_value:filter_values["processes"].add(str(process_value))
        if clean.get("stage"):filter_values["stages"].add(str(clean["stage"]))
        parsed.append(item)

    exact={
        "source_id":str(source_id or "").strip(),
        "process_uid":str(process_uid or "").strip(),
        "case_uid":str(case_uid or "").strip(),
        "stage":str(stage or "").strip(),
        "request_id":str(request_id or "").strip(),
    }
    needle=str(q or "").strip().casefold()
    def keep(item):
        detail=item["detail"]
        for key,value in exact.items():
            if not value:continue
            if key=="process_uid":
                if value not in (str(detail.get("process_uid") or ""),str(detail.get("pack_id") or "")):return False
            elif str(detail.get(key) or "")!=value:return False
        if needle:
            hay=" ".join(str(x or "") for x in (
                item["event_code"],item["actor_id"],detail.get("message"),detail.get("error"),
                detail.get("path"),detail.get("source_id"),detail.get("process_uid"),
                detail.get("case_uid"),detail.get("stage"),detail.get("request_id"),
            )).casefold()
            if needle not in hay:return False
        return True
    result=[item for item in parsed if keep(item)][:limit]
    return {
        "scope":"tenant" if admin else "self",
        "logs":result,"limit":limit,
        "filters":{
            "actors":sorted(filter_values["actors"]),
            "sources":sorted(filter_values["sources"]),
            "processes":sorted(filter_values["processes"]),
            "stages":sorted(filter_values["stages"]),
        },
        "truncated":len(rows)>=fetch_limit,
    }

def _operations_key(tenant_id,actor):
    return user_key("operations",_scope(tenant_id),str(actor))


def _prune_operations(rows,limit=50):
    if not isinstance(rows,dict):return {}
    ordered=sorted(
        ((str(key),value) for key,value in rows.items() if isinstance(value,dict)),
        key=lambda item:str(item[1].get("updated_at") or item[1].get("started_at") or ""),
        reverse=True,
    )
    # Running/cancelled entries may still have a late worker capable of returning.
    # Never prune those guards until the worker reaches finish_operation.
    guarded=[item for item in ordered if item[1].get("state") in ("running","cancelled")]
    terminal=[item for item in ordered if item[1].get("state") not in ("running","cancelled")][:limit]
    return dict([*guarded,*terminal])


def start_operation(tenant_id,actor,request_id,kind,detail=None):
    if not request_id:return
    now=datetime.now(timezone.utc).isoformat()
    key=_operations_key(tenant_id,actor)
    with agent_storage.transaction() as tx:
        rows=tx.get(key,{},lock=True)
        if not isinstance(rows,dict):rows={}
        previous=rows.get(str(request_id),{})
        if previous.get("state")=="cancelled":
            raise OperationCancelled("پردازش توسط کاربر متوقف شده است.")
        rows[str(request_id)]={"state":"running","kind":str(kind)[:80],"started_at":now,"updated_at":now,
                              "context":_clean_detail(detail or {})}
        tx.put(key,_prune_operations(rows))
        tx.audit(str(tenant_id),str(actor),"SECRETARY_PROCESSING_STARTED",{
            "request_id":request_id,"kind":kind,**_clean_detail(detail or {})
        })


def cancel_operation(tenant_id,actor,request_id):
    now=datetime.now(timezone.utc).isoformat();key=_operations_key(tenant_id,actor)
    with agent_storage.transaction() as tx:
        rows=tx.get(key,{},lock=True)
        if not isinstance(rows,dict):rows={}
        row=rows.get(str(request_id),{})
        row={**row,"state":"cancelled","updated_at":now}
        rows[str(request_id)]=row
        tx.put(key,_prune_operations(rows))
        tx.audit(str(tenant_id),str(actor),"SECRETARY_PROCESSING_CANCELLED",{
            **row.get("context",{}),"request_id":request_id,"kind":row.get("kind","secretary")
        })
    return {"cancelled":True,"request_id":request_id}


def ensure_active(tenant_id,actor,request_id):
    if not request_id:return
    with agent_storage.transaction() as tx:
        rows=tx.get(_operations_key(tenant_id,actor),{})
    row=rows.get(str(request_id),{}) if isinstance(rows,dict) else {}
    if row.get("state") in ("cancelled","cancelled_finished"):
        raise OperationCancelled("پردازش توسط کاربر متوقف شد؛ هیچ تغییری از این پاسخ ثبت نشد.")


def finish_operation(tenant_id,actor,request_id,state="completed",detail=None):
    if not request_id:return
    key=_operations_key(tenant_id,actor);now=datetime.now(timezone.utc).isoformat()
    with agent_storage.transaction() as tx:
        rows=tx.get(key,{},lock=True)
        if not isinstance(rows,dict):rows={}
        row=rows.get(str(request_id),{})
        # Cancellation wins over late model completion. Once the old worker
        # reaches this point, downgrade the persistent guard to a terminal state
        # that is eligible for bounded pruning.
        was_cancelled=row.get("state")=="cancelled"
        final_state="cancelled_finished" if was_cancelled else state
        rows[str(request_id)]={**row,"state":final_state,"updated_at":now}
        tx.put(key,_prune_operations(rows))
        # cancel_operation already writes the authoritative cancellation audit.
        if not was_cancelled:
            event={
                "completed":"SECRETARY_PROCESSING_COMPLETED",
                "failed":"SECRETARY_PROCESSING_FAILED",
                "cancelled":"SECRETARY_PROCESSING_CANCELLED",
            }.get(final_state,"SECRETARY_PROCESSING_FINISHED")
            tx.audit(str(tenant_id),str(actor),event,{
                **row.get("context",{}),"request_id":request_id,"kind":row.get("kind","secretary"),**_clean_detail(detail or {})
            })

