"""Bounded repair state tests. All providers and model decisions are labelled mocks."""
import importlib.util
import pytest

def test_repair_off_noop_cap_and_ambiguous(tmp_path):
    assert importlib.util.find_spec('corrections'),'bounded corrections missing'
    from corrections import Corrections,CorrectionRequest
    from generation import Generation
    from test_generation import MockProvider
    from artifacts import digest
    p=MockProvider();g=Generation(tmp_path,p,{'approved':True,'total_usd':'1','max_attempts':3})
    evaluation={'id':'a'*64,'status':'reviewed','binding':{'candidate_id':'b'*64,'layout_revision':'c'*64,'style_spec_id':'d'*64},'gate':{'production_approved':False,'findings':[{'criterion':'materials','correction':'Use calmer large slabs','observation':'MOCK: noisy tiny paving','location':'center','evidence_ids':['final'],'blocking':True}]}}
    class E:
        def get(self,eid):return evaluation
    def submit(workflow,prompt):
        b={'layout_revision':'c'*64,'guide_sha256':digest(b'g'),'style_id':'s','style_sha256':digest(b's'),'prompt':prompt,'correction_id':workflow['id']}
        q=g.quote(b);return g.confirm(q['id'],'c'*64,b'g',b's')
    service=Corrections(g,E(),submit)
    with pytest.raises(ValueError,match='opt-in'):service.create(CorrectionRequest(evaluation_id='a'*64))
    w=service.create(CorrectionRequest(evaluation_id='a'*64,enabled=True,max_attempts=1))
    p.ambiguous=True
    result=service.step(w['id'],'a'*64)
    assert result['status']=='ambiguous'
    with pytest.raises(ValueError,match='ambiguous|cap'):service.step(w['id'],'a'*64)
    assert p.submitted==1
    evaluation['gate']['findings']=[]
    with pytest.raises(ValueError,match='no-op'):service.create(CorrectionRequest(evaluation_id='a'*64,enabled=True,max_attempts=2))


def test_repair_shared_budget_blocks_submit(tmp_path):
    assert importlib.util.find_spec('corrections'),'bounded corrections missing'
    from corrections import Corrections,CorrectionRequest
    from generation import Generation
    from test_generation import MockProvider
    from artifacts import digest
    p=MockProvider();g=Generation(tmp_path,p,{'approved':True,'total_usd':'0.01','max_attempts':2})
    ev={'status':'reviewed','binding':{'candidate_id':'b'*64,'layout_revision':'c'*64,'style_spec_id':'d'*64},'gate':{'production_approved':False,'findings':[{'correction':'MOCK: use large slabs','blocking':True}]}}
    class E:
        def get(self,eid):return ev
    def submit(w,prompt):
        q=g.quote({'layout_revision':'c'*64,'guide_sha256':digest(b'g'),'style_id':'s','style_sha256':digest(b's'),'prompt':prompt})
        return g.confirm(q['id'],'c'*64,b'g',b's')
    service=Corrections(g,E(),submit)
    w=service.create(CorrectionRequest(evaluation_id='a'*64,enabled=True,max_attempts=2))
    result=service.step(w['id'],'a'*64)
    assert result['status']=='blocked';assert p.submitted==0
    with pytest.raises(ValueError):service.step(w['id'],'a'*64)


def test_successful_attempt_cap_and_unchanged_source_noop(tmp_path):
    from corrections import Corrections,CorrectionRequest
    from generation import Generation
    from test_generation import MockProvider
    g=Generation(tmp_path,MockProvider(),{'approved':True,'total_usd':'1','max_attempts':3})
    base={'status':'reviewed','binding':{'candidate_id':'b'*64,'layout_revision':'c'*64,'style_spec_id':'d'*64,'source_sha256':'f'*64},'gate':{'production_approved':False,'findings':[{'correction':'MOCK: large quiet slabs','blocking':True}]}}
    next_ev={**base,'binding':{**base['binding'],'candidate_id':'e'*64}}
    class E:
        def get(self,eid):return base if eid=='a'*64 else next_ev
    calls=[]
    def submit(w,prompt):calls.append(w['id']);return {'id':'mock-job','status':'submitted'}
    service=Corrections(g,E(),submit)
    w=service.create(CorrectionRequest(evaluation_id='a'*64,enabled=True,max_attempts=1))
    assert service.step(w['id'],'a'*64)['status']=='submitted'
    with pytest.raises(ValueError,match='cap'):service.step(w['id'],'a'*64)
    assert len(calls)==1
    w2=service.create(CorrectionRequest(evaluation_id='a'*64,enabled=True,max_attempts=2));service.step(w2['id'],'a'*64)
    g.get=lambda jid:{'status':'candidate_ready','candidate_id':'e'*64} # explicitly labelled state fixture
    with pytest.raises(ValueError,match='unchanged source'):service.step(w2['id'],'9'*64)
    assert len(calls)==2
