import importlib.util
import io
import base64
import copy
from PIL import Image


def test_http_generate_download_validate_and_readback(tmp_path):
    assert importlib.util.find_spec('app'), 'HTTP service missing'
    from app import create_app
    from fastapi.testclient import TestClient
    with TestClient(create_app(tmp_path)) as c:
        assert c.get('/').status_code == 200
        result = c.post('/api/layouts',json={'brief':'Teich im Nordosten; Weg West-Ost; 1 Haus','seed':19})
        assert result.status_code == 201, result.text
        value = result.json()
        rid = value['revision']
        assert c.get('/api/layouts/'+rid).json() == value
        assert c.post('/api/layouts',json={'brief':'Berge und Brücke'}).status_code == 422
        assert c.post('/api/layouts',json={'waterfalls':3}).status_code == 422
        assert c.put('/api/layouts/'+rid,json={}).status_code == 405
        assert c.get('/api/layouts/'+rid+'/download').content[:2] == b'PK'
        assert c.get('/api/layouts/'+rid+'/artifacts/clean-guide.png').headers['content-type'] == 'image/png'
        damaged = copy.deepcopy(value['layout'])
        damaged['projection']['density'] = 8
        assert not c.post('/api/validate',json=damaged).json()['valid']
        assert c.get('/api/capabilities').json()['paid_generation'] is False
        assert c.get('/api/layouts/'+'0'*64).status_code == 404


def test_local_terrain_boundary_never_claims_visual_pass(tmp_path):
    assert importlib.util.find_spec('app'), 'HTTP service missing'
    from app import create_app
    from fastapi.testclient import TestClient
    with TestClient(create_app(tmp_path)) as c:
        value = c.post('/api/layouts',json={}).json()
        rid = value['revision']
        guide = c.get('/api/layouts/'+rid+'/artifacts/clean-guide.png').content
        body = dict(png_base64=base64.b64encode(guide).decode(), projection=value['layout']['projection'])
        result = c.post('/api/layouts/'+rid+'/terrain',json=body)
        assert result.status_code == 201, result.text
        terrain = result.json()
        assert terrain['registration']['declared_frame'] == 'matches'
        assert terrain['registration']['image_alignment'] == 'unverified'
        assert terrain['local_semantic_compliance'] == 'not_assessed'
        assert terrain['status'] == 'needs_attention'
        assert c.get('/api/terrain/'+terrain['id']).json() == terrain
        assert c.get('/api/terrain/'+terrain['id']+'/source.png').content == guide
        body['projection']['origin_px'][0] += 24
        bad = c.post('/api/layouts/'+rid+'/terrain',json=body).json()
        assert bad['status'] == 'rejected'
        assert bad['registration']['declared_frame'] == 'mismatch'
        stream = io.BytesIO()
        Image.new('RGBA',(20,20)).save(stream,format='PNG')
        body['png_base64'] = base64.b64encode(stream.getvalue()).decode()
        bad_size = c.post('/api/layouts/'+rid+'/terrain',json=body).json()
        assert bad_size['registration']['decoded_dimensions'] == 'mismatch'
