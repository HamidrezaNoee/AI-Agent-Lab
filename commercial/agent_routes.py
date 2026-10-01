"""Authenticated, permission-scoped Agent application endpoints."""
from __future__ import annotations
from datetime import datetime,timezone
import asyncio,hashlib,json,logging,time
from fastapi import Depends,HTTPException,Request,Query
from fastapi.responses import JSONResponse,Response
from pydantic import BaseModel,ConfigDict,Field
from .agent_tools import MeetingTools,normal,MonitorQuery,ActionQuery
from .meeting_agent import run_agent,run_slot,AgentUnavailable,AgentBusy,AgentInvalid
from . import agent_state,agent_workspace,agent_monitor,agent_voice
from .secretary_agent import extract_draft,MinutesDraft,candidate_owners,validate_edit,processmaker_export


class Question(BaseModel):
    model_config=ConfigDict(extra='forbid')
    question:str=Field(min_length=3,max_length=2000)
    new_conversation:bool=False
    conversation_id:str | None=Field(None,max_length=64)


class DraftRequest(BaseModel):
    model_config=ConfigDict(extra='forbid')
    meeting_no:str=Field(min_length=1,max_length=80)
    notes:str=Field(min_length=10,max_length=18000)


class Approval(BaseModel):
    model_config=ConfigDict(extra='forbid')
    confirmed:bool
    revision:int=Field(1,ge=1)


class Subscribe(BaseModel):
    model_config=ConfigDict(extra='forbid')
    enabled:bool
    interval_seconds:int=Field(300,ge=300,le=86400)


class DraftEdit(BaseModel):
    model_config=ConfigDict(extra="forbid")
    revision:int=Field(ge=1)
    payload:MinutesDraft


class SpeechRequest(BaseModel):
    model_config=ConfigDict(extra="forbid")
    conversation_id:str=Field(min_length=1,max_length=64)
    turn_id:str=Field(min_length=1,max_length=64)
    part:int=Field(0,ge=0,le=20)


def snapshot(principal,module,meeting_id=None):
    from .production_app import _store_response,_normalise_dates
    from .production_store import authorized_meeting_snapshot,ProductionAccessDenied
    def read(con,scope):
        if module not in scope['license']['modules']:raise ProductionAccessDenied('Module not licensed')
        rows,complete=authorized_meeting_snapshot(con,scope,**({"meeting_id":meeting_id} if meeting_id is not None else {}))
        _normalise_dates(rows)
        return scope,rows,complete
    return _store_response(read,principal)


