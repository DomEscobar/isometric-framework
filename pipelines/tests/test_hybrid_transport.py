"""Transport mocks only: never presented as provider/live acceptance."""
import json,time,io
import pytest
from PIL import Image
from generation import Generation
from provider import WaveSpeed
from hybrid_store import Store
from hybrid_models import OpenRouter
from artifacts import canonical,digest

def fixture(tmp):
    s=Store(Generation(tmp,WaveSpeed(key=''),{'total_usd':'10','approved':False}));s.create('test',{'mode':'live'});c=s.claim()
    a={'config_sha256':digest(canonical(c['config'])),'budget_microusd':100000,'max_images':3,'max_calls':4,'expires':time.time()+60}
    meta={'id':'test/mock','context_length':100,'pricing':{'prompt':'0.000001','completion':'0.000001'}}
    b=io.BytesIO();Image.new('RGB',(8,8)).save(b,format='PNG')
    return s,c,a,meta,b.getvalue()
def test_metadata_price_drift_blocks_new_call(tmp_path):
    s,c,a,m,im=fixture(tmp_path)
    p=OpenRouter('test/mock',lambda *args: (_ for _ in ()).throw(AssertionError('no POST allowed')))
    p.preflight=lambda:{**m,'pricing':{**m['pricing'],'prompt':'1'}}
    with pytest.raises(ValueError,match='Metadaten'):p.call(s,c,'planner','test',{'reference':im},{},a,m)
    assert s.calls(c['id'])==[]

def test_known_receipt_recover_no_duplicate_post(tmp_path):
    s,c,a,m,im=fixture(tmp_path);posts=[]
    def post(method,path,body):posts.append(body);return {'id':'mock-response','model':'test/mock','choices':[{'finish_reason':'stop','message':{'content':'{"ok":true}'}}]}
    p=OpenRouter('test/mock',post);p.preflight=lambda:m
    assert p.call(s,c,'planner','test',{'reference':im},{},a,m)=={'ok':True}
    assert p.call(s,c,'planner','test',{'reference':im},{},a,m)=={'ok':True}
    assert len(posts)==1

def test_unknown_post_blocks_retries_and_other_calls(tmp_path):
    s,c,a,m,im=fixture(tmp_path);posts=[]
    def post(*args):posts.append(1);raise TimeoutError('mock uncertain network')
    p=OpenRouter('test/mock',post);p.preflight=lambda:m
    with pytest.raises(TimeoutError):p.call(s,c,'planner','test',{'reference':im},{},a,m)
    with pytest.raises(ValueError):p.call(s,c,'planner','test',{'reference':im},{},a,m)
    with pytest.raises(ValueError):p.call(s,c,'review','new',{'reference':im},{},a,m)
    assert len(posts)==1 and s.calls(c['id'])[0]['receipt_known'] is False

def test_image_order_stable_across_restarts(tmp_path):
    s,c,a,m,im=fixture(tmp_path);posts=[]
    def post(method,path,body):posts.append(body);return {'id':'mock-response','model':'test/mock','choices':[{'finish_reason':'stop','message':{'content':'{}'}}]}
    p=OpenRouter('test/mock',post);p.preflight=lambda:m
    p.call(s,c,'review','test',{'reference':im,'final':im},{},a,m)
    p.call(s,c,'review','test',{'final':im,'reference':im},{},a,m)
    assert len(posts)==1,'image order drift must not trigger another paid POST'
    with pytest.raises(ValueError):p.call(s,c,'review','changed prompt',{'final':im,'reference':im},{},a,m)
