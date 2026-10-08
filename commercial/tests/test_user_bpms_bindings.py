"""Regression tests for ADR-001: AVAN identity is independent from BPMS identity."""
from contextlib import contextmanager
from unittest.mock import patch
from uuid import UUID

import pytest

from commercial import (
    bpms_registry, production_onboarding, user_bpms_bindings,
    processmaker_store, native_access, production_license, agent_workspace,
)
from commercial.security import Principal


TENANT="168418b2-8fa6-4414-a37f-83c9a26da332"
SOURCE="a"*24


def test_username_match_is_suggestion_not_binding():
    avan={"subject":"sub-1","username":"amin.t","email":"amin@example.org",
          "name":"Amin Test","enabled":True}
    directory=[
        {"external_user_id":"1","username":"amin.t","display_name":"Amin Test",
         "email":"other@example.org","status":"ACTIVE","active":True,"unit":""},
        {"external_user_id":"2","username":"ali.j","display_name":"Ali J",
         "email":"amin@example.org","status":"ACTIVE","active":True,"unit":""},
    ]
    with patch.object(user_bpms_bindings,"_avan_user",return_value=({"tenant_id":TENANT},avan)),\
         patch.object(user_bpms_bindings,"_source",return_value={
             "id":SOURCE,"name":"PM 1","engine":"processmaker",
             "connection_type":"processmaker","enabled":True,"active":True}),\
         patch.object(user_bpms_bindings,"directory_users",return_value=directory):
        result=user_bpms_bindings.suggestions("sub-1",SOURCE)
    assert result["suggestions"][0]["external_user_id"]=="1"
    assert result["suggestions"][0]["reason"]=="username_exact"
    # Suggestion has no persistence side effect.
    assert "binding" not in result


class FakeTx:
    def __init__(self,state):
        self.store={"bpms_user_bindings":state}
        self.audits=[]
    def get(self,key,default,lock=False):
        return self.store.get(key,default)
    def put(self,key,value):
        self.store[key]=value
    def audit(self,*args):
        self.audits.append(args)


def test_admin_can_bind_avan_username_to_different_bpms_username():
    tx=FakeTx({"version":1,"bindings":[]})
    @contextmanager
    def transaction():
        yield tx
    avan={"subject":"sub-1","username":"amin.t","email":"amin@example.org",
          "name":"Amin Test","enabled":True}
    external={"external_user_id":"pm-ali","username":"ali.j","display_name":"Ali J",
              "email":"ali@example.org","status":"ACTIVE","active":True,"unit":"Sales"}
    source={"id":SOURCE,"name":"PM 1","engine":"processmaker",
            "connection_type":"processmaker","enabled":True,"active":True}
    with patch.object(user_bpms_bindings,"_avan_user",
                      return_value=({"tenant_id":TENANT},avan)),\
         patch.object(user_bpms_bindings,"_source",return_value=source),\
         patch.object(user_bpms_bindings,"directory_users",return_value=[external]),\
         patch.object(user_bpms_bindings.agent_storage,"transaction",transaction),\
         patch.object(user_bpms_bindings.setup,"audit"):
        saved=user_bpms_bindings.bind(
            subject="sub-1",source_id=SOURCE,external_user_id="pm-ali",
            match_method="manual")
    assert saved["external_username"]=="ali.j"
    assert saved["avan_subject"]=="sub-1"
    assert saved["match_method"]=="manual"
    assert tx.store["bpms_user_bindings"]["bindings"][0]["external_user_id"]=="pm-ali"


def test_adapter_directory_contract_is_tenant_scoped():
    source={"id":SOURCE,"name":"External","kind":"avan-rest-v1","engine":"camunda",
            "base_url":"https://bpms.example.org","bearer_token":"0123456789-secret",
            "enabled":True}
    payload={"schema_version":1,"tenant_id":TENANT,
             "as_of_utc":"2026-10-01T12:00:00Z",
             "users":[{"external_user_id":"u1","username":"amin.t",
                       "display_name":"Amin Test","email":"amin@example.org",
                       "status":"ACTIVE","active":True,"unit":"Sales"}]}
    with patch.object(bpms_registry,"_all",return_value=[source]),\
         patch.object(bpms_registry.setup,"get_setting",
                      side_effect={"company":{"tenant_id":TENANT}}.get),\
         patch.object(bpms_registry,"_request",return_value=payload) as request:
        users=bpms_registry.directory_users(SOURCE)
    assert users[0]["username"]=="amin.t"
    assert request.call_args.args[1]=="/avan/v1/directory/users"

    payload["tenant_id"]="different"
    with patch.object(bpms_registry,"_all",return_value=[source]),\
         patch.object(bpms_registry.setup,"get_setting",
                      side_effect={"company":{"tenant_id":TENANT}}.get),\
         patch.object(bpms_registry,"_request",return_value=payload):
        with pytest.raises(bpms_registry.BPMSUnavailable):
            bpms_registry.directory_users(SOURCE)


