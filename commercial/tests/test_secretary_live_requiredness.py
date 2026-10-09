import copy
import pytest

from commercial import secretary_runtime as runtime
from commercial import secretary_catalog as catalog
from commercial import secretary_time
from commercial.tests.test_secretary_inbox import task
from commercial.tests.test_secretary_workflow import S


def all_optional_pack(pack,stage):
    p=copy.deepcopy(pack)
    for owner in ("meeting","action"):
        if stage in p.get(owner,{}).get("stages",{}):
            stage_spec=p[owner]["stages"][stage]
            break
    else:
        stage_spec=p["stages"][stage]
    # Update both union/subtree because fixtures may not share object identity.
    for container in [p["stages"][stage],stage_spec]:
        for spec in container["fields"].values():
            spec["required"]=False
            for column in spec.get("columns",[]) or []:
                column["required"]=False
    return p


@pytest.mark.parametrize("stage",[
    "invitation","invitation_approval","minutes","minutes_approval",
    "action_execution","action_review","monitoring",
])
def test_avan_invents_no_required_fields_when_pm_marks_all_optional(pack,stage):
    p=all_optional_pack(pack,stage)
    t=task(p,stage)
    values={}
    if stage=="minutes":
        values={"MTG_MeetingHeld":"Held","MTG_Participants":{
            "1":{"MTG_ParticipantUserUID":"c"*32}
        }}
    if stage=="monitoring":
        values={"MTG_ActionSummary":{}}
    assert runtime.gaps(values,t)==[]


def test_required_flag_change_immediately_changes_gap(pack):
    p=all_optional_pack(pack,"minutes")
    t=task(p,"minutes")
    values={"MTG_MeetingHeld":"Held"}

    assert runtime.gaps(values,t)==[]

    p2=copy.deepcopy(p)
    p2["stages"]["minutes"]["fields"]["MTG_MeetingDiscussionSummary"]["required"]=True
    p2["meeting"]["stages"]["minutes"]["fields"]["MTG_MeetingDiscussionSummary"]["required"]=True
    t2=task(p2,"minutes")

    gaps=runtime.gaps(values,t2)
    assert [x["field"] for x in gaps]==["MTG_MeetingDiscussionSummary"]

    p3=copy.deepcopy(p2)
    p3["stages"]["minutes"]["fields"]["MTG_MeetingDiscussionSummary"]["required"]=False
    p3["meeting"]["stages"]["minutes"]["fields"]["MTG_MeetingDiscussionSummary"]["required"]=False
    assert runtime.gaps(values,task(p3,"minutes"))==[]


def test_required_grid_column_is_owned_by_pm(pack):
    p=all_optional_pack(pack,"minutes")
    for container in [
        p["stages"]["minutes"]["fields"]["MTG_Participants"],
        p["meeting"]["stages"]["minutes"]["fields"]["MTG_Participants"],
    ]:
        column=next(c for c in container["columns"] if c["id"]=="MTG_AttendanceStatus")
        column["required"]=True

    values={"MTG_Participants":{"1":{
        "MTG_ParticipantUserUID":"c"*32,
        "MTG_ParticipantPosition":"مدیریت",
    }}}
    gaps=runtime.gaps(values,task(p,"minutes"))
    assert len(gaps)==1
    assert gaps[0]["field"]=="MTG_Participants.1.MTG_AttendanceStatus"

    values["MTG_Participants"]["1"]["MTG_AttendanceStatus"]="Present"
    assert runtime.gaps(values,task(p,"minutes"))==[]


def test_live_overlay_changes_only_requiredness(pack):
    stage="minutes"
    live=copy.deepcopy(pack["stages"][stage]["fields"])
    for spec in live.values():
        spec["required"]=False
        for column in spec.get("columns",[]) or []:
            column["required"]=False
    live["MTG_MeetingDiscussionSummary"]["required"]=True

    overlaid=catalog._overlay_live_requiredness(pack,stage,live)

    assert overlaid["stages"][stage]["fields"]["MTG_MeetingDiscussionSummary"]["required"] is True
    assert overlaid["stages"][stage]["fields"]["MTG_ParkingLot"]["required"] is False
    assert overlaid["live_requiredness_hash"]
    # Writable surface is still the reviewed adapter, not arbitrary PM fields.
    assert set(overlaid["stages"][stage]["fields"])==set(pack["stages"][stage]["fields"])


