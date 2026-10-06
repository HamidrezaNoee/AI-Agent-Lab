import json
import phpserialize
import pytest

from commercial import process_case_graph as g
from commercial.processmaker_store import ProductionAccessDenied


PACK={
 "id":"a"*24,"adapter":"meeting_v2",
 "meeting":{"process_uid":"m"*32},
 "action":{"process_uid":"c"*32},
 "stages":{
  "invitation":{"task_uid":"1"*32},
  "invitation_approval":{"task_uid":"2"*32},
  "minutes":{"task_uid":"3"*32},
  "minutes_approval":{"task_uid":"4"*32},
  "action_execution":{"task_uid":"5"*32},
  "action_review":{"task_uid":"6"*32},
  "monitoring":{"task_uid":"7"*32},
 }
}
U1="a"*32
U2="b"*32
SCOPE={
 "source_id":"source","external_user_id":U1,"role":"Expert",
 "license":{"modules":{1,2,3,4}},
 "visible_uids":{U1},
 "directory":{
  U1:{"active":True,"name":"Administrator","avan_name":"مدیر سیستم","username":"administrator","unit":"IT"},
  U2:{"active":True,"name":"CEO","avan_name":"مدیرعامل","username":"ceo","unit":"مدیریت"},
 },
 "staff":{},
}


def test_flow_graph_builds_git_like_stage_and_current_owner(monkeypatch):
 data={
  "MTG_MeetingNo":"MTG-1001","MTG_MeetingTitle":"بررسی AVAN",
  "MTG_SecretaryUserUID":U1,"MTG_ChairUserUID":U2,
  "MTG_Participants":{"1":{"MTG_ParticipantUserUID":U1}},
 }
 parent=("f"*32,718,"TO_DO",phpserialize.dumps(data),"2026-10-05 10:00:00",None,U1)
 monkeypatch.setattr(g,"_pack",lambda scope,pack_id:PACK)
 def fake_query(con,sql,args=()):
  if "FROM APPLICATION a WHERE" in sql:return [parent]
  if "FROM APP_DELEGATION d" in sql:
   return [("f"*32,2,"2"*32,U2,"OPEN",None,"2026-10-05 10:05:00","تأیید دعوت")]
  raise AssertionError(sql)
 monkeypatch.setattr(g,"query",fake_query)
 result=g.load(object(),SCOPE,g.FlowGraphQuery(pack_id="a"*24,period="all"))
 assert result["summary"]["total_cases"]==1
 row=result["rows"][0]
 assert row["current_stage"]=="invitation_approval"
 assert row["current_owner_label"]=="مدیرعامل"
 assert row["my_roles"]==["secretary","participant"]
 assert row["progress_percent"]==29
 assert [n["state"] for n in row["nodes"][:3]]==["done","current","future"]
 approval=row["nodes"][1]
 assert approval["entered_at"]=="2026-10-05 10:05:00"
 assert approval["chair"]["name"]=="مدیرعامل"
 assert approval["secretary"]["name"]=="مدیر سیستم"
 assert [p["name"] for p in approval["people"]]==["مدیرعامل"]
 assert row["topology"]["split_after"]=="minutes_approval"


def test_flow_graph_filters_by_role_and_owner(monkeypatch):
 data={"MTG_MeetingTitle":"جلسه","MTG_SecretaryUserUID":U1,"MTG_ChairUserUID":U2}
 parent=("f"*32,10,"TO_DO",phpserialize.dumps(data),"2026-10-05",None,U1)
 monkeypatch.setattr(g,"_pack",lambda scope,pack_id:PACK)
 def fake_query(con,sql,args=()):
  if "FROM APPLICATION a WHERE" in sql:return [parent]
  if "FROM APP_DELEGATION d" in sql:return [("f"*32,1,"2"*32,U2,"OPEN",None,"2026-10-05 10:05:00","")]
  raise AssertionError(sql)
 monkeypatch.setattr(g,"query",fake_query)
 yes=g.load(object(),SCOPE,g.FlowGraphQuery(pack_id="a"*24,role="secretary",owner_uid=U2,period="all"))
 no=g.load(object(),SCOPE,g.FlowGraphQuery(pack_id="a"*24,role="chair",period="all"))
 assert yes["total"]==1
 assert no["total"]==0


