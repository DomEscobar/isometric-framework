"""Read back exact targets, old rows, billing holds and terminal production denial."""
import sys,json,sqlite3
from pathlib import Path
import httpx
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from artifacts import canonical,digest
from hybrid_worker import default_store,immutable
from hybrid_recovery import validated_parent
out=ROOT/'evidence/hybrid-receipt-continuation';rid=json.loads((out/'new-run.json').read_bytes())['id'];s=default_store();r=s.get(rid)
assert r['phase']=='needs_attention' and r['call_count']==3 and r['image_count']==1 and r['latest'] is None and r['best'] is None
proof,plan,cfg=validated_parent(s,r['config']['continuation'])
pid=proof['parent_id'];d=ROOT/'data/hybrid'/rid
assert (d/'planner-result.json').read_bytes()==(ROOT/'data/hybrid'/pid/'planner-result.json').read_bytes()
assert r['world']['revision']=='d6664a4ba7579eb40e86a07f08606d98225c05c24d1d64dd3a3570d4f9f3730a'
with s.g.connect() as db:
    old=json.loads((ROOT/'data/hybrid-continuation-before.json').read_bytes());preserved={}
    for table,rows in old.items():
        key='seq' if table=='hybrid_events' else 'id'
        assert all(dict(db.execute('SELECT * FROM '+table+' WHERE '+key+'=?',(x[key],)).fetchone())==x for x in rows)
        preserved[table]=len(rows)
    held=sum(db.execute('SELECT coalesce(sum(reserve),0) FROM '+t).fetchone()[0] for t in ['jobs','reviews'])
    calls=[]
    for x in db.execute('SELECT * FROM hybrid_calls WHERE run IN (?,?)',(pid,rid)):
        receipt=json.loads(x['receipt']);calls.append(dict(call_id=x['id'],run=x['run'],role=x['role'],held_microusd=x['amount'],request_sha256=digest(x['request'].encode()),receipt_sha256=digest(x['receipt'].encode()),provider_id=receipt['id'],usage=receipt.get('usage'),finish_reason=(receipt.get('choices') or [{}])[0].get('finish_reason')))
with httpx.Client(base_url='http://127.0.0.1:48765') as c:
    status=c.get('/api/hybrid-runs/'+rid);status.raise_for_status();assert status.json()['phase']==r['phase']
    assert c.post('/api/hybrid-runs/'+rid+'/resume').json()['phase']==r['phase']
    assert c.get('/api/hybrid-runs/'+rid+'/download?mode=production').status_code==409
    assert c.get('/api/hybrid-runs/'+rid+'/download?mode=diagnostic').status_code==409
result=dict(run_id=rid,phase=r['phase'],latest=None,best=None,production_denied=True,diagnostic_denied=True,preserved_old_rows=preserved,calls=calls,source_sha256=digest((d/'source-0.png').read_bytes()),held_microusd=held,remaining_microusd=10000000-held,next_minimum_holds=3*817152,lifetime_calls=3,lifetime_call_cap=5,remaining_calls=2,next_minimum_calls=3,normalization=r['world']['normalization'],stop_reason=r['stop_reason'])
immutable(out/'verification.json',canonical(result));immutable(out/'provider-original.png',(d/'source-0.png').read_bytes())
a=ROOT/'data/hybrid-authorizations'/(rid+'.json');a.unlink(missing_ok=True);assert not a.exists()
print(json.dumps(result,indent=2))
