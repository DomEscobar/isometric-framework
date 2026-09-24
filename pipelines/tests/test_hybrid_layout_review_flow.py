import json,time,re
import pytest
from artifacts import canonical,digest
from generation import Generation
from hybrid_store import Store
from hybrid_worker import Worker,immutable
from hybrid_models import OpenRouter
from hybrid_artifact import ROOT,ACTOR
from test_hybrid_layout import sample


def fixture(tmp_path,monkeypatch,decisions):
    model='test/planner';review_model='test/independent-reviewer';calls=[]
    plan={'unsupported':[],'layout':{'schema':'hybrid-layout/1','width':18,'height':16,'actor_width':0.64,'spawn':[2,8],'goals':[[10,7]],'cells':[['land']*18 for _ in range(16)],'heights':[[0]*18 for _ in range(16)],'transitions':[],'unsupported':[]},'material_plan':{'intent':'Mock reference-derived flat materials','materials':{'land':'grass','stairs':'stone','plateau':'stone','path':'earth','water':'water','wall':'masonry'},'avoid':[],'uncertainty':[]},'interpretation':'Mock fixture only'}
    layout=plan['layout']
    for y in range(1,4):
        for x in range(1,4):layout['cells'][y][x]='water'
    for x in range(2,7):layout['cells'][8][x]='path'
    for y in range(6,9):
        for x in range(9,12):layout['cells'][y][x]='plateau';layout['heights'][y][x]=24
    layout['cells'][8][6]='stairs';layout['heights'][8][6]=8
    layout['cells'][8][7]='stairs';layout['heights'][8][7]=16
    layout['cells'][8][8]='stairs';layout['heights'][8][8]=24
    # Each level transition has a stair endpoint; top stair borders the plateau.
    layout['transitions']=[[[5,8],[6,8]],[[6,8],[7,8]],[[7,8],[8,8]]]
    layout['goals']=[[10,7]]
    assessments=[]
    for decision in decisions:
        assessment={'decision':decision,'criteria':{
          name:{'verdict':'pass','observation':'Independent mock criterion','correction':''}
          for name in ['water_shore','path_shape','stair_visibility','plateau','walkability','height_consistency']},'summary':'Mock response; not real visual evidence.'}
        if decision=='revise':
            assessment['criteria']['stair_visibility']={'verdict':'fail','observation':'Stair strip needs contrast.','correction':'Render one contiguous straight two-cell stair strip.'}
        assessments.append(assessment)
    metadata={m:{'id':m,'context_length':4096,'top_provider':{'max_completion_tokens':16384},'pricing':{'prompt':'0.000000001','completion':'0.000000001'},'architecture':{'input_modalities':['text','image'],'output_modalities':['text']},'supported_parameters':['response_format','max_tokens','temperature','structured_outputs','reasoning'],'reasoning':{'supported_efforts':['low']}} for m in [model,review_model]}
    planner_results=[dict(plan)]
    def request(self,method,path,body=None):
        if path=='/auth/key':return {'data':{}}
        if path=='/models':return {'data':[metadata[model],metadata[review_model]]}
        calls.append((self.model,body))
        if self.model==model:
            index=sum(m==model for m,_ in calls)-1
            result=dict(planner_results[min(index,len(planner_results)-1)])
        elif self.model==review_model:
            assessment_index=sum(m==review_model for m,_ in calls)-1
            result=dict(assessments[min(assessment_index,len(assessments)-1)])
            text=body['messages'][1]['content'][0]['text']
            result['layout_sha256']=re.search(r'layout_sha256=([0-9a-f]{64})',text).group(1)
            result['preview_sha256']=re.search(r'preview_sha256=([0-9a-f]{64})',text).group(1)
        else:result=plan
        return {'id':'mock-'+str(len(calls)),'model':self.model,'choices':[{'finish_reason':'stop','message':{'content':json.dumps(result)}}]}
    monkeypatch.setattr(OpenRouter,'request',request)
    from hybrid_models import MaterialImage
    reference=(ROOT/'evidence/hybrid-multilevel/generation/style-reference.png').read_bytes()
    s=Store(Generation(tmp_path,MaterialImage(key=''),{'approved':False,'total_usd':'10'}))
    immutable(tmp_path/'hybrid-uploads'/(digest(reference)+'.png'),reference);immutable(tmp_path/'hybrid-uploads'/(digest(reference)+'.original'),reference)
    cfg={'mode':'live','description':'Flat meadow, compact water, narrow path, plateau and stairs','constraints':{'width':18,'height':16,'actor_width':0.64},
      'reference_sha256':digest(reference),'reference_original_sha256':digest(reference),'actor_sha256':digest((ACTOR/'character.png').read_bytes()),
      'planner_model':model,'reviewer_model':review_model,'max_seconds':1800,'max_calls':12,'max_images':3,'budget_microusd':1000000,
      'auto_continue':False,'layout_review_iterations':5,'token_policy':{'planner':{'max_tokens':8192,'reasoning_effort':'low'},'layout_review':{'max_tokens':8192,'reasoning_effort':'low'}}}
    corrected=dict(plan);corrected['layout']=json.loads(json.dumps(layout));corrected['material_plan']=dict(plan['material_plan'])
    planner_results.append(corrected)
    run=s.create('review-loop',cfg);immutable(tmp_path/'hybrid-authorizations'/(run['id']+'.json'),canonical({'config_sha256':digest(canonical(cfg)),'expires':time.time()+600,'max_images':3,'max_calls':12,'budget_microusd':1000000}))
    return s,run,Worker(s),calls,model,review_model


