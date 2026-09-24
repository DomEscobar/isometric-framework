"""Settle five known complex-chain receipts (capture raw, then settle). Unknowns untouched."""
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
TARGETS=['38c6a3dd0c1c01318440a03b9dc69c2df691093fcd5d1df3164d47fc8f94fcd5',
 'aabdc6d57ac833ceec6a532c877d3bdb12aede249fc173fe7140248bb6bb036e',
 'af108e162b7a1be0310338635f8f927efc85e5141e9bdeb2bad818ea9da55786',
 '6427aba6041a5a19b3a23071afd5b8187cbbc726c6bb5b24efdcd796e5affa6e',
 'f80ae53ede5e429a2b054840858ad1a5d4786e9a129abcca6b3b6f9d65157823']
s=default_store();report=[]
for cid in TARGETS:
    with s.g.connect() as db:gid=json.loads(db.execute('SELECT receipt FROM hybrid_calls WHERE id=?',(cid,)).fetchone()[0])['id']
    raw=fetch(gid);expected=digest(raw)
    immutable(ROOT/'evidence'/'hybrid-complex-terrain'/(gid+'-raw-billing.json'),raw)
    try:
        p=settle(s.g,cid,fetch,expected)
        entry=dict(call_id=cid,generation_id=gid,status='settled',actual_usd=p['actual_usd'],released_microusd=p['released_microusd'])
    except ValueError as e:
        entry=dict(call_id=cid,generation_id=gid,status='not_settled',reason=str(e)[:160])
    report.append(entry);print(json.dumps(entry))
with s.g.connect() as db:t=totals(db)
print(json.dumps(t))
(ROOT/'evidence/hybrid-complex-terrain/settlement-chain.json').write_text(json.dumps(dict(settlements=report,totals=t),indent=1))
