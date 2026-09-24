"""Authorized existing urban candidate only. prepare/preflight are free; run buys ONE review.
No generation POST, no policy changes, no retries. Exact inputs/outputs retained.
"""
import sys,io,json,base64
from pathlib import Path
from decimal import Decimal
from PIL import Image
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app import create_app
from fastapi.testclient import TestClient
from artifacts import canonical,digest
root=Path(__file__).resolve().parents[1];out=root/'evidence/strict-style';out.mkdir(exist_ok=True)
app=create_app();c=TestClient(app)
tid='f3bdc310f809cf7a6b95015cc16af343e337a192e1865432ac530eb2b02fa96a'
mode=sys.argv[1]

def ok(r):
    assert r.status_code<300,r.text[:500]
    return r.json()
if mode=='prepare':
    source=Path('/root/.hermes/cache/images/img_a6b8a9229c19.jpg').read_bytes()
    im=Image.open(io.BytesIO(source)).convert('RGB');stream=io.BytesIO();im.save(stream,format='PNG');raw=stream.getvalue()
    assert np.array_equal(np.array(im),np.array(Image.open(io.BytesIO(raw))))
    (out/'user-original.jpg').write_bytes(source);(out/'user-decoded.png').write_bytes(raw)
    ref=ok(c.post('/api/styles',json={'png_base64':base64.b64encode(raw).decode(),'role':'style_only'}))
    lineage={'original_sha256':digest(source),'normalized_sha256':digest(raw),'reference_id':ref['id'],'processing':'one JPEG RGB decode; lossless PNG encoding; identical decoded pixels; no resize','size':list(im.size)}
    (out/'user-reference-lineage.json').write_bytes(canonical(lineage))
    materials={
      'sidewalk':{'prompt':'Large calm warm cream/beige slabs, broad readable faces with sparse subtle seams; precise restrained curb edges. Not a dense uniform grid of tiny pavers.','reference_ids':[ref['id']]},
      'street':{'prompt':'Quiet warm-neutral gray asphalt, broad coherent flat clusters, sparse low-contrast wear. Avoid blue/cool cast and speckled gravel noise.','reference_ids':[ref['id']]},
      'planting':{'prompt':'Maintained trimmed lawn with coherent green clusters and controlled edges inside the planned planting footprint, not wild meadow tufts spreading over walkable paving.','reference_ids':[ref['id']]}}
    spec={'version':1,'prompt':'Friendly coherent isometric pixel-art urban ground. Match the reference ground material scale, warm quiet palette and legible pixel clusters, not its arrangement or upright props. Preserve canonical guide and all collision/clearance geometry exactly. Judge only ground; absent buses, people, trees, benches and buildings are intentionally out of scope.',
      'avoid':['dense tiny uniform noisy pavers','cool blue speckled asphalt','wild meadow grass tufts','foliage spilling into walkable clearance','mushy anti-aliased fine detail','copying the reference street layout','upright props baked into ground'],
      'materials':materials,'references':[{'reference_id':ref['id'],'role':'style_only','material':None,'crop':None},
        {'reference_id':ref['id'],'role':'material_only','material':'sidewalk','crop':[264,77,53,41]},
        {'reference_id':ref['id'],'role':'material_only','material':'street','crop':[236,25,68,48]},
        {'reference_id':ref['id'],'role':'material_only','material':'planting','crop':[283,270,55,39]}]}
    saved=ok(c.post('/api/style-specs',json=spec));(out/'style-spec-request.json').write_bytes(canonical(spec));(out/'style-spec.json').write_bytes(canonical(saved))
    ok(c.put('/api/style-presets/urban-calm-warm',json={'style_spec_id':saved['id']}))
    ev=ok(c.post('/api/terrain/'+tid+'/evaluations',json={'style_spec_id':saved['id'],'density':1}))
    (out/'evaluation-prepared.json').write_bytes(canonical(ev))
    print(json.dumps({'evaluation_id':ev['id'],'style_spec_id':saved['id'],'local_blockers':ev['binding']['local_blockers'],'evidence':ev['binding']['evidence']},indent=2))
elif mode=='preflight':
    meta=ok(c.post('/api/reviewer/preflight'))
    status=ok(c.get('/api/generation/status'))
    reserve=Decimal(meta['pricing']['prompt'])*meta['context_length']+Decimal(meta['pricing']['completion'])*4096
    assert Decimal(status['reserved_usd'])+reserve<=Decimal(status['total_budget_usd'])
    (out/'reviewer-live-metadata.json').write_bytes(canonical(meta))
    (out/'preflight.json').write_bytes(canonical({'free_auth_probe':'HTTP200','metadata_id':meta['id'],'metadata_sha256':digest(canonical(meta)),'reserve_usd':str(reserve),'accounting_before':status}))
    print(json.dumps({'model':meta['id'],'reserve_usd':str(reserve),'accounting':status},indent=2))
elif mode=='run':
    eid=json.loads((out/'evaluation-prepared.json').read_bytes())['id']
    assert (out/'preflight.json').exists(),'free check required before paid review'
    result=ok(c.post('/api/evaluations/'+eid+'/review',json={'confirm_paid':True}))
    readback=ok(c.get('/api/evaluations/'+eid));assert result==readback
    (out/'evaluation-reviewed.json').write_bytes(canonical(readback))
    status=ok(c.get('/api/generation/status'));(out/'accounting-after.json').write_bytes(canonical(status))
    print(json.dumps({'id':eid,'gate':readback['gate'],'usage':readback['result']['usage'],'actual_model':readback['result']['actual_model'],'accounting':status},indent=2))
else:raise ValueError('prepare|preflight|run')
