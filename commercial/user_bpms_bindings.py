"""AVAN-native user to external BPMS identity bindings.

AVAN authentication/roles are authoritative for the application.  A binding only
identifies the external BPMS account used to scope data/capabilities for one
configured source.  Directory reads are always read-only and never create users.
"""
from __future__ import annotations

from datetime import datetime, timezone
from difflib import SequenceMatcher
import re
from typing import Any

from . import agent_storage
from . import native_access
from . import setup_console as setup

STORE_KEY="bpms_user_bindings"
VERSION=1
MAX_DIRECTORY_USERS=5000


class BindingError(Exception):
    pass


def _now()->str:
    return datetime.now(timezone.utc).isoformat()


def _clean_text(value:Any,limit:int=250)->str:
    return str(value or "").strip()[:limit]


def _norm(value:Any)->str:
    return re.sub(r"[^a-z0-9]+","",_clean_text(value).casefold())


def _pm_profiles()->list[dict]:
    raw=setup.get_setting("processmaker_profiles") or {}
    profiles=raw.get("profiles") if isinstance(raw,dict) else []
    return [p for p in (profiles or [])
            if isinstance(p,dict) and re.fullmatch(r"[0-9a-f]{24}",str(p.get("id","")))
            and isinstance(p.get("name"),str)]


def active_processmaker_source_id()->str|None:
    raw=setup.get_setting("processmaker_profiles") or {}
    active=raw.get("active_id") if isinstance(raw,dict) else None
    return active if isinstance(active,str) and re.fullmatch(r"[0-9a-f]{24}",active) else None


def source_catalog()->list[dict]:
    result=[{
        "id":p["id"],"name":p["name"],"engine":"processmaker",
        "connection_type":"processmaker","enabled":True,
        "active":p["id"]==active_processmaker_source_id(),
    } for p in _pm_profiles()]
    from .bpms_registry import sources
    result.extend({
        "id":row["id"],"name":row["name"],"engine":row.get("engine","other"),
        "connection_type":"adapter","enabled":bool(row.get("enabled")),
        "active":bool(row.get("enabled")),
    } for row in sources())
    return result


def _source(source_id:str)->dict:
    source=next((s for s in source_catalog() if s["id"]==source_id),None)
    if not source:
        raise BindingError("BPMS source does not exist")
    return source


def _pm_directory(source_id:str)->list[dict]:
    profile=next((p for p in _pm_profiles() if p["id"]==source_id),None)
    if not profile:
        raise BindingError("ProcessMaker source does not exist")
    mysql=profile.get("mysql") or {}
    try:
        from .processmaker_store import open_production,query,ProductionUnavailable
        with open_production(config=mysql) as con:
            rows=query(con,
                "SELECT u.USR_UID,u.USR_USERNAME,u.USR_FIRSTNAME,u.USR_LASTNAME,"
                "u.USR_EMAIL,u.USR_STATUS,d.DEP_TITLE "
                "FROM USERS u LEFT JOIN DEPARTMENT d ON d.DEP_UID=u.DEP_UID "
                "ORDER BY u.USR_USERNAME")
    except ProductionUnavailable as exc:
        raise BindingError("ProcessMaker directory is unavailable") from exc
    if len(rows)>MAX_DIRECTORY_USERS:
        raise BindingError("BPMS directory exceeds configured bounds")
    users=[]
    for row in rows:
        uid=_clean_text(row[0],128).lower()
        username=_clean_text(row[1],120)
        if not re.fullmatch(r"[a-fA-F0-9]{32}",uid) or not username:
            continue
        status=_clean_text(row[5],32).upper()
        users.append({
            "external_user_id":uid,
            "username":username,
            "display_name":(" ".join(x for x in (_clean_text(row[2],120),
                                                  _clean_text(row[3],120)) if x)
                            or username)[:240],
            "email":_clean_text(row[4],240) or None,
            "status":status,
            "active":status=="ACTIVE",
            "unit":_clean_text(row[6],160) if len(row)>6 else "",
        })
    return users


