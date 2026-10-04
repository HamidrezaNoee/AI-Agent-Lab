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
