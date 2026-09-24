"""ONE authorized live material continuation. Never run as a regression test."""
import os,sys,json,time,shlex
from pathlib import Path
import httpx
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from artifacts import canonical,digest
from hybrid_worker import default_store,immutable
from hybrid_material_repair import validated_material
from hybrid_models import OpenRouter,MaterialImage
from billing_settlement import totals
out=ROOT/'evidence/hybrid-material-repair';out.mkdir(exist_ok=True)
if (out/'new-run.json').exists():raise SystemExit('Already launched; no duplicate child')
for line in Path('/root/.config/layout-terrain-hybrid/environment').read_text().splitlines():
    if line.strip() and not line.lstrip().startswith('#'):
        key,value=line.split('=',1)
        if key in ['OPENROUTER_API_KEY','WAVESPEED_API_KEY']:os.environ[key]=shlex.split(value)[0]
s=default_store();pid='8b8ad09078db49c4b90724487bc208a6'
p,plan,cfg=validated_material(s,parent_id=pid)
with s.g.connect() as db:
    before={table:[dict(x) for x in db.execute('SELECT * FROM '+table+' ORDER BY rowid')] for table in ['jobs','reviews','hybrid_runs','hybrid_calls','hybrid_events','hybrid_liability_authorizations']}
    account=totals(db);unknown=[dict(x) for x in db.execute('SELECT * FROM hybrid_calls WHERE receipt IS NULL')]
assert account['effective_microusd']==9095632 and account['released_microusd']==0 and len(unknown)==2
assert not s.g.policy['approved'] and s.g.policy['total_usd']=='20.00'
private=ROOT/'data/hybrid-material-repair-before.json'
immutable(private,canonical(dict(tables=before,policy=s.g.policy)));private.chmod(0o600)
meta={key:OpenRouter(cfg[key+'_model']).preflight() for key in ['planner','reviewer']}
pimage=MaterialImage();schema=pimage.discover()
immutable(out/'live-metadata.json',canonical(meta));immutable(out/'image-schema.json',canonical(schema))
budget=8000000
assert budget+account['effective_microusd']<=20000000
approval=(ROOT/'HYBRID_MATERIAL_REPAIR_AUTHORIZATION.md').read_text()
with httpx.Client(base_url='http://127.0.0.1:48765',timeout=180) as c:
    response=c.post('/api/hybrid-runs/'+pid+'/continue-material',json=dict(budget_microusd=budget,max_seconds=3600,confirm_paid=True,approval_text=approval),headers={'Idempotency-Key':'material-repair-project20-calls12-images3-once-v1'})
    response.raise_for_status();r=response.json();immutable(out/'new-run.json',canonical(r))
    scope=dict(run_id=r['id'],config_sha256=r['config_sha256'],approval_text=approval,amendment=r['config']['authorization_amendment'],project_cap_microusd=20000000,budget_microusd=budget,max_calls=12,max_images=3,expires=time.time()+3600,liabilities=[dict(call_id=x['id'],request_sha256=digest(x['request'].encode()),amount=x['amount']) for x in unknown])
    aid=s.acknowledge_liabilities(scope)
    with s.g.connect() as db:assert json.loads(db.execute('SELECT record FROM hybrid_liability_authorizations WHERE id=?',(aid,)).fetchone()[0])==scope
    auth={k:scope[k] for k in ['config_sha256','budget_microusd','max_calls','max_images','expires']};auth['liability_authorization']=aid
    immutable(ROOT/'data/hybrid-authorizations'/(r['id']+'.json'),canonical(auth));immutable(out/'authorization.json',canonical(scope))
    c.post('/api/hybrid-runs/'+r['id']+'/resume',json={}).raise_for_status()
    got=c.get('/api/hybrid-runs/'+r['id']);got.raise_for_status();immutable(out/'launch-readback.json',canonical(got.json()))
    print(json.dumps(dict(run_id=r['id'],phase=got.json()['phase'],inherited_calls=r['call_count'],inherited_images=r['image_count'],acknowledgment_id=aid,held_before=account['effective_microusd'],remaining=20000000-account['effective_microusd'])))
