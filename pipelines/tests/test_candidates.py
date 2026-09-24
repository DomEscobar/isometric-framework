import base64
import io
import json
import zipfile
from fastapi.testclient import TestClient
from app import create_app
from artifacts import digest


def setup(c):
    v = c.post('/api/layouts', json={}).json()
    raw = c.get('/api/layouts/'+v['revision']+'/artifacts/clean-guide.png').content
    t = c.post('/api/layouts/'+v['revision']+'/terrain', json={'png_base64':base64.b64encode(raw).decode(),'projection':v['layout']['projection']}).json()
    return v, raw, t


def test_candidate_export_bound_original_diagnostics(tmp_path):
    with TestClient(create_app(tmp_path)) as c:
        v, raw, t = setup(c)
        assert t.get('guide_sha256') == digest(raw), 'immutable guide binding missing'
        assert t['image_checks']['semantic_verdict'] == 'unverified'
        url = f"/api/terrain/{t['id']}/download?revision={v['revision']}&density=2"
        r = c.get(url)
        assert r.status_code == 200, r.text
        assert r.content == c.get(url).content
        with zipfile.ZipFile(io.BytesIO(r.content)) as z:
            assert z.read('sources/original.png') == raw
            p = json.loads(z.read('terrain-provenance.json'))
            assert p['production_approved'] is False
            assert p['processing']['from_original'] is True
            assert p['processing']['density'] == 2
            for name, sha in json.loads(z.read('checksums.json')).items():
                assert digest(z.read(name)) == sha
        assert c.get(url.replace(v['revision'], '0'*64)).status_code == 409
        path = tmp_path/'terrain'/t['id']/'record.json'
        record = json.loads(path.read_bytes()); record['decoded_size'][0] += 1
        path.write_text(json.dumps(record))
        assert c.get(url).status_code == 409


def test_style_explicit_role_quote_and_no_budget(tmp_path):
    with TestClient(create_app(tmp_path)) as c:
        v,raw,t=setup(c)
        payload={'png_base64':base64.b64encode(raw).decode()}
        assert c.post('/api/styles',json=payload).status_code == 422
        result=c.post('/api/styles',json={**payload,'role':'style_only'})
        assert result.status_code == 201, result.text
        style=result.json()
        assert style['role']=='style_only'
        assert c.get('/api/styles/'+style['id']).json()==style
        assert c.get('/api/styles/'+style['id']+'/source.png').content==raw
        status=c.get('/api/generation/status').json()
        assert status['enabled'] is False
        assert 'budget' in ' '.join(status['reasons'])
        # Missing budget is checked before any external upload/generation.
        assert c.post('/api/generation/confirm',json={'quote_id':'0'*64,'revision':v['revision']}).status_code in (403,422)


def test_wrong_size_source_drift_and_density(tmp_path):
    from PIL import Image
    with TestClient(create_app(tmp_path)) as c:
        v,raw,t=setup(c)
        url=f"/api/terrain/{t['id']}/download?revision={v['revision']}"
        assert c.get(url+'&density=3').status_code==422
        (tmp_path/'terrain'/t['id']/'source.png').write_bytes(b'changed')
        assert c.get(url).status_code==409
        out=io.BytesIO();Image.new('RGBA',(20,20)).save(out,format='PNG')
        bad=c.post('/api/layouts/'+v['revision']+'/terrain',json={'png_base64':base64.b64encode(out.getvalue()).decode(),'projection':v['layout']['projection']}).json()
        assert bad['status']=='rejected'
        assert c.get(f"/api/terrain/{bad['id']}/download?revision={v['revision']}").status_code==422


def test_legacy_import_export_fails_closed_without_mutation(tmp_path):
    from artifacts import canonical
    with TestClient(create_app(tmp_path)) as c:
        v,raw,t=setup(c)
        legacy={k:val for k,val in t.items() if k not in ('id','guide_sha256','image_checks')}
        tid=digest(canonical(legacy));legacy['id']=tid
        directory=tmp_path/'terrain'/tid;directory.mkdir()
        (directory/'source.png').write_bytes(raw)
        (directory/'record.json').write_bytes(canonical(legacy))
        assert c.get('/api/terrain/'+tid).json()==legacy
        r=c.get(f"/api/terrain/{tid}/download?revision={v['revision']}")
        assert r.status_code==422
        assert 're-import' in r.json()['detail']
        assert (directory/'record.json').read_bytes()==canonical(legacy)
