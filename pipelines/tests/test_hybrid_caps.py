import time,pytest,json
from artifacts import canonical,digest
from generation import Generation
from provider import WaveSpeed
from hybrid_store import Store

@pytest.mark.parametrize('cap',[3,15])
def test_image_lifetime_cap_survives_reopen(tmp_path,cap):
    g=Generation(tmp_path,WaveSpeed(key=''),{'total_usd':'10','approved':False});s=Store(g);s.create('bounded',{'mode':'live'});c=s.claim()
    auth={'config_sha256':digest(canonical(c['config'])),'budget_microusd':1000,'max_images':cap,'max_calls':64,'expires':time.time()+60}
    for i in range(cap):
        s=Store(g);v=s.reserve_call(c,'image-'+str(i),{'attempt':i},1,auth);s.receipt(v['id'],{'id':'mock-'+str(i)})
    assert s.get(c['id'])['image_count']==cap
    s.resume(c['id'])
    with pytest.raises(ValueError,match='Bildlimit'):s.reserve_call(c,'image-'+str(cap),{'attempt':cap},1,auth)
    assert s.get(c['id'])['image_count']==cap

def test_expired_auth_and_after_cancel_never_reserve(tmp_path):
    s=Store(Generation(tmp_path,WaveSpeed(key=''),{'total_usd':'10','approved':False}));s.create('one',{});c=s.claim()
    a={'config_sha256':digest(canonical(c['config'])),'expires':time.time()-1,'budget_microusd':100,'max_calls':4,'max_images':3}
    with pytest.raises(ValueError):s.reserve_call(c,'planner',{},1,a)
    a['expires']=time.time()+60;s.cancel(c['id'])
    with pytest.raises(ValueError):s.reserve_call(c,'planner',{},1,a)
    assert s.calls(c['id'])==[]
