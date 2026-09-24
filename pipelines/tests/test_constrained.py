"""MOCK transport; no provider purchases."""
import importlib.util
import pytest
from artifacts import digest
from generation import Generation
from test_generation import MockProvider


def test_masked_provider_uses_same_transactional_ledger(tmp_path):
    assert importlib.util.find_spec('constrained_provider'), 'supported masked provider adapter missing'
    from constrained_provider import MaskedWaveSpeed
    calls=[]
    def transport(method,path,body=None):
        calls.append((path,body))
        if path=='/models':return [{'model_id':MaskedWaveSpeed.model_id,'api_schema':{'api_schemas':[{'type':'model_run','request_schema':{'required':['prompt','image','mask_image'],'properties':{k:{'type':'string'} for k in ['prompt','image','mask_image','size']}}}]}}]
        if path=='/model/price':return dict(price=.02,currency='USD')
        return dict(id='mock-masked')
    p=MaskedWaveSpeed(key='mock',transport=transport)
    p.upload=lambda raw,name:'https://example.org/'+name
    policy=dict(approved=True,total_usd='.03',max_attempts=2)
    g=Generation(tmp_path,p,policy)
    g.reserve_review('old-liability',15000,{'unchanged':True})
    refs=[dict(input_sha256=digest(x),role=role,material=None) for x,role in [(b's','correction_target'),(b'm','edit_mask')]]
    b=dict(layout_revision='r',guide_sha256=digest(b'g'),style_id='s',style_sha256=digest(b's'),style_references=refs,prompt='localized correction',constrained=dict(size='768*408',strategy='canonical-sidewalk-mask-v1'))
    q=g.quote(b)
    assert q['model']==p.model_id
    assert set(q['inputs_template'])=={'image','mask_image','prompt','size'}
    with pytest.raises(ValueError,match='budget'):g.confirm(q['id'],'r',b'g',b's',[b'm'])
    policy['total_usd']='1'
    j=g.confirm(q['id'],'r',b'g',b's',[b'm'])
    assert j['prediction_id']=='mock-masked'
    assert j['request']['image'].endswith('style.png')
    assert j['request']['mask_image'].endswith('material-0.png')
    assert 'image_urls' not in j['request']
    assert g.confirm(q['id'],'r',b'g',b's',[b'm'])['id']==j['id']
    assert sum(path=='/'+p.model_id for path,body in calls)==1
    assert g.status()['reserved_usd']=='0.035'
    assert Generation(tmp_path,MockProvider(),policy).get(j['id'])['request']==j['request']


def test_mask_keeps_road_and_outer_landmarks_and_verifies_original():
    import numpy as np
    import io
    from PIL import Image
    from artifacts import png
    import constrained_provider as cp
    assert hasattr(cp,'build_edit_mask'), 'canonical mask and preservation proof missing'
    terrain=np.zeros((30,50),dtype=bool);terrain[3:27,3:47]=True
    road=np.zeros_like(terrain);road[13:17]=True
    sidewalk=terrain & ~road
    mask=cp.build_edit_mask(png(sidewalk.astype('uint8')*255),png(terrain.astype('uint8')*255))
    m=np.array(Image.open(io.BytesIO(mask)))>0
    assert not (m & road).any() and not m[3:6].any()
    assert m[8,8] and not m[0].any()
    original=np.zeros((30,50,4),dtype='uint8');original[:,:,3]=255
    changed=original.copy();changed[m,:3]=190
    assert cp.preservation_check(png(original),png(changed),mask)['preserved']
    changed[14,8,0]=1
    assert not cp.preservation_check(png(original),png(changed),mask)['preserved']
    assert not cp.preservation_check(png(original),png(changed[:20]),mask)['preserved']


def test_constrained_successor_selects_reviewed_history_and_one_attempt(tmp_path):
    from test_auto_engine import service,drain
    from artifacts import canonical
    s,a,rid=service(tmp_path)
    assert hasattr(s,'constrained_run'), 'constrained durable successor missing'
    w=s.get(rid)
    w.update(status='needs_attention',phase='register',stop_reason='registration_ambiguous')
    w['iterations']=[dict(id='a1',plan={'action':'register','findings':['mock']},candidate_id='e'*64,review={'id':'f'*64,'valid':True}),dict(id='a2',plan={'action':'generate','findings':['mock']},job_status='candidate_ready',registration={'blocker':'registration_ambiguous'})]
    s.save(w);original=canonical(s.get(rid))
    a.constrained_seed=lambda w:dict(candidate_id='e'*64,evaluation_id='f'*64,eligible=True,registered=True,reviewed=True,valid=True,no_unknown_liabilities=True)
    a.constrained_authorization=lambda rid:dict(parent_run_id=rid,authorization_sha256='9'*64,strategy='canonical-sidewalk-mask-v1')
    child=s.constrained_run(rid)
    assert child['inherited_iterations']==2 and child['max_iterations']==15
    assert child['latest_candidate_id']=='e'*64 and child['evaluation_id']=='f'*64
    assert s.constrained_run(rid)['id']==child['id']
    assert canonical(s.get(rid))==original
    # The one-new-image bound remains independent of the lifetime 15 cap.
    c=s.get(child['id']);c['iterations']=[{'plan':{'action':'generate','findings':['mock']}}];s.save(c)
    assert s.tick(c['id'])['stop_reason']=='constrained_one_attempt_complete'
    assert a.submits==0


