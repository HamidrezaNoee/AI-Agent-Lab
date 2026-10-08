"""Persian date/time and attendance tools; punctuation is semantic data."""
import copy
import re
import jdatetime
from . import secretary_resolution as resolution

MONTHS=('فروردین','اردیبهشت','خرداد','تیر','مرداد','شهریور','مهر','آبان','آذر','دی','بهمن','اسفند')
DIGITS=str.maketrans('۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩','01234567890123456789')


def digits(text):return str(text or '').translate(DIGITS)


def has_date(text):
    raw=digits(text)
    return any(re.search(r'(?<![آ-ی])'+month+r'(?![آ-ی])',raw) for month in MONTHS) or bool(re.search(r'\d{4}[/\-]\d{1,2}[/\-]\d{1,2}',raw))


def jalali_date(text):
    raw=digits(text)
    match=re.search(r'(?<!\d)(1[34]\d{2})[/\-](\d{1,2})[/\-](\d{1,2})(?!\d)',raw)
    if match:y,m,d=map(int,match.groups())
    else:
        match=re.search(r'(?<!\d)(\d{1,2})\s+('+'|'.join(MONTHS)+r')\s+(1[34]\d{2})(?!\d)',raw)
        if not match:return None
        d=int(match[1]);m=MONTHS.index(match[2])+1;y=int(match[3])
    try:return jdatetime.date(y,m,d).strftime('%Y/%m/%d')
    except ValueError:raise ValueError('این تاریخ شمسی معتبر نیست؛ روز، ماه و سال را بررسی کنید.')


def clock(text,allow_bare=False):
    raw=digits(text).strip()
    if has_date(raw):return None
    # Never turn 17:30 into 17:00, or 17:99 into a valid-looking hour.
    match=re.search(r'(?<!\d)(\d{1,2}):([0-9]{2})(?!\d)',raw)
    if ':' in raw:
        if not match or int(match[1])>23 or int(match[2])>59:return None
        return f'{int(match[1]):02d}:{int(match[2]):02d}'
    normalized=resolution.normalize_text(raw)
    if not allow_bare and not any(x in normalized for x in ('ساعت','صبح','ظهر','عصر','شب')):return None
    match=re.search(r'(?<!\d)(\d{1,2})(?!\d)',raw)
    if match:hour=int(match[1])
    else:
        words={'یک':1,'دو':2,'سه':3,'چهار':4,'پنج':5,'شش':6,'هفت':7,'هشت':8,'نه':9,'ده':10,'یازده':11,'دوازده':12}
        word=next((x for x in words if re.search(r'\b'+x+r'\b',normalized)),None)
        if not word:return None
        hour=words[word]
    if not 0<=hour<=23:return None
    if any(x in normalized for x in ('عصر','شب','بعد از ظهر')) and 1<=hour<12:hour+=12
    if 'صبح' in normalized and hour==12:hour=0
    minute=30 if 'نیم' in normalized else 0
    return f'{hour:02d}:{minute:02d}'


