import copy,json
from contextlib import contextmanager
from datetime import timedelta
from pathlib import Path
import pytest,phpserialize
from commercial import secretary_runtime as r,secretary_catalog as c,secretary_credentials as credentials
from commercial.agent_workspace import RevisionConflict
from commercial.tests.test_secretary_workflow import S,V

@pytest.fixture
def pack():
 p=json.loads(Path(__file__).parents[1].joinpath('secretary_pack_reference.json').read_text())
 return {**p,'id':'1'*24,'source_id':'source','enabled':True,'revision':1,'monitor_lead_minutes':1440,'action_lead_minutes':60}
@pytest.fixture
def store(monkeypatch,pack):
 # Unit tests use the reviewed fixture contract; live DynaForm requiredness is
 # covered separately without opening a real ProcessMaker database.
 monkeypatch.setattr(c,'with_live_requiredness',lambda source_id,pack,stage,con=None:pack)
 data={c.STORE:[copy.deepcopy(pack)]}
 class Tx:
  def get(self,k,default=None,**kw):return copy.deepcopy(data.get(k,default))
  def put(self,k,v):data[k]=copy.deepcopy(v)
  def audit(self,*a):pass
 @contextmanager
 def transaction():yield Tx()
 monkeypatch.setattr(c.agent_storage,'transaction',transaction)
 return data

def task(pack,stage,native=None):
 return {'case_uid':'a'*32,'index':1,'pack_id':pack['id'],'stage':stage,'pack':pack,'native':native or {},'title':'جلسه','number':'100'}

@pytest.mark.parametrize('stage',['invitation_approval','minutes_approval'])
def test_chair_vote_never_inherited_or_made_required_by_avan(pack,stage):
 v={'MTG_InvitationApproval':'Approved','MTG_MinutesApproval':'Approved'}
 t=task(pack,stage,v);values=r.initial(t)
 key='MTG_InvitationApproval' if stage=='invitation_approval' else 'MTG_MinutesApproval'
 assert values[key]==''
 # Current PM DynaForms do not mark the hidden vote field Required. AVAN must
 # not manufacture a gap, while still never inheriting/guessing a prior vote.
 assert key not in {x['field'] for x in r.gaps(values,t)}

def test_completion_claim_is_not_secretary_approval(pack):
 t=task(pack,'action_review',{'MTGA_ProgressPercent':'100','MTGA_ActualEffortMinutes':'70','MTGA_SubmissionType':'CompletionClaim'})
 v=r.initial(t);assert v['MTGA_SecretaryProgressPercent2']=='100' and v['MTGA_ReviewStatus2']==''
 v.update(MTGA_ReviewStatus2='Rework',MTGA_SecretaryProgressPercent2='60',MTGA_SecretaryComment1='مدرک کامل نیست')
 r.validate(v,t,S);assert v['MTGA_SecretaryProgressPercent2']=='60' and not r.gaps(v,t)

@pytest.mark.parametrize('value',['-1','101','sixty'])
def test_invalid_progress(pack,value):
 with pytest.raises(ValueError):r.validate({'MTGA_ProgressPercent':value},task(pack,'action_execution'),S)

def test_action_report_types_and_claim_normalization(pack):
 t=task(pack,'action_execution');v={'MTGA_SubmissionType':'CompletionClaim','MTGA_ProgressPercent':'80'}
 r.validate(v,t,S);assert v['MTGA_ProgressPercent']=='100'
 with pytest.raises(ValueError):r.validate({'MTGA_SubmissionType':'invented'},t,S)
 with pytest.raises(ValueError):r.validate({'MTG_MinutesApproval':'Approved'},t,S)

def test_native_update_and_duplicate_submit(pack,store):
 t=task(pack,'invitation_approval',copy.deepcopy(V));row=r.draft(S,'actor',t)
 values={**row['values'],'MTG_InvitationApproval':'Approved'}
 row=r.update(S,'actor',t,row['revision'],values)
 class PM:
  count=0
  def assigned(self,*a):return 1
  def variables(self,*a):return t["native"]
  def submit_stage(self,*a):self.count+=1
 pm=PM();r.submit(S,'actor',t,row['revision'],pm=pm)
 with pytest.raises(RevisionConflict):r.submit(S,'actor',t,row['revision'],pm=pm)
 assert pm.count==1

def test_native_change_rejects_stale_draft(pack,store):
 t=task(pack,'invitation_approval',copy.deepcopy(V));row=r.draft(S,'actor',t)
 t['native']['MTG_Location']='محل جدید'
 with pytest.raises(RevisionConflict):r.update(S,'actor',t,row['revision'],row['values'])
 reopened=r.draft(S,'actor',t);assert reopened['revision']>row['revision'] and reopened['values']['MTG_Location']=='محل جدید'

def test_timeout_is_not_retried(pack,store):
 t=task(pack,'invitation_approval',copy.deepcopy(V));row=r.draft(S,'actor',t);row=r.update(S,'actor',t,row['revision'],{'MTG_InvitationApproval':'Approved'})
 class PM:
  def assigned(self,*a):return 1
  def variables(self,*a):return t["native"]
  def submit_stage(self,*a):raise TimeoutError()
 with pytest.raises(TimeoutError):r.submit(S,'actor',t,row['revision'],pm=PM())
 assert r.draft(S,'actor',t)['status']=='reconciliation_required'
 with pytest.raises(RevisionConflict):r.submit(S,'actor',t,row['revision']+1,pm=PM())

def test_disabled_pack_and_source_isolation(pack,store):
 with pytest.raises(PermissionError):c.get('other',pack['id'])
 store[c.STORE][0]['enabled']=False
 with pytest.raises(PermissionError):c.get('source',pack['id'])

