"""Local image/HTTP tests use synthetic fixtures, NEVER presented as artwork."""
import importlib.util
import io
import numpy as np
from PIL import Image,ImageDraw
from artifacts import png

def test_conservative_registration_rejects_ambiguous_frame():
    assert importlib.util.find_spec('auto_adapter'),'automatic adapter missing'
    from auto_adapter import measure_registration
    guide=Image.new('RGBA',(120,80));ImageDraw.Draw(guide).polygon([(10,40),(60,15),(110,40),(60,65)],fill=(180,180,180,255))
    source=Image.new('RGB',(240,160));source.paste(guide.resize((240,160),Image.Resampling.NEAREST),mask=guide.resize((240,160),Image.Resampling.NEAREST).getchannel('A'))
    r=measure_registration(png(np.array(source)),png(np.array(guide)))
    assert not r.get('blocker') and abs(r['scale']-.5)<.02
    r=measure_registration(png(np.full((160,240,3),180,dtype=np.uint8)),png(np.array(guide)))
    assert r['blocker']

def test_api_start_is_background_and_deduplicates(tmp_path):
    from app import create_app
    from fastapi.testclient import TestClient
    app=create_app(tmp_path)
    assert hasattr(app.state,'auto_repair'),'auto repair API not installed'
    class A:
        def freeze(self,eid):return {'evaluation_id':eid,'candidate_id':'b'*64}
        def validate(self,w):raise ValueError('MOCK deliberately stopped')
    app.state.auto_repair.adapter=A()
    with TestClient(app) as c:
        html=c.get('/').text
        assert 'autoRepairStart' in html and 'autoRepairCancel' in html and 'autoRepairResume' in html
        r=c.post('/api/auto-repair/start',json={'evaluation_id':'a'*64,'confirm_paid':True})
        assert r.status_code==201,r.text
        rid=r.json()['id'];assert c.get('/api/auto-repair/'+rid).status_code==200
        assert c.post('/api/auto-repair/start',json={'evaluation_id':'a'*64,'confirm_paid':True}).json()['id']==rid
        assert c.post('/api/auto-repair/'+rid+'/cancel').status_code==200
        assert c.post('/api/auto-repair/'+rid+'/resume').status_code==200
