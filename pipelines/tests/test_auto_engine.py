"""MOCK adapters exercise real durable engine and locks; no provider quality claims."""
import threading
from concurrent.futures import ThreadPoolExecutor
import pytest
from auto_repair import AutoRepair,Start
from generation import Generation
from test_generation import MockProvider

class Adapter:
    def __init__(self):self.submits=0;self.n=0;self.approved=False;self.nochange=False;self.error=None
    def freeze(self,eid):return dict(evaluation_id=eid,candidate_id='b'*64,revision='c'*64,style='d'*64,density=1)
    def validate(self,w):
        if self.error:raise ValueError(self.error)
    def plan(self,w):return {'prompt':'MOCK change '+str(len(w['iterations'])),'findings':['material'], 'action':'generate'}
    def prepare(self,w,a):return {'id':'q'+str(a['number'])}
    def submit(self,w,a):self.submits+=1;return {'id':a['quote_id'],'status':'submitted'}
    def recover(self,w,a):return None
    def poll(self,w,a):return {'id':a['job_id'],'status':'candidate_ready','candidate_id':('b'*64 if self.nochange else str(a['number']).zfill(64))}
    def register(self,w,a):return {'candidate_id':a['candidate_id'],'measurements':{'mock':True}}
    def review(self,w,a):return {'id':'ev'+str(a['number']),'approved':self.approved,'score':[a['number']]*4,'source_sha256':a['candidate_id'],'blockers':[] if self.approved else ['MOCK fail'],'valid':True}
    def baseline(self,w):return {'score':[0]*4,'source_sha256':'b'*64}

def service(tmp_path):
    g=Generation(tmp_path,MockProvider(),{'approved':True,'total_usd':'10','max_attempts':17});a=Adapter();s=AutoRepair(g,a)
    w=s.start(Start(evaluation_id='a'*64,confirm_paid=True,max_iterations=15));return s,a,w['id']

def drain(s,rid):
    for _ in range(180):
        w=s.tick(rid)
        if w['status']!='running':return w
    raise AssertionError('stuck')

def test_cap_across_resume_and_concurrent_workers(tmp_path):
    s,a,rid=service(tmp_path)
    assert hasattr(s,'tick'),'durable background tick missing'
    with ThreadPoolExecutor(4) as p:list(p.map(lambda _:s.tick(rid),range(20)))
    s=AutoRepair(s.g,a);s.resume(rid);w=drain(s,rid)
    assert len(w['iterations'])==15 and a.submits==15
    assert w['stop_reason']=='iteration_limit'
    assert s.resume(rid)['status']=='needs_attention'

def test_success_cancel_nochange_stale(tmp_path):
    s,a,rid=service(tmp_path);a.approved=True
    w=drain(s,rid);assert w['status']=='succeeded' and a.submits==1
    s,a,rid=service(tmp_path/'cancel');s.cancel(rid);assert drain(s,rid)['status']=='cancelled' and a.submits==0
    s,a,rid=service(tmp_path/'same');a.nochange=True
    assert drain(s,rid)['stop_reason']=='unchanged_source' and a.submits==1
    s,a,rid=service(tmp_path/'stale');a.error='stale references'
    assert 'stale references' in drain(s,rid)['stop_reason'] and a.submits==0

def test_crash_before_or_after_receipt_never_resubmits(tmp_path):
    for receipt in (False,True):
        s,a,rid=service(tmp_path/str(receipt));s.tick(rid);s.tick(rid)
        w=s.get(rid);w['phase']='submitting';s.save(w)
        if receipt:a.recover=lambda w,a:{'id':a['quote_id'],'status':'submitted'}
        w=drain(s,rid) if not receipt else s.tick(rid)
        assert a.submits==0
        assert w['stop_reason']=='unknown_submission' if not receipt else w['phase']=='poll'

def test_exhausted_budget_no_post_and_regression_not_promoted(tmp_path):
    s,a,rid=service(tmp_path)
    def exhausted(w,a):raise ValueError('budget exhausted')
    a.prepare=exhausted
    w=drain(s,rid);assert a.submits==0 and 'budget exhausted' in w['stop_reason']
    s,a,rid=service(tmp_path/'regress')
    a.review=lambda w,a:dict(id='bad',approved=False,score=[-1]*4,source_sha256='new',blockers=['uncertain'],valid=False)
    w=drain(s,rid);assert w['best_candidate_id']=='b'*64 and w['status']=='needs_attention'
    assert a.submits==1

def test_launch_deduplicates_background_threads(tmp_path):
    s,a,rid=service(tmp_path)
    entered=threading.Event();release=threading.Event()
    def validate(w):entered.set();release.wait(3);raise ValueError('MOCK stop')
    a.validate=validate
    s.launch(rid);assert entered.wait(2)
    assert hasattr(s,'workers'),'background launch registry missing'
    thread=s.workers[rid]
    for _ in range(5):s.launch(rid)
    assert s.workers[rid] is thread
    release.set();thread.join(4)
