"""MOCK/temporary-root proof only: never live artwork or paid calls."""
import importlib.util
import json
from concurrent.futures import ThreadPoolExecutor
import pytest
from generation import Generation
from test_generation import MockProvider


class FakeAdapter:
    submissions=0
    reviews=0
    fail_registration=True
    unknown=False
    receipt=None
    def validate(self,w):pass
    def prepare(self,w,a):return {'id':a['style_spec_id']}
    def submit(self,w,a):
        assert self.service.get(w['id'])['styles'][w['styles'].index(a)]['phase']=='submitting'
        self.submissions+=1
        if self.unknown:raise RuntimeError('mock lost response')
        return {'id':a['quote_id'],'prediction_id':'mock-prediction','status':'submitted'}
    def recover(self,w,a):return self.receipt
    def poll(self,w,a):return dict(status='candidate_ready',candidate_id='source-'+a['style_spec_id'])
    def register(self,w,a):
        if self.fail_registration:return {'blocker':'registration_ambiguous: frozen 2.5px'}
        return {'candidate_id':'registered-'+a['style_spec_id']}
    def prepare_review(self,w,a):return {'id':'review-'+a['style_spec_id']}
    def review(self,w,a,recover=False):
        assert a['phase']=='reviewing'
        self.reviews+=1
        return dict(id=a['evaluation_id'],approved=False,valid=True,findings=[{'correction':'specific mock correction'}])
    def freeze(self, request):
        return dict(revision=request.revision, density=request.density,
                    styles=request.style_spec_ids, authorization_sha256='f'*64)


def setup(tmp_path):
    from overnight_batch import OvernightBatch, Start
    g=Generation(tmp_path,MockProvider(),{'approved':True,'total_usd':'10','max_attempts':7})
    with g.connect() as db:
        db.execute('CREATE TABLE auto_runs(id TEXT PRIMARY KEY, record TEXT)')
        db.execute('INSERT INTO auto_runs VALUES (?,?)',('old','immutable stopped run'))
    adapter=FakeAdapter()
    service=OvernightBatch(g,adapter)
    adapter.service=service
    request=Start(revision='a'*64,style_spec_ids=['b'*64,'c'*64],density=1,confirm_paid=True)
    return g,adapter,service,request


def test_scoped_durable_start(tmp_path):
    assert importlib.util.find_spec('overnight_batch'), 'scoped two-style service missing'
    from overnight_batch import OvernightBatch, Start
    g,a,s,req=setup(tmp_path)
    with ThreadPoolExecutor(4) as pool:
        runs=list(pool.map(lambda _:s.start(req),range(8)))
    assert len({r['id'] for r in runs})==1
    run=runs[0]
    assert OvernightBatch(g,a).start(req)==run
    assert len(run['styles'])==2
    assert run['limits']==dict(initial_per_style=1,repair_per_style=0,new_images=2,alltime_images=7)
    for change in [dict(revision='d'*64),dict(density=2),dict(style_spec_ids=['b'*64,'e'*64])]:
        with pytest.raises(ValueError):s.start(req.model_copy(update=change))
    for styles in [['b'*64],['b'*64,'b'*64],['b'*64,'c'*64,'d'*64]]:
        with pytest.raises(ValueError):Start(revision='a'*64,style_spec_ids=styles,confirm_paid=True)
    with pytest.raises(ValueError):Start(revision='a'*64,style_spec_ids=['b'*64,'c'*64],confirm_paid=False)
    with g.connect() as db:assert db.execute('SELECT record FROM auto_runs').fetchone()[0]=='immutable stopped run'


def drive(s,rid):
    for _ in range(30):
        w=s.tick(rid)
        if w['status']!='running':return w
    raise AssertionError('mock run did not terminate')


def test_registration_failure_preserves_both_sources_no_review(tmp_path):
    g,a,s,req=setup(tmp_path)
    assert hasattr(s,'tick'), 'durable batch worker missing'
    w=drive(s,s.start(req)['id'])
    assert a.submissions==2 and a.reviews==0
    assert w['status']=='blocked'
    for st in w['styles']:
        assert st['source_candidate_id']==st['candidate_id']
        assert st['source_candidate_id'] and st['evaluation_id'] is None
        assert 'registration_ambiguous' in st['stop_reason']
        assert st['journal']
    assert s.resume(w['id'])==w
    assert a.submissions==2


