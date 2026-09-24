"""Provider calls here are mocked transport only; never live generation."""
import importlib.util
from decimal import Decimal
import pytest


def test_adapter_live_contract_with_mocked_transport():
    assert importlib.util.find_spec('provider'), 'provider adapter missing'
    from provider import WaveSpeed
    calls=[]
    def request(method,path,body=None):
        calls.append((method,path,body))
        if path == '/models':
            return [{'model_id':'bytedance/seedream-v5.0-lite/edit','api_schema':{'api_schemas':[{'type':'model_run','request_schema':{'required':['prompt','images'],'properties':{'prompt':{'type':'string'},'images':{'type':'array'},'output_format':{'enum':['png']},'size':{'type':'string'}}}}]}}]
        if path == '/model/price': return {'model_id':'bytedance/seedream-v5.0-lite/edit','price':0.035,'discounted_price':0.035,'currency':'USD'}
        if path.endswith('/result'): return {'id':'prediction-1','status':'completed','outputs':['https://example.org/result.png']}
        return {'id':'prediction-1','status':'created'}
    p=WaveSpeed(key='TEST-NOT-A-SECRET',transport=request)
    schema=p.discover()
    inputs={'prompt':'ground','images':['https://example.org/a.png'],'output_format':'png','size':'1920*1344'}
    q=p.quote(inputs)
    assert Decimal(str(q['price'])) == Decimal('0.035')
    assert p.submit(inputs)['id'] == 'prediction-1'
    assert p.poll('prediction-1')['status'] == 'completed'
    assert calls[-2][1] == '/bytedance/seedream-v5.0-lite/edit'
    assert 'images' in schema['required'] and 'size' in schema['properties']


class MockProvider:
    authenticated=True
    submitted=0
    ambiguous=False
    def discover(self): return {'required':['prompt','image_urls'],'properties':{'prompt':{},'image_urls':{},'output_format':{'enum':['png']}}}
    def quote(self,inputs): return {'price':0.011,'discounted_price':0.011,'currency':'USD','model_id':'meta/muse-image/edit'}
    def upload(self,raw,name): return 'https://example.org/'+name
    def submit(self,inputs):
        self.submitted += 1
        if self.ambiguous: raise TimeoutError('mock uncertain submission')
        return {'id':'prediction-1','status':'created'}
    def poll(self,pid): return {'id':pid,'status':'processing'}


def test_budget_reservation_idempotency_and_exact_recovery(tmp_path):
    assert importlib.util.find_spec('generation'), 'durable generation workflow missing'
    from generation import Generation
    p=MockProvider()
    g=Generation(tmp_path,p,policy={'approved':False,'total_usd':'0','max_attempts':0})
    binding={'layout_revision':'r1','guide_sha256':'g1','style_id':'s1','style_sha256':'s2','prompt':'ground'}
    q=g.quote(binding)
    with pytest.raises(ValueError,match='budget'):
        g.confirm(q['id'],'r1',b'guide',b'style')
    assert p.submitted == 0
    policy={'approved':True,'total_usd':'0.02','max_attempts':1}
    g=Generation(tmp_path,p,policy=policy)
    with pytest.raises(ValueError,match='stale'):
        g.confirm(q['id'],'r2',b'guide',b'style')
    from artifacts import digest
    binding.update(guide_sha256=digest(b'guide'),style_sha256=digest(b'style'))
    q=g.quote(binding)
    job=g.confirm(q['id'],'r1',b'guide',b'style')
    assert job['prediction_id']=='prediction-1'
    assert g.confirm(q['id'],'r1',b'guide',b'style')['id']==job['id']
    assert p.submitted==1
    restarted=Generation(tmp_path,p,policy=policy)
    assert restarted.resume(job['id'])['status']=='processing'
    assert p.submitted==1
    assert restarted.status()['reserved_usd']=='0.011'
    q2=g.quote({**binding,'prompt':'another candidate'})
    with pytest.raises(ValueError,match='budget|attempt'):
        g.confirm(q2['id'],'r1',b'guide',b'style')


