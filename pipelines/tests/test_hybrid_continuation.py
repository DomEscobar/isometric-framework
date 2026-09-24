import json,time,base64
import pytest
from artifacts import canonical,digest
from generation import Generation
from hybrid_store import Store
from hybrid_worker import immutable
from hybrid_models import Plan
from test_hybrid_layout import sample

def parent(tmp_path):
    s=Store(Generation(tmp_path,None,{'total_usd':'10'}))
    actor=(__import__('hybrid_artifact').ACTOR/'character.png').read_bytes()
    cfg=dict(mode='live',planner_model='test/model',reviewer_model='test/model',description='test description',constraints={k:sample()[k] for k in ['width','height','actor_width']},reference_sha256=digest(b'ref'),reference_original_sha256=digest(b'ref'),actor_sha256=digest(actor),shadow_sha256=digest(b'shadow'),max_images=1,max_calls=5,max_local_corrections=0,max_seconds=1800,budget_microusd=3000000)
    r=s.create('parent',cfg);r=s.claim()
    plan=dict(layout=sample(),material_plan=dict(intent='test material intent',materials={'land':'grass','wall':'stone'},avoid=[],uncertainty=[]),interpretation='test plan',unsupported=[])
    inputs=[dict(id=n,sha256=digest(v)) for n,v in [('actor',actor),('reference',b'ref')]]
    content=[]
    for n,v in [('actor',actor),('reference',b'ref')]:content.extend([dict(type='text',text='evidence_id='+n),dict(type='image_url',image_url={'url':'data:image/png;base64,'+base64.b64encode(v).decode()})])
    req=dict(body={'model':'test/model','messages':[{},dict(content=content)]},metadata={'id':'test/model'},inputs=inputs)
    auth={**cfg,'config_sha256':digest(canonical(cfg)),'expires':time.time()+500}
    call=s.reserve_call(r,'planner',req,100,auth)
    s.receipt(call['id'],dict(id='gen-test',model='test/model',choices=[dict(finish_reason='stop',message={'content':json.dumps(plan)})]))
    immutable(tmp_path/'hybrid'/r['id']/'planner-result.json',canonical(Plan.model_validate(plan).model_dump()))
    s.save(r,phase='needs_attention');s.release(r)
    return s,r,call

def test_worker_consumes_parent_automatically_without_planner(tmp_path,monkeypatch):
    from hybrid_recovery import continue_planner
    from hybrid_worker import Worker
    from hybrid_models import OpenRouter
    s,r,c=parent(tmp_path);child=continue_planner(s,r['id'],'child',2000000,1800)
    immutable(tmp_path/'hybrid-authorizations'/(child['id']+'.json'),canonical({**child['config'],'config_sha256':digest(canonical(child['config'])),'expires':time.time()+500}))
    monkeypatch.setattr(OpenRouter,'preflight',lambda self:{'id':self.model})
    monkeypatch.setattr(OpenRouter,'call',lambda *a,**kw:pytest.fail('must not buy planner'))
    monkeypatch.setattr('hybrid_reference.reference_bytes',lambda *a:(b'ref',None))
    Worker(s).tick()
    child=s.get(child['id'])
    assert child['phase']=='generating',child.get('stop_reason')
    assert child['call_count']==1 and s.calls(child['id'])==[]
    assert (tmp_path/'hybrid'/child['id']/'planner-result.json').read_bytes()==(tmp_path/'hybrid'/r['id']/'planner-result.json').read_bytes()

def test_known_image_recovers_before_metadata(tmp_path,monkeypatch):
    from hybrid_worker import Worker
    from hybrid_models import MaterialImage
    s,parent_run,c=parent(tmp_path);cfg=parent_run['config'];r=s.create('image-test',cfg);r=s.claim()
    auth={**cfg,'config_sha256':digest(canonical(cfg)),'expires':time.time()+500}
    immutable(tmp_path/'hybrid-authorizations'/(r['id']+'.json'),canonical(auth))
    request=dict(attempt=0,body={'test':'exact'},schema={},quote={},amount=100)
    s.save(r,phase='generating',metadata={'planner':{},'reviewer':{}},accepted_layout=sample(),frozen_sha256=digest(canonical({'config':cfg,'layout':sample()})),material_plan={'materials':{'land':'grass','wall':'stone'}},prepared_image=request)
    call=s.reserve_call(r,'image-0',request,100,auth);s.receipt(call['id'],{'id':'test-known-image'});s.release(r)
    monkeypatch.setattr('hybrid_reference.reference_bytes',lambda *a:(b'ref',None))
    monkeypatch.setattr(MaterialImage,'discover',lambda *a:pytest.fail('no metadata for known receipt'))
    Worker(s).tick();after=s.get(r['id'])
    assert after['phase']=='polling' and after['prediction_id']=='test-known-image'
    assert len(s.calls(r['id']))==1

