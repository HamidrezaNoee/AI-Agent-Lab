"""Read-only Git-like flow graph for AVAN meeting cases.

The graph never writes ProcessMaker state. It derives case membership, current
delegations and workflow stage from reviewed meeting_v2 task UIDs plus native
APPLICATION.APP_DATA.
"""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator

from . import secretary_catalog as catalog
from .processmaker_store import query, decode_case, grid, cell, text, ProductionAccessDenied, ProductionUnavailable

MAX_SCAN=1000
MAX_CHILDREN=5000
MAX_DELEGATIONS=10000

STAGES=(
 ("invitation","دعوت جلسه","دبیر"),
 ("invitation_approval","تأیید دعوت‌نامه","رئیس جلسه"),
 ("minutes","ثبت صورت‌جلسه","دبیر"),
 ("minutes_approval","تأیید صورت‌جلسه","رئیس جلسه"),
 ("action_execution","اجرای اقدام","اقدام‌کننده"),
 ("action_review","بررسی اقدام","دبیر"),
 ("monitoring","پایش و اختتام","دبیر"),
)
STAGE_INDEX={key:i+1 for i,(key,_,_) in enumerate(STAGES)}
ROLE_LABELS={
 "secretary":"دبیر","chair":"رئیس جلسه","participant":"شرکت‌کننده",
 "presenter":"ارائه‌دهنده","action_owner":"اقدام‌کننده","assignee":"مسئول وظیفه",
}
STATUS_LABELS={
 "active":"فعال","completed":"تکمیل‌شده","cancelled":"لغوشده",
 "draft":"پیش‌نویس","paused":"متوقف",
}


class FlowGraphQuery(BaseModel):
 model_config=ConfigDict(extra="forbid")
 pack_id:str=Field(pattern=r"^[0-9a-f]{24}$")
 person_uid:str|None=Field(None,pattern=r"^[a-fA-F0-9]{32}$")
 q:str=Field("",max_length=180)
 status:Literal["all","active","completed","cancelled","draft","paused"]="all"
 stage:Literal["all","invitation","invitation_approval","minutes","minutes_approval","action_execution","action_review","monitoring"]="all"
 role:Literal["all","secretary","chair","participant","presenter","action_owner","assignee"]="all"
 owner_uid:str|None=Field(None,pattern=r"^[a-fA-F0-9]{32}$")
 unit:str|None=Field(None,max_length=160)
 action_scope:Literal["all","with_actions","without_actions"]="all"
 waiting_only:bool=False
 sort:Literal["newest","oldest","progress_desc","progress_asc","stage","waiting"]="newest"
 period:Literal["all","30d","90d","365d","custom"]="90d"
 start:date|None=None
 end:date|None=None
 offset:int=Field(0,ge=0,le=5000)
 limit:int=Field(30,ge=1,le=100)

 @model_validator(mode="after")
 def dates(self):
  if bool(self.start)!=bool(self.end):
   raise ValueError("تاریخ شروع و پایان باید با هم تعیین شوند.")
  if self.start and self.end and self.end<self.start:
   raise ValueError("بازه تاریخی معتبر نیست.")
  return self


class FlowSnapshotQuery(BaseModel):
 model_config=ConfigDict(extra="forbid")
 pack_id:str=Field(pattern=r"^[0-9a-f]{24}$")
 person_uid:str|None=Field(None,pattern=r"^[a-fA-F0-9]{32}$")


def _pack(scope,pack_id):
 packs=catalog.runtime_meeting_packs(scope["source_id"])
 pack=next((p for p in packs if p.get("id")==pack_id),None)
 if not pack or pack.get("adapter")!="meeting_v2":
  raise ValueError("بسته مدیریت جلسات برای این اتصال فعال نیست.")
 return pack


def _authorized_person(scope,requested):
 uid=str(requested or scope["external_user_id"])
 visible=set(scope.get("visible_uids") or ())
 visible.add(str(scope["external_user_id"]))
 if scope.get("role")!="SysAdmin" and uid not in visible:
  raise ProductionAccessDenied("این شخص خارج از دامنه مجاز شماست.")
 if uid not in scope.get("directory",{}) and uid!=scope.get("external_user_id"):
  raise ProductionAccessDenied("کاربر انتخاب‌شده در دامنه اتصال فعال نیست.")
 return uid


