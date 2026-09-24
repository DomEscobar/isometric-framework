"""All model responses in this module are labelled mocks, NOT live evidence."""
import importlib.util
import pytest

CRITERIA=('layout_fidelity','materials','pixel_style','walkable_clearance')

def mock_decision():
    return {'criteria':{k:{'verdict':'pass','observations':[{'observation':'MOCK ONLY: visible edge and surface are consistent.','location':'center at 10,10','evidence_ids':['final','guide','reference-0']}]} for k in CRITERIA},'findings':[]}

@pytest.mark.parametrize('criterion',CRITERIA)
@pytest.mark.parametrize('verdict',['fail','uncertain'])
def test_each_criterion_blocks_aggregate(criterion,verdict):
    assert importlib.util.find_spec('production_gate'),'strict gate missing'
    from production_gate import assess
    d=mock_decision();d['criteria'][criterion]['verdict']=verdict
    assert assess(d,{'final','guide','reference-0'},[])['production_approved'] is False


def test_missing_citations_and_local_blocks():
    assert importlib.util.find_spec('production_gate'),'strict gate missing'
    from production_gate import assess
    d=mock_decision()
    assert assess(d,{'final','guide','reference-0'},[])['production_approved'] is True
    assert not assess(d,{'final','guide'},[])['production_approved']
    assert not assess(d,{'final','guide','reference-0'},['local blocking overlap'])['production_approved']
    d['criteria']['materials']['observations']=[]
    assert not assess(d,{'final','guide','reference-0'},[])['production_approved']


def test_immutable_evaluation_stale_hash_and_exact_inputs(tmp_path):
    from test_style_gate import setup
    import base64,json
    c,l,r,s,raw=setup(tmp_path)
    spec=c.post('/api/style-specs',json=s).json()
    t=c.post('/api/layouts/'+l['revision']+'/terrain',json={'png_base64':base64.b64encode(raw).decode(),'projection':l['layout']['projection']}).json()
    req={'style_spec_id':spec['id'],'density':1}
    res=c.post('/api/terrain/'+t['id']+'/evaluations',json=req)
    assert res.status_code==201,res.text
    ev=res.json();eid=ev['id']
    assert ev['binding']['style_spec_id']==spec['id']
    assert ev['binding']['candidate_id']==t['id']
    assert {'final','guide','reference-0'}.issubset({i['id'] for i in ev['binding']['evidence']})
    assert c.get('/api/evaluations/'+eid).json()['gate']['production_approved'] is False
    assert c.get('/api/terrain/'+t['id']).json()==t
    c.app.state.generation.policy={'approved':True,'total_usd':'10','max_attempts':2}
    meta={'id':'mock/labelled-vision','architecture':{'input_modalities':['text','image'],'output_modalities':['text']},'supported_parameters':['response_format','temperature','max_tokens'],'pricing':{'prompt':'0.000001','completion':'0.000001'},'context_length':10000}
    decision=mock_decision()
    def post(body):
        assert 'Before returning, audit each criterion' in body['messages'][0]['content'][0]['text']
        return {'id':'mock-only','model':meta['id'],'choices':[{'finish_reason':'stop','message':{'content':json.dumps(decision)}}],'usage':{'cost':0.00001}}
    c.app.state.evaluations.run(eid,meta,post)
    saved=(tmp_path/'evaluations'/eid/'result.json').read_bytes()
    (tmp_path/'evaluations'/eid/'result.json').unlink() # MOCK crash after durable receipt
    assert hasattr(c.app.state.evaluations,'recover'), 'receipt-only review recovery missing'
    c.app.state.evaluations.recover(eid)
    assert (tmp_path/'evaluations'/eid/'result.json').read_bytes()==saved
    # Technical guide fixture is a local blocker even when the mocked model says all PASS.
    assert not c.get('/api/evaluations/'+eid).json()['gate']['production_approved']
    with pytest.raises(ValueError,match='attempted'):
        c.app.state.evaluations.run(eid,meta,post)
    (tmp_path/'terrain'/t['id']/'source.png').write_bytes(b'changed')
    assert c.get('/api/evaluations/'+eid).status_code in (409,422)


