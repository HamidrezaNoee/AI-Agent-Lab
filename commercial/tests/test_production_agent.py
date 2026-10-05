"""Agent acceptance tests: no production data, external calls or SQL writes."""
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime,timezone,timedelta,date
import json
from types import SimpleNamespace as NS
from unittest.mock import patch,Mock
import pytest
from fastapi.testclient import TestClient
from commercial.agent_tools import MeetingTools,ActionQuery,MeetingQuery,MonitorQuery,period_bounds
from commercial.meeting_agent import run_agent,AgentInvalid,AgentUnavailable,AgentBusy,run_slot
from commercial.secretary_agent import extract_draft
from commercial import agent_state,setup_console as setup
from commercial import production_app as web,agent_routes,agent_storage
from commercial.security import Principal
from uuid import UUID

NOW=datetime(2026,9,22,9,tzinfo=timezone.utc)
SCOPE={'tenant_id':'11111111-1111-1111-1111-111111111111','source_id':'a'*24,'external_user_id':'p1','role':'Expert','company':'org','visible_uids':{'p1'},'license':{'modules':[1,2,3,4]}}

def records():
    def action(identifier,owner,closed=False,progress=30,due='2026-09-01T00:00:00+00:00'):
        return {'action_id':identifier,'action_no':f'A-{identifier}','description':'پیگیری ترخیص خودرو',
                'owner_uid':owner,'owner_name':'علی','owner_unit':'لجستیک','is_closed':closed,
                'progress_percent':progress,'due_at_utc':due,'status':'Closed' if closed else 'Completed',
                'created_at_utc':'2026-09-01T00:00:00+00:00','submission_history_available':True,
                'last_submission_at_utc':None}
    return [{'meeting_id':1,'meeting_no':'۱۴۰۵/۱','title':'ترخیص خودرو','discussion':'مانع مجوز ترخیص مطرح شد',
             'parking_lot':'بررسی قرارداد','secretary_uid':'p1','meeting_date_utc':'2026-09-10T10:00:00+00:00',
             'actions':[action(1,'p1',progress=100),action(2,'p2',True,100),action(3,'p1',progress=None,due=None)]},
            {'meeting_id':2,'meeting_no':'1405/2','title':'ترخیص خودرو','discussion':'پیگیری مشکل مجوز',
             'parking_lot':None,'secretary_uid':'p1','meeting_date_utc':'2026-09-20T10:00:00+00:00',
             'actions':[action(4,'p2',due='2026-09-24T00:00:00+00:00')]}]


def test_totals_use_full_set_even_when_paginated_and_closure_not_progress():
    tools=MeetingTools(records(),now=NOW)
    r=tools.execute('analyze_actions',{'limit':1})
    assert r['metrics']['total']==4 and r['metrics']['closed']==1
    assert r['metrics']['open']==3 and r['metrics']['overdue']==1
    assert r['metrics']['missing_progress']==1 and r['metrics']['missing_due']==1
    assert r['metrics']['average_progress']==76.7 and r['has_more']
    assert len(r['rows'])==1


def test_owner_uid_distinguishes_identical_names_and_filters_normalize_persian_digits():
    tools=MeetingTools(records(),now=NOW)
    r=tools.actions(ActionQuery(group_by='owner'))
    assert len(r['groups'])==2
    assert tools.actions(ActionQuery(meeting_no='1405/1'))['metrics']['total']==3
    assert tools.search(MeetingQuery(meeting_no='1'))['total']==0
    assert tools.search(MeetingQuery(text='مجوز'))['total']==2


