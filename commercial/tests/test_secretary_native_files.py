import copy,json
from pathlib import Path

from commercial import secretary_runtime as runtime
from commercial import secretary_evidence as evidence


def pack():
    p=json.loads(
        Path(__file__).parents[1]
        .joinpath("secretary_pack_reference.json")
        .read_text(encoding="utf-8")
    )
    return {
        **p,
        "id":"1"*24,
        "source_id":"source",
        "enabled":True,
        "revision":1,
        "monitor_lead_minutes":1440,
        "action_lead_minutes":60,
    }


def task(stage,native=None):
    p=pack()
    return {
        "case_uid":"a"*32,
        "index":1,
        "pack_id":p["id"],
        "stage":stage,
        "pack":p,
        "native":native or {},
        "title":"جلسه",
        "number":"100",
    }


def test_meeting_minutes_file_control_is_editable_and_approval_is_view_only():
    minutes=runtime.file_controls(task("minutes"))
    approval=runtime.file_controls(task("minutes_approval"))

    assert minutes["MTG002_MeetingAttachment"]["mode"]=="edit"
    assert minutes["MTG002_MeetingAttachment"]["inp_doc_uid"]=="8069894396a958d0a5007d7087550366"

    assert approval["MTG002_MeetingAttachment"]["mode"]=="view"
    assert approval["MTG002_MeetingAttachment"]["inp_doc_uid"]=="8069894396a958d0a5007d7087550366"


def test_action_evidence_is_editable_then_view_only():
    execution=runtime.file_controls(task("action_execution"))
    review=runtime.file_controls(task("action_review"))

    assert execution["MTGA_EvidenceFile1"]["mode"]=="edit"
    assert execution["MTGA_EvidenceFile1"]["inp_doc_uid"]=="6343078616ac0d6c53a98d9079721622"

    assert review["MTGA_EvidenceFile1"]["mode"]=="view"
    assert review["MTGA_EvidenceFile1"]["inp_doc_uid"]=="6343078616ac0d6c53a98d9079721622"


def test_view_file_control_rejects_upload():
    try:
        runtime.file_control(task("action_review"),"MTGA_EvidenceFile1",write=True)
    except PermissionError:
        pass
    else:
        raise AssertionError("review-stage evidence must be view-only")


def test_field_documents_filters_to_the_pmx_input_document(monkeypatch):
    t=task("action_review")

    docs=[
        {
            "app_doc_uid":"1"*32,
            "app_doc_version":"1",
            "app_doc_filename":"evidence.pdf",
            "doc_uid":"6343078616ac0d6c53a98d9079721622",
            "app_doc_create_date":"2026-10-09 18:00:00",
        },
        {
            "app_doc_uid":"2"*32,
            "app_doc_version":"1",
            "app_doc_filename":"unrelated.pdf",
            "doc_uid":"9"*32,
            "app_doc_create_date":"2026-10-09 19:00:00",
        },
    ]
    monkeypatch.setattr(evidence,"native_documents",lambda *a,**kw:copy.deepcopy(docs))

    result=evidence.field_documents(t,{"source_id":"source"},"actor","MTGA_EvidenceFile1")
    assert [x["app_doc_filename"] for x in result]==["evidence.pdf"]


def test_native_upload_uses_current_task_and_reviewed_input_doc_uid(monkeypatch):
    t=task("action_execution")
    calls={}

    class PM:
        def __init__(self,*a,**kw):pass
        def assigned(self,case,task_uid,person):
            calls["assigned"]=(case,task_uid,person)
            return 1
        def upload_input_document(self,case,input_doc_uid,field_name,filename,data,content_type,comment=""):
            calls["upload"]=(case,input_doc_uid,field_name,filename,data,content_type,comment)
            return {
                "app_doc_uid":"3"*32,
                "app_doc_version":"1",
                "app_doc_filename":filename,
                "doc_uid":input_doc_uid,
                "field_name":field_name,
                "app_doc_type":"INPUT",
            }
        def close(self):pass

    monkeypatch.setattr(evidence,"PM",PM)
    monkeypatch.setattr(evidence,"token",lambda *a,**kw:"token")
    monkeypatch.setattr(evidence,"field_documents",lambda *a,**kw:[{
        "app_doc_uid":"3"*32,
        "app_doc_version":"1",
        "app_doc_filename":"proof.pdf",
        "doc_uid":"6343078616ac0d6c53a98d9079721622",
        "app_doc_type":"INPUT",
    }])

    scope={"source_id":"source","external_user_id":"u"*32}
    result=evidence.upload_field_document(
        t,scope,"actor","MTGA_EvidenceFile1",
        "proof.pdf","application/pdf",b"%PDF-test"
    )

    expected_task=t["pack"]["stages"]["action_execution"]["task_uid"]
    assert calls["assigned"]==(t["case_uid"],expected_task,scope["external_user_id"])
    assert calls["upload"][1]=="6343078616ac0d6c53a98d9079721622"
    assert calls["upload"][2]=="MTGA_EvidenceFile1"
    assert result["app_doc_filename"]=="proof.pdf"
