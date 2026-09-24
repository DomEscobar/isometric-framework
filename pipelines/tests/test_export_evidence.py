import json,io,zipfile,base64
from fastapi.testclient import TestClient
from app import create_app
from artifacts import canonical,digest
from test_generation import MockProvider

def test_export_includes_verified_provider_request_and_review(tmp_path):
 p=MockProvider();p.poll=lambda pid:{'id':pid,'status':'completed','outputs':['https://example.org/output.png']}
 with TestClient(create_app(tmp_path,provider=p,policy={'approved':True,'total_usd':'1','max_attempts':1})) as c:
  v=c.post('/api/layouts',json={}).json();rid=v['revision'];raw=c.get(f'/api/layouts/{rid}/artifacts/clean-guide.png').content;p.download=lambda _:raw
  style=c.post('/api/styles',json={'png_base64':base64.b64encode(raw).decode(),'role':'style_only'}).json()
  q=c.post('/api/generation/quote',json={'revision':rid,'style_id':style['id'],'prompt':'MOCK transport evidence only'}).json();j=c.post('/api/generation/confirm',json={'revision':rid,'quote_id':q['id']}).json();j=c.post(f"/api/generation/jobs/{j['id']}/resume",json={}).json();t=c.get('/api/terrain/'+j['candidate_id']).json()
  review={'candidate_id':t['id'],'layout_revision':rid,'source_sha256':t['source_sha256'],'guide_sha256':t['guide_sha256'],'status':'needs_attention','production_approved':False,'model_review':{'fixture':True},'technical_verdict':'pass','semantic_verdict':'needs_attention','visual_verdict':'needs_attention'};review['id']=digest(canonical(review));(tmp_path/'terrain'/t['id']/'review.json').write_bytes(canonical(review))
  z=zipfile.ZipFile(io.BytesIO(c.get(f"/api/terrain/{t['id']}/download?revision={rid}").content))
  assert 'generation/request-provenance.json' in z.namelist(), 'provider request/quote missing from actual export'
  assert z.read('sources/style-only.png')==raw
  evidence=json.loads(z.read('generation/request-provenance.json'))
  assert evidence['request_sha256']==j['request_sha256']
  assert 'image_urls' not in evidence['request_without_media_urls']
  assert json.loads(z.read('review.json'))==review
  assert c.get(f"/api/terrain/{t['id']}/review").json()==review
  review['candidate_id']='wrong';(tmp_path/'terrain'/t['id']/'review.json').write_bytes(canonical(review))
  assert c.get(f"/api/terrain/{t['id']}/download?revision={rid}").status_code==409