def test_own_native_task_query_only(pack,store,monkeypatch):
 calls=[]
 def query(con,sql,args):calls.append((sql,args));return [(pack['meeting']['process_uid'],100,phpserialize.dumps({}),pack['stages']['minutes_approval']['task_uid'])]
 monkeypatch.setattr(r,'query',query)
 t=r.task(None,S,'a'*32,1,pack['id']);assert t['stage']=='minutes_approval'
 assert 'd.USR_UID=%s' in calls[0][0] and S['external_user_id'] in calls[0][1]
 monkeypatch.setattr(r,'query',lambda *a:[])
 with pytest.raises(PermissionError):r.task(None,S,'a'*32,1,pack['id'])

def test_reminder_boundary_and_new_unread(pack,store,monkeypatch):
 due=r.legacy.jalali_instant('1405/07/15','16:30');v={'MTG_MeetingEndDateTime':'1405/07/15','MTG_PlannedActionEndTime':'16:30'}
 monkeypatch.setattr(r,'query',lambda *a:[('a'*32,100,pack['meeting']['process_uid'],phpserialize.dumps(v),1,pack['stages']['monitoring']['task_uid'])])
 early=r.inbox(None,S,due-timedelta(days=1,seconds=1));assert not early['tasks'][0]['available'] and not early['notifications']
 active=r.inbox(None,S,due-timedelta(days=1));assert active['tasks'][0]['available'] and active['notifications'][0]['kind']=='monitoring_due'
 r.acknowledge(S,active['notifications'][0]['id']);assert r.inbox(None,S,due)['notifications'][0]['read']
 monkeypatch.setattr(r,'query',lambda *a:[]);assert not r.inbox(None,S,due)['notifications']

def test_action_due_resets_seen_notification(pack,store,monkeypatch):
 due=r.legacy.jalali_instant('1405/07/15','16:30');v={'MTGA_DueDateTime':'1405/07/15','MTGA_DueTime':'16:30'}
 monkeypatch.setattr(r,'query',lambda *a:[('a'*32,100,pack['action']['process_uid'],phpserialize.dumps(v),1,pack['stages']['action_execution']['task_uid'])])
 before=r.inbox(None,S,due-timedelta(hours=2));n=before['notifications'][0];r.acknowledge(S,n['id'])
 after=r.inbox(None,S,due-timedelta(hours=1));assert after['notifications'][0]['kind']=='action_due' and not after['notifications'][0]['read']

def test_personal_oauth_matches_binding_and_invalidates_endpoint(store,monkeypatch):
 monkeypatch.setattr(credentials,'processmaker_profile',lambda *a:{'api':{'base_url':'https://pm','workspace':'workflow'}})
 called=[]
 monkeypatch.setattr(credentials,'_pm_oauth_token',lambda *a:called.append(a) or {'access_token':'access','refresh_token':'refresh','expires_in':3600})
 with pytest.raises(PermissionError):credentials.connect(S,'actor','other','password','client','secret','bound')
 assert not called
 credentials.connect(S,'actor','bound','password','client','secret','bound');assert credentials.token(S,'actor')=='access'
 assert 'password' not in json.dumps(store)
 monkeypatch.setattr(credentials,'processmaker_profile',lambda *a:{'api':{'base_url':'https://different','workspace':'workflow'}})
 assert not credentials.connected(S,'actor')
 from fastapi import HTTPException
 with pytest.raises(HTTPException):credentials.token(S,'actor')

def test_latest_invitation_does_not_invent_agenda_timing_requirements(pack):
 gaps=r.gaps(V,task(pack,'invitation'))
 fields={x['field'] for x in gaps}
 assert 'MTG_AgendaPresenterUID' not in fields
 assert 'MTG_AgendaPlannedMinutes' not in fields

def test_followup_asks_for_date_location(pack,store):
 t=task(pack,'monitoring',{'MTG_ChairUserUID':'c'*32,'MTG_MeetingTitle':'قبلی','MTG_Actions':{'1':{'MTG_ActionNo':'1','MTG_ActionOwnerUID':'c'*32,'MTG_ActionDescription':'انجام نشده'}}})
 row=r.followup(S,'actor',t);_,fake=r.session_load(S,'actor',row['id'])
 assert row['values']['MTG_Participants']['1']['MTG_ParticipantUserUID']=='c'*32
 assert {x['field'] for x in r.gaps(row['values'],fake)}>={'MTG_Location','MTG_MeetingStartDateTime'}

def test_parser_rejects_xml_entities():
 with pytest.raises(ValueError):c.parse_pmx('<!DOCTYPE x [<!ENTITY e SYSTEM "file:///etc/passwd">]><x/>')

def test_evidence_is_bounded_and_not_arbitrary_files():
 from commercial.secretary_evidence import document_text,MAX_BYTES
 assert document_text('مدرک کار'.encode(),'report.txt')=='مدرک کار'
 for data,name in [(b'x'*(MAX_BYTES+1),'x.txt'),(b'not a pdf','x.pdf'),(b'<script>x</script>','x.html'),(b'\xff','x.txt')]:
  with pytest.raises(ValueError):document_text(data,name)

def test_advice_cannot_certify_without_quote(pack,store):
 from commercial.secretary_evidence import assess
 from types import SimpleNamespace
 t=task(pack,'action_review',{'MTGA_ExecutionDescription':'گزارش بدون مدرک','MTGA_ProgressPercent':'100'})
 client=SimpleNamespace(responses=SimpleNamespace(create=lambda **kw:SimpleNamespace(status='completed',output_text=json.dumps({'summary':'گزارش موجود است','proposal':'مدرک تکمیلی درخواست شود','quotes':['گزارش بدون مدرک'],'missing':['مدرک انجام کار']}))))
 result=assess(S,'actor',t,client=client,model='configured');assert result['advisory'] and result['document_count']==0
 client.responses.create=lambda **kw:SimpleNamespace(status='completed',output_text=json.dumps({'summary':'حدس','proposal':'بسته شود','quotes':['سند ساختگی'],'missing':[]}))
 with pytest.raises(r.AgentInvalid):assess(S,'actor',t,client=client,model='configured')
 with pytest.raises(PermissionError):assess(S,'actor',task(pack,'action_execution'),client=client,model='configured')

