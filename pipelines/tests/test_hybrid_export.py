import importlib.util,pytest
from generation import Generation
from provider import WaveSpeed
from hybrid_store import Store

def test_production_requires_bound_actual_model_receipts(tmp_path):
    assert importlib.util.find_spec('hybrid_export'), 'production receipt gate missing'
    from hybrid_export import production_bundle
    s=Store(Generation(tmp_path,WaveSpeed(key='')))
    r=s.create('forged',{'mode':'live'});c=s.claim();s.save(c,phase='succeeded',production_approved=True)
    with pytest.raises(ValueError):production_bundle(s,s.get(r['id']))
