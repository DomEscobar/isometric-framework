"""Settle the two known planner receipts (capture authenticated raw, then settle). No unknowns touched."""
import os,sys,json,shlex
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import httpx
from hybrid_worker import default_store,immutable
from artifacts import canonical,digest
from billing_settlement import settle,totals
for line in Path('/root/.config/layout-terrain-hybrid/environment').read_text().splitlines():
    if line.strip() and not line.lstrip().startswith('#'):
        key,value=line.split('=',1)
        if key=='OPENROUTER_API_KEY':os.environ[key]=shlex.split(value)[0]
key=os.environ['OPENROUTER_API_KEY']
def fetch(gid):
    with httpx.Client(timeout=60) as hc:
        r=hc.get('https://openrouter.ai/api/v1/generation',params={'id':gid},headers={'Authorization':'Bearer '+key})
        r.raise_for_status();return r.content
s=default_store();report=[]
with s.g.connect() as db:
    rows=[dict(x) for x in db.execute("SELECT id,run,role,receipt,amount FROM hybrid_calls WHERE role='planner' AND receipt IS NOT NULL ORDER BY rowid DESC")]
for call in rows[:2]:
    gid=json.loads(call['receipt']).get('id')
    raw=fetch(gid)                      # independent authenticated capture
    expected=digest(raw)
    immutable(ROOT/'evidence'/'hybrid-complex-terrain'/(gid+'-raw-billing.json'),raw)
    try:
        p=settle(s.g,call['id'],fetch,expected)
        entry=dict(call_id=call['id'],run=call['run'],generation_id=gid,status='settled',actual_usd=p['actual_usd'],released_microusd=p['released_microusd'],raw_sha256=expected)
    except ValueError as e:
        entry=dict(call_id=call['id'],run=call['run'],generation_id=gid,status='not_settled',reason=str(e)[:160])
    report.append(entry);print(json.dumps(entry))
with s.g.connect() as db:t=totals(db)
print(json.dumps(t))
(ROOT/'evidence/hybrid-complex-terrain/settlement-planners.json').write_text(json.dumps(dict(settlements=report,totals=t),indent=1))
