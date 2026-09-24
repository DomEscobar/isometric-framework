"""Labelled technical fixtures and mocked provider; no invented live decisions."""
import base64
import pytest
from fastapi.testclient import TestClient
from app import create_app
from test_generation import MockProvider


def setup(tmp_path):
    app=create_app(tmp_path,provider=MockProvider())
    c=TestClient(app)
    layout=c.post('/api/layouts',json={'kind':'urban'}).json()
    raw=c.get(f"/api/layouts/{layout['revision']}/artifacts/clean-guide.png").content
    ref=c.post('/api/styles',json={'png_base64':base64.b64encode(raw).decode(),'role':'style_only'}).json()
    spec={'version':1,'prompt':'Calm warm pixel ground','avoid':['speckle'],'materials':{'sidewalk':{'prompt':'Large warm slabs','reference_ids':[]}},'references':[{'reference_id':ref['id'],'role':'style_only','material':None,'crop':None}]}
    return c,layout,ref,spec,raw


def test_style_version_preset_quote_semantics(tmp_path):
    c,l,r,s,raw=setup(tmp_path)
    response=c.post('/api/style-specs',json=s)
    assert response.status_code==201,response.text
    first=response.json()
    assert c.put('/api/style-presets/calm',json={'style_spec_id':first['id']}).status_code==200
    s['materials']['sidewalk']['prompt']='Broad quiet cream slabs'
    second=c.post('/api/style-specs',json=s).json()
    assert second['id']!=first['id']
    c.put('/api/style-presets/calm',json={'style_spec_id':second['id']})
    assert c.get('/api/style-specs/'+first['id']).json()==first
    q=c.post('/api/generation/quote',json={'revision':l['revision'],'style_spec_id':second['id']})
    assert q.status_code==200,q.text
    assert q.json()['binding']['style_spec_id']==second['id']
    assert 'Broad quiet cream slabs' in q.json()['inputs_template']['prompt']
    assert 'speckle' in q.json()['inputs_template']['prompt']
    assert c.get('/api/layouts/'+l['revision']).json()==l


def test_production_requires_bound_review_diagnostic_label(tmp_path):
    c,l,r,s,raw=setup(tmp_path)
    t=c.post('/api/layouts/'+l['revision']+'/terrain',json={'png_base64':base64.b64encode(raw).decode(),'projection':l['layout']['projection']}).json()
    url=f"/api/terrain/{t['id']}/download?revision={l['revision']}&density=1"
    assert c.get(url+'&mode=production').status_code==409
    diagnostic=c.get(url+'&mode=diagnostic')
    assert diagnostic.status_code==200
    assert diagnostic.headers['X-Production-Approved']=='false'
    assert 'diagnostic' in diagnostic.headers['content-disposition']


def test_spec_reference_crop_reaches_exact_paid_request_mock(tmp_path):
    c,l,r,s,raw=setup(tmp_path)
    g=c.app.state.generation;g.policy={'approved':True,'total_usd':'1','max_attempts':2}
    s['references'][0]['crop']=[1,2,100,100]
    spec=c.post('/api/style-specs',json=s).json()
    q=c.post('/api/generation/quote',json={'revision':l['revision'],'style_spec_id':spec['id']}).json()
    j=c.post('/api/generation/confirm',json={'revision':l['revision'],'quote_id':q['id'],'style_spec_id':spec['id']})
    assert j.status_code==200,j.text
    assert j.json()['status']=='submitted',j.text
    assert g.get(j.json()['id'])['binding']['style_spec_id']==spec['id']
    stale=c.post('/api/generation/confirm',json={'revision':l['revision'],'quote_id':q['id'],'style_spec_id':'a'*64})
    assert stale.status_code==422


@pytest.mark.parametrize('change', ['unknown','crop','material','role','avoid','version','preset'])
def test_invalid_spec_references(tmp_path,change):
    c,l,r,s,raw=setup(tmp_path)
    if change=='unknown':s['ignored_style_parameter']='not allowed'
    if change=='crop':s['references'][0]['crop']=[0,0,99999,1]
    if change=='material':s['materials']['sidewalk']['reference_ids']=[r['id']]
    if change=='role':s['references'][0]['role']='geometry_authority'
    if change=='avoid':s['avoid']=['x']*25
    if change=='version':s['version']=2
    if change=='preset':
        spec=c.post('/api/style-specs',json=s).json()
        assert c.put('/api/style-presets/invalid name',json={'style_spec_id':spec['id']}).status_code==422
    else:assert c.post('/api/style-specs',json=s).status_code==422


def test_material_crops_share_retained_source(tmp_path):
    c,l,r,s,raw=setup(tmp_path)
    s['references'].append({'reference_id':r['id'],'role':'material_only','material':'sidewalk','crop':[10,10,80,80]})
    s['materials']['sidewalk']['reference_ids']=[r['id']]
    res=c.post('/api/style-specs',json=s)
    assert res.status_code==201,res.text
    assert res.json()['reference_lineage'][1]['crop']==[10,10,80,80]


def test_secondary_reference_source_drift_blocks_job(tmp_path):
    c,l,r,s,raw=setup(tmp_path)
    g=c.app.state.generation;g.policy={'approved':True,'total_usd':'1','max_attempts':2}
    s['references'].append({'reference_id':r['id'],'role':'material_only','material':'sidewalk','crop':[10,10,80,80]})
    s['materials']['sidewalk']['reference_ids']=[r['id']]
    spec=c.post('/api/style-specs',json=s).json()
    q=c.post('/api/generation/quote',json={'revision':l['revision'],'style_spec_id':spec['id']}).json()
    j=c.post('/api/generation/confirm',json={'revision':l['revision'],'quote_id':q['id'],'style_spec_id':spec['id']}).json()
    assert len(q['roles'])==3
    assert q['roles'][2]=='material_only sidewalk'
    sha=spec['reference_lineage'][1]['input_sha256']
    (tmp_path/'generation-sources'/(sha+'.png')).write_bytes(b'changed secondary crop')
    with pytest.raises(ValueError,match='source'):g.get(j['id'])


def test_soil_is_valid_material_and_version_not_boolean(tmp_path):
    c,l,r,s,raw=setup(tmp_path)
    s['materials']['soil']={'prompt':'Quiet earth clusters','reference_ids':[]}
    assert c.post('/api/style-specs',json=s).status_code==201
    s['version']=True
    assert c.post('/api/style-specs',json=s).status_code==422
