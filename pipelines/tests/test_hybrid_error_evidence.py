"""Offline transport regressions; synthetic failures are NOT the historical response."""
import json
import stat
import httpx
import pytest
import hybrid_models
from test_hybrid_transport import fixture

@pytest.mark.parametrize('status', [400, 401, 429, 503])
def test_http_failure_retained_privately_without_receipt_or_retry(tmp_path, monkeypatch, status):
    s,c,a,m,im=fixture(tmp_path)
    secret='synthetic-private-token'
    raw=json.dumps({'error':{'message':'synthetic server error '+secret,'code':status}}).encode()
    posts=[]
    def handler(request):
        posts.append(request)
        return httpx.Response(status,content=raw)
    client=httpx.Client
    monkeypatch.setenv('OPENROUTER_API_KEY',secret)
    monkeypatch.setattr(hybrid_models.httpx,'Client',lambda **kw:client(transport=httpx.MockTransport(handler),**kw))
    p=hybrid_models.OpenRouter('test/mock');p.preflight=lambda:m
    with pytest.raises(ValueError) as error:
        p.call(s,c,'planner','test',{'reference':im},{},a,m)
    assert 'HTTP '+str(status) in str(error.value)
    assert secret not in str(error.value)
    cid=s.calls(c['id'])[0]['id']
    directory=tmp_path/'hybrid-errors'/cid
    evidence=json.loads((directory/'diagnostic.json').read_text())
    assert evidence['http_status']==status
    assert evidence['kind']=='http_status'
    assert evidence['call_id']==cid
    assert evidence['request_sha256']
    assert evidence['billing']=='unsettled_hold_retained'
    assert (directory/'response.bin').read_bytes()==raw
    assert stat.S_IMODE(directory.stat().st_mode)==0o700
    assert stat.S_IMODE((directory/'response.bin').stat().st_mode)==0o600
    assert secret not in (directory/'diagnostic.json').read_text()
    assert s.calls(c['id'])[0]['receipt_known'] is False
    with pytest.raises(ValueError):p.call(s,c,'planner','test',{'reference':im},{},a,m)
    assert len(posts)==1
    assert (directory/'response.bin').read_bytes()==raw

@pytest.mark.parametrize('failure,kind',[(httpx.ReadTimeout,'timeout'),(httpx.ConnectError,'transport')])
def test_network_failure_distinct_from_http(tmp_path,monkeypatch,failure,kind):
    s,c,a,m,im=fixture(tmp_path)
    def handler(request):raise failure('private exception detail',request=request)
    client=httpx.Client
    monkeypatch.setenv('OPENROUTER_API_KEY','synthetic')
    monkeypatch.setattr(hybrid_models.httpx,'Client',lambda **kw:client(transport=httpx.MockTransport(handler),**kw))
    p=hybrid_models.OpenRouter('test/mock');p.preflight=lambda:m
    with pytest.raises(ValueError) as error:p.call(s,c,'planner','test',{'reference':im},{},a,m)
    assert 'private exception detail' not in str(error.value)
    cid=s.calls(c['id'])[0]['id']; directory=tmp_path/'hybrid-errors'/cid
    evidence=json.loads((directory/'diagnostic.json').read_text())
    assert evidence['kind']==kind and evidence['http_status'] is None
    assert not (directory/'response.bin').exists()
    assert not s.calls(c['id'])[0]['receipt_known']


def test_invalid_json_response_retains_original_bytes(tmp_path,monkeypatch):
    s,c,a,m,im=fixture(tmp_path)
    raw=b'<html>synthetic upstream response</html>'
    client=httpx.Client
    monkeypatch.setenv('OPENROUTER_API_KEY','synthetic')
    monkeypatch.setattr(hybrid_models.httpx,'Client',lambda **kw:client(transport=httpx.MockTransport(lambda request:httpx.Response(200,content=raw)),**kw))
    p=hybrid_models.OpenRouter('test/mock');p.preflight=lambda:m
    with pytest.raises(ValueError,match='response_decode'):p.call(s,c,'planner','test',{'reference':im},{},a,m)
    directory=tmp_path/'hybrid-errors'/s.calls(c['id'])[0]['id']
    assert (directory/'response.bin').read_bytes()==raw
    evidence=json.loads((directory/'diagnostic.json').read_text())
    assert evidence['http_status']==200 and evidence['kind']=='response_decode'
    assert not s.calls(c['id'])[0]['receipt_known']


def test_actual_plan_payload_has_schema_prompt_and_verified_image_before_post(tmp_path):
    import base64
    s,c,a,m,im=fixture(tmp_path)
    schema=hybrid_models.Plan.model_json_schema();posted=[]
    def post(method,path,body):
        assert method=='POST' and path=='/chat/completions'
        posted.append(body)
        return {'model':'test/mock','choices':[{'finish_reason':'stop','message':{'content':'{}'}}]}
    p=hybrid_models.OpenRouter('test/mock',post);p.preflight=lambda:m
    p.call(s,c,'planner','geometry description',{'reference':im},schema,a,m)
    body=posted[0]
    assert body['response_format']['type']=='json_schema'
    assert body['response_format']['json_schema']['strict'] is True
    assert json.loads(body['messages'][0]['content'].split('LOCAL_JSON_SCHEMA:\n')[1])==hybrid_models.strict_schema(schema)
    with s.g.connect() as db:
        retained=json.loads(db.execute('SELECT request FROM hybrid_calls WHERE run=?',(c['id'],)).fetchone()[0])
    assert retained['body']==body
    assert retained['transport_contract']=='openrouter-json-schema-strict-local-validation-v1'
    content=body['messages'][1]['content']
    assert content[0]['text']=='geometry description' and content[1]['text']=='evidence_id=reference'
    assert base64.b64decode(content[2]['image_url']['url'].split(',')[1])==im


def test_invalid_image_payload_fails_before_metadata_or_reservation(tmp_path):
    s,c,a,m,im=fixture(tmp_path)
    p=hybrid_models.OpenRouter('test/mock',lambda *args:pytest.fail('network forbidden'))
    with pytest.raises(Exception):p.call(s,c,'planner','test',{'reference':b'not an image'},{},a,m)
    assert s.calls(c['id'])==[]