def _date_bounds(args):
 if args.start:
  return datetime.combine(args.start,datetime.min.time()),datetime.combine(args.end+timedelta(days=1),datetime.min.time())
 if args.period in ("all","custom"):return None,None
 days={"30d":30,"90d":90,"365d":365}[args.period]
 return datetime.now()-timedelta(days=days),None


def _stage_maps(pack):
 by_task={}
 for key,stage in pack["stages"].items():
  by_task[str(stage["task_uid"])]=key
 return by_task


def _person(scope,uid):
 uid=str(uid or "")
 p=scope.get("directory",{}).get(uid,{})
 staff=scope.get("staff",{}).get(uid,{})
 return {
  "uid":uid,
  "name":p.get("avan_name") or p.get("name") or staff.get("name") or uid or "نامشخص",
  "username":p.get("avan_username") or p.get("username") or staff.get("username") or "",
  "unit":p.get("unit") or p.get("avan_department") or staff.get("department_name") or "واحد ثبت نشده",
 }


def _rows(value):
 return grid(value)


def _roles(data,person_uid,delegated=False):
 result=[]
 if text(data.get("MTG_SecretaryUserUID"))==person_uid:result.append("secretary")
 if text(data.get("MTG_ChairUserUID"))==person_uid:result.append("chair")
 if any(text(cell(r,"MTG_ParticipantUserUID",0))==person_uid for r in _rows(data.get("MTG_Participants"))):result.append("participant")
 if any(text(cell(r,"MTG_AgendaPresenterUID",3))==person_uid for r in _rows(data.get("MTG_Agenda"))):result.append("presenter")
 if any(text(cell(r,"MTG_ActionOwnerUID",3))==person_uid for r in _rows(data.get("MTG_Actions"))):result.append("action_owner")
 if delegated:result.append("assignee")
 return list(dict.fromkeys(result))


def _status(raw):
 value=str(raw or "").upper()
 return {
  "COMPLETED":"completed","CANCELLED":"cancelled","DRAFT":"draft",
  "PAUSED":"paused","TO_DO":"active",
 }.get(value,"active")


def _batch_delegations(con,ids):
 rows=[]
 for start in range(0,len(ids),150):
  chunk=ids[start:start+150]
  if not chunk:continue
  part=query(con,
   "SELECT d.APP_UID,d.DEL_INDEX,d.TAS_UID,d.USR_UID,d.DEL_THREAD_STATUS,d.DEL_FINISH_DATE,d.DEL_DELEGATE_DATE,t.TAS_TITLE "
   "FROM APP_DELEGATION d LEFT JOIN TASK t ON t.TAS_UID=d.TAS_UID WHERE d.APP_UID IN ("
   +",".join("%s" for _ in chunk)+") ORDER BY d.APP_UID,d.DEL_INDEX",
   chunk)
  rows.extend(part)
  if len(rows)>MAX_DELEGATIONS:raise ProductionUnavailable("Process graph delegation bound exceeded")
 return rows


def _child_map(data):
 try:mapping=json.loads(data.get("MTG_ActionCaseMapJson") or "{}")
 except (ValueError,TypeError):return {}
 if not isinstance(mapping,dict):return {}
 result={}
 for number,value in mapping.items():
  uid=value.get("caseUid") if isinstance(value,dict) else None
  if isinstance(uid,str) and len(uid)==32 and all(c in "0123456789abcdefABCDEF" for c in uid):
   result[str(number)]=uid
 return result


def _child_ids(data):
 return list(dict.fromkeys(_child_map(data).values()))


def _nodes(current_indices,completed):
 if completed:
  return [{"key":k,"title":title,"role":role,"index":i,"state":"done"} for i,(k,title,role) in enumerate(STAGES,1)]
 current=set(current_indices)
 if not current:current={1}
 first=min(current)
 result=[]
 for i,(key,title,role) in enumerate(STAGES,1):
  state="current" if i in current else "done" if i<first else "future"
  result.append({"key":key,"title":title,"role":role,"index":i,"state":state})
 return result


def _current_stage(indices,completed):
 if completed:return "completed","تکمیل‌شده"
 if not indices:return "invitation","دعوت جلسه"
 # Parallel action cases can expose both execution and review. The earliest
 # unfinished branch is the operational bottleneck.
 index=min(indices)
 key,title,_=STAGES[index-1]
 return key,title


