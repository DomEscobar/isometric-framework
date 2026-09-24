import os,sys,json,time,shlex
from pathlib import Path
import httpx
ROOT=Path('/root/services/layout-terrain-pipeline');sys.path.insert(0,str(ROOT))
from artifacts import canonical,digest
from hybrid_worker import default_store,immutable
from hybrid_models import OpenRouter,MaterialImage
from hybrid_reference import reference_bytes
from hybrid_painted_terrain import prompt as flat_prompt,GUIDE_SIZE,make_guide,bind_source,validate_painted_source,cell_material
from hybrid_layout import compile_layout
from hybrid_render import render
from billing_settlement import totals
from decimal import Decimal,ROUND_CEILING
out=ROOT/'evidence/code-layout-flat-live-v2';out.mkdir(parents=True,exist_ok=True)
if (out/'new-run.json').exists():raise SystemExit('refusing duplicate launch')
for line in Path('/root/.config/layout-terrain-hybrid/environment').read_text().splitlines():
 if line.strip() and not line.lstrip().startswith('#'):
  k,v=line.split('=',1)
  if k in ('OPENROUTER_API_KEY','WAVESPEED_API_KEY'):os.environ[k]=shlex.split(v)[0]
s=default_store()
with s.g.connect() as db:
 before=totals(db);unknown=[dict(x) for x in db.execute('SELECT id,run,role,request,amount FROM hybrid_calls WHERE receipt IS NULL ORDER BY id')]
assert len(unknown)==2 and {x['id'] for x in unknown}=={'ff21a6ffd8500f6d9139eb1b71677078271381cd0f26f6291750a30d6deb696e','79320908cff658062cc43764eb539e5d706a5f747029a98e62c212ef5011357a'}
assert before['effective_microusd']==7462930 and before['settled_calls']==22
assert s.g.policy['approved'] and s.g.policy['max_attempts']==25 and s.g.policy['total_usd']=='20.00'
model='openai/gpt-6-luna-pro';planner=OpenRouter(model);meta=planner.preflight();review=OpenRouter(model);rmeta=review.preflight();image=MaterialImage();image.discover()
for m in (meta,rmeta):assert 'reasoning' in m.get('supported_parameters',[]) and 'medium' in m.get('reasoning',{}).get('supported_efforts',[])
# reserve conservative model completion cost for 32768 medium-token calls
planner_reserve=planner.cost(meta,32768);review_reserve=review.cost(rmeta,32768)
quote=image.quote(image.inputs('bounded price preflight',['https://example.invalid/layout.png','https://example.invalid/style.png']))
image_reserve=int((Decimal(str(quote['price']))*1_000_000).to_integral_value(rounding=ROUND_CEILING))
first_budget=planner_reserve+image_reserve+2*review_reserve
headroom=20_000_000-before['effective_microusd']
assert first_budget<=headroom and first_budget==714728
refsha='db1ecdcf7628fbfbaff8c9fae32a573b874d9a2ff76ea511bd62d90f2f7471d3';reforig='38ecd43956d121a06003a406f03d437ee985841f1245edc4fbd72a7711f5d10e'
ref,orig=reference_bytes(s.g.root,dict(reference_sha256=refsha,reference_original_sha256=reforig));assert digest(ref)==refsha and digest(orig)==reforig
description=('18x16-cell walkable isometric meadow: an open green field, a clear warm earth path from the left to one broad stone staircase on the right leading onto a raised paved plateau, open walkable corridor behind the plateau, two height levels, exactly one stairway. A small FLAT water surface patch at lower left with a sandy land shoreline; water and shore cells stay at the same base height, with NO basin, hollow, bowl or depression. No buildings, trees, flowers, props, shadows, characters, or text. Generate the code-defined geometry/layout first and stop at layout preview for human review; only after explicit freeze paint flat top-down pixel-art material inside the exact frozen grid. Renderer adds cliffs and staircase geometry.')
body=dict(mode='live',terrain_flow='painted_flat',description=description,constraints=dict(width=18,height=16,actor_width=.64),reference_sha256=refsha,reference_original_sha256=reforig,budget_microusd=headroom,max_images=15,max_calls=46,max_local_corrections=0,max_seconds=7200,auto_continue=False,confirm_paid=True,token_policy=dict(planner=dict(max_tokens=32768,reasoning_effort='medium'),review=dict(max_tokens=32768,reasoning_effort='medium')))
# Snapshot is not recopied: prior immutable snapshot is the pre-policy-change evidence.
snapshot=ROOT/'data/code-layout-flat-before.json';assert snapshot.exists()
with httpx.Client(base_url='http://127.0.0.1:48765',timeout=120) as c:
 pre=c.post('/api/hybrid/preflight');pre.raise_for_status();immutable(out/'preflight.json',canonical(pre.json()))
 response=c.post('/api/hybrid-runs',json=body,headers={'Idempotency-Key':'code-layout-painted-flat-v2-20260923'})
 if response.status_code!=201:raise RuntimeError(f'run start rejected {response.status_code}: {response.text}')
 r=response.json();assert r['config']['terrain_flow']=='painted_flat' and r['config']['max_calls']==46 and r['config']['max_images']==15
 immutable(out/'new-run.json',canonical(r))
 scope=dict(run_id=r['id'],config_sha256=r['config_sha256'],approval_text='Owner explicitly approved: “Ja, starte unter genau diesen Grenzen”. Water is explicitly flat with sandy shore and no depression. This run alone: maximum15 images, 46 calls, spend no more than current remaining shared USD12.537070; lifetime attempts 10+15=25; project ceiling USD20 unchanged. Two exact receipt-less historical liabilities remain fully reserved and untouched.',project_cap_microusd=20000000,budget_microusd=headroom,max_calls=46,max_images=15,expires=time.time()+7200,liabilities=[dict(call_id=x['id'],request_sha256=digest(x['request'].encode()),amount=x['amount']) for x in unknown])
 aid=s.acknowledge_liabilities(scope)
 with s.g.connect() as db:assert json.loads(db.execute('SELECT record FROM hybrid_liability_authorizations WHERE id=?',(aid,)).fetchone()[0])==scope
 auth={k:scope[k] for k in ['config_sha256','budget_microusd','max_calls','max_images','expires']};auth['liability_authorization']=aid
 immutable(ROOT/'data/hybrid-authorizations'/(r['id']+'.json'),canonical(auth));immutable(out/'authorization.json',canonical(scope))
 read=c.get('/api/hybrid-runs/'+r['id']);read.raise_for_status();immutable(out/'launch-readback.json',canonical(read.json()))
 print(json.dumps({'run_id':r['id'],'phase':read.json()['phase'],'max_images':15,'max_calls':46,'budget_microusd':headroom,'held_before':before['effective_microusd'],'unknown_holds_retained':len(unknown),'planner_reserve':planner_reserve,'review_reserve_each':review_reserve,'image_quote':image_reserve,'authorization_id':aid}))
