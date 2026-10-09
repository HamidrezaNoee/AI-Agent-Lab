"""Admin-registered, source-specific secretary packs compiled from reviewed PMX."""
from __future__ import annotations
import copy,hashlib,json,re,secrets
import xml.etree.ElementTree as ET
from . import agent_storage
from .secretary_workflow import CONTRACT,WRITE_FIELDS

STORE='secretary_packs_v2'

class MeetingPromotionUnavailable(ValueError):
 pass
STAGES={'invitation':'FR-MTG-001','invitation_approval':'FR-MTG-002','minutes':'FR-MTG-003','minutes_approval':'FR-MTG-004','monitoring':'FR-MTG-005','action_execution':'FR-MTG-A01','action_review':'FR-MTG-A02'}

def records(root,name):
 table=root.find(".//table[@name='"+name+"']")
 return [{x.tag:x.text or '' for x in a} for a in table] if table is not None else []

def parse_pmx(xml):
 if not isinstance(xml,str) or len(xml.encode())>2_500_000 or re.search(r'<!\s*(DOCTYPE|ENTITY)',re.sub(r'<!\[CDATA\[.*?\]\]>', '', xml, flags=re.S),re.I):raise ValueError('فایل PMX معتبر و بدون DTD لازم است.')
 try:root=ET.fromstring(xml)
 except ET.ParseError as exc:raise ValueError('ساختار XML فایل PMX معتبر نیست.') from exc
 metadata={a.get('key'):a.text for a in root.findall('metadata/meta')}
 process=metadata.get('uid','')
 if not re.fullmatch(r'[a-f0-9]{32}',process):raise ValueError('شناسه فرایند PMX معتبر نیست.')
 tasks={a['tas_uid']:a['tas_title'] for a in records(root,'tasks')}
 steps=records(root,'steps');triggers=records(root,'steptriggers');stages={}
 for form in records(root,'dynaforms'):
  title=form['dyn_title']
  stage=next((s for s,prefix in STAGES.items() if re.match(re.escape(prefix)+r'(?:\s|[-–]|$)',title)),None)
  if not stage:continue
  fields={}
  def walk(v):
   if isinstance(v,dict):
    if v.get('variable'):
     spec={k:v.get(k) for k in ('label','type','required','options','mode')}
     if v.get('type')=='grid':spec['columns']=[{k:c.get(k) for k in ('id','label','type','options','required','mode')} for c in v.get('columns',[])]
     fields[v['variable']]=spec
    for a in v.values():walk(a)
   elif isinstance(v,list):
    for a in v:walk(a)
  try:walk(json.loads(form['dyn_content']))
  except (ValueError,RecursionError) as exc:raise ValueError('تعریف فرم PMX معتبر نیست.') from exc
  linked=[a for a in steps if a['step_uid_obj']==form['dyn_uid'] and a['step_type_obj']=='DYNAFORM']
  if len(linked)!=1 or stage in stages:raise ValueError('نگاشت فرم به وظیفه باید یکتا باشد.')
  step=linked[0];task=step['tas_uid']
  assigned=[a for a in triggers if a['step_uid']==step['step_uid'] and a['tas_uid']==task]
  if any(a.get('st_condition') for a in assigned):raise ValueError('تریگر شرطی نیاز به توسعه و بازبینی آداپتور دارد.')
  stages[stage]={'task_uid':task,'task_title':tasks[task],'form_uid':form['dyn_uid'],'fields':fields,
   'before':[a['tri_uid'] for a in sorted(assigned,key=lambda a:int(a['st_position'])) if a['st_type']=='BEFORE'],
   'after':[a['tri_uid'] for a in sorted(assigned,key=lambda a:int(a['st_position'])) if a['st_type']=='AFTER']}
 used={uid for stage in stages.values() for side in ('before','after') for uid in stage[side]}
 source={row['tri_uid']:row.get('tri_webbot','') for row in records(root,'triggers')}
 if not used<=source.keys():raise ValueError('کد یکی از تریگرهای متصل در PMX موجود نیست.')
 hashes={uid:hashlib.sha256(source[uid].replace('\r\n','\n').strip().encode()).hexdigest() for uid in sorted(used)}
 return {'process_uid':process,'title':metadata.get('name',process),'pmx_sha256':hashlib.sha256(xml.encode()).hexdigest(),'stages':stages,'trigger_hashes':hashes}