def directory_users(source_id:str)->list[dict]:
    source=_source(source_id)
    if source["connection_type"]=="processmaker":
        return _pm_directory(source_id)
    if not source.get("enabled"):
        raise BindingError("BPMS source is disabled")
    from .bpms_registry import directory_users as adapter_directory,BPMSUnavailable
    try:
        rows=adapter_directory(source_id)
    except BPMSUnavailable as exc:
        raise BindingError(str(exc)) from exc
    return rows


def _state(tx,*,lock:bool=False)->dict:
    raw=tx.get(STORE_KEY,{"version":VERSION,"bindings":[]},lock=lock)
    if not isinstance(raw,dict):
        raw={"version":VERSION,"bindings":[]}
    bindings=raw.get("bindings")
    if not isinstance(bindings,list):
        bindings=[]
    return {"version":VERSION,"bindings":[b for b in bindings if isinstance(b,dict)]}


def list_bindings(subject:str|None=None)->list[dict]:
    with agent_storage.transaction() as tx:
        state=_state(tx)
    rows=state["bindings"]
    if subject is not None:
        rows=[b for b in rows if b.get("avan_subject")==subject]
    return [dict(b) for b in rows]


def binding_for(subject:str,source_id:str)->dict|None:
    return next((b for b in list_bindings(subject)
                 if b.get("source_id")==source_id and b.get("status")=="active"),None)


def bindings_by_source(source_id:str)->dict[str,dict]:
    return {str(b["avan_subject"]):b for b in list_bindings()
            if b.get("source_id")==source_id and b.get("status")=="active"
            and b.get("avan_subject")}


def _avan_user(subject:str)->tuple[dict,dict]:
    data=native_access.read()
    user=next((u for u in data.get("users",[]) if u.get("subject")==subject),None)
    if not user:
        raise BindingError("AVAN user does not exist")
    return data,user


def suggestions(subject:str,source_id:str)->dict:
    _,user=_avan_user(subject)
    source=_source(source_id)
    rows=[u for u in directory_users(source_id) if u.get("active")]
    username=_norm(user.get("username"))
    email=_clean_text(user.get("email"),240).casefold()
    name=_norm(user.get("name"))
    candidates=[]
    for ext in rows:
        score=0
        reason=None
        if username and _norm(ext.get("username"))==username:
            score,reason=100,"username_exact"
        elif email and ext.get("email") and _clean_text(ext.get("email"),240).casefold()==email:
            score,reason=90,"email_exact"
        elif name and _norm(ext.get("display_name")):
            ratio=SequenceMatcher(None,name,_norm(ext.get("display_name"))).ratio()
            if ratio>=.82:
                score,reason=int(40+ratio*20),"display_name_similar"
        if score:
            candidates.append({**ext,"score":score,"reason":reason})
    candidates.sort(key=lambda x:(-x["score"],x.get("username","").casefold()))
    return {"source":source,"subject":subject,"suggestions":candidates[:8]}


def bind(*,subject:str,source_id:str,external_user_id:str,
         match_method:str="manual",approved_by:str="GodAdmin")->dict:
    data,user=_avan_user(subject)
    tenant_id=data.get("tenant_id")
    if not tenant_id:
        raise BindingError("Organization is not configured")
    source=_source(source_id)
    users=directory_users(source_id)
    external=next((u for u in users if u.get("external_user_id")==external_user_id),None)
    if not external or not external.get("active"):
        raise BindingError("Selected BPMS user is absent or inactive")
    if match_method not in {"manual","username_suggestion","email_suggestion",
                            "display_name_suggestion","legacy_migration"}:
        raise BindingError("Invalid binding method")
    now=_now()
    with agent_storage.transaction() as tx:
        state=_state(tx,lock=True)
        duplicate=next((b for b in state["bindings"]
                        if b.get("tenant_id")==tenant_id
                        and b.get("source_id")==source_id
                        and b.get("external_user_id")==external_user_id
                        and b.get("avan_subject")!=subject
                        and b.get("status")=="active"),None)
        if duplicate:
            raise BindingError("This BPMS user is already bound to another AVAN user")
        state["bindings"]=[b for b in state["bindings"]
                           if not (b.get("tenant_id")==tenant_id
                                   and b.get("avan_subject")==subject
                                   and b.get("source_id")==source_id)]
        record={
            "tenant_id":tenant_id,
            "avan_subject":subject,
            "source_id":source_id,
            "source_name":source["name"],
            "source_engine":source["engine"],
            "external_user_id":external["external_user_id"],
            "external_username":external.get("username") or "",
            "external_display_name":external.get("display_name") or "",
            "external_email":external.get("email"),
            "status":"active",
            "match_method":match_method,
            "approved_by":approved_by,
            "approved_at":now,
            "last_verified_at":now,
        }
        state["bindings"].append(record)
        tx.put(STORE_KEY,state)
        tx.audit(tenant_id,approved_by,"BPMS_USER_BINDING_UPSERTED",
                 {"source_id":source_id,"avan_subject":subject,
                  "external_user_id":external_user_id})
    setup.audit("BPMS_USER_BINDING_UPSERTED")
    return record


