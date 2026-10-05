import copy,json
from types import SimpleNamespace
import pytest
from commercial import secretary_ai_context as ctx,secretary_runtime as r
from commercial.tests.test_secretary_inbox import pack,task
from commercial.tests.test_secretary_workflow import S

def test_large_directory_is_shortlisted_and_private_fields_omitted(pack):
 scope=copy.deepcopy(S)
 scope['directory']={f'{i:032x}':{'active':True,'name':f'Person {i}','email':'private@example.com'} for i in range(2000)}
 uid=f'{1000:032x}'
 data=ctx.build_context('Person 1000',task(pack,'action_execution'),{},scope,{'x':{'type':'text','options':None}})
 assert uid in data['directory'] and len(data['directory'])<=80
 assert data['directory_incomplete']
 assert 'private@example.com' not in json.dumps(data)
 assert data['fields']['x']=={'type':'text'}

def test_stage_context_excludes_unknown_history_and_duplicate_values(pack):
 t=task(pack,'action_execution',{'MTGA_ProgressPercent':'20','MTGA_SecretHistory':'private','unrelated':'private'})
 data=ctx.build_context('گزارش',t,{'MTGA_ProgressPercent':'30'},S,r.form(t))
 assert not data['context'] and data['current']['MTGA_ProgressPercent']=='30'


def test_oversized_context_rejected_without_silent_truncation(pack):
 with pytest.raises(ValueError,match='زیاد'):
  ctx.build_context('گزارش',task(pack,'action_execution'),{'x':'a'*50000},S,{})


def test_chair_hidden_vote_is_typed_and_does_not_mutate_pack(pack):
 t=task(pack,'invitation_approval')
 before=copy.deepcopy(pack)
 spec=r.form(t)['MTG_InvitationApproval']
 assert spec['type']=='dropdown' and 'تأیید' in spec['label']
 assert {x['value'] for x in spec['options']}=={'Approved','NeedsRevision'}
 assert pack==before


def test_fake_ai_extracts_evidenced_progress_and_uses_budget(pack):
 captured={}
 def create(**kw):
  captured.update(kw)
  return SimpleNamespace(status='completed',output_text=json.dumps({'assignments':[{'field':'MTGA_ProgressPercent','value_json':'"40"','quote':'40'}],'questions':[]}))
 client=SimpleNamespace(responses=SimpleNamespace(create=create))
 vals,questions=r.extract('پیشرفت 40 درصد',task(pack,'action_execution'),{'MTGA_SubmissionType':'ProgressUpdate'},S,client=client,model='test')
 assert vals['MTGA_ProgressPercent']=='40'
 assert captured['max_output_tokens']==3500 and captured['store'] is False
 assert not questions


def test_empty_evidence_cannot_authorize_assignment(pack):
 client=SimpleNamespace(responses=SimpleNamespace(create=lambda **kw:SimpleNamespace(status='completed',output_text=json.dumps({'assignments':[{'field':'MTGA_ProgressPercent','value_json':'"100"','quote':' '}],'questions':[]}))))
 with pytest.raises(r.AgentInvalid):
  r.extract('گزارش',task(pack,'action_execution'),{'MTGA_SubmissionType':'ProgressUpdate'},S,client=client,model='test')


def test_persian_surnames_in_large_directory_keep_all_candidates(pack):
 scope=copy.deepcopy(S)
 scope['directory']={f'{i:032x}':{'active':True,'name':f'Employee {i}'} for i in range(200)}
 scope['directory'].update({
  'a'*32:{'active':True,'name':'علی کاویانی','unit':'مالی'},
  'b'*32:{'active':True,'name':'رضا کاویانی','unit':'فروش'},
  'c'*32:{'active':True,'name':'حسین سلطانی‌زاده'},
  'd'*32:{'active':False,'name':'کاویانی'},
 })
 data=ctx.build_context('آقای كاوياني رئیس، سلطانی زاده دبیر',task(pack,'invitation'),{},scope,{})
 assert set(data['directory'])=={'a'*32,'b'*32,'c'*32}
 assert data['directory']['a'*32]['unit']=='مالی'

@pytest.mark.parametrize('name,text,expected',[
 ('علی رضایی','علیرضا دبیر است',False),
 ('عَلِي كاوياني','کاویانی رئیس است',True),
 ('حسین سلطانی‌زاده','سلطانی زاده حاضر باشد',True),
 ('مهندس رضا احمدی','مهندس دبیر باشد',False),
])
def test_name_matching_uses_normalized_tokens(name,text,expected):
 assert bool(ctx.name_matches(name,text)) is expected


