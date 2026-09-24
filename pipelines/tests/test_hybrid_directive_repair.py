import json,time
import pytest
from artifacts import canonical,digest

def ok_parent(tmp_path,monkeypatch):
    import copy,io
    from hybrid_artifact import replay_materials
    from hybrid_models import OpenRouter,MaterialImage,CRITERIA
    from hybrid_store import Store
    from generation import Generation
    from hybrid_worker import Worker,immutable,ACTOR,ROOT
    from test_hybrid_layout import sample
    source,crops=replay_materials();reference=(ROOT/'evidence/hybrid-multilevel/generation/style-reference.png').read_bytes();calls=[]
    model='mock/explicit-test-only';review_model='mock/independent-reviewer'
    meta={'id':model,'context_length':10000,'top_provider':{'max_completion_tokens':16384},'pricing':{'prompt':'0.000001','completion':'0.000001'},'architecture':{'input_modalities':['text','image'],'output_modalities':['text']},'reasoning':{'supported_efforts':['low']},'supported_parameters':['response_format','max_tokens','temperature','structured_outputs','reasoning']}
    plan={'unsupported':[],'layout':sample(),'material_plan':{'intent':'Mock test reference-derived grass and masonry','materials':{'land':'grass','wall':'masonry'},'avoid':[],'uncertainty':[]},'interpretation':'Mock fixture; NOT natural-language/live inference'}
    review={'criteria':{key:{'verdict':'pass','evidence_ids':['final','guide'] if key in ['layout_fidelity','walkable_clearance'] else ['final','reference'],'observation':'Explicit mock decision, not genuine visual approval','correction':''} for key in CRITERIA}}
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
        else:
            result={'source_sha256':digest(source),'crops':{k:crops['crops'][k] for k in ['land','wall']}} if text.startswith('Locate') else copy.deepcopy(review);response_model=self.model
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
    cfg=dict(reference_original_sha256=digest(reference),mode='live',description='Mock fixture, not a live inference',constraints={k:sample()[k] for k in ['width','height','actor_width']},reference_sha256=digest(reference),actor_sha256=digest((ACTOR/'character.png').read_bytes()),planner_model=model,reviewer_model=review_model,layout_review_iterations=5,token_policy={'planner':{'max_tokens':8192,'reasoning_effort':'low'},'layout_review':{'max_tokens':8192,'reasoning_effort':'low'}},max_seconds=1800,max_calls=12,max_images=1,max_local_corrections=0,budget_microusd=5_000_000,auto_continue=False)
    r=s.create('directive-parent',cfg)
    immutable(tmp_path/'hybrid-authorizations'/(r['id']+'.json'),canonical({'config_sha256':digest(canonical(cfg)),'expires':time.time()+300,'max_images':1,'max_calls':12,'budget_microusd':5_000_000}))
    worker=Worker(s);worker.tick();worker.accept(r['id'],sample())
    for _ in range(10):
        Worker(s).tick()
        if s.get(r['id'])['phase'] in ['succeeded','needs_attention']:break
    parent=s.get(r['id'])
    call_state=[(x['role'], bool(x['receipt_known']), (x.get('receipt') or {}).get('model'), (x.get('receipt') or {}).get('choices',[{}])[0].get('finish_reason')) for x in s.calls(r['id'])]
    assert parent['phase']=='succeeded' and parent['production_approved'], f"phase={parent['phase']} stop_reason={parent.get('stop_reason')} calls={call_state}"
    return s,parent

def test_directive_child_starts_single_board_edit_and_keeps_parent(tmp_path,monkeypatch):
    from hybrid_directive_repair import continue_directive,validated_directive
    from hybrid_worker import Worker,immutable
    s,p=ok_parent(tmp_path,monkeypatch);old=s.get(p['id'])
    child=continue_directive(s,p['id'],'directive-child',4_000_000,3600,'bounded directive authority','owner wants richer varied flat material swatches, finer joints')
    assert child['config']['max_images']==p['image_count']+1 and child['config']['max_calls']==p['call_count']+4
    assert child['config']['followup_call_limit']==4 and 'no_new_images' not in child['config']
    immutable(tmp_path/'hybrid-authorizations'/(child['id']+'.json'),canonical({**child['config'],'config_sha256':digest(canonical(child['config'])),'expires':time.time()+500}))
    Worker(s).tick();r=s.get(child['id'])
    assert r['phase']=='generating',r.get('stop_reason')
    assert r['correction']['kind']=='owner_style_directive/1'
    assert 'richer varied' in r['correction']['directive']
    assert r['previous_source']==f"source-{p['attempt']}.png"
    assert s.get(p['id'])==old
    validated_directive(s,child['config']['continuation'])
    with pytest.raises(ValueError):continue_directive(s,p['id'],'dup',4_000_000,3600,'bounded directive authority','owner wants richer varied flat material swatches, finer joints')

def test_validated_directive_detects_drift(tmp_path,monkeypatch):
    from hybrid_directive_repair import continue_directive,validated_directive
    from hybrid_worker import immutable
    s,p=ok_parent(tmp_path,monkeypatch)
    child=continue_directive(s,p['id'],'drift',4_000_000,3600,'bounded directive authority','owner wants richer varied flat material swatches, finer joints')
    immutable(tmp_path/'hybrid-authorizations'/(child['id']+'.json'),canonical({**child['config'],'config_sha256':digest(canonical(child['config'])),'expires':time.time()+500}))
    proof,_,_=validated_directive(s,child['config']['continuation'])
    d=tmp_path/'hybrid'/p['id']
    (d/f"crop-decision-{p['attempt']}.json").write_bytes(b'{}')
    with pytest.raises((ValueError,OSError)):validated_directive(s,proof)