def unbind(*,subject:str,source_id:str,approved_by:str="GodAdmin")->dict:
    data,_=_avan_user(subject)
    tenant_id=data.get("tenant_id")
    removed=False
    with agent_storage.transaction() as tx:
        state=_state(tx,lock=True)
        kept=[]
        for b in state["bindings"]:
            if (b.get("tenant_id")==tenant_id and b.get("avan_subject")==subject
                    and b.get("source_id")==source_id):
                removed=True
            else:
                kept.append(b)
        if not removed:
            raise BindingError("Binding does not exist")
        state["bindings"]=kept
        tx.put(STORE_KEY,state)
        tx.audit(tenant_id or "",approved_by,"BPMS_USER_BINDING_REMOVED",
                 {"source_id":source_id,"avan_subject":subject})
    setup.audit("BPMS_USER_BINDING_REMOVED")
    return {"removed":True,"subject":subject,"source_id":source_id}


def refresh_source(source_id:str)->dict:
    source=_source(source_id)
    directory={u["external_user_id"]:u for u in directory_users(source_id)}
    now=_now();active=stale=0
    with agent_storage.transaction() as tx:
        state=_state(tx,lock=True)
        for b in state["bindings"]:
            if b.get("source_id")!=source_id:
                continue
            ext=directory.get(b.get("external_user_id"))
            if ext and ext.get("active"):
                b.update({
                    "status":"active",
                    "external_username":ext.get("username") or "",
                    "external_display_name":ext.get("display_name") or "",
                    "external_email":ext.get("email"),
                    "last_verified_at":now,
                })
                active+=1
            else:
                b["status"]="stale"
                b["last_verified_at"]=now
                stale+=1
        tx.put(STORE_KEY,state)
        tx.audit((native_access.read().get("tenant_id") or ""),"GodAdmin",
                 "BPMS_USER_BINDINGS_REFRESHED",
                 {"source_id":source_id,"active":active,"stale":stale})
    return {"source":source,"directory_users":len(directory),
            "active_bindings":active,"stale_bindings":stale}


def migrate_legacy_processmaker_bindings()->dict:
    """Copy legacy pm_uid mappings to the active ProcessMaker source, once possible."""
    source_id=active_processmaker_source_id()
    if not source_id:
        return {"migrated":0,"skipped":0,"reason":"no_active_processmaker_source"}
    data=native_access.read();migrated=skipped=0
    existing={(b.get("avan_subject"),b.get("source_id")) for b in list_bindings()}
    for user in data.get("users",[]):
        subject=user.get("subject");pm_uid=user.get("pm_uid")
        if not subject or not pm_uid or (subject,source_id) in existing:
            continue
        try:
            bind(subject=subject,source_id=source_id,external_user_id=pm_uid,
                 match_method="legacy_migration",approved_by="migration")
            migrated+=1
        except BindingError:
            skipped+=1
    return {"migrated":migrated,"skipped":skipped,"source_id":source_id}