def test_evidence_retention_cannot_change_task_owner(pack,store):
 from commercial.secretary_evidence import retain
 t=task(pack,'action_review');row=r.draft(S,'actor',t);doc={'app_doc_uid':'d'*32,'app_doc_version':1,'text':'سند','sha256':'hash'}
 with pytest.raises(PermissionError):retain(S,'another',t,row['revision'],doc)
 result=retain(S,'actor',t,row['revision'],doc);assert result['revision']==row['revision']+1 and 'text' not in result['documents'][0]
 with pytest.raises(RevisionConflict):retain(S,'actor',t,row['revision'],doc)

def test_route_maps_denied_before_source_wrapper_masks(pack,store,monkeypatch):
 from fastapi import FastAPI,HTTPException
 from fastapi.testclient import TestClient
 from types import SimpleNamespace
 from commercial.secretary_inbox_routes import register
 from commercial import production_app
 principal=SimpleNamespace(subject='actor',tenant_id='tenant')
 def source(source_id,action,p):
  try:return action(None,S)
  except HTTPException:raise
  except Exception:raise HTTPException(503,'masked')
 monkeypatch.setattr(production_app,'_source_store_response',source)
 monkeypatch.setattr(r,'task',lambda *a:(_ for _ in ()).throw(PermissionError('not your task')))
 app=FastAPI();register(app,lambda:(None,{},principal),lambda:(None,{},principal));client=TestClient(app)
 resp=client.post('/api/sources/source/secretary/tasks/load',json={'pack_id':pack['id'],'case_uid':'a'*32,'index':1})
 assert resp.status_code==403
 assert client.post('/api/sources/source/secretary/tasks/open',json={'pack_id':pack['id'],'case_uid':'bad','index':1}).status_code==422

def test_personal_transport_never_requires_or_refreshes_shared_token(monkeypatch):
 from commercial import secretary_processmaker as transport
 monkeypatch.setattr(transport,'processmaker_profile',lambda *a:{'api':{'base_url':'https://pm.example.com','workspace':'workflow','token_managed':True,'access_token_expires_at':0}})
 monkeypatch.setattr(transport,'_pm_profile_refresh',lambda *a:(_ for _ in ()).throw(AssertionError('shared refresh')))
 pm=transport.PM('source',process_uid='p'*32,bearer='personal');assert pm.client.headers['Authorization']=='Bearer personal';pm.close()

def test_unknown_monitor_deadline_is_not_open(pack,store,monkeypatch):
 monkeypatch.setattr(r,'query',lambda *a:[('a'*32,100,pack['meeting']['process_uid'],phpserialize.dumps({}),1,pack['stages']['monitoring']['task_uid'])])
 assert not r.inbox(None,S)['tasks'][0]['available']

def test_monitor_reference_identity_is_immutable(pack):
 native={'MTG_ActionSummary':{'1':{'MTG_MonActionNo':'A1','MTG_MonOwner':'مالک','MTG_MonSecReviewStatus':''}}}
 t=task(pack,'monitoring',native);v=r.initial(t);v['MTG_ActionSummary']['1'].update(MTG_MonSecReviewStatus='Rework',MTG_MonSecProgress='60',MTG_MonSecComment='ادامه کار')
 r.validate(v,t,S)
 v['MTG_ActionSummary']['1']['MTG_MonOwner']='فرد دیگر'
 with pytest.raises(ValueError):r.validate(v,t,S)

def test_text_pdf_is_read_by_bounded_worker():
 from commercial.secretary_evidence import document_text
 from pypdf import PdfWriter
 from pypdf.generic import DictionaryObject,NameObject,DecodedStreamObject
 from io import BytesIO
 writer=PdfWriter();page=writer.add_blank_page(width=595,height=842)
 font=DictionaryObject({NameObject('/Type'):NameObject('/Font'),NameObject('/Subtype'):NameObject('/Type1'),NameObject('/BaseFont'):NameObject('/Helvetica')})
 page[NameObject('/Resources')]=DictionaryObject({NameObject('/Font'):DictionaryObject({NameObject('/F1'):font})})
 content=DecodedStreamObject();content.set_data(b'BT /F1 12 Tf 72 720 Td (Completed shipment) Tj ET');page[NameObject('/Contents')]=writer._add_object(content)
 data=BytesIO();writer.write(data)
 assert 'Completed shipment' in document_text(data.getvalue(),'report.pdf')



def test_new_conversation_does_not_ask_for_system_generated_meeting_number(pack,store):
    row=r.session_create(S,'actor',pack['id'])
    _,fake=r.session_load(S,'actor',row['id'])
    fields={x['field'] for x in r.gaps(row['values'],fake)}
    assert 'MTG_MeetingNo' not in fields
    assert {'MTG_MeetingTitle','MTG_Location','MTG_MeetingStartDateTime','MTG_MeetingStartTime','MTG_ChairUserUID'} <= fields


def test_explicit_chair_voice_decision_is_deterministic(pack):
    values={}
    assert r.apply_explicit_decision('بله، دعوت‌نامه را تأیید می‌کنم','invitation_approval',values)=='Approved'
    assert values['MTG_InvitationApproval']=='Approved'
    values={}
    assert r.apply_explicit_decision('نیاز به اصلاح؛ ساعت جلسه عوض شود','invitation_approval',values)=='NeedsRevision'
    assert values['MTG_InvitationApproval']=='NeedsRevision'
    assert r.explicit_start_intent('بله، ایجاد و ارسال کن')
    assert not r.explicit_start_intent('مکان جلسه ساختمان جردن است')


def test_assistant_state_summarizes_invitation_for_chair(pack):
    t=task(pack,'invitation_approval',{
        **V,
        'MTG_Objective':'بررسی وضعیت واردات',
        'MTG_Participants':{'1':{'MTG_ParticipantUserUID':'c'*32}},
        'MTG_Agenda':{'1':{'MTG_AgendaTitle':'وضعیت مجوزها','MTG_AgendaPresenterUID':'c'*32,'MTG_AgendaPlannedMinutes':'20'}},
    })
    values=r.initial(t)
    state=r.assistant_state(values,t,S)
    assert 'بررسی واردات' in state['summary']
    assert 'رئیس' in state['summary']
    assert 'وضعیت مجوزها' in state['summary']
    assert 'تأیید' in state['message']



