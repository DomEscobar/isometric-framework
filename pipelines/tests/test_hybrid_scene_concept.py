import json,time
import pytest
from artifacts import canonical,digest

def test_scene_concept_flow_paints_concepts_then_board(tmp_path,monkeypatch):
    from test_hybrid_directive_repair import ok_parent
    from hybrid_directive_repair import continue_directive
    from hybrid_worker import Worker,immutable
    s,p=ok_parent(tmp_path,monkeypatch)
    child=continue_directive(s,p['id'],'concept-child',5_000_000,3600,'bounded scene concept authority','paint beautiful full scene then derive flat board',flow='scene_concept')
    assert child['config']['max_images']==p['image_count']+2 and child['config']['followup_call_limit']==5
    immutable(tmp_path/'hybrid-authorizations'/(child['id']+'.json'),canonical({**child['config'],'config_sha256':digest(canonical(child['config'])),'expires':time.time()+500}))
    seen=[]
    from hybrid_models import MaterialImage
    orig=MaterialImage.submit
    monkeypatch.setattr(MaterialImage,'submit',lambda self,body:(seen.append(body) or {'id':'mock-img-'+str(len(seen))}))
    for _ in range(8):
        Worker(s).tick()
        if s.get(child['id'])['phase'] in ['succeeded','needs_attention']:break
    r=s.get(child['id'])
    d=tmp_path/'hybrid'/r['id']
    assert (d/f"concept-{r['attempt']}.png").exists(), 'scene concept artifact missing: '+str(r.get('stop_reason'))
    assert len(seen)==2, 'exactly two image calls: concept then board'
    assert 'scene' in json.dumps(seen[0])[:2000] or 'Scene' in json.dumps(seen[0])[:2000]
    assert r['image_count']==p['image_count']+2
