"""Bound model input by stage; never send an entire directory or case history."""
import json
import re
import unicodedata
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

MAX_CONTEXT_CHARS = 48000
MAX_PEOPLE = 80

def compact(value):
    if isinstance(value, dict):
        return {k: compact(v) for k, v in value.items() if v is not None and v != []}
    if isinstance(value, list):
        return [compact(v) for v in value]
    return value

def normalize(value):
    text = unicodedata.normalize('NFKC', str(value))
    text = text.translate(str.maketrans({'ي':'ی','ى':'ی','ك':'ک','آ':'ا','أ':'ا','إ':'ا','ـ':'','\u200c':' '}))
    text = ''.join(c for c in text if not unicodedata.combining(c))
    return ' '.join(re.findall(r'[^\W_]+', text.casefold()))

def name_matches(name, text):
    """Token boundaries prevent Ali matching Alireza; surname fragments remain candidates."""
    tokens = normalize(name).split()
    ignored = {'اقای', 'اقا', 'خانم', 'دکتر', 'مهندس'}
    tokens = [t for t in tokens if t not in ignored]
    words = set(normalize(text).split())
    return any(len(t) > 2 and t in words and re.search(r'[؀-ۿ]', t) for t in tokens)


def username_matches(username, text):
    username = str(username or '').strip()
    return bool(username and re.search(r'(?<![\w.@-])'+re.escape(username)+r'(?![\w.@-])', text, re.IGNORECASE))

def calendar_context():
    import jdatetime
    from .setup_console import get_setting
    now = datetime.now(ZoneInfo('Asia/Tehran'))
    mode=str((get_setting('ui') or {}).get('calendar','jalali')).lower()
    if mode not in ('jalali','gregorian'):mode='jalali'
    tomorrow=now.date()+timedelta(days=1)
    return {'timezone':'Asia/Tehran','now':now.isoformat(),'display_calendar':mode,
            'gregorian_today':now.date().isoformat(),'gregorian_tomorrow':tomorrow.isoformat(),
            'jalali_today':jdatetime.date.fromgregorian(date=now.date()).strftime('%Y/%m/%d'),
            'jalali_tomorrow':jdatetime.date.fromgregorian(date=tomorrow).strftime('%Y/%m/%d')}

def build_context(notes, task, current, scope, fields, questions=(), history=()):
    if not isinstance(notes,str) or not notes.strip() or len(notes)>18000:
        raise ValueError('متن را در بخش‌های حداکثر ۱۸ هزار نویسه ارسال کنید.')
    # History supplies reference context, never new authority or assignment evidence.
    conversation=[{'role':item['role'],'text':item['text'][-2000:]}
                  for item in list(history or [])[-8:]
                  if isinstance(item,dict) and item.get('role') in ('user','assistant')
                  and isinstance(item.get('text'),str) and item['text'].strip()]
    reference_text='\n'.join(item['text'] for item in conversation)+'\n'+notes
    stage_fields=task['pack']['stages'][task['stage']]['fields']
    native={k:v for k,v in task['native'].items() if k in stage_fields and
            not any(x in k for x in ('File','Evidence','Json','History')) and k not in current}
    # Keep all current values; never silently truncate grids or evidence.
    referenced=set(re.findall(r'\b[a-fA-F0-9]{32}\b',json.dumps([current,native,reference_text])))
    text=normalize(reference_text)
    people={}
    candidates=[]
    for uid, person in scope['directory'].items():
        if not person.get('active'):
            continue
        names=[person.get('name',''),person.get('avan_name','')]
        normalized=[normalize(x) for x in names if x]
        if uid in referenced:
            people[uid]={'name':person.get('name','') or person.get('avan_name','')}
        elif (username_matches(person.get('username'), reference_text)
              or username_matches(person.get('avan_username'), reference_text)
              or any(name and ((' '+name+' ') in (' '+text+' ') or name_matches(name, reference_text)) for name in normalized)):
            candidates.append((uid,person.get('name','') or person.get('avan_name','')))
    if len(people)+len(candidates)>MAX_PEOPLE:
        raise ValueError('افراد این درخواست زیاد هستند؛ اطلاعات را در چند بخش وارد کنید.')
    people.update({uid:{'name':name} for uid,name in candidates})
    for uid in people:
        people[uid]['unit']=scope['directory'][uid].get('unit','')
        people[uid]['username']=scope['directory'][uid].get('username','')
        people[uid]['avan_name']=scope['directory'][uid].get('avan_name','')
        people[uid]['avan_username']=scope['directory'][uid].get('avan_username','')
    # Include every matching candidate; never resolve ambiguous names by directory order.
    active={k:{'name':v.get('name',''),'unit':v.get('unit',''),'username':v.get('username',''),
               'avan_name':v.get('avan_name',''),'avan_username':v.get('avan_username','')}
            for k,v in scope['directory'].items() if v.get('active')}
    if len(active)<=MAX_PEOPLE:
        people=active
    payload={'calendar':calendar_context(),'notes':notes,'stage':task['stage'],'current':current,
             'conversation':conversation,
             'previous_questions':list(questions)[-12:],'context':native,
             'fields':compact(fields),'directory':people,
             'directory_incomplete':len(people)<len(active)}
    if len(json.dumps(payload,ensure_ascii=False,separators=(',',':')))>MAX_CONTEXT_CHARS:
        raise ValueError('اطلاعات این مرحله برای یک درخواست AI زیاد است؛ از ویرایش فرم یا ورودی کوچک‌تر استفاده کنید.')
    return payload