def test_conversational_uploads_extract_text_without_executing_embedded_content():
    from commercial import secretary_uploads as uploads
    from io import BytesIO
    import zipfile

    text,meta=uploads.extract('عنوان جلسه: بررسی واردات'.encode('utf-8'),'notes.txt','text/plain')
    assert 'بررسی واردات' in text and meta['type']=='txt'

    buf=BytesIO()
    with zipfile.ZipFile(buf,'w') as z:
        z.writestr('[Content_Types].xml','<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"/>')
        z.writestr('word/document.xml','''<?xml version="1.0" encoding="UTF-8"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
 <w:body><w:p><w:r><w:t>جلسه هیئت واردات فردا برگزار شود</w:t></w:r></w:p></w:body>
</w:document>''')
        z.writestr('word/vbaProject.bin',b'not-executed')
    doc,meta=uploads.extract(buf.getvalue(),'agenda.docx','application/vnd.openxmlformats-officedocument.wordprocessingml.document')
    assert 'جلسه هیئت واردات' in doc and meta['type']=='docx'



def test_new_meeting_uses_native_generated_number_before_routing_to_chair(pack,store):
    draft=r.session_create(S,'actor',pack['id'])
    values=copy.deepcopy(V)
    values.pop('MTG_MeetingNo')
    values['MTG_Agenda']['1'].update(
        MTG_AgendaPresenterUID='c'*32,
        MTG_AgendaPlannedMinutes='20',
    )
    draft=r.session_update(S,'actor',draft['id'],draft['revision'],values)
    created=[];written=[];submitted=[];triggers=[]
    class PM:
        def create_for(self,task,payload):created.append(copy.deepcopy(payload));return 'a'*32
        def assigned(self,*args):return 1
        def set_variables(self,case,index,payload,**kwargs):written.append(copy.deepcopy(payload))
        def execute_trigger(self,case,trigger,**kwargs):triggers.append(trigger)
        def variables(self,*args):return {'MTG_MeetingNo':'MTG-1405-001','MTG_FRMTG001_FormDate':'1405/07/12'}
        def submit_stage(self,case,stage,person,payload,index):submitted.append(payload)
    result=r.session_send(S,'actor',draft['id'],draft['revision'],pm=PM())
    assert result['status']=='awaiting_invitation_approval'
    assert result['case_uid']=='a'*32
    assert created[0]['MTG_MeetingTitle']==values['MTG_MeetingTitle']
    assert created[0]['MTG_Agenda']['1']['MTG_AgendaPresenterUID']=='c'*32
    assert written[0]['MTG_MeetingTitle']==values['MTG_MeetingTitle']
    assert triggers==pack['stages']['invitation']['before']
    assert submitted[0]['MTG_MeetingNo']=='MTG-1405-001'


def test_failed_new_meeting_reconciles_same_processmaker_case_without_duplicate(pack,store):
    draft=r.session_create(S,'actor',pack['id'])
    values=copy.deepcopy(V);values.pop('MTG_MeetingNo')
    values['MTG_Agenda']['1'].update(MTG_AgendaPresenterUID='c'*32,MTG_AgendaPlannedMinutes='20')
    draft=r.session_update(S,'actor',draft['id'],draft['revision'],values)
    class FailingPM:
        def variables(self,case):return {}
        def create_for(self,task,payload):return 'a'*32
        def assigned(self,*args):return 1
        def set_variables(self,*args,**kwargs):raise RuntimeError('trigger transport stopped after create')
    with pytest.raises(RuntimeError):
        r.session_send(S,'actor',draft['id'],draft['revision'],pm=FailingPM())
    failed=next(x for x in r.sessions(S,'actor') if x['id']==draft['id'])
    assert failed['status']=='reconciliation_required'
    assert failed['case_uid']=='a'*32
    assert failed['last_error']

    calls=[]
    class RecoveryPM:
        def assigned(self,case,*args):calls.append(('assigned',case));return 1
        def set_variables(self,case,index,payload,**kwargs):calls.append(('variables',case,payload['MTG_MeetingTitle']))
        def execute_trigger(self,case,trigger,**kwargs):calls.append(('before',case,trigger))
        def variables(self,case):return {'MTG_MeetingNo':'MTG-1405-009','MTG_FRMTG001_FormDate':'1405/07/13'}
        def submit_stage(self,case,stage,person,payload,index):calls.append(('submit',case,payload['MTG_MeetingNo']))
    result=r.session_reconcile(S,'actor',draft['id'],failed['revision'],pm=RecoveryPM())
    assert result['case_uid']=='a'*32
    assert result['status']=='awaiting_invitation_approval'
    assert all(call[1]=='a'*32 for call in calls)
    assert ('submit','a'*32,'MTG-1405-009') in calls



def test_virtual_meeting_pack_drives_real_owned_task_inbox(store,monkeypatch):
 trusted=c._trusted_meeting_pack()
 store[c.STORE]=[
  {'id':'a'*24,'source_id':'source','enabled':True,'revision':1,'adapter':'native_tasks_v1',
   'process':{'process_uid':trusted['meeting']['process_uid'],'title':'فرایند مدیریت جلسات'},
   'monitor_lead_minutes':1440,'action_lead_minutes':60,'tools':['read_own_tasks']},
  {'id':'b'*24,'source_id':'source','enabled':True,'revision':1,'adapter':'native_tasks_v1',
   'process':{'process_uid':trusted['action']['process_uid'],'title':'فرایند اقدام مصوب جلسه'},
   'monitor_lead_minutes':1440,'action_lead_minutes':60,'tools':['read_own_tasks']},
 ]
 virtual=c.runtime_meeting_pack('source')
 assert virtual and virtual['runtime_virtual']
 stage='invitation_approval'
 monkeypatch.setattr(r,'query',lambda *a:[(
   'a'*32,100,trusted['meeting']['process_uid'],phpserialize.dumps(V),1,
   trusted['stages'][stage]['task_uid']
 )])
 result=r.inbox(None,S,pack_id=virtual['id'])
 assert result['packs'][0]['id']==virtual['id']
 assert result['tasks'][0]['stage']==stage
 # task() selects four columns, whereas inbox() selects six.
 monkeypatch.setattr(r,'query',lambda *a:[(trusted['meeting']['process_uid'],100,phpserialize.dumps(V),trusted['stages'][stage]['task_uid'])])
 loaded=r.task(None,S,'a'*32,1,virtual['id'])
 assert loaded['pack']['adapter']=='meeting_v2'
 assert loaded['stage']==stage



