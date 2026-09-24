"""Isolated app and labelled local review fixtures; no provider traffic."""
import base64
import io
import json
import pytest
import numpy as np
from PIL import Image
from artifacts import canonical, digest, png
from auto_repair import Start
from test_strict_review import mock_decision


def fixture(tmp_path, decision=None, registered=True, color=180, translation=None):
    from test_style_gate import setup
    from auto_adapter import measure_registration
    c,l,_,spec,raw=setup(tmp_path)
    a=np.array(Image.open(io.BytesIO(raw)).convert('RGBA'))
    a[a[:,:,3]>0,:3]=color
    source=png(a)
    t=c.post('/api/layouts/'+l['revision']+'/terrain',json={'png_base64':base64.b64encode(source).decode(),'projection':l['layout']['projection']}).json()
    if registered:
        measured=measure_registration(source,raw)
        t=c.post('/api/terrain/'+t['id']+'/register',json={'scale':measured.get('scale',1),'translation':translation or measured.get('translation',[0,0]),'notes':'MOCK technical fixture'}).json()
    sid=c.post('/api/style-specs',json=spec).json()['id']
    ev=c.app.state.evaluations
    e=ev.prepare(t['id'],sid,1)
    g=c.app.state.generation
    g.policy={'approved':True,'total_usd':'10','max_attempts':2}
    meta={'id':'mock/vision','architecture':{'input_modalities':['text','image'],'output_modalities':['text']},'supported_parameters':['response_format','temperature','max_tokens'],'pricing':{'prompt':'0.000001','completion':'0.000001'},'context_length':10000}
    e=ev.run(e['id'],meta,lambda _:dict(model=meta['id'],choices=[dict(finish_reason='stop',message={'content':json.dumps(decision or mock_decision())})]))
    service=c.app.state.auto_repair
    w=service.start(Start(evaluation_id=e['id'],confirm_paid=True,max_iterations=3))
    w.update(status='needs_attention',phase='register',stop_reason='registration_ambiguous: fixture',iterations=[dict(registration={'blocker':'registration_ambiguous: fixture'},plan={'action':'register'})])
    service.save(w)
    g.policy={'approved':False,'total_usd':'10','max_attempts':2}
    def forbidden(*a,**kw):raise AssertionError('readiness must not call provider or mutate state')
    g.provider.discover=forbidden;c.app.state.reviewer.preflight=forbidden
    return c,w,e


def readiness(c,w):
    r=c.get('/api/auto-repair/'+w['id']+'/continuation-readiness')
    assert r.status_code==200,r.text
    return r.json()


def snapshot(root):
    return {str(p.relative_to(root)):digest(p.read_bytes()) for p in root.rglob('*') if p.is_file()}


def test_readiness_proves_actual_registered_review_without_writes(tmp_path):
    c,w,e=fixture(tmp_path)
    before=snapshot(tmp_path)
    r=readiness(c,w)
    assert r['eligible'] is True,r
    assert r['lifetime_iterations']==1
    assert r['best_candidate_id']==w['best_candidate_id']
    assert r['latest_candidate_id']==w['latest_candidate_id']
    assert r['best_evaluation_id']==e['id']
    proof=c.app.state.auto_repair.adapter.continuation_seed(w)
    assert all(proof[k] is True for k in ('registered','reviewed','valid','no_unknown_liabilities'))
    assert proof['frozen_sha256']==digest(canonical(w['frozen']))
    assert proof['registration']['measurements']['limits']==w['frozen']['registration_limits']
    assert snapshot(tmp_path)==before
    assert c.post('/api/auto-repair/'+w['id']+'/continue').status_code in (404,405)


def test_legacy_named_review_receipts_are_verified_not_label_rejected(tmp_path):
    import shutil
    c,w,e=fixture(tmp_path);g=c.app.state.generation
    with g.connect() as db:
        record=json.loads(db.execute('SELECT record FROM reviews WHERE id=?',(e['id'],)).fetchone()[0])
        record['id']='paid-pilot-02-verified-auth'
        db.execute('INSERT INTO reviews VALUES (?,?,?)',(record['id'],record['reserve_microusd'],canonical(record).decode()))
    shutil.copytree(tmp_path/'reviews'/e['id'],tmp_path/'reviews'/record['id'])
    before=snapshot(tmp_path)
    assert readiness(c,w)['eligible'] is True
    assert snapshot(tmp_path)==before
    g.policy['approved']=True;g.reserve_review('paid-pilot-01',100,{'retained':'unknown old hold'})
    before=snapshot(tmp_path)
    r=readiness(c,w)
    assert not r['eligible']
    assert 'unknown or unverifiable paid review receipt: paid-pilot-01' in r['blockers']
    assert snapshot(tmp_path)==before


def test_proof_under_engine_write_lock_never_recovers(tmp_path):
    c,w,e=fixture(tmp_path)
    service=c.app.state.auto_repair;g=service.g
    def forbidden(*a,**kw):raise AssertionError('no recovery or write during proof')
    g.resume=forbidden;g.save=forbidden;g.reserve_review=forbidden
    c.app.state.evaluations.recover=forbidden;c.app.state.evaluations.finish=forbidden
    c.app.state.evaluations.prepare=forbidden
    before=snapshot(tmp_path)
    with g.connect() as db:
        db.execute('BEGIN IMMEDIATE')
        proof=service.adapter.continuation_seed(w)
        assert proof['eligible'],proof
        assert json.loads(db.execute('SELECT record FROM reviews WHERE id=?',(e['id'],)).fetchone()[0])['status']=='reserved_unknown_until_receipt'
    assert snapshot(tmp_path)==before