def test_date_windows_missing_values_and_selected_calendar_month_boundaries():
    tools=MeetingTools(records(),now=NOW)
    assert tools.actions(ActionQuery(status='due_soon'))['metrics']['total']==1
    r=tools.actions(ActionQuery(start='2026-09-20T00:00:00Z',end='2026-09-21T00:00:00Z'))
    assert r['metrics']['total']==1
    assert tools.actions(ActionQuery(date_field='due',period='last_30_days'))['excluded_missing_date']==1
    now=datetime(2026,3,25,tzinfo=timezone.utc)
    import jdatetime
    from zoneinfo import ZoneInfo
    tehran=ZoneInfo('Asia/Tehran')
    with patch('commercial.agent_tools.calendar_mode',return_value='jalali'):
        start,end=period_bounds('last_month',now)
    assert jdatetime.date.fromgregorian(date=start.astimezone(tehran).date()).month==12
    assert start<end<now
    with patch('commercial.agent_tools.calendar_mode',return_value='gregorian'):
        gstart,gend=period_bounds('last_month',now)
    assert gstart.astimezone(tehran).date()==date(2026,2,1)
    assert gend.astimezone(tehran).date()==date(2026,3,1)
    assert gstart<gend<now


@pytest.mark.parametrize('args',[{'sql':'SELECT *'},{'tenant_id':'x'},{'limit':99},{'offset':-1},{'group_by':'password'}])
def test_tool_arguments_reject_arbitrary_queries(args):
    with pytest.raises(ValueError):MeetingTools(records()).execute('analyze_actions',args)


def test_missing_or_invalid_dates_do_not_default_to_full_data():
    with pytest.raises(ValueError):MeetingTools(records()).execute('analyze_actions',{'start':'nonsense'})
    with pytest.raises(ValueError):MeetingTools(records()).execute('analyze_actions',{'start':'2026-09-01'})


def test_tools_fail_closed_for_unlicensed_and_unknown_operations():
    t=MeetingTools(records(),modules=[1])
    assert [x['name'] for x in t.definitions()]==['search_meetings']
    with pytest.raises(PermissionError):t.execute('monitor_actions',{})
    with pytest.raises(ValueError):t.execute('write_processmaker',{})


def test_monitor_excludes_closed_and_covers_real_reporting_age():
    r=MeetingTools(records(),now=NOW).monitor(MonitorQuery())
    kinds={a['kind'] for a in r['alerts']}
    assert {'overdue','due_soon','missing_due','awaiting_closure','no_recent_report','recurring_open_topic'}<=kinds
    assert all(a['source']['action_no']!='A-2' for a in r['alerts'])
    young=records();young[0]['actions'][0]['created_at_utc']=NOW.isoformat()
    r=MeetingTools(young,now=NOW).monitor(MonitorQuery())
    assert not any(a['kind']=='no_recent_report' and a['source']['action_no']=='A-1' for a in r['alerts'])


def test_stalled_unknown_progress_not_claimed_and_partial_coverage_exposed():
    obs={'M:1:A:1':{'changed_at':'2026-09-01T00:00:00Z'},'M:1:A:3':{'changed_at':'2026-09-01T00:00:00Z'}}
    t=MeetingTools(records(),now=NOW,complete=False,observations=obs)
    result=t.execute('monitor_actions',{})
    stalls=[a for a in result['alerts'] if a['kind']=='stalled_progress']
    assert len(stalls)==1 and stalls[0]['source']['action_no']=='A-1'
    assert not result['coverage_complete']


def response(*,call=None,answer=None):
    output=[NS(type='function_call',name=call[0],arguments=json.dumps(call[1]),call_id='call-1')] if call else []
    return NS(output=output,output_text=json.dumps(answer),status='completed',usage=NS(input_tokens=50,output_tokens=20))


def fake_client(outputs):
    return NS(responses=NS(create=Mock(side_effect=outputs)))


def final(ref='T:1'):
    return {'claims':[{'text':'یک اقدام عقب افتاده است.','kind':'fact','sources':[ref]}],
            'clarification':None,'limitations':[]}


def test_real_tool_loop_and_source_validation_with_sdk_wire_shape():
    client=fake_client([response(call=('analyze_actions',{'status':'overdue'})),response(answer=final())])
    answer=run_agent('کدام اقدامات عقب افتاده هستند؟',MeetingTools(records(),now=NOW),client=client,model='test')
    assert answer['model_used'] and answer['evidence'][0]['result']['metrics']['total']==1
    assert answer['usage']['input_tokens']==100
    assert client.responses.create.call_args_list[0].kwargs['store'] is False
    assert any(isinstance(x,dict) and x.get('type')=='function_call_output' for x in client.responses.create.call_args.kwargs['input'])


