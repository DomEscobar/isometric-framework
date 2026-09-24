import json
import pytest
from artifacts import canonical,digest
from hybrid_models import OpenRouter
from test_hybrid_transport import fixture

def test_frozen_32768_medium_policy_is_sent_and_fully_reserved(tmp_path):
    s,c,a,m,im=fixture(tmp_path)
    policy={'max_tokens':32768,'reasoning_effort':'medium'}
    cfg={**c['config'],'token_policy':{'extraction':policy,'review':policy}}
    with s.g.connect() as db:db.execute('UPDATE hybrid_runs SET config=? WHERE id=?',(canonical(cfg).decode(),c['id']))
    c=s.get(c['id']);a['config_sha256']=digest(canonical(cfg))
    m.update(reasoning={'mandatory':True,'supported_efforts':['low','medium','high']},top_provider={'max_completion_tokens':65536})
    m['supported_parameters']=['reasoning']
    sent=[]
    def post(method,path,body):
        sent.append(body);return {'model':'test/mock','choices':[{'finish_reason':'stop','message':{'content':'{}'}}]}
    p=OpenRouter('test/mock',post);p.preflight=lambda:m
    p.call(s,c,'extraction-0','test',{'reference':im},{},a,m)
    assert sent[0]['max_tokens']==32768 and sent[0]['reasoning']=={'effort':'medium'}
    assert s.calls(c['id'])[0]['amount']==p.cost(m,32768)

@pytest.mark.parametrize('cap,effort',[(65537,'medium'),(32768,'disabled')])
def test_policy_rejects_unsupported_before_purchase(tmp_path,cap,effort):
    s,c,a,m,im=fixture(tmp_path)
    c['config']['token_policy']={'extraction':{'max_tokens':cap,'reasoning_effort':effort}}
    m.update(reasoning={'supported_efforts':['medium']},top_provider={'max_completion_tokens':65536})
    p=OpenRouter('test/mock',lambda *a:pytest.fail('no POST'))
    with pytest.raises(ValueError):p.call(s,c,'extraction-0','test',{}, {},a,m)
    assert s.calls(c['id'])==[]
