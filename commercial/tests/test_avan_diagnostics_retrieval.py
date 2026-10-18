import json
from types import SimpleNamespace
import httpx
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from commercial import diagnostics, secretary_runtime as runtime, secretary_evidence as evidence
from commercial.secretary_processmaker import PM
from commercial.retrieval import ranked_indices
from commercial.tests.test_secretary_native_files import task


def test_reviewed_alias_and_hidden_routing_choice():
    t=task('invitation_approval',{'MTG_InvitationChairComment_1':'اصلاح شود'})
    assert runtime.initial(t)['MTG_InvitationChairComment']=='اصلاح شود'
    assert runtime.form(t)['MTG_InvitationChairComment']['type']=='textarea'
    values=runtime.labelled({'MTG_InvitationChairComment':'تأیید'},t,{'directory':{}})
    assert values['MTG_InvitationChairComment_1']==values['MTG_InvitationChairComment']=='تأیید'
    review=runtime.form(task('action_review'))['MTGA_ReviewStatus2']
    assert review['type']=='dropdown' and review['required']
    assert {x['value'] for x in review['options']}=={'Closed','Rework'}


def test_native_array_shapes_and_multiple_false_metadata():
    ref={'app_doc_uid':'a'*32,'app_doc_filename':'a.txt','app_doc_version':2}
    assert runtime.native_file_refs({'1':ref})==runtime.native_file_refs(ref)
    assert runtime.native_file_refs(ref)[0]['version']==2
    assert runtime.file_controls(task('action_execution'))['MTGA_EvidenceFile1']['multiple']


@pytest.mark.parametrize('link_fails',[False,True])
def test_upload_preserves_previous_refs_and_reports_partial_success(monkeypatch,link_fails):
    from commercial.tests.test_secretary_workflow import S
    previous={'appDocUid':'a'*32,'name':'previous.pdf','version':1}
    writes=[]
    def link(case,index,values,**kwargs):
        writes.append(values)
        if link_fails:raise TimeoutError('private-message')
    pm=SimpleNamespace(assigned=lambda *a:1,close=lambda:None,
        upload_input_document=lambda *a,**k:{'app_doc_uid':'b'*32},
        variables=lambda *a:{'MTGA_EvidenceFile1':{'1':previous}},set_variables=link)
    monkeypatch.setattr(evidence,'PM',lambda *a,**k:pm)
    monkeypatch.setattr(evidence,'token',lambda *a:'private-token')
    def run():return evidence.upload_field_document(task('action_execution'),S,'actor','MTGA_EvidenceFile1','new.txt','text/plain',b'new')
    if link_fails:
        with pytest.raises(HTTPException) as exc:run()
        assert exc.value.status_code==502 and 'منتقل شد' in exc.value.detail
        assert 'private-message' not in exc.value.detail
    else:assert run()['app_doc_uid']=='b'*32
    assert len(writes)==1
    assert writes[0]['MTGA_EvidenceFile1'][0]==previous
    assert len(writes[0]['MTGA_EvidenceFile1'])==2


@pytest.mark.parametrize('body',[b'<html>login</html>',b'{"error":"rejected"}'])
def test_upload_rejects_false_http_success_without_retry(body):
    calls=[]
    def transport(request):
        calls.append(request)
        if len(calls)==1:return httpx.Response(200,json=[{'appDocUid':'a'*32}])
        return httpx.Response(200,content=body)
    pm=PM.__new__(PM);pm.base='https://pm.test/api/1.0/workflow'
    pm.client=httpx.Client(transport=httpx.MockTransport(transport))
    try:
        with pytest.raises(HTTPException):pm.upload_input_document('b'*32,'c'*32,'Evidence','a.txt',b'text')
    finally:pm.close()
    assert len(calls)==2
    assert calls[1].extensions['timeout']['read']==120


def test_diagnostics_excludes_messages_content_and_secrets(tmp_path,monkeypatch):
    monkeypatch.setenv('AVAN_STATE_DIR',str(tmp_path))
    token=diagnostics.request_id.set('request-1234567890123456')
    try:
        try:raise RuntimeError('secret exception message')
        except RuntimeError as error:diagnostics.emit('upload.failed',error=error,body='secret body',token='secret token',status=502)
    finally:diagnostics.request_id.reset(token)
    result=diagnostics.export_runtime()
    text=json.dumps(result)
    assert all(value not in text for value in ('secret exception message','secret body','secret token'))
    assert result['runtime'][0]['error_type']=='RuntimeError'
    assert result['runtime'][0]['stack']
    assert not diagnostics.export_runtime(selected_request_id='another-request-id')['runtime']


def test_ranked_persian_tokens_order_and_snapshot_scope():
    docs=['گزارش هَزینهٔ تامين قطعات ۱۲', 'گزارش فروش قطعات', 'هزینه تامین']
    assert ranked_indices('تأمین',docs)==[]  # lexical search does not invent synonyms
    assert ranked_indices('قطعات هزینه 12',docs)==[0]
    assert ranked_indices('قطعات هزینه 12',docs[1:])==[]
    assert ranked_indices('فروش قطعات',docs)==[1]


def test_support_export_enforces_identity_scope_and_omits_free_text(monkeypatch):
    from commercial import user_experience_routes as routes
    principal=SimpleNamespace(tenant_id='tenant',subject='actor')
    role=['Expert'];calls=[]
    monkeypatch.setattr(routes,'_identity',lambda value:(principal,role[0]))
    monkeypatch.setattr(routes.ux,'logs',lambda tenant,actor,role,**kw: calls.append((tenant,actor,role)) or {'scope':'self','logs':[{'event_code':'API_ERROR','detail':{'status':500,'message':'private','error':'secret'}}]})
    monkeypatch.setattr(diagnostics,'export_runtime',lambda **kw:{'schema':1,'includes_payloads':False,'runtime':[{'phase':'http.complete'}]})
    app=FastAPI();routes.register(app,lambda:None,lambda:None)
    client=TestClient(app)
    mine=client.get('/api/support/diagnostics').json()
    assert mine['runtime']==[] and 'private' not in json.dumps(mine) and 'secret' not in json.dumps(mine)
    assert calls==[('tenant','actor','Expert')]
    role[0]='GodAdmin'
    assert client.get('/api/support/diagnostics').json()['runtime']


def test_coverage_tracks_canonical_chair_comment_alias():
    from commercial.secretary_coverage import coverage_issues
    problems=coverage_issues('توضیحات رئیس: اصلاح شود',task('invitation_approval'),{},[],{})
    assert any('توضیحات' in message for message in problems)


def test_runtime_export_survives_unavailable_audit_store(monkeypatch):
    from commercial import user_experience_routes as routes
    principal=SimpleNamespace(tenant_id='tenant',subject='owner')
    monkeypatch.setattr(routes,'_identity',lambda value:(principal,'GodAdmin'))
    def unavailable(*args,**kwargs):raise RuntimeError('private SQL connection')
    monkeypatch.setattr(routes.ux,'logs',unavailable)
    monkeypatch.setattr(diagnostics,'export_runtime',lambda **kw:{'schema':1,'includes_payloads':False,'runtime':[]})
    app=FastAPI();routes.register(app,lambda:None,lambda:None)
    response=TestClient(app).get('/api/support/diagnostics')
    assert response.status_code==200 and response.json()['audit_unavailable']
    assert 'private SQL' not in response.text
