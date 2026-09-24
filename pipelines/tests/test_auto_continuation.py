"""Transport-free continuation tests; no live authorization or paid calls."""
import pytest
from concurrent.futures import ThreadPoolExecutor
from artifacts import canonical, digest
from auto_repair import AutoRepair
from test_auto_engine import service, drain


def stopped(tmp_path):
    s, a, rid = service(tmp_path)
    a.register = lambda w, attempt: {'blocker': 'registration_ambiguous: MOCK unsafe'}
    w = drain(s, rid)
    a.continuation_seed = lambda parent: dict(
        candidate_id=parent['best_candidate_id'], evaluation_id=parent['best_evaluation_id'],
        frozen_sha256=digest(canonical(parent['frozen'])), registered=True,
        reviewed=True, valid=True, no_unknown_liabilities=True)
    return s, a, w


def authorization(w):
    return dict(authorization_sha256=digest(('new explicit authority '+w['id']).encode()),
                parent_run_id=w['id'], reason='Explicitly select retained reviewed best; unsafe latest retained',
                candidate_id=w['best_candidate_id'], evaluation_id=w['best_evaluation_id'])


def row(s, rid):
    with s.g.connect() as db:
        return tuple(db.execute('SELECT * FROM auto_runs WHERE id=?', (rid,)).fetchone())


def test_explicit_continuation_deduplicates_without_spend_or_mutation(tmp_path):
    s, a, w = stopped(tmp_path)
    original = row(s, w['id']); submits = a.submits
    with ThreadPoolExecutor(4) as pool:
        children = list(pool.map(lambda _: AutoRepair(s.g,a).continue_run(w['id'], authorization(w), 15), range(8)))
    child = children[0]
    assert len({c['id'] for c in children}) == 1
    assert row(s,w['id']) == original and a.submits == submits
    assert child['frozen'] == w['frozen'] and child['iterations'] == []
    assert child['inherited_iterations'] == 1
    assert child['latest_candidate_id'] == w['best_candidate_id']
    assert child['continuation']['previous_latest_candidate_id'] == w['latest_candidate_id']
    assert child['continuation']['parent_run_id'] == w['id']
    assert child['continuation']['authorization'] == authorization(w)
    assert s.resume(w['id']) == w


def test_lifetime_cap_across_successors(tmp_path):
    s, a, parent = stopped(tmp_path)
    # Distinct evidence-driven mock plans; no identity-only reroll.
    a.plan = lambda w: dict(action='generate', findings=['material'],
                            prompt='MOCK change '+str(w['inherited_iterations']))
    for limit in (2, 3):
        original = row(s,parent['id'])
        child = s.continue_run(parent['id'], authorization(parent), limit)
        parent = drain(s,child['id'])
        assert len(parent['iterations']) == 1
        assert parent['iterations'][0]['number'] == limit
        assert parent['inherited_iterations'] + len(parent['iterations']) == limit
        assert row(s,parent['continuation']['parent_run_id']) == original
        with pytest.raises(ValueError,match='limit'):
            s.continue_run(parent['id'],authorization(parent),limit)
    with pytest.raises(ValueError):s.continue_run(parent['id'],authorization(parent),16)


def test_signature_blocks_metadata_disguised_rerolls(tmp_path):
    s, a, rid = service(tmp_path)
    a.plan = lambda w: dict(action='generate',correction_signature='same correction',candidate=w['latest_candidate_id'])
    result = drain(s,rid)
    assert result['stop_reason'] == 'identical_correction_plan'
    assert a.submits == 1


@pytest.mark.parametrize('semantic', [False, True])
def test_unsigned_history_blocks_same_signed_correction(tmp_path, semantic):
    s, a, parent = stopped(tmp_path)
    if semantic:
        parent['iterations'][0]['plan'] = dict(
            action='generate', findings=[dict(criterion='materials', observation='wrong paving',
                                            correction='restore paving', blocking=True)],
            prompt='old prompt and evidence', source_candidate_id='old')
        parent = s.save(parent)
    original = parent['iterations'][0]['plan']
    signature = (digest(canonical(sorted((f['criterion'], f['observation'], f['correction'])
                                        for f in original['findings'])))
                 if semantic else digest(canonical(original)))
    proposed = {**original, 'correction_signature': signature}
    if semantic:
        proposed.update(prompt='new prompt and evidence', source_candidate_id='new')
        proposed['findings'] = [{**f, 'evidence_ids': ['final']} for f in original['findings']]
    a.plan = lambda w: proposed
    before = row(s, parent['id'])
    child = s.continue_run(parent['id'], authorization(parent), 15)
    final = drain(s, child['id'])
    assert final['stop_reason'] == 'identical_correction_plan'
    assert a.submits == 1
    assert row(s, parent['id']) == before


