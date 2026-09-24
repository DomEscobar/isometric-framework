"""Worker integration: planner -> one flat image edit -> deterministic height renderer."""
import io,json,time
from pathlib import Path
from PIL import Image
from artifacts import canonical,digest
from generation import Generation
from provider import WaveSpeed
from hybrid_store import Store
from hybrid_worker import Worker,immutable
from hybrid_models import OpenRouter,MaterialImage,CRITERIA
from test_hybrid_layout import sample
from hybrid_artifact import ROOT,ACTOR


def test_paint_alignment_feedback_bounds_repairs():
    # v26/v27 live stop: a misaligned atlas killed the run. It must become a
    # bounded corrective repaint (2 repairs) with named-cell feedback.
    from hybrid_worker import _paint_alignment_feedback,_review_repaint_feedback
    assert _paint_alignment_feedback('painted semantic alignment mismatch: stairs at [12, 6]',0)=='stairs at [12, 6] was painted in the wrong material category'
    assert _paint_alignment_feedback('painted semantic alignment mismatch: x at [1, 1]',2) is None
    assert _paint_alignment_feedback('Bildformat falsch',0) is None
    # v28 live stop: a materials-fail review routed into the legacy crop
    # extraction and crashed (Fehlendes Material: shore). For the painted flow
    # the corrections must become repaint feedback.
    feedback=_review_repaint_feedback({'criteria':{'materials':{'verdict':'fail','correction':'Resample land from clean grass.'},'lighting':{'verdict':'pass','correction':'None.'}}})
    assert feedback=='Resample land from clean grass.'
    assert _review_repaint_feedback({'criteria':{}})=='resolve the failed review criteria'