def apply(r,c):
    raw=resolution.normalize_text(c['notes']);task=c['task'];values=copy.deepcopy(c['current'])
    last=next((resolution.normalize_text(x.get('text','')) for x in reversed(c['history']) if isinstance(x,dict) and x.get('role')=='assistant'),'')
    def result(reply,changed=False):
        return dict(values=values,questions=list(c['questions']),reply=reply,
                    intent='resolved' if changed else 'question',pending_confirmation=None)
    if task['stage']=='minutes':
        participants=values.get('MTG_Participants') or {}
        if not isinstance(participants,dict):return None
        if 'ساعت' in raw and 'حضور' in raw and any(x in raw for x in ('اجباری نیست','اختیاری','خالی بماند','خالی بمونه','نپرس')):
            return result('ساعت حضور اختیاری است؛ خالی بودن آن مانع تکمیل صورت‌جلسه نیست و دیگر برای آن سؤال نمی‌کنم.')
        on_time=any(x in raw for x in ('به موقع','بموقع','بهموقع','به موقه','بموقه','بهموقه','سر ساعت','ساعت جلسه','سر تایم جلسه'))
        collective=any(x in raw for x in ('همه','حضورها','حضور ها','حاضرین','شرکت کنندگان'))
        if on_time and collective and not any(x in raw for x in ('نیامد','نرسید','تاخیر','تأخیر','دیر آمد','دیر امد')):
            meeting={**task.get('native',{}),**values}
            start=clock(meeting.get('MTG_MeetingStartTime',''),allow_bare=True)
            everyone_came='همه' in raw and any(word in raw for word in ('آمدند','امدند','آمده اند','امده اند','اومدن','آمدن','امدن'))
            if everyone_came:
                for row in participants.values():row['MTG_AttendanceStatus']='Present'
            if not start:
                return result('حضور همه شرکت‌کنندگان ثبت شد؛ ساعت حضور اختیاری است و خالی می‌ماند.' if everyone_came else 'متوجه شدم افراد حاضر به‌موقع رسیدند؛ چون ساعت شروع ثبت نشده، ساعت حضور اختیاری را خالی نگه می‌دارم.',everyone_came)
            changed=0
            for row in participants.values():
                if row.get('MTG_AttendanceStatus')=='Present':row['MTG_AttendanceTime']=start;changed+=1
            if changed:
                suffix='وضعیت همه شرکت‌کنندگان حاضر ثبت شد.' if everyone_came else 'وضعیت غیبت افراد دیگر تغییر نکرد.'
                return result(f'ساعت حضور {changed} فرد حاضر، مطابق ساعت شروع جلسه، روی {start} ثبت شد. ساعت حضور اختیاری است. '+suffix,True)
            return result('هنوز فردی با وضعیت حاضر ثبت نشده است؛ بگویید چه کسانی حاضر بوده‌اند یا «همه حاضر بودند».')
        if raw in ('حاضر بوده','حاضر بود','حاضر است','حاضر بوده است','حاضر','بله حاضر بوده'):
            refs=re.findall(r'(?:ردیف|شرکت کننده)\s*(\d+)',last)
            key=refs[-1] if refs else None
            if key in participants:
                participants[key]['MTG_AttendanceStatus']='Present'
                return result('وضعیت شرکت‌کننده ردیف '+key+' روی «حاضر» ثبت شد.',True)
        # A bare time answers the latest single attendance-time question.
        if 'ساعت حضور' in last and (re.fullmatch(r'\s*[۰-۹٠-٩0-9]{1,2}:[۰-۹٠-٩0-9]{2}\s*',c['notes']) or raw.startswith('ساعت ')):
            value=clock(c['notes'],allow_bare=True)
            refs=re.findall(r'(?:ردیف|شرکت کننده)\s*(\d+)',last)
            key=refs[-1] if refs else None
            if value and key in participants and participants[key].get('MTG_AttendanceStatus')=='Present':
                participants[key]['MTG_AttendanceTime']=value
                return result('ساعت حضور ردیف '+key+' روی '+value+' ثبت شد.',True)
    # A focused answer to a clock question must keep minutes and respect stage writes.
    value=clock(c['notes'],allow_bare=True)
    focused=bool(re.fullmatch(r'\s*[۰-۹٠-٩0-9]{1,2}:[۰-۹٠-٩0-9]{2}\s*',c['notes']))
    target='MTG_MeetingEndTime' if 'ساعت پایان' in last else ('MTG_MeetingStartTime' if 'ساعت شروع' in last else None)
    if focused and target and value:
        if target not in r.form(task):return result('ساعت را '+value+' فهمیدم؛ زمان برنامه در این مرحله فقط خواندنی است و برای اصلاح آن باید دعوت‌نامه به مرحله اصلاح برگردد.')
        values[target]=value
        return result('ساعت روی '+value+' ثبت شد.',True)
    if has_date(c['notes']):
        try:day=jalali_date(c['notes'])
        except ValueError as exc:return result(str(exc))
        if not day:return None
        labels=(('MTG_MeetingStartDateTime',('تاریخ جلسه','تاریخ برگزاری')),('MTG_MeetingEndDateTime',('تاریخ پایان برنامه',)))
        target=None
        for text in (raw,last):
            matches=[(text.rfind(label),key) for key,parts in labels for label in parts if label in text]
            if matches:target=max(matches)[1];break
        if target is None and task['stage']=='invitation':target='MTG_MeetingStartDateTime'
        if target:
            if target not in r.form(task):
                return result('تاریخ را '+day+' فهمیدم. تاریخ برنامه در این مرحله از دعوت‌نامه تأییدشده خوانده می‌شود و قابل ویرایش نیست؛ برای اصلاح برنامه باید دعوت‌نامه به مرحله اصلاح برگردد.')
            values[target]=day
            return result('تاریخ روی '+day+' در پیش‌نویس ثبت شد.',True)
    return None
