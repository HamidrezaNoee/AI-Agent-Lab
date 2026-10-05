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
     err=body.get('error') if isinstance(body,dict) else None
     if isinstance(err,dict):message=str(err.get('message') or err.get('code') or '')
     elif err:message=str(err)
    except Exception:
     message=''
    safe=re.sub(r'[\r\n\t]+',' ',message).strip()[:240]
    logger.warning('ProcessMaker rejected operation=%s method=%s path=%s status=%s message=%s',
                   label,method,path,r.status_code,safe or '-')
    low=safe.casefold()
    if 'mtg_meeting_sequence' in low and ("doesn't exist" in low or 'does not exist' in low):
     raise HTTPException(409,'زیرساخت شماره‌گذاری جلسات ProcessMaker آماده نیست: جدول MTG_MEETING_SEQUENCE در دیتابیس Workspace وجود ندارد.')
    raise HTTPException(502,f'ProcessMaker عملیات «{label}» را نپذیرفت (HTTP {r.status_code}).')
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
  self.call('PUT',f'/cases/{uid(case)}/route-case',{'del_index':index},operation='ارسال پرونده به مرحله بعد')

 def create_for(self,task,values):
  result=self.call('POST','/cases',{'pro_uid':self.process_uid,'tas_uid':uid(task),'variables':[values]},operation='ایجاد پرونده')
  return uid(result['app_uid'])
 def set_variables(self,case,index,values,*,operation='ثبت اطلاعات فرم'):
  return self.call('PUT',f'/cases/{uid(case)}/variable?del_index={int(index)}',values,operation=operation)
 def execute_trigger(self,case,trigger,*,operation='اجرای Trigger'):
  return self.call('PUT',f'/cases/{uid(case)}/execute-trigger/{uid(trigger)}',operation=operation)
 def route(self,case,index):
  return self.call('PUT',f'/cases/{uid(case)}/route-case',{'del_index':int(index)},operation='ارسال پرونده به مرحله بعد')
 def submit_stage(self,case,stage,person,values,expected_index):
  index=self.assigned(case,stage['task_uid'],person)
  if index!=expected_index:raise ValueError('نسخه وظیفه در فرایند تغییر کرده است.')
  self.set_variables(case,index,values,operation='ثبت نهایی اطلاعات مرحله')
  for trigger in stage['after']:
   self.execute_trigger(case,trigger,operation='اجرای Trigger بعد از فرم')
  self.route(case,index)