def _compile_pair(meeting,action):
 meeting_stages={'invitation','invitation_approval','minutes','minutes_approval','monitoring'}
 action_stages={'action_execution','action_review'}
 if set(meeting['stages'])!=meeting_stages or set(action['stages'])!=action_stages:
  raise ValueError('PMX جلسه باید پنج مرحله جلسه و PMX اقدام باید دو مرحله اجرا و بررسی اقدام را داشته باشد؛ ترتیب فایل‌ها و نگاشت فرم‌ها را بررسی کنید.')
 for process in (meeting,action):
  task_ids=[stage['task_uid'] for stage in process['stages'].values()]
  if len(set(task_ids))!=len(task_ids):
   raise ValueError('هر مرحله بسته جلسات باید وظیفه مستقل داشته باشد؛ چند فرم نقش روی یک وظیفه پشتیبانی نمی‌شود.')
 stages={**meeting['stages'],**action['stages']}
 if set(stages)!=set(STAGES) or meeting['process_uid']==action['process_uid']:raise ValueError('دو PMX جلسات و اقدامات با هفت مرحله کامل لازم است.')
 for s in ('invitation','minutes','monitoring'):
  if not WRITE_FIELDS[s]<=stages[s]['fields'].keys():raise ValueError('فیلدهای ضروری بسته مدیریت جلسه در PMX موجود نیستند.')
 # This is a typed adapter, not arbitrary code generated/executed from uploaded XML.
 for s,keys in {'invitation_approval':['MTG_InvitationApproval','MTG_InvitationChairComment'],
   'minutes_approval':['MTG_MinutesApproval','MTG_ChairComment'],
   'action_execution':['MTGA_SubmissionType','MTGA_ProgressPercent','MTGA_ExecutionDescription'],
   'action_review':['MTGA_ReviewStatus2','MTGA_SecretaryProgressPercent2']}.items():
  if not set(keys)<=stages[s]['fields'].keys():raise ValueError('قرارداد مرحله '+s+' با آداپتور جلسات سازگار نیست.')
 return {'adapter':'meeting_v2','meeting':meeting,'action':action,'stages':stages}

def compile_pack(meeting_xml,action_xml):
 return _compile_pair(parse_pmx(meeting_xml),parse_pmx(action_xml))

def _form_fields(content):
 fields={}
 def walk(v):
  if isinstance(v,dict):
   if v.get('variable'):
    spec={k:v.get(k) for k in ('label','type','required','options','mode')}
    if v.get('type')=='grid':
     spec['columns']=[{k:c.get(k) for k in ('id','label','type','options','required','mode')} for c in v.get('columns',[])]
    fields[str(v['variable'])]=spec
   for a in v.values():walk(a)
  elif isinstance(v,list):
   for a in v:walk(a)
 try:
  from html import unescape
  raw=str(content or '').strip().lstrip('\ufeff')
  parsed=None;last=None
  for candidate in (raw,unescape(raw)):
   try:
    parsed=json.loads(candidate)
    # Some PM3 builds/drivers expose DYN_CONTENT as a JSON string containing
    # the actual JSON document. Unwrap at most twice; never eval arbitrary text.
    for _ in range(2):
     if not isinstance(parsed,str):break
     parsed=json.loads(parsed)
    break
   except (ValueError,TypeError) as exc:last=exc
  if parsed is None:raise last or ValueError('empty DynaForm content')
  walk(parsed)
 except (ValueError,RecursionError,TypeError) as exc:
  raise ValueError('تعریف فرم نصب‌شده ProcessMaker معتبر نیست.') from exc
 return fields


def _required_bool(value):
 if value is True:return True
 if value is False or value is None:return False
 return str(value).strip().lower() in ('1','true','yes','required')