@pytest.mark.parametrize('historical', [
    {'action': 'generate', 'prompt': 'old real prompt'},
    {'action': 'generate', 'findings': []},
    {'action': 'generate', 'findings': [{'criterion': 'materials', 'observation': 'wrong'}]},
    {'action': 'generate', 'findings': ['material'], 'prompt': 'not a MOCK plan'},
])
def test_unreconstructable_unsigned_history_fails_closed(tmp_path, historical):
    s, a, parent = stopped(tmp_path)
    parent['iterations'][0]['plan'] = historical
    parent = s.save(parent)
    a.plan = lambda w: dict(action='generate', findings=[dict(
        criterion='materials', observation='new defect', correction='repair defect')])
    before = row(s, parent['id'])
    child = s.continue_run(parent['id'], authorization(parent), 15)
    final = drain(s, child['id'])
    assert final['stop_reason'] == 'correction semantics unavailable; no safe duplicate comparison'
    assert a.submits == 1 and row(s, parent['id']) == before


def test_mock_prompt_fallback_cannot_apply_to_real_authorized_contract(tmp_path):
    s, a, parent = stopped(tmp_path)
    contract = {**parent, 'frozen': {**parent['frozen'], 'authorization_sha256': 'a'*64}}
    with pytest.raises(ValueError, match='correction semantics unavailable'):
        s.correction_signature(contract, parent['iterations'][0]['plan'])


@pytest.mark.parametrize('field', ['criterion', 'observation', 'correction'])
def test_reconstructed_semantics_allow_genuinely_different_findings(tmp_path, field):
    s, a, parent = stopped(tmp_path)
    finding = dict(criterion='materials', observation='wrong paving', correction='restore paving')
    parent['iterations'][0]['plan'] = dict(action='generate', findings=[finding], prompt='old')
    parent = s.save(parent)
    changed = {**finding, field: 'different semantic value'}
    a.plan = lambda w: dict(action='generate', findings=[changed], correction_signature=digest(
        canonical([(changed['criterion'], changed['observation'], changed['correction'])])))
    child = s.continue_run(parent['id'], authorization(parent), 15)
    assert s.tick(child['id'])['phase'] == 'prepare'
    assert s.tick(child['id'])['phase'] == 'submit'
    assert s.tick(child['id'])['phase'] == 'poll'
    assert a.submits == 2


def test_signature_survives_continuation(tmp_path):
    s, a, w = stopped(tmp_path)
    old = s.get(w['id'])
    old['iterations'][0]['plan']['correction_signature'] = 'unchanged'
    s.save(old)
    a.plan = lambda w: dict(action='generate',correction_signature='unchanged',candidate=w['id'])
    child = s.continue_run(w['id'],authorization(w),15)
    assert drain(s,child['id'])['stop_reason'] == 'identical_correction_plan'
    assert a.submits == 1


@pytest.mark.parametrize('status,phase,reason', [
    ('running','plan',None), ('cancelled','register','cancelled'),
    ('succeeded','assess','all_strict_criteria_pass'),
    ('needs_attention','submitting','unknown_submission'),
    ('needs_attention','review','review_unknown_submission'),
    ('needs_attention','poll','poll_limit; known prediction retained'),
    ('needs_attention','assess','invalid_review; no citation repair or retry'),
])
def test_ineligible_stops_never_continue(tmp_path,status,phase,reason):
    s,a,w=stopped(tmp_path)
    w.update(status=status,phase=phase,stop_reason=reason);w=s.save(w)
    before=row(s,w['id']);posts=a.submits
    with pytest.raises(ValueError):s.continue_run(w['id'],authorization(w),15)
    assert row(s,w['id'])==before and a.submits==posts


@pytest.mark.parametrize('bad', ['missing_hook','unsafe','wrong_evaluation','unknown_liability','missing_auth','wrong_seed','cancel_requested'])
def test_seed_and_authorization_are_fail_closed(tmp_path,bad):
    s,a,w=stopped(tmp_path);auth=authorization(w)
    if bad=='missing_hook':a.continuation_seed=None
    elif bad in ('unsafe','wrong_evaluation','unknown_liability'):
        proof=a.continuation_seed(w)
        proof[{'unsafe':'registered','wrong_evaluation':'evaluation_id','unknown_liability':'no_unknown_liabilities'}[bad]]=False
        a.continuation_seed=lambda w:proof
    elif bad=='missing_auth':auth={}
    elif bad=='wrong_seed':auth['candidate_id']=w['latest_candidate_id']
    else:w['cancel_requested']=True;w=s.save(w)
    before=row(s,w['id']);posts=a.submits
    with pytest.raises(ValueError):s.continue_run(w['id'],auth,15)
    assert row(s,w['id'])==before and a.submits==posts


