import os,sys,json,time,shlex
from pathlib import Path
from decimal import Decimal,ROUND_CEILING
import httpx
ROOT=Path('/root/services/layout-terrain-pipeline');sys.path.insert(0,str(ROOT))
from artifacts import canonical,digest
from hybrid_worker import default_store,immutable,runtime_version
from hybrid_models import OpenRouter,MaterialImage
from hybrid_reference import reference_bytes
from billing_settlement import totals
OUT=ROOT/'evidence/code-layout-flat-live-v3';OUT.mkdir(parents=True,exist_ok=True)
if (OUT/'new-run.json').exists():raise SystemExit('duplicate start refused')
for line in Path('/root/.config/layout-terrain-hybrid/environment').read_text().splitlines():
 if line.strip() and not line.lstrip().startswith('#'):
  k,v=line.split('=',1)
  if k in ('OPENROUTER_API_KEY','WAVESPEED_API_KEY'):os.environ[k]=shlex.split(v)[0]
store=default_store()
with store.g.connect() as db:
 before=totals(db)
 unknown=[dict(x) for x in db.execute('SELECT id,run,role,request,amount FROM hybrid_calls WHERE receipt IS NULL ORDER BY id')]
 expected={'ff21a6ffd8500f6d9139eb1b71677078271381cd0f26f6291750a30d6deb696e','79320908cff658062cc43764eb539e5d706a5f747029a98e62c212ef5011357a'}
 assert {x['id'] for x in unknown}==expected and len(unknown)==2
 assert before['effective_microusd']==7932082 and before['settled_calls']==22
 assert store.g.policy['approved'] and store.g.policy['max_attempts']==25 and store.g.policy['total_usd']=='20.00'
headroom=20_000_000-before['effective_microusd']
model='openai/gpt-6-luna-pro';planner=OpenRouter(model);pm=planner.preflight();reviewer=OpenRouter(model);rm=reviewer.preflight();image=MaterialImage();image.discover()
for m in (pm,rm):assert 'reasoning' in m.get('supported_parameters',[]) and 'medium' in m.get('reasoning',{}).get('supported_efforts',[])
quote=image.quote(image.inputs('flat water bank pixel-art material preflight',['https://example.invalid/layout.png','https://example.invalid/style.png']))
reserve=planner.cost(pm,32768)+2*reviewer.cost(rm,32768)+int((Decimal(str(quote['price']))*1_000_000).to_integral_value(rounding=ROUND_CEILING))
assert reserve<=headroom
refsha='db1ecdcf7628fbfbaff8c9fae32a573b874d9a2ff76ea511bd62d90f2f7471d3';reforig='38ecd43956d121a06003a406f03d437ee985841f1245edc4fbd72a7711f5d10e'
ref,orig=reference_bytes(store.g.root,dict(reference_sha256=refsha,reference_original_sha256=reforig));assert digest(ref)==refsha and digest(orig)==reforig
description=('18x16-cell walkable isometric meadow. Code-defined layout: compact 3x3-cell flat water patch in the lower-left, fully surrounded by one-cell-wide land shoreline; all water and shore at base height, NO basin, hollow, bowl or depression. A single-cell-wide warm earth path in one straight horizontal row from the left spawn, ending visibly at one broad but distinct stair strip on the right; do not let the path run beneath or disappear into the raised plateau. Exactly one clearly visible stairway connecting base to one raised level-8 paved plateau in the upper-right; clear open land corridor behind/alongside plateau. Keep the stair material category on the connecting transition cells. No additional water, paths, stairs, buildings, trees, flowers, props, shadows, characters, bridges or text. All cells/height changes and the layout are generated from this description first. Stop at code-generated layout preview for review; only after separate explicit freeze paint flat top-down pixel-art material inside the exact frozen cell grid. Renderer creates the stair geometry/cliffs deterministically.')
body=dict(mode='live',terrain_flow='painted_flat',description=description,constraints=dict(width=18,height=16,actor_width=.64),reference_sha256=refsha,reference_original_sha256=reforig,budget_microusd=headroom,max_images=15,max_calls=46,max_local_corrections=0,max_seconds=7200,auto_continue=False,confirm_paid=True,token_policy=dict(planner=dict(max_tokens=32768,reasoning_effort='medium'),review=dict(max_tokens=32768,reasoning_effort='medium')))
with httpx.Client(base_url='http://127.0.0.1:48765',timeout=120) as c:
 pre=c.post('/api/hybrid/preflight');pre.raise_for_status();immutable(OUT/'preflight.json',canonical(pre.json()))
 response=c.post('/api/hybrid-runs',json=body,headers={'Idempotency-Key':'code-layout-flat-offline-proposal-live-v3-20260923'})
 if response.status_code!=201:raise RuntimeError(f'run start rejected {response.status_code}: {response.text}')
 run=response.json();immutable(OUT/'new-run.json',canonical(run))
 scope=dict(run_id=run['id'],config_sha256=run['config_sha256'],approval_text='Owner explicitly authorized: “Ja, ein Planner-Aufruf unter diesen Limits”. Use one NEW live Planner call for the offline-tested corrected geometry intent (compact flat 3x3 water with one-cell land shore, one-cell-wide visible path, distinct stair strip and raised plateau). One planner only before layout review; no image or freeze at launch. Same water interpretation and no basin. This run alone: max15 image cycles, max46 paid calls, spend capped at the currently verified remaining shared budget of USD '+f'{headroom/1_000_000:.6f}'+', shared project ceiling USD20 unchanged, attempt cap25 unchanged; all known and unknown historical liabilities remain held, exact two receipt-less IDs below are acknowledged unresolved only.',project_cap_microusd=20_000_000,budget_microusd=headroom,max_calls=46,max_images=15,expires=time.time()+7200,liabilities=[dict(call_id=x['id'],request_sha256=digest(x['request'].encode()),amount=x['amount']) for x in unknown])
 aid=store.acknowledge_liabilities(scope)
 with store.g.connect() as db:
  saved=db.execute('SELECT record FROM hybrid_liability_authorizations WHERE id=?',(aid,)).fetchone()
  assert saved and json.loads(saved[0])==scope
 auth={k:scope[k] for k in ['config_sha256','budget_microusd','max_calls','max_images','expires']};auth['liability_authorization']=aid
 immutable(ROOT/'data/hybrid-authorizations'/(run['id']+'.json'),canonical(auth));immutable(OUT/'authorization.json',canonical(scope))
 read=c.get('/api/hybrid-runs/'+run['id']);read.raise_for_status();immutable(OUT/'launch-readback.json',canonical(read.json()))
 print(json.dumps({'run_id':run['id'],'phase':read.json()['phase'],'planner_reserve':planner.cost(pm,32768),'image_quote_microusd':int(Decimal(str(quote['price']))*1_000_000),'review_reserve_each':reviewer.cost(rm,32768),'first_paid_boundary_reserve':reserve,'remaining_project_headroom':headroom,'unresolved_liabilities':len(unknown),'authorization_id':aid,'runtime_version':runtime_version()}))
