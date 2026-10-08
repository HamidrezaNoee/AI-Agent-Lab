"""Acceptance cases from the October 8 Persian conversation, with no live model."""
import copy
from types import SimpleNamespace
import pytest
from commercial import secretary_runtime as r,secretary_time as temporal,secretary_journal as journal
from commercial.secretary_processmaker import _repair_mojibake,PMRejected
from commercial.tests.test_secretary_inbox import pack,store,task
from commercial.tests.test_secretary_workflow import S,V

@pytest.mark.parametrize('text,expected', [('17:30','17:30'),('۱۷:۳۰','17:30'),('ساعت پنج و نیم بعد از ظهر','17:30'),('17:99',None),('24:30',None),('17 مهر 1405',None),('7 مهر 1405',None),('ساعت بعدی 17:30','17:30')])
def test_time_preserves_minutes_and_never_eats_dates(text,expected):
 assert temporal.clock(text,allow_bare=True)==expected

@pytest.mark.parametrize('text,day',[('۷ مهر ۱۴۰۵','1405/07/07'),('17 مهر 1405','1405/07/17'),('1405-07-17','1405/07/17')])
def test_jalali_date(text,day):assert temporal.jalali_date(text)==day

def test_invalid_date():
 with pytest.raises(ValueError):temporal.jalali_date('31 مهر 1405')

def test_exact_mixed_encoding_from_owner():
 raw='Ø¨Ø±Ø§Û Ø´Ø±Ú©ØªâÚ©ÙÙØ¯Ù Ø­Ø§Ø¶Ø±Ø Ø³Ø§Ø¹Øª Ø­Ø¶ÙØ± Ø±Ø§ Ø¨Ø§ ÙØ§ÙØ¨ HH:mm ÙØ§Ø±Ø¯ Ú©ÙÛØ¯.'
 expected='برای شرکت‌کننده حاضر، ساعت حضور را با قالب HH:mm وارد کنید.'
 assert _repair_mojibake(raw)==expected
 assert _repair_mojibake('خطا: '+raw)=='خطا: '+expected
 assert PMRejected('کنترل نهایی صورت‌جلسه',400,raw).upstream_message==expected
 assert _repair_mojibake(expected)==expected

def test_on_time_uses_native_start_and_preserves_absence(pack):
 values={'MTG_MeetingHeld':'Held','MTG_Participants':{'1':{'MTG_AttendanceStatus':'Present'},'7':{'MTG_AttendanceStatus':'Excused'}}}
 t=task(pack,'minutes',{'MTG_MeetingStartTime':'09:30'})
 result=r.converse('حضور ها بهموقع سر ساعت جلسه بودند',t,values,S)
 assert result[0]['MTG_Participants']['1']['MTG_AttendanceTime']=='09:30'
 assert result[0]['MTG_Participants']['7']==values['MTG_Participants']['7']
 assert values['MTG_Participants']['1'].get('MTG_AttendanceTime') is None
 assert result.receipt['tool']=='temporal.resolve'

def test_short_present_follows_last_question(pack):
 values={'MTG_MeetingHeld':'Held','MTG_Participants':{'7':{'MTG_AttendanceStatus':'Excused'}}}
 result=r.converse('حاضر بوده',task(pack,'minutes'),values,S,history=[{'role':'assistant','text':'وضعیت ردیف ۷، مدیر حقوقی، غیبت موجه است؛ آیا حاضر بوده؟'}])
 assert result[0]['MTG_Participants']['7']['MTG_AttendanceStatus']=='Present'

def test_date_reply_does_not_write_locked_minutes_time(pack):
 values={'MTG_MeetingHeld':'Held'}
 result=r.converse('17 مهر 1405',task(pack,'minutes'),values,S,history=[{'role':'assistant','text':'تاریخ پایان برنامه‌ریزی‌شده چیست؟'}])
 assert result[0]==values
 assert '1405/07/17' in result[2]
 assert 'قابل ویرایش نیست' in result[2]

def test_invitation_time_and_date_answer(pack):
 t=task(pack,'invitation')
 first=r.converse('۱۷ مهر ۱۴۰۵',t,{},S)
 assert first[0]['MTG_MeetingStartDateTime']=='1405/07/17'
 second=r.converse('17:30',t,first[0],S,history=[{'role':'assistant','text':'ساعت پایان جلسه چیست؟'}])
 assert second[0]['MTG_MeetingEndTime']=='17:30'

