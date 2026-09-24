import importlib.util
from fastapi.testclient import TestClient
from generation import Generation
from provider import WaveSpeed
from hybrid_store import Store

def test_api_reload_preview_download_cancel(tmp_path):
    assert importlib.util.find_spec('hybrid_api'), 'standalone API/UI missing'
    from hybrid_api import create_app
    s=Store(Generation(tmp_path,WaveSpeed(key=''),{'approved':False,'total_usd':'10','max_attempts':0}))
    c=TestClient(create_app(s));assert c.get('/').status_code==200
    q=c.post('/api/hybrid-runs',headers={'Idempotency-Key':'one'},json={'mode':'replay','description':'Replay, keine Sprachübersetzung'})
    assert q.status_code==201,q.text
    rid=q.json()['id']
    assert c.get('/api/hybrid-runs').json()[0]['id']==rid
    assert c.post('/api/hybrid-runs/'+rid+'/cancel').json()['cancel_requested']
    assert c.get('/api/hybrid-runs/'+rid+'/download?mode=production').status_code==409
    assert c.get('/api/hybrid-runs/'+rid+'/artifacts/../../generation.sqlite3').status_code!=200
    claim=s.claim()
    r=s.create('other',{'mode':'replay'});claim=s.claim();s.save(claim,prepared_image={'body':{'image_urls':['https://secret.example/?token=private']}});s.release(claim)
    assert 'secret.example' not in c.get('/api/hybrid-runs/'+r['id']).text
    assert 'secret.example' not in c.get('/api/hybrid-runs/'+r['id']+'/events').text

def test_uploaded_original_binding_rejects_wrong_reference(tmp_path,monkeypatch):
    import io,base64
    from PIL import Image
    from hybrid_api import create_app
    monkeypatch.setenv('HYBRID_PLANNER_MODEL','mock/planner');monkeypatch.setenv('HYBRID_REVIEWER_MODEL','mock/reviewer')
    s=Store(Generation(tmp_path,WaveSpeed(key=''),{'approved':False,'total_usd':'10'}));c=TestClient(create_app(s))
    uploads=[]
    for color in ['red','blue']:
        b=io.BytesIO();Image.new('RGB',(16,16),color).save(b,format='JPEG')
        uploads.append(c.post('/api/hybrid/uploads',json={'base64_data':base64.b64encode(b.getvalue()).decode()}).json())
    cfg={'mode':'live','description':'Test reference binding','confirm_paid':True,'budget_microusd':100000,'reference_sha256':uploads[0]['sha256'],'reference_original_sha256':uploads[0]['original_sha256']}
    ok=c.post('/api/hybrid-runs',headers={'Idempotency-Key':'valid'},json=cfg)
    assert ok.status_code==201,ok.text
    wrong=c.post('/api/hybrid-runs',headers={'Idempotency-Key':'wrong'},json={**cfg,'reference_original_sha256':uploads[1]['original_sha256']})
    assert wrong.status_code==409
    assert not s.calls(ok.json()['id'])


def test_live_run_uses_separate_planner_and_independent_visual_reviewer(tmp_path,monkeypatch):
    import io,base64
    from PIL import Image
    from hybrid_api import create_app
    monkeypatch.setenv('HYBRID_PLANNER_MODEL','openai/gpt-6-luna-pro')
    monkeypatch.setenv('HYBRID_REVIEWER_MODEL','google/gemini-3.8-flash')
    s=Store(Generation(tmp_path,WaveSpeed(key=''),{'approved':False,'total_usd':'10'}));c=TestClient(create_app(s))
    b=io.BytesIO();Image.new('RGB',(16,16),'green').save(b,format='PNG')
    ref=c.post('/api/hybrid/uploads',json={'base64_data':base64.b64encode(b.getvalue()).decode()}).json()
    cfg={'mode':'live','description':'Flat meadow with water and a path','confirm_paid':True,'budget_microusd':1000000,
         'reference_sha256':ref['sha256'],'reference_original_sha256':ref['original_sha256'],
         'max_calls':10,'max_images':1,'layout_review_iterations':5,
         'layout_contract':'flat-pond-path-plateau/1'}
    result=c.post('/api/hybrid-runs',headers={'Idempotency-Key':'separate-reviewer'},json=cfg)
    assert result.status_code==201,result.text
    assert result.json()['config']['layout_contract']=='flat-pond-path-plateau/1'
    assert result.json()['config']['planner_model']=='openai/gpt-6-luna-pro'
    assert result.json()['config']['reviewer_model']=='google/gemini-3.8-flash'
    assert result.json()['config']['planner_model']!=result.json()['config']['reviewer_model']


