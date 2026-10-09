"""Bounded, stage-aware secretary orchestration. No persistence or PM writes.

Tools can inspect the current authorized snapshot or propose draft changes. Only
runtime commit/submit services may persist or advance a workflow. Receipts describe
observable operations, never private model reasoning.
"""
from dataclasses import dataclass
import copy
import re
import time
from . import secretary_time,secretary_coverage


@dataclass(frozen=True)
class Tool:
    name: str
    label: str
    effect: str
    handler: object


class TurnResult(tuple):
    def __new__(cls, values, questions, reply, intent, pending, receipt):
        result=super().__new__(cls,(values,questions,reply,intent,pending))
        result.receipt=receipt
        return result


def _confirmation(r,c):
    pending=c['pending']
    if not pending:
        last=next((str(x.get('text') or '') for x in reversed(c['history'])
                   if isinstance(x,dict) and x.get('role')=='assistant'),'')
        if last:
            pending=r.resolution.propose_identity_confirmation(last,c['current'],
                r.gaps(c['current'],c['task']),c['scope'].get('directory',{}))
    c['pending']=pending
    return r.resolution.resolve_pending(c['notes'],c['current'],c['questions'],pending,
                                        c['scope'].get('directory',{}))


def _identity(r,c):
    return r.resolution.resolve_direct_identity(c['notes'],c['current'],c['questions'],
        r.gaps(c['current'],c['task']),c['scope'].get('directory',{}),history=c['history'])


def _commands(r,c):
    return r.commands.apply(c['notes'],c['current'],c['task'],c['scope'],
                            questions=c['questions'],history=c['history'])


def _inspect(r,c):
    raw=r._intent_text(c['notes']).rstrip('؟?!. ')
    if len(raw)>180:return None
    state=None;reply=None
    if any(x in raw for x in ('چرا ارور','چرا خطا','چرا ارو')):
        previous=next((str(x.get('text') or '') for x in reversed(c['history']) if isinstance(x,dict) and x.get('role')=='assistant'),'')
        reply=('در پاسخ قبلی نتوانستم تغییر را با اطمینان ثبت کنم. '+previous) if 'نتوانستم' in previous else 'ممکن است درخواست قبلی در پردازش یا ارسال رد شده باشد؛ نبود آن در تاریخچه به معنی نبود خطا نیست. متن پیام را اصلاح و دوباره ارسال کنید؛ برای خطای ارسال پرونده ابتدا وضعیت پرونده را تازه کنید.'
    if any(x in raw for x in ('کجا گیریم','کجا گیر کردیم','کجا هستیم','کجا موندی','کجا ماندی',
        'چی مونده','چی باقی مونده','چی باقی مانده','چه چیزی مونده','چه چیزی باقی مونده',
        'چه چیزی باقی مانده','چه چیزهایی مونده','چه چیزهایی باقی مونده','چه مواردی باقی مونده',
        'چه مواردی باقی مانده','مرحله بعد چیه','مرحله بعد چیست')):
        missing=r.gaps(c['current'],c['task'])
        state=r.assistant_state(c['current'],c['task'],c['scope'],c['questions'])
        reply=('این مرحله کامل است و مورد اجباری باز نداریم. '+state['message']) if not missing else (
            'الان روی «'+r.STAGE_LABELS.get(c['task']['stage'],c['task']['stage'])+'» هستیم. مورد بعدی: '+missing[0]['question']+
            (' بعد از آن '+str(len(missing)-1)+' مورد ضروری دیگر باقی می‌ماند.' if len(missing)>1 else ''))
    elif raw in ('خلاصه بده','خلاصه جلسه','خلاصه را بگو','خلاصه رو بگو','خلاصه اقدامات','فهرست اقدامات','چه اطلاعاتی ثبت شده'):
        state=r.assistant_state(c['current'],c['task'],c['scope'],c['questions'])
        reply=state['summary'] or 'هنوز اطلاعاتی برای خلاصه‌کردن در این مرحله ثبت نشده است.'
    elif raw in ('چه کارهایی میتونی انجام بدی','چه کارهایی می توانی انجام بدهی','راهنما','چه کمکی میکنی','چه کمکی می کنی'):
        reply='در این پرونده می‌توانم اطلاعات جلسه را از متن، صوت و فایل دریافت کنم، اطلاعات ثبت‌شده را توضیح بدهم و پیش‌نویس همین مرحله را اصلاح کنم. در صورت‌جلسه، می‌توانم مسئولان را از افراد شناخته‌شده تعیین کنم و با درخواست شما برای حاضران اقدام و مهلت بسازم. می‌توانید بگویید «خلاصه بده» یا «کجا گیریم؟». ارسال به مرحله بعد فقط با دستور صریح شما انجام می‌شود.'
    elif 'ردیف' in raw and any(x in raw for x in ('چیه','چیست','کدام','کدوم','موضوعش')):
        match=re.search(r'ردیف\s*(\d+)',raw)
        agenda={**c['task'].get('native',{}),**c['current']}.get('MTG_Agenda') or {}
        if not match:
            last=next((str(x.get('text') or '') for x in reversed(c['history']) if isinstance(x,dict) and x.get('role')=='assistant'),r.assistant_state(c['current'],c['task'],c['scope'],c['questions'])['message'])
            match=re.search(r'دستور جلسه ردیف\s*(\d+)',last)
        if not match and isinstance(agenda,dict) and len(agenda)==1:
            match=re.search(r'(\d+)',str(next(iter(agenda))))
        if match and isinstance(agenda,dict):
            number=str(int(match.group(1)));row=agenda.get(number)
            if row:
                reply='موضوع ردیف '+number+' دستور جلسه: «'+str(row.get('MTG_AgendaTitle') or 'هنوز ثبت نشده')+'».'
                if row.get('MTG_AgendaPlannedMinutes'):reply+=' زمان ارائه: '+str(row['MTG_AgendaPlannedMinutes'])+' دقیقه.'
                presenter=row.get('MTG_AgendaPresenterUID')
                reply+=(' ارائه‌دهنده: '+r._person(presenter,c['scope'])+'.') if presenter else ' ارائه‌دهنده این ردیف هنوز مشخص نشده؛ چه کسی ارائه می‌کند؟'
    if reply is None:return None
    return dict(values=copy.deepcopy(c['current']),questions=list(c['questions']),reply=reply,
                intent='question',pending_confirmation=c['pending'])


