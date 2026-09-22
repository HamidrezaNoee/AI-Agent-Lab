"""Native adapter acceptance: serialized grids, permission isolation and current review semantics."""
from unittest.mock import patch
from contextlib import contextmanager
from uuid import UUID
import phpserialize
import pytest
from commercial import processmaker_store as store,native_access,setup_console as setup
from commercial.security import Principal

PARENT='f'*32; OWNER='a'*32; OTHER='b'*32

def raw(d):return phpserialize.dumps(d,charset='utf-8')
def meeting(owner=OWNER):
    return {'MTG_MinutesApproval':'Approved','MTG_MeetingNo':'۱۴۰۵/۱','MTG_MeetingTitle':'جلسه تست','MTG_SecretaryUserUID':owner,
            'MTG_MeetingStartDateTime':'۱۴۰۵/۰۶/۳۱','MTG_MeetingStartTime':'09:00',
            'MTG_Actions':{1:{'MTG_ActionNo':'A-1','MTG_ActionDescription':'پیگیری','MTG_ActionOwnerUID':owner,
                                 'MTG_persiandate_ActionDueDateTime':'۱۴۰۵/۰۷/۰۱','MTG_ActionPriority':'High'}}}

def scope(uid=OWNER):return {'role':'Expert','visible_uids':{uid},'directory':{uid:{'name':'کاربر'}},'staff':{uid:{'department_name':'فنی'}}}

def test_serialized_arrays_persian_and_object_rejection():
    assert store.decode_case(raw(meeting()))['MTG_MeetingTitle']=='جلسه تست'
    with pytest.raises(store.ProductionUnavailable):store.decode_case(b'O:8:"stdClass":0:{}')
    with pytest.raises(store.ProductionUnavailable):store.decode_case(b'bad data')
    with pytest.raises(store.ProductionUnavailable):store.decode_case(b'x'*(store.MAX_CASE_BYTES+1))


def test_grid_bases_and_jalali_deadline():
    assert store.cell({0:'decision',1:'A-1'},'MTG_ActionNo',1)=='A-1'
    assert store.cell({1:'decision',2:'A-1'},'MTG_ActionNo',1)=='A-1'
    assert store.iso('۱۴۰۵/۰۱/۰۱',end_day=True)=='2026-03-21T23:59:59+03:30'
    assert store.iso('۱۴۰۵/۱۳/۰۱') is None


def test_candidate_false_positive_never_reaches_output():
    data=meeting(OTHER);data['irrelevant_note']=OWNER
    with patch.object(store,'query',return_value=[(PARENT,7,'TO_DO',raw(data))]):
        page=store.authorized_meetings_page(None,scope())
    assert page['meetings']==[] and not page['has_more']


def test_native_snapshot_counts_closed_only_for_current_review():
    child={'MTGA_ParentCaseUID':PARENT,'MTGA_ActionNo':'A-1','MTGA_OwnerUserUID':OWNER,
           'MTGA_ProgressPercent':'100','MTGA_LastSubmittedAt':'2026-09-22 10:00:00',
           'MTGA_LastReviewedAt':'2026-09-21 10:00:00','MTGA_ReviewStatus':'Closed',
           'MTGA_SecretaryProgressPercent':'90','MTGA_SubmissionHistoryJson':'[]'}
    calls=[]
    def query(c,sql,args):
        calls.append((sql,args));return [(PARENT,7,'TO_DO',raw(meeting()))] if args[0]==store.MEETING_PROCESS else [('c'*32,8,'TO_DO',raw(child))]
    with patch.object(store,'query',side_effect=query):rows,complete=store.authorized_meeting_snapshot(None,scope())
    action=rows[0]['actions'][0]
    assert complete and action['status']=='AwaitingReview' and not action['is_closed'] and action['progress_percent']==100
    assert action['owner_unit']=='فنی' and action['due_at_utc'].startswith('2026-09-23T23:59:59')
    assert all(sql.startswith('SELECT') for sql,_ in calls)
    assert any(OWNER in str(args) for _,args in calls)
    child['MTGA_LastReviewedAt']='2026-09-22 10:01:00'
    with patch.object(store,'query',side_effect=query):rows,_=store.authorized_meeting_snapshot(None,scope())
    assert rows[0]['actions'][0]['is_closed'] and rows[0]['actions'][0]['progress_percent']==90


