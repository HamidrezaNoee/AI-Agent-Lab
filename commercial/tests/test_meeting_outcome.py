from unittest.mock import patch
from types import SimpleNamespace
import pytest
from fastapi import HTTPException

from commercial.processmaker_store import _meeting
from commercial.agent_tools import MeetingTools, MeetingQuery
from commercial.setup_routes import PMConfig, _pm_check


def record(data):
    with patch('commercial.processmaker_store.iso', return_value=None):
        return _meeting(('case', 1, 'COMPLETED'), data)


def test_completed_workflow_does_not_imply_held_or_absent():
    m = record({'MTG_Participants': {1: {'MTG_ParticipantUserUID': 'user'}}})
    assert m['meeting_held'] is None
    assert m['attendance'][0]['status'] is None
    assert m['attendance'][0]['arrival_time_local'] is None


def test_meeting_date_uses_field_exported_by_latest_minutes_process():
    m = _meeting(('case', 1, 'TO_DO'), {
        'MTG_persiandate_MeetingStartDateTime': '1405/07/04',
        'MTG_MeetingStartTime': '09:15',
    })
    assert m['meeting_date_utc'].startswith('2026-09-26T09:15:00+03:30')


def test_not_held_suppresses_stale_attendance_and_exposes_reason():
    m = record({'MTG_MeetingHeld': 'NotHeld', 'MTG_NotHeldReason': 'نبود حد نصاب',
                'MTG_Participants': {1: {'MTG_ParticipantUserUID': 'user',
                  'MTG_AttendanceStatus': 'Present', 'MTG_AttendanceTime': '09:00'}}})
    assert m['not_held_reason'] == 'نبود حد نصاب'
    assert m['attendance'][0]['status'] is None
    tools = MeetingTools([m])
    assert tools.search(MeetingQuery(meeting_held='Held'))['total'] == 0
    r = tools.search(MeetingQuery(meeting_held='NotHeld', text='حد نصاب'))
    assert r['total'] == 1 and r['rows'][0]['meeting_held'] == 'NotHeld'


def test_attendance_normalizes_persian_time_and_rejects_bad_time():
    m = record({'MTG_MeetingHeld': 'Held', 'MTG_Participants': {
        1: {1:'u1', 2:'', 3:'', 4:'', 5:'Present', 6:'۰۹:۳۵'},
        2: {0:'u2', 1:'', 2:'', 3:'', 4:'Present', 5:'29:99'},
        3: {'MTG_ParticipantUserUID':'u3', 'MTG_AttendanceStatus':'Absent', 'MTG_AttendanceTime':'10:00'},
    }})
    assert [r['arrival_time_local'] for r in m['attendance']] == ['09:35', None, None]
    assert [r['participant_uid'] for r in m['attendance']] == ['u1','u2','u3']


def test_attendance_and_reason_are_bounded_and_unknown_filter_works():
    m = record({'MTG_MeetingHeld':'NotHeld','MTG_NotHeldReason':'a'*1001})
    m['attendance'] = [{'participant_uid':str(i)} for i in range(101)]
    unknown = record({})
    tools = MeetingTools([m,unknown])
    row = tools.search(MeetingQuery(meeting_held='NotHeld'))['rows'][0]
    assert len(row['attendance']) == 100 and row['attendance_truncated']
    assert len(row['not_held_reason']) == 1000 and row['text_truncated']
    assert tools.search(MeetingQuery(meeting_held='unknown'))['total'] == 1


def test_local_processmaker_api_uses_actual_host_port_only_in_lab(monkeypatch):
    monkeypatch.setenv('AVAN_PM_ALLOW_LOCAL_HTTP','1')
    called=[]
    class HTTP:
        def __init__(self, **kwargs): pass
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def get(self,url,**kwargs):
            called.append(url)
            return SimpleNamespace(status_code=200,content=b'[]',json=lambda:[])
    with patch('commercial.setup_routes.httpx.Client',HTTP):
        assert _pm_check(PMConfig(base_url='http://host.docker.internal:443',workspace='workflow',bearer_token='token-123456')) == 200
    assert called==['http://host.docker.internal:443/api/1.0/workflow/users']
    with pytest.raises(HTTPException):
        _pm_check(PMConfig(base_url='http://example.test:443',workspace='workflow',bearer_token='token-123456'))
    monkeypatch.delenv('AVAN_PM_ALLOW_LOCAL_HTTP')
    with pytest.raises(HTTPException):
        _pm_check(PMConfig(base_url='http://host.docker.internal:443',workspace='workflow',bearer_token='token-123456'))
