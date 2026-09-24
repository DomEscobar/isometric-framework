import json,time,io
import pytest
from PIL import Image
from artifacts import canonical,digest
from hybrid_worker import Worker,immutable
from hybrid_models import OpenRouter
from test_hybrid_continuation import parent

def source_parent(tmp_path,monkeypatch):
    from hybrid_recovery import continue_planner
    s,r,c=parent(tmp_path);child=continue_planner(s,r['id'],'image-child',2000000,1800)
    a={**child['config'],'config_sha256':digest(canonical(child['config'])),'expires':time.time()+500}
    immutable(tmp_path/'hybrid-authorizations'/(child['id']+'.json'),canonical(a))
    monkeypatch.setattr(OpenRouter,'preflight',lambda self:{'id':self.model})
    monkeypatch.setattr('hybrid_reference.reference_bytes',lambda *a:(b'ref',None))
    Worker(s).tick();r=s.claim()
    buf=io.BytesIO();Image.new('RGB',(32,32)).save(buf,format='PNG');source=buf.getvalue()
    req={'body':{},'amount':100};call=s.reserve_call(r,'image-0',req,100,a);s.receipt(call['id'],{'id':'image-real-test'})
    extraction={'body':{'model':'test/model','max_tokens':8192},'inputs':[{'id':'board','sha256':digest(source)}]}
    call=s.reserve_call(r,'extraction-0',extraction,100,a);s.receipt(call['id'],{'id':'gen-truncated','model':'test/model','choices':[{'finish_reason':'length','message':{'content':'{'}}]})
    immutable(tmp_path/'hybrid'/r['id']/'source-0.png',source)
    s.save(r,phase='needs_attention',prepared_image=req,prediction_id='image-real-test',source_sha256=digest(source));s.release(r)
    return s,r

def test_source_continuation_no_new_plan_image_inherits_three_calls(tmp_path,monkeypatch):
    from hybrid_source_recovery import continue_source
    s,r=source_parent(tmp_path,monkeypatch);before=s.get(r['id'])
    child=continue_source(s,r['id'],'source-child',1900000,1800,'standing user repair plus token increase')
    assert child['call_count']==3 and child['image_count']==1 and child['config']['max_calls']==6
    assert child['config']['token_policy']['extraction']['max_tokens']==32768
    immutable(tmp_path/'hybrid-authorizations'/(child['id']+'.json'),canonical({**child['config'],'config_sha256':digest(canonical(child['config'])),'expires':time.time()+500}))
    monkeypatch.setattr(OpenRouter,'call',lambda *a:pytest.fail('no POST during inheritance'))
    Worker(s).tick();after=s.get(child['id'])
    assert after['phase']=='extracting',after.get('stop_reason')
    assert after['prediction_id']=='image-real-test'
    assert s.get(r['id'])==before
    assert (tmp_path/'hybrid'/child['id']/'source-0.png').read_bytes()==(tmp_path/'hybrid'/r['id']/'source-0.png').read_bytes()
    with pytest.raises(ValueError):continue_source(s,r['id'],'duplicate',1900000,1800,'same')
    claim=s.claim();auth={**child['config'],'config_sha256':digest(canonical(child['config'])),'expires':time.time()+500}
    with pytest.raises(ValueError):s.reserve_call(claim,'image-1',{},100,auth)
    with pytest.raises(ValueError):s.reserve_call(claim,'planner',{},100,auth)
    for role in ['extraction-0','review_sample-0','review_final-0']:
        call=s.reserve_call(claim,role,{'test':role},100,auth);s.receipt(call['id'],{'id':role})
    assert s.get(child['id'])['call_count']==6
    with pytest.raises(ValueError,match='Aufruflimit'):s.reserve_call(claim,'extra',{},100,auth)

@pytest.mark.parametrize('drift',['source','receipt','ledger','guide'])
def test_source_continuation_drift_closes_before_paid(tmp_path,monkeypatch,drift):
    from hybrid_source_recovery import continue_source
    from hybrid_recovery import validated_parent
    s,r=source_parent(tmp_path,monkeypatch);child=continue_source(s,r['id'],'child',1900000,1800,'standing authority')
    if drift=='source':(tmp_path/'hybrid'/r['id']/'source-0.png').write_bytes(b'changed')
    if drift=='guide':(tmp_path/'hybrid'/r['id']/s.get(r['id'])['guide_file']).write_bytes(b'changed')
    with s.g.connect() as db:
        call=db.execute("SELECT id FROM hybrid_calls WHERE run=? AND role='image-0'",(r['id'],)).fetchone()[0]
        if drift=='receipt':db.execute('UPDATE hybrid_calls SET receipt=? WHERE id=?',('{}',call))
        if drift=='ledger':db.execute('UPDATE reviews SET reserve=1 WHERE id=?',(call,))
    with pytest.raises((ValueError,KeyError)):validated_parent(s,child['config']['continuation'])
