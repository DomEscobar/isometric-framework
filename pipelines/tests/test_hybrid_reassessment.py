import copy,json,time,base64
import pytest
from test_hybrid_material_repair import decision

def candidate(attempt,conflict=True):
    raw=decision()
    raw['crops']['stairs']['observation']=('Flat speckled grey concrete or stone slab without any cut stone stair treads or visible risers.' if conflict else 'Architectural risers, not flat stone')
    return dict(attempt=attempt,decision=raw,source_sha256='a'*64,size=[32,32])

def test_select_newest_only_contract_conflict_not_latest_regression():
    from hybrid_reassessment import select_candidate
    candidates=[candidate(9,False),candidate(3),candidate(1)]
    old=copy.deepcopy(candidates)
    selected=select_candidate(candidates,{'land','stairs'})
    assert selected['attempt']==3
    assert selected['decision']['crops']['stairs']['verdict']=='fail'
    assert selected['invalidation']['validator_version']=='flat-material-role/2'
    assert selected['invalidation']['production_approved'] is False
    assert candidates==old
    assert select_candidate(list(reversed(candidates)),{'land','stairs'})==selected

@pytest.mark.parametrize('bad',['hash','citation','uncertain','bounds','additional_defect'])
def test_selector_rejects_invalid_or_mixed_failure(bad):
    from hybrid_reassessment import select_candidate
    c=candidate(1)
    if bad=='hash':c['source_sha256']='b'*64
    if bad=='citation':c['decision']['crops']['land']['evidence_ids']=['reference']
    if bad=='uncertain':c['decision']['crops']['land']['verdict']='uncertain'
    if bad=='bounds':c['decision']['crops']['stairs']['xywh']=[99,0,16,16]
    if bad=='additional_defect':c['decision']['crops']['land']['verdict']='fail'
    with pytest.raises(ValueError):select_candidate([c],{'land','stairs'})

def archived_parent(tmp_path,monkeypatch):
    from test_hybrid_material_repair import failed_parent
    from hybrid_material_repair import continue_material
    from hybrid_worker import Worker,immutable,ACTOR
    from hybrid_reference import reference_bytes
    from artifacts import canonical,digest
    s,p=failed_parent(tmp_path,monkeypatch)
    child=continue_material(s,p['id'],'archive-parent',1900000,1800,'pipeline livefix authority')
    auth={**child['config'],'config_sha256':digest(canonical(child['config'])),'expires':time.time()+500}
    immutable(tmp_path/'hybrid-authorizations'/(child['id']+'.json'),canonical(auth))
    Worker(s).tick();r=s.claim();d=tmp_path/'hybrid'/r['id']
    from hybrid_reference import reference_bytes
    reference,_=reference_bytes(s.g.root,r['config'])
    for attempt in [1,2]:
        source=(d/'source-0.png').read_bytes();sha=digest(source)
        immutable(d/f'source-{attempt}.png',source)
        inputs=[dict(id='reference',sha256=r['config']['reference_sha256']),dict(id='guide',sha256=r['guide_sha256']),dict(id='correction_target',sha256=sha)]
        req=dict(attempt=attempt,amount=100,inputs=inputs,body={'prompt':'flat source contract'})
        immutable(d/f'image-request-{attempt}.json',canonical(req))
        c=s.reserve_call(r,f'image-{attempt}',req,100,auth)
        s.receipt(c['id'],dict(id=f'prediction-{attempt}',input=req['body']))
        s.save(r,phase='polling',prediction_id=f'prediction-{attempt}')
        s.save(r,phase='extracting',source_sha256=sha)
        raw=candidate(attempt,attempt==1)['decision'];raw['source_sha256']=sha
        raw['crops']={k:copy.deepcopy(raw['crops']['stairs' if k==next(iter(r['material_plan']['materials'])) else 'land']) for k in r['material_plan']['materials']}
        images={'actor':(ACTOR/'character.png').read_bytes(),'board':source,'reference':reference}
        content=[]
        for k,v in sorted(images.items()):content.extend([dict(type='text',text='evidence_id='+k),dict(type='image_url',image_url={'url':'data:image/png;base64,'+base64.b64encode(v).decode()})])
        req=dict(body=dict(model='test/model',messages=[{},dict(content=content)]),inputs=[dict(id=k,sha256=digest(v)) for k,v in sorted(images.items())])
        c=s.reserve_call(r,f'extraction-{attempt}',req,100,auth)
        s.receipt(c['id'],dict(id=f'extract-{attempt}',model='test/model',choices=[dict(finish_reason='stop',message={'content':json.dumps(raw)})]))
        immutable(d/f'crop-decision-{attempt}.json',canonical(raw))
    s.save(r,phase='needs_attention',attempt=2);s.release(r)
    return s,s.get(r['id'])