def _progress(indices,completed):
 if completed:return 100
 if not indices:return 0
 return min(99,round(min(indices)*100/len(STAGES)))


def _load_candidates(con,scope,args,person_uid,pack):
 start,end=_date_bounds(args)
 where=["a.PRO_UID=%s","(a.APP_DATA LIKE %s OR EXISTS (SELECT 1 FROM APP_DELEGATION md WHERE md.APP_UID=a.APP_UID AND md.USR_UID=%s))"]
 params=[pack["meeting"]["process_uid"],"%"+person_uid+"%",person_uid]
 if start:
  where.append("a.APP_CREATE_DATE>=%s");params.append(start)
 if end:
  where.append("a.APP_CREATE_DATE<%s");params.append(end)
 rows=query(con,
  "SELECT a.APP_UID,a.APP_NUMBER,a.APP_STATUS,a.APP_DATA,a.APP_CREATE_DATE,a.APP_FINISH_DATE,a.APP_INIT_USER "
  "FROM APPLICATION a WHERE "+" AND ".join(where)+" ORDER BY a.APP_NUMBER DESC LIMIT "+str(MAX_SCAN+1),
  params)
 truncated=len(rows)>MAX_SCAN
 return rows[:MAX_SCAN],truncated


def _action_definition_rows(data):
 result={}
 for index,row in enumerate(_rows(data.get("MTG_Actions")),1):
  number=text(cell(row,"MTG_ActionNo",1)) or str(index)
  result[number]={
   "number":number,
   "title":text(cell(row,"MTG_ActionDescription",2)) or "اقدام جلسه",
   "owner_uid":text(cell(row,"MTG_ActionOwnerUID",3)),
  }
 return result


def _action_branch(scope,number,definition,child_uid,child_row,child_data,delegations,by_task):
 owner_uid=text(child_data.get("MTGA_OwnerUserUID")) or definition.get("owner_uid","")
 owner=_person(scope,owner_uid) if owner_uid else None
 current_stage=None
 current_owner=None
 for d in delegations:
  stage=by_task.get(str(d[2]))
  if stage in ("action_execution","action_review") and str(d[4])=="OPEN":
   current_stage=stage
   current_owner=_person(scope,d[3]) if d[3] else owner
   break
 closed=bool(child_row and (_status(child_row[2])=="completed" or text(child_data.get("MTGA_ReviewStatus"))=="Closed" or text(child_data.get("MTGA_ReviewStatus2"))=="Closed"))
 if closed:
  state="closed";stage_label="بسته‌شده";progress=100
 elif current_stage=="action_review":
  state="review";stage_label="بررسی اقدام";progress=75
 elif current_stage=="action_execution":
  state="execution";stage_label="اجرای اقدام"
  raw=child_data.get("MTGA_ProgressPercent")
  try:progress=max(0,min(99,int(raw))) if raw not in (None,"") else 35
  except (ValueError,TypeError):progress=35
 elif child_uid:
  state="created";stage_label="ایجادشده";progress=10
 else:
  state="pending";stage_label="در انتظار ایجاد";progress=0
 history=[]
 for d in delegations:
  stage=by_task.get(str(d[2]))
  if stage not in ("action_execution","action_review"):continue
  history.append({
   "case_uid":str(d[0]),"index":d[1],"stage":stage,
   "stage_title":next((title for key,title,_ in STAGES if key==stage),stage),
   "owner":_person(scope,d[3]) if d[3] else owner,
   "state":"current" if str(d[4])=="OPEN" else "done",
   "delegated_at":str(d[6] or ""),"finished_at":str(d[5] or ""),
  })
 nodes=[]
 for stage_key,title,role in (x for x in STAGES if x[0] in ("action_execution","action_review")):
  events=[x for x in history if x["stage"]==stage_key]
  people=[]
  for event in events:
   person=event.get("owner")
   if person and person.get("uid") and person["uid"] not in {p["uid"] for p in people}:people.append(person)
  if owner and owner.get("uid") and owner["uid"] not in {p["uid"] for p in people}:people.append(owner)
  entered=min((x["delegated_at"] for x in events if x["delegated_at"]),default="")
  finished=max((x["finished_at"] for x in events if x["finished_at"]),default="")
  open_now=any(x["state"]=="current" for x in events)
  if closed or (stage_key=="action_execution" and current_stage=="action_review") or (events and not open_now and finished):
   node_state="done"
  elif open_now:
   node_state="current"
  else:
   node_state="future"
  nodes.append({"key":stage_key,"title":title,"role":role,"state":node_state,
                "entered_at":entered,"finished_at":finished,"people":people})
 return {
  "action_no":number,
  "title":text(child_data.get("MTGA_ActionDescription")) or definition.get("title") or "اقدام جلسه",
  "case_uid":child_uid,
  "case_number":(int(child_row[1]) if child_row and str(child_row[1]).isdigit() else (str(child_row[1]) if child_row else None)),
  "owner":owner,
  "current_owner":current_owner or owner,
  "stage":current_stage,
  "stage_label":stage_label,
  "state":state,
  "progress_percent":progress,
  "history":history,
  "nodes":nodes,
 }


