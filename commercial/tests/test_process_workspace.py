"""Adapter, process and current-assignment scope tests without live services."""
import copy
from dataclasses import replace
import pytest,phpserialize
from commercial import process_workspace as w,secretary_runtime as r,secretary_catalog as c
from commercial.tests.test_secretary_inbox import pack,store,task
from commercial.tests.test_secretary_workflow import S,V

@pytest.fixture(autouse=True)
def registry(monkeypatch):monkeypatch.setattr(w,'_ADAPTERS',dict(w._ADAPTERS))

def rows(pack,stage='invitation_approval'):
 return [('a'*32,100,pack['meeting']['process_uid'],phpserialize.dumps(V),1,pack['stages'][stage]['task_uid'])]

def test_selected_process_filters_native_sql_and_drafts(pack,store,monkeypatch):
 p2=copy.deepcopy(pack);p2.update(id='2'*24);p2['meeting']['process_uid']='b'*32;p2['action']['process_uid']='c'*32;store[c.STORE].append(p2)
 requests=[]
 def query(con,sql,args):requests.append(args);return rows(pack)
 monkeypatch.setattr(r,'query',query)
 r.session_create(S,'actor',pack['id']);r.session_create(S,'actor',p2['id'])
 result=w.workspace(None,S,'actor',pack['id'],'drafts')
 assert all(d['pack_id']==pack['id'] for d in result['sessions'])
 assert len(requests[0])==6 and pack['meeting']['process_uid'] in requests[0] and p2['meeting']['process_uid'] not in requests[0]
 assert result['tasks']==[]

def test_role_sections_follow_own_current_tasks(pack,store,monkeypatch):
 monkeypatch.setattr(r,'query',lambda *a:rows(pack,'action_review') if False else [('a'*32,100,pack['action']['process_uid'],phpserialize.dumps({}),1,pack['stages']['action_review']['task_uid'])])
 result=w.workspace(None,S,'actor',pack['id']);ids={x['id'] for x in result['navigation']}
 assert 'reviews' in ids and 'approvals' not in ids and 'execution' not in ids
 with pytest.raises(PermissionError):w.workspace(None,S,'actor',pack['id'],'approvals')

def test_other_source_disabled_pack_missing_license_fail_closed(pack,store):
 with pytest.raises(PermissionError):w.workspace(None,{**S,'source_id':'other'},'actor',pack['id'])
 assert w.processes({**S,'license':{'modules':set()}})['processes']==[]
 store[c.STORE][0]['enabled']=False
 assert w.processes(S)['processes']==[]
 with pytest.raises(PermissionError):w.workspace(None,S,'actor',pack['id'])

def test_unknown_adapter_does_not_appear_or_execute(pack,store):
 store[c.STORE][0]['adapter']='uninstalled'
 assert not w.processes(S)['processes']
 with pytest.raises(PermissionError):w.workspace(None,S,'actor',pack['id'])
 with pytest.raises(PermissionError):r.session_create(S,'actor',pack['id'])

def test_future_adapter_has_distinct_menu_without_mtg_names(pack,store):
 generic={'id':'3'*24,'source_id':'source','enabled':True,'revision':1,'adapter':'purchase_test','purchase':{'process_uid':'d'*32,'title':'خرید'}}
 store[c.STORE].append(generic)
 w.register_adapter(w.Adapter('purchase_test','خرید',frozenset({2}),('purchase',),(w.Section('queue','درخواست‌های خرید'),w.Section('orders','سفارش‌های من',stages=('order',))),
  lambda con,scope,pack_id:{'tasks':[{'case_uid':'e'*32,'index':2,'stage':'order','pack_id':pack_id,'title':'سفارش'}]},lambda *a:[]))
 result=w.workspace(None,S,'actor',generic['id'],'orders')
 assert result['process']['title']=='خرید' and {x['id'] for x in result['navigation']}=={'queue','orders'}
 assert result['tasks'][0]['stage']=='order'
 assert 'MTG_' not in str(result)

def test_native_adapter_reads_only_own_process_tasks(store,monkeypatch):
 scope={**S,'license':{'modules':{1,2}}};p=c.save('source',{'adapter':'native_tasks_v1','process':{'process_uid':'f'*32,'title':'خرید خارجی'}},'admin')
 calls=[]
 from commercial import processmaker_store
 monkeypatch.setattr(processmaker_store,'query',lambda con,sql,args:calls.append((sql,args)) or [('a'*32,12,3,'b'*32,'بررسی خرید')])
 result=w.workspace(None,scope,'actor',p['id'])
 assert result['tasks'][0]['read_only'] and result['process']['renderer']=='generic'
 assert calls[0][1][:2]==('f'*32,S['external_user_id']) and 'd.USR_UID=%s' in calls[0][0]
 with pytest.raises(ValueError):c.save('source',{'adapter':'native_tasks_v1','process':{'process_uid':'f'*32,'title':'تکراری'}},'admin')

