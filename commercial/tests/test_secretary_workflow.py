import copy
from contextlib import contextmanager
from datetime import datetime,timedelta,timezone
import pytest
from commercial import secretary_workflow as f
from commercial.agent_workspace import RevisionConflict

S={'tenant_id':'tenant','source_id':'source','external_user_id':'s'*32,'role':'User','license':{'modules':{2}},'directory':{'s'*32:{'active':True,'name':'دبیر'},'c'*32:{'active':True,'name':'رئیس'}}}
V={'MTG_MeetingNo':'100','MTG_MeetingTitle':'بررسی واردات','MTG_Location':'دفتر','MTG_MeetingStartDateTime':'1405/07/10','MTG_MeetingStartTime':'10:00','MTG_SecretaryUserUID':'s'*32,'MTG_ChairUserUID':'c'*32,'MTG_Participants':{'1':{'MTG_ParticipantUserUID':'c'*32}},'MTG_Agenda':{'1':{'MTG_AgendaTitle':'واردات'}}}
@pytest.fixture
def store(monkeypatch):
 data={}
 class Tx:
  def get(self,k,default=None,**kw):return copy.deepcopy(data.get(k,default))
  def put(self,k,v):data[k]=copy.deepcopy(v)
  def audit(self,*args):pass
 @contextmanager
 def transaction():yield Tx()
 monkeypatch.setattr(f.agent_storage,'transaction',transaction)
 return data
class PM:
 def __init__(self,task=f.PLAN):self.task=task;self.calls=[];self.vars=copy.deepcopy(V);self.status='TO_DO'
 def new(self,p,v):self.calls.append('new');return 'a'*32
 def submit(self,c,t,p,v):self.calls.append(('submit',t));self.task=f.INVITE if t==f.PLAN else f.APPROVE
 def info(self,c):return {'app_status':self.status,'current_task':[{'tas_uid':self.task}]}
 def variables(self,c):return self.vars
 def assigned(self,*a):return 1
 def call(self,*a):self.calls.append(a);return {}

def ready():
 w=f.create(S,'actor');return f.update(S,'actor',w['id'],w['revision'],copy.deepcopy(V))

def test_contract_and_missing():
 assert f.PLAN=='4a6419a60141d7d36001ba9344db4eac'
 assert f.MINUTES=='a07e9ed93a4b3244aca40996c45eb227'
 assert len(f.missing({},'invitation'))==9
 assert not f.missing(V,'invitation')
 assert f.missing({'MTG_MeetingHeld':'NotHeld'},'minutes')[0]['field']=='MTG_NotHeldReason'

def test_refuses_invented_identity_or_approval():
 with pytest.raises(ValueError):f.validate({**V,'MTG_ChairUserUID':'unknown'},'invitation',S['directory'])
 with pytest.raises(ValueError):f.validate({'MTG_MinutesApproval':'Approved'},'minutes',S['directory'])
 with pytest.raises(ValueError):f.validate({**V,'MTG_MeetingStartTime':'26:01'},'invitation',S['directory'])

def test_revision_and_source_isolation(store):
 w=ready()
 with pytest.raises(RevisionConflict):f.update(S,'actor',w['id'],1,V)
 with pytest.raises(PermissionError):f.load({**S,'source_id':'other'},'actor',w['id'])
 with pytest.raises(PermissionError):f.load(S,'other',w['id'])

def test_send_waits_for_native_chair_and_rejects_duplicate(store):
 w=ready();pm=PM();sent=f.submit(S,'actor',w['id'],w['revision'],pm=pm)
 assert sent['status']=='awaiting_invitation_approval'
 with pytest.raises(RevisionConflict):f.submit(S,'actor',w['id'],sent['revision'],pm=pm)
 assert pm.calls.count('new')==1
 poll=f.refresh(S,'actor',w['id'],pm=pm)
 assert poll['stage']=='invitation' and poll['status']=='awaiting_invitation_approval'
 pm.task=f.MINUTES
 poll=f.refresh(S,'actor',w['id'],pm=pm)
 assert poll['stage']=='minutes' and poll['status']=='collecting'

