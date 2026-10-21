"""Seven-stage contract through real runtime + REST adapter with simulated PM HTTP.
This verifies AVAN request ordering, not execution of PHP triggers on a PM server.
"""
import copy
import httpx
import pytest
from commercial import secretary_runtime as runtime
from commercial.secretary_processmaker import PM
from commercial.tests.test_secretary_inbox import pack,store,task
from commercial.tests.test_secretary_workflow import S,V


def payload(stage):
 if stage=='invitation':
  values=copy.deepcopy(V)
  values['MTG_Agenda']['1'].update(MTG_AgendaPresenterUID='c'*32,MTG_AgendaPlannedMinutes='20')
  return values
 if stage=='invitation_approval':return {'MTG_InvitationApproval':'Approved'}
 if stage=='minutes':return {
  'MTG_MeetingHeld':'Held','MTG_MeetingDiscussionSummary':'گزارش بررسی شد',
  'MTG_Participants':{'1':{'MTG_ParticipantUserUID':'c'*32,'MTG_AttendanceStatus':'Present','MTG_AttendanceTime':'10:00'}},
  'MTG_Decisions':{'1':{'MTG_DecisionNo':'D-001','MTG_DecisionText':'پیگیری شود'}},
  'MTG_Actions':{'1':{'MTG_ActionDecisionNo':'D-001','MTG_ActionNo':'A-001','MTG_ActionDescription':'پیگیری',
                       'MTG_ActionOwnerUID':'c'*32,'MTG_persiandate_ActionDueDateTime':'1405/07/20'}}
 }
 if stage=='minutes_approval':return {'MTG_MinutesApproval':'Approved'}
 if stage=='action_execution':return {'MTGA_SubmissionType':'CompletionClaim','MTGA_ProgressPercent':'70','MTGA_ExecutionDescription':'گزارش انجام کار','MTGA_ActualEffortMinutes':'60','MTGA_ActualCompletionDateTime':'1405/07/10','MTGA_ActualCompletionTime':'11:00'}
 if stage=='action_review':return {'MTGA_ReviewStatus2':'Closed','MTGA_SecretaryProgressPercent2':'100','MTGA_SecretaryActualEffortMinutes2':'60','MTGA_SecretaryActualCompletionDateTime2':'1405/07/10','MTGA_SecretaryActualCompletionTime2':'11:00'}
 return {'MTG_ClosingNote':'اقدامات بررسی شد','MTG_ActionSummary':{}}


@pytest.mark.parametrize('stage',list(runtime.STAGE_LABELS))
def test_each_stage_writes_then_runs_exact_after_triggers_then_routes(stage,pack,store):
 native={**copy.deepcopy(V),'MTG_LockedPlan':copy.deepcopy(V)}
 if stage not in ('invitation','invitation_approval'):native.update(payload('minutes'))
 t=task(pack,stage,native)
 row=runtime.draft(S,'actor',t)
 row=runtime.update(S,'actor',t,row['revision'],{**row['values'],**payload(stage)})
 calls=[]
 def transport(request):
  path=request.url.path;calls.append((request.method,path))
  if request.method=='GET' and path.endswith('/variables'):
   return httpx.Response(200,json=native)
  if request.method=='GET':
   return httpx.Response(200,json={'pro_uid':runtime.process_for(pack,stage),'current_task':[{'tas_uid':pack['stages'][stage]['task_uid'],'usr_uid':S['external_user_id'],'del_thread_status':'OPEN','del_index':1}]})
  return httpx.Response(200,json={})
 pm=PM.__new__(PM);pm.base='https://pm.test/api/1.0/workflow';pm.process_uid=runtime.process_for(pack,stage)
 pm.client=httpx.Client(transport=httpx.MockTransport(transport))
 try:
  assert runtime.submit(S,'actor',t,row['revision'],pm=pm)['status']=='sent'
 finally:pm.close()
 writes=[path for method,path in calls if method=='PUT']
 base='/api/1.0/workflow/cases/'+t['case_uid']
 assert writes==[base+'/variable']+[base+'/execute-trigger/'+uid for uid in pack['stages'][stage]['after']]+[base+'/route-case']
 if stage=='action_execution':assert row['values']['MTGA_ProgressPercent']=='100'


