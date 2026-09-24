"""Evidence-backed settlement of KNOWN receipts only. Never touches unknown holds."""
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
# Exact pre-captured raw billing hashes (tools/verify_reassessment.py + billing lookups).
TARGETS=[
 ('0fdf6e2b4603ab9a5e6c0f9fa5d7877d5d71d8802f52e0ae28a205584fb824dc','26d5d2a6d8441ffc0783d5d4c24f197efeb0726620b533546bcf160b3fcf7bb1'),
 ('11634cdccddf46d67b5cced12a95b69080fc29fb8ee346b68b2e61d1751affc1','1756ac3608d64317c40f43126e10fd53753fe3e87d8b3e51b8060afb220e2c5d'),
]
s=default_store();report=[]
for cid,expected in TARGETS:
    try:
        p=settle(s.g,cid,fetch,expected)
        entry=dict(call_id=cid,status='settled',actual_usd=p['actual_usd'],released_microusd=p['released_microusd'])
    except ValueError as e:
        entry=dict(call_id=cid,status='not_settled',reason=str(e)[:160])
    report.append(entry);print(json.dumps(entry))
with s.g.connect() as db:t=totals(db)
print(json.dumps(t))
(ROOT/'evidence/hybrid-complex-terrain/settlement-summary.json').write_text(json.dumps(dict(settlements=report,totals=t),indent=1))