def test_avan_account_approval_does_not_require_bpms_user():
    state={"tenant_id":None,"company_name":None,"users":[]}
    @contextmanager
    def edit():
        yield state
    pending={"tenant_id":TENANT,"subject":"sub-1","username":"amin.t",
             "name":"Amin Test","email":"amin@example.org",
             "email_verified":True,"roles":["Expert"]}
    with patch.object(production_onboarding,"find_pending",return_value=pending),\
         patch.object(production_onboarding.native_access,"edit",edit),\
         patch("commercial.production_license.capacity",return_value={"max_users":10}),\
         patch.object(production_onboarding,"finish_pending"),\
         patch.object(production_onboarding.setup,"audit"):
        result=production_onboarding.approve_avan_user(
            tenant_id=TENANT,subject="sub-1",company_name="ACME",
            role="Expert",department_name="Sales",manager_subject=None)
    assert result["approved"] is True
    assert state["users"][0]["username"]=="amin.t"
    assert "pm_uid" not in state["users"][0]
    assert "pm_active" not in state["users"][0]


def test_processmaker_scope_uses_binding_of_selected_source_only():
    source_a="a"*24
    source_b="b"*24
    external_a="1"*32
    external_b="2"*32
    organization={"tenant_id":TENANT,"company_name":"ACME","users":[{
        "subject":"sub-1","username":"amin.t","name":"Amin","role":"Expert",
        "department_name":"Sales","enabled":True
    }]}
    profiles={
        source_a:{"id":source_a,"name":"PM A","mysql":{"timezone":"Asia/Tehran"}},
        source_b:{"id":source_b,"name":"PM B","mysql":{"timezone":"UTC"}},
    }
    bindings={
        source_a:{"sub-1":{"avan_subject":"sub-1","source_id":source_a,
                           "external_user_id":external_a,"status":"active"}},
        source_b:{"sub-1":{"avan_subject":"sub-1","source_id":source_b,
                           "external_user_id":external_b,"status":"active"}},
    }
    directory={
        external_a:{"name":"Ali A","email":None,"active":True,"unit":"A"},
        external_b:{"name":"Ali B","email":None,"active":True,"unit":"B"},
    }
    entitlement={"modules":frozenset({1,2,3,4}),"expires_at":None,
                 "mode":"local_evaluation"}
    principal=Principal(UUID(TENANT),"sub-1",frozenset())

    with patch.object(native_access,"read",return_value=organization), \
         patch.object(user_bpms_bindings,"active_processmaker_source_id",return_value=source_a), \
         patch.object(user_bpms_bindings,"bindings_by_source",
                      side_effect=lambda source_id:bindings[source_id]), \
         patch.object(user_bpms_bindings,"processmaker_profile",
                      side_effect=lambda source_id:profiles[source_id]), \
         patch.object(processmaker_store,"directory",return_value=directory), \
         patch.object(production_license,"entitlement",return_value=entitlement):
        scope_a=processmaker_store.verified_scope(object(),principal,source_id=source_a)
        scope_b=processmaker_store.verified_scope(object(),principal,source_id=source_b)

    assert scope_a["external_user_id"]==external_a
    assert scope_a["source_id"]==source_a
    assert scope_a["timezone"]=="Asia/Tehran"
    assert scope_b["external_user_id"]==external_b
    assert scope_b["source_id"]==source_b
    assert scope_b["timezone"]=="UTC"
    assert scope_a["visible_uids"]=={external_a}
    assert scope_b["visible_uids"]=={external_b}


