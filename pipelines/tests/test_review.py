import pytest
from PIL import Image
from artifacts import digest
from generation import Generation
from test_generation import MockProvider

def test_review_retains_real_receipt_and_never_reposts(tmp_path):
    import importlib.util
    assert importlib.util.find_spec('review'), 'bounded grounded review workflow missing'
    from review import run_review
    g=Generation(tmp_path,MockProvider(),{'approved':True,'total_usd':'1','max_attempts':1})
    img=tmp_path/'image.png';Image.new('RGB',(48,24)).save(img)
    calls=[]
    def post(body):
        calls.append(body)
        return {'id':'test-receipt','model':'test-vision','choices':[{'message':{'content':'{"semantic_verdict":"needs_attention","visual_verdict":"needs_attention","findings":["test fixture only"]}'}}],'usage':{'cost':0.0001}}
    meta={'id':'test-vision','context_length':1000,'pricing':{'prompt':'0.000001','completion':'0.000001'},'architecture':{'input_modalities':['image','text']}}
    r=run_review(g,'test-review',[(img,'guide')],'Test fixture only',meta,post,max_tokens=100)
    assert r['response']['id']=='test-receipt'
    assert r['inputs'][0]['sha256']==digest(img.read_bytes())
    assert g.status()['review_reserved_usd']=='0.0011'
    with pytest.raises(ValueError,match='already'):run_review(g,'test-review',[(img,'guide')],'Test fixture only',meta,post,max_tokens=100)
    assert len(calls)==1

def test_unclear_review_remains_attention():
    from review import verdict
    for content in ['', 'OK', '{"semantic_verdict":"pass"}', '{"semantic_verdict":"pass","visual_verdict":"pass","findings":[]}']:
        v=verdict(content)
        assert v['production_approved'] is False
        assert v['status']=='needs_attention'
