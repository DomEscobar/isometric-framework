import importlib.util
import pytest
from generation import Generation
from provider import WaveSpeed

def test_duplicate_start_fencing_cancel(tmp_path):
    assert importlib.util.find_spec('hybrid_store'), 'persisted hybrid workflow missing'
    from hybrid_store import Store
    s=Store(Generation(tmp_path,WaveSpeed(key=''),{'approved':False,'total_usd':'10','max_attempts':0}))
    a=s.create('one',{'mode':'replay'});b=s.create('one',{'mode':'replay'})
    assert a['id']==b['id']
    with pytest.raises(ValueError):s.create('one',{'mode':'live'})
    claim=s.claim();assert claim and s.claim() is None
    s.cancel(a['id'])
    s.save(claim,phase='planning')
    assert s.get(a['id'])['cancel_requested']
    with pytest.raises(ValueError):s.save({**claim,'fence':0},phase='succeeded')