def test_unknown_submit_blocks_every_new_image_but_receipt_recovers(tmp_path):
    g,a,s,req=setup(tmp_path);a.unknown=True
    rid=s.start(req)['id'];s.tick(rid)
    w=s.tick(rid)
    assert w['status']=='needs_attention'
    assert w['styles'][0]['phase']=='submitting'
    assert a.submissions==1
    s.resume(rid);s.tick(rid)
    assert a.submissions==1
    a.receipt=dict(id=req.style_spec_ids[0],prediction_id='mock-recovered',status='submitted')
    a.unknown=False
    s.resume(rid)
    w=drive(s,rid)
    assert a.submissions==2
    assert w['styles'][0]['prediction_id']=='mock-recovered'


def test_strict_review_failure_stops_without_repair(tmp_path):
    g,a,s,req=setup(tmp_path);a.fail_registration=False
    w=drive(s,s.start(req)['id'])
    assert a.submissions==2 and a.reviews==2
    for st in w['styles']:
        assert st['evaluation_id'] and st['source_candidate_id']!=st['candidate_id']
        assert st['stop_reason']=='strict_review_failed; repairs disabled; no blind reroll'
    s.resume(w['id'])
    assert a.submissions==2


def real_adapter_fixture(tmp_path):
    """Real ledger + real immutable Styles; MOCK transports, tiny test images."""
    import io
    from types import SimpleNamespace as NS
    from PIL import Image
    from artifacts import canonical,digest
    from style_specs import Styles,StyleSpec
    from layout_core import generate
    from artifacts import export_files
    from overnight_batch import BatchAdapter,OvernightBatch,Start
    g=Generation(tmp_path,MockProvider(),{'approved':True,'total_usd':'10','max_attempts':7})
    refs={};paths=[];sids=[]
    styles=Styles(g,lambda sid:refs[sid])
    for i,color in enumerate(['red','green']):
        path=tmp_path/f'authorized-{i}.jpg';Image.new('RGB',(16,16),color).save(path);paths.append(path)
        out=io.BytesIO();Image.open(path).convert('RGB').save(out,format='PNG');raw=out.getvalue();sid=digest(raw)
        refs[sid]=({'source_sha256':digest(raw)},raw)
        sids.append(styles.save(StyleSpec(version=1,prompt=f'MOCK style {i}',references=[dict(reference_id=sid,role='style_only')]))['id'])
    auth=tmp_path/'AUTH.md';auth.write_text('MOCK authorization fixture: two styles')
    layout=generate(dict(width=16,height=14,seed=897,tile_width=32,density=1,actor_width=.6,kind='meadow',path='west-east',trees=0,houses=0,brief=''))
    revision=digest(canonical(layout));files=export_files(layout)
    meta=dict(id='mock-review',context_length=1000,pricing=dict(prompt='0.000001',completion='0.000001'),architecture=dict(input_modalities=['text','image'],output_modalities=['text']),supported_parameters=['response_format','temperature','max_tokens'])
    reviewer=NS(config=NS(enabled=True),preflight=lambda:meta,post=lambda _:pytest.fail('paid reviewer called'))
    app=NS(state=NS(generation=g,styles=styles,reviewer=reviewer,evaluations=NS()))
    adapter=BatchAdapter(app,lambda _:files,lambda _:None,lambda _:layout,lambda *_:None,lambda jid:g.public(g.resume(jid)),authorization_path=auth,reference_paths=paths)
    s=OvernightBatch(g,adapter)
    req=Start(revision=revision,style_spec_ids=sids,confirm_paid=True)
    return g,adapter,s,req,reviewer,auth


def test_real_adapter_scopes_initial_quote_and_central_image_hold(tmp_path):
    import overnight_batch
    assert hasattr(overnight_batch,'BatchAdapter'), 'real scoped adapter missing'
    g,a,s,req,reviewer,auth=real_adapter_fixture(tmp_path)
    w=s.start(req);rid=w['id']
    s.tick(rid);w=s.tick(rid)
    assert w['status']=='running' and w['styles'][0]['phase']=='poll'
    assert g.provider.submitted==1 and g.status()['reserved_usd']=='0.011'
    q=g.get_quote(w['styles'][0]['quote_id'])
    assert q['binding']['style_spec_id']==req.style_spec_ids[0]
    assert q['binding']['layout_revision']==req.revision
    assert q['binding']['overnight_batch_id']==rid
    assert all(r['role']!='correction_target' for r in q['binding']['style_references'])
    assert 'asphalt' not in q['binding']['prompt']
    auth.write_text('changed MOCK scope')
    w=s.tick(rid)
    assert w['status']=='needs_attention'
    assert g.provider.submitted==1


