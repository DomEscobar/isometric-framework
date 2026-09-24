"""One bounded continuing LIVE lineage; no new planner purchase."""
import sys,json,time,sqlite3
from pathlib import Path
import httpx
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from artifacts import canonical,digest
from hybrid_worker import default_store,immutable
out=ROOT/'evidence/hybrid-receipt-continuation';out.mkdir(exist_ok=True)
if (out/'new-run.json').exists():raise SystemExit('Already started; no repeated new run')
s=default_store()
with s.g.connect() as db:
    snap={t:[dict(r) for r in db.execute('SELECT * FROM '+t+' ORDER BY rowid')] for t in ['jobs','reviews','hybrid_runs','hybrid_calls','hybrid_events']}
held=sum(r['reserve'] for t in ['jobs','reviews'] for r in snap[t]);budget=10_000_000-held
assert held==7358168 and budget==2641832
p=ROOT/'data/hybrid-continuation-before.json';immutable(p,canonical(snap));p.chmod(0o600)
unknown=[r for r in snap['hybrid_calls'] if r['receipt'] is None]
assert len(unknown)==2
with httpx.Client(base_url='http://127.0.0.1:48765',timeout=180) as c:
    pre=c.post('/api/hybrid/preflight');pre.raise_for_status();pre=pre.json();immutable(out/'preflight.json',canonical(pre))
    from decimal import Decimal
    assert pre['planner_model']['authenticated'] and pre['reviewer_model']['authenticated']
    need=int(Decimal(str(pre['image_quote']['price']))*1000000)+pre['planner_model']['reserve_microusd']+2*pre['reviewer_model']['reserve_microusd']
    assert pre['image_quote']['currency']=='USD' and need<=budget
    response=c.post('/api/hybrid-runs/a8d71015aaa64977af1bf73fc3240004/continue',json=dict(budget_microusd=budget,max_seconds=1800,confirm_paid=True),headers={'Idempotency-Key':'receipt-continuation-standing-live-fix-v1'});response.raise_for_status();r=response.json()
    immutable(out/'new-run.json',canonical(r))
    scope=dict(run_id=r['id'],config_sha256=r['config_sha256'],approval_text='Standing LIVE -> FIX bis funktioniert: continue original bounded lineage using verified planner receipt automatically, no new planner, max lifetime1image/5calls/0local, unchanged USD10 shared ceiling. Acknowledge exact TWO historical unknown requests/full retained holds; no settlement or old identity retry.',project_cap_microusd=10000000,budget_microusd=budget,max_calls=r['config']['max_calls'],max_images=r['config']['max_images'],expires=time.time()+1800,liabilities=[dict(call_id=x['id'],request_sha256=digest(x['request'].encode()),amount=x['amount']) for x in unknown])
    aid=s.acknowledge_liabilities(scope)
    with s.g.connect() as db:assert json.loads(db.execute('SELECT record FROM hybrid_liability_authorizations WHERE id=?',(aid,)).fetchone()[0])==scope
    auth={k:scope[k] for k in ['config_sha256','budget_microusd','max_calls','max_images','expires']};auth['liability_authorization']=aid
    immutable(ROOT/'data/hybrid-authorizations'/(r['id']+'.json'),canonical(auth));immutable(out/'authorization.json',canonical(scope))
    c.post('/api/hybrid-runs/'+r['id']+'/resume').raise_for_status()
    actual=c.get('/api/hybrid-runs/'+r['id']);actual.raise_for_status();immutable(out/'launch-readback.json',canonical(actual.json()))
    print(json.dumps(dict(run_id=r['id'],phase=actual.json()['phase'],held_before=held,remaining=budget,first_candidate_hold=need,acknowledgment_id=aid)))
