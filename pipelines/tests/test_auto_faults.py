"""Additional MOCK fault injections; no paid requests."""
from test_auto_engine import service,drain
from auto_adapter import Adapter

def test_cancel_during_submission_retains_reservation(tmp_path):
    s,a,rid=service(tmp_path)
    def submit(w,it):
        s.g.reserve_review('mock-liability',12345,{'mock':True})
        s.cancel(rid)
        return {'id':'mock-job','status':'submitted'}
    a.submit=submit
    w=drain(s,rid)
    assert w['status']=='cancelled'
    assert s.g.status()['reserved_usd']=='0.012345'
    assert w['iterations'][0]['job_id']=='mock-job'

def test_stuck_poll_and_stagnation_stop(tmp_path):
    s,a,rid=service(tmp_path)
    a.poll=lambda w,a:{'id':a['job_id'],'status':'processing'}
    assert drain(s,rid)['stop_reason'].startswith('poll_limit') and a.submits==1
    s,a,rid=service(tmp_path/'stagnant')
    a.review=lambda w,it:dict(id='ev',approved=False,valid=True,score=[0]*4,source_sha256=str(it['number']),blockers=['fail'])
    assert drain(s,rid)['stop_reason'].startswith('stagnation') and a.submits==2

def test_global_transform_is_free_registration_not_reroll():
    class E:
        def get(self,eid):return {'gate':{'production_approved':False,'findings':[dict(criterion='layout_fidelity',blocking=True,observation='MOCK global offset of all terrain',correction='Correct translation with uniform scale')]}}
    a=object.__new__(Adapter);a.ev=E()
    p=a.plan({'evaluation_id':'mock','latest_candidate_id':'source','iterations':[]})
    assert p['action']=='register'
    assert p['provider_fields']==['prompt','image_urls','output_format']