def test_partial_pack_poll_preserves_other_pack_notifications(pack,store,monkeypatch):
 p2=copy.deepcopy(pack);p2['id']='2'*24;p2['meeting']['process_uid']='b'*32;p2['action']['process_uid']='c'*32;store[c.STORE].append(p2)
 monkeypatch.setattr(r,'query',lambda con,sql,args:rows(pack) if pack['meeting']['process_uid'] in args else [('b'*32,101,p2['meeting']['process_uid'],phpserialize.dumps(V),2,p2['stages']['invitation_approval']['task_uid'])])
 a=r.inbox(None,S,pack_id=pack['id']);b=r.inbox(None,S,pack_id=p2['id']);r.acknowledge(S,a['notifications'][0]['id'])
 assert r.inbox(None,S,pack_id=pack['id'])['notifications'][0]['read']
 assert len(store[r.source_user_key('secretary_notifications',S,S['external_user_id'])])==2

def test_changed_rest_variables_block_before_any_write(pack,store):
 t=task(pack,'invitation_approval',copy.deepcopy(V));d=r.draft(S,'actor',t);d=r.update(S,'actor',t,d['revision'],{**d['values'],'MTG_InvitationApproval':'Approved'})
 class PM:
  def assigned(self,*a):return 1
  def variables(self,*a):return {**V,'MTG_Location':'محل تغییر یافته'}
  def submit_stage(self,*a):raise AssertionError('must not write')
 from commercial.agent_workspace import RevisionConflict
 with pytest.raises(RevisionConflict):r.submit(S,'actor',t,d['revision'],pm=PM())
 assert r.draft(S,'actor',t)['status']=='draft'

def test_invalidated_person_prevents_remote_case_creation(pack,store):
 row=r.session_create(S,'actor',pack['id'],copy.deepcopy(V));_,t=r.session_load(S,'actor',row['id'])
 v=copy.deepcopy(V);v['MTG_Agenda']['1'].update(MTG_AgendaPresenterUID='c'*32,MTG_AgendaPlannedMinutes='10')
 row=r.session_update(S,'actor',row['id'],row['revision'],v)
 scope=copy.deepcopy(S);scope['directory']['c'*32]['active']=False
 class PM:
  def create_for(self,*a):raise AssertionError('must not create')
 with pytest.raises(ValueError):r.session_send(scope,'actor',row['id'],row['revision'],pm=PM())

def test_rejects_arbitrary_renderer_and_no_default_section():
 a=w._ADAPTERS['native_tasks_v1']
 with pytest.raises(ValueError):w.register_adapter(replace(a,key='malicious',renderer='javascript_from_pmx'))
 with pytest.raises(ValueError):w.register_adapter(replace(a,key='no_default',sections=(w.Section('only','تنها',task_only=True),)))

def test_analytics_without_secretary_license_hides_secretary_data(pack,store,monkeypatch):
 monkeypatch.setattr(r,'inbox',lambda *a,**kw:(_ for _ in ()).throw(AssertionError('secretary tasks unavailable')))
 monkeypatch.setattr(r,'sessions',lambda *a:(_ for _ in ()).throw(AssertionError('secretary drafts unavailable')))
 result=w.workspace(None,{**S,'license':{'modules':{3}}},'actor',pack['id'])
 assert [s['id'] for s in result['navigation']]==['reports'] and not result['tasks'] and not result['sessions']

def test_analytical_selection_changes_sql_scope_and_conversation_stamp(pack,store):
 from commercial import process_context as context
 from commercial.agent_workspace import scope_stamp
 key=context._selected.set(pack['id'])
 try:
  selected=context.scoped(S)
  assert selected['meeting_process_uid']==pack['meeting']['process_uid']
  assert selected['action_process_uid']==pack['action']['process_uid']
  assert scope_stamp(selected)!=scope_stamp(S)
  from commercial.processmaker_store import ProductionAccessDenied
  with pytest.raises(ProductionAccessDenied):context.scoped({**S,'source_id':'other'})
 finally:context._selected.reset(key)
 assert context.scoped(S)==S
 assert context.analytical_path('/api/sources/source/ask') and not context.analytical_path('/api/sources/source/secretary/tasks/open')