def test_wrong_parent_child_does_not_supply_data():
    child={'MTGA_ParentCaseUID':'e'*32,'MTGA_ActionNo':'A-1','MTGA_ActionDescription':'SECRET'}
    with patch.object(store,'query',side_effect=[[(PARENT,7,'TO_DO',raw(meeting()))],[('c'*32,8,'TO_DO',raw(child))]]):
        rows,_=store.authorized_meeting_snapshot(None,scope())
    assert rows[0]['actions'][0]['description']=='پیگیری'


def test_duplicate_children_fail_instead_of_double_count():
    child=raw({'MTGA_ParentCaseUID':PARENT,'MTGA_ActionNo':'A-1'})
    with patch.object(store,'query',side_effect=[[(PARENT,7,'TO_DO',raw(meeting()))],[('c'*32,8,'TO_DO',child),('d'*32,9,'TO_DO',child)]]):
        with pytest.raises(store.ProductionUnavailable):store.authorized_meeting_snapshot(None,scope())


def test_pagination_marks_incomplete_snapshot():
    rows=[(PARENT,i,'TO_DO',raw(meeting())) for i in range(3,0,-1)]
    with patch.object(store,'query',return_value=rows):page=store.authorized_meetings_page(None,scope(),limit=1)
    assert page['has_more'] and page['next_cursor']==3 and len(page['meetings'])==1


def test_verified_role_and_active_pm_account_required():
    tid='11111111-1111-1111-1111-111111111111'
    p=Principal(subject='subject',tenant_id=UUID(tid),roles=frozenset({'Expert'}))
    data={'tenant_id':tid,'company_name':'شرکت','users':[{'subject':'subject','pm_uid':OWNER,'role':'Expert','enabled':True,'pm_active':True}]}
    with patch.object(native_access,'read',return_value=data),patch.object(store,'directory',return_value={OWNER:{'active':False}}):
        with pytest.raises(store.EmployeeMappingRequired):store.verified_scope(None,p)
    data['users'][0]['role']='SysAdmin'
    with patch.object(native_access,'read',return_value=data),patch.object(store,'directory',return_value={OWNER:{'active':True}}):
        with pytest.raises(store.ProductionAccessDenied):store.verified_scope(None,p)


def test_sql_server_admin_routes_are_removed():
    from commercial.setup_routes import router
    assert not any('/sql/' in r.path for r in router.routes)
    assert any(r.path.endswith('/mysql/save') for r in router.routes)

def test_review_version_beats_equal_second_timestamp():
    import json
    child={'MTGA_ParentCaseUID':PARENT,'MTGA_ActionNo':'A-1','MTGA_ReviewStatus':'Closed',
           'MTGA_LastSubmittedAt':'2026-09-22 10:00:00','MTGA_LastReviewedAt':'2026-09-22 10:00:00',
           'MTGA_SubmissionHistoryJson':json.dumps([{'submissionVersion':2,'submittedAt':'2026-09-22 10:00:00','progressPercent':70}]),
           'MTGA_ReviewHistoryJson':json.dumps([{'submissionVersion':1,'reviewedAt':'2026-09-22 10:00:00','reviewStatus':'Closed','progressPercent':100}])}
    def run():
        with patch.object(store,'query',side_effect=[[(PARENT,7,'TO_DO',raw(meeting()))],[('c'*32,8,'TO_DO',raw(child))]]):
            return store.authorized_meeting_snapshot(None,scope())[0][0]['actions'][0]
    assert not run()['is_closed'] and run()['progress_percent']==70
    review=json.loads(child['MTGA_ReviewHistoryJson']);review[0]['submissionVersion']=2
    child['MTGA_ReviewHistoryJson']=json.dumps(review)
    assert run()['is_closed'] and run()['progress_percent']==100
