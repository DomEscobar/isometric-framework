"""Narrow forensic transport reconciliation; NEVER settlement or model evidence.

Only the independently retained paid-pilot-01 HTTP401 may use this branch.
No browser-provided status/hash/request identifier is accepted. The central
original row and full reservation remain unchanged. Evidence is re-read on use.
"""
import json
import sqlite3
import time
from pathlib import Path
from artifacts import canonical,digest

EVIDENCE_ROOT=Path(__file__).parent
MANIFEST=EVIDENCE_ROOT/'evidence/quality-recovery/reconciliation/verification.json'
MANIFEST_SHA256='b3c334ec449467f113d46e2e404db170af95d2ce5ae4a5252413294b9c7c14fd'
FAILURE_PATH='evidence/paid-pilot/reviewer-attempt-01-failure.json'
HISTORY_DB=Path('/root/.hermes/state.db')
HISTORY_ID=24546
RID='paid-pilot-01'


def _evidence(g):
    def require(value):
        if not value:raise ValueError('historical transport evidence missing or drifted; hold retained')
    try:
        raw=MANIFEST.read_bytes();require(digest(raw)==MANIFEST_SHA256);m=json.loads(raw)
        require(m['review_id']==RID and m['http_status']==401 and m['transport_outcome']=='http_rejected' and m['receipt_exists'] is False)
        with g.connect() as db:row=db.execute('SELECT reserve,record FROM reviews WHERE id=?',(RID,)).fetchone()
        require(row is not None)
        record=json.loads(row['record']);b=record['binding'];d=g.root/'reviews'/RID
        require(row['reserve']==record['reserve_microusd']==m['reserve_microusd'] and row['reserve']>0)
        require(digest(row['record'].encode())==m['central_record_text_sha256'])
        require(b==json.loads((d/'intent.json').read_bytes()) and b['request_sha256']==m['request_sha256'])
        require(not (d/'receipt.json').exists())
        for p in [d/'intent.json',d/'request.json',d/'metadata.json',*[d/f'input-{i}.png' for i in range(len(b['inputs']))]]:
            # Data may reside in a test root; production manifest paths start data/.
            key=str(p.relative_to(EVIDENCE_ROOT))
            require(digest(p.read_bytes())==m['file_sha256'][key])
        status_raw=(EVIDENCE_ROOT/FAILURE_PATH).read_bytes()
        require(digest(status_raw)==m['file_sha256'][FAILURE_PATH])
        status=json.loads(status_raw);require(status['review_id']==RID and status['http_status']==401)
        primary=next(x for x in m['history_evidence'] if x['id']==HISTORY_ID)
        require(primary['hashed_field']=='content' and primary['database']==str(HISTORY_DB))
        with sqlite3.connect('file:'+str(HISTORY_DB)+'?mode=ro',uri=True) as history:
            history.execute('PRAGMA query_only=ON')
            sid,text=history.execute('SELECT session_id,content FROM messages WHERE id=?',(HISTORY_ID,)).fetchone()
        require(sid==primary['session_id'] and digest(text.encode())==primary['sha256'])
        result=json.loads(text)
        require(result['exit_code']==1 and "run_review(g,'paid-pilot-01'" in result['output'] and
                'ValueError: review provider HTTP 401; liability retained; no retry' in result['output'])
        return dict(schema_version=1,review_id=RID,request_sha256=b['request_sha256'],
                    original_record_sha256=m['central_record_text_sha256'],evidence_manifest_sha256=MANIFEST_SHA256,
                    primary_status_sha256=primary['sha256'],primary_message_id=HISTORY_ID,
                    transport_outcome='http_rejected',http_status=401,execution_receipt_state='no_model_receipt',
                    billing_state='unverified_full_hold_retained',settled_cost_usd=None,reserve_microusd=row['reserve'],
                    released_microusd=0,retry_authorized=False)
    except (OSError,KeyError,TypeError,StopIteration,sqlite3.Error) as exc:
        raise ValueError('historical transport evidence unavailable; hold retained') from None


def reconcile(g,authorization_sha256):
    if not isinstance(authorization_sha256,str) or len(authorization_sha256)!=64 or any(c not in '0123456789abcdef' for c in authorization_sha256):
        raise ValueError('server authenticated authorization required')
    evidence=_evidence(g)
    with g.connect() as db:
        db.execute('BEGIN IMMEDIATE')
        db.execute('CREATE TABLE IF NOT EXISTS transport_reconciliations(id TEXT PRIMARY KEY,review_id TEXT UNIQUE,record TEXT NOT NULL)')
        db.execute("CREATE TRIGGER IF NOT EXISTS transport_reconciliation_no_update BEFORE UPDATE ON transport_reconciliations BEGIN SELECT RAISE(ABORT,'append only'); END")
        db.execute("CREATE TRIGGER IF NOT EXISTS transport_reconciliation_no_delete BEFORE DELETE ON transport_reconciliations BEGIN SELECT RAISE(ABORT,'append only'); END")
        old=db.execute('SELECT record FROM transport_reconciliations WHERE review_id=?',(RID,)).fetchone()
        if old:return verified_rejection(g,RID)
        # Recheck central row after locking, never reduce/replace its reservation.
        row=db.execute('SELECT reserve,record FROM reviews WHERE id=?',(RID,)).fetchone()
        if row['reserve']!=evidence['reserve_microusd'] or digest(row['record'].encode())!=evidence['original_record_sha256']:
            raise ValueError('historical ledger drift')
        event={**evidence,'authorization_sha256':authorization_sha256,'actor':'trusted local quality-recovery service','created_at':time.time()}
        eid=digest(canonical(event));event['id']=eid
        db.execute('INSERT INTO transport_reconciliations VALUES (?,?,?)',(eid,RID,canonical(event).decode()))
    return verified_rejection(g,RID)


def verified_rejection(g,rid):
    if rid!=RID:raise ValueError('no historical rejection proof for this identity')
    with g.connect() as db:
        if not db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='transport_reconciliations'").fetchone():
            raise ValueError('transport not reconciled')
        row=db.execute('SELECT id,record FROM transport_reconciliations WHERE review_id=?',(rid,)).fetchone()
    if not row:raise ValueError('transport not reconciled')
    e=json.loads(row['record'])
    if e.get('id')!=row['id'] or digest(canonical({k:v for k,v in e.items() if k!='id'}))!=e['id']:
        raise ValueError('transport event drift')
    expected=_evidence(g)
    if any(e.get(k)!=v for k,v in expected.items()):raise ValueError('transport evidence drift')
    return e