@pytest.mark.parametrize('drift',['wrong_reference','old_revision','oversized_cap','oversized_budget','exhausted_cap','submit_headroom'])
def test_real_adapter_fails_closed_scope_and_budget(tmp_path,drift):
    g,a,s,req,reviewer,auth=real_adapter_fixture(tmp_path)
    if drift=='wrong_reference':
        a.reference_paths[0].write_bytes(a.reference_paths[1].read_bytes())
        with pytest.raises(ValueError):s.start(req)
        return
    if drift=='old_revision':
        with g.connect() as db:db.execute('INSERT INTO jobs VALUES (?,?,?,?)',('old','old',11,json.dumps({'binding':{'layout_revision':req.revision}})))
        with pytest.raises(ValueError):s.start(req)
        return
    rid=s.start(req)['id']
    if drift=='oversized_cap':g.policy['max_attempts']=8
    if drift=='oversized_budget':g.policy['total_usd']='15'
    if drift=='exhausted_cap':g.policy['max_attempts']=0
    s.tick(rid)
    if drift=='submit_headroom':
        g.reserve_review('MOCK-other-review',9985000,{'label':'MOCK prior liability'})
    w=s.tick(rid)
    assert w['status']=='needs_attention'
    assert g.provider.submitted==0


def test_real_adapter_review_uses_exact_style_density_and_recovery_only(tmp_path):
    from types import SimpleNamespace as NS
    from production_gate import CRITERIA
    g,a,s,req,reviewer,auth=real_adapter_fixture(tmp_path)
    assert hasattr(a,'prepare_review'), 'durable pre-review binding missing'
    w=s.start(req);st=w['styles'][0];st['candidate_id']='mock-registered'
    calls=[]
    e=dict(id='mock-evaluation',status='prepared_unreviewed',binding=dict(source_sha256='mock-source'),gate=dict(production_approved=False,criteria={k:{'verdict':'fail'} for k in CRITERIA},blockers=['materials failed'],findings=[{'correction':'mock actionable'}]))
    def prepare(tid,sid,density):
        calls.append(('prepare',tid,sid,density));return e
    def run(eid,meta,post):calls.append(('run',eid));return {**e,'status':'reviewed'}
    def recover(eid):calls.append(('recover',eid));return {**e,'status':'reviewed'}
    a.ev=NS(prepare=prepare,run=run,recover=recover,get=lambda eid:e)
    st['evaluation_id']=a.prepare_review(w,st)['id']
    result=a.review(w,st)
    assert result['valid'] and not result['approved']
    assert result['findings']==e['gate']['findings']
    assert calls[0]==('prepare','mock-registered',req.style_spec_ids[0],1)
    a.review(w,st,recover=True)
    assert calls[-1]==('recover','mock-evaluation')
    assert sum(c[0]=='run' for c in calls)==1


def test_install_http_start_get_resume_and_single_worker(tmp_path,monkeypatch):
    import time
    import overnight_batch as module
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    g,a,s,req=setup(tmp_path)
    assert hasattr(module,'install'), 'install API missing'
    app=FastAPI();app.state.generation=g
    monkeypatch.setattr(module,'BatchAdapter',lambda *args:a)
    service=module.install(app,None,None,None,None,None);a.service=service
    with TestClient(app) as client:
        r=client.post('/api/overnight-batch/start',json=req.model_dump())
        assert r.status_code==201
        rid=r.json()['id']
        for _ in range(8):
            assert client.post('/api/overnight-batch/start',json=req.model_dump()).json()['id']==rid
            service.launch(rid)
        service.workers[rid].join(timeout=10)
        w=client.get('/api/overnight-batch/'+rid).json()
        assert w['status']=='blocked' and a.submissions==2
        assert client.post('/api/overnight-batch/'+rid+'/resume').json()==w
        assert client.get('/api/overnight-batch/'+'e'*64).status_code==409
        assert len(service.workers)==1


def test_quote_drift_does_not_authorize_different_prompt(tmp_path):
    g,a,s,req,reviewer,auth=real_adapter_fixture(tmp_path)
    rid=s.start(req)['id'];w=s.tick(rid);st=w['styles'][0]
    q=g.get_quote(st['quote_id'])
    changed=g.quote({**q['binding'],'prompt':'unauthorized changed style intent'})
    st['quote_id']=changed['id'];s.save(w)
    w=s.tick(rid)
    assert w['status']=='needs_attention' and g.provider.submitted==0


def test_review_preflight_rejects_expanded_central_ceiling(tmp_path):
    g,a,s,req,reviewer,auth=real_adapter_fixture(tmp_path)
    g.policy['total_usd']='15'
    with pytest.raises(ValueError):a.preflight()


def test_invalid_layout_cannot_bind_authorization(tmp_path):
    g,a,s,req,reviewer,auth=real_adapter_fixture(tmp_path)
    original=a.load(req.revision)
    a.load=lambda _: {**original,'goals':[]}
    with pytest.raises(ValueError):s.start(req)


