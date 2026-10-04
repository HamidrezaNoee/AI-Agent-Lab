"""Server-owned process adapters: navigation and inbox do not depend on MTG names.

An adapter is trusted installed Python code, never imported from an uploaded PMX.
Its runtime must enforce native ownership independently of navigation visibility.
"""
from __future__ import annotations
from dataclasses import dataclass
import re
from typing import Callable
from . import secretary_catalog as catalog

@dataclass(frozen=True)
class Section:
    id: str
    label: str
    view: str = 'tasks'
    stages: tuple[str, ...] = ()
    task_only: bool = False
    modules: frozenset[int] = frozenset()

@dataclass(frozen=True)
class Adapter:
    key: str
    title: str
    modules: frozenset[int]
    process_keys: tuple[str, ...]
    sections: tuple[Section, ...]
    inbox: Callable
    drafts: Callable
    # Known renderer and server routes, not URLs supplied by uploaded XML.
    renderer: str = 'generic'
    analytical_modules: frozenset[int] = frozenset()

_ADAPTERS: dict[str, Adapter] = {}

def register_adapter(adapter: Adapter):
    if not re.fullmatch(r'[a-z][a-z0-9_]{1,63}', adapter.key) or adapter.key in _ADAPTERS:
        raise ValueError('Adapter key must be unique')
    if not adapter.process_keys or not adapter.modules or not adapter.sections or not any(not s.task_only for s in adapter.sections):
        raise ValueError('Adapter needs processes, modules and sections')
    ids=set()
    for section in adapter.sections:
        if (not re.fullmatch(r'[a-z][a-z0-9_]{0,63}', section.id) or section.id in ids
                or section.view not in ('tasks','drafts','overview','meetings','assistant','reports','monitor') or not section.label):
            raise ValueError('Invalid process section')
        ids.add(section.id)
    if adapter.renderer not in ('generic','meeting'):
        raise ValueError('Renderer is not installed')
    _ADAPTERS[adapter.key]=adapter

def resolve(pack, scope):
    adapter=_ADAPTERS.get(pack.get('adapter'))
    if not adapter or not (adapter.modules<=set(scope['license']['modules']) or adapter.analytical_modules & set(scope['license']['modules'])):
        raise PermissionError('آداپتور یا مجوز این فرایند فعال نیست.')
    if not all(isinstance(pack.get(k),dict) and pack[k].get('process_uid') for k in adapter.process_keys):
        raise ValueError('قرارداد بسته فرایندی معتبر نیست.')
    return adapter

def configured(scope):
    if 2 in set(scope['license']['modules']):
        catalog.ensure_installed_meeting_pack(scope['source_id'])
    results=[]
    for pack in catalog.packs(scope['source_id'],True):
        try:resolve(pack,scope)
        except PermissionError:continue
        results.append(pack)
    return results

def identity(pack,adapter):
    primary=pack[adapter.process_keys[0]]
    return {'id':pack['id'],'title':primary.get('title') or adapter.title,
            'adapter':adapter.key,'revision':pack['revision'],
            'processes':[{'process_uid':pack[k]['process_uid'],'title':pack[k].get('title') or k} for k in adapter.process_keys],
            'renderer':adapter.renderer}

def processes(scope):
    return {'processes':[identity(p,resolve(p,scope)) for p in configured(scope)]}

def workspace(con,scope,actor,pack_id,section_id=None):
    # Source ownership and license are independently revalidated by the route.
    pack=catalog.get(scope['source_id'],pack_id)
    adapter=resolve(pack,scope)
    licensed=set(scope['license']['modules'])
    can_tasks=any(s.view=='tasks' and s.modules<=licensed for s in adapter.sections)
    data=adapter.inbox(con,scope,pack_id) if can_tasks else {}
    tasks=[t for t in data.get('tasks',[]) if t.get('pack_id')==pack_id]
    drafts=[d for d in adapter.drafts(scope,actor,pack_id) if d.get('pack_id')==pack_id] if any(s.view=='drafts' and s.modules<=licensed for s in adapter.sections) else []
    counts={s.id:sum(1 for t in tasks if not s.stages or t['stage'] in s.stages) for s in adapter.sections}
    sections=[s for s in adapter.sections if s.modules<=set(scope['license']['modules']) and (not s.task_only or counts[s.id]>0)]
    if not sections:raise PermissionError('بخش مجاز برای این فرایند وجود ندارد.')
    if section_id is not None and section_id not in {s.id for s in sections}:
        raise PermissionError('بخش انتخاب‌شده در کارتابل فعلی این فرایند در دسترس نیست.')
    selected=next((s for s in sections if s.id==section_id),sections[0])
    visible=[t for t in tasks if not selected.stages or t['stage'] in selected.stages]
    return {'process':identity(pack,adapter),'section':selected.id,
            'navigation':[{'id':s.id,'label':s.label,'view':s.view,'count':counts[s.id]} for s in sections],
            'tasks':visible if selected.view=='tasks' else [],
            'notifications':[n for n in data.get('notifications',[]) if n.get('task',{}).get('pack_id')==pack_id and any(t['case_uid']==n['task']['case_uid'] and t['index']==n['task']['index'] for t in visible)],
            'sessions':drafts if selected.view=='drafts' else [],
            'truncated':bool(data.get('truncated'))}

def _meeting_inbox(con,scope,pack_id):
    from .secretary_runtime import inbox
    return inbox(con,scope,pack_id=pack_id)

def _meeting_drafts(scope,actor,pack_id):
    from .secretary_runtime import sessions
    return [{'id':r['id'],'pack_id':r['pack_id'],'status':r['status'],
             'title':r['values'].get('MTG_MeetingTitle') or 'جلسه جدید','case_uid':r['case_uid']}
            for r in sessions(scope,actor) if r['pack_id']==pack_id]

