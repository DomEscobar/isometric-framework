"""NO NETWORK: mocked provider decisions + retained real pixels; not live proof."""
import json,time,io,zipfile
from pathlib import Path
import pytest
from artifacts import canonical,digest
from generation import Generation
from hybrid_store import Store
from hybrid_worker import Worker,immutable
from hybrid_models import OpenRouter,MaterialImage,CRITERIA
from hybrid_artifact import replay_materials,ROOT,ACTOR
from hybrid_export import production_bundle
from test_hybrid_layout import sample

@pytest.mark.parametrize('fail_first',[False,True,'local','local_cap','local_wrong','local_uncertain','local_call_cap'])
def test_mocked_full_adapter_worker_flow_and_production_gate(tmp_path,monkeypatch,fail_first):
    source,crops=replay_materials();reference=(ROOT/'evidence/hybrid-multilevel/generation/style-reference.png').read_bytes();calls=[]
    model='mock/explicit-test-only';review_model='mock/independent-reviewer';meta={'id':model,'context_length':10000,'top_provider':{'max_completion_tokens':16384},'pricing':{'prompt':'0.000001','completion':'0.000001'},'architecture':{'input_modalities':['text','image'],'output_modalities':['text']},'reasoning':{'supported_efforts':['low']},'supported_parameters':['response_format','max_tokens','temperature','structured_outputs','reasoning']}
    plan={'unsupported':[],'layout':sample(),'material_plan':{'intent':'Mock test reference-derived grass and masonry','materials':{'land':'grass','wall':'masonry'},'avoid':[],'uncertainty':[]},'interpretation':'Mock fixture; NOT natural-language/live inference'}
    review={'criteria':{key:{'verdict':'pass','evidence_ids':['final','guide'] if key in ['layout_fidelity','walkable_clearance'] else ['final','reference'],'observation':'Explicit mock decision, not genuine visual approval','correction':''} for key in CRITERIA}}
    def request(self,method,path,body=None):
        if path=='/auth/key':return {'data':{}}
        if path=='/models':return {'data':[meta,{**meta,'id':review_model}]}
        calls.append(body)
        text=body['messages'][1]['content'][0]['text']
        
        if self.model==model and len(calls)==1:result=plan
        elif text.startswith('You are an independent visual and structural reviewer.'):
            import re
            result={'decision':'approve','criteria':{key:{'verdict':'pass','observation':'Mock independent layout criterion.','correction':''} for key in ['water_shore','path_shape','stair_visibility','plateau','walkability','height_consistency']},'summary':'Mock response only.'}
            result['layout_sha256']=re.search(r'layout_sha256=([0-9a-f]{64})',text).group(1);result['preview_sha256']=re.search(r'preview_sha256=([0-9a-f]{64})',text).group(1)
        elif text.startswith('Locate'):result={'source_sha256':digest(source),'crops':{k:crops['crops'][k] for k in ['land','wall']}}
        elif text.startswith('Independent visual review, stage '):
            result=json.loads(json.dumps(review))
            stage_calls=[x for x in calls if x['messages'][1]['content'][0]['text'].startswith('Independent visual review, stage review_sample')]
            first_sample_review=text.startswith('Independent visual review, stage review_sample') and len(stage_calls)==1
            if first_sample_review and fail_first is True:
                result['criteria']['materials']['verdict']='fail';result['criteria']['materials']['correction']='Change source material'
            if first_sample_review and str(fail_first).startswith('local'):
                result['criteria']['scale']['verdict']='fail'
                binding={'source_sha256':digest(source),'crops':{k:crops['crops'][k] for k in ['land','wall']}}
                result['local_sampling']={'source_sha256':digest(source),'binding_sha256':digest(canonical(binding)),'materials':{'land':{'source_pixels_per_unit':binding['crops']['land']['source_pixels_per_unit'],'offset':[1,2]}}}
                if fail_first=='local_wrong':result['local_sampling']['source_sha256']='0'*64
                if fail_first=='local_uncertain':result['criteria']['scale']['verdict']='uncertain'
        else:result=review
        return {'id':'mock-'+str(len(calls)),'model':self.model,'choices':[{'finish_reason':'stop','message':{'content':json.dumps(result)}}],'usage':{'mock':True}}
    monkeypatch.setattr(OpenRouter,'request',request)
    monkeypatch.setattr(MaterialImage,'discover',lambda self:{'mock':'schema'})
    monkeypatch.setattr(MaterialImage,'upload',lambda self,raw,name:'https://mock.invalid/'+name)
    monkeypatch.setattr(MaterialImage,'quote',lambda self,body:{'price':.011,'currency':'USD'})
    monkeypatch.setattr(MaterialImage,'submit',lambda self,body:{'id':'mock-image'})
    monkeypatch.setattr(MaterialImage,'poll',lambda self,pid:{'id':pid,'status':'completed','outputs':['https://mock.invalid/output.png']})
    monkeypatch.setattr(MaterialImage,'download',lambda self,url:source)
    s=Store(Generation(tmp_path,MaterialImage(),{'approved':False,'total_usd':'10'}));immutable(tmp_path/'hybrid-uploads'/(digest(reference)+'.png'),reference)
    immutable(tmp_path/'hybrid-uploads'/(digest(reference)+'.original'),reference)
    cfg=dict(reference_original_sha256=digest(reference),mode='live',description='Mock fixture, not a live inference',constraints={k:sample()[k] for k in ['width','height','actor_width']},reference_sha256=digest(reference),actor_sha256=digest((ACTOR/'character.png').read_bytes()),planner_model=model,reviewer_model=review_model,token_policy={'planner':{'max_tokens':8192,'reasoning_effort':'low'},'layout_review':{'max_tokens':8192,'reasoning_effort':'low'},'extraction':{'max_tokens':8192,'reasoning_effort':'low'},'review':{'max_tokens':8192,'reasoning_effort':'low'}},max_seconds=1800,max_calls=12,max_images=3,budget_microusd=1_000_000,auto_continue=False)
    if fail_first=='local_cap':cfg['max_local_corrections']=0
    if fail_first=='local_call_cap':cfg['max_calls']=5
    r=s.create('mock-only',cfg);immutable(tmp_path/'hybrid-authorizations'/(r['id']+'.json'),canonical({'config_sha256':digest(canonical(cfg)),'expires':time.time()+300,'max_images':3,'max_calls':cfg['max_calls'],'budget_microusd':1_000_000}))
    worker=Worker(s);worker.tick();assert s.get(r['id'])['phase']=='layout_preview'
    worker.accept(r['id'],sample())
    for _ in range(16):
        worker=Worker(s);worker.tick()
        if s.get(r['id'])['phase'] in ['succeeded','needs_attention']:break
    r=s.get(r['id'])
    if fail_first=='local_call_cap':
        assert r['phase']=='needs_attention' and r['image_count']==0 and len(calls)==2
        assert 'Aufruflimit' in r['stop_reason']
        return
    if fail_first in ['local_cap','local_wrong','local_uncertain']:
        assert r['phase']=='needs_attention',r
        assert r['image_count']==1 and len(calls)==4
        expected={'local_cap':'Korrekturlimit','local_wrong':'bindung','local_uncertain':'unsicher'}[fail_first]
        assert expected.lower() in r['stop_reason'].lower(),r['stop_reason']
        with pytest.raises(ValueError):production_bundle(s,r)
        return
    if fail_first is True:
        assert r['phase']=='needs_attention',r.get('stop_reason')
        assert 'identisch' in r['stop_reason']
        assert len(calls)==4
        return
    assert r['phase']=='succeeded',r.get('stop_reason')
    assert len(calls)==(6 if fail_first=='local' else 5) and len(s.calls(r['id']))==(7 if fail_first=='local' else 6)
    if fail_first=='local':
        assert r['local_count']==1 and r['image_count']==1
        assert r['crop_binding']['crops']['land']['offset']==[1,2]
    assert r.get('sample_binding'), 'separate sample must precede target rendering'
    sample_dir=tmp_path/'hybrid'/r['id']/r['sample_directory']
    assert (sample_dir/'scene.png').read_bytes() != (tmp_path/'hybrid'/r['id']/r['latest']/'scene.png').read_bytes()
    assert r['verification'].get('production_rebuild_exact'), 'worker must verify full production rebuild before success'
    with pytest.raises(ValueError):production_bundle(s,{**r,'verification':{**r['verification'],'production_rebuild_exact':False}})
    raw=production_bundle(s,r)
    with zipfile.ZipFile(io.BytesIO(raw)) as package:
        assert 'reference-original.image' in package.namelist(), 'original upload missing'
        assert package.read('reference-original.image')==reference
        extracted=tmp_path/'production-extracted';package.extractall(extracted)
    import subprocess
    rebuilt=tmp_path/'production-rebuilt'
    result=subprocess.run(['python3',str(extracted/'source/rebuild.py'),str(rebuilt)],capture_output=True)
    assert result.returncode==0,result.stderr.decode()
    assert (rebuilt/'production.zip').read_bytes()==raw
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        assert json.loads(z.read('provenance.json'))['production_approved']
        assert len(json.loads(z.read('approval.json'))['reviews'])==2
    if fail_first=='local':
        import os,socket,threading,uvicorn,urllib.request
        from hybrid_api import create_app
        evidence=Path(os.environ.get('HYBRID_MOCK_EVIDENCE',str(tmp_path/'mock-browser')));evidence.mkdir(parents=True,exist_ok=True)
        sock=socket.socket();sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
        server=uvicorn.Server(uvicorn.Config(create_app(s),log_level='error'));thread=threading.Thread(target=server.run,kwargs={'sockets':[sock]},daemon=True);thread.start()
        try:
            for _ in range(100):
                if server.started:break
                time.sleep(.02)
            assert server.started
            result=subprocess.run(['node',str(ROOT/'tests/hybrid-production-browser.mjs')],env={**os.environ,'BASE_URL':f'http://127.0.0.1:{port}','RUN_ID':r['id'],'EVIDENCE':str(evidence)},capture_output=True,timeout=60)
            assert result.returncode==0,result.stderr.decode()
            assert (evidence/'browser-production.zip').read_bytes()==raw
            with zipfile.ZipFile(evidence/'browser-production.zip') as z:z.extractall(evidence/'extracted')
            check=subprocess.run(['python3',str(evidence/'extracted/source/rebuild.py'),str(evidence/'rebuilt')],capture_output=True,timeout=120)
            assert check.returncode==0,check.stderr.decode()
            assert (evidence/'rebuilt/production.zip').read_bytes()==raw
            (evidence/'verification.json').write_bytes(canonical({'mock_receipts':True,'production_rebuild_exact':True,'download_sha256':digest(raw),'local_count':r['local_count'],'image_count':r['image_count'],'call_count':r['call_count']}))
        finally:
            server.should_exit=True;thread.join(timeout=10);sock.close()
    assert b'https://mock.invalid' not in b''.join(zipfile.ZipFile(io.BytesIO(raw)).read(n) for n in zipfile.ZipFile(io.BytesIO(raw)).namelist())
    with pytest.raises(ValueError):production_bundle(s,{**r,'config':{**r['config'],'reference_original_sha256':'0'*64}})
    d=tmp_path/'hybrid'/r['id']/r['latest'];(d/'scene.png').write_bytes(b'tampered')
    with pytest.raises(ValueError):production_bundle(s,r)
