import time
import pytest
from artifacts import canonical,digest
from test_hybrid_calls import setup


def fixture(tmp_path):
    s=setup(tmp_path)
    cfg=dict(mode='live',budget_microusd=500,max_calls=5,max_images=1)
    old=s.create('old',cfg);c=s.claim()
    auth=dict(config_sha256=digest(canonical(cfg)),budget_microusd=500,max_calls=5,max_images=1,expires=time.time()+600)
    call=s.reserve_call(c,'planner',{'old':True},80,auth)
    s.save(c,phase='needs_attention');s.release(c)
    new=s.create('new',cfg);c=s.claim()
    with s.g.connect() as db:
        snapshot=dict(db.execute('SELECT * FROM hybrid_calls WHERE id=?',(call['id'],)).fetchone())
        ledger=dict(db.execute('SELECT * FROM reviews WHERE id=?',(call['id'],)).fetchone())
    scope=dict(run_id=new['id'],config_sha256=digest(canonical(cfg)),approval_text='weiter? ja was stehst du hier rum? One NEW run, keep all unresolved holds.',project_cap_microusd=10_000_000,budget_microusd=500,max_calls=5,max_images=1,expires=auth['expires'],liabilities=[dict(call_id=call['id'],request_sha256=digest(canonical({'old':True})),amount=80)])
    return s,c,auth,scope,snapshot,ledger


def test_scoped_new_attempt_retains_old_rows(tmp_path):
    s,c,a,scope,old,ledger=fixture(tmp_path)
    with pytest.raises(ValueError):s.reserve_call(c,'planner',{'new':True},80,a)
    assert hasattr(s,'acknowledge_liabilities'), 'missing immutable scoped liability authorization'
    aid=s.acknowledge_liabilities(scope)
    a['liability_authorization']=aid
    assert s.reserve_call(c,'planner',{'new':True},80,a)['new']
    with s.g.connect() as db:
        assert dict(db.execute('SELECT * FROM hybrid_calls WHERE id=?',(old['id'],)).fetchone())==old
        assert dict(db.execute('SELECT * FROM reviews WHERE id=?',(old['id'],)).fetchone())==ledger
    with pytest.raises(ValueError):s.reserve_call(c,'review',{'new':2},80,a)


def test_ack_budget_cannot_exceed_remaining_headroom(tmp_path):
    s,c,a,scope,old,ledger=fixture(tmp_path)
    scope['project_cap_microusd']=550
    with pytest.raises(ValueError,match='Headroom'):s.acknowledge_liabilities(scope)


@pytest.mark.parametrize('change',['cross_run','expiry','config','old_request','old_hold','unrelated_unknown','limit_reset','cancel','fence','replay'])
def test_bound_ack_rejects_drift_and_reuse(tmp_path,change):
    s,c,a,scope,old,ledger=fixture(tmp_path)
    aid=s.acknowledge_liabilities(scope);a['liability_authorization']=aid
    if change=='replay':
        with pytest.raises(Exception):s.acknowledge_liabilities(scope)
        return
    with s.g.connect() as db:
        if change=='cross_run':
            s.release(c);s.cancel(c['id']);other=s.create('other',c['config']);c=s.claim()
        elif change=='expiry':a['expires']=0
        elif change=='config':db.execute('UPDATE hybrid_runs SET config=? WHERE id=?',(canonical({**c['config'],'changed':True}).decode(),c['id']))
        elif change=='old_request':db.execute('UPDATE hybrid_calls SET request=? WHERE id=?',('{}',old['id']))
        elif change=='old_hold':db.execute('UPDATE reviews SET reserve=1 WHERE id=?',(old['id'],))
        elif change=='unrelated_unknown':db.execute('INSERT INTO hybrid_calls VALUES(?,?,?,?,NULL,?)',('unrelated','another','planner','{}',1))
        elif change=='limit_reset':a['max_calls']=64
        elif change=='cancel':db.execute('UPDATE hybrid_runs SET cancel=1 WHERE id=?',(c['id'],))
        elif change=='fence':c['fence']-=1
    with pytest.raises(ValueError):s.reserve_call(c,'planner',{'new':True},80,a)


def test_receipted_steps_continue_without_resetting_limits(tmp_path):
    s,c,a,scope,old,ledger=fixture(tmp_path)
    a['liability_authorization']=s.acknowledge_liabilities(scope)
    for role in ['planner','image-0','extract','sample','final']:
        call=s.reserve_call(c,role,{'role':role},80,a);s.receipt(call['id'],{'id':role})
    with pytest.raises(ValueError):s.reserve_call(c,'extra',{},1,a)
    with pytest.raises(ValueError):s.reserve_call(c,'image-1',{},1,a)
    with pytest.raises(ValueError):s.reserve_call(c,'planner',{'drift':True},1,a)
