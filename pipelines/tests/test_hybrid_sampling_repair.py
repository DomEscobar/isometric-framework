import copy,json,time
import pytest
from artifacts import canonical,digest
from hybrid_worker import ACTOR,ROOT

def capped_parent(tmp_path,monkeypatch):
    """Mocked full run stopped at the local-correction cap (scale-only fail + valid plan)."""
    import io
    from hybrid_artifact import replay_materials
    from hybrid_models import OpenRouter,MaterialImage,CRITERIA
    from hybrid_store import Store
    from generation import Generation
    from hybrid_worker import Worker,immutable
    from test_hybrid_layout import sample
    source,crops=replay_materials();reference=(ROOT/'evidence/hybrid-multilevel/generation/style-reference.png').read_bytes();calls=[]
    model='mock/explicit-test-only';review_model='mock/independent-reviewer'
    meta={'id':model,'context_length':10000,'top_provider':{'max_completion_tokens':16384},'pricing':{'prompt':'0.000001','completion':'0.000001'},'architecture':{'input_modalities':['text','image'],'output_modalities':['text']},'reasoning':{'supported_efforts':['low']},'supported_parameters':['response_format','max_tokens','temperature','structured_outputs','reasoning']}
    image=MaterialImage();plan={'unsupported':[],'layout':sample(),'material_plan':{'intent':'Mock test reference-derived grass and masonry','materials':{'land':'grass','wall':'masonry'},'avoid':[],'uncertainty':[]},'interpretation':'Mock fixture; NOT natural-language/live inference'}
    review={'criteria':{key:{'verdict':'pass','evidence_ids':['final','guide'] if key in ['layout_fidelity','walkable_clearance'] else ['final','reference'],'observation':'Explicit mock decision, not genuine visual approval','correction':''} for key in CRITERIA}}
    binding={'source_sha256':digest(source),'crops':{k:crops['crops'][k] for k in ['land','wall']}}
    def request(self,method,path,body=None):
        if path=='/auth/key':return {'data':{}}
        if path=='/models':return {'data':[meta,{**meta,'id':review_model}]}
        calls.append(body)
        text=body['messages'][1]['content'][0]['text']
        if text.startswith('Create ONLY'):
            result=copy.deepcopy(plan);response_model=model
        elif text.startswith('You are an independent visual and structural reviewer.'):
            import re
            result={'decision':'approve','criteria':{key:{'verdict':'pass','observation':'Mock independent criterion.','correction':''} for key in ['water_shore','path_shape','stair_visibility','plateau','walkability','height_consistency']},'summary':'Mock only.'}
            result['layout_sha256']=re.search(r'layout_sha256=([0-9a-f]{64})',text).group(1);result['preview_sha256']=re.search(r'preview_sha256=([0-9a-f]{64})',text).group(1);response_model=review_model
        elif text.startswith('Locate'):
            result={'source_sha256':digest(source),'crops':{k:crops['crops'][k] for k in ['land','wall']}};response_model=self.model
        elif text.startswith('Independent visual review, stage '):
            result=copy.deepcopy(review);response_model=self.model
            stage_calls=[x for x in calls if x['messages'][1]['content'][0]['text'].startswith('Independent visual review, stage ')]
            if len(stage_calls)==2:
                result['criteria']['scale']['verdict']='fail'
                result['local_sampling']={'source_sha256':digest(source),'binding_sha256':digest(canonical(binding)),'materials':{'land':{'source_pixels_per_unit':binding['crops']['land']['source_pixels_per_unit'],'offset':[1,2]}}}
        else:
            result=copy.deepcopy(review);response_model=self.model
        return {'id':'mock-'+str(len(calls)),'model':response_model,'choices':[{'finish_reason':'stop','message':{'content':json.dumps(result)}}],'usage':{'mock':True}}
    monkeypatch.setattr(OpenRouter,'request',request)
    monkeypatch.setattr(MaterialImage,'discover',lambda self:{'mock':'schema'})
    monkeypatch.setattr(MaterialImage,'upload',lambda self,raw,name:'https://mock.invalid/'+name)
    monkeypatch.setattr(MaterialImage,'quote',lambda self,body:{'price':.011,'currency':'USD'})
    monkeypatch.setattr(MaterialImage,'submit',lambda self,body:{'id':'mock-image'})
    monkeypatch.setattr(MaterialImage,'poll',lambda self,pid:{'id':pid,'status':'completed','outputs':['https://mock.invalid/output.png']})
    monkeypatch.setattr(MaterialImage,'download',lambda self,url:source)
    s=Store(Generation(tmp_path,MaterialImage(),{'approved':False,'total_usd':'10'}))
    immutable(tmp_path/'hybrid-uploads'/(digest(reference)+'.png'),reference)
    immutable(tmp_path/'hybrid-uploads'/(digest(reference)+'.original'),reference)
    cfg=dict(reference_original_sha256=digest(reference),mode='live',description='Mock fixture, not a live inference',constraints={k:sample()[k] for k in ['width','height','actor_width']},reference_sha256=digest(reference),actor_sha256=digest((ACTOR/'character.png').read_bytes()),planner_model=model,reviewer_model=review_model,layout_review_iterations=5,max_seconds=1800,max_calls=12,max_images=1,max_local_corrections=0,budget_microusd=5_000_000,auto_continue=False,token_policy={'planner':{'max_tokens':8192,'reasoning_effort':'low'},'layout_review':{'max_tokens':8192,'reasoning_effort':'low'},'review':{'max_tokens':8192,'reasoning_effort':'low'}})
    r=s.create('sampling-repair-parent',cfg)
    immutable(tmp_path/'hybrid-authorizations'/(r['id']+'.json'),canonical({'config_sha256':digest(canonical(cfg)),'expires':time.time()+300,'max_images':1,'max_calls':12,'budget_microusd':5_000_000}))
    worker=Worker(s);worker.tick()
    if s.get(r['id'])['phase']=='layout_preview':worker.accept(r['id'],sample())
    for _ in range(10):
        Worker(s).tick()
        if s.get(r['id'])['phase'] in ['succeeded','needs_attention']:break
    parent=s.get(r['id'])
    assert parent['phase']=='needs_attention' and 'Korrekturlimit' in (parent.get('stop_reason') or '')
    return s,parent

