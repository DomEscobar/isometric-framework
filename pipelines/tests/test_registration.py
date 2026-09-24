import base64,io,json,zipfile
import numpy as np
from PIL import Image
from fastapi.testclient import TestClient
from app import create_app

def test_explicit_uniform_registration_preserves_original_and_collision(tmp_path):
 with TestClient(create_app(tmp_path)) as c:
  v=c.post('/api/layouts',json={}).json();rid=v['revision'];p=v['layout']['projection']
  # Technical synthetic resized guide, never production evidence.
  raw=c.get(f'/api/layouts/{rid}/artifacts/clean-guide.png').content
  im=Image.open(io.BytesIO(raw));b=io.BytesIO();im.resize((im.width*2,im.height*2),Image.Resampling.NEAREST).save(b,format='PNG');original=b.getvalue()
  t=c.post(f'/api/layouts/{rid}/terrain',json={'png_base64':base64.b64encode(original).decode(),'projection':p}).json()
  assert t['status']=='rejected'
  payload={'scale':0.5,'translation':[0.0,0.0],'notes':'Known 2x technical fixture; explicit uniform transform, not semantic approval.'}
  response=c.post(f"/api/terrain/{t['id']}/register",json=payload)
  assert response.status_code==201,response.text
  reg=response.json();assert reg['id']!=t['id'];assert reg['status']=='needs_attention';assert reg['parent_candidate_id']==t['id']
  assert c.get(f"/api/terrain/{t['id']}").json()==t
  assert c.get(f"/api/terrain/{reg['id']}/source.png").content==original
  assert c.get(f'/api/layouts/{rid}').json()==v
  preview=c.get(f"/api/terrain/{reg['id']}/preview.png");assert preview.status_code==200
  assert np.array_equal(np.array(Image.open(io.BytesIO(preview.content))),np.array(im.convert('RGBA')))
  z=zipfile.ZipFile(io.BytesIO(c.get(f"/api/terrain/{reg['id']}/download?revision={rid}&density=2").content))
  assert z.read('sources/original.png')==original
  assert np.array_equal(np.array(Image.open(io.BytesIO(z.read('terrain.png')))),np.array(Image.open(io.BytesIO(original)).convert('RGBA')))
  provenance=json.loads(z.read('terrain-provenance.json'))
  assert provenance['processing']['registration']['scale']==0.5
  for bad in [{**payload,'scale':[0.5,0.6]},{**payload,'scale':0},{**payload,'translation':[0.0]},{**payload,'scale_x':0.5}]:
   assert c.post(f"/api/terrain/{t['id']}/register",json=bad).status_code==422