def test_flow_graph_rejects_person_outside_scope(monkeypatch):
 monkeypatch.setattr(g,"_pack",lambda scope,pack_id:PACK)
 with pytest.raises(ProductionAccessDenied):
  g.load(object(),SCOPE,g.FlowGraphQuery(pack_id="a"*24,person_uid=U2,period="all"))


def test_completed_case_marks_all_seven_nodes_done():
 nodes=g._nodes([],True)
 assert len(nodes)==7
 assert all(n["state"]=="done" for n in nodes)
 assert g._progress([],True)==100


def test_action_branch_models_parallel_git_like_lane():
 scope={**SCOPE,"visible_uids":{U1,U2}}
 branch=g._action_branch(
  scope,"A-01",{"title":"پیگیری قرارداد","owner_uid":U2},
  "c"*32,("c"*32,900,"TO_DO",b"",None,None,U2),
  {"MTGA_ActionDescription":"پیگیری قرارداد","MTGA_OwnerUserUID":U2,"MTGA_ProgressPercent":"60"},
  [("c"*32,1,"5"*32,U2,"OPEN",None,"2026-10-05 12:00:00","اجرای اقدام")],
  {"5"*32:"action_execution","6"*32:"action_review"},
 )
 assert branch["stage"]=="action_execution"
 assert branch["state"]=="execution"
 assert branch["progress_percent"]==60
 assert branch["current_owner"]["name"]=="مدیرعامل"
 assert [n["key"] for n in branch["nodes"]]==["action_execution","action_review"]
 assert branch["nodes"][0]["state"]=="current"
 assert branch["nodes"][0]["entered_at"]=="2026-10-05 12:00:00"
 assert branch["nodes"][0]["people"][0]["name"]=="مدیرعامل"


def test_waiting_only_filters_to_selected_person(monkeypatch):
 data={"MTG_MeetingTitle":"جلسه","MTG_SecretaryUserUID":U1,"MTG_ChairUserUID":U2}
 parent=("f"*32,10,"TO_DO",phpserialize.dumps(data),"2026-10-05",None,U1)
 monkeypatch.setattr(g,"_pack",lambda scope,pack_id:PACK)
 def fake_query(con,sql,args=()):
  if "FROM APPLICATION a WHERE" in sql:return [parent]
  if "FROM APP_DELEGATION d" in sql:return [("f"*32,1,"2"*32,U2,"OPEN",None,"2026-10-05 10:05:00","")]
  raise AssertionError(sql)
 monkeypatch.setattr(g,"query",fake_query)
 result=g.load(object(),{**SCOPE,"role":"SysAdmin"},g.FlowGraphQuery(pack_id="a"*24,person_uid=U2,waiting_only=True,period="all"))
 assert result["total"]==1
 assert result["summary"]["waiting_my_action"]==1