def test_explicit_action_and_review_voice_intents_are_deterministic():
 values={}
 assert r.apply_explicit_workflow_intent('اقدام تکمیل شد','action_execution',values)=='completion'
 assert values['MTGA_SubmissionType']=='CompletionClaim'
 assert values['MTGA_ProgressPercent']=='100'
 assert r.explicit_advance_intent('اقدام تکمیل شد','action_execution','completion')

 values={}
 assert r.apply_explicit_workflow_intent('تأیید و ببند','action_review',values)=='closed'
 assert values['MTGA_ReviewStatus2']=='Closed'
 assert r.explicit_advance_intent('تأیید و ببند','action_review','closed')

 values={}
 assert r.apply_explicit_workflow_intent('برای اصلاح برگردان','action_review',values)=='rework'
 assert values['MTGA_ReviewStatus2']=='Rework'
 assert r.explicit_advance_intent('برای اصلاح برگردان','action_review','rework')

 assert r.explicit_advance_intent('صورتجلسه را ثبت و ارسال کن','minutes')
 assert r.explicit_advance_intent('جلسه را خاتمه بده','monitoring')
 assert not r.explicit_advance_intent('به نظرم خوب است','action_execution')



def test_secretary_asks_missing_information_one_question_at_a_time(pack):
 t=task(pack,'invitation',{})
 missing=r.gaps({},t)
 assert len(missing)>1
 state=r.assistant_state({},t,S)
 assert missing[0]['question'] in state['message']
 assert missing[1]['question'] not in state['message']
 assert 'مورد باقی‌مانده' in state['message']


def test_assignment_evidence_allows_persian_unicode_and_spacing_normalization():
 notes='رئیس جلسه administrator و دبیر جلسه admini است.'
 assert r._evidence_in_notes('رئیس جلسه  administrator',notes)
 assert r._evidence_in_notes('دبير جلسه admini',notes)
 assert not r._evidence_in_notes('جلسه ساعت ۱۰ است',notes)



def test_secretary_provider_failures_are_classified_safely():
 class Timeout:
  status_code=None
  __class__=type('APITimeoutError',(object,),{})
 # Build representative exception classes by name without importing OpenAI internals.
 APITimeoutError=type('APITimeoutError',(Exception,),{})
 APIConnectionError=type('APIConnectionError',(Exception,),{})
 AuthenticationError=type('AuthenticationError',(Exception,),{})
 RateLimitError=type('RateLimitError',(Exception,),{})
 BadRequestError=type('BadRequestError',(Exception,),{})
 assert 'زمان مقرر' in r._model_failure(APITimeoutError())
 assert 'ارتباط AVAN' in r._model_failure(APIConnectionError())
 auth=AuthenticationError();auth.status_code=401
 assert 'API Key' in r._model_failure(auth)
 rate=RateLimitError();rate.status_code=429
 assert 'سهمیه' in r._model_failure(rate)
 bad=BadRequestError();bad.status_code=400
 assert 'Structured Output' in r._model_failure(bad)



def test_extract_prefers_official_responses_parse(pack):
 class Responses:
  def __init__(self):self.calls=0
  def parse(self,**kwargs):
   self.calls+=1
   assert kwargs['text_format'] is r.legacy.Extraction
   class Result:
    status='completed'
    output_parsed=r.legacy.Extraction(assignments=[],questions=['عنوان جلسه چیست؟'])
   return Result()
  def create(self,**kwargs):
   raise AssertionError('manual structured create must not be used when parse is available')
 class Client:
  def __init__(self):self.responses=Responses()
 client=Client()
 values,questions=r.extract('یک جلسه می‌خواهم',task(pack,'invitation',{}),{},S,client=client,model='test-model')
 assert values=={}
 assert questions==['عنوان جلسه چیست؟']
 assert client.responses.calls==1



def test_extracted_grid_merges_into_empty_string_without_attribute_error():
 incoming={'1':{'MTG_ParticipantUserUID':'u1','MTG_ParticipantName':'کاربر'}}
 merged=r._merge_extracted_value('',incoming)
 assert merged==incoming


def test_extracted_grid_preserves_existing_row_fields():
 current={'1':{'MTG_ParticipantUserUID':'u1','MTG_ParticipantName':'قدیمی'}}
 incoming={'1':{'MTG_ParticipantName':'جدید'},'2':{'MTG_ParticipantUserUID':'u2'}}
 merged=r._merge_extracted_value(current,incoming)
 assert merged['1']['MTG_ParticipantUserUID']=='u1'
 assert merged['1']['MTG_ParticipantName']=='جدید'
 assert merged['2']['MTG_ParticipantUserUID']=='u2'


def test_conversational_reply_is_persisted_in_history(store,pack):
 t=task(pack,'invitation')
 row=r.draft(S,'actor',t)
 reply='موضوع ردیف سوم نیازمندی‌های بازرگانی است.'
 updated=r.update(S,'actor',t,row['revision'],row['values'],turn_text='موضوع ردیف چیه؟',reply=reply)
 assert updated['reply']==reply
 assert updated['history'][-1]['text']==reply
 assert updated['values']==row['values']



