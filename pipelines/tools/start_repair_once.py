"""ONE authorized live image-to-image material repair. Never run as a regression test."""
import os,sys,json,time,shlex
from pathlib import Path
import httpx
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from artifacts import canonical,digest
from hybrid_worker import default_store,immutable
from hybrid_reassessment_repair import validated_repair
from hybrid_models import OpenRouter,MaterialImage
from hybrid_source_recovery import TOKEN_POLICY
from billing_settlement import totals
out=ROOT/'evidence/hybrid-reassessment-repair';out.mkdir(exist_ok=True)
if (out/'new-run.json').exists():raise SystemExit('Already launched; no duplicate child')
for line in Path('/root/.config/layout-terrain-hybrid/environment').read_text().splitlines():
    if line.strip() and not line.lstrip().startswith('#'):
        key,value=line.split('=',1)
        if key in ['OPENROUTER_API_KEY','WAVESPEED_API_KEY']:os.environ[key]=shlex.split(value)[0]
s=default_store();pid='b9a94348e6404358b353d3b3c5fd5f24'
p,plan,cfg=validated_repair(s,parent_id=pid)
assert set(p['correction']['failed_materials'])=={'square'} and p['correction']['excluded'] and p['correction']['deferred']
assert (p['inherited_calls'],p['inherited_images'])==(10,3) and p['inherited_calls']+4<=15 and p['inherited_images']+1<=4
with s.g.connect() as db:
    before={table:[dict(x) for x in db.execute('SELECT * FROM '+table+' ORDER BY rowid')] for table in ['jobs','reviews','hybrid_runs','hybrid_calls','hybrid_events','hybrid_liability_authorizations']}
    account=totals(db);unknown=[dict(x) for x in db.execute('SELECT * FROM hybrid_calls WHERE receipt IS NULL')]
assert account['effective_microusd']==12754880 and account['released_microusd']==0 and len(unknown)==2
assert not s.g.policy['approved'] and s.g.policy['total_usd']=='20.00'
private=ROOT/'data/hybrid-reassessment-repair-before.json'
immutable(private,canonical(dict(tables=before,policy=s.g.policy)));private.chmod(0o600)
meta={key:OpenRouter(cfg[key+'_model']).preflight() for key in ['planner','reviewer']}
pimage=MaterialImage();schema=pimage.discover()
immutable(out/'live-metadata.json',canonical(meta));immutable(out/'image-schema.json',canonical(schema))
def reserve_cost(role,group,model_meta):
    o=OpenRouter(cfg[role+'_model'])
    return o.cost(model_meta,o.policy(cfg,group,model_meta)['max_tokens'])
call_reserve=reserve_cost('planner','extraction',meta['planner'])
review_reserve=reserve_cost('reviewer','review_sample',meta['reviewer'])
budget=3*max(call_reserve,review_reserve)+20000
assert budget+account['effective_microusd']<=20000000
approval=(ROOT/'HYBRID_REASSESSMENT_REPAIR_AUTHORIZATION.md').read_text()
directive='Owner explicit wish 2026-09-22: it must work and look good; richer coherent flat face-on stone grain for the stairs material (NO treads, NO risers, NO stair objects: the renderer builds all steps) and clearly finer flagstone pavers for the square material; preserve land, path and wall materials exactly.'
with httpx.Client(base_url='http://127.0.0.1:48765',timeout=180) as c:
    response=c.post('/api/hybrid-runs/'+pid+'/continue-repair',json=dict(budget_microusd=budget,max_seconds=7200,confirm_paid=True,approval_text=approval,owner_style_directive=directive),headers={'Idempotency-Key':'reassessment-repair-project20-calls4-images1-once-v1'})
    response.raise_for_status();r=response.json();immutable(out/'new-run.json',canonical(r))
    assert (r['call_count'],r['image_count'])==(10,3) and r['config']['max_images']==4 and r['config']['max_calls']==15
    assert r['config']['continuation']['kind']=='source_reassessment_repair' and r['config']['followup_call_limit']==4
    scope=dict(run_id=r['id'],config_sha256=r['config_sha256'],approval_text=approval,owner_style_directive=directive,
        parent_id=pid,amendment=r['config']['authorization_amendment'],project_cap_microusd=20000000,budget_microusd=budget,
        max_calls=15,max_images=4,new_images=1,followup_calls=4,expires=time.time()+7200,
        liabilities=[dict(call_id=x['id'],request_sha256=digest(x['request'].encode()),amount=x['amount']) for x in unknown])
    aid=s.acknowledge_liabilities(scope)
    with s.g.connect() as db:assert json.loads(db.execute('SELECT record FROM hybrid_liability_authorizations WHERE id=?',(aid,)).fetchone()[0])==scope
    auth={k:scope[k] for k in ['config_sha256','budget_microusd','max_calls','max_images','expires']};auth['liability_authorization']=aid
    immutable(ROOT/'data/hybrid-authorizations'/(r['id']+'.json'),canonical(auth));immutable(out/'authorization.json',canonical(scope))
    c.post('/api/hybrid-runs/'+r['id']+'/resume',json={}).raise_for_status()
    got=c.get('/api/hybrid-runs/'+r['id']);got.raise_for_status();immutable(out/'launch-readback.json',canonical(got.json()))
    print(json.dumps(dict(run_id=r['id'],phase=got.json()['phase'],inherited_calls=r['call_count'],inherited_images=r['image_count'],acknowledgment_id=aid,budget_microusd=budget,per_call=call_reserve,held_before=account['effective_microusd'])))