def test_semantic_retry_then_help_is_persistable_not_502(pack,monkeypatch):
 calls=[]
 def parse(**kw):
  calls.append(kw)
  raise r.AgentInvalid('Invalid assignment evidence')
 fake=SimpleNamespace(responses=SimpleNamespace(parse=parse),close=lambda:None)
 monkeypatch.setattr(r,'configured_client',lambda:(fake,'fixture'))
 t=task(pack,'minutes');values={'MTG_MeetingHeld':'Held'}
 result=r.converse('یک اصلاح مبهم',t,values,S)
 assert len(calls)==3
 assert result[0]==values and result[3]=='question'
 assert 'پس از سه بار' in result[2]
 follow=r.converse('چرا ارور دادی',t,values,S,history=[{'role':'assistant','text':result[2]}])
 assert 'نتوانستم' in follow[2] and len(calls)==3

def test_undo_is_revision_scoped_and_single_use(pack,store):
 t=task(pack,'invitation_approval',copy.deepcopy(V))
 row=r.draft(S,'actor',t);before=copy.deepcopy(row['values'])
 after={**before,'MTG_InvitationApproval':'Approved'}
 changed=r.update(S,'actor',t,row['revision'],after)
 assert journal.can_undo(changed) and changed['last_change']['count']==1
 with pytest.raises(PermissionError):r.undo_task(S,'other',t,changed['revision'])
 with pytest.raises(r.RevisionConflict):r.undo_task(S,'actor',t,changed['revision']-1)
 restored=r.undo_task(S,'actor',t,changed['revision'])
 assert restored['values']==before and not journal.can_undo(restored)
 with pytest.raises(r.RevisionConflict):r.undo_task(S,'actor',t,restored['revision'])

def test_sent_draft_not_undoable():
 row={'values':{'x':'old'},'status':'draft','revision':1}
 journal.record(row,{'x':'new'},{},{})
 row.update(values={'x':'new'},status='sent')
 assert not journal.can_undo(row)

@pytest.mark.parametrize('status',[429,503,401])
def test_transient_model_failure_has_bounded_budget(pack,monkeypatch,status):
 import httpx
 from openai import APIStatusError
 calls=[]
 def parse(**kw):
  calls.append(kw)
  raise APIStatusError('fixture',response=httpx.Response(status,request=httpx.Request('POST','https://api.openai.com/v1/responses')),body=None)
 monkeypatch.setattr(r,'configured_client',lambda:(SimpleNamespace(responses=SimpleNamespace(parse=parse),close=lambda:None),'fixture'))
 result=r.converse('این پیام نیاز به استخراج دارد',task(pack,'minutes'),{},S)
 assert len(calls)==(1 if status==401 else 3)
 assert result[0]=={} and result[3]=='question'
 assert 'محفوظ' in result[2] and 'فرم' in result[2]

def test_session_undo_route_keeps_checkpoint_private(pack,store,monkeypatch):
 from fastapi import FastAPI
 from fastapi.testclient import TestClient
 from commercial.secretary_inbox_routes import register
 from commercial import production_app
 principal=SimpleNamespace(subject='actor',tenant_id='tenant')
 monkeypatch.setattr(production_app,'_source_store_response',lambda source,fn,p:fn(None,S))
 app=FastAPI();register(app,lambda:(None,{},principal),lambda:(None,{},principal))
 client=TestClient(app);row=r.session_create(S,'actor',pack['id']);base='/api/sources/source/secretary/sessions/'+row['id']
 edited=client.post(base+'/edit',json={'revision':row['revision'],'values':{**row['values'],'MTG_MeetingTitle':'عنوان جدید'}})
 assert edited.status_code==200
 public=edited.json()
 assert public['can_undo'] and '_undo_checkpoint' not in public and 'scope' not in public
 undone=client.post(base+'/undo',json={'revision':public['revision']})
 assert undone.status_code==200 and undone.json()['session']['values']==row['values']
 assert not undone.json()['session']['can_undo']
 assert client.post(base+'/undo',json={'revision':public['revision']}).status_code==409


