"""Bounded PM 3.2 REST transport. No database writes or automatic retries."""
import logging,re,time
import httpx
from fastapi import HTTPException
from .user_bpms_bindings import processmaker_profile
from .setup_routes import _pm_target,_pm_profile_refresh,_pm_profiles_state
from .secretary_workflow import CONTRACT,PLAN,MINUTES,MONITOR

AFTER={PLAN:'7c9d0f8ea4e54f92b1f7931fb6f97a01',MINUTES:'fe88e8afc98ca69585ab0f5fb16bbf74',MONITOR:'9cfa2876edd7cfa8fa5016a2f25f771d'}
BEFORE_MONITOR='408334d60c9cca3317668fba26f7e8b5'
logger=logging.getLogger(__name__)

def _repair_mojibake(value):
 """Repair the common UTF-8→Windows-1252/Latin-1 mojibake returned by old PM/PHP stacks."""
 text=str(value or "")
 if not text:return ""
 def score(s):
  persian=sum(1 for ch in s if "\u0600"<=ch<="\u06ff")
  junk=sum(s.count(x) for x in ("Ø","Ù","Û","Ã","Â","�"))
  return persian*4-junk*3
 # Legacy PHP responses can mix cp1252 characters with Latin-1 controls.
 reverse={}
 for byte in range(256):
  try:reverse[bytes([byte]).decode('cp1252')]=byte
  except UnicodeDecodeError:pass
 def repair(match):
  raw=match.group()
  try:
   data=bytes(ord(ch) if ord(ch)<256 else reverse[ch] for ch in raw)
   candidate=data.decode('utf-8')
  except (KeyError,ValueError,UnicodeDecodeError):return raw
  return candidate if score(candidate)>score(raw) else raw
 pattern='['+re.escape(''.join(set(chr(i) for i in range(256))|set(reverse)))+']+'
 for _ in range(2):
  updated=re.sub(pattern,repair,text)
  if updated==text:break
  text=updated
 return text

class PMRejected(HTTPException):
 def __init__(self,operation,status,message=''):
  self.operation=str(operation or 'عملیات ProcessMaker')
  self.upstream_status=int(status)
  self.upstream_message=_repair_mojibake(message)
  detail=f'ProcessMaker عملیات «{self.operation}» را نپذیرفت (HTTP {self.upstream_status})'
  if self.upstream_message:detail+=': '+self.upstream_message
  if 'ساعت حضور' in self.upstream_message:detail+=' اگر ساعتی وارد کرده‌اید، قالب آن باید HH:mm باشد. اگر ساعت خالی است، Trigger نصب‌شده هنوز شرط قدیمی را دارد و باید اصلاح «ساعت حضور اختیاری» در ProcessMaker اعمال شود.'
  super().__init__(502,detail)

def uid(value):
 if not re.fullmatch(r'[a-zA-Z0-9]{32}',str(value)):raise ValueError('شناسه پرونده معتبر نیست.')
 return value

