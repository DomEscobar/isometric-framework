"""ONE authorized receipt-bound planner continuation (v3: reuses the v2 plan, buys no planner)."""
import os,sys,json,time,shlex
from pathlib import Path
import httpx
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from artifacts import canonical,digest
from hybrid_worker import default_store,immutable
from hybrid_recovery import validated_parent,normalize_material_plan
from billing_settlement import totals
out=ROOT/'evidence/hybrid-complex-terrain-v3';out.mkdir(exist_ok=True)
if (out/'new-run.json').exists():raise SystemExit('Already launched; no duplicate child')
for line in Path('/root/.config/layout-terrain-hybrid/environment').read_text().splitlines():
    if line.strip() and not line.lstrip().startswith('#'):
        key,value=line.split('=',1)
        if key in ['OPENROUTER_API_KEY','WAVESPEED_API_KEY']:os.environ[key]=shlex.split(value)[0]
s=default_store();pid='4fa30c195c8f41ae8e403cfe1ade0acd'
proof,plan,cfg=validated_parent(s,parent_id=pid)
# The retained plan must be complete and only fail on the documented 'walls' alias.
from hybrid_layout import compile_layout
w=compile_layout(plan['layout'])
required={c for row in w['cells'] for c in row}|{'wall'}
normalized=normalize_material_plan(plan['material_plan'],required)
assert set(normalized['materials'])==required
assert plan['layout']['width']==24 and plan['layout']['height']==20 and 16 in {z for row in w['heights'] for z in row}
assert proof['inherited_calls']==1 and proof['inherited_images']==0
with s.g.connect() as db:
    before={table:[dict(x) for x in db.execute('SELECT * FROM '+table+' ORDER BY rowid')] for table in ['jobs','reviews','hybrid_runs','hybrid_calls','hybrid_events','hybrid_liability_authorizations','billing_settlements']}
    account=totals(db);unknown=[dict(x) for x in db.execute('SELECT * FROM hybrid_calls WHERE receipt IS NULL')]
assert account['effective_microusd']==15448350 and account['released_microusd']==1771930 and account['settled_calls']==2
assert len(unknown)==2 and not s.g.policy['approved'] and s.g.policy['total_usd']=='20.00'
private=ROOT/'data/hybrid-complex-terrain-v3-before.json'
immutable(private,canonical(dict(tables=before,policy=s.g.policy)));private.chmod(0o600)
budget=2800000
assert budget+account['effective_microusd']<=20000000
approval=(ROOT/'HYBRID_COMPLEX_TERRAIN_AUTHORIZATION.md').read_text()
with httpx.Client(base_url='http://127.0.0.1:48765',timeout=180) as c:
    response=c.post('/api/hybrid-runs/'+pid+'/continue',json=dict(budget_microusd=budget,max_seconds=7200,confirm_paid=True),headers={'Idempotency-Key':'complex-terrain-receipt-continuation-once-v3'})
    response.raise_for_status();r=response.json();immutable(out/'new-run.json',canonical(r))
    assert (r['call_count'],r['image_count'])==(1,0) and r['config']['max_images']==1 and r['config']['max_calls']==6
    assert r['config']['continuation']['kind']=='source' or r['config']['continuation'].get('plan_sha256')
    assert r['config']['token_policy']['planner']['max_tokens']==32768
    scope=dict(run_id=r['id'],config_sha256=r['config_sha256'],approval_text=approval,amendment=None,parent_id=pid,
        project_cap_microusd=20000000,budget_microusd=budget,max_calls=6,max_images=1,new_images=1,
        reused_planner_call_id=proof['call_id'],settled_calls=2,expires=time.time()+7200,
        liabilities=[dict(call_id=x['id'],request_sha256=digest(x['request'].encode()),amount=x['amount']) for x in unknown])
    aid=s.acknowledge_liabilities(scope)
    with s.g.connect() as db:assert json.loads(db.execute('SELECT record FROM hybrid_liability_authorizations WHERE id=?',(aid,)).fetchone()[0])==scope
    auth={k:scope[k] for k in ['config_sha256','budget_microusd','max_calls','max_images','expires']};auth['liability_authorization']=aid
    immutable(ROOT/'data/hybrid-authorizations'/(r['id']+'.json'),canonical(auth));immutable(out/'authorization.json',canonical(scope))
    c.post('/api/hybrid-runs/'+r['id']+'/resume',json={}).raise_for_status()
    got=c.get('/api/hybrid-runs/'+r['id']);got.raise_for_status();immutable(out/'launch-readback.json',canonical(got.json()))
    print(json.dumps(dict(run_id=r['id'],phase=got.json()['phase'],acknowledgment_id=aid,budget_microusd=budget,reused_planner=proof['call_id'],held_effective_before=account['effective_microusd'])))