def test_real_registration_failure_uses_frozen_estimator_no_app_import(tmp_path):
    import io
    import sys
    from PIL import Image
    g,a,s,req,reviewer,auth=real_adapter_fixture(tmp_path)
    w=s.start(req);st=w['styles'][0];st['candidate_id']='mock-source'
    folder=tmp_path/'terrain'/'mock-source';folder.mkdir(parents=True)
    out=io.BytesIO();Image.new('RGB',(128,128),'white').save(out,format='PNG')
    (folder/'source.png').write_bytes(out.getvalue())
    a.record=lambda _:{}
    before='app' in sys.modules
    result=a.register(w,st)
    assert 'registration_ambiguous' in result['blocker']
    assert ('app' in sys.modules)==before
    assert (folder/'source.png').read_bytes()==out.getvalue()


def test_free_reviewer_disabled_or_auth_failure_prevents_image(tmp_path):
    g,a,s,req,reviewer,auth=real_adapter_fixture(tmp_path)
    reviewer.config.enabled=False
    w=drive(s,s.start(req)['id'])
    assert w['status']=='needs_attention' and g.provider.submitted==0

def test_display_labels_preserve_historical_record_without_references(tmp_path):
    g,a,s,req=setup(tmp_path)
    w=drive(s,s.start(req)['id'])
    w['status']='completed'
    for st in w['styles']:st['status']='stopped'
    s.save(w)
    with g.connect() as db:before=db.execute('SELECT record FROM overnight_batches').fetchone()[0]
    a.validate=lambda _:pytest.fail('readback must not validate transient references')
    view=s.public(w['id'])
    assert view['status']=='completed' and view['display_status']=='blocked'
    assert view['terminal'] and not view['can_resume'] and not view['can_cancel']
    assert all(st['display_status']=='blocked' for st in view['styles'])
    assert s.resume(w['id'])==w
    with g.connect() as db:assert db.execute('SELECT record FROM overnight_batches').fetchone()[0]==before


def test_success_requires_both_strict_reviews(tmp_path):
    g,a,s,req=setup(tmp_path);a.fail_registration=False
    a.review=lambda w,st,recover=False:dict(approved=True,valid=True)
    w=drive(s,s.start(req)['id'])
    assert w['status']=='succeeded'
    assert all(st['status']=='succeeded' for st in w['styles'])

def test_cancel_durable_preserves_holds_and_inflight_receipt(tmp_path):
    from overnight_batch import OvernightBatch
    g,a,s,req=setup(tmp_path)
    g.reserve_review('unknown-old',12345,{'label':'MOCK unknown liability'})
    rid=s.start(req)['id'];s.tick(rid)
    def submit(w,st):
        a.submissions+=1
        s.cancel(rid)
        return dict(id=st['quote_id'],prediction_id='retained-receipt',status='submitted')
    a.submit=submit
    w=s.tick(rid)
    assert w['status']=='cancelled'
    assert w['styles'][0]['prediction_id']=='retained-receipt'
    assert w['styles'][0]['phase']=='poll'
    restarted=OvernightBatch(g,a)
    assert restarted.cancel(rid)==w
    assert restarted.resume(rid)==w
    assert restarted.tick(rid)==w
    assert a.submissions==1 and a.reviews==0
    assert g.status()['reserved_usd']=='0.012345'
    assert not restarted.public(rid)['can_resume']
    assert all(st['display_status']=='cancelled' for st in restarted.public(rid)['styles'])


def test_cancel_before_work_and_terminal_cancel_no_rewrite(tmp_path):
    g,a,s,req=setup(tmp_path)
    rid=s.start(req)['id'];w=s.cancel(rid)
    assert w['status']=='cancelled' and s.tick(rid)==w
    assert a.submissions==0
    with g.connect() as db:assert db.execute('SELECT record FROM auto_runs').fetchone()[0]=='immutable stopped run'

def test_http_saved_discovery_cancel_and_terminal_labels(tmp_path,monkeypatch):
    import overnight_batch as module
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    g,a,s,req=setup(tmp_path)
    app=FastAPI();app.state.generation=g
    monkeypatch.setattr(module,'BatchAdapter',lambda *args:a)
    service=module.install(app,None,None,None,None,None);a.service=service
    rid=service.start(req)['id']
    with TestClient(app) as c:
        result=c.get('/api/overnight-batch')
        assert result.status_code==200
        assert result.json()[0]['id']==rid
        assert result.json()[0]['can_cancel']
        cancelled=c.post('/api/overnight-batch/'+rid+'/cancel',json={})
        assert cancelled.status_code==200 and cancelled.json()['display_status']=='cancelled'
        assert c.get('/api/overnight-batch/'+rid).json()==cancelled.json()
        assert c.post('/api/overnight-batch/'+rid+'/resume',json={}).json()==cancelled.json()
    assert a.submissions==0
