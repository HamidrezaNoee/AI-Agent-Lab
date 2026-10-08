from contextlib import contextmanager
from datetime import datetime, timezone
import json

import pytest

from commercial import user_experience as ux
from commercial import agent_storage
from commercial import meeting_agent


@pytest.fixture
def memory_store(monkeypatch):
    memory={"state":{},"audits":[]}

    class Tx:
        def get(self,name,default=None,lock=False):
            value=memory["state"].get(name,default)
            if isinstance(value,dict):
                return dict(value)
            if isinstance(value,list):
                return list(value)
            return value

        def put(self,name,value):
            memory["state"][name]=dict(value) if isinstance(value,dict) else value

        def audit(self,tenant,actor,event,detail):
            memory["audits"].append({
                "id":f"{len(memory['audits'])+1:032d}",
                "tenant":str(tenant),"actor":str(actor),"event":str(event),
                "at":datetime.now(timezone.utc),
                "detail":dict(detail),
            })

    @contextmanager
    def transaction():
        yield Tx()

    class Cursor:
        def __init__(self):
            self.rows=[]

        def execute(self,sql,*params):
            tenant=str(params[0]);index=1
            actor=None;event=None
            if "ActorID=?" in sql:
                actor=str(params[index]);index+=1
            if "EventCode=?" in sql:
                event=str(params[index])
            rows=[
                x for x in memory["audits"]
                if x["tenant"]==tenant
                and (actor is None or x["actor"]==actor)
                and (event is None or x["event"]==event)
            ]
            rows=list(reversed(rows))
            self.rows=[
                (x["id"],x["tenant"],x["actor"],x["event"],
                 x["at"].replace(tzinfo=None),json.dumps(x["detail"],ensure_ascii=False))
                for x in rows
            ]
            return self

        def fetchall(self):
            return self.rows

    class Connection:
        def cursor(self):
            return Cursor()
        def close(self):
            pass

    monkeypatch.setattr(agent_storage,"transaction",transaction)
    monkeypatch.setattr(agent_storage,"connect",lambda *args,**kwargs:Connection())
    return memory


def test_user_preferences_are_private_and_safe_by_default(memory_store):
    assert ux.preferences("tenant-1","user-a")=={
        "secretary_auto_play_voice":False,
        "voice_auto_transcribe":True,
        "voice_auto_send":False,
    }

    saved=ux.save_preferences("tenant-1","user-a",{
        "secretary_auto_play_voice":True,
        "voice_auto_transcribe":False,
        "voice_auto_send":True,
    })
    assert saved["secretary_auto_play_voice"] is True
    assert saved["voice_auto_transcribe"] is False
    # Auto-send can never remain on when automatic transcription is disabled.
    assert saved["voice_auto_send"] is False
    assert ux.preferences("tenant-1","user-a")==saved

    # Another user receives independent defaults.
    assert ux.preferences("tenant-1","user-b")["secretary_auto_play_voice"] is False
    assert any(x["event"]=="USER_PREFERENCES_CHANGED" for x in memory_store["audits"])


def test_cancelled_secretary_operation_cannot_late_commit(memory_store):
    request_id="request_1234567890abcdef"
    ux.start_operation("tenant-1","user-a",request_id,"secretary_task_turn",{
        "case_uid":"a"*32,"stage":"minutes",
    })
    ux.ensure_active("tenant-1","user-a",request_id)

    result=ux.cancel_operation("tenant-1","user-a",request_id)
    assert result["cancelled"] is True
    with pytest.raises(ux.OperationCancelled):
        ux.ensure_active("tenant-1","user-a",request_id)

    # A late model completion must not overwrite the cancellation.
    ux.finish_operation("tenant-1","user-a",request_id,"completed",{"result":"late"})
    with pytest.raises(ux.OperationCancelled):
        ux.ensure_active("tenant-1","user-a",request_id)


def test_support_logs_are_user_scoped_and_admin_sees_tenant(memory_store):
    ux.audit("tenant-1","user-a","API_ACTION",{"path":"/api/a","status":200})
    ux.audit("tenant-1","user-b","API_ERROR",{"path":"/api/b","status":503,"error":"failure"})
    ux.audit("tenant-2","user-c","API_ERROR",{"path":"/api/c","status":500})

    mine=ux.logs("tenant-1","user-a","Expert",limit=100)
    assert mine["scope"]=="self"
    assert {x["actor_id"] for x in mine["logs"]}=={"user-a"}

    admin=ux.logs("tenant-1","admin","SysAdmin",limit=100)
    assert admin["scope"]=="tenant"
    assert {x["actor_id"] for x in admin["logs"]}=={"user-a","user-b"}
    assert all(x["tenant_id"]=="tenant-1" for x in admin["logs"])

    errors=ux.logs("tenant-1","admin","SysAdmin",limit=100,event="API_ERROR")
    assert [x["actor_id"] for x in errors["logs"]]==["user-b"]


def test_audit_sanitizes_secret_fields(memory_store):
    ux.audit("tenant-1","user-a","API_ERROR",{
        "path":"/api/test",
        "message":"visible",
        "password":"must-not-log",
        "token":"must-not-log",
        "body":"must-not-log",
    })
    detail=memory_store["audits"][-1]["detail"]
    assert detail["path"]=="/api/test"
    assert detail["message"]=="visible"
    assert "password" not in detail
    assert "token" not in detail
    assert "body" not in detail