@pytest.mark.parametrize('outputs',[
    [response(answer=final())],
    [response(call=('analyze_actions',{})),response(answer=final('M:999'))],
    [response(call=('write_sql',{})),response(answer=final())],
])
def test_agent_rejects_ungrounded_answers(outputs):
    with pytest.raises(AgentInvalid):run_agent('سؤال تحلیلی',MeetingTools(records()),client=fake_client(outputs),model='test')


def test_excessive_tool_turns_are_bounded():
    client=fake_client([response(call=('search_meetings',{}))]*8)
    with pytest.raises(AgentInvalid):run_agent('جلسات را بررسی کن',MeetingTools(records()),client=client,model='test')
    assert client.responses.create.call_count==7


def test_agent_connection_error_never_becomes_fabricated_answer():
    with pytest.raises(AgentUnavailable):run_agent('سؤال تحلیلی',MeetingTools(records()),client=fake_client([RuntimeError('secret')]),model='test')


def test_concurrent_run_per_identity_rejected():
    with run_slot('test-unique'):
        with pytest.raises(AgentBusy):
            with run_slot('test-unique'):pass


def draft_data():
    return {'summary':'پیگیری مجوز','actions':[{'description':'پیگیری مجوز ترخیص','source_quote':'مجوز را پیگیری کند',
        'owner_uid':'p1','suggested_role':'دبیر','owner_reason':'مسئول مرتبط','priority':'high',
        'proposed_due_date':'2026-09-25','due_reason':'موعد پیشنهادی','needs_clarification':True}], 'questions':[]}


def test_secretary_extracts_evidence_and_rejects_fabricated_quote_or_owner():
    data=draft_data()
    def run(data):return extract_draft('مصوب شد مجوز را پیگیری کند',records()[0],[{'uid':'p1','name':'علی'}],
        today=NOW.date(),client=fake_client([response(answer=data)]),model='test')
    assert run(data)['registration_status']=='not_registered'
    data['actions'][0]['owner_uid']='outside'
    with pytest.raises(AgentInvalid):run(data)
    data=draft_data();data['actions'][0]['source_quote']='not in notes'
    with pytest.raises(AgentInvalid):run(data)


@pytest.fixture
def state_dir(tmp_path,monkeypatch):
    for name,value in {'ROOT':tmp_path,'SQLITE':tmp_path/'setup.sqlite3','KEYFILE':tmp_path/'setup.key','INITIAL':tmp_path/'initial','PUBLIC':tmp_path/'pub'}.items():
        monkeypatch.setattr(setup,name,value)
    setup.initialize()
    memory={'payloads':{},'audits':[]}
    class Tx:
        def get(self,name,default=None,lock=False):
            return setup._unseal('agent:'+name,memory['payloads'][name]) if name in memory['payloads'] else deepcopy(default)
        def put(self,name,value):memory['payloads'][name]=setup._seal('agent:'+name,value)
        def audit(self,tenant,actor,event,detail):memory['audits'].append({'tenant':tenant,'actor':actor,'event':event,'detail':detail})
    @contextmanager
    def transaction():
        backup=deepcopy(memory)
        try:yield Tx()
        except Exception:memory.clear();memory.update(backup);raise
    monkeypatch.setattr(agent_storage,'transaction',transaction)
    return memory


