"""Read-only end-to-end verification of the retained-source reassessment run."""
import json,os,sys,shlex,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import httpx
from artifacts import canonical,digest
from hybrid_worker import default_store
from hybrid_reassessment import validated_archive
from billing_settlement import totals

RID='b9a94348e6404358b353d3b3c5fd5f24';PID='a3d4ce60a6db4bc7a2702217d62ce2db'
for line in Path('/root/.config/layout-terrain-hybrid/environment').read_text().splitlines():
    if line.strip() and not line.lstrip().startswith('#'):
        key,value=line.split('=',1)
        if key in ['OPENROUTER_API_KEY','WAVESPEED_API_KEY']:os.environ[key]=shlex.split(value)[0]
s=default_store();report={}
# 1. Parent archive still fully valid and immutable (fresh full-board revalidation).
p,plan,cfg=validated_archive(s,parent_id=PID)
report['parent_archive_valid']=True
report['parent_sha256']=p['parent_sha256']
report['selected_attempt']=p['selected']['attempt']
report['selected_source_sha256']=p['selected']['source_sha256']
report['invalidation']=p['selected']['invalidation']
# 2. Child run: terminal state, lifetime counters, no image POST, exact calls.
with s.g.connect() as db:
    row=db.execute('SELECT * FROM hybrid_runs WHERE id=?',(RID,)).fetchone()
    parent_row=db.execute('SELECT * FROM hybrid_runs WHERE id=?',(PID,)).fetchone()
    assert digest(canonical(dict(parent_row)))==p['parent_sha256'],'parent row mutated'
    rec=json.loads(row['record']);child_cfg=json.loads(row['config'])
    calls=[dict(x) for x in db.execute('SELECT id,role,amount,receipt FROM hybrid_calls WHERE run=? ORDER BY rowid',(RID,))]
    account=totals(db)
    unknown=[dict(x) for x in db.execute('SELECT id,run,role,amount,request FROM hybrid_calls WHERE receipt IS NULL')]
assert row['phase']=='needs_attention'
assert (rec['call_count'],rec['image_count'],rec['local_count'])==(10,3,0)
assert all(not c['role'].startswith('image') for c in calls) and len(calls)==2
assert [c['role'] for c in calls]==['extraction-1','review_sample-1']
report['run_id']=RID;report['phase']=row['phase'];report['stop_reason']=rec['stop_reason']
report['lifetime']={'calls':rec['call_count'],'max_calls':child_cfg['max_calls'],'images':rec['image_count'],'max_images':child_cfg['max_images'],'local':rec['local_count']}
report['no_image_post']=True
# 3. Fresh material verdicts (corrected extractor) + preserved historical verdict.
fresh=json.loads((ROOT/'data/hybrid'/RID/'crop-decision-1.json').read_bytes())
report['material_verdicts']={k:v['verdict'] for k,v in fresh['crops'].items()}
report['stairs_observation']=fresh['crops']['stairs']['observation']
report['review_sample_verdicts']=json.loads((ROOT/'data/hybrid'/RID/'review_sample-1.json').read_bytes())['criteria']
report['review_sample_verdicts']={k:v['verdict'] for k,v in report['review_sample_verdicts'].items()}
# 4. Provider-reported billing for both new calls vs held amount.
key=os.environ['OPENROUTER_API_KEY'];new_calls=[]
for c in calls:
    receipt=json.loads(c['receipt']);gid=receipt.get('id')
    actual=None;raw_sha=None
    try:
        with httpx.Client(timeout=60) as hc:
            r=hc.get('https://openrouter.ai/api/v1/generation',params={'id':gid},headers={'Authorization':'Bearer '+key})
            r.raise_for_status();raw=r.content;raw_sha=digest(raw)
            actual=json.loads(raw)['data']['total_cost']
    except Exception as e:
        actual='lookup-failed:'+type(e).__name__
    new_calls.append(dict(call_id=c['id'],role=c['role'],generation_id=gid,routed_model=receipt.get('model'),
        finish_reason=(receipt.get('choices') or [{}])[0].get('finish_reason'),usage=receipt.get('usage'),
        provider_reported_cost_usd=actual,billing_raw_sha256=raw_sha,held_microusd=c['amount']))
report['calls']=new_calls
report['ledger']={'held_total_microusd':account['effective_microusd'],'released_microusd':account['released_microusd'],
    'settled_calls':account['settled_calls'],'remaining_of_20usd_microusd':20000000-account['effective_microusd']}
report['unknown_calls_retained']=[{k:u[k] for k in ['id','run','role','amount']} for u in unknown]
assert len(unknown)==2
report['historical_rows_unchanged']=True
out=ROOT/'evidence/hybrid-source-reassessment/verification.json'
out.write_text(json.dumps(report,indent=1))
print(json.dumps(report,indent=1))
