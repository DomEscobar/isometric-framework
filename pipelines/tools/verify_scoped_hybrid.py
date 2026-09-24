"""Read-only final verification of the single scoped run and old liabilities."""
import json,sqlite3,sys,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from artifacts import canonical,digest
out=ROOT/'evidence/hybrid-scoped-attempt';rid=json.loads((out/'new-run.json').read_bytes())['id']
snap=json.loads((ROOT/'data/hybrid-scoped-before.json').read_bytes())
db=sqlite3.connect('file:'+str(ROOT/'data/generation.sqlite3')+'?mode=ro',uri=True);db.row_factory=sqlite3.Row
old_proof={}
for table,rows in snap.items():
    key='seq' if table=='hybrid_events' else 'id'
    for row in rows:
        now=dict(db.execute('SELECT * FROM '+table+' WHERE '+key+'=?',(row[key],)).fetchone())
        assert now==row,(table,row[key])
    old_proof[table]=dict(count=len(rows),unchanged=True,sha256=digest(canonical(rows)))
calls=[dict(r) for r in db.execute('SELECT * FROM hybrid_calls WHERE run=?',(rid,))]
assert len(calls)==1 and calls[0]['receipt'] is None
cid=calls[0]['id'];diag=json.loads((ROOT/'data/hybrid-errors'/cid/'diagnostic.json').read_bytes());raw=(ROOT/'data/hybrid-errors'/cid/'response.bin').read_bytes();assert digest(raw)==diag['response_sha256'];assert digest(calls[0]['request'].encode())==diag['request_sha256']
error=json.loads(raw)['error'];meta=error['metadata'];upstream=json.loads(meta['raw'])['error']
# Explicit allowlist: no user account IDs, arbitrary body, or credentials exported.
sanitized=dict(http_status=diag['http_status'],provider=meta['provider_name'],provider_error_code=meta['provider_error_code'],upstream_code=upstream['code'],upstream_status=upstream['status'],upstream_message=upstream['message'],previous_provider_errors=[dict(provider=e['provider_name'],code=e['code']) for e in meta.get('previous_errors',[])],request_sha256=diag['request_sha256'],response_sha256=diag['response_sha256'],completion_receipt=False,billing='unsettled_full_hold_retained')
held=sum(db.execute('SELECT coalesce(sum(reserve),0) FROM '+t).fetchone()[0] for t in ['jobs','reviews'])
assert held==5723864+817152
run=db.execute('SELECT * FROM hybrid_runs WHERE id=?',(rid,)).fetchone();assert run['phase']=='needs_attention'
result=dict(run_id=rid,phase=run['phase'],old_rows=old_proof,central_held_microusd=held,remaining_microusd=10_000_000-held,new_held_microusd=calls[0]['amount'],new_known_billed_cost=None,images=0,new_calls=1,error=sanitized,no_zip_or_visual_review=True)
(out/'verification.json').write_bytes(canonical(result));(out/'sanitized-provider-error.json').write_bytes(canonical(sanitized));print(json.dumps(result,indent=2))