def test_sampling_repair_extracts_bounded_plan_and_fails_closed():
    from hybrid_sampling_repair import sampling_repair
    from hybrid_models import CRITERIA
    def review(fail,plan):
        raw={'criteria':{key:{'verdict':'fail' if key==fail else 'pass','evidence_ids':['final','guide'] if key in ['layout_fidelity','walkable_clearance'] else ['final','reference'],'observation':'mock decision evidence','correction':''} for key in CRITERIA}}
        raw['criteria'][fail]['verdict']='fail'
        if plan is not None:raw['local_sampling']=plan
        return raw
    binding={'source_sha256':'a'*64,'crops':{'land':{'xywh':[0,0,32,32],'source_pixels_per_unit':[32,32],'verdict':'pass','evidence_ids':['board'],'observation':'clean flat material'}}}
    evidence={'final','guide','reference','crop-land'}
    plan={'source_sha256':'a'*64,'binding_sha256':digest(canonical(binding)),'materials':{'land':{'source_pixels_per_unit':[64,64],'offset':[1,2]}}}
    corrected=sampling_repair(review('scale',plan),binding,'a'*64,evidence)
    assert corrected['crops']['land']['source_pixels_per_unit']==[64,64] and corrected['crops']['land']['offset']==[1,2]
    assert corrected['crops']['land']['xywh']==[0,0,32,32]
    before=copy.deepcopy(binding);assert binding==before
    with pytest.raises(ValueError):sampling_repair(review('scale',None),binding,'a'*64,evidence)
    with pytest.raises(ValueError):sampling_repair(review('materials',plan),binding,'a'*64,evidence)
    broken=json.loads(json.dumps(plan));broken['binding_sha256']='0'*64
    with pytest.raises(ValueError):sampling_repair(review('scale',broken),binding,'a'*64,evidence)
    extreme=json.loads(json.dumps(plan));extreme['materials']['land']['source_pixels_per_unit']=[96,96]
    with pytest.raises(ValueError):sampling_repair(review('scale',extreme),binding,'a'*64,evidence)

def test_sampling_repair_child_finishes_production(tmp_path,monkeypatch):
    from hybrid_sampling_repair import continue_sampling_repair,validated_sampling_repair
    from hybrid_worker import Worker,immutable
    s,p=capped_parent(tmp_path,monkeypatch);old=s.get(p['id'])
    child=continue_sampling_repair(s,p['id'],'sampling-child',4_000_000,3600,'bounded sampling repair authority')
    assert (child['call_count'],child['image_count'],child['local_count'])==(p['call_count'],p['image_count'],0)
    assert child['config']['max_calls']==p['call_count']+2 and child['config']['max_local_corrections']==1
    assert child['config']['followup_call_limit']==2 and child['config'].get('no_new_images') is True
    immutable(tmp_path/'hybrid-authorizations'/(child['id']+'.json'),canonical({**child['config'],'config_sha256':digest(canonical(child['config'])),'expires':time.time()+500}))
    for _ in range(10):
        Worker(s).tick()
        if s.get(child['id'])['phase'] in ['succeeded','needs_attention']:break
    r=s.get(child['id'])
    assert r['phase']=='succeeded',r.get('stop_reason')
    assert r['local_count']==1 and r['image_count']==p['image_count']
    assert r['crop_binding']['crops']['land']['offset']==[1,2]
    assert r['gate']['approved'] and r.get('production_approved')
    assert s.get(p['id'])==old
    proof,_,_=validated_sampling_repair(s,child['config']['continuation'])
    assert proof['binding_sha256']==digest(canonical(r['crop_binding']))
    with pytest.raises(ValueError):continue_sampling_repair(s,p['id'],'duplicate',4_000_000,3600,'bounded sampling repair authority')

@pytest.mark.parametrize('bad',['review','source','plan'])
def test_validated_sampling_repair_detects_drift(tmp_path,monkeypatch,bad):
    from hybrid_sampling_repair import continue_sampling_repair,validated_sampling_repair
    from hybrid_worker import immutable
    s,p=capped_parent(tmp_path,monkeypatch)
    child=continue_sampling_repair(s,p['id'],'drift-check',4_000_000,3600,'bounded sampling repair authority')
    immutable(tmp_path/'hybrid-authorizations'/(child['id']+'.json'),canonical({**child['config'],'config_sha256':digest(canonical(child['config'])),'expires':time.time()+500}))
    proof,_,_=validated_sampling_repair(s,child['config']['continuation'])
    d=tmp_path/'hybrid'/p['id'];attempt=p['attempt']
    if bad=='review':(d/f'review_final-{attempt}.json').write_bytes(b'{}')
    if bad=='source':(d/f'source-{attempt}.png').write_bytes(b'changed')
    if bad=='plan':proof['corrected_binding']['crops']['land']['offset']=[9,9]
    with pytest.raises((ValueError,OSError)):validated_sampling_repair(s,proof)
