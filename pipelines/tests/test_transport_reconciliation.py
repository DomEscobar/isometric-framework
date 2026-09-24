"""MOCK forensic fixtures exercise real ledger append/readback; no network."""
import json
import sqlite3
import shutil
import pytest
from artifacts import canonical,digest
from test_continuation_readiness import fixture


def evidence(tmp_path,monkeypatch):
    import transport_reconciliation as tr
    c,w,e=fixture(tmp_path);g=c.app.state.generation
    rid='paid-pilot-01'
    with g.connect() as db:
        row=db.execute('SELECT reserve,record FROM reviews WHERE id=?',(e['id'],)).fetchone()
        rec=json.loads(row['record']);rec['id']=rid
        db.execute('INSERT INTO reviews VALUES (?,?,?)',(rid,row['reserve'],canonical(rec).decode()))
    d=tmp_path/'reviews'/rid;shutil.copytree(tmp_path/'reviews'/e['id'],d);(d/'receipt.json').unlink()
    status=tmp_path/'failure.json';status.write_bytes(canonical(dict(review_id=rid,http_status=401)))
    h=tmp_path/'history.sqlite3'
    text=canonical(dict(exit_code=1,output="MOCK run_review(g,'paid-pilot-01'\nValueError: review provider HTTP 401; liability retained; no retry")).decode()
    with sqlite3.connect(h) as db:
        db.execute('CREATE TABLE messages(id INTEGER,session_id TEXT,content TEXT)')
        db.execute('INSERT INTO messages VALUES(?,?,?)',(9,'mock-session',text))
    manifest=dict(review_id=rid,http_status=401,transport_outcome='http_rejected',receipt_exists=False,
        reserve_microusd=row['reserve'],central_record_text_sha256=digest(canonical(rec)),request_sha256=rec['binding']['request_sha256'],
        file_sha256={str(p.relative_to(tmp_path)):digest(p.read_bytes()) for p in [*d.iterdir(),status]},
        history_evidence=[dict(database=str(h),id=9,session_id='mock-session',hashed_field='content',sha256=digest(text.encode()))])
    m=tmp_path/'proof.json';m.write_bytes(canonical(manifest))
    monkeypatch.setattr(tr,'MANIFEST',m);monkeypatch.setattr(tr,'MANIFEST_SHA256',digest(m.read_bytes()))
    monkeypatch.setattr(tr,'EVIDENCE_ROOT',tmp_path);monkeypatch.setattr(tr,'FAILURE_PATH','failure.json')
    monkeypatch.setattr(tr,'HISTORY_ID',9);monkeypatch.setattr(tr,'HISTORY_DB',h)
    return c,g,w,m,d


def test_rejected_transport_append_only_retains_full_hold(tmp_path,monkeypatch):
    import transport_reconciliation as tr
    c,g,w,m,d=evidence(tmp_path,monkeypatch)
    budget=g.status()
    with g.connect() as db:before=list(map(tuple,db.execute('SELECT * FROM reviews')))
    assert c.app.state.auto_repair.adapter.liability_blockers()
    event=tr.reconcile(g,'a'*64)
    assert event['released_microusd']==0 and event['settled_cost_usd'] is None
    assert event['billing_state']=='unverified_full_hold_retained' and event['retry_authorized'] is False
    assert tr.reconcile(g,'a'*64)==event
    assert tr.verified_rejection(g,'paid-pilot-01')==event
    assert c.app.state.auto_repair.adapter.liability_blockers()==[]
    assert not (d/'receipt.json').exists() and g.status()==budget
    with g.connect() as db:assert list(map(tuple,db.execute('SELECT * FROM reviews')))==before


def test_reconciliation_http_requires_document_authority(tmp_path,monkeypatch):
    import auto_adapter
    c,g,w,m,d=evidence(tmp_path,monkeypatch)
    url='/api/auto-repair/'+w['id']+'/reconcile-transport'
    assert c.post(url,json={'confirm_paid':True}).status_code==409
    doc=tmp_path/'authorization.md';doc.write_text('MOCK recovery authority')
    monkeypatch.setattr(auto_adapter,'QUALITY_AUTHORIZATION',doc)
    (tmp_path/'quality-recovery-policy.json').write_bytes(canonical(dict(enabled=True,parent_run_id=w['id'],authorization_sha256=digest(doc.read_bytes()))))
    r=c.post(url,json={'confirm_paid':True});assert r.status_code==200,r.text
    assert r.json()['transport_outcome']=='http_rejected'
    assert c.get(url).json()==r.json()
    assert c.post(url,json={'confirm_paid':True,'http_status':401}).status_code==422


@pytest.mark.parametrize('damage',['manifest','request','failure','history','row','receipt'])
def test_reconciliation_refuses_unbound_or_tampered_evidence(tmp_path,monkeypatch,damage):
    import transport_reconciliation as tr
    c,g,w,m,d=evidence(tmp_path,monkeypatch)
    event=tr.reconcile(g,'a'*64)
    if damage=='manifest':m.write_text('{}')
    elif damage=='request':(d/'request.json').write_text('{}')
    elif damage=='failure':(tmp_path/'failure.json').write_text('{"http_status":401}')
    elif damage=='history':
        with sqlite3.connect(tmp_path/'history.sqlite3') as db:db.execute("UPDATE messages SET content='timeout'")
    elif damage=='row':
        with g.connect() as db:db.execute("UPDATE reviews SET reserve=reserve-1 WHERE id='paid-pilot-01'")
    else:(d/'receipt.json').write_text('{}')
    with pytest.raises(ValueError):tr.verified_rejection(g,'paid-pilot-01')
    assert c.app.state.auto_repair.adapter.liability_blockers()
