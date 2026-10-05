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
    now = datetime.now(ZoneInfo('Asia/Tehran'))
    return {'timezone':'Asia/Tehran','now':now.isoformat(),
            'jalali_today':jdatetime.date.fromgregorian(date=now.date()).strftime('%Y/%m/%d'),
            'jalali_tomorrow':jdatetime.date.fromgregorian(date=now.date()+timedelta(days=1)).strftime('%Y/%m/%d')}

def build_context(notes, task, current, scope, fields, questions=()):
    if not isinstance(notes,str) or not notes.strip() or len(notes)>18000:
        raise ValueError('متن را در بخش‌های حداکثر ۱۸ هزار نویسه ارسال کنید.')
    stage_fields=task['pack']['stages'][task['stage']]['fields']
    native={k:v for k,v in task['native'].items() if k in stage_fields and
            not any(x in k for x in ('File','Evidence','Json','History')) and k not in current}
    # Keep all current values; never silently truncate grids or evidence.
    referenced=set(re.findall(r'\b[a-fA-F0-9]{32}\b',json.dumps([current,native,notes])))
    text=normalize(notes)
    people={}
    candidates=[]
    for uid, person in scope['directory'].items():
        if not person.get('active'):
            continue
        name=normalize(person.get('name',''))
        if uid in referenced:
            people[uid]={'name':person.get('name','')}
        elif username_matches(person.get('username'), notes) or (name and ((' '+name+' ') in (' '+text+' ') or name_matches(name, notes))):
            candidates.append((uid,person.get('name','')))
    if len(people)+len(candidates)>MAX_PEOPLE:
        raise ValueError('افراد این درخواست زیاد هستند؛ اطلاعات را در چند بخش وارد کنید.')
    people.update({uid:{'name':name} for uid,name in candidates})
    for uid in people:
        people[uid]['unit']=scope['directory'][uid].get('unit','')
        people[uid]['username']=scope['directory'][uid].get('username','')
    # Include every matching candidate; never resolve ambiguous names by directory order.
    active={k:{'name':v.get('name',''),'unit':v.get('unit',''),'username':v.get('username','')} for k,v in scope['directory'].items() if v.get('active')}
    if len(active)<=MAX_PEOPLE:
        people=active
    payload={'calendar':calendar_context(),'notes':notes,'stage':task['stage'],'current':current,
             'previous_questions':list(questions)[-12:],'context':native,
             'fields':compact(fields),'directory':people,
             'directory_incomplete':len(people)<len(active)}
    if len(json.dumps(payload,ensure_ascii=False,separators=(',',':')))>MAX_CONTEXT_CHARS:
        raise ValueError('اطلاعات این مرحله برای یک درخواست AI زیاد است؛ از ویرایش فرم یا ورودی کوچک‌تر استفاده کنید.')
    return payload
