"""ONE authorized source continuation via live API. Not a regression command."""
import os,sys,json,time,shlex
from pathlib import Path
import httpx
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from artifacts import canonical,digest
from hybrid_models import OpenRouter
from hybrid_worker import immutable,default_store
from hybrid_source_recovery import validated_source,TOKEN_POLICY
from billing_settlement import totals
out=ROOT/'evidence/hybrid-source-continuation';out.mkdir(exist_ok=True)
if (out/'new-run.json').exists():raise SystemExit('Already launched; never start another')
for line in Path('/root/.config/layout-terrain-hybrid/environment').read_text().splitlines():
    if line.strip() and not line.lstrip().startswith('#'):
        key,value=line.split('=',1)
        if key=='OPENROUTER_API_KEY':os.environ[key]=shlex.split(value)[0]
s=default_store();before=json.loads((ROOT/'data/hybrid-source-continuation-before.json').read_bytes())
assert s.g.policy=={**before['policy'],'total_usd':'20.00'} and not s.g.policy['approved']
with s.g.connect() as db:
    for table,rows in before['tables'].items():assert [dict(x) for x in db.execute('SELECT * FROM '+table+' ORDER BY rowid')]==rows,table
    account=totals(db);unknown=[dict(x) for x in db.execute('SELECT * FROM hybrid_calls WHERE receipt IS NULL')]
assert account['original_microusd']==8186320 and account['effective_microusd']==8186320 and len(unknown)==2
pid='d270dd95c2104370938199f8f91bcb55';proof,plan,cfg=validated_source(s,parent_id=pid)
metas={};costs={}
for key in ['planner','reviewer']:
    p=OpenRouter(cfg[key+'_model']);meta=p.preflight();metas[key]=meta
    p.policy({'token_policy':TOKEN_POLICY},'extraction' if key=='planner' else 'review_sample',meta)
    costs[key]=p.cost(meta,32768)
budget=costs['planner']+2*costs['reviewer'];assert account['effective_microusd']+budget<=20000000
immutable(out/'live-metadata.json',canonical(metas))
immutable(out/'cap-readback.json',canonical({'policy':s.g.policy,'accounting':account,'all_prior_rows_unchanged':True,'project_cap_microusd':20000000,'required_new_budget_microusd':budget,'per_call_reserve':costs,'token_policy':TOKEN_POLICY}))
approval=(ROOT/'HYBRID_SOURCE_CONTINUATION_AUTHORIZATION.md').read_text()
with httpx.Client(base_url='http://127.0.0.1:48765',timeout=180) as c:
    status=c.get('/api/hybrid/config');status.raise_for_status();assert status.json()['ledger']['total_budget_usd']=='20.00'
    response=c.post('/api/hybrid-runs/'+pid+'/continue-source',json=dict(budget_microusd=budget,max_seconds=1800,confirm_paid=True,approval_text=approval),headers={'Idempotency-Key':'source-token32768-project20-once-v1'})
    response.raise_for_status();r=response.json();immutable(out/'new-run.json',canonical(r))
    scope=dict(run_id=r['id'],config_sha256=r['config_sha256'],approval_text=approval,project_cap_microusd=20000000,budget_microusd=budget,max_calls=6,max_images=1,expires=time.time()+1800,liabilities=[dict(call_id=x['id'],request_sha256=digest(x['request'].encode()),amount=x['amount']) for x in unknown])
    aid=s.acknowledge_liabilities(scope)
    with s.g.connect() as db:assert json.loads(db.execute('SELECT record FROM hybrid_liability_authorizations WHERE id=?',(aid,)).fetchone()[0])==scope
    auth={k:scope[k] for k in ['config_sha256','budget_microusd','max_calls','max_images','expires']};auth['liability_authorization']=aid
    immutable(ROOT/'data/hybrid-authorizations'/(r['id']+'.json'),canonical(auth));immutable(out/'authorization.json',canonical(scope))
    c.post('/api/hybrid-runs/'+r['id']+'/resume').raise_for_status()
    result=c.get('/api/hybrid-runs/'+r['id']);result.raise_for_status();immutable(out/'launch-readback.json',canonical(result.json()))
    print(json.dumps({'run_id':r['id'],'phase':result.json()['phase'],'project_cap_microusd':20000000,'held_before':account['effective_microusd'],'new_budget_microusd':budget,'max_tokens':32768,'reasoning':'medium','lifetime_calls':3,'max_calls':6,'acknowledgment_id':aid}))