def test_snapshot_returns_latest_cross_stage_case_data(monkeypatch):
 child_uid="c"*32
 data={
  "MTG_MeetingNo":"MTG-200","MTG_MeetingTitle":"جلسه چندشاخه",
  "MTG_Objective":"بررسی اقدامات","MTG_Location":"اتاق جلسات",
  "MTG_MeetingStartDateTime":"1405/07/13","MTG_MeetingStartTime":"10:00",
  "MTG_SecretaryUserUID":U1,"MTG_ChairUserUID":U2,
  "MTG_Participants":{"1":{"MTG_ParticipantUserUID":U2,"MTG_ParticipantPresent":"Yes"}},
  "MTG_Agenda":{"1":{"MTG_AgendaTitle":"بررسی قرارداد","MTG_AgendaPresenterUID":U2,"MTG_AgendaPlannedMinutes":"15"}},
  "MTG_Decisions":{"1":{"MTG_DecisionNo":"D-01","MTG_DecisionText":"قرارداد پیگیری شود"}},
  "MTG_Actions":{"1":{"MTG_ActionNo":"A-01","MTG_ActionDescription":"پیگیری قرارداد","MTG_ActionOwnerUID":U2,
                      "MTG_persiandate_ActionDueDateTime":"1405/07/20","MTG_ActionDecisionNo":"D-01"}},
  "MTG_ActionCaseMapJson":json.dumps({"A-01":{"caseUid":child_uid}}),
 }
 child_data={"MTGA_ActionNo":"A-01","MTGA_ActionDescription":"پیگیری قرارداد",
             "MTGA_OwnerUserUID":U2,"MTGA_ProgressPercent":"60"}
 parent=("f"*32,200,"TO_DO",phpserialize.dumps(data),"2026-10-05 10:00:00",None,U1)
 child=(child_uid,901,"TO_DO",phpserialize.dumps(child_data),"2026-10-05 11:00:00",None,U2)
 monkeypatch.setattr(g,"_pack",lambda scope,pack_id:PACK)
 def fake_query(con,sql,args=()):
  if "WHERE APP_UID=%s AND PRO_UID=%s LIMIT 1" in sql:return [parent]
  if "FROM APPLICATION WHERE PRO_UID=%s AND APP_UID IN" in sql:return [child]
  if "FROM APP_DELEGATION d" in sql:
   return [
    ("f"*32,1,"1"*32,U1,"CLOSED","2026-10-05 10:04:00","2026-10-05 10:00:00","دعوت"),
    (child_uid,1,"5"*32,U2,"OPEN",None,"2026-10-05 11:05:00","اجرای اقدام"),
   ]
  raise AssertionError(sql)
 monkeypatch.setattr(g,"query",fake_query)
 result=g.snapshot(object(),SCOPE,"f"*32,g.FlowSnapshotQuery(pack_id="a"*24))
 assert result["meeting"]["title"]=="جلسه چندشاخه"
 assert result["secretary"]["name"]=="مدیر سیستم"
 assert result["chair"]["name"]=="مدیرعامل"
 assert result["participants"][0]["person"]["name"]=="مدیرعامل"
 assert result["agenda"][0]["title"]=="بررسی قرارداد"
 assert result["decisions"][0]["number"]=="D-01"
 assert result["actions"][0]["action_no"]=="A-01"
 assert result["actions"][0]["progress_percent"]==60
 assert result["actions"][0]["nodes"][0]["entered_at"]=="2026-10-05 11:05:00"
 assert {x["stage"] for x in result["stage_history"]}=={"invitation","action_execution"}


def test_snapshot_rejects_case_without_membership(monkeypatch):
 data={"MTG_MeetingTitle":"جلسه دیگر","MTG_SecretaryUserUID":U2}
 parent=("f"*32,300,"TO_DO",phpserialize.dumps(data),"2026-10-05",None,U2)
 monkeypatch.setattr(g,"_pack",lambda scope,pack_id:PACK)
 def fake_query(con,sql,args=()):
  if "WHERE APP_UID=%s AND PRO_UID=%s LIMIT 1" in sql:return [parent]
  if "FROM APP_DELEGATION d" in sql:return []
  raise AssertionError(sql)
 monkeypatch.setattr(g,"query",fake_query)
 with pytest.raises(ProductionAccessDenied):
  g.snapshot(object(),SCOPE,"f"*32,g.FlowSnapshotQuery(pack_id="a"*24))


def test_planned_actions_do_not_create_visual_branches_before_child_cases(monkeypatch):
 data={
  "MTG_MeetingTitle":"جلسه قبل از ایجاد کیس اقدام",
  "MTG_SecretaryUserUID":U1,"MTG_ChairUserUID":U2,
  "MTG_Actions":{"1":{"MTG_ActionNo":"A-001","MTG_ActionDescription":"پیگیری مجوز","MTG_ActionOwnerUID":U2}},
 }
 parent=("f"*32,77,"TO_DO",phpserialize.dumps(data),"2026-10-05 10:00:00",None,U1)
 monkeypatch.setattr(g,"_pack",lambda scope,pack_id:PACK)
 def fake_query(con,sql,args=()):
  if "FROM APPLICATION a WHERE" in sql:return [parent]
  if "FROM APP_DELEGATION d" in sql:
   return [("f"*32,4,"4"*32,U2,"OPEN",None,"2026-10-05 12:00:00","تأیید صورتجلسه")]
  raise AssertionError(sql)
 monkeypatch.setattr(g,"query",fake_query)
 result=g.load(object(),{**SCOPE,"visible_uids":{U1,U2}},g.FlowGraphQuery(pack_id="a"*24,period="all"))
 row=result["rows"][0]
 assert row["actions"]["planned"]==1
 assert row["actions"]["total"]==0
 assert row["action_branches"]==[]
 assert row["topology"]["branches_materialized"] is False
 assert row["topology"]["branch_count"]==0
