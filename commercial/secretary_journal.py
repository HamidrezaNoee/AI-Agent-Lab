"""One bounded undo checkpoint and human-readable receipts for draft mutations."""
import copy
import hashlib
import json


def stamp(values):
    return hashlib.sha256(json.dumps(values,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()


def changes(before,after,fields,directory):
    result=[]
    def display(value,spec):
        if value in (None,''):return 'خالی'
        if isinstance(value,dict):return str(len(value))+' ردیف'
        raw=str(value)
        if raw in directory:
            person=directory[raw]
            return str(person.get('name') or person.get('username') or 'کاربر ثبت‌شده')[:180]
        for option in spec.get('options',[]) or []:
            if str(option.get('value'))==raw:return str(option.get('label') or raw)[:180]
        return raw[:180]
    for field in sorted(set(before)|set(after)):
        old=before.get(field);new=after.get(field)
        if old==new:continue
        spec=fields.get(field,{})
        title=spec.get('label') or 'اطلاعات مرحله'
        if spec.get('type')=='grid':
            columns={x['id']:x for x in spec.get('columns',[])}
            old=old if isinstance(old,dict) else {};new=new if isinstance(new,dict) else {}
            for key in sorted(set(old)|set(new),key=lambda x:int(x) if str(x).isdigit() else 0):
                a=old.get(key,{}) or {};b=new.get(key,{}) or {}
                if key not in old or key not in new:
                    result.append({'label':title+' · ردیف '+str(key),
                                   'before':'موجود' if key in old else 'خالی',
                                   'after':'افزوده شد' if key in new else 'حذف شد'})
                else:
                    for column in sorted(set(a)|set(b)):
                        if a.get(column)==b.get(column):continue
                        col=columns.get(column,{})
                        result.append({'label':title+' · ردیف '+str(key)+' · '+str(col.get('label') or 'مقدار'),
                                       'before':display(a.get(column),col),'after':display(b.get(column),col)})
        else:result.append({'label':title,'before':display(old,spec),'after':display(new,spec)})
    return {'count':len(result),'items':result[:80],'truncated':len(result)>80}


def record(row,values,fields,directory,receipt=None,*,checkpoint=True):
    before=row.get('values') or {}
    delta=changes(before,values,fields,directory)
    if before!=values:
        row['_undo_checkpoint']={'values':copy.deepcopy(before),'questions':list(row.get('questions') or []),
                                 'after_hash':stamp(values)} if checkpoint else None
    elif not checkpoint:row['_undo_checkpoint']=None
    row['last_change']={**delta,'revision':int(row.get('revision') or 0)+1}
    row['agent_receipt']={k:v for k,v in (receipt or {}).items()
                          if k in ('version','tool','label','effect','model_used','elapsed_ms')}
    return delta


def can_undo(row):
    checkpoint=row.get('_undo_checkpoint') or {}
    return bool(row.get('status')=='draft' and checkpoint and checkpoint.get('after_hash')==stamp(row.get('values') or {}))
