import json
import pytest
from artifacts import canonical,digest
from test_hybrid_continuation import parent

def fixture(tmp_path):
    s,r,c=parent(tmp_path)
    with s.g.connect() as db:
        row=db.execute('SELECT * FROM hybrid_calls WHERE id=?',(c['id'],)).fetchone()
        receipt=json.loads(row['receipt']);receipt['usage']={'cost':0.0000201,'is_byok':False}
        db.execute('UPDATE hybrid_calls SET receipt=? WHERE id=?',(canonical(receipt).decode(),c['id']))
    raw=canonical({'data':{'id':'gen-test','model':'test/model','total_cost':0.0000201,'usage':0.0000201,'is_byok':False,'provider_name':'Test','provider_responses':[{'model_permaslug':'test/model','provider_name':'Test','status':200}]}})
    return s,c['id'],raw

def test_authenticated_settlement_keeps_old_rows_and_counts_once(tmp_path):
    import billing_settlement as b
    s,c,raw=fixture(tmp_path)
    with s.g.connect() as db:before=[tuple(x) for x in db.execute('SELECT * FROM reviews')]
    fetch=lambda gid:raw
    first=b.settle(s.g,c,fetch,digest(raw))
    assert first['actual_microusd']==21 and first['released_microusd']==79
    assert b.settle(s.g,c,fetch,digest(raw))==first
    with s.g.connect() as db:
        assert b.totals(db)['effective_microusd']==21
        assert [tuple(x) for x in db.execute('SELECT * FROM reviews')]==before
        assert db.execute('SELECT count(*) FROM billing_settlements').fetchone()[0]==1
        with pytest.raises(Exception):db.execute('DELETE FROM billing_settlements')

@pytest.mark.parametrize('bad',['hash','negative','overreserve','generation','model','receipt_cost','unknown'])
def test_bad_settlement_retains_hold(tmp_path,bad):
    import billing_settlement as b
    s,c,raw=fixture(tmp_path);data=json.loads(raw)
    if bad=='negative':data['data'].update(total_cost=-1,usage=-1)
    if bad=='overreserve':data['data'].update(total_cost=1,usage=1)
    if bad=='generation':data['data']['id']='gen-other'
    if bad=='model':data['data']['model']='wrong/model'
    if bad=='receipt_cost':data['data']['total_cost']=0
    if bad=='unknown':
        with s.g.connect() as db:db.execute('UPDATE hybrid_calls SET receipt=NULL WHERE id=?',(c,))
    raw=canonical(data)
    with pytest.raises(ValueError):b.settle(s.g,c,lambda gid:raw,'wrong' if bad=='hash' else digest(raw))
    with s.g.connect() as db:assert b.totals(db)['effective_microusd']==100

def test_concurrent_settlement_and_receipt_drift_fail_closed(tmp_path):
    import billing_settlement as b
    from concurrent.futures import ThreadPoolExecutor
    s,c,raw=fixture(tmp_path)
    with ThreadPoolExecutor(2) as pool:results=list(pool.map(lambda _:b.settle(s.g,c,lambda gid:raw,digest(raw)),range(2)))
    assert results[0]==results[1]
    with s.g.connect() as db:
        assert b.totals(db)['effective_microusd']==21
        db.execute('UPDATE hybrid_calls SET receipt=? WHERE id=?',('{}',c))
    with s.g.connect() as db:
        with pytest.raises((ValueError,KeyError)):b.totals(db)

def test_shared_generation_budget_uses_effective_amount(tmp_path):
    import billing_settlement as b
    s,c,raw=fixture(tmp_path);b.settle(s.g,c,lambda gid:raw,digest(raw))
    s.g.policy.update(approved=True,total_usd='0.0001')
    s.g.reserve_review('second',79,{'test':True})
    with s.g.connect() as db:assert b.totals(db)['effective_microusd']==100
    with pytest.raises(ValueError):s.g.reserve_review('third',1,{})

def test_explicit_twenty_dollar_policy_not_hardcoded_ten(tmp_path):
    from hybrid_store import Store
    from generation import Generation
    import time
    s=Store(Generation(tmp_path,None,{'total_usd':'20','approved':False}))
    cfg={'budget_microusd':12000000,'max_calls':6,'max_images':1}
    s.create('twenty',cfg);r=s.claim()
    a={**cfg,'config_sha256':digest(canonical(cfg)),'expires':time.time()+100}
    call=s.reserve_call(r,'review-test',{},11000000,a)
    assert call['new']
    s.receipt(call['id'],{'id':'test'})
    with pytest.raises(ValueError):s.reserve_call(r,'review-more',{},10000000,a)


