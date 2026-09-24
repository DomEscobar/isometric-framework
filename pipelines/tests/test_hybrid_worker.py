import importlib.util,json
from pathlib import Path
from generation import Generation
from provider import WaveSpeed
from hybrid_store import Store
from test_hybrid_layout import sample

def test_runtime_revision_drift_stops(tmp_path):
    from hybrid_worker import Worker
    s=Store(Generation(tmp_path,WaveSpeed(key=''),{'total_usd':'10','approved':False}))
    r=s.create('stale',{'mode':'replay','runtime_version':'wrong','max_seconds':1800,'layout_fixture':sample()})
    Worker(s).tick()
    assert s.get(r['id'])['phase']=='needs_attention'
    assert 'Runtime' in s.get(r['id'])['stop_reason']

def test_replay_persisted_preview_then_material_phase(tmp_path):
    assert importlib.util.find_spec('hybrid_worker'), 'independent worker missing'
    from hybrid_worker import Worker
    s=Store(Generation(tmp_path,WaveSpeed(key=''),{'approved':False,'total_usd':'10','max_attempts':0}))
    c={'mode':'replay','description':'Explicit replay fixture, not translation','layout_fixture':sample(),'auto_continue':False,'max_images':3,'max_calls':12,'max_seconds':1800,'budget_microusd':0}
    r=s.create('replay',c);worker=Worker(s);worker.tick()
    assert s.get(r['id'])['phase']=='layout_preview'
    worker.accept(r['id'],sample());worker.tick()
    out=s.get(r['id']);assert out['phase']=='needs_attention'
    assert 'REPLAY' in out['stop_reason']
    assert (tmp_path/'hybrid'/r['id']/'candidate-0'/'diagnostic.zip').exists()
    assert s.calls(r['id'])==[]
    assert s.g.status()['reserved_usd']=='0'
    assert out.get('artifact_binding'), 'output hashes must bind every download'
    assert out.get('guide_file'), 'edited accepted geometry must own reviewer guide'
    assert out.get('sample_binding'), 'replay must exercise real material sample too'
    from fastapi.testclient import TestClient
    from hybrid_api import create_app
    client=TestClient(create_app(s))
    assert client.get('/api/hybrid-runs/'+r['id']+'/artifacts/'+out['sample_directory']+'/scene.png').status_code==200
    assert client.get('/api/hybrid-runs/'+r['id']+'/download?mode=production').status_code==409
