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
        def variables(self,case):
            raise AssertionError("native upload must not GET ProcessMaker case variables (403)")
        def set_variables(self,case,index,values,operation=None):
            calls["set_variables"]=(case,index,copy.deepcopy(values),operation)
        def close(self):pass

    monkeypatch.setattr(evidence,"PM",PM)
    monkeypatch.setattr(evidence,"token",lambda *a,**kw:"token")
    monkeypatch.setattr(evidence.runtime,"_native_case_values",
                        lambda scope,case: {})
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
    assert calls["set_variables"][0:2]==(t["case_uid"],1)
    assert calls["set_variables"][2]["MTGA_EvidenceFile1"]==[{
        "appDocUid":"3"*32,
        "name":"proof.pdf",
        "version":1,
    }]
    assert result["app_doc_filename"]=="proof.pdf"




def test_native_upload_preserves_previous_refs_when_rest_variables_is_forbidden(monkeypatch):
    t=task("minutes")
    field="MTG002_MeetingAttachment"
    previous={"appDocUid":"1"*32,"name":"previous.pdf","version":1}
    recorded={}
    class PM:
        def __init__(self,*a,**kw):pass
        def assigned(self,*a):return t["index"]
        def variables(self,*a):
            raise AssertionError("ProcessMaker GET /cases/{uid}/variables returns 403")
        def upload_input_document(self,*a,**kw):
            return {"app_doc_uid":"2"*32,"app_doc_version":1,
                    "app_doc_filename":"new.pdf"}
        def set_variables(self,case,index,payload,**kw):
            recorded.update(copy.deepcopy(payload))
        def close(self):pass

    monkeypatch.setattr(evidence,"PM",PM)
    monkeypatch.setattr(evidence,"token",lambda *a,**kw:"personal")
    monkeypatch.setattr(
        evidence.runtime,"_native_case_values",
        lambda scope,case:{field:[previous]},
    )
    scope={"source_id":"source","external_user_id":"u"*32}
    result=evidence.upload_field_document(
        t,scope,"actor",field,"new.pdf","application/pdf",b"%PDF-test")
    assert result["app_doc_uid"]=="2"*32
    assert recorded[field]==[previous,{
        "appDocUid":"2"*32,"name":"new.pdf","version":1
    }]


def test_pm3_light_upload_uses_field_name_and_two_step_protocol():
    from commercial.secretary_processmaker import PM

    class Response:
        status_code=200
        content=b'{"status":"ok"}'
        def json(self):return {"status":"ok"}

    class Client:
        def __init__(self):self.posts=[]
        def post(self,url,**kwargs):
            self.posts.append((url,kwargs))
            return Response()

    pm=object.__new__(PM)
    pm.base="http://pm.local/api/1.0/workflow"
    pm.client=Client()
    calls=[]

    def call(method,path,data=None,operation=None):
        calls.append((method,path,copy.deepcopy(data),operation))
        return [{
            "appDocUid":"4"*32,
            "docVersion":1,
            "appDocFilename":"proof.pdf",
            "appDocType":"INPUT",
            "appDocIndex":7,
        }]
    pm.call=call

    result=pm.upload_input_document(
        "a"*32,
        "6343078616ac0d6c53a98d9079721622",
        "MTGA_EvidenceFile1",
        "proof.pdf",
        b"%PDF-test",
        "application/pdf",
    )

    assert calls[0][0:2]==(
        "POST",
        "/light/case/"+"a"*32+"/upload",
    )
    assert calls[0][2]==[{
        "name":"proof.pdf",
        "appDocType":"INPUT",
        "docUid":"6343078616ac0d6c53a98d9079721622",
        "fieldName":"MTGA_EvidenceFile1",
    }]
    assert len(pm.client.posts)==1
    url,kwargs=pm.client.posts[0]
    assert url.endswith("/light/case/"+"a"*32+"/upload/"+"4"*32)
    assert "form[MTGA_EvidenceFile1]" in kwargs["files"]
    filename,payload,mime=kwargs["files"]["form[MTGA_EvidenceFile1]"]
    assert filename=="proof.pdf"
    assert payload==b"%PDF-test"
    assert mime=="application/pdf"
    assert result["app_doc_uid"]=="4"*32
    assert result["doc_uid"]=="6343078616ac0d6c53a98d9079721622"
    assert result["field_name"]=="MTGA_EvidenceFile1"



def test_field_documents_prefers_pmx_multiplefile_refs_without_document_step(monkeypatch):
    t=task("action_review",{
        "MTGA_EvidenceFile1":[{
            "appDocUid":"5"*32,
            "name":"proof-from-execution.pdf",
            "version":2,
        }]
    })
    monkeypatch.setattr(
        evidence,"native_documents",
        lambda *a,**kw:(_ for _ in ()).throw(AssertionError("must not need Input Document step listing"))
    )
    docs=evidence.field_documents(
        t,{"source_id":"source"},"actor","MTGA_EvidenceFile1")
    assert docs==[{
        "app_doc_uid":"5"*32,
        "app_doc_version":2,
        "app_doc_filename":"proof-from-execution.pdf",
        "app_doc_type":"INPUT",
        "doc_uid":"6343078616ac0d6c53a98d9079721622",
    }]



def test_live_dynaform_promotes_reviewed_file_control_into_older_pack():
    from commercial import secretary_catalog as catalog

    p=pack()
    p["stages"]["action_execution"]["fields"].pop("MTGA_EvidenceFile1",None)
    p["action"]["stages"]["action_execution"]["fields"].pop("MTGA_EvidenceFile1",None)

    live=copy.deepcopy(pack()["stages"]["action_execution"]["fields"])
    overlaid=catalog._overlay_live_requiredness(p,"action_execution",live)

    control=runtime.file_controls({
        "stage":"action_execution",
        "pack":overlaid,
    })["MTGA_EvidenceFile1"]

    assert control["mode"]=="edit"
    assert control["inp_doc_uid"]=="6343078616ac0d6c53a98d9079721622"


def test_live_file_mode_changes_from_upload_to_view_between_stages():
    from commercial import secretary_catalog as catalog

    p=pack()

    live_execution=copy.deepcopy(p["stages"]["action_execution"]["fields"])
    live_execution["MTGA_EvidenceFile1"]["mode"]="edit"
    execution=catalog._overlay_live_requiredness(
        p,"action_execution",live_execution)

    live_review=copy.deepcopy(p["stages"]["action_review"]["fields"])
    live_review["MTGA_EvidenceFile1"]["mode"]="view"
    review=catalog._overlay_live_requiredness(
        p,"action_review",live_review)

    assert runtime.file_controls({
        "stage":"action_execution","pack":execution
    })["MTGA_EvidenceFile1"]["mode"]=="edit"

    assert runtime.file_controls({
        "stage":"action_review","pack":review
    })["MTGA_EvidenceFile1"]["mode"]=="view"


def test_minutes_attachment_uses_same_native_input_document_for_approval():
    p=pack()
    minutes=runtime.file_controls({"stage":"minutes","pack":p})
    approval=runtime.file_controls({"stage":"minutes_approval","pack":p})

    assert minutes["MTG002_MeetingAttachment"]["inp_doc_uid"] == (
        approval["MTG002_MeetingAttachment"]["inp_doc_uid"]
    )
