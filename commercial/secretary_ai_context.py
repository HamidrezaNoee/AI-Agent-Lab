"""Bound model input by stage; never send an entire directory or case history."""
import json
import re

MAX_CONTEXT_CHARS = 48000
MAX_PEOPLE = 80

def compact(value):
    if isinstance(value, dict):
        return {k: compact(v) for k, v in value.items() if v is not None and v != []}
    if isinstance(value, list):
        return [compact(v) for v in value]
    return value

def normalize(value):
    return str(value).translate(str.maketrans({'ي':'ی','ك':'ک','\u200c':' '})).casefold().strip()

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
        elif name and len(name)>2 and name in text:
            candidates.append((uid,person.get('name','')))
    if len(people)+len(candidates)>MAX_PEOPLE:
        raise ValueError('افراد این درخواست زیاد هستند؛ اطلاعات را در چند بخش وارد کنید.')
    people.update({uid:{'name':name} for uid,name in candidates})
    # Small directories are useful for ambiguous names. Larger ones require exact
    # identification rather than sending every employee email/department to AI.
    active={k:{'name':v.get('name','')} for k,v in scope['directory'].items() if v.get('active')}
    if len(active)<=MAX_PEOPLE:
        people=active
    payload={'notes':notes,'stage':task['stage'],'current':current,
             'previous_questions':list(questions)[-12:],'context':native,
             'fields':compact(fields),'directory':people,
             'directory_incomplete':len(people)<len(active)}
    if len(json.dumps(payload,ensure_ascii=False,separators=(',',':')))>MAX_CONTEXT_CHARS:
        raise ValueError('اطلاعات این مرحله برای یک درخواست AI زیاد است؛ از ویرایش فرم یا ورودی کوچک‌تر استفاده کنید.')
    return payload