def test_collective_on_time_attendance_marks_everyone_present(pack):
    p=all_optional_pack(pack,"minutes")
    t=task(p,"minutes",{
        "MTG_MeetingStartTime":"10:00",
    })
    current={
        "MTG_Participants":{
            "1":{"MTG_ParticipantUserUID":"c"*32,"MTG_ParticipantPosition":"مدیر"},
            "2":{"MTG_ParticipantUserUID":"s"*32,"MTG_ParticipantPosition":"دبیر"},
        }
    }
    result=secretary_time.apply(runtime,{
        "notes":"هم شرکت کنندگان سر تایم جلسه حاضر بودند",
        "task":t,
        "current":current,
        "history":[],
        "questions":[],
    })
    assert result is not None
    assert result["intent"]=="resolved"
    for row in result["values"]["MTG_Participants"].values():
        assert row["MTG_AttendanceStatus"]=="Present"
        assert row["MTG_AttendanceTime"]=="10:00"


def test_collective_presence_without_start_time_still_marks_present(pack):
    p=all_optional_pack(pack,"minutes")
    t=task(p,"minutes",{})
    current={"MTG_Participants":{
        "1":{"MTG_ParticipantUserUID":"c"*32},
        "2":{"MTG_ParticipantUserUID":"s"*32},
    }}
    result=secretary_time.apply(runtime,{
        "notes":"همه شرکت‌کنندگان حاضر بودند",
        "task":t,
        "current":current,
        "history":[],
        "questions":[],
    })
    assert result["intent"]=="resolved"
    assert all(row["MTG_AttendanceStatus"]=="Present" for row in result["values"]["MTG_Participants"].values())
    assert all(not row.get("MTG_AttendanceTime") for row in result["values"]["MTG_Participants"].values())


def test_grid_owner_uid_can_be_supported_by_unique_role_in_same_row(pack):
    p=all_optional_pack(pack,"minutes")
    t=task(p,"minutes")
    spec=runtime.form(t)["MTG_Actions"]
    u1="1"*32;u2="2"*32
    directory={
        u1:{"active":True,"username":"mgr.strategy","name":"مدیر استراتژی","position":"مدیر استراتژی","unit":"استراتژی"},
        u2:{"active":True,"username":"mgr.sales","name":"مدیر فروش","position":"مدیر فروش","unit":"فروش"},
    }
    value={
        "1":{
            "MTG_ActionDescription":"تدوین برنامه استراتژی",
            "MTG_ActionOwnerUID":u1,
            "MTG_ActionOwnerPosition":"مدیر استراتژی",
        },
        "2":{
            "MTG_ActionDescription":"ساخت برنامه فروش",
            "MTG_ActionOwnerUID":u2,
            "MTG_ActionOwnerPosition":"مدیر فروش",
        },
    }
    evidence="""اثدامات
مصوبه یک با مدیر استراتژی تا تاریخ 20 مهر وقت داره که تدوین کنه
مصوبه 2 با مدیر فروش که بتونه برنامه فروش رو بسازه تا تاریخ 20 مهر"""
    resolved,questions=runtime.resolve_extracted_people(
        "MTG_Actions",value,spec,directory,evidence=evidence,current=None)
    assert questions==[]
    assert resolved["1"]["MTG_ActionOwnerUID"]==u1
    assert resolved["2"]["MTG_ActionOwnerUID"]==u2


def test_assistant_drops_old_attendance_question_when_pm_makes_it_optional(pack):
    p=all_optional_pack(pack,"minutes")
    t=task(p,"minutes")
    values={
        "MTG_MeetingHeld":"Held",
        "MTG_Participants":{"1":{
            "MTG_ParticipantUserUID":"c"*32,
            "MTG_ParticipantPosition":"مدیریت سامانه",
        }},
    }
    state=runtime.assistant_state(
        values,t,S,
        questions=["وضعیت حضور شرکت‌کننده ردیف 1 (مدیریت سامانه) را مشخص کنید: حاضر، غایب یا غیبت موجه."])
    assert state["missing"]==[]
    assert "وضعیت حضور شرکت‌کننده" not in state["message"]


def test_assistant_drops_old_discussion_question_when_pm_makes_it_optional(pack):
    p=all_optional_pack(pack,"minutes")
    t=task(p,"minutes")
    state=runtime.assistant_state(
        {"MTG_MeetingHeld":"Held"},t,S,
        questions=["لطفاً شرح و جمع‌بندی مذاکرات جلسه را مشخص کنید."])
    assert state["missing"]==[]
    assert "شرح و جمع‌بندی مذاکرات" not in state["message"]


def test_requiredness_hash_changes_when_live_pm_required_flag_changes(pack):
    stage="minutes"
    live=copy.deepcopy(pack["stages"][stage]["fields"])
    for spec in live.values():
        spec["required"]=False
        for column in spec.get("columns",[]) or []:
            column["required"]=False
    first=catalog._overlay_live_requiredness(pack,stage,live)
    live["MTG_MeetingDiscussionSummary"]["required"]=True
    second=catalog._overlay_live_requiredness(pack,stage,live)
    assert first["live_requiredness_hash"]!=second["live_requiredness_hash"]