def test_review_loop_uses_separate_model_and_returns_actionable_correction(tmp_path,monkeypatch):
    s,r,w,calls,planner,reviewer=fixture(tmp_path,monkeypatch,['revise','approve'])
    w.tick();current=s.get(r['id'])
    assert current['phase']=='planning' and current['layout_iteration']==1
    assert current['layout_review_feedback'].startswith('stair_visibility: fail')
    assert len(calls)==2 and calls[0][0]==planner and calls[1][0]==reviewer
    w.tick();current=s.get(r['id'])
    assert current['phase']=='layout_preview' and current['layout_iteration']==2
    assert len(calls)==4 and [x[0] for x in calls]==[planner,reviewer,planner,reviewer]
    assert s.calls(r['id'])[0]['role']=='planner' and s.calls(r['id'])[2]['role']=='planner-2'
    assert (tmp_path/'hybrid'/r['id']/'layout-review-2.json').exists()


def test_review_loop_hard_stops_after_five_and_cannot_freeze_failed_layout(tmp_path,monkeypatch):
    s,r,w,calls,planner,reviewer=fixture(tmp_path,monkeypatch,['revise']*5)
    for _ in range(5):w.tick()
    current=s.get(r['id'])
    assert current['phase']=='needs_attention' and current['layout_iteration']==5
    assert 'Circuit breaker' in current['stop_reason']
    assert len(calls)==10
    with pytest.raises(ValueError):w.accept(r['id'],current.get('layout_candidate'))
    assert all(x['receipt_known'] for x in s.calls(r['id']))


def test_bound_acknowledgment_allows_new_review_round_without_touching_old_unknown_hold(tmp_path,monkeypatch):
    s,r,w,calls,planner,reviewer=fixture(tmp_path,monkeypatch,['approve'])
    request=canonical({'old_request':'unknown'}).decode();call_id='a'*64;amount=100
    request_sha=digest(request.encode())
    ledger={'id':call_id,'reserve_microusd':amount,'binding':{'request_sha256':request_sha},'status':'reserved_unknown_until_receipt'}
    with s.g.connect() as db:
        db.execute('INSERT INTO reviews VALUES (?,?,?)',(call_id,amount,canonical(ledger).decode()))
        db.execute('INSERT INTO hybrid_calls VALUES (?,?,?,?,NULL,?)',(call_id,'old-run','planner',request,amount))
    cfg=r['config'];scope={'run_id':r['id'],'config_sha256':digest(canonical(cfg)),
        'approval_text':'Owner authorizes this fresh bounded run, retain unknown old hold unchanged.',
        'project_cap_microusd':10_000_000,'budget_microusd':cfg['budget_microusd'],
        'max_calls':cfg['max_calls'],'max_images':cfg['max_images'],'expires':time.time()+600,
        'liabilities':[{'call_id':call_id,'request_sha256':request_sha,'amount':amount}]}
    aid=s.acknowledge_liabilities(scope)
    authorization={'config_sha256':scope['config_sha256'],'budget_microusd':scope['budget_microusd'],
        'max_calls':scope['max_calls'],'max_images':scope['max_images'],'expires':scope['expires'],
        'liability_authorization':aid}
    (s.g.root/'hybrid-authorizations'/(r['id']+'.json')).write_bytes(canonical(authorization))
    from hybrid_worker import authorization as load_authorization
    assert load_authorization(s,r)['liability_authorization']==aid
    w.tick();current=s.get(r['id'])
    assert current['phase']=='layout_preview',current.get('stop_reason')
    assert [x[0] for x in calls]==[planner,reviewer]
    with s.g.connect() as db:
        assert db.execute('SELECT receipt FROM hybrid_calls WHERE id=?',(call_id,)).fetchone()[0] is None
        assert db.execute('SELECT reserve FROM reviews WHERE id=?',(call_id,)).fetchone()[0]==amount


def test_generic_layout_run_is_not_subject_to_special_flat_pond_contract():
    from hybrid_worker import _target_contract_issues
    from test_hybrid_layout import sample

    # Existing workflows have different geometry contracts; only a run that opts in
    # to the specific v1 terrain brief should receive its deterministic gate.
    assert _target_contract_issues(sample(), {}) == []
    assert _target_contract_issues(sample(), {'layout_contract': 'flat-pond-path-plateau/1'})


def test_unknown_model_submission_blocks_next_review_loop_round(tmp_path,monkeypatch):
    s,r,w,calls,planner,reviewer=fixture(tmp_path,monkeypatch,['revise','approve'])
    original=OpenRouter.request
    def ambiguous(self,method,path,body=None):
        if method=='POST' and self.model==reviewer:
            from hybrid_models import OpenRouterFailure
            raise OpenRouterFailure('transport')
        return original(self,method,path,body)
    monkeypatch.setattr(OpenRouter,'request',ambiguous)
    w.tick();current=s.get(r['id'])
    assert current['phase']=='needs_attention'
    rows=s.calls(r['id'])
    assert len(rows)==2 and rows[0]['receipt_known'] and not rows[1]['receipt_known']
    assert len(calls)==1
