"""Reject configurations whose role forms cannot map to the native process."""
import copy
import pytest
from commercial import secretary_catalog as c
from commercial.tests.test_secretary_inbox import pack, store

def compile_parts(monkeypatch, meeting, action):
    monkeypatch.setattr(c, 'parse_pmx', lambda value: copy.deepcopy({'meeting': meeting, 'action': action}[value]))
    return c.compile_pack('meeting', 'action')

def test_correct_role_processes_compile(pack, monkeypatch):
    result = compile_parts(monkeypatch, pack['meeting'], pack['action'])
    assert set(result['stages']) == set(c.STAGES)

def test_swapped_process_files_rejected(pack, monkeypatch):
    with pytest.raises(ValueError, match='PMX'):
        compile_parts(monkeypatch, pack['action'], pack['meeting'])

def test_stage_in_wrong_process_rejected(pack, monkeypatch):
    meeting, action = copy.deepcopy(pack['meeting']), copy.deepcopy(pack['action'])
    action['stages']['minutes_approval'] = meeting['stages'].pop('minutes_approval')
    with pytest.raises(ValueError, match='PMX'):
        compile_parts(monkeypatch, meeting, action)

def test_ambiguous_task_roles_rejected(pack, monkeypatch):
    meeting = copy.deepcopy(pack['meeting'])
    meeting['stages']['minutes_approval']['task_uid'] = meeting['stages']['invitation']['task_uid']
    with pytest.raises(ValueError, match='وظیفه مستقل'):
        compile_parts(monkeypatch, meeting, pack['action'])

def test_upgrade_existing_readonly_meeting_keeps_id_and_revision(pack, store):
    store[c.STORE] = []
    native = c.save('source', {'adapter': 'native_tasks_v1', 'process': {
        'process_uid': pack['meeting']['process_uid'], 'title': 'جلسه'}}, 'admin')
    upgraded = c.save('source', pack, 'admin', identifier=native['id'], revision=native['revision'])
    assert upgraded['id'] == native['id'] and upgraded['revision'] == 2
    assert upgraded['adapter'] == 'meeting_v2' and 'review_action' in upgraded['tools']
    assert len(store[c.STORE]) == 1
    with pytest.raises(ValueError):
        c.save('source', pack, 'admin', identifier=native['id'], revision=native['revision'])

def test_upgrade_does_not_replace_unrelated_process(pack, store):
    store[c.STORE] = []
    native = c.save('source', {'adapter': 'native_tasks_v1', 'process': {
        'process_uid': 'f'*32, 'title': 'خرید'}}, 'admin')
    with pytest.raises(ValueError, match='همان فرایند'):
        c.save('source', pack, 'admin', identifier=native['id'], revision=native['revision'])
    assert store[c.STORE] == [native]


def test_reviewed_pair_merges_both_readonly_inboxes_atomically(pack,store,monkeypatch):
    monkeypatch.setattr(c,'verify_installed',lambda source,p:None)
    store[c.STORE]=[]
    a=c.save('source',{'adapter':'native_tasks_v1','process':pack['meeting']},'admin')
    b=c.save('source',{'adapter':'native_tasks_v1','process':pack['action']},'admin')
    row=c.install_reviewed('source','admin',{a['id']:a['revision'],b['id']:b['revision']})
    assert row['id']==a['id'] and row['revision']==2 and len(store[c.STORE])==1
    assert set(row['stages'])==set(c.STAGES)
    with pytest.raises(ValueError,match='تغییر'):
        c.install_reviewed('source','admin',{})
    assert store[c.STORE]==[row]


def test_reviewed_pair_requires_installed_verification_before_save(pack,store,monkeypatch):
    before=copy.deepcopy(store)
    def unavailable(*args):raise ValueError('PMX mismatch')
    monkeypatch.setattr(c,'verify_installed',unavailable)
    with pytest.raises(ValueError,match='PMX mismatch'):
        c.install_reviewed('source','admin',{})
    assert store==before


@pytest.mark.parametrize('change',['fields','after','before','form_uid'])
def test_installed_contract_drift_is_rejected(pack,monkeypatch,change):
    from contextlib import contextmanager
    from commercial import processmaker_store,user_bpms_bindings
    @contextmanager
    def opened(config):yield object()
    monkeypatch.setattr(user_bpms_bindings,'processmaker_profile',lambda source:{'mysql':{}})
    monkeypatch.setattr(processmaker_store,'open_production',opened)
    altered=copy.deepcopy(pack['meeting'])
    stage=altered['stages']['minutes']
    if change=='fields':stage['fields']['MTG_MeetingHeld']['type']='text'
    elif change=='form_uid':stage['form_uid']='f'*32
    elif change=='before':stage['before']=list(reversed(stage['before']))
    else:stage['after'].append('f'*32)
    monkeypatch.setattr(c,'_installed_process',lambda con,uid:altered if uid==pack['meeting']['process_uid'] else pack['action'])
    with pytest.raises(ValueError,match='یکسان'):
        c.verify_installed('source',pack)