def test_reviewer_config_validates_live_capabilities_before_paid_call(tmp_path):
    assert importlib.util.find_spec('reviewer_provider'),'configured review adapter missing'
    from reviewer_provider import Reviewer
    calls=[]
    def request(method,path,body=None):
        calls.append((method,path))
        if path=='/auth/key':return {}
        return {'data':[{'id':'google/gemini-3.8-flash','architecture':{'input_modalities':['text'],'output_modalities':['text']}}]}
    provider=Reviewer(tmp_path,request=request)
    with pytest.raises(ValueError,match='image'):provider.preflight()
    assert calls==[('GET','/auth/key'),('GET','/models')]


def test_production_export_requires_exact_style_density_and_review(tmp_path):
    from test_style_gate import setup
    import base64,json,io
    from PIL import Image
    c,l,r,s,raw=setup(tmp_path)
    im=Image.open(io.BytesIO(raw)).convert('RGBA');pix=im.load()
    for x in range(im.width):
        for y in range(im.height):
            if pix[x,y][3]:pix[x,y]=(90,110,80,255)
    stream=io.BytesIO();im.save(stream,format='PNG')
    t=c.post('/api/layouts/'+l['revision']+'/terrain',json={'png_base64':base64.b64encode(stream.getvalue()).decode(),'projection':l['layout']['projection']}).json()
    spec=c.post('/api/style-specs',json=s).json()
    eid=c.post('/api/terrain/'+t['id']+'/evaluations',json={'style_spec_id':spec['id'],'density':1}).json()['id']
    c.app.state.generation.policy={'approved':True,'total_usd':'10','max_attempts':2}
    meta={'id':'mock/labelled-vision','architecture':{'input_modalities':['text','image'],'output_modalities':['text']},'supported_parameters':['response_format','temperature','max_tokens'],'pricing':{'prompt':'0.000001','completion':'0.000001'},'context_length':10000}
    result=c.app.state.evaluations.run(eid,meta,lambda b:{'model':meta['id'],'choices':[{'finish_reason':'stop','message':{'content':json.dumps(mock_decision())}}],'usage':{'cost':0.00001}})
    assert result['gate']['production_approved'],result['gate']
    url=f"/api/terrain/{t['id']}/download?revision={l['revision']}&mode=production&evaluation_id={eid}&style_spec_id={spec['id']}"
    assert c.get(url+'&density=1').status_code==200
    assert c.get(url+'&density=2').status_code==409
    assert c.get(url.replace(spec['id'],'a'*64)+'&density=1').status_code==409
    (tmp_path/'reviews'/eid/'request.json').write_text('{}')
    assert c.get(url+'&density=1').status_code==409


def test_paid_review_requires_explicit_confirmation(tmp_path):
    from test_style_gate import setup
    c,*_=setup(tmp_path)
    assert c.post('/api/evaluations/'+'a'*64+'/review',json={'confirm_paid':False}).status_code==422
    assert c.post('/api/evaluations/'+'a'*64+'/review',json={'confirm_paid':1}).status_code==422
    assert c.get('/api/reviewer/config').json()['enabled'] is False


def test_bad_citation_blocks_without_erasing_real_verdict():
    from production_gate import assess
    d=mock_decision();d['criteria']['materials']['verdict']='fail'
    d['criteria']['materials']['observations'][0]['evidence_ids']=['reference-0']
    gate=assess(d,{'final','guide','reference-0'},[])
    assert not gate['production_approved']
    assert gate['criteria']['materials']['verdict']=='fail'
    assert 'materials: fail' in gate['blockers']
    assert 'materials: missing final evidence citation' in gate['blockers']