def ensure_still_authorized(principal,initial_scope,initial_rows,module):
    # A role, hierarchy, BPMS binding or meeting membership can change while the
    # external model runs. Re-check source visibility before returning any content.
    scope,rows,_=snapshot(principal,module)
    if agent_workspace.scope_stamp(scope)!=agent_workspace.scope_stamp(initial_scope):
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
    return agent_state.alert_status(scope,principal.subject,result)


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
                'direct_processmaker_write':False,'voice_enabled':bool(cfg.get('voice_enabled'))}

    @app.post('/api/ask')
    def ask(body:Question,value=Depends(csrf)):
        _,session,principal=value
        def work():
            with run_slot((str(principal.tenant_id),principal.subject)):
                scope,rows,complete=snapshot(principal,1)
                tools=MeetingTools(rows,complete=complete,modules=scope['license']['modules'])
                identifier=None if body.new_conversation else (body.conversation_id or session.get('conversation_id'))
                history=[]
                if identifier:
                    try:
                        previous=agent_workspace.conversation(scope,principal.subject,identifier,{m['meeting_id'] for m in rows})
                        history=[{'question':t['question'],'previous_answer':[c['text'][:700] for c in t['answer'].get('claims',[])][:6],'answered_at':t['created_at']} for t in previous['turns'][-4:]]
                    except PermissionError:raise HTTPException(404,'گفت‌وگو در دامنه فعلی در دسترس نیست؛ گفت‌وگوی تازه بسازید.')
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
                try:
                    conversation_id,turn_id=agent_workspace.save_turn(scope,principal.subject,identifier,body.question,result,{m['meeting_id'] for m in rows})
                except PermissionError:raise HTTPException(409,'گفت‌وگو تغییر کرده است؛ دوباره بارگذاری کنید.')
                session['conversation_id']=conversation_id
                session['agent_questions']=(history+[body.question])[-4:]
                agent_state.audit(scope,principal.subject,'AGENT_COMPLETED',{
                    **detail,'model':result['model'],'tools':[t['tool'] for t in result['tool_trace']],
                    **result['usage'],'coverage_complete':complete})
                return {**result,'company':scope['company'],'role':scope['role'],'conversation_id':conversation_id,'turn_id':turn_id}
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
                owners=candidate_owners(meeting,scope)
                if len(owners)>100:raise HTTPException(422,'تعداد مسئولان این جلسه بیش از دامنه استخراج است.')
                from zoneinfo import ZoneInfo
                import os
                today=datetime.now(ZoneInfo(os.getenv('AVAN_DATA_TIMEZONE','Asia/Tehran'))).date()
                payload=extract_draft(body.notes,meeting,owners,today=today)
                from .production_app import _oidc_config
                _oidc_config()[4].authenticate("Bearer "+session["access_token"])
                ensure_still_authorized(principal,scope,[meeting],2)
                identifier=agent_state.save_draft(scope,principal.subject,meeting['meeting_id'],payload)
                return {'id':identifier,'status':'draft','revision':1,'payload':payload,'read_only':True}
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
        if scope['role']!='SysAdmin' and scope['external_user_id']!=meeting.get('secretary_uid'):
            raise HTTPException(403,'تأیید پیش‌نویس فقط برای دبیر جلسه یا مدیر سیستم مجاز است.')
        try:result=agent_state.approve_draft(scope,principal.subject,identifier,{m['meeting_id'] for m in rows},body.revision)
        except agent_workspace.RevisionConflict:raise HTTPException(409,'نسخه پیش‌نویس تغییر کرده است؛ دوباره بازبینی کنید.')
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

    @app.get('/api/conversations')
    def conversations(value=Depends(authorized)):
        scope,rows,_=snapshot(value[2],1)
        items=agent_workspace.conversations(scope,value[2].subject,{m['meeting_id'] for m in rows})
        return {'conversations':[{k:v for k,v in c.items() if k!='turns'} for c in items]}

    def load_conversation(principal,identifier):
        scope,rows,_=snapshot(principal,1)
        try:record=agent_workspace.conversation(scope,principal.subject,identifier,{m['meeting_id'] for m in rows})
        except PermissionError:raise HTTPException(404,'گفت‌وگو در دسترس نیست.')
        return scope,rows,record

    @app.get('/api/conversations/{identifier}')
    def conversation(identifier:str,value=Depends(authorized)):
        return agent_workspace.public_conversation(load_conversation(value[2],identifier)[2])

    @app.post('/api/conversations/{identifier}/delete')
    def remove_conversation(identifier:str,value=Depends(csrf)):
        scope,_,_=snapshot(value[2],1)
        agent_workspace.delete_conversation(scope,value[2].subject,identifier)
        if value[1].get('conversation_id')==identifier:value[1].pop('conversation_id',None)
        return {'deleted':True}

    @app.get('/api/secretary/drafts')
    def drafts(value=Depends(authorized)):
        scope,rows,_=snapshot(value[2],2)
        return {'drafts':agent_state.list_drafts(scope,value[2].subject,{m['meeting_id'] for m in rows})}

    @app.post('/api/secretary/drafts/{identifier}/edit')
    def edit_draft(identifier:str,body:DraftEdit,value=Depends(csrf)):
        scope,rows,record=load_draft(value[2],identifier)
        meeting=next(m for m in rows if m['meeting_id']==record['meeting_id'])
        try:
            payload=validate_edit(body.payload,record['payload'],candidate_owners(meeting,scope))
            return agent_state.update_draft(scope,value[2].subject,identifier,{m['meeting_id'] for m in rows},payload,body.revision)
        except ValueError as exc:raise HTTPException(422,str(exc))
        except agent_workspace.RevisionConflict:raise HTTPException(409,'پیش‌نویس تغییر کرده یا تأیید شده است؛ دوباره بارگذاری کنید.')

    @app.post('/api/secretary/drafts/{identifier}/reopen')
    def reopen_draft(identifier:str,body:Approval,value=Depends(csrf)):
        if not body.confirmed:raise HTTPException(422,'بازگشایی نیازمند تأیید است.')
        scope,rows,_=load_draft(value[2],identifier)
        try:return agent_state.reopen_draft(scope,value[2].subject,identifier,{m['meeting_id'] for m in rows},body.revision)
        except agent_workspace.RevisionConflict:raise HTTPException(409,'نسخه پیش‌نویس تغییر کرده است.')

    @app.get('/api/secretary/drafts/{identifier}/processmaker')
    def native_export(identifier:str,value=Depends(authorized)):
        scope,rows,record=load_draft(value[2],identifier)
        if record['status']!='approved':raise HTTPException(409,'ابتدا پیش‌نویس را تأیید کنید.')
        meeting=next(m for m in rows if m['meeting_id']==record['meeting_id'])
        try:payload=processmaker_export(record,meeting,candidate_owners(meeting,scope))
        except ValueError as exc:raise HTTPException(422,str(exc))
        agent_state.audit(scope,value[2].subject,'SECRETARY_NATIVE_EXPORT',{'draft_id':identifier})
        return JSONResponse(payload,headers={'Content-Disposition':'attachment; filename="processmaker-actions.json"'})

    @app.post('/api/reports/actions')
    def action_report(body:ActionQuery,value=Depends(csrf)):
        from .agent_reports import report
        scope,rows,complete=snapshot(value[2],3)
        try:return report(rows,scope,complete,body)
        except ValueError:raise HTTPException(422,'بازه زمانی یا فیلتر گزارش معتبر نیست.')

    @app.post('/api/reports/actions/export')
    def action_export(body:ActionQuery,value=Depends(csrf)):
        from .agent_reports import export_csv
        scope,rows,complete=snapshot(value[2],3)
        try:data=export_csv(rows,scope,complete,body)
        except ValueError:raise HTTPException(422,'فیلتر گزارش معتبر نیست.')
        agent_state.audit(scope,value[2].subject,'ACTION_REPORT_EXPORTED',{'coverage_complete':complete})
        return Response(data,media_type='text/csv; charset=utf-8',headers={'Content-Disposition':'attachment; filename="meeting-actions.csv"'})

    @app.get('/api/meetings/{meeting_id}')
    def meeting_detail(meeting_id:int,value=Depends(authorized)):
        _,rows,_=snapshot(value[2],1,meeting_id)
        if not rows:raise HTTPException(404,'جلسه در دسترس نیست.')
        return rows[0]

    @app.post('/api/monitor')
    def monitor(value=Depends(csrf)):
        _,_,principal=value
        result=monitor_for(principal)
        # Current result contains no cached source text. Subscription status is metadata only.
        state=agent_monitor.status({'tenant_id':str(principal.tenant_id)},principal.subject)
        return {**result,'subscription':state,'subscribed':state['enabled']}

    @app.post('/api/monitor/subscribe')
    def subscribe(body:Subscribe,value=Depends(csrf)):
        _,session,principal=value
        scope,_,_=snapshot(principal,4)
        try:return agent_monitor.subscribe(scope,principal.subject,session,body.enabled,body.interval_seconds)
        except ValueError as exc:raise HTTPException(409,str(exc))

    @app.post('/api/monitor/alerts/{identifier}/acknowledge')
    def acknowledge(identifier:str,value=Depends(csrf)):
        result=monitor_for(value[2])
        if not any(a['id']==identifier for a in result['alerts']):raise HTTPException(404,'هشدار در دامنه فعلی موجود نیست.')
        agent_state.acknowledge({'tenant_id':str(value[2].tenant_id)},value[2].subject,identifier)
        return {'acknowledged':True}

    @app.post('/api/voice/transcribe')
    async def transcribe(request:Request,value=Depends(csrf)):
        from starlette.concurrency import run_in_threadpool
        principal=value[2]
        scope,rows,_=await run_in_threadpool(snapshot,principal,1)
        try:agent_voice.configuration()
        except AgentUnavailable as exc:raise HTTPException(503,str(exc))
        data=bytearray()
        async for chunk in request.stream():
            data.extend(chunk)
            if len(data)>agent_voice.MAX_AUDIO:raise HTTPException(413,'حداکثر حجم صوت ۸ مگابایت است.')
        def work():
            with run_slot((str(principal.tenant_id),principal.subject)):
                try:content=agent_voice.transcribe(bytes(data),request.headers.get('content-type',''))
                except AgentInvalid:raise HTTPException(422,'فایل صوت معتبر نیست یا متن از حد مجاز بیشتر است.')
                from .production_app import _oidc_config
                _oidc_config()[4].authenticate('Bearer '+value[1]['access_token'])
                ensure_still_authorized(principal,scope,rows,1)
                agent_state.audit(scope,principal.subject,'VOICE_TRANSCRIBED',{})
                return {'text':content,'requires_review':True}
        return await run_in_threadpool(guard_model,work)

    @app.post('/api/voice/speech')
    def speech(body:SpeechRequest,value=Depends(csrf)):
        principal=value[2]
        def work():
            with run_slot((str(principal.tenant_id),principal.subject)):
                scope,rows,record=load_conversation(principal,body.conversation_id)
                turn=next((t for t in record['turns'] if t['id']==body.turn_id),None)
                if not turn:raise HTTPException(404,'پاسخ ذخیره‌شده موجود نیست.')
                audio,parts=agent_voice.speak(turn['answer'],body.part)
                from .production_app import _oidc_config
                _oidc_config()[4].authenticate('Bearer '+value[1]['access_token'])
                ensure_still_authorized(principal,scope,rows,1)
                agent_state.audit(scope,principal.subject,'VOICE_GENERATED',{})
                return Response(audio,media_type='audio/mpeg',headers={'X-AVAN-Audio-Parts':str(parts)})
        return guard_model(work)