class PM:
 def __init__(self,source_id,*,process_uid=None,bearer=None):
  profile=processmaker_profile(source_id);api=profile.get('api') or {}
  if not bearer and api.get('token_managed') and float(api.get('access_token_expires_at') or 0)<=time.time()+90:
   profile=_pm_profile_refresh(profile,_pm_profiles_state());api=profile['api']
  base,workspace=_pm_target(api.get('base_url',''),api.get('workspace',''))
  if not bearer and not api.get('bearer_token'):raise HTTPException(409,'توکن API پروسس‌میکر تنظیم نشده است.')
  self.process_uid=process_uid or CONTRACT['process_uid']
  self.base=base+'/api/1.0/'+workspace
  self.client=httpx.Client(timeout=20,follow_redirects=False,trust_env=False,
    headers={'Authorization':'Bearer '+(bearer or api['bearer_token'])})
 def close(self):self.client.close()
 def call(self,method,path,data=None,*,operation=None):
  label=str(operation or 'عملیات ProcessMaker')
  try:
   r=self.client.request(method,self.base+path,**({'json':data} if data is not None else {}))
   if not 200<=r.status_code<300:
    message=''
    try:
     body=r.json()
     if isinstance(body,dict):
      err=body.get('error')
      if isinstance(err,dict):message=str(err.get('message') or err.get('code') or body.get('message') or '')
      elif err:message=str(err)
      elif body.get('message'):message=str(body.get('message'))
     elif body:message=str(body)
    except Exception:
     message=''
    if not message:
     try:
      raw=r.text or ''
      raw=re.sub(r'<[^>]+>',' ',raw)
      message=re.sub(r'\s+',' ',raw).strip()
     except Exception:
      message=''
    safe=re.sub(r'[\r\n\t]+',' ',_repair_mojibake(message)).strip()[:360]
    if re.search(r'(?i)(authorization|bearer|access[_ -]?token|refresh[_ -]?token|client[_ -]?secret|password)\s*[:=]',safe):
     safe=''
    logger.warning('ProcessMaker rejected operation=%s method=%s path=%s status=%s message=%s',
                   label,method,path,r.status_code,safe or '-')
    low=safe.casefold()
    if 'mtg_meeting_sequence' in low and ("doesn't exist" in low or 'does not exist' in low):
     raise HTTPException(409,'زیرساخت شماره‌گذاری جلسات ProcessMaker آماده نیست: جدول MTG_MEETING_SEQUENCE در دیتابیس Workspace وجود ندارد.')
    raise PMRejected(label,r.status_code,safe)
   result=r.json() if r.content else {}
   if isinstance(result,dict) and result.get('error'):
    logger.warning('ProcessMaker returned error object operation=%s method=%s path=%s',label,method,path)
    raise HTTPException(502,f'ProcessMaker در عملیات «{label}» خطای فرایندی برگرداند.')
   return result
  except HTTPException:
   raise
  except (httpx.HTTPError,ValueError) as exc:
   logger.warning('ProcessMaker transport failure operation=%s method=%s path=%s type=%s',
                  label,method,path,exc.__class__.__name__)
   raise HTTPException(502,f'پاسخ عملیات «{label}» مشخص نیست؛ پیش از تکرار، همان پرونده در ProcessMaker بررسی شود.') from exc
 def info(self,case):
  result=self.call('GET','/cases/'+uid(case),operation='خواندن وضعیت پرونده')
  if result.get('pro_uid')!=getattr(self,'process_uid',CONTRACT['process_uid']):raise PermissionError('Wrong process')
  return result
 def variables(self,case):return self.call('GET','/cases/'+uid(case)+'/variables',operation='خواندن متغیرهای پرونده')
 def assigned(self,case,task,person):
  found=[t for t in self.info(case).get('current_task',[]) if t.get('tas_uid')==task and t.get('usr_uid')==person and t.get('del_thread_status')=='OPEN']
  if len(found)!=1:raise ValueError('مرحله دبیر به کاربر متصل فعلی تخصیص ندارد یا تغییر کرده است.')
  return int(found[0]['del_index'])
 def new(self,person,values):
  result=self.call('POST','/cases/impersonate',{'pro_uid':CONTRACT['process_uid'],'tas_uid':PLAN,'usr_uid':uid(person),'variables':[values]},operation='ایجاد پرونده با جانشینی کاربر')
  return uid(result['app_uid'])
 def submit(self,case,task,person,values):
  index=self.assigned(case,task,person)
  self.call('PUT',f'/cases/{uid(case)}/variable?del_index={index}',values,operation='ثبت متغیرهای پرونده')
  # Dynaform AFTER triggers do not fire merely by setting variables via REST.
  # Execute only the exact secretary-stage trigger from the selected PMX.
  self.call('PUT',f'/cases/{uid(case)}/execute-trigger/{AFTER[task]}',operation='اجرای Trigger بعد از فرم')
  self.call('PUT',f'/cases/{uid(case)}/route-case',{'del_index':str(index)},operation='ارسال پرونده به مرحله بعد')

 def create_for(self,task,values):
  result=self.call('POST','/cases',{'pro_uid':self.process_uid,'tas_uid':uid(task),'variables':[values]},operation='ایجاد پرونده')
  return uid(result['app_uid'])
 def set_variables(self,case,index,values,*,operation='ثبت اطلاعات فرم'):
  return self.call('PUT',f'/cases/{uid(case)}/variable?del_index={int(index)}',values,operation=operation)
 def upload_input_document(self,case,input_doc_uid,field_name,filename,data,content_type='application/octet-stream',comment=''):
  """Upload one DynaForm File/multipleFile value through ProcessMaker Light API.

  PM3 file controls use a two-step protocol:
  1) POST /light/case/{app_uid}/upload creates APP_DOCUMENT with DOC_UID and
     APP_DOC_FIELDNAME.
  2) POST /light/case/{app_uid}/upload/{app_doc_uid} sends multipart bytes.

  This works for DynaForm file controls even when the Input Document is not a
  STEP on the current task. AVAN never writes ProcessMaker tables directly.
  """
  case=uid(case);input_doc_uid=uid(input_doc_uid)
  field=str(field_name or '').strip()
  if not re.fullmatch(r'[A-Za-z0-9_]{1,120}',field):
   raise ValueError('نام متغیر فایل ProcessMaker معتبر نیست.')
  name=str(filename or 'document').replace('\\','/').split('/')[-1].strip()
  if not name or len(name)>240 or any(ord(ch)<32 for ch in name):
   raise ValueError('نام فایل معتبر نیست.')
  if not isinstance(data,(bytes,bytearray)) or not data:
   raise ValueError('فایل خالی است.')
  mime=str(content_type or 'application/octet-stream')[:160]

  # First phase is a normal JSON API mutation and creates the native document
  # record with the exact DynaForm field name.
  created=self.call(
   'POST',f'/light/case/{case}/upload',
   [{'name':name,'appDocType':'INPUT','docUid':input_doc_uid,'fieldName':field}],
   operation='ایجاد رکورد فایل فرم ProcessMaker')
  if not isinstance(created,list) or len(created)!=1 or not isinstance(created[0],dict):
   raise HTTPException(502,'ProcessMaker رکورد معتبر برای فایل فرم ایجاد نکرد.')
  record=created[0]
  app_doc_uid=str(record.get('appDocUid') or '')
  if not re.fullmatch(r'[a-zA-Z0-9]{32}',app_doc_uid):
   raise HTTPException(502,'ProcessMaker شناسه معتبر برای فایل فرم برنگرداند.')

  # PHP expects $_FILES["form"]["name"][<DynaForm variable>]. Using the nested
  # multipart key below yields that exact shape.
  try:
   response=self.client.post(
    self.base+f'/light/case/{case}/upload/{app_doc_uid}',
    files={f'form[{field}]':(name,bytes(data),mime)},
   )
  except httpx.HTTPError as exc:
   logger.warning('ProcessMaker file upload transport failure app_doc_uid=%s type=%s',
                  app_doc_uid,exc.__class__.__name__)
   raise HTTPException(
    502,'رکورد فایل در ProcessMaker ایجاد شد اما انتقال محتوای فایل نامشخص ماند؛ '
        'پیش از تکرار، همان پرونده را بررسی کنید.') from exc

  if not 200<=response.status_code<300:
   logger.warning('ProcessMaker rejected file bytes app_doc_uid=%s status=%s',
                  app_doc_uid,response.status_code)
   if response.status_code==413:
    raise HTTPException(413,'حجم فایل از محدودیت تعریف‌شده در ProcessMaker بیشتر است.')
   if response.status_code==415:
    raise HTTPException(415,'نوع یا پسوند فایل با تنظیم Input Document در ProcessMaker سازگار نیست.')
   if response.status_code in (401,403):
    raise HTTPException(403,'حساب متصل ProcessMaker مجوز بارگذاری این فایل را ندارد.')
   raise HTTPException(
    502,'رکورد فایل در ProcessMaker ایجاد شد اما ProcessMaker محتوای فایل را نپذیرفت؛ '
        'پیش از تکرار، همان پرونده را بررسی کنید.')

  try:uploaded=response.json() if response.content else {}
  except ValueError:
   uploaded={}
  if isinstance(uploaded,dict) and uploaded.get('status') not in (None,'ok','OK',True):
   raise HTTPException(
    502,'ProcessMaker رکورد فایل را ایجاد کرد اما تکمیل بارگذاری را تأیید نکرد؛ '
        'پیش از تکرار، همان پرونده را بررسی کنید.')

  return {
   'app_doc_uid':app_doc_uid,
   'app_doc_version':record.get('docVersion') or 1,
   'app_doc_filename':record.get('appDocFilename') or name,
   'app_doc_type':record.get('appDocType') or 'INPUT',
   'app_doc_create_date':record.get('appDocCreateDate'),
   'app_doc_create_user':record.get('appDocCreateUser'),
   'app_doc_index':record.get('appDocIndex'),
   'doc_uid':input_doc_uid,
   'field_name':field,
  }

 def execute_trigger(self,case,trigger,*,operation='اجرای Trigger'):
  return self.call('PUT',f'/cases/{uid(case)}/execute-trigger/{uid(trigger)}',operation=operation)
 def route(self,case,index):
  # ProcessMaker 3.3.x validates route-case del_index as an alphanumeric
  # request value; JSON numeric values are rejected by some builds.
  return self.call('PUT',f'/cases/{uid(case)}/route-case',{'del_index':str(int(index))},operation='ارسال پرونده به مرحله بعد')
 def submit_stage(self,case,stage,person,values,expected_index):
  index=self.assigned(case,stage['task_uid'],person)
  if index!=expected_index:raise ValueError('نسخه وظیفه در فرایند تغییر کرده است.')
  try:
   self.set_variables(case,index,values,operation='ثبت نهایی اطلاعات مرحله')
  except Exception as exc:
   try:exc.pm_phase='variables'
   except Exception:pass
   raise
  for trigger in stage['after']:
   try:
    self.execute_trigger(case,trigger,operation='اجرای Trigger بعد از فرم')
   except Exception as exc:
    try:
     exc.pm_phase='after_trigger'
     exc.pm_trigger=trigger
    except Exception:pass
    raise
  try:
   self.route(case,index)
  except Exception as exc:
   try:exc.pm_phase='route'
   except Exception:pass
   raise

