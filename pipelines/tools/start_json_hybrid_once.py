"""ONE owner-authorized DIFFERENT transport run; not a regression tool."""
import sys,json,time,sqlite3
from pathlib import Path
import httpx
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from artifacts import canonical,digest
from hybrid_worker import default_store,immutable,runtime_version
out=ROOT/'evidence/hybrid-json-transport';out.mkdir(exist_ok=True)
if (out/'new-run.json').exists():raise SystemExit('Already created; no retry')
db=sqlite3.connect('file:'+str(ROOT/'data/generation.sqlite3')+'?mode=ro',uri=True);db.row_factory=sqlite3.Row
snap={t:[dict(r) for r in db.execute('SELECT * FROM '+t+' ORDER BY rowid')] for t in ['jobs','reviews','hybrid_runs','hybrid_calls','hybrid_events']}
p=ROOT/'data/hybrid-json-before.json';immutable(p,canonical(snap));p.chmod(0o600)
held=sum(r['reserve'] for t in ['jobs','reviews'] for r in snap[t]);budget=10_000_000-held
assert held==6541016 and budget==3458984
old=json.loads(next(r['config'] for r in snap['hybrid_runs'] if r['id']=='72e30617e8294e1f8529ffccaee00286'))
unknown=[r for r in snap['hybrid_calls'] if r['receipt'] is None]
assert len(unknown)==2 and {r['run'] for r in unknown}=={'603c561c946e48efa2ba77a62e4b5848','72e30617e8294e1f8529ffccaee00286'}
oldrequest=json.loads(next(r['request'] for r in unknown if r['run']=='72e30617e8294e1f8529ffccaee00286'))
assert oldrequest['body']['response_format']['type']=='json_schema'
source=(ROOT/'hybrid_models.py').read_bytes()
assert b"response_format={'type':'json_object'}" in source
immutable(out/'transport-precheck.json',canonical(dict(old_request_sha256=digest(canonical(oldrequest)),old_format='json_schema',new_format='json_object',adapter_sha256=digest(source),runtime_version=runtime_version(),docs='https://openrouter.ai/docs/api_reference/parameters#response-format')))
with httpx.Client(base_url='http://127.0.0.1:48765',timeout=180) as client:
    f=client.post('/api/hybrid/preflight');f.raise_for_status();pre=f.json();immutable(out/'preflight.json',canonical(pre))
    assert pre['planner_model']['authenticated'] and pre['reviewer_model']['authenticated']
    from decimal import Decimal
    assert pre['image_quote']['currency']=='USD'
    image=int(Decimal(str(pre['image_quote']['price']))*1_000_000)
    need=2*pre['planner_model']['reserve_microusd']+2*pre['reviewer_model']['reserve_microusd']+image
    assert need==3279608 and need<=budget
    cfg={k:old[k] for k in ['description','constraints','reference_sha256','reference_original_sha256']}
    cfg.update(mode='live',budget_microusd=budget,max_images=1,max_calls=5,max_local_corrections=0,max_seconds=1800,auto_continue=True,confirm_paid=True)
    response=client.post('/api/hybrid-runs',json=cfg,headers={'Idempotency-Key':'explicit-json-object-new-attempt-v1'});response.raise_for_status();run=response.json()
    immutable(out/'new-run.json',canonical(run))
    assert run['config']['runtime_version']==runtime_version()
    scope=dict(run_id=run['id'],config_sha256=run['config_sha256'],approval_text='ja los. Explicit task: repair provider transport and ONE DIFFERENT independent LIVE run; acknowledge BOTH exact unresolved calls/full holds; USD10 shared ceiling, no old-call retry, max1image max5calls zero local corrections.',project_cap_microusd=10_000_000,budget_microusd=budget,max_calls=5,max_images=1,expires=time.time()+1800,liabilities=[dict(call_id=r['id'],request_sha256=digest(r['request'].encode()),amount=r['amount']) for r in unknown])
    s=default_store();aid=s.acknowledge_liabilities(scope)
    with s.g.connect() as check:assert json.loads(check.execute('SELECT record FROM hybrid_liability_authorizations WHERE id=?',(aid,)).fetchone()[0])==scope
    auth={k:scope[k] for k in ['config_sha256','budget_microusd','max_calls','max_images','expires']};auth['liability_authorization']=aid
    immutable(ROOT/'data/hybrid-authorizations'/(run['id']+'.json'),canonical(auth))
    immutable(out/'authorization.json',canonical(scope));immutable(out/'budget.json',canonical(dict(prior_held=held,remaining=budget,first_candidate_hold=need,authorization_id=aid)))
    read=client.get('/api/hybrid-runs/'+run['id']);read.raise_for_status();assert read.json()['config_sha256']==run['config_sha256']
    print(json.dumps(dict(run_id=run['id'],phase=read.json()['phase'],authorization_id=aid,first_candidate_hold=need,prior_held=held)))