@pytest.mark.parametrize('field,identity',[
 ('MTG_Participants','MTG_ParticipantUserUID'),
 ('MTG_Agenda','MTG_AgendaTitle'),
])
def test_explicit_addition_does_not_overwrite_existing_rows(field,identity):
 old={'1':{identity:'existing','detail':'keep'}}
 result=r._merge_assignment(field,old,{'1':{identity:'new'}},'این مورد را اضافه کن')
 assert result=={'1':{identity:'existing','detail':'keep'},'2':{identity:'new'}}
 assert old=={'1':{identity:'existing','detail':'keep'}}
 assert r._merge_assignment(field,result,{'1':{identity:'new'}},'اضافه کن')==result

def test_usernames_reach_model_even_when_display_names_are_persian(pack):
 scope=copy.deepcopy(S)
 scope['directory']={f'{i:032x}':{'active':True,'name':f'Employee {i}'} for i in range(200)}
 names=['administrator','ceo','mgr.strategy','mgr.commercial','mgr.foreign','mgr.finance','mgr.legal','mgr.sales']
 for i,name in enumerate(names,300):
  scope['directory'][f'{i:032x}']={'active':True,'name':'کاربر سازمان','username':name}
 notes='رئیس جلسه ceo و دبیر administrator\nشرکت‌کنندگان:\n'+'\n'.join(names)+'\nدستور جلسه:\n1- mgr.strategy برنامه توسعه را 15 دقیقه بررسی کند.'
 data=ctx.build_context(notes,task(pack,'invitation'),{},scope,{})
 assert {v['username'] for v in data['directory'].values()}==set(names)
 assert data['calendar']['timezone']=='Asia/Tehran'
 from commercial.secretary_workflow import jalali_instant
 assert (jalali_instant(data['calendar']['jalali_tomorrow'],'00:00')-jalali_instant(data['calendar']['jalali_today'],'00:00')).days==1

@pytest.mark.parametrize('text,expected',[
 ('mgr.strategy برنامه را ارائه کند',True),
 ('MGR.STRATEGY',True),
 ('mgr.strategy2',False),
 ('xmgr.strategy',False),
 ('mgr.strategy@example.com',False),
])
def test_username_boundaries(text,expected):
 assert ctx.username_matches('mgr.strategy',text)==expected

def test_omitted_explicit_sections_retry_then_report_instead_of_silent_success(pack):
 calls=[]
 def create(**kw):
  calls.append(kw)
  return SimpleNamespace(status='completed',output_text='{"assignments":[],"questions":[]}')
 _,questions=r.extract('شرکت‌کنندگان:\nceo\nدستور جلسه:\n1- بررسی AVAN',task(pack,'invitation'),{},S,
  client=SimpleNamespace(responses=SimpleNamespace(create=create)),model='test')
 assert len(calls)==2
 assert len(questions)==2 and all('استخراج نشد' in q for q in questions)

def test_username_resolution_and_unknown_people_preserve_agenda(pack):
 scope=copy.deepcopy(S)
 names=['administrator','ceo','mgr.strategy','mgr.commercial','mgr.foreign','mgr.finance','mgr.legal','mgr.sales']
 scope['directory']={f'{i+300:032x}':{'active':True,'username':name,'name':'نام '+str(i)} for i,name in enumerate(names)}
 assignments=[
  {'field':'MTG_ChairUserUID','value_json':'"ceo"','quote':'ceo'},
  {'field':'MTG_Participants','value_json':json.dumps({str(i+1):{'MTG_ParticipantUserUID':n} for i,n in enumerate(names)}),'quote':'شرکت‌کنندگان'},
  {'field':'MTG_Agenda','value_json':json.dumps({'1':{'MTG_AgendaTitle':'بررسی توسعه','MTG_AgendaPresenterUID':'mgr.strategy','MTG_AgendaPlannedMinutes':'15'},'2':{'MTG_AgendaTitle':'بررسی مالی','MTG_AgendaPresenterUID':'not-found','MTG_AgendaPlannedMinutes':'10'}}),'quote':'دستور جلسه'}
 ]
 client=SimpleNamespace(responses=SimpleNamespace(create=lambda **kw:SimpleNamespace(status='completed',output_text=json.dumps({'assignments':assignments,'questions':[]}))))
 values,questions=r.extract('ceo شرکت‌کنندگان دستور جلسه',task(pack,'invitation'),{},scope,client=client,model='test')
 assert len(values['MTG_Participants'])==8
 assert values['MTG_ChairUserUID']==f'{301:032x}'
 assert values['MTG_Agenda']['1']['MTG_AgendaPresenterUID']==f'{302:032x}'
 assert values['MTG_Agenda']['2']['MTG_AgendaTitle']=='بررسی مالی'
 assert values['MTG_Agenda']['2']['MTG_AgendaPresenterUID']==''
 assert any('not-found' in q for q in questions)
 assert any('2' in q['question'] for q in r.gaps(values,task(pack,'invitation')))

