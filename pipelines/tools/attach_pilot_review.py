"""Attach auditable evidence to the exact candidate; no approval/geometry mutation."""
from pathlib import Path
import json,io
import numpy as np
from PIL import Image
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from artifacts import canonical,digest
out=Path('evidence/paid-pilot');record=json.loads((out/'registered-candidate.json').read_bytes());v=json.loads((out/'layout-response.json').read_bytes());p=v['layout']['projection'];reg=record['processing_registration']
s=reg['scale'];tx,ty=reg['translation'];proxy=np.array(Image.open(out/'water-proxy.png').transform(tuple(p['image_size']),Image.Transform.AFFINE,(1/s,0,-tx/s,0,1/s,-ty/s),resample=Image.Resampling.NEAREST))>0
y,x=np.where(proxy);matrix=np.array([p['column_basis_px'],p['row_basis_px']]).T
world=np.linalg.solve(matrix,np.stack([x+.5-p['origin_px'][0],y+.5-p['origin_px'][1]]));cols=np.floor(world[0]).astype(int);rows=np.floor(world[1]).astype(int)
half=v['layout']['actor_width']/2;inside=(abs(world[0]-(cols+.5))<=half)&(abs(world[1]-(rows+.5))<=half)
graph=v['validation']['graph'];hit=[(int(c),int(r)) for c,r,ok in zip(cols,rows,inside) if ok and f'{c},{r}' in graph]
local=json.loads((out/'registered-local-checks.json').read_bytes());local['proxy_pixels_inside_any_safe_stationary_actor_square']=len(hit);local['safe_actor_cells_with_proxy_overlap']=sorted([list(c) for c in set(hit)]);(out/'registered-local-checks.json').write_bytes(canonical(local))
review=json.loads((out/'model-review.json').read_bytes());response=review['response'];assert response['model']=='google/gemini-3.8-flash' and response['choices'][0]['finish_reason']=='stop'
req=json.loads(Path('data/reviews/paid-pilot-02-verified-auth/request.json').read_bytes())
evidence=dict(candidate_id=record['id'],layout_revision=record['layout_revision'],source_sha256=record['source_sha256'],guide_sha256=record['guide_sha256'],
 status='needs_attention',production_approved=False,technical_verdict='pass',semantic_verdict='needs_attention',visual_verdict='secondary_pass_parent_pending',
 reviewed_terrain_sha256=digest((out/'registered.png').read_bytes()),reviewed_density=1,reviewed_dimensions=[768,408],
 model_review=review,review_request_text=[c['text'] for c in req['messages'][0]['content'] if c['type']=='text'],review_model_metadata=json.loads((out/'reviewer-live-metadata.json').read_bytes()),local_checks=local,
 worker_visual_review={'model':'gpt-6-astra subagent','observations':['Entire diamond framed at true 768x408 canvas/CSS size, DPR1; no anisotropic scaling.','Main ochre path reads continuously; petrol backdrop, moss greens and warm leaf accents follow style source.','Small cyan shoreline deviations remain; proxy is not a semantic classifier. Model secondary pass is not parent approval.','Clumps are painted ground decoration, not separate props. House/tree reservations and stick actor remain technical placeholders.','Clean view hides diagnostic overlays only; collision/objects unchanged.'], 'images':{n:digest((out/n).read_bytes()) for n in ['original.png','registered.png','guide-vs-registered.png','browser/play-scale-clean.png','browser/canvas-native.png']}},
 browser_verification=json.loads((out/'browser/browser-report.json').read_bytes()),review_run_id='paid-pilot-02-verified-auth',remaining=['Parent/main-session Astra and user visual approval missing','337 blue-proxy pixels outside planned water require shoreline judgement; no collision changes permitted','No generated props, production actor, engine adapter or public deployment'])
evidence['id']=digest(canonical(evidence));target=Path('data/terrain')/record['id']/'review.json'
with target.open('xb') as f:f.write(canonical(evidence))
(out/'attached-review.json').write_bytes(canonical(evidence));print(json.dumps({'review_id':evidence['id'],'local':local},indent=2))
