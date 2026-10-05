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