def _history(scope,case_uid,child_ids,by_case,by_task):
 events=[]
 for uid in [case_uid,*child_ids]:
  for d in by_case.get(uid,[]):
   stage=by_task.get(str(d[2]))
   if not stage:continue
   person=_person(scope,d[3]) if d[3] else None
   events.append({
    "case_uid":uid,
    "index":d[1],
    "stage":stage,
    "stage_title":next((title for key,title,_ in STAGES if key==stage),stage),
    "owner":person,
    "state":"current" if str(d[4])=="OPEN" else "done",
    "delegated_at":str(d[6] or ""),
    "finished_at":str(d[5] or ""),
   })
 return sorted(events,key=lambda x:(x["delegated_at"],x["index"]))[-40:]


def _unique_people(items):
 result=[]
 seen=set()
 for person in items:
  if not person or not person.get("uid") or person["uid"] in seen:continue
  seen.add(person["uid"]);result.append(person)
 return result


def _stage_nodes(scope,data,history,current_indices,completed):
 secretary_uid=text(data.get("MTG_SecretaryUserUID"))
 chair_uid=text(data.get("MTG_ChairUserUID"))
 secretary=_person(scope,secretary_uid) if secretary_uid else None
 chair=_person(scope,chair_uid) if chair_uid else None
 result=[]
 for node in _nodes(current_indices,completed):
  events=[event for event in history if event["stage"]==node["key"]]
  people=[event.get("owner") for event in events if event.get("owner")]
  if node["key"] in ("invitation","minutes","monitoring") and secretary:people.append(secretary)
  if node["key"] in ("invitation_approval","minutes_approval") and chair:people.append(chair)
  entered=min((event["delegated_at"] for event in events if event["delegated_at"]),default="")
  finished=max((event["finished_at"] for event in events if event["finished_at"]),default="")
  result.append({**node,
   "entered_at":entered,"finished_at":finished,"people":_unique_people(people),
   "secretary":secretary,"chair":chair,
  })
 return result


def _scalar(value,limit=5000):
 if value in (None,""):return ""
 if isinstance(value,dict):
  value=value.get("label",value.get("value",value.get("uid","")))
 if isinstance(value,(str,int,float,bool)):
  raw=str(value).strip()
  return raw[:limit]
 return ""


def _collected_fields(pack,data,stage):
 fields=(pack.get("stages",{}).get(stage,{}) or {}).get("fields",{}) or {}
 result=[]
 for key,spec in fields.items():
  if key not in data:continue
  if any(part in key.casefold() for part in ("password","secret","token","file","evidence","json","history")):continue
  value=data.get(key)
  if isinstance(value,(dict,list)) or value in (None,""):continue
  rendered=_scalar(value)
  if not rendered:continue
  result.append({"key":key,"label":str(spec.get("label") or key),"value":rendered})
 return result[:120]


def _grid_details(row,exclude=()):
 result=[]
 for key,value in row.items():
  if str(key) in exclude or str(key).endswith("_label"):continue
  rendered=_scalar(value,1200)
  if rendered:result.append({"key":str(key),"value":rendered})
 return result[:40]


def _authorized_case(scope,person_uid,data,case_uid,child_ids,child_data,history_people):
 roles=_roles(data,person_uid,person_uid in history_people.get(case_uid,set()))
 if roles:return roles
 for cid in child_ids:
  cd=child_data.get(cid,{})
  if text(cd.get("MTGA_OwnerUserUID"))==person_uid or person_uid in history_people.get(cid,set()):
   result=[]
   if text(cd.get("MTGA_OwnerUserUID"))==person_uid:result.append("action_owner")
   if person_uid in history_people.get(cid,set()):result.append("assignee")
   return result
 raise ProductionAccessDenied("این پرونده خارج از دامنه مجاز شماست.")