@pytest.mark.parametrize('cancel_child', [False, True])
def test_terminal_parent_cancel_after_child_plan_is_immutable(tmp_path, cancel_child):
    s, a, parent = stopped(tmp_path)
    a.plan = lambda w: dict(action='generate', correction_signature='new correction')
    before = row(s, parent['id'])
    child = s.continue_run(parent['id'], authorization(parent), 15)
    assert s.tick(child['id'])['phase'] == 'prepare'
    child_before = row(s, child['id'])
    assert s.cancel(parent['id']) == parent
    assert row(s, parent['id']) == before
    assert row(s, child['id']) == child_before
    if cancel_child:
        s.cancel(child['id'])
        final = drain(s, child['id'])
        assert final['status'] == 'cancelled' and a.submits == 1
    else:
        assert s.tick(child['id'])['phase'] == 'submit'
        assert s.tick(child['id'])['phase'] == 'poll'
        assert a.submits == 2
    assert row(s, parent['id']) == before


@pytest.mark.parametrize('phase', ['prepare', 'submit', 'submitting', 'poll', 'register', 'review'])
def test_lineage_drift_stops_every_tick_before_adapter_work(tmp_path, phase):
    s, a, parent = stopped(tmp_path)
    a.plan = lambda w: dict(action='generate', correction_signature='new correction')
    child = s.continue_run(parent['id'], authorization(parent), 15)
    child = s.tick(child['id'])
    child['phase'] = phase
    s.save(child)
    # Simulate external historical evidence drift after planning, not cancellation.
    parent['events'].append(dict(reason='MOCK evidence drift'))
    s.save(parent)
    calls = []
    for name in ('prepare', 'submit', 'recover', 'poll', 'register', 'review'):
        def forbidden(*args, name=name):
            calls.append(name)
            raise AssertionError('adapter work after lineage drift')
        setattr(a, name, forbidden)
    final = s.tick(child['id'])
    assert final['status'] == 'needs_attention'
    assert final['stop_reason'] == 'continuation parent evidence drift'
    assert calls == [] and a.submits == 1


def test_conflicting_authorizations_cannot_fork(tmp_path):
    s,a,w=stopped(tmp_path)
    def attempt(i):
        auth=authorization(w);auth['reason']+=str(i)
        try:return s.continue_run(w['id'],auth,15)['id']
        except ValueError:return None
    with ThreadPoolExecutor(4) as pool:results=list(pool.map(attempt,range(8)))
    assert sum(x is not None for x in results)==1
    from auto_repair import Start
    assert s.start(Start(evaluation_id='a'*64,confirm_paid=True))['id']==w['id']
    with pytest.raises(ValueError):s.start(Start(evaluation_id='f'*64,confirm_paid=True))


def test_hard_fifteen_cap_includes_prior_generations(tmp_path):
    s,a,w=stopped(tmp_path)
    from test_auto_engine import Adapter
    a.register=Adapter().register
    a.plan=lambda w:dict(action='generate',correction_signature='new'+str(w.get('inherited_iterations',0)+len(w['iterations'])))
    child=s.continue_run(w['id'],authorization(w),15)
    final=drain(s,child['id'])
    assert final['stop_reason']=='iteration_limit'
    assert len(final['iterations'])==14 and a.submits==15
    assert final['iterations'][-1]['number']==15
    with pytest.raises(ValueError,match='limit'):s.continue_run(final['id'],authorization(final),15)


def test_stagnation_does_not_reset_at_generation_boundary(tmp_path):
    s,a,w=stopped(tmp_path)
    from test_auto_engine import Adapter
    a.register=Adapter().register
    a.plan=lambda w:dict(action='generate',correction_signature=str(w.get('inherited_iterations',0)+len(w['iterations'])))
    a.review=lambda w,x:dict(id='review'+str(x['number']),approved=False,valid=True,score=[0]*4,source_sha256=x['candidate_id'],blockers=['mock fail'])
    first=s.continue_run(w['id'],authorization(w),2)
    first=drain(s,first['id'])
    assert first['stop_reason']=='iteration_limit'
    second=s.continue_run(first['id'],authorization(first),15)
    second=drain(s,second['id'])
    assert second['stop_reason'].startswith('stagnation')
    assert len(second['iterations'])==1