def test_not_held_requires_reason_and_does_not_invent_minutes(pack):
 t=task(pack,'minutes',V)
 assert runtime.gaps({'MTG_MeetingHeld':'NotHeld'},t)
 assert not runtime.gaps({'MTG_MeetingHeld':'NotHeld','MTG_NotHeldReason':'عدم حضور رئیس'},t)


def test_action_return_requires_secretary_comment(pack):
 t=task(pack,'action_review')
 values={'MTGA_ReviewStatus2':'Rework','MTGA_SecretaryProgressPercent2':'50','MTGA_SecretaryActualEffortMinutes2':'30'}
 assert any(x['field']=='MTGA_SecretaryComment1' for x in runtime.gaps(values,t))
 values['MTGA_SecretaryComment1']='مدرک تکمیل لازم است'
 assert not runtime.gaps(values,t)


@pytest.mark.parametrize('status',[200,206])
def test_native_document_download_accepts_pm_success_statuses(pack,monkeypatch,status):
 from commercial import secretary_evidence as e
 from types import SimpleNamespace
 doc={'app_doc_uid':'d'*32,'app_doc_version':'1','app_doc_filename':'evidence.txt'}
 monkeypatch.setattr(e,'native_documents',lambda *args:[doc])
 monkeypatch.setattr(e,'token',lambda *args:'personal-token')
 client=httpx.Client(transport=httpx.MockTransport(lambda request:httpx.Response(status,content='گزارش انجام کار'.encode())))
 pm=SimpleNamespace(client=client,base='https://pm.test/api/1.0/workflow',assigned=lambda *args:1,close=client.close)
 monkeypatch.setattr(e,'PM',lambda *args,**kwargs:pm)
 result=e.read_native(task(pack,'action_review'),S,'actor','d'*32,1)
 assert result['text']=='گزارش انجام کار'



def test_new_case_posts_reviewed_invitation_values_immediately():
 captured={}
 def transport(request):
  captured['method']=request.method;captured['path']=request.url.path
  captured['json']=__import__('json').loads(request.content.decode())
  return httpx.Response(200,json={'app_uid':'a'*32,'app_number':718})
 pm=PM.__new__(PM);pm.base='https://pm.test/api/1.0/workflow';pm.process_uid='p'*32
 pm.client=httpx.Client(transport=httpx.MockTransport(transport))
 try:
  uid=pm.create_for('t'*32,{'MTG_MeetingTitle':'جلسه تست','MTG_Location':'طبقه ۴'})
 finally:pm.close()
 assert uid=='a'*32
 assert captured['method']=='POST' and captured['path'].endswith('/cases')
 assert captured['json']['variables'][0]['MTG_MeetingTitle']=='جلسه تست'
 assert captured['json']['variables'][0]['MTG_Location']=='طبقه ۴'


def test_processmaker_rejection_names_exact_failed_operation():
 from fastapi import HTTPException
 def transport(request):
  return httpx.Response(403,json={'error':{'code':403,'message':'Not authorized'}})
 pm=PM.__new__(PM);pm.base='https://pm.test/api/1.0/workflow';pm.process_uid='p'*32
 pm.client=httpx.Client(transport=httpx.MockTransport(transport))
 try:
  with pytest.raises(HTTPException) as exc:
   pm.call('PUT','/cases/'+'a'*32+'/execute-trigger/'+'b'*32,operation='اجرای Trigger قبل از فرم')
 finally:pm.close()
 assert 'اجرای Trigger قبل از فرم' in exc.value.detail
 assert 'HTTP 403' in exc.value.detail



def test_route_case_serializes_del_index_as_string_for_processmaker_33():
 captured={}
 def transport(request):
  captured['method']=request.method
  captured['path']=request.url.path
  captured['json']=__import__('json').loads(request.content.decode())
  return httpx.Response(200,json={})
 pm=PM.__new__(PM);pm.base='https://pm.test/api/1.0/workflow';pm.process_uid='p'*32
 pm.client=httpx.Client(transport=httpx.MockTransport(transport))
 try:
  pm.route('a'*32,1)
 finally:pm.close()
 assert captured['method']=='PUT'
 assert captured['path'].endswith('/route-case')
 assert captured['json']=={'del_index':'1'}


