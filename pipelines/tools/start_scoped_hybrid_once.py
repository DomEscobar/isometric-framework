"""ONE explicitly authorized new run. Never invoke as a test/retry."""
import sys,json,time,sqlite3,base64
from pathlib import Path
import httpx
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from artifacts import canonical,digest
from hybrid_worker import default_store,immutable
out=ROOT/'evidence/hybrid-scoped-attempt';out.mkdir(exist_ok=True)
if (out/'new-run.json').exists():raise SystemExit('Already created; no new attempt')
db=sqlite3.connect('file:'+str(ROOT/'data/generation.sqlite3')+'?mode=ro',uri=True);db.row_factory=sqlite3.Row
snap={t:[dict(r) for r in db.execute('SELECT * FROM '+t+' ORDER BY rowid')] for t in ['jobs','reviews','hybrid_runs','hybrid_calls','hybrid_events']}
# Snapshot is private because retained exact requests can contain signed URLs.
p=ROOT/'data/hybrid-scoped-before.json';immutable(p,canonical(snap));p.chmod(0o600)
old=json.loads(next(r['config'] for r in snap['hybrid_runs'] if r['id']=='603c561c946e48efa2ba77a62e4b5848'))
held=sum(r['reserve'] for t in ['jobs','reviews'] for r in snap[t]);budget=10_000_000-held
with httpx.Client(base_url='http://127.0.0.1:48765',timeout=180) as client:
    f=client.post('/api/hybrid/preflight');f.raise_for_status();pre=f.json();immutable(out/'preflight.json',canonical(pre))
    assert pre['planner_model']['authenticated'] and pre['reviewer_model']['authenticated']
    need=2*pre['planner_model']['reserve_microusd']+2*pre['reviewer_model']['reserve_microusd']+11000
    assert need<=budget and budget==4276136
    ref=Path('/root/.hermes/cache/images/img_b9807e3d9a04.jpg').read_bytes()
    u=client.post('/api/hybrid/uploads',json={'base64_data':base64.b64encode(ref).decode()});u.raise_for_status();upload=u.json()
    assert upload['original_sha256']==old['reference_original_sha256']
    cfg={k:old[k] for k in ['description','constraints']}
    cfg.update(mode='live',reference_sha256=upload['sha256'],reference_original_sha256=upload['original_sha256'],budget_microusd=budget,max_images=1,max_calls=6,max_local_corrections=1,max_seconds=1800,auto_continue=True,confirm_paid=True)
    response=client.post('/api/hybrid-runs',json=cfg,headers={'Idempotency-Key':'explicit-scoped-new-attempt-v1'});response.raise_for_status();run=response.json()
    immutable(out/'new-run.json',canonical(run))
    unknown=[r for r in snap['hybrid_calls'] if r['receipt'] is None]
    assert len(unknown)==1 and unknown[0]['run']=='603c561c946e48efa2ba77a62e4b5848'
    scope=dict(run_id=run['id'],config_sha256=run['config_sha256'],approval_text='weiter?; ja was stehst du hier rum?; MACH JETZT LIVE LAUF WAS SOLL DER SCHEIS. Explicit task: ONE independent NEW attempt, keep all old holds, project USD10 cap; no legacy retry.',project_cap_microusd=10_000_000,budget_microusd=budget,max_calls=6,max_images=1,expires=time.time()+1800,liabilities=[dict(call_id=r['id'],request_sha256=digest(r['request'].encode()),amount=r['amount']) for r in unknown])
    s=default_store();aid=s.acknowledge_liabilities(scope)
    with s.g.connect() as check:assert json.loads(check.execute('SELECT record FROM hybrid_liability_authorizations WHERE id=?',(aid,)).fetchone()[0])==scope
    auth={k:scope[k] for k in ['config_sha256','budget_microusd','max_calls','max_images','expires']};auth['liability_authorization']=aid
    immutable(ROOT/'data/hybrid-authorizations'/(run['id']+'.json'),canonical(auth))
    immutable(out/'authorization.json',canonical(scope));immutable(out/'budget.json',canonical(dict(prior_held=held,remaining=budget,first_candidate_hold=need,authorization_id=aid)))
    read=client.get('/api/hybrid-runs/'+run['id']);read.raise_for_status();assert read.json()['config_sha256']==run['config_sha256']
    print(json.dumps(dict(run_id=run['id'],phase=read.json()['phase'],authorization_id=aid,first_candidate_hold=need,prior_held=held)))