def test_control_signature_is_bound_to_actual_supported_mask():
    from auto_repair import AutoRepair
    from constrained_provider import MaskedWaveSpeed
    s=object.__new__(AutoRepair)
    w={'frozen':{'authorization_sha256':'a'*64}}
    old={'findings':[dict(criterion='materials',observation='tiny pavers',correction='broad slabs')]}
    masked={**old,'control':dict(strategy='canonical-sidewalk-mask-v1',model=MaskedWaveSpeed.model_id,mask_sha256='b'*64,source_sha256='c'*64)}
    assert s.correction_signature(w,old)!=s.correction_signature(w,masked)
    assert s.correction_signature(w,masked)==s.correction_signature(w,dict(masked))
    with pytest.raises(ValueError):s.correction_signature(w,{**masked,'control':{**masked['control'],'mask_sha256':'invalid'}})


def test_constrained_adapter_is_installed_with_closed_http_start(tmp_path):
    from app import create_app
    from fastapi.testclient import TestClient
    app=create_app(tmp_path)
    assert hasattr(app.state.auto_repair.adapter,'constrained_seed'), 'constrained orchestration adapter missing'
    response=TestClient(app).post('/api/auto-repair/'+'a'*64+'/constrained',json={'confirm_paid':True})
    assert response.status_code==409
    assert app.state.generation.status()['attempts']==0


def test_masked_output_is_retained_and_rejected_without_compositing(tmp_path):
    from constrained_adapter import ConstrainedAdapter
    from artifacts import png
    import numpy as np
    from types import SimpleNamespace
    a=object.__new__(ConstrainedAdapter)
    original=np.zeros((20,30,4),dtype='uint8');original[:,:,3]=255
    output=original.copy();output[0,0,0]=1
    raw=png(output);source=png(original);mask=png(np.zeros((20,30),dtype='uint8'))
    j=dict(id='a'*64,status='completed',output_url='https://example.org/output.png')
    g=SimpleNamespace(root=tmp_path,provider=SimpleNamespace(download=lambda u:raw),resume=lambda jid:j,save=lambda j:j)
    a.masked_generation=lambda:g
    a.masked_inputs=lambda w:(b'guide',[{'raw':source},{'raw':mask}])
    a.poll_call=lambda jid:pytest.fail('unsafe provider pixels must never reach import or review')
    attempt={'job_id':j['id']}
    result=a.poll({'continuation':{'mode':'constrained-mask-recovery'}},attempt)
    assert result['status']=='failed' and result['constrained_blocker']=='constrained_unmasked_pixels_changed'
    assert (tmp_path/'constrained-outputs'/j['id']/'provider-original.bin').read_bytes()==raw
    assert attempt['preservation']['unmasked_changed_pixels']==1


def test_constrained_original_endpoint_retains_exact_bytes_and_rejects_drift(tmp_path):
    from app import create_app
    from fastapi.testclient import TestClient
    from artifacts import png
    import numpy as np
    app=create_app(tmp_path);jid='a'*64;raw=png(np.zeros((2,2,3),dtype='uint8'))
    d=tmp_path/'constrained-outputs'/jid;d.mkdir(parents=True);(d/'provider-original.bin').write_bytes(raw)
    app.state.generation.get=lambda value:dict(id=jid,binding={'constrained':{}},preservation={'provider_original_sha256':digest(raw)})
    client=TestClient(app)
    response=client.get('/api/generation/jobs/'+jid+'/constrained-original')
    assert response.status_code==200 and response.content==raw
    assert response.headers['X-Terrain-Status']=='rejected-or-unapproved-provider-original'
    (d/'provider-original.bin').write_bytes(b'drift')
    assert client.get('/api/generation/jobs/'+jid+'/constrained-original').status_code==409


def test_no_purchase_without_explicit_png_contract():
    from constrained_provider import MaskedWaveSpeed
    p=MaskedWaveSpeed(key='MOCK')
    assert hasattr(p,'require_output_contract'), 'missing lossless pre-purchase contract guard'
    p.discover=lambda:{'properties':{'image':{},'mask_image':{},'size':{}}}
    with pytest.raises(ValueError,match='lossless PNG'):p.require_output_contract()


def test_mask_prompt_excludes_unmasked_road_correction():
    from constrained_adapter import ConstrainedAdapter
    from types import SimpleNamespace
    a=object.__new__(ConstrainedAdapter)
    fs=[dict(blocking=True,criterion='materials',location='sidewalk paving',observation='tiny pavers',correction='broad slabs'),dict(blocking=True,criterion='materials',location='street roadway',observation='blue road',correction='recolor road'),dict(blocking=True,criterion='walkable_clearance',location='planting bed edges adjacent to sidewalk',observation='tufts spill',correction='confine fringe')]
    a.ev=SimpleNamespace(get=lambda eid:{'gate':{'production_approved':False,'findings':fs}})
    a.styles=SimpleNamespace(prompt=lambda sid:'unchanged style intent')
    a.control=lambda w:{'actual':'mask'}
    p=a.plan(dict(continuation={'mode':'constrained-mask-recovery'},evaluation_id='e',latest_candidate_id='c',frozen={'style':'s'}))
    assert len(p['findings'])==2 and 'recolor road' not in p['prompt']
    assert p['deferred_findings']==[fs[1]]

