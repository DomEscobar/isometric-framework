import json
import importlib.util,pytest
from generation import Generation
from provider import WaveSpeed
from hybrid_store import Store

def test_production_requires_bound_actual_model_receipts(tmp_path):
    assert importlib.util.find_spec('hybrid_export'), 'production receipt gate missing'
    from hybrid_export import production_bundle
    s=Store(Generation(tmp_path,WaveSpeed(key='')))
    r=s.create('forged',{'mode':'live'});c=s.claim();s.save(c,phase='succeeded',production_approved=True)
    with pytest.raises(ValueError):production_bundle(s,s.get(r['id']))


def test_export_decision_must_unwrap_wire_form_criteria():
    # v29 live stop: the sample review returned criteria as {key,value} wire
    # entries (valid transport form); the flow-time gate unwrapped it but the
    # production export re-parsed raw JSON and rejected it ('Review-JSON
    # ungültig'). Both paths must share one normalization.
    from hybrid_export import decision_from_response
    from hybrid_models import CRITERIA,review_gate
    def entry(key):
        return {'key':key,'value':{'verdict':'pass','evidence_ids':['final','guide'] if key in ['layout_fidelity','walkable_clearance'] else ['final','reference'],'observation':'matches guide','correction':'None.'}}
    wire={'choices':[{'finish_reason':'stop','message':{'content':json.dumps({'criteria':[entry(k) for k in sorted(CRITERIA)],'local_sampling':None})}}]}
    decision=decision_from_response(wire)
    assert decision['criteria']['layout_fidelity']['verdict']=='pass'
    gate=review_gate(decision,{'final':'a','guide':'b','reference':'c'})
    assert gate['approved'],gate['reasons']
    native_form={k:entry(k)['value'] for k in sorted(CRITERIA)}
    native={'choices':[{'finish_reason':'stop','message':{'content':json.dumps({'criteria':native_form})}}]}
    assert decision_from_response(native)['criteria']['layout_fidelity']['verdict']=='pass'
