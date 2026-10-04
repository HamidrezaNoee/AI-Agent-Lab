"""Admin-registered, source-specific secretary packs compiled from reviewed PMX."""
from __future__ import annotations
import hashlib,json,re,secrets
import xml.etree.ElementTree as ET
from . import agent_storage
from .secretary_workflow import CONTRACT,WRITE_FIELDS

STORE='secretary_packs_v2'
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
     if v.get('type')=='grid':spec['columns']=[{k:c.get(k) for k in ('id','label','type','options')} for c in v.get('columns',[])]
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
 return {'process_uid':process,'title':metadata.get('name',process),'pmx_sha256':hashlib.sha256(xml.encode()).hexdigest(),'stages':stages}

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
     spec['columns']=[{k:c.get(k) for k in ('id','label','type','options')} for c in v.get('columns',[])]
    fields[v['variable']]=spec
   for a in v.values():walk(a)
  elif isinstance(v,list):
   for a in v:walk(a)
 try:walk(json.loads(content))
 except (ValueError,RecursionError,TypeError) as exc:raise ValueError('تعریف فرم نصب‌شده ProcessMaker معتبر نیست.') from exc
 return fields

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
 """Built-in typed descriptor for the reviewed Iran Rover meeting/action PMX pair.

 The meeting form field contract is already shipped as secretary_pmx.json.
 Only the minimal editable action fields are declared here; native context
 variables remain readable from APP_DATA and are never user-writable.
 """
 from pathlib import Path
 contract=json.loads(Path(__file__).with_name('secretary_pmx.json').read_text(encoding='utf-8'))
 forms=contract.get('forms') or {}
 def by_prefix(prefix):
  found=[v for k,v in forms.items() if re.match(re.escape(prefix)+r'(?:\\s|[-–]|$)',k)]
  if len(found)!=1:raise ValueError('قرارداد فرم داخلی مدیریت جلسات ناقص است.')
  return found[0]
 meeting_meta={
  'invitation':('4a6419a60141d7d36001ba9344db4eac','1b4a9033de82d5d38afb8a471d4bd5b1',['8bfb9a18e7b6d6ae82441e22101b7909'],['7c9d0f8ea4e54f92b1f7931fb6f97a01'],'FR-MTG-001'),
  'invitation_approval':('f040c82fd83e47fd908770b62d967384','7774ba689f3c4c46b3d5efaa55fde907',[],['2cce620239ad07d5d415eedee1916175'],'FR-MTG-002'),
  'minutes':('a07e9ed93a4b3244aca40996c45eb227','5e84e43db54993a49119997cb0b5df34',['575a453b1e1dc60a52f64edf2c0a57f0','7942584696aa92ab223c498087838907'],['fe88e8afc98ca69585ab0f5fb16bbf74'],'FR-MTG-003'),
  'minutes_approval':('af8402c57b05992f6b6e6c6d9eb5276a','366ac686c45b9ecc2ad8c41a00846db7',['575a453b1e1dc60a52f64edf2c0a57f0','09a5c128a12a358797021feb3e8b2ab8'],['2593597a9d5a6de465784bf8dc338439'],'FR-MTG-004'),
  'monitoring':('cb9f098d6b9462db552ae29d4622950a','d30094992baf2ab00fce7f558ba7160a',['575a453b1e1dc60a52f64edf2c0a57f0','408334d60c9cca3317668fba26f7e8b5'],['9cfa2876edd7cfa8fa5016a2f25f771d'],'FR-MTG-005'),
 }
 meeting_stages={}
 for stage,(task_uid,form_uid,before,after,prefix) in meeting_meta.items():
  meeting_stages[stage]={'task_uid':task_uid,'task_title':stage,'form_uid':form_uid,
                         'fields':by_prefix(prefix),'before':before,'after':after}

 def spec(label,kind='text',required=False,options=None,mode='edit'):
  return {'label':label,'type':kind,'required':required,'options':options,'mode':mode}
 action_stages={
  'action_execution':{
   'task_uid':'473bb4e227460a3ea6ac0f2cbf8ef8d4',
   'task_title':'اجرای اقدام',
   'form_uid':'a6f690be582466ab0c0ad6649ba8b93f',
   'before':['290a2731cf20d1515dc2e8202b9fc94e'],
   'after':['a4f666dadb04c365e1762e0b33495692'],
   'fields':{
    'MTGA_SubmissionType':spec('نوع ارسال','dropdown',True,[{'value':'ProgressUpdate','label':'گزارش پیشرفت'},{'value':'CompletionClaim','label':'اعلام تکمیل اقدام'}]),
    'MTGA_ProgressPercent':spec('درصد پیشرفت اعلامی','text',True),
    'MTGA_ExecutionDescription':spec('شرح اقدام انجام‌شده / گزارش پیشرفت','textarea'),
    'MTGA_ActualCompletionDateTime':spec('تاریخ واقعی انجام (در صورت تکمیل)'),
    'MTGA_ActualCompletionTime':spec('ساعت واقعی انجام (در صورت تکمیل)'),
    'MTGA_ActualEffortMinutes':spec('زمان واقعی صرف‌شده (دقیقه)'),
   }},
  'action_review':{
   'task_uid':'1bc65198c9b4cf2fae5d3ffbfeea3c00',
   'task_title':'بررسی اقدام توسط دبیر جلسه',
   'form_uid':'42ba129e30d6f03e685e81a4301cdaa4',
   'before':['8666274ec4af8ae2eab09a4af385b4d5'],
   'after':['b12993814458ae485790da734d84eb38'],
   'fields':{
    'MTGA_ReviewStatus2':spec('نتیجه بررسی','dropdown',True,[{'value':'Closed','label':'تأیید و بستن اقدام'},{'value':'Rework','label':'بازگشت برای اصلاح / ادامه اقدام'}]),
    'MTGA_SecretaryProgressPercent2':spec('درصد پیشرفت تأییدشده توسط دبیر','text',True),
    'MTGA_SecretaryActualCompletionDateTime2':spec('تاریخ واقعی مورد تأیید دبیر'),
    'MTGA_SecretaryActualCompletionTime2':spec('ساعت واقعی مورد تأیید دبیر'),
    'MTGA_SecretaryActualEffortMinutes2':spec('زمان واقعی تأییدشده (دقیقه)'),
    'MTGA_SecretaryComment1':spec('نظر دبیر جلسه','textarea'),
   }},
 }
 meeting={'process_uid':'f7f263ea31d8731d212820f220c65a48','title':'فرایند مدیریت جلسات',
          'pmx_sha256':contract.get('pmx_sha256','builtin'),'stages':meeting_stages}
 action={'process_uid':'cd66870095907431106b6dd110e06fa7','title':'فرایند اقدام مصوب جلسه',
         'pmx_sha256':'trusted-action-pmx-v7','stages':action_stages}
 return _compile_pair(meeting,action)

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
 try:
  trusted=_trusted_meeting_pack()
  by_uid={p.get('process',{}).get('process_uid'):p for p in native}
  if trusted['meeting']['process_uid'] in by_uid and trusted['action']['process_uid'] in by_uid:
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
 except ValueError:
  # Fall through to generic installed-schema discovery for any other compatible pair.
  pass

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
 if len(meetings)!=1 or len(actions)!=1:return None
 meeting_native,meeting=meetings[0][1],meetings[0][2]
 action_native,action=actions[0][1],actions[0][2]
 try:pack=_compile_pair(meeting,action)
 except ValueError:return None

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

