import json,time,concurrent.futures
import pytest
from artifacts import canonical,digest
from generation import Generation
from provider import WaveSpeed
from hybrid_store import Store
from hybrid_layout import compile_layout,supported,allowed
from test_hybrid_layout import sample

def test_stale_lease_reclaim_and_independent_cancel(tmp_path):
    s=Store(Generation(tmp_path,WaveSpeed(key='')));r=s.create('one',{'mode':'replay'});old=s.claim()
    with s.g.connect() as db:db.execute('UPDATE hybrid_runs SET lease=0')
    new=s.claim();assert new['fence']>old['fence']
    with pytest.raises(ValueError):s.save(old,phase='planning')
    s.cancel(r['id']);s.save(new,phase='planning');assert s.get(r['id'])['cancel_requested']
def test_await_authorization_not_reclaimed(tmp_path):
    s=Store(Generation(tmp_path,WaveSpeed(key='')));s.create('one',{});c=s.claim();s.save(c,phase='await_authorization');s.release(c)
    assert s.claim() is None

def test_water_entire_footprint_and_cliff_graph():
    x=sample();x['cells'][1][2]='water';x['actor_width']=1.2;x['spawn']=[3,3]
    w=compile_layout(x);assert not supported(w,[1,1]);assert not allowed(w,[1,2],[2,2])
    x=sample();x['heights'][3][4]=16
    with pytest.raises(ValueError,match='verbunden'):compile_layout(x)
    x['transitions']=[[[4,2],[4,3]]]
    with pytest.raises(ValueError,match='8px'):compile_layout(x)
def test_stair_full_swept_width_cliff_side():
    x=sample();x['actor_width']=1.2;x['heights'][3][4]=8;x['cells'][3][4]='stairs';x['transitions']=[[[4,2],[4,3]]]
    with pytest.raises(ValueError):compile_layout(x)
def test_unsupported_and_grid_constraints():
    x=sample();x['unsupported']=['Brücke']
    with pytest.raises(ValueError,match='Brücke'):compile_layout(x)
    x=sample();x['cells'][0].pop()
    with pytest.raises(ValueError):compile_layout(x)
    x=sample();x['heights'][0][0]=9
    with pytest.raises(ValueError):compile_layout(x)

def test_concurrent_start_and_central_budget(tmp_path):
    s=Store(Generation(tmp_path,WaveSpeed(key=''),{'approved':False,'total_usd':'0.0001'}))
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:rows=list(pool.map(lambda _:s.create('same',{'a':1}),range(12)))
    assert len({r['id'] for r in rows})==1
    c=s.claim();auth={'config_sha256':digest(canonical(c['config'])),'expires':time.time()+100,'budget_microusd':100,'max_calls':4,'max_images':3}
    with s.g.connect() as db:db.execute('INSERT INTO reviews VALUES(?,?,?)',('legacy',90,'{}'))
    with pytest.raises(ValueError,match='Budget'):s.reserve_call(c,'planner',{},11,auth)
    call=s.reserve_call(c,'planner',{},10,auth);s.cancel(c['id']);s.receipt(call['id'],{'real':'receipt after cancel'})
    with pytest.raises(ValueError):s.reserve_call(c,'review',{},1,auth)
    assert s.calls(c['id'])[0]['receipt_known']

def test_terminal_no_reopen(tmp_path):
    s=Store(Generation(tmp_path,WaveSpeed(key='')));r=s.create('terminal',{});c=s.claim();s.save(c,phase='needs_attention');s.release(c)
    before=s.get(r['id']);assert s.resume(r['id'])==before;assert s.cancel(r['id'])==before
