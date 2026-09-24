"""Complete authorization for the already-created v3 child (no second start)."""
import os,sys,json,time,shlex
from pathlib import Path
import httpx
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from artifacts import canonical,digest
from hybrid_worker import default_store,immutable
from billing_settlement import totals
out=ROOT/'evidence/hybrid-complex-terrain-v3'
r=json.loads((out/'new-run.json').read_bytes())
assert r['config']['continuation'].get('plan_sha256') and r['config']['continuation'].get('parent_id')=='4fa30c195c8f41ae8e403cfe1ade0acd'
assert (r['call_count'],r['image_count'])==(1,0) and r['config']['max_images']==1 and r['config']['max_calls']==6
assert r['config']['token_policy']['planner']['max_tokens']==32768
s=default_store()
with s.g.connect() as db:
    account=totals(db);unknown=[dict(x) for x in db.execute('SELECT * FROM hybrid_calls WHERE receipt IS NULL')]
assert account['effective_microusd']==15448350 and len(unknown)==2
budget=r['config']['budget_microusd']
assert budget==2800000 and budget+account['effective_microusd']<=20000000
approval=(ROOT/'HYBRID_COMPLEX_TERRAIN_AUTHORIZATION.md').read_text()
scope=dict(run_id=r['id'],config_sha256=r['config_sha256'],approval_text=approval,amendment=None,
    parent_id='4fa30c195c8f41ae8e403cfe1ade0acd',project_cap_microusd=20000000,budget_microusd=budget,
    max_calls=6,max_images=1,new_images=1,reused_planner_call_id=r['config']['continuation']['call_id'],
    settled_calls=2,expires=time.time()+7200,
    liabilities=[dict(call_id=x['id'],request_sha256=digest(x['request'].encode()),amount=x['amount']) for x in unknown])
aid=s.acknowledge_liabilities(scope)
with s.g.connect() as db:assert json.loads(db.execute('SELECT record FROM hybrid_liability_authorizations WHERE id=?',(aid,)).fetchone()[0])==scope
auth={k:scope[k] for k in ['config_sha256','budget_microusd','max_calls','max_images','expires']};auth['liability_authorization']=aid
immutable(ROOT/'data/hybrid-authorizations'/(r['id']+'.json'),canonical(auth));immutable(out/'authorization.json',canonical(scope))
with httpx.Client(base_url='http://127.0.0.1:48765',timeout=120) as c:
    c.post('/api/hybrid-runs/'+r['id']+'/resume',json={}).raise_for_status()
    got=c.get('/api/hybrid-runs/'+r['id']);got.raise_for_status();immutable(out/'launch-readback.json',canonical(got.json()))
    print(json.dumps(dict(run_id=r['id'],phase=got.json()['phase'],acknowledgment_id=aid,reused_planner=r['config']['continuation']['call_id'],held_effective_before=account['effective_microusd'])))