def get(source_id,identifier):
 found=next((p for p in packs(source_id,True) if p['id']==identifier),None)
 if not found:raise PermissionError('بسته دبیر این فرایند فعال نیست.')
 return found

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

def verify_installed(source_id,pack):
 from .user_bpms_bindings import processmaker_profile
 from .processmaker_store import open_production,query
 with open_production(processmaker_profile(source_id)['mysql']) as con:
  for process in ('meeting','action'):
   p=pack[process];tasks={str(r[0]) for r in query(con,'SELECT TAS_UID FROM TASK WHERE PRO_UID=%s',(p['process_uid'],))}
   if not {s['task_uid'] for s in p['stages'].values()}<=tasks:raise ValueError('وظایف PMX با فرایند نصب‌شده این اتصال مطابقت ندارند.')
   for s in p['stages'].values():
    steps=query(con,'SELECT STEP_UID FROM STEP WHERE TAS_UID=%s AND STEP_UID_OBJ=%s',(s['task_uid'],s['form_uid']))
    if len(steps)!=1:raise ValueError('فرم PMX در فرایند نصب‌شده پیدا نشد.')
    installed=query(con,'SELECT TRI_UID,ST_TYPE FROM STEP_TRIGGER WHERE STEP_UID=%s',(steps[0][0],))
    actual={(str(r[0]),str(r[1])) for r in installed}
    if not {(t,'AFTER') for t in s['after']}|{(t,'BEFORE') for t in s['before']}<=actual:raise ValueError('تریگرهای PMX با سرور یکسان نیستند.')