def test_flat_painted_terrain_runs_without_crop_extraction(tmp_path,monkeypatch):
    from hybrid_layout import compile_layout
    world=sample();world['cells'][0][0]='path';world['cells'][0][1]='water';world['cells'][1][1]='plateau';world['cells'][2][1]='stairs'
    world=compile_layout(world)
    source=reference=(ROOT/'evidence/hybrid-multilevel/generation/style-reference.png').read_bytes()
    model='mock/flat-terrain';review_model='mock/independent-layout-reviewer';events=[];uploads={}
    meta={'id':model,'context_length':10000,'top_provider':{'max_completion_tokens':8192},'reasoning':{'supported_efforts':['low'],'mandatory':False},'pricing':{'prompt':'0.000001','completion':'0.000001'},
          'architecture':{'input_modalities':['text','image'],'output_modalities':['text']},
          'supported_parameters':['response_format','max_tokens','temperature','structured_outputs','reasoning']}
    plan={'unsupported':[],'layout':{k:world[k] for k in ['schema','width','height','actor_width','spawn','goals','cells','heights','transitions','unsupported']},'material_plan':{'intent':'flat pixel ground materials in guide zones','materials':{'land':'grass','path':'earth','water':'water','plateau':'stone','stairs':'stone','wall':'stone'},'avoid':['objects'],'uncertainty':[]},'interpretation':'Mock plan'}
    review={'criteria':{key:{'verdict':'pass','evidence_ids':['final','guide'] if key in ['layout_fidelity','walkable_clearance'] else ['final','reference'],'observation':'mock only, not user approval','correction':''} for key in CRITERIA}}
    def request(self,method,path,body=None):
        if path=='/auth/key':return {'data':{}}
        if path=='/models':return {'data':[meta,{**meta,'id':review_model}]}
        events.append(body)
        text=body['messages'][1]['content'][0]['text']
        actual_model=review_model if text.startswith(('You are an independent visual and structural reviewer.','Independent visual review, stage')) else model
        result=review if actual_model==review_model else plan
        if actual_model==review_model:
            if text.startswith('You are an independent visual and structural reviewer.'):
                import re
                result={'criteria':{k:{'verdict':'pass','observation':'Independent mock criterion passes.','correction':''} for k in ['water_shore','path_shape','stair_visibility','plateau','walkability','height_consistency']}}
                result.update(decision='approve',summary='Mock independent review only.',layout_sha256=re.search(r'layout_sha256=([0-9a-f]{64})',text).group(1),preview_sha256=re.search(r'preview_sha256=([0-9a-f]{64})',text).group(1))
        return {'id':'mock-call-'+str(len(events)),'model':actual_model,'choices':[{'finish_reason':'stop','message':{'content':json.dumps(result)}}],'usage':{'mock':True}}
    monkeypatch.setattr(OpenRouter,'request',request)
    monkeypatch.setattr(MaterialImage,'discover',lambda self:{'required':['prompt','image_urls','output_format']})
    monkeypatch.setattr(MaterialImage,'upload',lambda self,raw,name:(uploads.__setitem__(name,raw) or 'https://mock.invalid/'+name))
    monkeypatch.setattr(MaterialImage,'quote',lambda self,body:{'price':.011,'currency':'USD'})
    monkeypatch.setattr(MaterialImage,'submit',lambda self,body:(events.append(body) or {'id':'flat-image'}))
    monkeypatch.setattr(MaterialImage,'poll',lambda self,pid:{'id':pid,'status':'completed','outputs':['https://mock.invalid/result.png']})
    monkeypatch.setattr(MaterialImage,'download',lambda self,url:next(v for k,v in uploads.items() if k.startswith('flat_layout')))
    s=Store(Generation(tmp_path,WaveSpeed(key=''),{'approved':False,'total_usd':'10','max_attempts':0}))
    immutable(tmp_path/'hybrid-uploads'/(digest(reference)+'.png'),reference);immutable(tmp_path/'hybrid-uploads'/(digest(reference)+'.original'),reference)
    cfg={'mode':'live','terrain_flow':'painted_flat','description':'mock only','constraints':{k:world[k] for k in ['width','height','actor_width']},
         'reference_sha256':digest(reference),'reference_original_sha256':digest(reference),'actor_sha256':digest((ACTOR/'character.png').read_bytes()),
         'planner_model':model,'reviewer_model':review_model,'layout_review_iterations':5,'max_seconds':1800,'max_calls':12,'max_images':1,'max_local_corrections':0,'budget_microusd':1_000_000,
         'auto_continue':False,'token_policy':{'planner':{'max_tokens':8192,'reasoning_effort':'low'},'layout_review':{'max_tokens':8192,'reasoning_effort':'low'},'review':{'max_tokens':8192,'reasoning_effort':'low'}}}
    r=s.create('painted-flat',cfg);immutable(tmp_path/'hybrid-authorizations'/(r['id']+'.json'),canonical({'config_sha256':digest(canonical(cfg)),'expires':time.time()+600,'max_images':1,'max_calls':12,'budget_microusd':1_000_000}))
    worker=Worker(s);worker.tick();assert s.get(r['id'])['phase']=='layout_preview',s.get(r['id']).get('stop_reason')
    layout={k:world[k] for k in ['schema','width','height','actor_width','spawn','goals','cells','heights','transitions','unsupported']}
    worker.accept(r['id'],layout)
    worker=Worker(s)
    for _ in range(15):
        claim=s.claim()
        if not claim:break
        try:worker.process(claim)
        finally:s.release(claim)
        if s.get(r['id'])['phase'] in ['succeeded','needs_attention']:break
    out=s.get(r['id']);d=tmp_path/'hybrid'/r['id']
    assert out['phase']=='succeeded',out.get('stop_reason')
    assert out['image_count']==1 and out['call_count']==5
    assert len(events)==5, 'one planner + one independent layout review + one image + two reviews; no crop extraction call'
    assert (d/'flat-guide-0.png').exists() and (d/'source-0.png').exists()
    assert out['crop_binding']['mode']=='flat-terrain-image/1'
    assert out['painted_alignment']['checked_probes']==world['width']*world['height']*48*48
    assert (d/out['latest']/'land-crop.png').exists()
    assert out['verification']['production_rebuild_exact']