def test_selected_meeting_uid_is_used_by_native_parent_query(monkeypatch):
 from commercial import processmaker_store as pm
 calls=[]
 monkeypatch.setattr(pm,'query',lambda con,sql,args:calls.append(args) or [])
 pm.authorized_meetings_page(None,{**S,'visible_uids':{S['external_user_id']},'meeting_process_uid':'d'*32})
 assert calls[0][0]=='d'*32



def test_trusted_meeting_descriptor_matches_reviewed_process_contract():
 trusted=c._trusted_meeting_pack()
 assert trusted['adapter']=='meeting_v2'
 assert trusted['meeting']['process_uid']=='f7f263ea31d8731d212820f220c65a48'
 assert trusted['action']['process_uid']=='cd66870095907431106b6dd110e06fa7'
 assert set(trusted['stages'])=={'invitation','invitation_approval','minutes','minutes_approval','monitoring','action_execution','action_review'}
 assert trusted['stages']['invitation']['task_uid']=='4a6419a60141d7d36001ba9344db4eac'
 assert trusted['stages']['action_execution']['task_uid']=='473bb4e227460a3ea6ac0f2cbf8ef8d4'
 assert 'MTGA_ReviewStatus2' in trusted['stages']['action_review']['fields']


def test_two_installed_native_processes_auto_promote_to_meeting_pack(pack,store,monkeypatch):
 meeting_native={
  'id':'a'*24,'source_id':'source','enabled':True,'revision':1,
  'adapter':'native_tasks_v1',
  'process':{'process_uid':pack['meeting']['process_uid'],'title':'فرایند مدیریت جلسات'},
  'monitor_lead_minutes':1440,'action_lead_minutes':60,'tools':['read_own_tasks'],
 }
 action_native={
  'id':'b'*24,'source_id':'source','enabled':True,'revision':1,
  'adapter':'native_tasks_v1',
  'process':{'process_uid':pack['action']['process_uid'],'title':'فرایند اقدام مصوب جلسه'},
  'monitor_lead_minutes':1440,'action_lead_minutes':60,'tools':['read_own_tasks'],
 }
 store[c.STORE]=[meeting_native,action_native]

 from commercial import user_bpms_bindings,processmaker_store
 from contextlib import contextmanager
 @contextmanager
 def opened(profile):
  yield object()
 monkeypatch.setattr(user_bpms_bindings,'processmaker_profile',lambda source_id:{'mysql':{}})
 monkeypatch.setattr(processmaker_store,'open_production',opened)
 monkeypatch.setattr(c,'_verify_trusted_pack',lambda source_id,pack:True)
 monkeypatch.setattr(
  c,'_installed_process',
  lambda con,uid:copy.deepcopy(pack['meeting'] if uid==pack['meeting']['process_uid'] else pack['action'])
 )

 promoted=c.ensure_installed_meeting_pack('source')
 assert promoted and promoted['adapter']=='meeting_v2'
 assert promoted['id']==meeting_native['id']
 assert len(store[c.STORE])==1
 assert {store[c.STORE][0]['meeting']['process_uid'],store[c.STORE][0]['action']['process_uid']}=={
  pack['meeting']['process_uid'],pack['action']['process_uid']
 }
 result=w.processes(S)
 assert result['processes'][0]['renderer']=='meeting'
 assert result['processes'][0]['title']==pack['meeting']['title']



def test_process_list_stays_selectable_when_meeting_auto_promotion_is_unavailable(store,monkeypatch):
 scope={**S,'license':{'modules':{1,2}}}
 generic=c.save('source',{'adapter':'native_tasks_v1','process':{
  'process_uid':'f'*32,'title':'فرایند عمومی نصب‌شده'}},'admin')
 from commercial.processmaker_store import ProductionUnavailable
 monkeypatch.setattr(
  c,'ensure_installed_meeting_pack',
  lambda source_id:(_ for _ in ()).throw(ProductionUnavailable('schema probe failed'))
 )
 diagnostics={}
 rows=w.configured(scope,diagnostics)
 assert [x['id'] for x in rows]==[generic['id']]
 assert diagnostics['promotion_state']=='unavailable'
 assert diagnostics['promotion_warning']
 assert w.processes(scope)['processes'][0]['title']=='فرایند عمومی نصب‌شده'