def snapshot(con,scope,case_uid,body:FlowSnapshotQuery):
 if 2 not in set(scope["license"]["modules"]):
  raise ProductionAccessDenied("ماژول مدیریت جلسات در لایسنس فعال نیست.")
 if len(case_uid)!=32 or any(c not in "0123456789abcdefABCDEF" for c in case_uid):
  raise ValueError("شناسه پرونده معتبر نیست.")
 pack=_pack(scope,body.pack_id)
 person_uid=_authorized_person(scope,body.person_uid)
 parent_rows=query(con,
  "SELECT APP_UID,APP_NUMBER,APP_STATUS,APP_DATA,APP_CREATE_DATE,APP_FINISH_DATE,APP_INIT_USER "
  "FROM APPLICATION WHERE APP_UID=%s AND PRO_UID=%s LIMIT 1",
  (case_uid,pack["meeting"]["process_uid"]))
 if not parent_rows:raise ProductionAccessDenied("پرونده در دامنه این بسته در دسترس نیست.")
 parent=parent_rows[0];data=decode_case(parent[3])
 mapping=_child_map(data);child_ids=list(dict.fromkeys(mapping.values()))
 child_rows=[]
 if child_ids:
  child_rows=query(con,
   "SELECT APP_UID,APP_NUMBER,APP_STATUS,APP_DATA,APP_CREATE_DATE,APP_FINISH_DATE,APP_INIT_USER "
   "FROM APPLICATION WHERE PRO_UID=%s AND APP_UID IN ("+",".join("%s" for _ in child_ids)+")",
   (pack["action"]["process_uid"],*child_ids))
 child_by_uid={str(row[0]):row for row in child_rows}
 child_data={str(row[0]):decode_case(row[3]) for row in child_rows}
 delegations=_batch_delegations(con,[case_uid,*child_by_uid.keys()])
 by_case={};history_people={}
 for d in delegations:
  by_case.setdefault(str(d[0]),[]).append(d)
  history_people.setdefault(str(d[0]),set()).add(str(d[3] or ""))
 roles=_authorized_case(scope,person_uid,data,case_uid,child_ids,child_data,history_people)
 by_task=_stage_maps(pack)
 history=_history(scope,case_uid,child_ids,by_case,by_task)
 secretary_uid=text(data.get("MTG_SecretaryUserUID"));chair_uid=text(data.get("MTG_ChairUserUID"))
 secretary=_person(scope,secretary_uid) if secretary_uid else None
 chair=_person(scope,chair_uid) if chair_uid else None

 participants=[]
 for row in _rows(data.get("MTG_Participants")):
  uid=text(cell(row,"MTG_ParticipantUserUID",0))
  if not uid:continue
  participants.append({"person":_person(scope,uid),"details":_grid_details(row,{"MTG_ParticipantUserUID"})})
 agenda=[]
 for i,row in enumerate(_rows(data.get("MTG_Agenda")),1):
  presenter_uid=text(cell(row,"MTG_AgendaPresenterUID",3))
  agenda.append({
   "index":i,
   "title":text(cell(row,"MTG_AgendaTitle",0)) or "بدون عنوان",
   "presenter":_person(scope,presenter_uid) if presenter_uid else None,
   "minutes":text(cell(row,"MTG_AgendaPlannedMinutes",2)),
   "details":_grid_details(row,{"MTG_AgendaTitle","MTG_AgendaPresenterUID","MTG_AgendaPlannedMinutes"}),
  })
 decisions=[]
 for i,row in enumerate(_rows(data.get("MTG_Decisions")),1):
  decisions.append({
   "index":i,
   "number":text(cell(row,"MTG_DecisionNo",0)) or str(i),
   "text":text(cell(row,"MTG_DecisionText",1)) or "بدون شرح",
   "details":_grid_details(row,{"MTG_DecisionNo","MTG_DecisionText"}),
  })
 definitions=_action_definition_rows(data)
 numbers=list(dict.fromkeys([*definitions.keys(),*mapping.keys()]))
 actions=[]
 for number in numbers:
  cid=mapping.get(number);crow=child_by_uid.get(cid) if cid else None;cd=child_data.get(cid,{}) if cid else {}
  branch=_action_branch(scope,number,definitions.get(number,{"number":number}),cid,crow,cd,by_case.get(cid,[]) if cid else [],by_task)
  source_row=next((r for r in _rows(data.get("MTG_Actions")) if (text(cell(r,"MTG_ActionNo",1)) or "")==number),{})
  actions.append({**branch,
   "due_date":text(cell(source_row,"MTG_persiandate_ActionDueDateTime",4)) or text(cd.get("MTGA_DueDateTime")),
   "priority":text(cell(source_row,"MTG_ActionPriority",5)) or text(cd.get("MTGA_Priority")),
   "decision_no":text(cell(source_row,"MTG_ActionDecisionNo",0)),
   "latest_fields":[
    {"key":key,"value":_scalar(value)}
    for key,value in cd.items()
    if _scalar(value) and not isinstance(value,(dict,list))
       and not any(part in str(key).casefold() for part in ("password","secret","token","file","evidence","json","history"))
   ][:80],
  })

 stages=[]
 for key,title,role in STAGES:
  if key in ("action_execution","action_review"):
   items=[]
   for action in actions:
    values=_collected_fields(pack,child_data.get(action.get("case_uid"),{}),key) if action.get("case_uid") else []
    if values:items.append({"action_no":action["action_no"],"title":action["title"],"fields":values})
   stages.append({"key":key,"title":title,"role":role,"actions":items,"fields":[]})
  else:
   stages.append({"key":key,"title":title,"role":role,"fields":_collected_fields(pack,data,key),"actions":[]})

 return {
  "case_uid":case_uid,
  "case_number":int(parent[1]) if str(parent[1]).isdigit() else str(parent[1]),
  "status":_status(parent[2]),"status_label":STATUS_LABELS.get(_status(parent[2]),_status(parent[2])),
  "roles":roles,
  "meeting":{
   "meeting_no":text(data.get("MTG_MeetingNo")) or str(parent[1]),
   "title":text(data.get("MTG_MeetingTitle")) or "جلسه بدون عنوان",
   "objective":text(data.get("MTG_Objective")),
   "location":text(data.get("MTG_Location")),
   "meeting_date":text(data.get("MTG_persiandate_MeetingStartDateTime") or data.get("MTG_MeetingStartDateTime")),
   "start_time":text(data.get("MTG_MeetingStartTime")),
   "end_date":text(data.get("MTG_persiandate_MeetingEndDateTime") or data.get("MTG_MeetingEndDateTime")),
   "end_time":text(data.get("MTG_MeetingEndTime") or data.get("MTG_PlannedActionEndTime")),
   "discussion":text(data.get("MTG_MeetingDiscussionSummary")),
   "parking_lot":text(data.get("MTG_ParkingLot")),
   "closing_note":text(data.get("MTG_ClosingNote")),
   "created_at":str(parent[4] or ""),"finished_at":str(parent[5] or ""),
  },
  "secretary":secretary,"chair":chair,"participants":participants,
  "agenda":agenda,"decisions":decisions,"actions":actions,
  "stage_history":history,"stages":stages,
 }


