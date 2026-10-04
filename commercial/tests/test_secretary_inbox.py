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
def test_chair_vote_never_inherited(pack,stage):
 v={'MTG_InvitationApproval':'Approved','MTG_MinutesApproval':'Approved'}
 t=task(pack,stage,v);values=r.initial(t)
 assert values['MTG_InvitationApproval' if stage=='invitation_approval' else 'MTG_MinutesApproval']==''
 assert r.gaps(values,t)

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

def test_agenda_timing_questions(pack):
 gaps=r.gaps(V,task(pack,'invitation'));assert {x['field'] for x in gaps}>={'MTG_AgendaPresenterUID','MTG_AgendaPlannedMinutes'}

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
    submitted=[]
    class PM:
        def create_for(self,*args):return 'a'*32
        def assigned(self,*args):return 1
        def call(self,*args):return {}
        def variables(self,*args):return {'MTG_MeetingNo':'MTG-1405-001','MTG_FRMTG001_FormDate':'1405/07/12'}
        def submit_stage(self,case,stage,person,payload,index):submitted.append(payload)
    result=r.session_send(S,'actor',draft['id'],draft['revision'],pm=PM())
    assert result['status']=='awaiting_invitation_approval'
    assert result['case_uid']=='a'*32
    assert submitted[0]['MTG_MeetingNo']=='MTG-1405-001'



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
 loaded=r.task(None,S,'a'*32,1,virtual['id'])
 assert loaded['pack']['adapter']=='meeting_v2'
 assert loaded['stage']==stage
