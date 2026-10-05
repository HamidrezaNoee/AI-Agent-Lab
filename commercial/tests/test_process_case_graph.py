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