def test_native_case_values_reads_application_app_data_from_fresh_readonly_mysql(monkeypatch):
 from commercial import processmaker_store,user_bpms_bindings
 payload={'MTG_MeetingNo':'MTG-1405-1001','MTG_FRMTG001_FormDate':'1405/07/15','MTG_MeetingTitle':'جلسه AVAN'}
 seen=[]
 monkeypatch.setattr(user_bpms_bindings,'processmaker_profile',lambda source_id:{'mysql':{'database':'bitnami_pm'}})
 @contextmanager
 def opened(config):
  seen.append(('open',config['database']))
  yield object()
 monkeypatch.setattr(processmaker_store,'open_production',opened)
 def fake_query(con,sql,args=()):
  seen.append(('query',sql,args))
  return [(phpserialize.dumps(payload),)]
 monkeypatch.setattr(r,'query',fake_query)
 result=r._native_case_values(S,'a'*32)
 assert result['MTG_MeetingNo']=='MTG-1405-1001'
 assert result['MTG_MeetingTitle']=='جلسه AVAN'
 assert seen[0]==('open','bitnami_pm')
 assert 'FROM APPLICATION' in seen[1][1]
 assert seen[1][2]==('a'*32,)


def test_live_session_path_can_use_readonly_native_reader_instead_of_rest_variables(pack,store,monkeypatch):
 draft=r.session_create(S,'actor',pack['id'])
 values=copy.deepcopy(V);values.pop('MTG_MeetingNo',None)
 values['MTG_Agenda']['1'].update(MTG_AgendaPresenterUID='c'*32,MTG_AgendaPlannedMinutes='20')
 draft=r.session_update(S,'actor',draft['id'],draft['revision'],values)
 monkeypatch.setattr(r,'_meeting_sequence_prerequisite',lambda scope:True)
 monkeypatch.setattr(r,'token',lambda scope,actor:'personal')
 monkeypatch.setattr(r,'_native_case_values',lambda scope,case:{
  'MTG_MeetingNo':'MTG-1405-1002','MTG_FRMTG001_FormDate':'1405/07/15'
 })
 calls=[]
 class LivePM:
  def __init__(self,*a,**kw):pass
  def create_for(self,task,payload):calls.append(('create',payload['MTG_MeetingTitle']));return 'a'*32
  def assigned(self,*a):return 1
  def set_variables(self,*a,**kw):calls.append(('set',))
  def execute_trigger(self,*a,**kw):calls.append(('trigger',))
  def variables(self,*a):raise AssertionError('live path must not GET variables through REST')
  def submit_stage(self,case,stage,person,payload,index):calls.append(('submit',payload['MTG_MeetingNo']))
  def close(self):pass
 monkeypatch.setattr(r,'PM',LivePM)
 result=r.session_send(S,'actor',draft['id'],draft['revision'])
 assert result['status']=='awaiting_invitation_approval'
 assert ('submit','MTG-1405-1002') in calls



def test_route_only_recovery_does_not_replay_variables_or_triggers(pack,store):
 t=task(pack,'invitation_approval',copy.deepcopy(V))
 row=r.draft(S,'actor',t)
 key=r.task_key(S,t['case_uid'],t['index'])
 with r.agent_storage.transaction() as tx:
  saved=tx.get(key,lock=True)
  saved.update(status='reconciliation_required',last_error='ProcessMaker عملیات «ارسال پرونده به مرحله بعد» را نپذیرفت (HTTP 400).')
  tx.put(key,saved)
 calls=[]
 class PM:
  def assigned(self,*args):calls.append('assigned');return t['index']
  def variables(self,*args):calls.append('variables');return copy.deepcopy(row['values'])
  def route(self,case,index):calls.append(('route',case,index))
 result=r.reconcile_task_route(S,'actor',t,row['revision'],pm=PM())
 assert result['status']=='sent'
 assert ('route',t['case_uid'],t['index']) in calls
 assert all(x not in calls for x in ('set_variables','execute_trigger'))


def test_processmaker_rejection_exposes_safe_trigger_message_and_phase():
 from types import SimpleNamespace
 from commercial import secretary_processmaker as transport
 class Client:
  def request(self,*args,**kwargs):
   return SimpleNamespace(status_code=400,content=b'x',json=lambda:{'error':{'message':'برای شرکت‌کننده حاضر، ساعت حضور را با قالب HH:mm وارد کنید.'}})
 pm=object.__new__(transport.PM);pm.base='https://pm/api/1.0/workflow';pm.client=Client()
 with pytest.raises(transport.PMRejected) as caught:
  pm.execute_trigger('a'*32,'f'*32,operation='اجرای Trigger بعد از فرم')
 assert caught.value.upstream_status==400
 assert 'ساعت حضور' in str(caught.value.detail)
 class StagePM:
  def assigned(self,*args):return 1
  def set_variables(self,*args,**kwargs):pass
  def execute_trigger(self,*args,**kwargs):raise transport.PMRejected('اجرای Trigger بعد از فرم',400,'رد شد')
  def route(self,*args):pytest.fail('route must not run after rejected trigger')
 stage_pm=StagePM()
 stage={'task_uid':'t'*32,'after':['f'*32]}
 with pytest.raises(transport.PMRejected) as phase:
  transport.PM.submit_stage(stage_pm,'a'*32,stage,'s'*32,{},1)
 assert phase.value.pm_phase=='after_trigger'


def test_minutes_submit_preflight_refuses_missing_locked_plan(pack,store):
 native={'MTG_MeetingHeld':'Held'}
 t=task(pack,'minutes',native);row=r.draft(S,'actor',t)
 class PM:
  def assigned(self,*args):return 1
  def variables(self,*args):return copy.deepcopy(native)
  def submit_stage(self,*args):pytest.fail('ProcessMaker must not be mutated before locked-plan preflight')
 with pytest.raises(ValueError,match='آماده'):
  r.submit(S,'actor',t,row['revision'],pm=PM())



