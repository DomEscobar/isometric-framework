import base64,copy,io,json,time
import pytest
from PIL import Image

def review():
    def c(verdict,ids,obs,fix=''):return dict(verdict=verdict,evidence_ids=ids,observation=obs,correction=fix)
    return dict(criteria={
        'layout_fidelity':c('fail',['final','guide'],'Guide zone positions do not match the rendered strip placement.'),
        'materials':c('fail',['final','reference','crop-stairs'],'Flat speckled grey surface with no cut stone stair treads, step risers, or nosing details.'),
        'scale':c('fail',['final','reference','crop-square'],'Square flagstone pavers oversized relative to the actor.','Use finer pavers.'),
        'pixel_style':c('pass',['final','reference'],'Matches the pixel aesthetic.'),
        'walkable_clearance':c('pass',['final','guide'],'Walkable ground clear.'),
        'repetition':c('pass',['final','reference'],'No harsh tiling lines.'),
        'lighting':c('pass',['final','reference'],'Consistent illumination.')})

def test_review_correction_targets_only_actionable_material_findings():
    from hybrid_reassessment_repair import review_correction
    evidence={'final','guide','reference','crop-land','crop-path','crop-square','crop-stairs','crop-wall'}
    raw=review();before=copy.deepcopy(raw)
    correction=review_correction(raw,evidence,'a'*64)
    assert list(correction['failed_materials'])==['square']
    assert correction['failed_materials']['square']['criterion']=='scale'
    assert correction['preserve_materials']==['land','path','stairs','wall']
    assert correction['excluded'][0]['criterion']=='materials' and 'conflict' in correction['excluded'][0]['reason']
    assert correction['deferred'][0]['criterion']=='layout_fidelity'
    assert 'owner_style_directive' not in correction
    assert raw==before

@pytest.mark.parametrize('bad',['conflict_only','geometry_only','citation','uncertain'])
def test_review_correction_fails_closed(bad):
    from hybrid_reassessment_repair import review_correction
    raw=review();evidence={'final','guide','reference','crop-square','crop-stairs'}
    if bad=='conflict_only':raw['criteria']['scale']['verdict']='pass'
    if bad=='geometry_only':
        raw['criteria']['scale']['verdict']='pass';raw['criteria']['materials']['verdict']='pass'
    if bad=='citation':raw['criteria']['scale']['evidence_ids']=['final','reference']
    if bad=='uncertain':raw['criteria']['scale']['verdict']='uncertain'
    with pytest.raises(ValueError):review_correction(raw,evidence,'a'*64)

def repair_parent(tmp_path,monkeypatch):
    from test_hybrid_reassessment import archived_parent
    from hybrid_reassessment import continue_archive
    from hybrid_worker import Worker,immutable,ACTOR
    from hybrid_models import validate_crops,review_gate
    from artifacts import canonical,digest
    s,p=archived_parent(tmp_path,monkeypatch)
    child=continue_archive(s,p['id'],'reassess-child',2727936,3600,'pipeline reassessment authority')
    immutable(tmp_path/'hybrid-authorizations'/(child['id']+'.json'),canonical({**child['config'],'config_sha256':digest(canonical(child['config'])),'expires':time.time()+500}))
    Worker(s).tick();r=s.claim();r=s.get(r['id']);d=tmp_path/'hybrid'/r['id']
    auth={**r['config'],'config_sha256':digest(canonical(r['config'])),'expires':time.time()+500}
    reference=b'ref';source=(d/'source-1.png').read_bytes();sha=digest(source)
    # Simulated fresh full-board extraction: all pass (the corrected extractor).
    materials=sorted(r['material_plan']['materials'])
    raw=dict(source_sha256=sha,crops={m:dict(xywh=[0,0,16,16],source_pixels_per_unit=[16,16],verdict='pass',evidence_ids=['board'],observation='Clean flat material interior') for m in materials})
    images={'actor':(ACTOR/'character.png').read_bytes(),'board':source,'reference':reference}
    content=[]
    for k,v in sorted(images.items()):content.extend([dict(type='text',text='evidence_id='+k),dict(type='image_url',image_url={'url':'data:image/png;base64,'+base64.b64encode(v).decode()})])
    req=dict(body=dict(model='test/model',messages=[{},dict(content=content)]),inputs=[dict(id=k,sha256=digest(v)) for k,v in sorted(images.items())])
    call=s.reserve_call(r,'extraction-1',req,100,auth)
    s.receipt(call['id'],dict(id='extract-fresh',model='test/model',choices=[dict(finish_reason='stop',message={'content':json.dumps(raw)})]))
    immutable(d/'crop-decision-1.json',canonical(raw))
    binding=validate_crops(raw,sha,list(Image.open(io.BytesIO(source)).size),set(materials))
    s.save(r,phase='sampling',crop_binding=binding);s.release(r)
    # Real local sample build exercises the functional stair transition.
    Worker(s).tick();r=s.claim();r=s.get(r['id'])
    sd=d/r['sample_directory']
    images={'final':(sd/'scene.png').read_bytes(),'guide':(sd/'guide.png').read_bytes(),'reference':reference}
    for m in materials:images['crop-'+m]=(sd/(m+'-crop.png')).read_bytes()
    def crit(verdict,ids,obs,fix=''):return dict(verdict=verdict,evidence_ids=ids,observation=obs,correction=fix)
    conflict_target=materials[0];actionable_target=materials[-1]
    decision=dict(criteria={
        'layout_fidelity':crit('fail',['final','guide'],'Zone positions need renderer-side placement fixes.'),
        'materials':crit('fail',['final','reference','crop-'+conflict_target],'Flat speckled grey surface with no cut stone stair treads or step risers.'),
        'scale':crit('fail',['final','reference','crop-'+actionable_target],'Pavers oversized relative to the actor.','Use finer pavers.'),
        'pixel_style':crit('pass',['final','reference'],'Matches pixel aesthetic.'),
        'walkable_clearance':crit('pass',['final','guide'],'Walkable ground clear.'),
        'repetition':crit('pass',['final','reference'],'No harsh tiling lines.'),
        'lighting':crit('pass',['final','reference'],'Consistent illumination.')})
    req=dict(body=dict(model='test/model',messages=[{},dict(content=[dict(type='text',text='review')])]),inputs=[dict(id=k,sha256=digest(v)) for k,v in sorted(images.items())])
    call=s.reserve_call(r,'review_sample-1',req,100,auth)
    s.receipt(call['id'],dict(id='review-fresh',model='test/model',choices=[dict(finish_reason='stop',message={'content':json.dumps(decision)})]))
    immutable(d/'review_sample-1.json',canonical(decision))
    s.save(r,phase='needs_attention',gate=review_gate(decision,images),stop_reason='Fresh review rejected retained-source assembly')
    s.release(r)
    return s,s.get(r['id'])

