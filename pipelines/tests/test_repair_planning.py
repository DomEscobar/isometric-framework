"""Planning tests: no provider calls; observations are explicit test fixtures."""
from types import SimpleNamespace
from auto_adapter import Adapter


def fixture(findings):
    evaluation={'gate':{'production_approved':False,'findings':findings}}
    adapter=object.__new__(Adapter)
    adapter.ev=SimpleNamespace(get=lambda _:evaluation)
    state={'evaluation_id':'review-fixture','latest_candidate_id':'candidate-fixture','iterations':[]}
    return adapter,state


def test_plan_does_not_invent_material_or_palette_changes():
    findings=[{'blocking':True,'criterion':'pixel_style','observation':'Soft outlines in final paving crop','correction':'Use crisp nearest-pixel cluster edges while retaining the existing dark olive palette.'}]
    adapter,state=fixture(findings)
    plan=adapter.plan(state)
    assert 'warm cream' not in plan['prompt']
    assert 'asphalt' not in plan['prompt']
    assert 'dark olive palette' in plan['prompt']
    assert plan['material_changes']=={}
    assert plan['classification']==['pixel_style']


def test_layout_only_never_buys_image_before_free_measurement():
    adapter,state=fixture([{'blocking':True,'criterion':'layout_fidelity','observation':'Paving is displaced relative to guide','correction':'Align all ground boundaries with guide'}])
    plan=adapter.plan(state)
    assert plan['action']=='register'
    assert 'measurement' in plan['strategy_reason']
    assert plan['requires_semantic_review'] is True


def test_material_plan_keeps_multiple_findings_without_overwrite():
    findings=[{'blocking':True,'criterion':'materials','observation':'Dense small stones','correction':'Use broad stone faces'}, {'blocking':True,'criterion':'materials','observation':'Wrong grass palette','correction':'Retain olive grass from reference'}]
    adapter,state=fixture(findings)
    plan=adapter.plan(state)
    assert plan['material_changes']==[f['correction'] for f in findings]
    assert plan['avoid_changes']==[f['observation'] for f in findings]
    assert plan['action']=='generate'


def test_signature_ignores_changing_candidate_and_review_ids():
    findings=[{'blocking':True,'criterion':'materials','observation':'Dense small stones','correction':'Use broad stone faces'}]
    adapter,state=fixture(findings)
    first=adapter.plan(state)
    state['latest_candidate_id']='next-candidate'
    state['evaluation_id']='next-evaluation'
    state['iterations']=[{'review':{'id':'next-evaluation','score':[1,0,1,1]}}]
    second=adapter.plan(state)
    assert first['correction_signature']==second['correction_signature']
    findings[0]['correction']='Reduce internal seams only; retain broad stone faces'
    assert adapter.plan(state)['correction_signature']!=first['correction_signature']