def test_minutes_direct_advance_uses_rest_only_and_routes_same_case(pack,store,monkeypatch):
 native=copy.deepcopy(V)
 native.update({
  'MTG_MeetingHeld':'Held',
  'MTG_MeetingDiscussionSummary':'جمع‌بندی',
  'MTG_MeetingEndTime':'17:00',
 })
 native['MTG_Participants']['1'].update(MTG_AttendanceStatus='Present',MTG_AttendanceTime='10:00')
 t=task(pack,'minutes',native)
 row=r.draft(S,'actor',t)
 trusted=c._trusted_meeting_pack()
 calls=[]
 class PM:
  def __init__(self,*a,**kw):calls.append(('init',a,kw))
  def info(self,case):
   calls.append(('info',case))
   return {'current_task':[{
    'tas_uid':trusted['stages']['minutes']['task_uid'],
    'usr_uid':S['external_user_id'],
    'del_thread_status':'OPEN','del_index':1,
   }]}
  def set_variables(self,case,index,values,operation=None):
   calls.append(('variables',case,index,operation))
  def execute_trigger(self,case,trigger,operation=None):
   calls.append(('trigger',case,trigger,operation))
  def route(self,case,index):calls.append(('route',case,index))
  def close(self):calls.append(('close',))
 monkeypatch.setattr(r,'PM',PM)
 monkeypatch.setattr(r,'_native_case_values',lambda *a:pytest.fail('minutes direct advance must never read PM MySQL'))
 result=r.advance_minutes_direct(
  S['tenant_id'],'actor',S['source_id'],S['external_user_id'],
  t['case_uid'],t['index'],pack['id'],'bearer-token',directory=S['directory'])
 assert result['status']=='sent'
 assert result['next_stage']=='minutes_approval'
 assert [x[0] for x in calls if x][1:]==['info','variables','trigger','route','close']
 saved=store[r.task_key(S,t['case_uid'],t['index'])]
 assert saved['status']=='sent'


def test_minutes_direct_advance_is_idempotent_after_case_reaches_approval(pack,store,monkeypatch):
 t=task(pack,'minutes',copy.deepcopy(V));r.draft(S,'actor',t)
 trusted=c._trusted_meeting_pack();calls=[]
 class PM:
  def __init__(self,*a,**kw):pass
  def info(self,case):
   return {'current_task':[{
    'tas_uid':trusted['stages']['minutes_approval']['task_uid'],
    'usr_uid':'c'*32,'del_thread_status':'OPEN','del_index':2,
   }]}
  def set_variables(self,*a,**kw):pytest.fail('already advanced case must not be written again')
  def execute_trigger(self,*a,**kw):pytest.fail('already advanced case must not rerun trigger')
  def route(self,*a,**kw):pytest.fail('already advanced case must not reroute')
  def close(self):calls.append('close')
 monkeypatch.setattr(r,'PM',PM)
 result=r.advance_minutes_direct(
  S['tenant_id'],'actor',S['source_id'],S['external_user_id'],
  t['case_uid'],t['index'],pack['id'],'bearer-token',directory=S['directory'])
 assert result['already_advanced'] is True
 assert result['next_stage']=='minutes_approval'
 assert calls==['close']

def test_trusted_runtime_pack_carries_reviewed_trigger_hashes():
 trusted=c._trusted_meeting_pack()
 reference=json.loads(Path(__file__).parents[1].joinpath('secretary_pack_reference.json').read_text(encoding='utf-8'))
 trigger='fe88e8afc98ca69585ab0f5fb16bbf74'
 assert trusted['meeting']['trigger_hashes'][trigger]==reference['meeting']['trigger_hashes'][trigger]
 assert trusted['action']['trigger_hashes']==reference['action']['trigger_hashes']


def test_processmaker_mojibake_repair_restores_persian():
 from commercial.secretary_processmaker import _repair_mojibake
 original="برای شرکت‌کننده حاضر، ساعت حضور را با قالب HH:mm وارد کنید."
 mojibake=original.encode("utf-8").decode("latin1")
 assert _repair_mojibake(mojibake)==original


def test_action_stage_requirements_match_latest_action_pmx(pack):
 execution=task(pack,'action_execution')
 gaps=r.gaps({
  'MTGA_SubmissionType':'CompletionClaim',
  'MTGA_ProgressPercent':'100',
  'MTGA_ExecutionDescription':'کار انجام شد',
 },execution)
 fields={x['field'] for x in gaps}
 assert 'MTGA_ActualEffortMinutes' not in fields
 assert 'MTGA_ActualCompletionDateTime' not in fields
 assert 'MTGA_ActualCompletionTime' not in fields

 review=task(pack,'action_review')
 gaps=r.gaps({
  'MTGA_ReviewStatus2':'Closed',
  'MTGA_SecretaryProgressPercent2':'100',
 },review)
 fields={x['field'] for x in gaps}
 assert 'MTGA_SecretaryActualEffortMinutes2' not in fields
 assert 'MTGA_SecretaryActualCompletionDateTime2' not in fields
 assert 'MTGA_SecretaryActualCompletionTime2' not in fields


def test_minutes_approval_does_not_invent_minimum_action_requirement(pack):
 t=task(pack,'minutes_approval',{
  'MTG_MeetingHeld':'Held',
  'MTG_MeetingDiscussionSummary':'جمع‌بندی',
  'MTG_Participants':{},
  'MTG_Decisions':{},
  'MTG_Actions':{},
 })
 gaps=r.gaps({'MTG_MinutesApproval':'Approved'},t)
 assert not any(x['field']=='MTG_Actions' for x in gaps)


