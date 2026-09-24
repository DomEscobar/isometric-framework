"""Transport-free MOCK state-machine tests, not live artwork evidence."""
import importlib.util
import pytest
from concurrent.futures import ThreadPoolExecutor
from generation import Generation
from test_generation import MockProvider


def test_durable_deduplicated_start_and_bounds(tmp_path):
    assert importlib.util.find_spec('auto_repair'), 'automatic repair service missing'
    from auto_repair import AutoRepair, Start
    g=Generation(tmp_path,MockProvider(),{'approved':True,'total_usd':'10','max_attempts':17})
    class Adapter:
        def freeze(self,eid):return {'evaluation_id':eid,'candidate_id':'b'*64,'revision':'c'*64,'style':'d'*64,'density':1,'gate_version':'strict-v1'}
    s=AutoRepair(g,Adapter())
    request=Start(evaluation_id='a'*64,confirm_paid=True,max_iterations=15)
    with ThreadPoolExecutor(4) as pool: runs=list(pool.map(lambda _:s.start(request),range(8)))
    assert len({r['id'] for r in runs})==1
    assert AutoRepair(g,Adapter()).start(request)==runs[0]
    assert Start(evaluation_id='a'*64,confirm_paid=True).max_iterations==3
    with pytest.raises(ValueError):Start(evaluation_id='a'*64,confirm_paid=True,max_iterations=16)
    with pytest.raises(ValueError):Start(evaluation_id='a'*64,confirm_paid=False)
    # A changed cap cannot reset the lifetime run counter.
    assert s.start(Start(evaluation_id='a'*64,confirm_paid=True,max_iterations=3))['id']==runs[0]['id']
