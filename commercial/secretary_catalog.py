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

def compile_pack(meeting_xml,action_xml):
 meeting,action=parse_pmx(meeting_xml),parse_pmx(action_xml)
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