def test_repair_continuation_buys_exactly_one_new_image_edit(tmp_path,monkeypatch):
    from hybrid_reassessment_repair import continue_repair,validated_repair
    from hybrid_worker import Worker,immutable
    from artifacts import canonical,digest
    s,p=repair_parent(tmp_path,monkeypatch);old=s.get(p['id'])
    child=continue_repair(s,p['id'],'repair-child',3000000,3600,'bounded repair authority','owner wants good-looking flat stone and finer pavers')
    assert (child['call_count'],child['image_count'])==(10,3)
    assert (child['config']['max_calls'],child['config']['max_images'])==(15,4)
    assert child['config']['followup_call_limit']==4 and child['config']['no_local_retries'] is True
    assert 'no_new_images' not in child['config']
    immutable(tmp_path/'hybrid-authorizations'/(child['id']+'.json'),canonical({**child['config'],'config_sha256':digest(canonical(child['config'])),'expires':time.time()+500}))
    Worker(s).tick();r=s.get(child['id'])
    assert r['phase']=='generating',r.get('stop_reason')
    assert r['attempt']==3 and r['previous_source']=='source-1.png' and r['image_count']==3
    assert r['correction']['kind']=='review_material_correction/1'
    assert r['correction']['owner_style_directive'].startswith('owner')
    assert s.get(p['id'])==old
    validated_repair(s,child['config']['continuation'])
    with pytest.raises(ValueError):continue_repair(s,p['id'],'duplicate',3000000,3600,'bounded repair authority','owner wants good-looking flat stone and finer pavers')

def test_repair_api_and_image_cap_bypass_fails(tmp_path,monkeypatch):
    from fastapi.testclient import TestClient
    from hybrid_api import create_app
    from hybrid_worker import immutable
    from artifacts import canonical,digest
    s,p=repair_parent(tmp_path,monkeypatch);c=TestClient(create_app(s))
    response=c.post('/api/hybrid-runs/'+p['id']+'/continue-repair',json=dict(budget_microusd=3000000,max_seconds=3600,confirm_paid=True,approval_text='bounded repair authority',owner_style_directive='owner wants good-looking flat stone and finer pavers'),headers={'Idempotency-Key':'api-repair'})
    assert response.status_code==201,response.text
    r=response.json()
    immutable(tmp_path/'hybrid-authorizations'/(r['id']+'.json'),canonical({**r['config'],'config_sha256':digest(canonical(r['config'])),'expires':time.time()+500}))
    claim=s.claim();auth={**r['config'],'config_sha256':digest(canonical(r['config'])),'expires':time.time()+500}
    # One image is authorized; a second one must fail closed at the ledger.
    s.reserve_call(claim,'image-3',{'attempt':3,'amount':100},100,auth)
    with pytest.raises(ValueError):s.reserve_call(claim,'image-4',{'attempt':4,'amount':100},100,auth)
    s.save(claim,phase='needs_attention');s.release(claim)

@pytest.mark.parametrize('bad',['review','source','request','directive'])
def test_validated_repair_detects_drift(tmp_path,monkeypatch,bad):
    from hybrid_reassessment_repair import continue_repair,validated_repair
    from hybrid_worker import immutable
    from artifacts import canonical,digest
    s,p=repair_parent(tmp_path,monkeypatch)
    child=continue_repair(s,p['id'],'drift-check',3000000,3600,'bounded repair authority','owner wants good-looking flat stone and finer pavers')
    immutable(tmp_path/'hybrid-authorizations'/(child['id']+'.json'),canonical({**child['config'],'config_sha256':digest(canonical(child['config'])),'expires':time.time()+500}))
    proof,_,_=validated_repair(s,child['config']['continuation'])
    d=tmp_path/'hybrid'/p['id']
    if bad=='review':(d/'review_sample-1.json').write_bytes(b'{}')
    if bad=='source':(d/'source-1.png').write_bytes(b'changed')
    if bad=='request':(d/'source-reassessment.json').write_bytes(b'{}')
    if bad=='directive':proof['correction']['preserve_materials']=['tampered']
    with pytest.raises((ValueError,OSError)):validated_repair(s,proof)
