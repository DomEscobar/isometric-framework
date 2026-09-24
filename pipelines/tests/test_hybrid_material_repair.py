import copy,json,time
import pytest
from artifacts import canonical,digest
from hybrid_models import validate_crops

def decision():
    return dict(source_sha256='a'*64,crops={k:dict(xywh=[0,0,16,16],source_pixels_per_unit=[16,16],verdict='fail' if k=='stairs' else 'pass',evidence_ids=['board'],observation='Architectural risers, not flat stone' if k=='stairs' else 'Clean flat material') for k in ['land','stairs']})

def test_concrete_material_failure_classified_without_accepting_crops():
    from hybrid_material_repair import material_defect
    raw=decision();before=copy.deepcopy(raw)
    correction=material_defect(raw,'a'*64,[32,32],{'land','stairs'})
    assert correction['failed_materials']=={'stairs':raw['crops']['stairs']}
    assert correction['preserve_materials']=={'land':raw['crops']['land']}
    assert raw==before
    with pytest.raises(ValueError):validate_crops(raw,'a'*64,[32,32],{'land','stairs'})

def failed_parent(tmp_path,monkeypatch):
    from test_hybrid_source_continuation import source_parent
    from hybrid_source_recovery import continue_source
    from hybrid_worker import Worker,immutable
    s,p=source_parent(tmp_path,monkeypatch)
    child=continue_source(s,p['id'],'extract-child',1900000,1800,'standing token approval')
    auth={**child['config'],'config_sha256':digest(canonical(child['config'])),'expires':time.time()+500}
    immutable(tmp_path/'hybrid-authorizations'/(child['id']+'.json'),canonical(auth))
    Worker(s).tick();r=s.claim();r=s.get(r['id']);sha=r['source_sha256']
    raw=decision();raw['source_sha256']=sha
    raw['crops']={k:copy.deepcopy(raw['crops']['stairs' if k=='stairs' else 'land']) for k in r['material_plan']['materials']}
    # Fixture geometry must actually have a failed material.
    name=next(iter(raw['crops']));raw['crops'][name]['verdict']='fail'
    req=dict(body={'model':'test/model'},inputs=[{'id':'board','sha256':sha}])
    call=s.reserve_call(r,'extraction-0',req,100,auth)
    s.receipt(call['id'],dict(id='complete-extraction',model='test/model',choices=[dict(finish_reason='stop',message={'content':json.dumps(raw)})]))
    immutable(tmp_path/'hybrid'/r['id']/'crop-decision-0.json',canonical(raw))
    s.save(r,phase='needs_attention');s.release(r)
    return s,r

def test_material_continuation_amends_not_resets_and_worker_starts_correction(tmp_path,monkeypatch):
    from hybrid_material_repair import continue_material,validated_material
    from hybrid_worker import Worker,immutable
    s,p=failed_parent(tmp_path,monkeypatch);old=s.get(p['id'])
    child=continue_material(s,p['id'],'repair-child',1900000,1800,'pipeline livefix standing authority')
    assert (child['call_count'],child['image_count'])==(4,1)
    assert (child['config']['max_calls'],child['config']['max_images'])==(12,3)
    assert child['config']['authorization_amendment']['previous_max_images']==1
    immutable(tmp_path/'hybrid-authorizations'/(child['id']+'.json'),canonical({**child['config'],'config_sha256':digest(canonical(child['config'])),'expires':time.time()+500}))
    Worker(s).tick();r=s.get(child['id'])
    assert r['phase']=='generating',r.get('stop_reason')
    assert r['attempt']==1 and r['previous_source']=='source-0.png'
    assert r['correction']['kind']=='material_source_defect/1'
    assert s.get(p['id'])==old
    validated_material(s,child['config']['continuation'])
    with pytest.raises(ValueError):continue_material(s,p['id'],'duplicate',1900000,1800,'pipeline livefix standing authority')
    (tmp_path/'hybrid'/p['id']/'crop-decision-0.json').write_bytes(b'{}')
    with pytest.raises(ValueError):validated_material(s,child['config']['continuation'])