def _overlay_live_requiredness(pack,stage,live_fields):
 """Overlay only PM-owned required flags onto the reviewed typed adapter."""
 result=copy.deepcopy(pack)
 if stage not in result.get('stages',{}):raise ValueError('مرحله موردنظر در بسته جلسات وجود ندارد.')
 target=result['stages'][stage]['fields']
 for field,spec in target.items():
  live=live_fields.get(field)
  if live is None:
   # Do not expand or mutate the audited writable surface just because PM changed.
   # A missing audited field is a contract drift, not an optional field.
   raise ValueError('فیلد '+field+' در فرم زنده ProcessMaker پیدا نشد؛ قرارداد فرم تغییر کرده است.')
  spec['required']=_required_bool(live.get('required'))
  if spec.get('type')=='grid':
   live_columns={str(c.get('id')):c for c in live.get('columns',[]) if c.get('id')}
   for column in spec.get('columns',[]):
    cid=str(column.get('id') or '')
    if cid and cid in live_columns:
     column['required']=_required_bool(live_columns[cid].get('required'))
 # meeting/action subtrees and the union are shared semantically but not always by
 # object identity after serialization; keep the current stage consistent.
 owner='action' if stage.startswith('action_') else 'meeting'
 if stage in result.get(owner,{}).get('stages',{}):
  result[owner]['stages'][stage]=copy.deepcopy(result['stages'][stage])
 canonical={
  key:{'required':bool(spec.get('required')),
       'columns':{str(c.get('id')):bool(c.get('required')) for c in spec.get('columns',[]) if c.get('id')}}
  for key,spec in sorted(target.items())
 }
 result['live_requiredness_hash']=hashlib.sha256(
  json.dumps(canonical,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
 ).hexdigest()
 result['live_requiredness_available']=True
 result['live_requiredness_warning']=''
 return result


def _requiredness_unavailable(pack,stage,reason):
 """Keep the reviewed editor usable when live PM form metadata is unavailable.

 No stale field is allowed to become a new AVAN blocker. Final workflow mutations
 re-read the live contract in strict mode before any ProcessMaker write/route.
 """
 result=copy.deepcopy(pack)
 target=result.get('stages',{}).get(stage,{}).get('fields',{})
 for spec in target.values():
  spec['required']=False
  for column in spec.get('columns',[]) or []:
   column['required']=False
 owner='action' if stage.startswith('action_') else 'meeting'
 if stage in result.get(owner,{}).get('stages',{}):
  result[owner]['stages'][stage]=copy.deepcopy(result['stages'][stage])
 result['live_requiredness_available']=False
 result['live_requiredness_warning']=(
  'تنظیم Required زنده ProcessMaker فعلاً قابل خواندن نیست؛ '
  'ویرایش و گفت‌وگو در AVAN باز می‌ماند، اما ارسال نهایی تا بازیابی این metadata متوقف است.'
 )
 result['live_requiredness_error']=str(reason or '')[:240]
 result['live_requiredness_hash']=''
 return result


def with_live_requiredness(source_id,pack,stage,*,con=None,strict=False):
 """Read current DynaForm required flags directly from ProcessMaker.

 Editor/chat reads are non-strict so a metadata permission outage never replaces
 the Smart Secretary UI with an emergency send page. Every final mutation calls
 this function with strict=True and therefore cannot bypass ProcessMaker's live
 Required contract.
 """
 if pack.get('adapter')!='meeting_v2':return pack
 if stage not in pack.get('stages',{}):raise ValueError('مرحله فرایند در بسته جلسات شناخته‌شده نیست.')
 stage_spec=pack['stages'][stage]
 owner='action' if stage.startswith('action_') else 'meeting'
 process_uid=pack[owner]['process_uid']
 form_uid=stage_spec['form_uid']
 from .processmaker_store import query,ProductionUnavailable
 owned=con is None
 manager=None;entered=False
 try:
  if owned:
   from .user_bpms_bindings import processmaker_profile
   from .processmaker_store import open_production
   manager=open_production(processmaker_profile(source_id)['mysql'])
   con=manager.__enter__();entered=True
  try:
   rows=query(con,'SELECT DYN_CONTENT FROM DYNAFORM WHERE DYN_UID=%s AND PRO_UID=%s LIMIT 2',
              (form_uid,process_uid))
  except Exception as exc:
   raise ProductionUnavailable('ProcessMaker DynaForm metadata unavailable') from exc
  if len(rows)!=1:
   raise ValueError('فرم زنده ProcessMaker برای مرحله جاری به‌صورت یکتا پیدا نشد.')
  live=_form_fields(str(rows[0][0] or '{}'))
  return _overlay_live_requiredness(pack,stage,live)
 except Exception as exc:
  if strict:raise
  return _requiredness_unavailable(pack,stage,exc)
 finally:
  if owned and manager is not None and entered:
   manager.__exit__(None,None,None)

def _installed_process(con,process_uid):
 from .processmaker_store import query
 process=query(con,'SELECT PRO_UID,PRO_TITLE FROM PROCESS WHERE PRO_UID=%s',(process_uid,))
 if len(process)!=1:raise ValueError('فرایند نصب‌شده ProcessMaker پیدا نشد.')
 tasks={str(r[0]):str(r[1] or r[0]) for r in query(con,'SELECT TAS_UID,TAS_TITLE FROM TASK WHERE PRO_UID=%s',(process_uid,))}
 forms=query(con,'SELECT DYN_UID,DYN_TITLE,DYN_CONTENT FROM DYNAFORM WHERE PRO_UID=%s',(process_uid,))
 stages={}
 signature=[]
 for dyn_uid,dyn_title,dyn_content in forms:
  title=str(dyn_title or '')
  stage=next((s for s,prefix in STAGES.items() if re.match(re.escape(prefix)+r'(?:\s|[-–]|$)',title)),None)
  if not stage:continue
  linked=query(con,"SELECT STEP_UID,TAS_UID FROM STEP WHERE STEP_UID_OBJ=%s AND STEP_TYPE_OBJ='DYNAFORM'",(str(dyn_uid),))
  if len(linked)!=1 or stage in stages:raise ValueError('نگاشت فرم نصب‌شده به وظیفه باید یکتا باشد.')
  step_uid,task_uid=map(str,linked[0])
  if task_uid not in tasks:raise ValueError('وظیفه فرم نصب‌شده متعلق به فرایند انتخابی نیست.')
  triggers=query(con,'SELECT TRI_UID,ST_TYPE,ST_POSITION,ST_CONDITION FROM STEP_TRIGGER WHERE STEP_UID=%s AND TAS_UID=%s ORDER BY ST_POSITION',(step_uid,task_uid))
  if any(str(r[3] or '').strip() for r in triggers):raise ValueError('تریگر شرطی نیاز به بازبینی آداپتور دارد.')
  stage_row={
   'task_uid':task_uid,'task_title':tasks[task_uid],'form_uid':str(dyn_uid),
   'fields':_form_fields(str(dyn_content or '{}')),
   'before':[str(r[0]) for r in triggers if str(r[1])=='BEFORE'],
   'after':[str(r[0]) for r in triggers if str(r[1])=='AFTER'],
  }
  stages[stage]=stage_row
  signature.append((stage,str(dyn_uid),task_uid,tuple(stage_row['before']),tuple(stage_row['after'])))
 digest=hashlib.sha256(json.dumps(signature,ensure_ascii=False,sort_keys=True).encode()).hexdigest()
 return {'process_uid':str(process[0][0]),'title':str(process[0][1] or process_uid),
         'pmx_sha256':'installed:'+digest,'stages':stages}

def _trusted_meeting_pack():
 """Return the single reviewed seven-stage contract shipped with AVAN.

 secretary_pack_reference.json is generated/reviewed against the two accepted
 PMX files and is the canonical runtime descriptor. Keeping a second hard-coded
 stage/form contract here caused the application to drift from ProcessMaker.
 """
 from pathlib import Path
 reference=json.loads(Path(__file__).with_name('secretary_pack_reference.json').read_text(encoding='utf-8'))
 pack=copy.deepcopy(reference)
 if pack.get('adapter')!='meeting_v2':
  raise ValueError('قرارداد داخلی بسته جلسات AVAN معتبر نیست.')
 if set((pack.get('meeting') or {}).get('stages') or {})!={'invitation','invitation_approval','minutes','minutes_approval','monitoring'}:
  raise ValueError('قرارداد داخلی فرایند مدیریت جلسات ناقص است.')
 if set((pack.get('action') or {}).get('stages') or {})!={'action_execution','action_review'}:
  raise ValueError('قرارداد داخلی فرایند اقدام مصوب جلسه ناقص است.')
 expected={**pack['meeting']['stages'],**pack['action']['stages']}
 if set(pack.get('stages') or {})!=set(expected):
  raise ValueError('قرارداد تجمیعی هفت مرحله با دو PMX مرجع یکسان نیست.')
 # Always rebuild the union to prevent stale duplicated stage definitions.
 pack['stages']=copy.deepcopy(expected)
 return _compile_pair(pack['meeting'],pack['action'])


def _verify_trusted_pack(source_id,pack):
 """Verify the reviewed descriptor against the installed PM without parsing DYN_CONTENT."""
 from .user_bpms_bindings import processmaker_profile
 from .processmaker_store import open_production,query
 with open_production(processmaker_profile(source_id)['mysql']) as con:
  for key in ('meeting','action'):
   proc=pack[key];uid=proc['process_uid']
   found=query(con,'SELECT PRO_UID FROM PROCESS WHERE PRO_UID=%s',(uid,))
   if len(found)!=1:raise ValueError('فرایند مورد انتظار بسته مدیریت جلسات روی این اتصال نصب نیست.')
   tasks={str(r[0]) for r in query(con,'SELECT TAS_UID FROM TASK WHERE PRO_UID=%s',(uid,))}
   forms={str(r[0]) for r in query(con,'SELECT DYN_UID FROM DYNAFORM WHERE PRO_UID=%s',(uid,))}
   triggers={str(r[0]) for r in query(con,'SELECT TRI_UID FROM TRIGGERS WHERE PRO_UID=%s',(uid,))}
   for stage in proc['stages'].values():
    if stage['task_uid'] not in tasks or stage['form_uid'] not in forms:
     raise ValueError('نسخه نصب‌شده فرایند جلسات با قرارداد تأییدشده آوان یکسان نیست.')
    needed=set(stage['before'])|set(stage['after'])
    if not needed<=triggers:
     raise ValueError('تریگرهای نسخه نصب‌شده با بسته تأییدشده مدیریت جلسات یکسان نیستند.')
 return True

def ensure_installed_meeting_pack(source_id,actor='system:auto'):
 """Promote two reviewed native ProcessMaker inboxes to meeting_v2 when their
 installed forms/tasks/triggers satisfy the typed seven-stage meeting contract.
 No PMX upload or untrusted code execution is involved.
 """
 existing=packs(source_id,True)
 if any(p.get('adapter')=='meeting_v2' for p in existing):return None
 native=[p for p in existing if p.get('adapter')=='native_tasks_v1' and p.get('enabled')]
 if len(native)<2:return None

 # Fast, deterministic promotion for the reviewed meeting/action pair already
 # shipped with AVAN. This avoids reparsing ProcessMaker 3.2/3.3 DYN_CONTENT,
 # whose storage representation differs between community builds.
 trusted_error=None
 try:
  trusted=_trusted_meeting_pack()
  by_uid={p.get('process',{}).get('process_uid'):p for p in native}
  trusted_candidate=(trusted['meeting']['process_uid'] in by_uid and trusted['action']['process_uid'] in by_uid)
  if trusted_candidate:
   _verify_trusted_pack(source_id,trusted)
   meeting_native=by_uid[trusted['meeting']['process_uid']]
   action_native=by_uid[trusted['action']['process_uid']]
   with agent_storage.transaction() as tx:
    data=tx.get(STORE,[],lock=True)
    if any(p.get('source_id')==source_id and p.get('adapter')=='meeting_v2' and p.get('enabled') for p in data):return None
    current_meeting=next((p for p in data if p.get('id')==meeting_native['id'] and p.get('source_id')==source_id),None)
    current_action=next((p for p in data if p.get('id')==action_native['id'] and p.get('source_id')==source_id),None)
    if current_meeting and current_action and current_meeting.get('adapter')=='native_tasks_v1' and current_action.get('adapter')=='native_tasks_v1':
     row={**trusted,'id':current_meeting['id'],'source_id':source_id,'enabled':True,
          'revision':max(int(current_meeting.get('revision',0)),int(current_action.get('revision',0)))+1,
          'monitor_lead_minutes':1440,'action_lead_minutes':60,
          'tools':['extract_fields','request_missing_fields','submit_invitation','review_invitation','submit_minutes','review_minutes','submit_action_report','review_action','prepare_monitoring','propose_followup']}
     remove={current_meeting['id'],current_action['id']}
     tx.put(STORE,[p for p in data if p.get('id') not in remove]+[row])
     tx.audit('',actor,'SECRETARY_TRUSTED_PACK_PROMOTED',{'source_id':source_id,'pack_id':row['id'],
              'meeting_process_uid':trusted['meeting']['process_uid'],'action_process_uid':trusted['action']['process_uid']})
     return row
 except ValueError as exc:
  # Preserve the exact incompatibility reason so the UI can explain why the
  # reviewed pair was not promoted, while still allowing generic discovery.
  trusted_error=str(exc)

 from .user_bpms_bindings import processmaker_profile
 from .processmaker_store import open_production
 compiled=[]
 with open_production(processmaker_profile(source_id)['mysql']) as con:
  for row in native:
   try:installed=_installed_process(con,row['process']['process_uid'])
   except ValueError:continue
   stage_set=set(installed['stages'])
   if stage_set=={'invitation','invitation_approval','minutes','minutes_approval','monitoring'}:
    compiled.append(('meeting',row,installed))
   elif stage_set=={'action_execution','action_review'}:
    compiled.append(('action',row,installed))
 meetings=[x for x in compiled if x[0]=='meeting'];actions=[x for x in compiled if x[0]=='action']
 if len(meetings)!=1 or len(actions)!=1:
  if trusted_error:raise MeetingPromotionUnavailable(trusted_error)
  return None
 meeting_native,meeting=meetings[0][1],meetings[0][2]
 action_native,action=actions[0][1],actions[0][2]
 try:pack=_compile_pair(meeting,action)
 except ValueError as exc:
  if trusted_error:raise MeetingPromotionUnavailable(trusted_error)
  raise MeetingPromotionUnavailable(str(exc))

 with agent_storage.transaction() as tx:
  data=tx.get(STORE,[],lock=True)
  if any(p.get('source_id')==source_id and p.get('adapter')=='meeting_v2' and p.get('enabled') for p in data):return None
  current_meeting=next((p for p in data if p.get('id')==meeting_native['id'] and p.get('source_id')==source_id),None)
  current_action=next((p for p in data if p.get('id')==action_native['id'] and p.get('source_id')==source_id),None)
  if not current_meeting or not current_action:return None
  if current_meeting.get('adapter')!='native_tasks_v1' or current_action.get('adapter')!='native_tasks_v1':return None
  row={**pack,'id':current_meeting['id'],'source_id':source_id,'enabled':True,
       'revision':max(int(current_meeting.get('revision',0)),int(current_action.get('revision',0)))+1,
       'monitor_lead_minutes':1440,'action_lead_minutes':60,
       'tools':['extract_fields','request_missing_fields','submit_invitation','review_invitation','submit_minutes','review_minutes','submit_action_report','review_action','prepare_monitoring','propose_followup']}
  remove={current_meeting['id'],current_action['id']}
  tx.put(STORE,[p for p in data if p.get('id') not in remove]+[row])
  tx.audit('',actor,'SECRETARY_NATIVE_PACK_AUTO_PROMOTED',{'source_id':source_id,'pack_id':row['id'],
           'meeting_process_uid':meeting['process_uid'],'action_process_uid':action['process_uid']})
 return row

def packs(source_id,enabled_only=False):
 with agent_storage.transaction() as tx:data=tx.get(STORE,[])
 return [p for p in data if p['source_id']==source_id and (p['enabled'] or not enabled_only)]

def runtime_pack_id(source_id):
 return hashlib.sha256(('meeting-runtime-v1:'+str(source_id)).encode()).hexdigest()[:24]

def runtime_meeting_pack(source_id):
 """Return an executable typed meeting pack even before catalog promotion.

 The source must already contain both reviewed native process bindings. Native
 task ownership is still revalidated from ProcessMaker for every operation.
 """
 saved=packs(source_id,True)
 real=next((p for p in saved if p.get('adapter')=='meeting_v2'),None)
 if real:return real
 native=[p for p in saved if p.get('adapter')=='native_tasks_v1' and p.get('enabled')]
 trusted=_trusted_meeting_pack()
 by_uid={p.get('process',{}).get('process_uid'):p for p in native}
 meeting_native=by_uid.get(trusted['meeting']['process_uid'])
 action_native=by_uid.get(trusted['action']['process_uid'])
 if not meeting_native or not action_native:return None
 return {**trusted,
  'id':runtime_pack_id(source_id),'source_id':source_id,'enabled':True,
  'revision':max(int(meeting_native.get('revision',0)),int(action_native.get('revision',0)))+100000,
  'monitor_lead_minutes':int(meeting_native.get('monitor_lead_minutes',1440) or 1440),
  'action_lead_minutes':int(action_native.get('action_lead_minutes',60) or 60),
  'runtime_virtual':True,
  'source_native_pack_ids':[meeting_native['id'],action_native['id']],
  'tools':['extract_fields','request_missing_fields','submit_invitation','review_invitation',
           'submit_minutes','review_minutes','submit_action_report','review_action',
           'prepare_monitoring','propose_followup']}

def runtime_meeting_packs(source_id):
 real=[p for p in packs(source_id,True) if p.get('adapter')=='meeting_v2']
 if real:return real
 virtual=runtime_meeting_pack(source_id)
 return [virtual] if virtual else []

def get(source_id,identifier):
 found=next((p for p in packs(source_id,True) if p['id']==identifier),None)
 if found:return found
 if identifier==runtime_pack_id(source_id):
  virtual=runtime_meeting_pack(source_id)
  if virtual:return virtual
  # Existing draft/session references remain valid if catalog promotion happens
  # after the conversation started.
  real=next((p for p in packs(source_id,True) if p.get('adapter')=='meeting_v2'),None)
  if real:return {**real,'id':identifier,'runtime_virtual':True}
 raise PermissionError('بسته دبیر این فرایند فعال نیست.')

def save(source_id,pack,actor,*,identifier=None,revision=None,enabled=True,monitor_lead_minutes=1440,action_lead_minutes=60):
 from .process_workspace import native_ids
 identifiers=native_ids(pack)
 if not 0<=monitor_lead_minutes<=43200 or not 0<=action_lead_minutes<=43200:raise ValueError('فاصله یادآوری معتبر نیست.')
 with agent_storage.transaction() as tx:
  data=tx.get(STORE,[],lock=True);old=next((p for p in data if p['id']==identifier and p['source_id']==source_id),None)
  if identifier and (not old or old['revision']!=revision):raise ValueError('تنظیم فرایند تغییر کرده است؛ دوباره بارگذاری کنید.')
  if old and old.get('adapter')=='native_tasks_v1' and pack.get('adapter')=='meeting_v2' and old['process']['process_uid']!=pack['meeting']['process_uid']:
   raise ValueError('برای ارتقا، PMX جلسه باید متعلق به همان فرایند کارتابل انتخاب‌شده باشد.')
  if any(p['id']!=identifier and p['source_id']==source_id and identifiers & {v['process_uid'] for v in p.values() if isinstance(v,dict) and 'process_uid' in v} for p in data):raise ValueError('این فرایند قبلاً برای همین اتصال تنظیم شده است.')
  row={**pack,'id':identifier or secrets.token_hex(12),'source_id':source_id,'enabled':enabled,'revision':(old or {}).get('revision',0)+1,
   'monitor_lead_minutes':monitor_lead_minutes,'action_lead_minutes':action_lead_minutes,
   'tools':['extract_fields','request_missing_fields','submit_invitation','review_invitation','submit_minutes','review_minutes','submit_action_report','review_action','prepare_monitoring','propose_followup'] if pack['adapter']=='meeting_v2' else ['read_own_tasks']}
  tx.put(STORE,[p for p in data if p['id']!=row['id']]+[row]);tx.audit('',actor,'SECRETARY_PACK_CONFIGURED',{'source_id':source_id,'pack_id':row['id']})
 return row

def discover(source_id):
 from .user_bpms_bindings import processmaker_profile
 from .processmaker_store import open_production,query
 with open_production(processmaker_profile(source_id)['mysql']) as con:
  return [{'process_uid':str(r[0]),'title':str(r[1] or r[0])} for r in query(con,'SELECT PRO_UID,PRO_TITLE FROM PROCESS ORDER BY PRO_TITLE')]

def _verify_installed_on_connection(con,pack):
 from .processmaker_store import query
 for process in ('meeting','action'):
  expected=pack[process]
  actual=_installed_process(con,expected['process_uid'])
  if set(actual['stages'])!=set(expected['stages']):
   raise ValueError('مراحل PMX با فرایند نصب‌شده یکسان نیستند.')
  for name,stage in expected['stages'].items():
   installed=actual['stages'][name]
   # A matching task ID alone is insufficient: changes in field contracts,
   # trigger order, extra triggers or conditional triggers affect REST routing.
   if any(installed[key]!=stage[key] for key in ('task_uid','form_uid','fields','before','after')):
    raise ValueError('فرم یا ترتیب تریگر مرحله '+name+' با PMX یکسان نیست؛ نسخه نصب‌شده را بررسی کنید.')
  if expected.get('trigger_hashes'):
   rows=query(con,'SELECT TRI_UID,TRI_WEBBOT FROM TRIGGERS WHERE PRO_UID=%s',(expected['process_uid'],))
   hashes={str(uid):hashlib.sha256(str(code or '').replace('\r\n','\n').strip().encode()).hexdigest() for uid,code in rows}
   # Reviewed one-condition migration: blank attendance time becomes optional.
   # Accept only the exact old/new trigger code, never arbitrary code drift.
   attendance_uid='fe88e8afc98ca69585ab0f5fb16bbf74'
   attendance_hashes={'9ab0a550de738f679538b6ddf00b50c497b85b5fe514a87a0cdd55e95625e6ee', 'ffb8f021208417274b5a9b2c451a130e2f01417f129163bd4698b46fb1454873'}
   if any(hashes.get(uid)!=digest and not (uid==attendance_uid and digest in attendance_hashes and hashes.get(uid) in attendance_hashes) for uid,digest in expected['trigger_hashes'].items()):
    raise ValueError('کد تریگر نصب‌شده با PMX بازبینی‌شده یکسان نیست؛ نسخه صحیح را در ProcessMaker نصب کنید.')


def verify_installed(source_id,pack,*,con=None):
 if con is not None:
  return _verify_installed_on_connection(con,pack)
 from .user_bpms_bindings import processmaker_profile
 from .processmaker_store import open_production
 with open_production(processmaker_profile(source_id)['mysql']) as owned:
  return _verify_installed_on_connection(owned,pack)


def install_reviewed(source_id,actor,expected_revisions):
 """Explicitly activate the shipped PMX pair after checking this installation.

 Existing standalone native inboxes are replaced atomically; concurrent edits or
 unrelated adapters are rejected. This grants no user permissions or task ownership.
 """
 from pathlib import Path
 pack=json.loads(Path(__file__).with_name('secretary_pack_reference.json').read_text(encoding='utf-8'))
 pack=_compile_pair(pack['meeting'],pack['action'])
 verify_installed(source_id,pack)
 wanted={pack['meeting']['process_uid'],pack['action']['process_uid']}
 from .process_workspace import native_ids
 with agent_storage.transaction() as tx:
  data=tx.get(STORE,[],lock=True)
  previous=[p for p in data if p['source_id']==source_id and native_ids(p)&wanted]
  if {p['id']:p['revision'] for p in previous}!=expected_revisions:
   raise ValueError('تنظیم فرایند تغییر کرده است؛ صفحه را تازه‌سازی کنید.')
  if any(p['adapter'] not in ('native_tasks_v1','meeting_v2') or not native_ids(p)<=wanted for p in previous):
   raise ValueError('بسته موجود به فرایند دیگری نیز متصل است؛ جایگزینی مجاز نیست.')
  old=next((p for p in previous if pack['meeting']['process_uid'] in native_ids(p)),None)
  row={**pack,'id':old['id'] if old else secrets.token_hex(12),'source_id':source_id,
       'enabled':True,'revision':max([p['revision'] for p in previous]+[0])+1,
       'monitor_lead_minutes':(old or {}).get('monitor_lead_minutes',1440),
       'action_lead_minutes':(old or {}).get('action_lead_minutes',60),
       'tools':['extract_fields','request_missing_fields','submit_invitation','review_invitation',
                'submit_minutes','review_minutes','submit_action_report','review_action',
                'prepare_monitoring','propose_followup']}
  replaced={p['id'] for p in previous}
  tx.put(STORE,[p for p in data if p['id'] not in replaced]+[row])
  tx.audit('',actor,'SECRETARY_REVIEWED_PAIR_INSTALLED',{'source_id':source_id,'pack_id':row['id'],
           'meeting_sha256':pack['meeting']['pmx_sha256'],'action_sha256':pack['action']['pmx_sha256']})
 return row

