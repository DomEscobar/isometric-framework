"""Create one fresh, user-authorized EUR50-capped terrain recovery run."""
import os,sys,json,time,shlex
from pathlib import Path
from decimal import Decimal,ROUND_CEILING
import httpx
ROOT=Path('/root/services/layout-terrain-pipeline');sys.path.insert(0,str(ROOT))
from artifacts import canonical,digest
from hybrid_worker import default_store,runtime_version,immutable
from hybrid_models import OpenRouter,MaterialImage
from hybrid_reference import reference_bytes
from billing_settlement import totals
OUT=ROOT/'evidence/code-layout-flat-live-v7';OUT.mkdir(parents=True,exist_ok=True)
if (OUT/'new-run.json').exists():raise SystemExit('Fresh-run artifact already exists; do not duplicate')
for line in Path('/root/.config/layout-terrain-hybrid/environment').read_text().splitlines():
 if line.strip() and not line.lstrip().startswith('#'):
  k,v=line.split('=',1)
  if k in ('OPENROUTER_API_KEY','WAVESPEED_API_KEY'):os.environ[k]=shlex.split(v)[0]
cap=json.loads((OUT/'authorization.json').read_bytes());store=default_store()
assert cap['project_cap_microusd']==57_315_000 and cap['max_calls']==46 and cap['max_images']==15
with store.g.connect() as db:
 before=totals(db)
 unknown=[dict(x) for x in db.execute('SELECT id,run,role,request,amount FROM hybrid_calls WHERE receipt IS NULL ORDER BY id')]
 expected={'ff21a6ffd8500f6d9139eb1b71677078271381cd0f26f6291750a30d6deb696e','79320908cff658062cc43764eb539e5d706a5f747029a98e62c212ef5011357a'}
 assert {x['id'] for x in unknown}==expected and len(unknown)==2
 assert before['effective_microusd']==7_932_082 and before['settled_calls']==22
assert store.g.policy['approved'] and store.g.policy['total_usd']=='57.315' and store.g.policy['max_attempts']==25
headroom=cap['project_cap_microusd']-before['effective_microusd']
assert headroom==cap['budget_microusd']==49_382_918
planner=OpenRouter('openai/gpt-6-luna-pro');pm=planner.preflight()
reviewer=OpenRouter('google/gemini-3.8-flash');rm=reviewer.preflight()
assert pm['id']!=rm['id'] and 'image' in rm.get('architecture',{}).get('input_modalities',[])
assert 'structured_outputs' in pm.get('supported_parameters',[]) and 'structured_outputs' in rm.get('supported_parameters',[])
image=MaterialImage();image.discover();quote=image.quote(image.inputs('flat terrain style input preflight',['https://example.invalid/layout.png','https://example.invalid/style.png']))
assert quote.get('currency')=='USD'
planner_reserve=planner.cost(pm,32768);reviewer_reserve=reviewer.cost(rm,32768)
image_reserve=int((Decimal(str(quote['price']))*1_000_000).to_integral_value(rounding=ROUND_CEILING))
assert planner_reserve+reviewer_reserve<=headroom
refsha='db1ecdcf7628fbfbaff8c9fae32a573b874d9a2ff76ea511bd62d90f2f7471d3';reforig='38ecd43956d121a06003a406f03d437ee985841f1245edc4fbd72a7711f5d10e'
ref,orig=reference_bytes(store.g.root,dict(reference_sha256=refsha,reference_original_sha256=reforig));assert digest(ref)==refsha and digest(orig)==reforig
description=('18x16-cell isometric meadow. Planner must design a compact 3x3-cell water patch at lower-left, with a one-cell land shoreline, all at base height and no bowl/depression. One single-cell-wide warm earth path runs in one straight horizontal row from the left spawn to one visible broad stair strip at the right. The stairs connect the base to exactly one raised level-8 paved plateau in the upper-right. Keep a clear, traversable open corridor behind/alongside that plateau; the path must not pass underneath or disappear into it. No other water, paths, stairs, buildings, trees, flowers, props, shadows, characters, bridges, or text. Geometry comes from the structured grid; the renderer draws stairs and exposed cliffs deterministically. Material painting is flat top-down image-to-image and only after the exact grid has been accepted by the independent reviewer. Do not report preview/freeze/painting operations as unsupported physical geometry.')
body=dict(mode='live',terrain_flow='painted_flat',layout_contract='flat-pond-path-plateau/1',description=description,constraints=dict(width=18,height=16,actor_width=.64),reference_sha256=refsha,reference_original_sha256=reforig,budget_microusd=headroom,max_images=15,max_calls=46,max_local_corrections=2,max_seconds=7200,auto_continue=True,confirm_paid=True,layout_review_iterations=5,token_policy=dict(planner=dict(max_tokens=32768,reasoning_effort='medium'),layout_review=dict(max_tokens=32768,reasoning_effort='medium'),extraction=dict(max_tokens=32768,reasoning_effort='medium'),review=dict(max_tokens=32768,reasoning_effort='medium')))
with httpx.Client(base_url='http://127.0.0.1:48765',timeout=180) as c:
 pre=c.post('/api/hybrid/preflight');pre.raise_for_status();live=pre.json()
 assert live['planner_model']['model']=='openai/gpt-6-luna-pro' and live['reviewer_model']['model']=='google/gemini-3.8-flash'
 immutable(OUT/'preflight.json',canonical(live))
 resp=c.post('/api/hybrid-runs',json=body,headers={'Idempotency-Key':'eur50-flat-terrain-recovery-v7-20260923'})
 if resp.status_code!=201:raise RuntimeError(f'run create failed {resp.status_code}: {resp.text}')
 run=resp.json();immutable(OUT/'new-run.json',canonical(run))
 scope=dict(run_id=run['id'],config_sha256=run['config_sha256'],approval_text=cap['authorization_text_source']+'; '+cap['notes'],project_cap_microusd=cap['project_cap_microusd'],budget_microusd=headroom,max_calls=46,max_images=15,expires=time.time()+7200,liabilities=[dict(call_id=x['id'],request_sha256=digest(x['request'].encode()),amount=x['amount']) for x in unknown])
 aid=store.acknowledge_liabilities(scope)
 with store.g.connect() as db:
  row=db.execute('SELECT record FROM hybrid_liability_authorizations WHERE id=?',(aid,)).fetchone();assert row and json.loads(row[0])==scope
 auth={k:scope[k] for k in ['config_sha256','budget_microusd','max_calls','max_images','expires']};auth['liability_authorization']=aid
 immutable(ROOT/'data/hybrid-authorizations'/(run['id']+'.json'),canonical(auth));immutable(OUT/'run-authorization.json',canonical(scope))
 c.post('/api/hybrid-runs/'+run['id']+'/resume').raise_for_status()
 read=c.get('/api/hybrid-runs/'+run['id']);read.raise_for_status();immutable(OUT/'launch-readback.json',canonical(read.json()))
 assert read.json()['config_sha256']==run['config_sha256']
 print(json.dumps(dict(run_id=run['id'],phase=read.json()['phase'],planner_model=pm['id'],reviewer_model=rm['id'],project_cap_microusd=cap['project_cap_microusd'],prior_held_microusd=before['effective_microusd'],run_budget_microusd=headroom,planner_reserve_microusd=planner_reserve,reviewer_reserve_microusd=reviewer_reserve,image_quote_microusd=image_reserve,unknown_holds_retained=len(unknown),authorization_id=aid,runtime_version=runtime_version())))
