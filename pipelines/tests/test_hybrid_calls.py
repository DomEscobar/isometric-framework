import pytest
from generation import Generation
from provider import WaveSpeed
from hybrid_store import Store

def setup(tmp):
    return Store(Generation(tmp,WaveSpeed(key=''),{'approved':False,'total_usd':'10','max_attempts':0}))
def test_atomic_call_intent_unknown_never_repeated(tmp_path):
    s=setup(tmp_path);r=s.create('run',{'mode':'live'});c=s.claim()
    assert hasattr(s,'reserve_call'), 'atomic central call intent missing'
    auth=dict(config_sha256=__import__('artifacts').digest(__import__('artifacts').canonical(r['config'])),budget_microusd=100,max_calls=5,max_images=3,expires=9999999999)
    a=s.reserve_call(c,'planner',{'model':'test'},80,auth)
    assert a['new']
    assert s.get(c['id'])['call_count']==1
    assert not s.reserve_call(c,'planner',{'model':'test'},80,auth)['new']
    with pytest.raises(ValueError):s.reserve_call(c,'review',{'model':'test'},10,auth)
    s.receipt(a['id'],{'id':'real-mocked-transport-response'})
    with pytest.raises(ValueError):s.reserve_call(c,'review',{'model':'test'},21,auth)
    b=s.reserve_call(c,'review',{'model':'test'},20,auth);assert b['new']
    assert s.g.status()['review_reserved_usd']=='0.0001'