def test_timeout_is_never_blindly_replayed(store):
 w=ready();pm=PM()
 def fail(*a):raise TimeoutError()
 pm.submit=fail
 with pytest.raises(TimeoutError):f.submit(S,'actor',w['id'],w['revision'],pm=pm)
 row=f.load(S,'actor',w['id']);assert row['status']=='reconciliation_required'
 poll=f.refresh(S,'actor',w['id'],pm=pm);assert poll['status']=='reconciliation_required'
 with pytest.raises(RevisionConflict):f.submit(S,'actor',w['id'],poll['revision'],pm=pm)
 assert pm.calls.count('new')==1

def test_monitoring_exactly_one_day_before_planned_end(store):
 w=ready();pm=PM();f.submit(S,'actor',w['id'],w['revision'],pm=pm)
 pm.task=f.MONITOR;pm.vars.update(MTG_MeetingEndDateTime='1405/07/15',MTG_PlannedActionEndTime='16:30',MTG_OpenActionCount='2',MTG_ActionSummary='دو اقدام باز')
 due=f.jalali_instant('1405/07/15','16:30')-timedelta(days=1)
 early=f.refresh(S,'actor',w['id'],pm=pm,now=due-timedelta(seconds=1))
 assert early['status']=='actions_in_progress'
 assert not any(isinstance(x,tuple) and 'execute-trigger' in str(x) for x in pm.calls)
 due_row=f.refresh(S,'actor',w['id'],pm=pm,now=due)
 assert due_row['stage']=='monitoring' and due_row['status']=='monitoring_ready'
 assert 'دو اقدام باز' in due_row['values']['MTG_ClosingNote']
 result=f.submit(S,'actor',w['id'],due_row['revision'],pm=pm)
 assert result['status']=='submitted_for_closure'
 assert ('submit',f.MONITOR) in pm.calls

def test_grid_labels_preserve_uids():
 x=f.labelled(V,'invitation',S['directory'])
 assert x['MTG_ChairUserUID_label']=='رئیس'
 assert x['MTG_Participants']['1']['MTG_ParticipantUserUID_label']=='رئیس'
 assert x['MTG_ChairUserUID']=='c'*32

def test_rest_transport_checks_assignment_and_runs_pmx_after_before_route(monkeypatch):
 from commercial.secretary_processmaker import PM,AFTER
 pm=object.__new__(PM);calls=[]
 def call(method,path,data=None):
  calls.append((method,path,data))
  if method=='GET':return {'pro_uid':f.CONTRACT['process_uid'],'current_task':[{'tas_uid':f.MINUTES,'usr_uid':'s'*32,'del_thread_status':'OPEN','del_index':3}]}
  return {}
 pm.call=call
 pm.submit('a'*32,f.MINUTES,'s'*32,{'MTG_MeetingHeld':'Held'})
 assert calls[1][1].endswith('/variable?del_index=3')
 assert calls[2][1].endswith('/execute-trigger/'+AFTER[f.MINUTES])
 assert calls[3][1].endswith('/route-case') and calls[3][2]=={'del_index':3}
 calls.clear()
 with pytest.raises(ValueError):pm.submit('a'*32,f.MINUTES,'c'*32,{})
 assert len(calls)==1

def test_minutes_requires_owner_deadline_and_real_decision():
 values={'MTG_MeetingHeld':'Held','MTG_MeetingDiscussionSummary':'مذاکرات','MTG_MeetingEndDateTime':'1405/07/15','MTG_PlannedActionEndTime':'16:30','MTG_Actions':{'1':{'MTG_ActionNo':'A-001','MTG_ActionDescription':'بررسی مدارک','MTG_ActionDecisionNo':'D-001'}}}
 gaps=f.missing(values,'minutes')
 assert any('MTG_ActionOwnerUID' in x['field'] for x in gaps)
 assert any('decision' in x['field'] for x in gaps)



def test_structured_response_text_falls_back_to_output_content_without_output_text():
 class Part:
  type='output_text'
  text='{"assignments":[],"questions":["تاریخ جلسه؟"]}'
 class Item:
  content=[Part()]
 class Result:
  output=[Item()]
 assert f.response_text(Result())=='{"assignments":[],"questions":["تاریخ جلسه؟"]}'


def test_structured_model_helpers_support_current_pydantic_api():
 schema=f.model_schema(f.Extraction)
 assert schema['type']=='object'
 parsed=f.validate_model_json(f.Extraction,'{"assignments":[],"questions":[]}')
 assert parsed.assignments==[] and parsed.questions==[]
