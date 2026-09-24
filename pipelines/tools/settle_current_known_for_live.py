"""Read authenticated billing for known receipts only, then append verified settlements.
Unknown/receipt-less requests are deliberately excluded and remain full holds.
"""
import json,os,shlex,sys
from pathlib import Path
import httpx
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from artifacts import canonical,digest
from hybrid_worker import default_store,immutable
from billing_settlement import settle,totals
for line in Path('/root/.config/layout-terrain-hybrid/environment').read_text().splitlines():
    if line.strip() and not line.lstrip().startswith('#'):
        k,v=line.split('=',1)
        if k=='OPENROUTER_API_KEY':os.environ[k]=shlex.split(v)[0]
key=os.environ['OPENROUTER_API_KEY'];s=default_store();out=ROOT/'evidence/live-run-known-billing';out.mkdir(exist_ok=True)
def fetch(gid):
    with httpx.Client(timeout=60) as c:
        r=c.get('https://openrouter.ai/api/v1/generation',params={'id':gid},headers={'Authorization':'Bearer '+key})
        r.raise_for_status();return r.content
with s.g.connect() as db:
    before=totals(db)
    unknown=[dict(x) for x in db.execute('SELECT id,run,role,amount FROM hybrid_calls WHERE receipt IS NULL ORDER BY id')]
    rows=[dict(x) for x in db.execute('SELECT hc.id,hc.run,hc.role,hc.amount,hc.receipt FROM hybrid_calls hc LEFT JOIN billing_settlements b ON b.call_id=hc.id WHERE hc.receipt IS NOT NULL AND b.call_id IS NULL ORDER BY hc.id')]
report=[];captured={}
for row in rows:
    receipt=json.loads(row['receipt']);gid=receipt.get('id')
    if not isinstance(gid,str) or not gid.startswith('gen-'):
        report.append({'call_id':row['id'],'status':'not_eligible','reason':'receipt has no OpenRouter generation id'});continue
    try:
        raw=fetch(gid);captured[gid]=raw
        immutable(out/(row['id']+'-'+gid+'-billing.json'),raw)
        p=settle(s.g,row['id'],lambda wanted: captured[wanted],digest(raw))
        report.append({'call_id':row['id'],'generation_id':gid,'status':'settled','held_microusd':row['amount'],'actual_microusd':p['actual_microusd'],'released_microusd':p['released_microusd']})
    except Exception as e:
        report.append({'call_id':row['id'],'generation_id':gid,'status':'not_settled','reason':str(e)[:180]})
with s.g.connect() as db:
    after=totals(db)
    now_unknown=[dict(x) for x in db.execute('SELECT id,run,role,amount FROM hybrid_calls WHERE receipt IS NULL ORDER BY id')]
    assert unknown==now_unknown, 'unknown liabilities changed'
    settlements=[dict(x) for x in db.execute('SELECT call_id,record FROM billing_settlements ORDER BY call_id')]
    assert len(settlements)>=before['settled_calls']
result={'before':before,'after':after,'unknown_unchanged':True,'unknown_count':len(unknown),'known_examined':len(rows),'results':report}
immutable(out/'settlement-report.json',canonical(result))
print(json.dumps({'before':before,'after':after,'unknown_count':len(unknown),'known_examined':len(rows),'results':report},separators=(',',':')))