@pytest.mark.parametrize('message',['همه به موقه امدند','یعنی سر تایم جلسه همه امدند'])
def test_owner_typo_and_followup_keep_existing_identities(pack,message):
 values={'MTG_MeetingHeld':'Held','MTG_Participants':{'1':{'MTG_ParticipantUserUID':'s'*32,'MTG_AttendanceStatus':'Present'},'7':{'MTG_ParticipantUserUID':'c'*32,'MTG_AttendanceStatus':'Excused'}}}
 answer=r.converse(message,task(pack,'minutes',{'MTG_MeetingStartTime':'10:00'}),values,S)
 assert answer.receipt['tool']=='temporal.resolve'
 assert answer[0]['MTG_Participants']['1']['MTG_AttendanceTime']=='10:00'
 assert answer[0]['MTG_Participants']['1']['MTG_ParticipantUserUID']=='s'*32
 assert answer[0]['MTG_Participants']['7']['MTG_ParticipantUserUID']=='c'*32
 assert answer[0]['MTG_Participants']['7']['MTG_AttendanceStatus']=='Present'
 assert 'نام/نام' not in answer[2]


def test_optional_attendance_drops_persisted_questions(pack):
 values={'MTG_MeetingHeld':'Held','MTG_MeetingDiscussionSummary':'جلسه برگزار شد','MTG_Participants':{'1':{'MTG_ParticipantUserUID':'s'*32,'MTG_AttendanceStatus':'Present'}}}
 question='ساعت حضور شرکت‌کننده حاضر ردیف 1 را به صورت HH:mm اعلام کنید.'
 answer=r.converse('ساعت حضور اجباری نیست، خالی بماند',task(pack,'minutes'),values,S,questions=[question])
 assert answer[0]==values and 'اختیاری' in answer[2]
 assert question not in answer[2]
 assert not any('AttendanceTime' in x['field'] for x in r.gaps(values,task(pack,'minutes')))


def test_model_grid_echo_keeps_only_same_row_existing_identity(pack):
 field='MTG_Participants';spec=r.form(task(pack,'minutes'))[field]
 before={'1':{'MTG_ParticipantUserUID':'s'*32,'MTG_AttendanceStatus':'Present'}}
 after={'1':{'MTG_ParticipantUserUID':'s'*32,'MTG_AttendanceTime':'10:00'}}
 resolved,questions=r.resolve_extracted_people(field,after,spec,S['directory'],evidence='سر تایم آمدند',current=before)
 assert resolved['1']['MTG_ParticipantUserUID']=='s'*32 and not questions
 # A moved/new identity does not inherit another row's evidence exemption.
 resolved,questions=r.resolve_extracted_people(field,{'2':after['1']},spec,S['directory'],evidence='سر تایم آمدند',current=before)
 assert not resolved['2']['MTG_ParticipantUserUID'] and questions

@pytest.mark.parametrize('tampered',[False,True])
def test_only_reviewed_optional_attendance_trigger_is_compatible(monkeypatch,tampered):
 import hashlib,json
 from pathlib import Path
 from commercial import secretary_catalog as catalog,processmaker_store
 root=Path(__file__).parents[2]
 code=(root/'docs/processmaker/minutes-after-optional-attendance.php').read_text()
 uid='fe88e8afc98ca69585ab0f5fb16bbf74'
 reference=json.loads((root/'commercial/secretary_pack_reference.json').read_text())
 old_hash=reference['meeting']['trigger_hashes'][uid]
 original=code.replace("$status === 'Present' && $time !== '' && !preg_match", "$status === 'Present' && !preg_match")
 assert hashlib.sha256(original.replace('\r\n','\n').strip().encode()).hexdigest()==old_hash
 expected={'process_uid':'meeting','stages':{},'trigger_hashes':{uid:old_hash}}
 pack={'meeting':expected,'action':{'process_uid':'action','stages':{}}}
 monkeypatch.setattr(catalog,'_installed_process',lambda *args:{'stages':{}})
 monkeypatch.setattr(processmaker_store,'query',lambda *args:[(uid,code+('\nthrow new Exception("unreviewed");' if tampered else ''))])
 if tampered:
  with pytest.raises(ValueError):catalog._verify_installed_on_connection(None,pack)
 else:catalog._verify_installed_on_connection(None,pack)
