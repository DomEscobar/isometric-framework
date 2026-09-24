"""Isolated recovery contracts; synthetic art/reviewer fixtures, no provider calls."""
import json
import pytest
from artifacts import canonical, digest
from test_continuation_readiness import fixture


def configured(tmp_path, monkeypatch, unknown=True):
    import auto_adapter
    c, parent, evaluation = fixture(tmp_path, translation=[.1,.1])
    doc=tmp_path/'QUALITY_RECOVERY_AUTHORIZATION.md'
    doc.write_text('MOCK explicit bounded recovery authorization; not a live spending grant')
    monkeypatch.setattr(auto_adapter,'QUALITY_AUTHORIZATION',doc,raising=False)
    policy=dict(enabled=True,authorization_sha256=digest(doc.read_bytes()),parent_run_id=parent['id'])
    (tmp_path/'quality-recovery-policy.json').write_bytes(canonical(policy))
    s=c.app.state.auto_repair
    if unknown:
        s.g.policy['approved']=True
        s.g.reserve_review('paid-pilot-01',100,{'retained':'unknown old hold'})
        s.g.policy['approved']=False
    return c,s,parent,evaluation


def test_free_registration_recovery_new_identity_no_paid_unknown_hold(tmp_path,monkeypatch):
    c,s,parent,e=configured(tmp_path,monkeypatch)
    before=canonical(s.get(parent['id']));budget=s.g.status()
    r=c.post('/api/auto-repair/'+parent['id']+'/recover-seed',json={'confirm_paid':True})
    assert r.status_code==201,r.text
    child=r.json();assert child['id']!=parent['id']
    # Disable asynchronous timing in the test by waiting on the existing worker.
    s.workers[child['id']].join(10)
    child=s.get(child['id'])
    assert child['status']=='awaiting_prerequisite',child
    assert child['phase']=='review'
    assert child['latest_candidate_id']!=parent['best_candidate_id']
    assert child['inherited_iterations']==1 and len(child['iterations'])==1
    assert child['iterations'][0]['number']==2
    assert child['iterations'][0]['registration']['candidate_id']==child['latest_candidate_id']
    assert any('paid-pilot-01' in b for b in child['prerequisite_blockers'])
    assert canonical(s.get(parent['id']))==before and s.g.status()==budget
    assert not (tmp_path/'evaluations'/child['prepared_evaluation_id']/'attempt.lock').exists()
    assert c.post('/api/auto-repair/'+parent['id']+'/recover-seed',json={'confirm_paid':True}).json()['id']==child['id']
    assert c.post('/api/auto-repair/'+child['id']+'/recover-seed/resume',json={'confirm_paid':True}).json()['status']=='awaiting_prerequisite'
    assert canonical(s.get(parent['id']))==before and s.g.status()==budget


@pytest.mark.parametrize('bad',['missing_policy','disabled','hash_drift','parent_drift','arbitrary_ui_hash','false_confirmation'])
def test_recovery_requires_trusted_doc_bound_authority(tmp_path,monkeypatch,bad):
    c,s,parent,e=configured(tmp_path,monkeypatch)
    p=tmp_path/'quality-recovery-policy.json';policy=json.loads(p.read_bytes())
    body={'confirm_paid':True}
    if bad=='missing_policy':p.unlink()
    elif bad=='disabled':policy['enabled']=False
    elif bad=='hash_drift':policy['authorization_sha256']='f'*64
    elif bad=='parent_drift':policy['parent_run_id']='f'*64
    elif bad=='arbitrary_ui_hash':body['authorization_sha256']='f'*64
    else:body['confirm_paid']=False
    if bad!='missing_policy':p.write_bytes(canonical(policy))
    before=canonical(s.get(parent['id']));budget=s.g.status()
    r=c.post('/api/auto-repair/'+parent['id']+'/recover-seed',json=body)
    assert r.status_code in (409,422),r.text
    assert canonical(s.get(parent['id']))==before and s.g.status()==budget
    with s.g.connect() as db:assert db.execute('SELECT count(*) FROM auto_runs').fetchone()[0]==1


def test_waiting_recovery_can_be_cancelled_without_touching_parent(tmp_path,monkeypatch):
    c,s,parent,e=configured(tmp_path,monkeypatch)
    child=s.recover_seed(parent['id']);s.tick(child['id']);s.tick(child['id'])
    before=canonical(s.get(parent['id']))
    cancelled=s.cancel(child['id'])
    assert cancelled['status']=='cancelled' and cancelled['cancel_requested']
    assert s.resume_quality(child['id'])['status']=='cancelled'
    assert canonical(s.get(parent['id']))==before


def test_pending_seed_review_runs_once_then_proves_new_bound_seed(tmp_path,monkeypatch):
    from test_strict_review import mock_decision
    c,s,parent,e=configured(tmp_path,monkeypatch,unknown=False)
    child=s.recover_seed(parent['id']);s.tick(child['id']);waiting=s.tick(child['id'])
    assert waiting['status']=='awaiting_prerequisite'
    s.g.policy={'approved':True,'total_usd':'10','max_attempts':17}
    reviewer=c.app.state.reviewer;reviewer.config.enabled=True
    meta={'id':'mock/vision','architecture':{'input_modalities':['text','image'],'output_modalities':['text']},'supported_parameters':['response_format','temperature','max_tokens'],'pricing':{'prompt':'0.000001','completion':'0.000001'},'context_length':10000}
    monkeypatch.setattr(reviewer,'preflight',lambda:meta)
    monkeypatch.setattr(s.g.provider,'discover',lambda:{})
    calls=[]
    def post(body):
        calls.append(body)
        return dict(model=meta['id'],choices=[dict(finish_reason='stop',message={'content':json.dumps(mock_decision())})])
    monkeypatch.setattr(reviewer,'post',post)
    s.resume_quality(child['id']);reviewed=s.tick(child['id']);result=s.tick(child['id'])
    assert len(calls)==1
    assert result['status']=='succeeded',result
    assert result['iterations'][0]['seed_proof']['eligible'] is True
    assert result['evaluation_id']!=e['id']
    assert s.resume_quality(child['id'])==result
    assert len(calls)==1


def test_resume_serializes_with_worker_lock(tmp_path,monkeypatch):
    import fcntl
    import threading
    from concurrent.futures import ThreadPoolExecutor
    c,s,parent,e=configured(tmp_path,monkeypatch)
    child=s.recover_seed(parent['id']);s.tick(child['id']);s.tick(child['id'])
    entered=threading.Event();original=s.adapter.recovery_prerequisites
    monkeypatch.setattr(s.adapter,'validate',lambda w:None)  # isolate lock, not expensive image replay
    def probe(w,a):entered.set();return original(w,a)
    monkeypatch.setattr(s.adapter,'recovery_prerequisites',probe)
    with (tmp_path/('auto-'+child['id']+'.lock')).open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        with ThreadPoolExecutor(1) as pool:
            task=pool.submit(s.resume_quality,child['id'])
            try:assert not entered.wait(.2),'resume entered while worker holds process lock'
            finally:fcntl.flock(lock,fcntl.LOCK_UN)
            assert task.result()['status']=='awaiting_prerequisite'


def test_quality_paid_boundary_rechecks_unknown_liabilities(tmp_path,monkeypatch):
    c,s,parent,e=configured(tmp_path,monkeypatch)
    child=s.recover_seed(parent['id'])
    with pytest.raises(ValueError,match='liabilit'):
        s.adapter.prepare(child,child['iterations'][0])
    with pytest.raises(ValueError,match='liabilit'):
        s.adapter.submit(child,child['iterations'][0])