def test_concurrent_successor_is_unique_and_stale_paid_claim_blocks(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    from hybrid_recovery import continue_planner
    s,r,c=parent(tmp_path)
    def create(key):
        try:return continue_planner(s,r['id'],key,2000000,1800)['id']
        except ValueError:return None
    with ThreadPoolExecutor(2) as pool:ids=list(pool.map(create,['one','two']))
    assert sum(x is not None for x in ids)==1
    child=s.claim();auth={**child['config'],'config_sha256':digest(canonical(child['config'])),'expires':time.time()+500}
    with pytest.raises(ValueError):s.reserve_call({**child,'fence':child['fence']-1},'image-0',{},100,auth)
    with pytest.raises(ValueError):s.reserve_call(child,'planner',{},100,auth)
    for i in range(4):
        call=s.reserve_call(child,'stage-'+str(i),{'test':i},100,auth);s.receipt(call['id'],{'id':'test-'+str(i)})
    assert s.get(child['id'])['call_count']==5
    with pytest.raises(ValueError,match='Aufruflimit'):s.reserve_call(child,'extra',{},100,auth)

def test_service_continuation_and_no_manual_plan(tmp_path):
    from fastapi.testclient import TestClient
    from hybrid_api import create_app
    s,r,c=parent(tmp_path);client=TestClient(create_app(s))
    url='/api/hybrid-runs/'+r['id']+'/continue'
    body=dict(budget_microusd=2000000,max_seconds=1800,confirm_paid=True)
    response=client.post(url,json=body,headers={'Idempotency-Key':'child'})
    assert response.status_code==201,response.text
    assert response.json()['config']['continuation']['parent_id']==r['id']
    assert client.post(url,json={**body,'plan':{}},headers={'Idempotency-Key':'bad'}).status_code==422

@pytest.mark.parametrize('drift',['receipt','request','ledger','plan','parent'])
def test_continuation_revalidates_every_bound_byte(tmp_path,drift):
    from hybrid_recovery import continue_planner,validated_parent
    s,r,c=parent(tmp_path);child=continue_planner(s,r['id'],'child',2000000,1800)
    with s.g.connect() as db:
        if drift=='receipt':db.execute('UPDATE hybrid_calls SET receipt=? WHERE id=?',('{}',c['id']))
        if drift=='request':db.execute('UPDATE hybrid_calls SET request=? WHERE id=?',('{}',c['id']))
        if drift=='ledger':db.execute('UPDATE reviews SET reserve=101 WHERE id=?',(c['id'],))
        if drift=='parent':db.execute("UPDATE hybrid_runs SET record=replace(record,'test','changed') WHERE id=?",(r['id'],));db.execute('UPDATE hybrid_runs SET cancel=1 WHERE id=?',(r['id'],))
    if drift=='plan':(tmp_path/'hybrid'/r['id']/'planner-result.json').write_text('{}')
    with pytest.raises((ValueError,KeyError)):validated_parent(s,child['config']['continuation'])

def test_continuation_immutable_receipt_and_lifetime(tmp_path):
    s,r,c=parent(tmp_path);before=s.get(r['id'])
    from hybrid_recovery import continue_planner,validated_parent
    child=continue_planner(s,r['id'],'child',2000000,1800)
    assert child['config']['mode']=='live' and child['call_count']==1
    assert child['config']['max_calls']==5
    assert validated_parent(s,child['config']['continuation'])[1]['layout']==sample()
    assert s.get(r['id'])==before
    assert continue_planner(s,r['id'],'child',2000000,1800)['id']==child['id']
    with pytest.raises(ValueError):continue_planner(s,r['id'],'another',2000000,1800)
    with s.g.connect() as db:db.execute('UPDATE hybrid_calls SET receipt=? WHERE id=?',('{}',c['id']))
    with pytest.raises(ValueError):validated_parent(s,child['config']['continuation'])
