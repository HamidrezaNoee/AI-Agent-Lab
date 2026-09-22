"""Authenticated application endpoints and session-scoped monitor worker."""
from __future__ import annotations
from datetime import datetime,timezone
import asyncio,hashlib,json,logging,time
from fastapi import Depends,HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel,ConfigDict,Field
from .agent_tools import MeetingTools,normal,MonitorQuery
from .meeting_agent import run_agent,run_slot,AgentUnavailable,AgentBusy,AgentInvalid
from . import agent_state
from .secretary_agent import extract_draft


class Question(BaseModel):
    model_config=ConfigDict(extra='forbid')
    question:str=Field(min_length=3,max_length=2000)
    new_conversation:bool=False


class DraftRequest(BaseModel):
    model_config=ConfigDict(extra='forbid')
    meeting_no:str=Field(min_length=1,max_length=80)
    notes:str=Field(min_length=10,max_length=18000)


class Approval(BaseModel):
    model_config=ConfigDict(extra='forbid')
    confirmed:bool


class Subscribe(BaseModel):
    model_config=ConfigDict(extra='forbid')
    enabled:bool


def snapshot(principal,module):
    from .production_app import _store_response,_normalise_dates
    from .production_store import authorized_meeting_snapshot,ProductionAccessDenied
    def read(con,scope):
        if module not in scope['license']['modules']:raise ProductionAccessDenied('Module not licensed')
        rows,complete=authorized_meeting_snapshot(con,scope)
        _normalise_dates(rows)
        return scope,rows,complete
    return _store_response(read,principal)


def ensure_still_authorized(principal,initial_scope,initial_rows,module):
    # A role, hierarchy, PM mapping or meeting membership can change while the
    # external model runs. Re-check source visibility before returning any content.
    scope,rows,_=snapshot(principal,module)
    if scope['pm_uid']!=initial_scope['pm_uid'] or scope['role']!=initial_scope['role']:
        raise HTTPException(403,'دسترسی سازمانی تغییر کرده است؛ دوباره پرسش را اجرا کنید.')
    if not {m['meeting_id'] for m in initial_rows}<={m['meeting_id'] for m in rows}:
        raise HTTPException(403,'دامنه جلسات تغییر کرده است؛ دوباره پرسش را اجرا کنید.')
    return scope


def guard_model(fn):
    from .security import AuthenticationFailed,ConfigurationFailed
    try:return fn()
    except (AuthenticationFailed,ConfigurationFailed):raise HTTPException(401,"اعتبار نشست پایان یافته است؛ دوباره وارد شوید.")
    except AgentBusy as exc:raise HTTPException(429,str(exc))
    except AgentUnavailable as exc:raise HTTPException(503,str(exc))
    except AgentInvalid:raise HTTPException(502,'پاسخ مدل از بررسی ساختار یا ارجاع عبور نکرد؛ پرسش را دوباره اجرا کنید.')


def monitor_for(principal):
    scope,rows,complete=snapshot(principal,4)
    now=datetime.now(timezone.utc)
    observations=agent_state.observe(scope,principal.subject,rows,now,complete)
    tools=MeetingTools(rows,now=now,complete=complete,modules=scope['license']['modules'],observations=observations)
    result=tools.execute('monitor_actions',{})
    result['read_only']=True
    return result