def test_result_cannot_forge_receipt_decision(tmp_path):
    c,w,e=fixture(tmp_path)
    path=tmp_path/'evaluations'/e['id']/'result.json'
    result=json.loads(path.read_bytes())
    result['decision']['criteria']['materials']['verdict']='fail'
    result['sha256']=digest(canonical({k:v for k,v in result.items() if k!='sha256'}))
    path.write_bytes(canonical(result))
    # ev.get alone verifies hashes, but does not compare extracted decision to receipt.
    assert c.app.state.evaluations.get(e['id'])['status']=='reviewed'
    before=snapshot(tmp_path)
    r=readiness(c,w)
    assert not r['eligible']
    assert any('decision binding mismatch' in b for b in r['blockers'])
    assert snapshot(tmp_path)==before


def test_stale_freeze_cannot_emit_contract_accepted_proof(tmp_path):
    c,w,e=fixture(tmp_path)
    w['frozen']['gate_sha256']='a'*64
    proof=c.app.state.auto_repair.adapter.continuation_seed(w)
    assert not proof['eligible']
    assert proof['valid'] is False  # continue_run checks flags, not eligible


@pytest.mark.parametrize('damage,expected',[
    ('citation','materials: missing final evidence citation'),
    ('structured','invalid/missing structured model decision or applicable citations'),
    ('source','retained best candidate/source'),
    ('receipt','review receipt drift'),
    ('request','review request/metadata drift'),
    ('input','submitted review image drift'),
    ('evidence','review evidence integrity failure'),
    ('ledger','best review central ledger'),
    ('unknown_review','unknown or unverifiable paid review receipt'),
    ('unknown_job','unknown or unresolved paid generation intent'),
    ('registration','registration'),
    ('transform','registration'),
    ('measurement','registration_ambiguous: foreground missing'),
])
def test_fail_closed_readiness_damage(tmp_path,damage,expected):
    d=mock_decision()
    if damage=='citation':
        d['criteria']['materials']['verdict']='fail'
        d['criteria']['materials']['observations'][0]['evidence_ids']=['reference-0']
    if damage=='structured':d={'criteria':{},'findings':[]}
    c,w,e=fixture(tmp_path,decision=d,registered=damage!='registration',color=50 if damage=='measurement' else 180,translation=[8,0] if damage=='transform' else None)
    g=c.app.state.generation;eid=e['id']
    paths={'source':tmp_path/'terrain'/w['best_candidate_id']/'source.png','receipt':tmp_path/'reviews'/eid/'receipt.json','request':tmp_path/'reviews'/eid/'request.json','input':tmp_path/'reviews'/eid/'input-0.png','evidence':tmp_path/'evaluations'/eid/'final.png'}
    if damage in paths:paths[damage].write_bytes(b'corrupt secret=https://private.invalid/token')
    if damage=='ledger':
        with g.connect() as db:db.execute('DELETE FROM reviews WHERE id=?',(eid,))
    if damage=='unknown_review':g.policy['approved']=True;g.reserve_review('f'*64,100,{'secret':'must-not-leak'})
    if damage=='unknown_job':
        with g.connect() as db:db.execute('INSERT INTO jobs VALUES (?,?,?,?)',('f'*64,'f'*64,100,canonical({'status':'ambiguous','secret':'must-not-leak'}).decode()))
    before=snapshot(tmp_path)
    r=readiness(c,w)
    assert r['eligible'] is False,r
    assert any(expected in b for b in r['blockers']),r
    assert 'private.invalid' not in json.dumps(r) and 'must-not-leak' not in json.dumps(r)
    assert snapshot(tmp_path)==before
    if damage=='citation':
        assert c.app.state.evaluations.get(eid)['gate']['criteria']['materials']['verdict']=='fail'
        assert r['seed_proof']['valid'] is False


@pytest.mark.parametrize('rid',['wrong','A'*64,'b'*64])
def test_missing_malformed_run_is_readonly_denial(tmp_path,rid):
    c,w,e=fixture(tmp_path)
    before=snapshot(tmp_path)
    r=c.get('/api/auto-repair/'+rid+'/continuation-readiness')
    assert r.status_code==200
    assert r.json()['eligible'] is False and r.json()['blockers']
    assert snapshot(tmp_path)==before


def test_valid_fail_is_actionable_not_fabricated_pass(tmp_path):
    d=mock_decision();d['criteria']['materials']['verdict']='fail'
    c,w,e=fixture(tmp_path,decision=d)
    r=readiness(c,w)
    assert r['eligible'] is True,r
    assert not c.app.state.evaluations.get(e['id'])['gate']['production_approved']


@pytest.mark.parametrize('change',['cancel','limit','unknown_stop','malformed_record','malformed_best','frozen_style','density','revision'])
def test_run_contract_and_lifetime_denials(tmp_path,change):
    c,w,e=fixture(tmp_path);service=c.app.state.auto_repair
    if change=='cancel':w['cancel_requested']=True
    elif change=='limit':w['iterations']=w['iterations']*15
    elif change=='unknown_stop':w['stop_reason']='unknown_submission'
    elif change=='malformed_best':w['best_candidate_id']='../../secret'
    elif change in ('frozen_style','density','revision'):
        w['frozen'][{'frozen_style':'style','density':'density','revision':'revision'}[change]]=2 if change=='density' else 'f'*64
        w['root']=digest(canonical(w['frozen']))
    with service.g.connect() as db:
        db.execute('UPDATE auto_runs SET record=? WHERE id=?',('[]' if change=='malformed_record' else canonical(w).decode(),w['id']))
    before=snapshot(tmp_path)
    r=readiness(c,w)
    assert not r['eligible'] and r['blockers'],r
    if change=='limit':assert r['lifetime_iterations']==15
    assert snapshot(tmp_path)==before