register_adapter(Adapter(
    key='meeting_v2',title='مدیریت جلسات',modules=frozenset({2}),
    process_keys=('meeting','action'),renderer='meeting',analytical_modules=frozenset({1,3,4}),
    sections=(Section('inbox','کارتابل من',modules=frozenset({2})),
              Section('drafts','جلسه جدید و پیش‌نویس‌ها','drafts',modules=frozenset({2})),
              Section('approvals','تأییدهای من',stages=('invitation_approval','minutes_approval'),task_only=True,modules=frozenset({2})),
              Section('minutes','دعوت‌نامه و صورتجلسه',stages=('invitation','minutes'),task_only=True,modules=frozenset({2})),
              Section('execution','اقدامات من',stages=('action_execution',),task_only=True,modules=frozenset({2})),
              Section('reviews','بررسی اقدامات',stages=('action_review',),task_only=True,modules=frozenset({2})),
              Section('monitoring','پایش و اختتام',stages=('monitoring',),task_only=True,modules=frozenset({2})),
              Section('meetings','سوابق جلسات','meetings',modules=frozenset({1})),
              Section('assistant','دستیار این فرایند','assistant',modules=frozenset({1})),
              Section('reports','گزارش اقدامات','reports',modules=frozenset({3})),
              Section('alerts','هشدار و پیگیری','monitor',modules=frozenset({4}))),
    inbox=_meeting_inbox,drafts=_meeting_drafts))

def register(app,authorized):
    from fastapi import Depends,HTTPException,Query
    def read(value,source_id,fn):
        from .production_app import _source_store_response
        def run(con,scope):
            try:return fn(con,scope,value[2])
            except PermissionError as exc:raise HTTPException(403,str(exc))
            except ValueError as exc:raise HTTPException(422,str(exc))
        return _source_store_response(source_id,run,value[2])
    @app.get('/api/sources/{source_id}/process-workspace/status')
    def process_status(source_id:str,value=Depends(authorized)):
        def build(con,scope,principal):
            enabled_packs=configured(scope)
            meeting_packs=[p for p in enabled_packs if p.get('adapter')=='meeting_v2']
            return {
                'source_id':scope['source_id'],
                'external_user_id':scope['external_user_id'],
                'role':scope['role'],
                'licensed_modules':sorted(scope['license']['modules']),
                'meeting_module_enabled':2 in set(scope['license']['modules']),
                'configured_processes':[identity(p,resolve(p,scope)) for p in enabled_packs],
                'meeting_packs':[{
                    'id':p['id'],
                    'enabled':bool(p.get('enabled')),
                    'revision':p.get('revision'),
                    'meeting_title':(p.get('meeting') or {}).get('title'),
                    'action_title':(p.get('action') or {}).get('title'),
                } for p in meeting_packs],
                'ready_for_meeting_management':bool(meeting_packs) and 2 in set(scope['license']['modules']),
            }
        return read(value,source_id,build)

    @app.get('/api/sources/{source_id}/process-workspace')
    def list_processes(source_id:str,value=Depends(authorized)):
        return read(value,source_id,lambda con,s,p:processes(s))
    @app.get('/api/sources/{source_id}/process-workspace/{pack_id}')
    def process_inbox(source_id:str,pack_id:str,section:str|None=Query(None,max_length=64),value=Depends(authorized)):
        if not re.fullmatch(r'[0-9a-f]{24}',pack_id):raise HTTPException(422,'شناسه بسته معتبر نیست.')
        return read(value,source_id,lambda con,s,p:workspace(con,s,p.subject,pack_id,section))


def native_ids(pack):
    adapter=_ADAPTERS.get(pack.get('adapter'))
    if not adapter:raise ValueError('آداپتور فرایند نصب نشده است.')
    result=set()
    for key in adapter.process_keys:
        value=pack.get(key,{}).get('process_uid')
        if not re.fullmatch(r'[a-f0-9]{32}',str(value)):raise ValueError('شناسه فرایند معتبر نیست.')
        result.add(value)
    if len(result)!=len(adapter.process_keys):raise ValueError('شناسه‌های فرایند بسته باید مستقل باشند.')
    return result

def _native_inbox(con,scope,pack_id):
    from .processmaker_store import query
    pack=catalog.get(scope['source_id'],pack_id)
    rows=query(con,'SELECT a.APP_UID,a.APP_NUMBER,d.DEL_INDEX,d.TAS_UID,t.TAS_TITLE FROM APPLICATION a JOIN APP_DELEGATION d ON d.APP_UID=a.APP_UID JOIN TASK t ON t.TAS_UID=d.TAS_UID WHERE a.PRO_UID=%s AND d.USR_UID=%s AND d.DEL_THREAD_STATUS=%s AND a.APP_STATUS IN (%s,%s) ORDER BY d.DEL_DELEGATE_DATE DESC LIMIT 201',
               (pack['process']['process_uid'],scope['external_user_id'],'OPEN','TO_DO','DRAFT'))
    return {'tasks':[{'case_uid':str(x[0]),'number':str(x[1]),'index':int(x[2]),'stage':str(x[3]),'stage_label':str(x[4] or 'وظیفه'),
                     'title':str(x[4] or 'وظیفه'),'pack_id':pack_id,'available':True,'read_only':True} for x in rows[:200]],
            'notifications':[],'truncated':len(rows)>200}

register_adapter(Adapter(key='native_tasks_v1',title='کارتابل فرایند',modules=frozenset({1}),
                         process_keys=('process',),sections=(Section('inbox','کارتابل من'),Section('overview','نمای فرایند','overview')),
                         inbox=_native_inbox,drafts=lambda scope,actor,pack_id:[]))