def load(con,scope,args:FlowGraphQuery):
 if 2 not in set(scope["license"]["modules"]):
  raise ProductionAccessDenied("ماژول مدیریت جلسات در لایسنس فعال نیست.")
 pack=_pack(scope,args.pack_id)
 person_uid=_authorized_person(scope,args.person_uid)
 parents,truncated=_load_candidates(con,scope,args,person_uid,pack)

 decoded={}
 valid=[]
 parent_ids=[]
 child_ids=[]
 for row in parents:
  data=decode_case(row[3])
  # APP_DATA LIKE is a candidate optimization only. Exact membership is
  # rechecked below together with historical delegation membership.
  decoded[row[0]]=data
  valid.append(row);parent_ids.append(str(row[0]))
  child_ids.extend(_child_ids(data))
 child_ids=list(dict.fromkeys(child_ids))
 if len(child_ids)>MAX_CHILDREN:raise ProductionUnavailable("Process graph child bound exceeded")

 child_rows=[]
 for start in range(0,len(child_ids),150):
  chunk=child_ids[start:start+150]
  child_rows.extend(query(con,
   "SELECT APP_UID,APP_NUMBER,APP_STATUS,APP_DATA,APP_CREATE_DATE,APP_FINISH_DATE,APP_INIT_USER "
   "FROM APPLICATION WHERE PRO_UID=%s AND APP_UID IN ("+",".join("%s" for _ in chunk)+")",
   (pack["action"]["process_uid"],*chunk)))
 child_by_uid={str(r[0]):r for r in child_rows}
 child_data={str(r[0]):decode_case(r[3]) for r in child_rows}

 all_ids=parent_ids+list(child_by_uid)
 delegations=_batch_delegations(con,all_ids)
 by_case={}
 historical_people={}
 for d in delegations:
  by_case.setdefault(str(d[0]),[]).append(d)
  historical_people.setdefault(str(d[0]),set()).add(str(d[3] or ""))

 by_task=_stage_maps(pack)
 rows=[]
 option_owners={}
 option_units=set()
 for parent in valid:
  case_uid=str(parent[0]);data=decoded[case_uid]
  delegated=person_uid in historical_people.get(case_uid,set())
  roles=_roles(data,person_uid,delegated)
  if not roles:
   # Exact membership may be represented only in an action child.
   child_membership=False
   for cid in _child_ids(data):
    cd=child_data.get(cid,{})
    if text(cd.get("MTGA_OwnerUserUID"))==person_uid or person_uid in historical_people.get(cid,set()):
     child_membership=True
     if text(cd.get("MTGA_OwnerUserUID"))==person_uid:roles.append("action_owner")
     if person_uid in historical_people.get(cid,set()):roles.append("assignee")
   if not child_membership:continue

  current=[]
  owners=[]
  action_counts={"total":0,"open":0,"review":0,"closed":0}
  for d in by_case.get(case_uid,[]):
   stage=by_task.get(str(d[2]))
   if stage and str(d[4])=="OPEN":
    current.append(STAGE_INDEX[stage])
    if d[3]:owners.append(str(d[3]))

  definitions=_action_definition_rows(data)
  mapping=_child_map(data)
  numbers=list(dict.fromkeys([*definitions.keys(),*mapping.keys()]))
  action_branches=[]
  for number in numbers:
   cid=mapping.get(number)
   crow=child_by_uid.get(cid) if cid else None
   cd=child_data.get(cid,{}) if cid else {}
   branch=_action_branch(scope,number,definitions.get(number,{"number":number}),cid,crow,cd,by_case.get(cid,[]) if cid else [],by_task)
   action_branches.append(branch)
   action_counts["total"]+=1
   if branch["state"]=="closed":action_counts["closed"]+=1
   elif branch["state"]=="review":action_counts["review"]+=1
   else:action_counts["open"]+=1
   if branch["stage"]:current.append(STAGE_INDEX[branch["stage"]])
   if branch["current_owner"] and branch["current_owner"].get("uid"):owners.append(branch["current_owner"]["uid"])
  raw_status=_status(parent[2])
  completed=raw_status=="completed"
  current=list(dict.fromkeys(current))
  owners=list(dict.fromkeys(x for x in owners if x))
  stage_key,stage_title=_current_stage(current,completed)
  owner_objects=[_person(scope,x) for x in owners]
  for owner in owner_objects:
   option_owners[owner["uid"]]=owner;option_units.add(owner["unit"])
  item={
   "case_uid":case_uid,
   "case_number":int(parent[1]) if str(parent[1]).isdigit() else str(parent[1]),
   "meeting_no":text(data.get("MTG_MeetingNo")) or str(parent[1]),
   "title":text(data.get("MTG_MeetingTitle")) or "جلسه بدون عنوان",
   "status":raw_status,
   "status_label":STATUS_LABELS.get(raw_status,raw_status),
   "current_stage":stage_key,
   "current_stage_title":stage_title,
   "current_owners":owner_objects,
   "current_owner_label":("، ".join(o["name"] for o in owner_objects[:2])+((" +"+str(len(owner_objects)-2)) if len(owner_objects)>2 else "")) if owner_objects else "بدون مسئول باز",
   "my_roles":roles,
   "my_role_label":"، ".join(ROLE_LABELS[r] for r in roles),
   "progress_percent":_progress(current,completed),
   "nodes":_stage_nodes(scope,data,_history(scope,case_uid,[x for x in mapping.values()],by_case,by_task),current,completed),
   "actions":action_counts,
   "action_branches":action_branches,
   "topology":{"split_after":"minutes_approval","merge_before":"monitoring",
               "branch_count":len(action_branches),
               "all_branches_closed":bool(action_branches) and all(x["state"]=="closed" for x in action_branches)},
   "meeting_roles":{
    "secretary":_person(scope,text(data.get("MTG_SecretaryUserUID"))) if text(data.get("MTG_SecretaryUserUID")) else None,
    "chair":_person(scope,text(data.get("MTG_ChairUserUID"))) if text(data.get("MTG_ChairUserUID")) else None,
   },
   "history":_history(scope,case_uid,[x for x in mapping.values()],by_case,by_task),
   "created_at":str(parent[4] or ""),
   "finished_at":str(parent[5] or ""),
   "meeting_date":text(data.get("MTG_persiandate_MeetingStartDateTime") or data.get("MTG_MeetingStartDateTime")),
  }
  rows.append(item)

 # Filter only after authorization + exact membership checks.
 needle=(args.q or "").strip().casefold()
 def keep(item):
  if needle and needle not in (" ".join([str(item["case_number"]),item["meeting_no"],item["title"]])).casefold():return False
  if args.status!="all" and item["status"]!=args.status:return False
  if args.stage!="all" and item["current_stage"]!=args.stage:return False
  if args.role!="all" and args.role not in item["my_roles"]:return False
  if args.owner_uid and args.owner_uid not in {o["uid"] for o in item["current_owners"]}:return False
  if args.unit and args.unit not in {o["unit"] for o in item["current_owners"]}:return False
  if args.action_scope=="with_actions" and not item["actions"]["total"]:return False
  if args.action_scope=="without_actions" and item["actions"]["total"]:return False
  if args.waiting_only and person_uid not in {o["uid"] for o in item["current_owners"]}:return False
  return True
 filtered=[x for x in rows if keep(x)]
 if args.sort=="oldest":filtered.sort(key=lambda x:(x["created_at"],str(x["case_number"])))
 elif args.sort=="progress_desc":filtered.sort(key=lambda x:(-x["progress_percent"],str(x["case_number"])))
 elif args.sort=="progress_asc":filtered.sort(key=lambda x:(x["progress_percent"],str(x["case_number"])))
 elif args.sort=="stage":filtered.sort(key=lambda x:(STAGE_INDEX.get(x["current_stage"],99),str(x["case_number"])))
 elif args.sort=="waiting":filtered.sort(key=lambda x:(person_uid not in {o["uid"] for o in x["current_owners"]},-x["progress_percent"],str(x["case_number"])))
 else:filtered.sort(key=lambda x:(x["created_at"],str(x["case_number"])),reverse=True)
 total=len(filtered)
 page=filtered[args.offset:args.offset+args.limit]
 summary={
  "total_cases":total,
  "active_cases":sum(x["status"] in ("active","draft","paused") for x in filtered),
  "completed_cases":sum(x["status"]=="completed" for x in filtered),
  "waiting_my_action":sum(person_uid in {o["uid"] for o in x["current_owners"]} for x in filtered),
  "average_progress":round(sum(x["progress_percent"] for x in filtered)/total) if total else 0,
 }
 visible=set(scope.get("visible_uids") or ())|{str(scope["external_user_id"])}
 people=[]
 for uid in sorted(visible):
  p=scope.get("directory",{}).get(uid,{})
  if not p.get("active"):continue
  obj=_person(scope,uid)
  people.append(obj)
  if len(people)>=300:break
 filters={
  "people":people,
  "owners":sorted(option_owners.values(),key=lambda x:(x["name"],x["uid"])),
  "units":sorted(x for x in option_units if x),
  "roles":[{"value":k,"label":v} for k,v in ROLE_LABELS.items()],
  "stages":[{"value":k,"label":title} for k,title,_ in STAGES],
  "statuses":[{"value":k,"label":v} for k,v in STATUS_LABELS.items()],
 }
 return {
  "person":_person(scope,person_uid),
  "summary":summary,
  "rows":page,
  "filters":filters,
  "total":total,
  "offset":args.offset,
  "limit":args.limit,
  "has_more":total>args.offset+args.limit,
  "truncated":truncated,
  "stage_order":[{"key":k,"title":t,"role":r,"index":i} for i,(k,t,r) in enumerate(STAGES,1)],
 }