def test_ambiguous_never_resubmits_even_after_restart(tmp_path):
    from generation import Generation
    from artifacts import digest
    p=MockProvider();p.ambiguous=True
    policy={'approved':True,'total_usd':'1','max_attempts':3}
    g=Generation(tmp_path,p,policy)
    b={'layout_revision':'r','guide_sha256':digest(b'g'),'style_id':'s','style_sha256':digest(b's'),'prompt':'x'}
    q=g.quote(b);j=g.confirm(q['id'],'r',b'g',b's')
    assert j['status']=='ambiguous'
    g=Generation(tmp_path,p,policy)
    assert g.resume(j['id'])['status']=='ambiguous'
    assert g.confirm(q['id'],'r',b'g',b's')['id']==j['id']
    q2=g.quote({**b,'prompt':'changed'})
    with pytest.raises(ValueError,match='unresolved'):g.confirm(q2['id'],'r',b'g',b's')
    assert p.submitted==1


def test_persisted_job_binding_drift_is_rejected(tmp_path):
    from generation import Generation
    from artifacts import digest,canonical
    import json
    p=MockProvider();g=Generation(tmp_path,p,{'approved':True,'total_usd':'1','max_attempts':3})
    b={'layout_revision':'r','guide_sha256':digest(b'g'),'style_id':'s','style_sha256':digest(b's'),'prompt':'x'}
    q=g.quote(b)
    with pytest.raises(ValueError,match='hash drift'):g.confirm(q['id'],'r',b'changed',b's')
    j=g.confirm(q['id'],'r',b'g',b's')
    j['binding']['layout_revision']='wrong'
    with g.connect() as db:db.execute('UPDATE jobs SET record=? WHERE id=?',(canonical(j).decode(),j['id']))
    with pytest.raises(ValueError,match='binding'):g.resume(j['id'])


def test_refreshed_quote_same_request_does_not_submit_twice(tmp_path,monkeypatch):
    from generation import Generation
    from artifacts import digest
    p=MockProvider();g=Generation(tmp_path,p,{'approved':True,'total_usd':'1','max_attempts':3})
    b={'layout_revision':'r','guide_sha256':digest(b'g'),'style_id':'s','style_sha256':digest(b's'),'prompt':'x'}
    q=g.quote(b);j=g.confirm(q['id'],'r',b'g',b's')
    import time
    now=time.time();monkeypatch.setattr('generation.time.time',lambda:now+10)
    q2=g.quote(b)
    assert q2['id']!=q['id']
    assert g.confirm(q2['id'],'r',b'g',b's')['id']==j['id']
    assert p.submitted==1


def test_mocked_provider_candidate_pipeline(tmp_path):
    from fastapi.testclient import TestClient
    from app import create_app
    import base64
    p=MockProvider()
    p.poll=lambda pid:{'id':pid,'status':'completed','outputs':['https://example.org/result.png']}
    with TestClient(create_app(tmp_path,provider=p,policy={'approved':True,'total_usd':'0.03','max_attempts':2})) as c:
        v=c.post('/api/layouts',json={}).json();rid=v['revision']
        raw=c.get(f'/api/layouts/{rid}/artifacts/clean-guide.png').content
        p.download=lambda url:raw # labelled technical fixture; not generated art
        style=c.post('/api/styles',json={'png_base64':base64.b64encode(raw).decode(),'role':'style_only'}).json()
        q=c.post('/api/generation/quote',json={'revision':rid,'style_id':style['id'],'prompt':'technical transport test'}).json()
        j=c.post('/api/generation/confirm',json={'revision':rid,'quote_id':q['id']}).json()
        assert j['status']=='submitted'
        assert 'request' not in j
        result=c.post(f"/api/generation/jobs/{j['id']}/resume",json={}).json()
        assert result['status']=='candidate_ready',result
        t=c.get('/api/terrain/'+result['candidate_id']).json()
        assert t['source']=='provider output; unreviewed'
        assert t['provider_origin']['prediction_id']=='prediction-1'
        assert t['production_approved'] is False
        assert c.get(f"/api/terrain/{t['id']}/download?revision={rid}&density=2").status_code==200
        assert c.post(f"/api/generation/jobs/{j['id']}/resume",json={}).json()['candidate_id']==t['id']
        assert p.submitted==1