def test_api_reassessment_whole_source_at_image_cap_immutable_parent(tmp_path,monkeypatch):
    from fastapi.testclient import TestClient
    from hybrid_api import create_app
    from hybrid_worker import Worker,immutable
    from hybrid_models import OpenRouter,MaterialImage
    from artifacts import canonical,digest
    s,p=archived_parent(tmp_path,monkeypatch);old=s.get(p['id']);c=TestClient(create_app(s))
    response=c.post('/api/hybrid-runs/'+p['id']+'/reassess-source',json=dict(budget_microusd=1900000,max_seconds=1800,confirm_paid=True,approval_text='standing livefix source reassessment'),headers={'Idempotency-Key':'reassess'})
    assert response.status_code==201,response.text
    child=response.json();proof=child['config']['continuation']
    assert (child['call_count'],child['image_count'])==(8,3)
    assert child['config']['max_images']==3 and child['config']['max_calls']==12
    assert proof['selected']['attempt']==1 and not child['production_approved']
    assert child['config']['followup_call_limit']==3
    immutable(tmp_path/'hybrid-authorizations'/(child['id']+'.json'),canonical({**child['config'],'config_sha256':digest(canonical(child['config'])),'expires':time.time()+500}))
    monkeypatch.setattr(MaterialImage,'submit',lambda *a:pytest.fail('No image POST'))
    Worker(s).tick();r=s.get(child['id'])
    assert r['phase']=='extracting',r.get('stop_reason')
    assert r['attempt']==1 and r['image_count']==3
    assert (tmp_path/'hybrid'/r['id']/'historical-crop-decision-1.json').exists()
    assert not (tmp_path/'hybrid'/r['id']/'crop-decision-1.json').exists()
    claim=s.claim();auth={**r['config'],'config_sha256':digest(canonical(r['config'])),'expires':time.time()+500}
    call=s.reserve_call(claim,'extraction-1',{'fresh':True},100,auth)
    s.receipt(call['id'],{'test':'known'})
    assert s.get(r['id'])['call_count']==9
    with pytest.raises(ValueError):s.reserve_call(claim,'image-3',{'bad':True},100,auth)
    s.save(claim,phase='needs_attention');s.release(claim)
    assert s.get(p['id'])==old

@pytest.mark.parametrize('bad',['source','request','decision','binding'])
def test_archived_binding_detects_drift(tmp_path,monkeypatch,bad):
    from hybrid_reassessment import validated_archive
    from artifacts import canonical
    s,p=archived_parent(tmp_path,monkeypatch)
    proof,_,_=validated_archive(s,parent_id=p['id'])
    d=tmp_path/'hybrid'/p['id']
    if bad=='source':(d/'source-1.png').write_bytes(b'changed')
    if bad=='request':(d/'image-request-1.json').write_bytes(b'{}')
    if bad=='decision':(d/'crop-decision-1.json').write_bytes(b'{}')
    if bad=='binding':proof['selected']['source_sha256']='b'*64
    with pytest.raises((ValueError,OSError)):validated_archive(s,proof)
