"""Create one fresh, EUR50-capped terrain run on the fixed strict-schema transport."""
import json,time,sys
from pathlib import Path
import httpx
ROOT=Path('/root/services/layout-terrain-pipeline');sys.path.insert(0,str(ROOT))
from hybrid_worker import default_store,runtime_version,immutable
from hybrid_reference import reference_bytes
from artifacts import canonical,digest
from billing_settlement import totals
OUT=ROOT/'evidence/code-layout-flat-live-v11';OUT.mkdir(parents=True,exist_ok=True)
if (OUT/'new-run.json').exists():raise SystemExit('already started')
parent_id='1f0a49ca0e7c4d17bffa54d72604cc60'
EXPECTED={'ff21a6ffd8500f6d9139eb1b71677078271381cd0f26f6291750a30d6deb696e','79320908cff658062cc43764eb539e5d706a5f747029a98e62c212ef5011357a','adb5ac81c797ecc1bdd553a59c37343e5869b674d123dbbb49e36b1a88db4d71'}
store=default_store()
with store.g.connect() as db:
    before=totals(db);unknown=[dict(x) for x in db.execute('select id,run,role,request,amount from hybrid_calls where receipt is null order by id')]
assert {u['id'] for u in unknown}==EXPECTED,'unbekannte Hold-Menge verändert'
parent=store.get(parent_id);assert parent['phase']=='needs_attention' and parent['image_count']==0 and parent['call_count']==1
cfg=parent['config'];assert cfg['layout_contract']=='flat-pond-path-plateau/1'
body={k:cfg[k] for k in ['mode','description','reference_sha256','reference_original_sha256','constraints','max_images','max_local_corrections','max_calls','max_seconds','auto_continue','terrain_flow','confirm_paid','token_policy','layout_review_iterations','layout_contract']}
budget=57_315_000-before['effective_microusd'];assert budget>0
body.update(budget_microusd=budget,max_calls=36,confirm_paid=True)
ref,orig=reference_bytes(store.g.root,body);assert digest(ref)==body['reference_sha256'] and digest(orig)==body['reference_original_sha256']
with httpx.Client(base_url='http://127.0.0.1:48765',timeout=120) as c:
    live=c.post('/api/hybrid/preflight');live.raise_for_status();immutable(OUT/'preflight.json',canonical(live.json()))
    resp=c.post('/api/hybrid-runs',json=body,headers={'Idempotency-Key':'eur50-flat-terrain-recovery-v11-20260923'})
    if resp.status_code!=201:raise SystemExit(f'create failed {resp.status_code}: {resp.text}')
    run=resp.json();assert run['config']['runtime_version']==runtime_version();assert run['config']['layout_contract']=='flat-pond-path-plateau/1';immutable(OUT/'new-run.json',canonical(run))
    scope=dict(run_id=run['id'],config_sha256=run['config_sha256'],approval_text='Same explicit EUR50 cap and quality recovery authorization; fresh run after strict-schema map/const fixes and pre-submit schema lint.',project_cap_microusd=57_315_000,budget_microusd=budget,max_calls=36,max_images=15,expires=time.time()+7200,liabilities=[dict(call_id=u['id'],request_sha256=digest(u['request'].encode()),amount=u['amount']) for u in unknown])
    aid=store.acknowledge_liabilities(scope)
    with store.g.connect() as db:assert json.loads(db.execute('select record from hybrid_liability_authorizations where id=?',(aid,)).fetchone()[0])==scope
    auth={k:scope[k] for k in ['config_sha256','budget_microusd','max_calls','max_images','expires']};auth['liability_authorization']=aid
    immutable(ROOT/'data/hybrid-authorizations'/(run['id']+'.json'),canonical(auth));immutable(OUT/'run-authorization.json',canonical(scope))
    c.post('/api/hybrid-runs/'+run['id']+'/resume').raise_for_status();rb=c.get('/api/hybrid-runs/'+run['id']);rb.raise_for_status();immutable(OUT/'launch-readback.json',canonical(rb.json()))
    print(json.dumps({'run_id':run['id'],'phase':rb.json()['phase'],'run_budget':budget,'effective_before':before['effective_microusd'],'unknown_holds':len(unknown),'authorization_id':aid,'runtime':runtime_version()}))