def test_latest_reviewed_pmx_pair_is_the_only_runtime_contract():
 trusted=c._trusted_meeting_pack()
 assert trusted['meeting']['pmx_sha256']=='153492224d92b8df34aa4502e92ff7a8b4c9ec76cc41acffed184db5e5d72015'
 assert trusted['action']['pmx_sha256']=='a44a7703546218ed84f32030822b6f14dccb92c7877ca7114badaa81235d8fdb'
 assert set(trusted['meeting']['stages'])=={'invitation','invitation_approval','minutes','minutes_approval','monitoring'}
 assert set(trusted['action']['stages'])=={'action_execution','action_review'}
 assert trusted['meeting']['stages']['minutes']['task_uid']=='a07e9ed93a4b3244aca40996c45eb227'
 assert trusted['meeting']['stages']['minutes_approval']['task_uid']=='af8402c57b05992f6b6e6c6d9eb5276a'
 assert trusted['meeting']['stages']['minutes']['after']==['fe88e8afc98ca69585ab0f5fb16bbf74']
 assert trusted['action']['stages']['action_execution']['task_uid']=='473bb4e227460a3ea6ac0f2cbf8ef8d4'
 assert trusted['action']['stages']['action_review']['task_uid']=='1bc65198c9b4cf2fae5d3ffbfeea3c00'
 assert 'MTG002_MeetingAttachment' in trusted['meeting']['stages']['minutes_approval']['fields']
 assert 'MTG_MeetingFile' not in trusted['meeting']['stages']['minutes_approval']['fields']




def test_processmaker_action_grid_serialization_sets_suggest_label(pack):
 scope=copy.deepcopy(S)
 owner='3'*32
 scope['directory'][owner]={
  'active':True,
  'username':'mgr.strategy',
  'name':'مدیر استراتژی',
  'position':'مدیر استراتژی',
  'unit':'استراتژی',
 }
 t=task(pack,'minutes')
 values={
  'MTG_Actions':{
   '1':{
    'MTG_ActionDecisionNo':'D-001',
    'MTG_ActionNo':'A-001',
    'MTG_ActionDescription':'تدوین برنامه استراتژی',
    'MTG_ActionOwnerUID':'',
    'MTG_ActionOwnerPosition':'مدیر استراتژی',
    'MTG_persiandate_ActionDueDateTime':'1405/07/20',
    'MTG_ActionPriority':'High',
   }
  }
 }
 payload=r.labelled(values,t,scope)
 row=payload['MTG_Actions']['1']
 assert row['MTG_ActionOwnerUID']==owner
 assert row['MTG_ActionOwnerUID_label']=='مدیر استراتژی'
 assert row['MTG_ActionOwnerPosition_label']=='مدیر استراتژی'
 assert row['MTG_ActionNo_label']=='A-001'
 assert row['MTG_ActionDescription_label']=='تدوین برنامه استراتژی'


def test_direct_minutes_submit_sends_labels_not_raw_uids(pack,store,monkeypatch):
 scope=copy.deepcopy(S)
 owner='3'*32
 scope['directory'][owner]={
  'active':True,
  'username':'mgr.strategy',
  'name':'مدیر استراتژی',
  'position':'مدیر استراتژی',
  'unit':'استراتژی',
 }
 native=copy.deepcopy(V)
 native.update({
  'MTG_MeetingHeld':'Held',
  'MTG_Decisions':{'1':{
   'MTG_DecisionNo':'D-001',
   'MTG_DecisionText':'برنامه استراتژی تدوین شود',
  }},
  'MTG_Actions':{'1':{
   'MTG_ActionDecisionNo':'D-001',
   'MTG_ActionNo':'A-001',
   'MTG_ActionDescription':'تدوین برنامه استراتژی',
   'MTG_ActionOwnerUID':'',
   'MTG_ActionOwnerPosition':'مدیر استراتژی',
   'MTG_persiandate_ActionDueDateTime':'1405/07/20',
   'MTG_ActionPriority':'High',
  }},
 })
 t=task(pack,'minutes',native)
 r.draft(scope,'actor',t)
 trusted=c._trusted_meeting_pack()
 written={}
 class PM:
  def __init__(self,*a,**kw):pass
  def info(self,case):
   return {'current_task':[{
    'tas_uid':trusted['stages']['minutes']['task_uid'],
    'usr_uid':scope['external_user_id'],
    'del_thread_status':'OPEN','del_index':1,
   }]}
  def set_variables(self,case,index,values,operation=None):
   written.update(copy.deepcopy(values))
  def execute_trigger(self,*a,**kw):pass
  def route(self,*a,**kw):pass
  def close(self):pass
 monkeypatch.setattr(r,'PM',PM)
 result=r.advance_minutes_direct(
  scope['tenant_id'],'actor',scope['source_id'],scope['external_user_id'],
  t['case_uid'],t['index'],pack['id'],'bearer-token',
  directory=scope['directory'])
 assert result['status']=='sent'
 row=written['MTG_Actions']['1']
 assert row['MTG_ActionOwnerUID']==owner
 assert row['MTG_ActionOwnerUID_label']=='مدیر استراتژی'
 assert row['MTG_ActionOwnerUID_label']!=owner



def test_opening_minutes_approval_repairs_legacy_suggest_labels(pack,store,monkeypatch):
 scope=copy.deepcopy(S)
 owner='3'*32
 scope['directory'][owner]={
  'active':True,
  'username':'mgr.strategy',
  'name':'مدیر استراتژی',
  'position':'مدیر استراتژی',
  'unit':'استراتژی',
 }
 native={
  'MTG_Actions':{'1':{
   'MTG_ActionDecisionNo':'D-001',
   'MTG_ActionNo':'A-001',
   'MTG_ActionDescription':'تدوین برنامه استراتژی',
   'MTG_ActionOwnerUID':'',
   'MTG_ActionOwnerPosition':'مدیر استراتژی',
   'MTG_persiandate_ActionDueDateTime':'1405/07/20',
   'MTG_ActionPriority':'High',
  }}
 }
 t=task(pack,'minutes_approval',native)
 written={}
 class PM:
  def __init__(self,*a,**kw):pass
  def assigned(self,*a):return 1
  def execute_trigger(self,*a,**kw):pass
  def set_variables(self,case,index,values,operation=None):
   written.update(copy.deepcopy(values))
  def close(self):pass
 monkeypatch.setattr(r,'PM',PM)
 monkeypatch.setattr(r,'token',lambda *a,**kw:'token')
 r.prepare(t,scope,'actor')
 row=written['MTG_Actions']['1']
 assert row['MTG_ActionOwnerUID']==owner
 assert row['MTG_ActionOwnerUID_label']=='مدیر استراتژی'