def test_failed_extraction_worker_queues_changed_source_not_reextract(tmp_path,monkeypatch):
    from hybrid_worker import Worker,immutable
    from hybrid_material_repair import continue_material
    from hybrid_models import OpenRouter
    s,p=failed_parent(tmp_path,monkeypatch)
    child=continue_material(s,p['id'],'automatic',1900000,1800,'pipeline livefix standing authority')
    immutable(tmp_path/'hybrid-authorizations'/(child['id']+'.json'),canonical({**child['config'],'config_sha256':digest(canonical(child['config'])),'expires':time.time()+500}))
    Worker(s).tick();r=s.claim();d=tmp_path/'hybrid'/r['id']
    immutable(d/'source-1.png',(d/'source-0.png').read_bytes())
    s.save(r,phase='extracting');s.release(r)
    raw=json.loads((d/'crop-decision-0.json').read_bytes())
    monkeypatch.setattr(OpenRouter,'call',lambda *a:raw)
    Worker(s).tick();r=s.get(r['id'])
    assert r['phase']=='generating',r.get('stop_reason')
    assert r['attempt']==2 and r['previous_source']=='source-1.png'
    assert (d/'source-correction-2.json').exists()

def test_material_edit_prompt_binds_actual_role_images_and_only_failed_material():
    from hybrid_material_repair import image_request
    raw=decision();correction=__import__('hybrid_material_repair').material_defect(raw,'a'*64,[32,32],{'land','stairs'})
    prompt,images=image_request({'materials':{'land':'grass','stairs':'stone'},'intent':'frozen'},b'ref',b'guide',b'board',correction)
    assert list(images)==['reference','guide','correction_target']
    assert images['correction_target']==b'board'
    for text in ['FLAT FACE-ON STONE TEXTURE','NO risers','NO tread arrangement','stairs','land','Image3','not guaranteed']:
        assert text in prompt

def test_material_api_continuation_and_safe_source_readback(tmp_path,monkeypatch):
    from fastapi.testclient import TestClient
    from hybrid_api import create_app
    from hybrid_worker import Worker,immutable
    s,p=failed_parent(tmp_path,monkeypatch);c=TestClient(create_app(s))
    response=c.post('/api/hybrid-runs/'+p['id']+'/continue-material',json=dict(budget_microusd=1900000,max_seconds=1800,confirm_paid=True,approval_text='pipeline livefix standing authority'),headers={'Idempotency-Key':'api-material'})
    assert response.status_code==201,response.text
    r=response.json()
    immutable(tmp_path/'hybrid-authorizations'/(r['id']+'.json'),canonical({**r['config'],'config_sha256':digest(canonical(r['config'])),'expires':time.time()+500}))
    Worker(s).tick()
    got=c.get('/api/hybrid-runs/'+r['id']+'/sources/source-0.png')
    assert got.status_code==200
    assert got.content==(tmp_path/'hybrid'/p['id']/'source-0.png').read_bytes()
    page=c.get('/').text
    assert 'source-before' in page and 'source-after' in page and 'correction_kind' in page

def test_actual_absent_risers_failure_is_contract_conflict_not_source_defect():
    from hybrid_material_repair import material_defect
    raw=decision()
    raw['crops']['stairs']['observation']='Flat speckled grey concrete or stone slab without any cut stone stair treads or visible risers.'
    with pytest.raises(ValueError,match='contract conflict'):
        material_defect(raw,'a'*64,[32,32],{'land','stairs'})

def test_extractor_explicitly_separates_scene_architecture_from_material():
    from hybrid_material_repair import extraction_prompt
    prompt=extraction_prompt({'materials':{'stairs':'Broad cut stone stair treads with visible risers'}},'a'*64,[32,32],{'stairs'})
    assert 'Absence of treads and risers is REQUIRED' in prompt
    assert 'planner architecture describes the FINAL SCENE' in prompt
    assert 'never a reason to FAIL' in prompt

@pytest.mark.parametrize('bad',['citation','uncertain','source','bounds','json'])
def test_invalid_or_uncertain_is_not_generation_evidence(bad):
    from hybrid_material_repair import material_defect
    raw=decision()
    if bad=='citation':raw['crops']['land']['evidence_ids']=['reference']
    if bad=='uncertain':raw['crops']['stairs']['verdict']='uncertain'
    if bad=='source':raw['source_sha256']='b'*64
    if bad=='bounds':raw['crops']['stairs']['xywh']=[999,0,16,16]
    if bad=='json':raw['extra']='injected'
    with pytest.raises(ValueError):material_defect(raw,'a'*64,[32,32],{'land','stairs'})