def test_legacy_pm_uid_never_authorizes_without_explicit_binding():
    source="c"*24
    legacy_uid="3"*32
    organization={"tenant_id":TENANT,"company_name":"ACME","users":[{
        "subject":"sub-legacy","username":"legacy","name":"Legacy User",
        "role":"Expert","enabled":True,"pm_uid":legacy_uid,"pm_active":True
    }]}
    principal=Principal(UUID(TENANT),"sub-legacy",frozenset())
    profile={"id":source,"name":"PM","mysql":{"timezone":"Asia/Tehran"}}
    with patch.object(native_access,"read",return_value=organization), \
         patch.object(user_bpms_bindings,"active_processmaker_source_id",return_value=source), \
         patch.object(user_bpms_bindings,"bindings_by_source",return_value={}), \
         patch.object(user_bpms_bindings,"processmaker_profile",return_value=profile), \
         patch.object(processmaker_store,"directory",
                      return_value={legacy_uid:{"name":"Legacy","active":True,"unit":""}}):
        with pytest.raises(processmaker_store.EmployeeMappingRequired):
            processmaker_store.verified_scope(object(),principal,source_id=source)


def test_agent_scope_stamp_isolated_by_bpms_source_even_for_same_external_user():
    base={"tenant_id":TENANT,"external_user_id":"same-user","role":"Expert",
          "visible_uids":{"same-user"},"license":{"modules":frozenset({1})}}
    first=agent_workspace.scope_stamp({**base,"source_id":"a"*24})
    second=agent_workspace.scope_stamp({**base,"source_id":"b"*24})
    assert first!=second


def test_binding_live_revalidates_selected_external_user_even_when_directory_can_be_cached():
    tx=FakeTx({"version":1,"bindings":[]})
    @contextmanager
    def transaction():
        yield tx
    avan={"subject":"sub-1","username":"amin.t","email":"amin@example.org",
          "name":"Amin Test","enabled":True}
    source={"id":SOURCE,"name":"PM 1","engine":"processmaker",
            "connection_type":"processmaker","enabled":True,"active":True}
    inactive={"external_user_id":"pm-ali","username":"ali.j","display_name":"Ali J",
              "email":"ali@example.org","status":"INACTIVE","active":False,"unit":"Sales"}
    with patch.object(user_bpms_bindings,"_avan_user",
                      return_value=({"tenant_id":TENANT},avan)), \
         patch.object(user_bpms_bindings,"_source",return_value=source), \
         patch.object(user_bpms_bindings,"directory_users",return_value=[inactive]) as directory, \
         patch.object(user_bpms_bindings.agent_storage,"transaction",transaction):
        with pytest.raises(user_bpms_bindings.BindingError):
            user_bpms_bindings.bind(subject="sub-1",source_id=SOURCE,
                                    external_user_id="pm-ali")
    directory.assert_called_once_with(SOURCE,refresh=True)
    assert tx.store["bpms_user_bindings"]["bindings"]==[]

def test_bind_by_username_resolves_exact_active_bpms_username_case_insensitively():
    directory=[
        {"external_user_id":"pm-1","username":"Hamid.Noee","display_name":"Hamid Noee",
         "email":"h@example.org","status":"ACTIVE","active":True,"unit":"IT"},
        {"external_user_id":"pm-2","username":"other.user","display_name":"Other",
         "email":"o@example.org","status":"ACTIVE","active":True,"unit":"Sales"},
    ]
    expected={"avan_subject":"sub-1","source_id":SOURCE,
              "external_user_id":"pm-1","external_username":"Hamid.Noee"}
    with patch.object(user_bpms_bindings,"directory_users",return_value=directory) as read_directory, \
         patch.object(user_bpms_bindings,"bind",return_value=expected) as persist:
        result=user_bpms_bindings.bind_by_username(
            subject="sub-1",source_id=SOURCE,
            external_username="hamid.noee",approved_by="admin-1")
    assert result==expected
    read_directory.assert_called_once_with(SOURCE,refresh=True)
    persist.assert_called_once_with(
        subject="sub-1",source_id=SOURCE,external_user_id="pm-1",
        match_method="manual",approved_by="admin-1",
        _directory_snapshot=directory,
    )


def test_bind_by_username_rejects_missing_or_inactive_bpms_username():
    directory=[
        {"external_user_id":"pm-1","username":"inactive.user","display_name":"Inactive",
         "email":None,"status":"INACTIVE","active":False,"unit":""}
    ]
    with patch.object(user_bpms_bindings,"directory_users",return_value=directory), \
         patch.object(user_bpms_bindings,"bind") as persist:
        with pytest.raises(user_bpms_bindings.BindingError):
            user_bpms_bindings.bind_by_username(
                subject="sub-1",source_id=SOURCE,external_username="inactive.user")
    persist.assert_not_called()