def register(app,authorized,csrf):
    @app.get('/api/agent/status')
    def status(value=Depends(authorized)):
        from .setup_console import get_setting
        _,_,principal=value
        from .production_app import _store_response
        scope=_store_response(lambda con,scope:scope,principal)
        cfg=get_setting('ai') or {}
        return {'enabled':bool(cfg.get('enabled') and cfg.get('api_key')),
                'model':cfg.get('model'),'modules':sorted(scope['license']['modules']),
                'direct_processmaker_write':False}

    @app.post('/api/ask')
    def ask(body:Question,value=Depends(csrf)):
        _,session,principal=value
        def work():
            with run_slot((str(principal.tenant_id),principal.subject)):
                scope,rows,complete=snapshot(principal,1)
                tools=MeetingTools(rows,complete=complete,modules=scope['license']['modules'])
                history=[] if body.new_conversation else session.get('agent_questions',[])
                detail={'question_hash':hashlib.sha256(body.question.encode()).hexdigest()}
                agent_state.audit(scope,principal.subject,'AGENT_STARTED',detail)
                try:
                    result=run_agent(body.question,tools,history=history)
                    from .production_app import _oidc_config
                    _oidc_config()[4].authenticate("Bearer "+session["access_token"])
                    ensure_still_authorized(principal,scope,rows,1)
                except Exception:
                    agent_state.audit(scope,principal.subject,'AGENT_FAILED',{'error_code':'generation_or_authorization'})
                    raise
                session['agent_questions']=(history+[body.question])[-4:]
                agent_state.audit(scope,principal.subject,'AGENT_COMPLETED',{
                    **detail,'model':result['model'],'tools':[t['tool'] for t in result['tool_trace']],
                    **result['usage'],'coverage_complete':complete})
                return {**result,'company':scope['company'],'role':scope['role']}
        return guard_model(work)

    @app.post('/api/secretary/drafts')
    def draft(body:DraftRequest,value=Depends(csrf)):
        _,session,principal=value
        def work():
            with run_slot((str(principal.tenant_id),principal.subject)):
                scope,rows,complete=snapshot(principal,2)
                matches=[m for m in rows if normal(m['meeting_no'])==normal(body.meeting_no)]
                if len(matches)!=1:raise HTTPException(404,'شماره جلسه در دامنه بازیابی‌شده یکتا نیست یا موجود نیست؛ شماره دقیق را بررسی کنید.')
                meeting=matches[0]
                owners={a['owner_uid']:{'uid':a['owner_uid'],'name':a.get('owner_name'),'unit':a.get('owner_unit')}
                        for a in meeting['actions'] if a.get('owner_uid')}
                if len(owners)>100:raise HTTPException(422,'تعداد مسئولان این جلسه بیش از دامنه استخراج است.')
                from zoneinfo import ZoneInfo
                import os
                today=datetime.now(ZoneInfo(os.getenv('AVAN_DATA_TIMEZONE','Asia/Tehran'))).date()
                payload=extract_draft(body.notes,meeting,list(owners.values()),today=today)
                from .production_app import _oidc_config
                _oidc_config()[4].authenticate("Bearer "+session["access_token"])
                ensure_still_authorized(principal,scope,[meeting],2)
                identifier=agent_state.save_draft(scope,principal.subject,meeting['meeting_id'],payload)
                return {'id':identifier,'status':'draft','payload':payload,'read_only':True}
        return guard_model(work)

    def load_draft(principal,identifier):
        scope,rows,_=snapshot(principal,2)
        try:record=agent_state.get_draft(scope,principal.subject,identifier,{m['meeting_id'] for m in rows})
        except PermissionError:raise HTTPException(404,'پیش‌نویس در دسترس نیست.')
        return scope,rows,record

    @app.get('/api/secretary/drafts/{identifier}')
    def read_draft(identifier:str,value=Depends(authorized)):
        return load_draft(value[2],identifier)[2]

    @app.post('/api/secretary/drafts/{identifier}/approve')
    def approve(identifier:str,body:Approval,value=Depends(csrf)):
        if not body.confirmed:raise HTTPException(422,'تأیید صریح پیش‌نویس لازم است.')
        _,_,principal=value
        scope,rows,record=load_draft(principal,identifier)
        meeting=next(m for m in rows if m['meeting_id']==record['meeting_id'])
        if scope['role']!='SysAdmin' and scope['pm_uid']!=meeting.get('secretary_uid'):
            raise HTTPException(403,'تأیید پیش‌نویس فقط برای دبیر جلسه یا مدیر سیستم مجاز است.')
        result=agent_state.approve_draft(scope,principal.subject,identifier,{m['meeting_id'] for m in rows})
        return {**result,'processmaker_written':False}

    @app.get('/api/secretary/drafts/{identifier}/export')
    def export(identifier:str,value=Depends(authorized)):
        scope,_,record=load_draft(value[2],identifier)
        if record['status']!='approved':raise HTTPException(409,'ابتدا پیش‌نویس را بازبینی و تأیید کنید.')
        # Canonical handover contract, not invented Dynaform variable names.
        payload={'schema_version':1,'meeting_id':record['meeting_id'],
                 'draft_id':record['id'],'registration_status':'not_registered',
                 'requires_processmaker_field_mapping':True,'draft':record['payload']}
        agent_state.audit(scope,value[2].subject,'SECRETARY_DRAFT_EXPORTED',{'draft_id':identifier})
        return JSONResponse(payload,headers={'Content-Disposition':'attachment; filename="meeting-actions.json"'})

    @app.post('/api/monitor')
    def monitor(value=Depends(csrf)):
        _,session,principal=value
        result=monitor_for(principal)
        return {**result,'subscribed':bool(session.get('monitor_enabled')),
                'subscription_expires_at':datetime.fromtimestamp(session['expires'],timezone.utc).isoformat()}

    @app.post('/api/monitor/subscribe')
    def subscribe(body:Subscribe,value=Depends(csrf)):
        _,session,principal=value
        scope,_,_=snapshot(principal,4)
        session['monitor_enabled']=body.enabled
        session['monitor_next']=0
        agent_state.audit(scope,principal.subject,'MONITOR_SUBSCRIPTION',{'status':'enabled' if body.enabled else 'disabled'})
        return {'enabled':body.enabled,'interval_seconds':300,'scope':'current_authenticated_session'}


async def monitor_worker():
    """No service identity or global bypass; reverify each subscribed session."""
    from starlette.concurrency import run_in_threadpool
    from .production_app import sessions,_oidc_config
    def tick():
        for session in list(sessions.values()):
            now=time.time()
            if not session.get('monitor_enabled') or session.get('expires',0)<=now or session.get('monitor_next',0)>now:continue
            session['monitor_next']=now+300
            try:
                principal=_oidc_config()[4].authenticate('Bearer '+session['access_token'])
                result=monitor_for(principal)
                session['monitor_last_count']=result['total']
                session['monitor_error']=False
            except Exception:
                # Never keep or return stale records after revocation/failure.
                session.pop('monitor_last_count',None)
                session['monitor_error']=True
                logging.getLogger(__name__).warning('Authorized monitoring refresh unavailable')
    while True:
        await asyncio.sleep(30)
        await run_in_threadpool(tick)