def test_draft_and_monitor_encrypted_actor_tenant_bound_idempotent_approval(state_dir):
    payload={'summary':'private-notes-marker'}
    key=agent_state.save_draft(SCOPE,'actor',1,payload)
    assert all(b'private-notes-marker' not in v for v in state_dir['payloads'].values())
    for scope,actor,ids in [(SCOPE,'other',{1}),({**SCOPE,'tenant_id':'other'},'actor',{1}),(SCOPE,'actor',{2})]:
        with pytest.raises(PermissionError):agent_state.get_draft(scope,actor,key,ids)
    a=agent_state.approve_draft(SCOPE,'actor',key,{1})
    b=agent_state.approve_draft(SCOPE,'actor',key,{1})
    assert a['approved_at']==b['approved_at']
    assert sum(r['event']=='SECRETARY_DRAFT_APPROVED' for r in state_dir['audits'])==1
    first=agent_state.observe(SCOPE,'actor',records(),NOW,True)
    later=agent_state.observe(SCOPE,'actor',records(),NOW+timedelta(days=8),True)
    assert later['M:1:A:1']['changed_at']==first['M:1:A:1']['changed_at']
    changed=records();changed[0]['actions'][0]['progress_percent']=50
    updated=agent_state.observe(SCOPE,'actor',changed,NOW+timedelta(days=9),True)
    assert updated['M:1:A:1']['changed_at']!=first['M:1:A:1']['changed_at']


def test_global_calendar_setting_defaults_jalali_and_can_switch(state_dir):
    assert setup.get_setting('ui')=={'calendar':'jalali'}
    setup.put_setting('ui',{'calendar':'gregorian'})
    assert web.ui_config()=={'calendar':'gregorian'}


def test_ai_settings_masking_and_no_environment_fallback(state_dir):
    setup.put_setting('ai',{'api_key':'a-secret-value-123456789','enabled':True,'model':'gpt-4.1-mini'})
    assert setup.masked_settings()['ai']['api_key']=='********'
    assert b'a-secret-value-123456789' not in setup.SQLITE.read_bytes()
    setup.put_setting('ai',{'enabled':False})
    from commercial.meeting_agent import configured_client
    with pytest.raises(AgentUnavailable):configured_client()


def test_routes_require_auth_and_csrf_without_model_calls():
    client=TestClient(web.app,base_url='http://127.0.0.1:8188')
    for path,body in [('/api/ask',{'question':'وضعیت جلسات چیست؟'}),('/api/secretary/drafts',{'meeting_no':'1','notes':'متن جلسه برای استخراج'}),('/api/monitor',None)]:
        assert client.post(path,json=body).status_code==401
    assert client.get('/api/agent/status').status_code==401


def test_final_scope_revocation_blocks_reply():
    principal=NS()
    with patch.object(agent_routes,'snapshot',return_value=(SCOPE,[],True)):
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as error:agent_routes.ensure_still_authorized(principal,SCOPE,records(),1)
        assert error.value.status_code==403


def test_responses_transport_serializes_schema_and_tools_without_live_api():
    import httpx
    from openai import OpenAI
    requests=[]
    def transport(request):
        body=json.loads(request.content);requests.append(body)
        if len(requests)==1:
            output=[{'type':'function_call','id':'fc1','call_id':'c1','name':'analyze_actions','arguments':'{"status":"overdue"}','status':'completed'}]
        else:
            output=[{'type':'message','id':'msg1','role':'assistant','status':'completed',
                'content':[{'type':'output_text','text':json.dumps(final()),'annotations':[]}]}]
        return httpx.Response(200,json={'id':'resp_test','object':'response','created_at':1,'model':'gpt-4.1-mini','status':'completed',
            'output':output,'usage':{'input_tokens':50,'output_tokens':20,'total_tokens':70}})
    with OpenAI(api_key='test-not-a-real-key',http_client=httpx.Client(transport=httpx.MockTransport(transport))) as client:
        answer=run_agent('کدام اقدام عقب افتاده است؟',MeetingTools(records(),now=NOW),client=client,model='gpt-4.1-mini')
    assert answer['claims'] and len(requests)==2
    assert requests[0]['tools'][0]['type']=='function'
    assert requests[0]['text']['format']['strict'] is True