def test_live_run_accepts_explicit_eur50_project_cap_in_usd(tmp_path,monkeypatch):
    import io,base64
    from PIL import Image
    from hybrid_api import create_app
    monkeypatch.setenv('HYBRID_PLANNER_MODEL','openai/gpt-6-luna-pro')
    monkeypatch.setenv('HYBRID_REVIEWER_MODEL','google/gemini-3.8-flash')
    s=Store(Generation(tmp_path,WaveSpeed(key=''),{'approved':True,'total_usd':'57.315','max_attempts':25}));c=TestClient(create_app(s))
    b=io.BytesIO();Image.new('RGB',(16,16),'green').save(b,format='PNG')
    ref=c.post('/api/hybrid/uploads',json={'base64_data':base64.b64encode(b.getvalue()).decode()}).json()
    cfg={'mode':'live','description':'Flat meadow with water and a path','confirm_paid':True,'budget_microusd':49_382_918,
         'reference_sha256':ref['sha256'],'reference_original_sha256':ref['original_sha256'],
         'max_calls':46,'max_images':15,'layout_review_iterations':5}
    result=c.post('/api/hybrid-runs',headers={'Idempotency-Key':'eur50-budget'},json=cfg)
    assert result.status_code==201,result.text
    assert result.json()['config']['budget_microusd']==49_382_918


def test_start_api_installs_space_bunny_as_default_planner(tmp_path,monkeypatch):
    import types
    from hybrid_api import models_config
    monkeypatch.delenv('HYBRID_PLANNER_MODEL',raising=False)
    monkeypatch.delenv('HYBRID_REVIEWER_MODEL',raising=False)
    store=types.SimpleNamespace(g=types.SimpleNamespace(root=tmp_path))
    cfg=models_config(store)
    assert cfg['planner_model']=='stealth/space-bunny-alpha'
    assert cfg['reviewer_model']=='google/gemini-3.8-flash'


def test_start_api_accepts_only_supported_named_layout_contract():
    from hybrid_api import Start
    from pydantic import ValidationError

    base={'mode':'live','description':'A meadow layout'}
    assert Start.model_validate({**base,'layout_contract':'flat-pond-path-plateau/1'}).layout_contract=='flat-pond-path-plateau/1'
    try:
        Start.model_validate({**base,'layout_contract':'arbitrary-contract'})
    except ValidationError:
        pass
    else:
        raise AssertionError('unknown contract must be rejected')


def test_live_run_rejects_same_planner_and_reviewer_models(tmp_path,monkeypatch):
    import io,base64
    from PIL import Image
    from hybrid_api import create_app
    monkeypatch.setenv('HYBRID_PLANNER_MODEL','openai/gpt-6-luna-pro')
    monkeypatch.setenv('HYBRID_REVIEWER_MODEL','openai/gpt-6-luna-pro')
    s=Store(Generation(tmp_path,WaveSpeed(key=''),{'approved':False,'total_usd':'10'}));c=TestClient(create_app(s))
    b=io.BytesIO();Image.new('RGB',(16,16),'green').save(b,format='PNG')
    ref=c.post('/api/hybrid/uploads',json={'base64_data':base64.b64encode(b.getvalue()).decode()}).json()
    cfg={'mode':'live','description':'Flat meadow with water and a path','confirm_paid':True,'budget_microusd':1000000,
         'reference_sha256':ref['sha256'],'reference_original_sha256':ref['original_sha256'],
         'max_calls':10,'max_images':1,'layout_review_iterations':5}
    result=c.post('/api/hybrid-runs',headers={'Idempotency-Key':'same-reviewer'},json=cfg)
    assert result.status_code==409 and 'unabhängiges' in result.text.lower()
