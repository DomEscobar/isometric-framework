"""Append-only authenticated OpenRouter billing; original reservations never mutate."""
import json,re
from decimal import Decimal,ROUND_CEILING
from artifacts import canonical,digest

def initialize(db):
    db.executescript('''CREATE TABLE IF NOT EXISTS billing_settlements(call_id TEXT PRIMARY KEY,record TEXT NOT NULL);
    CREATE TRIGGER IF NOT EXISTS billing_no_update BEFORE UPDATE ON billing_settlements BEGIN SELECT RAISE(ABORT,'immutable settlement'); END;
    CREATE TRIGGER IF NOT EXISTS billing_no_delete BEFORE DELETE ON billing_settlements BEGIN SELECT RAISE(ABORT,'immutable settlement'); END;''')

def proof(db,cid,raw):
    call=db.execute('SELECT * FROM hybrid_calls WHERE id=?',(cid,)).fetchone()
    ledger=db.execute('SELECT * FROM reviews WHERE id=?',(cid,)).fetchone()
    if not call or not call['receipt'] or not ledger:raise ValueError('Known receipt/ledger required')
    request=json.loads(call['request']);receipt=json.loads(call['receipt']);billing=json.loads(raw)['data']
    if cid!=digest(canonical([call['run'],call['role'],request])):raise ValueError('Call request drift')
    if ledger['reserve']!=call['amount'] or json.loads(ledger['record'])['binding']['request_sha256']!=digest(call['request'].encode()):raise ValueError('Ledger drift')
    model=request['body']['model'];backend=billing['model']
    if request['metadata']['id']!=model or receipt.get('model')!=model or billing.get('id')!=receipt.get('id') or not str(receipt.get('id','')).startswith('gen-'):raise ValueError('Generation/model mismatch')
    if backend!=model and not re.fullmatch(re.escape(model)+r'-\d{8}',backend):raise ValueError('Backend model mismatch')
    if not any(p.get('model_permaslug')==backend and p.get('provider_name')==billing.get('provider_name') and p.get('status')==200 for p in billing.get('provider_responses',[])):raise ValueError('Backend provider unproven')
    usage=receipt.get('usage',{})
    cost=Decimal(str(billing['total_cost']))
    if not cost.is_finite() or cost<0 or billing.get('is_byok') is not False or usage.get('is_byok') is not False:raise ValueError('Invalid/unproven billing')
    if cost!=Decimal(str(usage.get('cost'))) or cost!=Decimal(str(billing.get('usage'))):raise ValueError('Billing cost drift')
    actual=int((cost*1_000_000).to_integral_value(rounding=ROUND_CEILING))
    if actual>call['amount']:raise ValueError('Billing exceeds reservation; manual closure required')
    return dict(call_id=cid,run_id=call['run'],request_sha256=digest(call['request'].encode()),receipt_sha256=digest(call['receipt'].encode()),ledger_sha256=digest(canonical(dict(ledger))),generation_id=receipt['id'],routed_model=model,backend_model=backend,billing_raw_sha256=digest(raw),billing_raw=raw.decode(),actual_usd=str(cost),actual_microusd=actual,original_hold_microusd=call['amount'],released_microusd=call['amount']-actual)

def settle(g,cid,fetch,expected_raw_sha256):
    # fetch is an authenticated GET-only adapter; no caller-supplied cost/model.
    with g.connect() as db:
        row=db.execute('SELECT receipt FROM hybrid_calls WHERE id=?',(cid,)).fetchone()
        if not row or not row[0]:raise ValueError('Unknown receipt: hold retained')
        gid=json.loads(row[0]).get('id')
    raw=fetch(gid)
    if digest(raw)!=expected_raw_sha256:raise ValueError('Billing raw hash mismatch')
    with g.connect() as db:
        initialize(db);db.execute('BEGIN IMMEDIATE');p=proof(db,cid,raw)
        old=db.execute('SELECT record FROM billing_settlements WHERE call_id=?',(cid,)).fetchone()
        record=canonical(p).decode()
        if old and old[0]!=record:raise ValueError('Settlement drift')
        if not old:db.execute('INSERT INTO billing_settlements VALUES(?,?)',(cid,record))
    return p

def totals(db):
    original={t:db.execute('SELECT coalesce(sum(reserve),0) FROM '+t).fetchone()[0] for t in ['jobs','reviews']}
    release=0;actual=0;count=0
    if db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='billing_settlements'").fetchone():
        for row in db.execute('SELECT * FROM billing_settlements'):
            p=json.loads(row['record']);validated=proof(db,row['call_id'],p['billing_raw'].encode())
            if canonical(validated).decode()!=row['record']:raise ValueError('Settlement evidence drift; paid controls closed')
            release+=p['released_microusd'];actual+=p['actual_microusd'];count+=1
    held=sum(original.values())
    return dict(original_microusd=held,effective_microusd=held-release,released_microusd=release,settled_actual_microusd=actual,unsettled_hold_microusd=held-release-actual,settled_calls=count,jobs_microusd=original['jobs'],reviews_microusd=original['reviews']-release)