def test_cancel_run_slot_allows_immediate_replacement_without_old_finally_clobbering_it():
    key=("tenant-cancel","actor-cancel")
    first=meeting_agent.run_slot(key)
    first.__enter__()
    second=None
    try:
        with pytest.raises(meeting_agent.AgentBusy):
            with meeting_agent.run_slot(key):
                pass
        assert meeting_agent.cancel_run_slot(key) is True
        second=meeting_agent.run_slot(key)
        second.__enter__()
        # The late completion of the cancelled worker must not remove the new
        # generation's active marker.
        first.__exit__(None,None,None)
        first=None
        with pytest.raises(meeting_agent.AgentBusy):
            with meeting_agent.run_slot(key):
                pass
    finally:
        if first is not None:
            first.__exit__(None,None,None)
        if second is not None:
            second.__exit__(None,None,None)
        meeting_agent.cancel_run_slot(key)


def test_support_logs_filter_by_user_process_source_case_and_stage(memory_store):
    ux.audit("tenant-1","user-a","API_ACTION",{
        "source_id":"source-a","process_uid":"process-1","case_uid":"case-1",
        "stage":"minutes","request_id":"req-1111111111111111","message":"صورتجلسه",
    })
    ux.audit("tenant-1","user-b","API_ACTION",{
        "source_id":"source-b","process_uid":"process-2","case_uid":"case-2",
        "stage":"action_execution","request_id":"req-2222222222222222","message":"اقدام",
    })
    admin=ux.logs("tenant-1","admin","SysAdmin",limit=100,
                  actor_id="user-b",source_id="source-b",process_uid="process-2",
                  case_uid="case-2",stage="action_execution")
    assert len(admin["logs"])==1
    assert admin["logs"][0]["actor_id"]=="user-b"
    assert admin["logs"][0]["detail"]["case_uid"]=="case-2"
    assert set(admin["filters"])=={"actors","sources","processes","stages"}

    mine=ux.logs("tenant-1","user-a","Expert",limit=100,actor_id="user-b")
    assert {x["actor_id"] for x in mine["logs"]}=={"user-a"}


def test_support_log_text_search_matches_safe_operational_context(memory_store):
    ux.audit("tenant-1","user-a","API_ERROR",{
        "path":"/api/test","case_uid":"case-77","stage":"minutes","error":"ProcessMaker unavailable",
    })
    found=ux.logs("tenant-1","user-a","Expert",limit=100,q="processmaker")
    assert len(found["logs"])==1
    assert found["logs"][0]["detail"]["case_uid"]=="case-77"



def test_operation_failure_retains_source_process_and_case_context(memory_store):
    context={'source_id':'source-1','process_uid':'process-1','case_uid':'case-1','stage':'minutes'}
    ux.start_operation('tenant-1','user-a','req-1234567890123456','secretary_turn',context)
    ux.finish_operation('tenant-1','user-a','req-1234567890123456','failed',{'error':'timeout'})
    detail=memory_store['audits'][-1]['detail']
    assert all(detail[key]==value for key,value in context.items())
    assert detail['error']=='timeout'


def test_log_filters_are_parameterized_before_result_limit(monkeypatch):
    captured={}
    class Cursor:
        def execute(self,sql,*params):captured.update(sql=sql,params=params);return self
        def fetchall(self):return []
    class Connection:
        def cursor(self):return Cursor()
        def close(self):pass
    monkeypatch.setattr(agent_storage,'connect',Connection)
    ux.logs('tenant','owner','Expert',limit=100,actor_id='other',
        source_id='old-source',process_uid='old-process',case_uid='old-case',q="%' OR 1=1 --")
    sql=captured['sql']
    assert 'TOP 101' in sql and 'ISJSON(Detail)' in sql
    assert "'$.case_uid')=?" in sql and "'$.pack_id')=?" in sql
    assert 'CHARINDEX(LOWER(?),' in sql
    assert 'old-case' not in sql and 'OR 1=1' not in sql
    assert captured['params']==('tenant','owner','old-source','old-process','old-process','old-case',"%' OR 1=1 --")


def test_bound_godadmin_changes_keycloak_password_not_local_recovery(monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from types import SimpleNamespace
    from commercial import user_experience_routes as routes, user_accounts, setup_console
    principal=SimpleNamespace(subject='bound-owner',tenant_id='tenant')
    monkeypatch.setattr(routes,'is_godadmin',lambda p:True)
    calls=[]
    @contextmanager
    def directory():
        yield SimpleNamespace(password=lambda subject,password,revoke:(calls.append(subject),revoke()))
    monkeypatch.setattr(user_accounts,'directory',directory)
    monkeypatch.setattr(user_accounts,'revoke_sessions',lambda subject:calls.append('revoke:'+subject))
    monkeypatch.setattr(setup_console,'change_password',lambda *a:pytest.fail('Bound OIDC account must not rotate the local recovery password'))
    monkeypatch.setattr(ux,'audit',lambda *a:None)
    app=FastAPI()
    routes.register(app,lambda:('session',{},principal),lambda:('session',{},principal))
    with TestClient(app) as client:
        response=client.post('/api/user/password',json={'password':'strong-password-1234','confirmation':'strong-password-1234'})
    assert response.status_code==200
    assert response.json()['provider']=='keycloak'
    assert calls==['bound-owner','revoke:bound-owner']