def test_ask_endpoint_uses_tool_agent_and_audits_without_writing_mtg(state_dir):
    principal=Principal(UUID(SCOPE['tenant_id']),'api-actor')
    session={'access_token':'server-session-token','expires':9999999999}
    client_model=fake_client([response(call=('analyze_actions',{'group_by':'unit'})),response(answer=final())])
    web.app.dependency_overrides[web._csrf]=lambda:('s',session,principal)
    try:
        with patch.object(agent_routes,'snapshot',return_value=(SCOPE,records(),True)), \
             patch('commercial.meeting_agent.configured_client',return_value=(client_model,'test')), \
             patch.object(web,'_oidc_config',return_value=(None,None,None,None,NS(authenticate=lambda token:principal))):
            client_model.close=Mock()
            with TestClient(web.app,base_url='http://127.0.0.1:8188') as client:
                result=client.post('/api/ask',json={'question':'عملکرد واحدها چگونه است؟'})
        assert result.status_code==200,result.text
        assert result.json()['model_used'] is True
        assert session['agent_questions']==['عملکرد واحدها چگونه است؟']
        assert sum(r['event']=='AGENT_COMPLETED' for r in state_dir['audits'])==1
    finally:web.app.dependency_overrides.clear()


def test_draft_export_requires_review_and_current_owner_scope(state_dir):
    principal=Principal(UUID(SCOPE['tenant_id']),'draft-actor')
    session={'expires':9999999999}
    identifier=agent_state.save_draft(SCOPE,principal.subject,1,draft_data())
    web.app.dependency_overrides[web._authorized]=lambda:('s',session,principal)
    web.app.dependency_overrides[web._csrf]=lambda:('s',session,principal)
    try:
        with patch.object(agent_routes,'snapshot',return_value=(SCOPE,records(),True)):
            with TestClient(web.app,base_url='http://127.0.0.1:8188') as client:
                assert client.get(f'/api/secretary/drafts/{identifier}/export').status_code==409
                assert client.post(f'/api/secretary/drafts/{identifier}/approve',json={'confirmed':False}).status_code==422
                approved=client.post(f'/api/secretary/drafts/{identifier}/approve',json={'confirmed':True})
                assert approved.status_code==200 and approved.json()['processmaker_written'] is False
                exported=client.get(f'/api/secretary/drafts/{identifier}/export')
                assert exported.status_code==200
                assert exported.json()['requires_processmaker_field_mapping'] is True
        with patch.object(agent_routes,'snapshot',return_value=(SCOPE,[],True)):
            assert client.get(f'/api/secretary/drafts/{identifier}').status_code==404
    finally:web.app.dependency_overrides.clear()


def test_module_gate_runs_before_snapshot_query():
    from commercial.production_store import ProductionAccessDenied
    def store(fn,principal):return fn(object(),{**SCOPE,'license':{'modules':[1]}})
    with patch.object(web,'_store_response',side_effect=store), patch('commercial.production_store.authorized_meeting_snapshot') as read:
        with pytest.raises(ProductionAccessDenied):agent_routes.snapshot(NS(),2)
        read.assert_not_called()


def test_monitor_unit_growth_requires_full_coverage_and_comparison():
    rows=records();rows[1]['actions']+=deepcopy(rows[0]['actions'][:1])*4
    baseline={'__backlog':{'complete':True,'counts':{'لجستیک':2},'at':'2026-09-21T00:00:00Z'}}
    result=MeetingTools(rows,now=NOW,observations=baseline).monitor(MonitorQuery())
    assert any(a['kind']=='backlog_growth' for a in result['alerts'])
    result=MeetingTools(rows,now=NOW,observations=baseline,complete=False).monitor(MonitorQuery())
    assert not any(a['kind']=='backlog_growth' for a in result['alerts'])


def test_agent_snapshot_reads_exact_selected_bpms_source():
    selected="b"*24
    principal=Principal(UUID(SCOPE["tenant_id"]),"source-user")
    scoped={**SCOPE,"source_id":selected,"external_user_id":"external-b"}
    def source_store(source_id,action,received_principal):
        assert source_id==selected
        assert received_principal is principal
        return action(object(),scoped)
    with patch.object(web,"_source_store_response",side_effect=source_store) as routed, \
         patch("commercial.production_store.authorized_meeting_snapshot",
               return_value=([],True)):
        scope,rows,complete=agent_routes.snapshot(principal,1,source_id=selected)
    assert routed.call_count==1
    assert scope["source_id"]==selected
    assert scope["external_user_id"]=="external-b"
    assert rows==[] and complete is True