def _extract(r,c):
    try:
        values,questions,reply,intent=r.extract(c['notes'],c['task'],c['current'],c['scope'],
            questions=c['questions'],history=c['history'],with_reply=True)
    except (r.AgentInvalid,ValueError):
        missing=r.gaps(c['current'],c['task'])
        hint=missing[0]['question'] if missing else 'نام بخش و مقدار جدید را در یک جمله بگویید؛ مثلاً «خلاصه بحث را به ... تغییر بده».'
        return dict(values=copy.deepcopy(c['current']),questions=list(c['questions']),
            reply='پس از سه بار بررسی، نتوانستم تغییر این پیام را با اطمینان ثبت کنم؛ اطلاعات قبلی محفوظ است. لطفاً درخواست را با نام فرد یا ردیف و مقدار موردنظر بفرستید.\n'+hint,
            intent='question',pending_confirmation=c['pending'])
    except r.AgentUnavailable as exc:
        return dict(values=copy.deepcopy(c['current']),questions=list(c['questions']),
            reply='نتوانستم این پیام را پردازش کنم؛ پیش‌نویس قبلی محفوظ است. '+str(exc)+'\nمی‌توانید پیام را دوباره ارسال کنید یا اطلاعات را در فرم زیر اصلاح و ذخیره کنید.',
            intent='question',pending_confirmation=c['pending'])
    pending=r.resolution.propose_identity_confirmation(reply,values,r.gaps(values,c['task']),c['scope'].get('directory',{}))
    return dict(values=values,questions=questions,reply=reply,intent=intent,pending_confirmation=pending)


TOOLS=(Tool('confirmation.resolve','تفسیر پاسخ به سؤال قبلی','draft',_confirmation),
       Tool('temporal.resolve','تشخیص تاریخ، ساعت و حضور','draft',lambda r,c:secretary_time.apply(r,c)),
       Tool('identity.resolve','تطبیق فرد با کاربران همین اتصال','draft',_identity),
       Tool('draft.command','اجرای فرمان روی پیش‌نویس','draft',_commands),
       Tool('draft.inspect','خواندن اطلاعات همین پرونده','read',_inspect),
       Tool('draft.extract','استخراج اطلاعات پیام','draft',_extract))


def run(runtime,notes,task,current,scope,*,questions=(),pending_confirmation=None,history=()):
    if not isinstance(notes,str) or not notes.strip() or len(notes)>18000:
        raise ValueError('پیام باید بین ۱ تا ۱۸ هزار نویسه باشد.')
    if task.get('stage') not in runtime.STAGE_LABELS:
        raise ValueError('مرحله فرایند برای دبیر شناخته‌شده نیست.')
    c=dict(notes=notes,task=task,current=copy.deepcopy(current),scope=scope,
           questions=list(questions),pending=pending_confirmation,history=list(history or [])[-40:])
    started=time.monotonic()
    # High-density invitation messages must be read as one semantic unit. A
    # partial deterministic match (for example the first date) must never stop
    # the rest of the message from reaching exhaustive structured extraction.
    tools=TOOLS
    if secretary_coverage.is_compound_invitation(notes,task):
        tools=(TOOLS[0],TOOLS[-1])  # confirmation, then full extraction
    for tool in tools:
        result=tool.handler(runtime,c)
        if result is None:continue
        values=result['values'];intent=result.get('intent','resolved')
        if tool.effect=='read' or intent=='question':
            # A question can never smuggle assignments into a draft mutation.
            values=copy.deepcopy(current)
        elif values!=current:
            allowed=runtime.form(task)
            # Historical snapshots may also carry native read-only context.
            # Validate writable state and every changed key, never treat an
            # unchanged contextual field as a proposed mutation.
            runtime.validate({k:v for k,v in values.items()
                              if k in allowed or current.get(k)!=v},task,scope)
        reply=result['reply'];remaining=result['questions']
        if tool.name in ('confirmation.resolve','identity.resolve','draft.command','temporal.resolve'):
            state=runtime.assistant_state(values,task,scope,remaining)
            if state['message'] and state['message'] not in reply and (intent!='question' or state['missing']):
                reply+='\n\n'+state['message']
        receipt={'version':1,'tool':tool.name,'label':tool.label,'effect':'draft' if values!=current else 'read',
                 'model_used':tool.name=='draft.extract','elapsed_ms':round((time.monotonic()-started)*1000)}
        return TurnResult(values,remaining,reply,intent,result.get('pending_confirmation'),receipt)
    raise RuntimeError('No secretary tool handled the turn')
