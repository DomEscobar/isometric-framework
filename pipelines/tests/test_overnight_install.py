from fastapi.testclient import TestClient
from app import create_app


def test_create_app_installs_scoped_batch_api(tmp_path):
    app = create_app(tmp_path, policy={'approved':False,'total_usd':'0','max_attempts':0})
    with TestClient(app) as c:
        paths=c.get('/openapi.json').json()['paths']
        assert '/api/overnight-batch/start' in paths
        assert c.post('/api/overnight-batch/start',json={'revision':'a'*64,'style_spec_ids':['b'*64,'c'*64],'confirm_paid':False}).status_code == 422
        assert c.get('/api/overnight-batch/'+'d'*64).status_code == 409