def test_ambiguous_and_inactive_people_not_assigned():
 directory={'a':{'active':True,'name':'علی رضایی'},'b':{'active':True,'name':'علی رضایی'},'c':{'active':False,'username':'ceo'}}
 for raw in ('علی رضایی','ceo','fake-uid'):
  value,questions=r.resolve_extracted_people('MTG_ChairUserUID',raw,{},directory)
  assert value=='' and questions

def test_row_question_answers_from_draft_without_model_or_mutation(pack,monkeypatch):
 t=task(pack,'invitation')
 values={'MTG_Agenda':{'3':{'MTG_AgendaTitle':'نیازمندی‌های بازرگانی','MTG_AgendaPlannedMinutes':'10'}}}
 before=copy.deepcopy(values)
 monkeypatch.setattr(r,'extract',lambda *a,**kw:pytest.fail('Read-only row query must not call model'))
 result,questions,reply,intent=r.converse('موضوع ردیف ۳ چیه؟',t,values,S,questions=['قبلی'])
 assert 'نیازمندی‌های بازرگانی' in reply and '10' in reply
 assert intent=='question' and result==before==values and questions==['قبلی']

def test_model_question_cannot_apply_assignments_or_clear_pending_questions(pack):
 def create(**kw):
  return SimpleNamespace(status='completed',output_text=json.dumps({
   'intent':'question','reply':'موضوع ردیف سوم بررسی نیازمندی‌هاست.',
   'assignments':[{'field':'MTG_ChairUserUID','value_json':'"fake"','quote':'ندارد'}],'questions':[]}))
 original={'MTG_MeetingTitle':'جلسه'}
 result,questions,reply,intent=r.extract('موضوع چیه؟',task(pack,'invitation'),original,S,questions=['سؤال قبلی'],
  client=SimpleNamespace(responses=SimpleNamespace(create=create)),model='test',with_reply=True)
 assert result==original and questions==['سؤال قبلی'] and intent=='question'
 assert reply=='موضوع ردیف سوم بررسی نیازمندی‌هاست.'

def test_conversation_schema_requires_reply_and_intent():
 schema=r.legacy.model_schema(r.ConversationExtraction)
 assert {'reply','intent'}<=set(schema['required'])

def test_implicit_row_refers_to_current_missing_presenter(pack,monkeypatch):
 from commercial.tests.test_secretary_workflow import V
 values=copy.deepcopy(V)
 values['MTG_Agenda']={'3':{'MTG_AgendaTitle':'نیازمندی‌های واحد بازرگانی','MTG_AgendaPlannedMinutes':'10'}}
 monkeypatch.setattr(r,'extract',lambda *a,**kw:pytest.fail('Model should not be needed'))
 _,_,reply,intent=r.converse('موضوع ردیف چیه؟',task(pack,'invitation'),values,S)
 assert 'ردیف 3' in reply and 'نیازمندی‌های واحد بازرگانی' in reply and intent=='question'



def test_bound_avan_display_name_can_resolve_processmaker_identity(pack):
 scope=copy.deepcopy(S)
 uid='d'*32
 scope['directory']={
  uid:{'active':True,'name':'Sales Manager','username':'mgr.sales',
       'avan_name':'مدیر فروش','avan_username':'mgr.sales','unit':'فروش'}
 }
 data=ctx.build_context('ردیف چهار را مدیر فروش بگذار',task(pack,'invitation'),{},scope,{})
 assert uid in data['directory']
 assert data['directory'][uid]['avan_name']=='مدیر فروش'
 value,questions=r.resolve_extracted_people('MTG_ChairUserUID','مدیر فروش',{},scope['directory'])
 assert value==uid and questions==[]
