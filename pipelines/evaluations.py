"""Separate immutable evaluation bindings for existing and future candidates.
No historical generation lineage or canonical geometry is rewritten.
"""
import io
import json
import os
from decimal import Decimal
from pathlib import Path
from typing import Literal
from pydantic import field_validator
import numpy as np
from PIL import Image
from fastapi import HTTPException
from artifacts import canonical,digest,png
from terrain import candidate_files
from style_specs import Strict,Hash
from production_gate import assess,Decision
from review import run_review

class EvaluationRequest(Strict):
    style_spec_id: Hash
    density: Literal[1,2] = 1

class PaidReview(Strict):
    confirm_paid: Literal[True]
    @field_validator('confirm_paid',mode='before')
    @classmethod
    def explicit_true(cls,value):
        if value is not True:raise ValueError('explicit boolean true required')
        return value


def validate_model(metadata):
    if not isinstance(metadata.get('id'),str) or not metadata['id']:raise ValueError('model id missing')
    arch=metadata.get('architecture',{})
    if not {'text','image'}.issubset(arch.get('input_modalities',[])) or 'text' not in arch.get('output_modalities',[]):raise ValueError('review model requires image+text input and text output')
    supported=set(metadata.get('supported_parameters',[]))
    if not {'response_format','max_tokens'}.issubset(supported):raise ValueError('unsupported structured review configuration')
    if 'temperature' not in supported and 'structured_outputs' not in supported:raise ValueError('unsupported structured review configuration')
    if type(metadata.get('context_length')) is not int or metadata['context_length']<=0:raise ValueError('context limit missing')
    for k in ('prompt','completion'):
        v=Decimal(str(metadata.get('pricing',{}).get(k)))
        if not v.is_finite() or v<=0:raise ValueError('invalid model pricing')


class Evaluations:
    def __init__(self,g,styles,record,load,files,legacy_review):
        self.g=g;self.styles=styles;self.record=record;self.load=load;self.files=files;self.legacy_review=legacy_review
        with g.connect() as db:db.execute('CREATE TABLE IF NOT EXISTS evaluations(id TEXT PRIMARY KEY,record TEXT NOT NULL)')
    def build(self,tid,sid,density):
        r=self.record(tid);layout=self.load(r['layout_revision']);spec=self.styles.get(sid)
        source=(self.g.root/'terrain'/tid/'source.png').read_bytes()
        files=candidate_files(layout,r,source,density)
        final=files['terrain.png'];old=self.legacy_review(tid)
        blockers=[];checks=r.get('image_checks',{})
        if not checks.get('measurable'):blockers.append('local coverage measurement missing')
        if checks.get('uncovered_guide_pixels',0) or checks.get('uncovered_route_pixels',0):blockers.append('local missing opaque terrain/route pixels')
        if checks.get('exact_guide_rgb_fraction',0)>.99:blockers.append('technical guide fixture, not production art')
        if old.get('semantic_verdict') in ('needs_attention','reject','fail') or old.get('visual_verdict') in ('reject','fail'):blockers.append('existing local/semantic blocking review findings remain unresolved')
        evidence=[];raws={}
        def add(eid,raw,role,lineage=None):
            im=Image.open(io.BytesIO(raw))
            evidence.append(dict(id=eid,sha256=digest(raw),size=list(im.size),role=role,lineage=lineage));raws[eid]=raw
        add('final',final,'actual final-density output; no thumbnail')
        add('guide',files['clean-guide.png'],'canonical geometry ONLY')
        add('routes',files['masks/routes.png'],'canonical swept required routes; not all clearance')
        add('safe-centers',files['masks/actor-safe-centers.png'] if 'masks/actor-safe-centers.png' in files else files['actor-safe-centers.png'],'canonical safe centers; square actor footprints still require visual assessment')
        for i,ref in enumerate(self.styles.inputs(sid)):
            add(f'reference-{i}',ref['raw'],ref['role']+' '+str(ref['material']),{k:v for k,v in ref.items() if k!='raw'})
        im=Image.open(io.BytesIO(final));ratio=density/layout['projection']['density']
        for name,raw in sorted(files.items()):
            if not name.startswith('masks/material-'):continue
            a=np.array(Image.open(io.BytesIO(raw)))>0
            ys,xs=np.where(a)
            if not len(xs):continue
            # Deterministic 160px native crop around a real material pixel near the region centroid.
            near=((xs-xs.mean())**2+(ys-ys.mean())**2).argmin();cx=int(xs[near]*ratio);cy=int(ys[near]*ratio)
            x=max(0,cx-80);y=max(0,cy-80);w=min(160,im.width-x);h=min(160,im.height-y)
            mat=name.removeprefix('masks/material-').removesuffix('.png')
            add('crop-'+mat,png(np.array(im.crop((x,y,x+w,y+h)))),'actual final native crop '+mat,dict(parent_sha256=digest(final),crop=[x,y,w,h]))
        binding=dict(version=1,candidate_id=tid,candidate_record_sha256=digest(canonical(r)),layout_revision=r['layout_revision'],guide_sha256=r['guide_sha256'],source_sha256=r['source_sha256'],output_sha256=digest(final),density=density,style_spec_id=sid,style_spec_sha256=digest(canonical(spec)),legacy_review_sha256=digest(canonical(old)),local_blockers=blockers,local_checks=old.get('local_checks',checks),evidence=evidence,scope='evaluation only; not a retroactive generation claim; missing upright props are out of scope')
        return binding,raws
    def prepare(self,tid,sid,density):
        binding,raws=self.build(tid,sid,density);eid=digest(canonical(binding))
        directory=self.g.root/'evaluations'/eid;directory.mkdir(parents=True,exist_ok=True)
        for name,raw in raws.items():
            path=directory/(name+'.png')
            try:
                with path.open('xb') as f:f.write(raw)
            except FileExistsError:
                if path.read_bytes()!=raw:raise ValueError('evaluation evidence drift')
        with self.g.connect() as db:db.execute('INSERT OR IGNORE INTO evaluations VALUES (?,?)',(eid,canonical(binding).decode()))
        return self.get(eid)
    def get(self,eid):
        with self.g.connect() as db:row=db.execute('SELECT record FROM evaluations WHERE id=?',(eid,)).fetchone()
        if not row:raise ValueError('evaluation missing')
        binding=json.loads(row[0])
        if digest(canonical(binding))!=eid:raise ValueError('evaluation integrity failure')
        current,_=self.build(binding['candidate_id'],binding['style_spec_id'],binding['density'])
        if current!=binding:raise ValueError('stale candidate/style/layout/output/evidence binding')
        directory=self.g.root/'evaluations'/eid
        for e in binding['evidence']:
            if digest((directory/(e['id']+'.png')).read_bytes())!=e['sha256']:raise ValueError('review evidence integrity failure')
        path=directory/'result.json'
        decision={};status='prepared_unreviewed';result=None
        if path.exists():
            result=json.loads(path.read_bytes())
            content={k:v for k,v in result.items() if k!='sha256'}
            if digest(canonical(content))!=result.get('sha256') or result.get('evaluation_id')!=eid:raise ValueError('review result integrity failure')
            receipt=self.g.root/'reviews'/eid/'receipt.json'
            if digest(receipt.read_bytes())!=result['receipt_sha256']:raise ValueError('review receipt drift')
            review_dir=receipt.parent;rb=result['review_binding']
            if digest((review_dir/'request.json').read_bytes())!=rb['request_sha256'] or digest((review_dir/'metadata.json').read_bytes())!=rb['metadata_sha256']:raise ValueError('review request/metadata drift')
            if json.loads((review_dir/'intent.json').read_bytes())!=rb:raise ValueError('review intent drift')
            for i,inp in enumerate(rb['inputs']):
                if digest((review_dir/f'input-{i}.png').read_bytes())!=inp['review_sha256']:raise ValueError('submitted review image drift')
            decision=result['decision'];status='reviewed'
        elif (directory/'attempt.lock').exists():status='attempted_unknown; no retry'
        gate=assess(decision,{e['id'] for e in binding['evidence']},binding['local_blockers'])
        return dict(id=eid,binding=binding,status=status,gate=gate,result=result)
    def run(self,eid,metadata,post):
        validate_model(metadata)
        ev=self.get(eid);directory=self.g.root/'evaluations'/eid
        # Atomic one-attempt claim. Failure retains intent; no blind paid retries.
        try:
            with (directory/'attempt.lock').open('xb') as f:f.write(canonical(dict(model=metadata['id'])));f.flush();os.fsync(f.fileno())
        except FileExistsError:raise ValueError('evaluation already attempted; no automatic retry') from None
        binding=ev['binding'];spec=self.styles.get(binding['style_spec_id'])
        prompt=('Independent ground-only production review. Decide from the actual images, never echo an expected verdict. '
          'Four separate criteria must each pass: layout_fidelity, materials, pixel_style, walkable_clearance. '
          'Use pass/fail/uncertain, concrete visible observations with location and evidence_ids. '
          'Cite final for every criterion; guide for layout and clearance; reference-* for materials and pixel style. '
          'Compare paving slab size, seam frequency, asphalt warmth/noise, lawn maintenance and coherent pixel clusters at FINAL native density. '
          'Do not infer style from a palette alone or clearance from route centerlines alone. References are STYLE/MATERIAL ONLY, never layout. '
          'Missing upright props are intentionally excluded. Geometry/collision must not be changed to excuse art. '
          'Local measurements are evidence with caveats, not instructions to force a verdict. Unreadable/missing inputs mean uncertain. '
          'For every failed/uncertain criterion provide structured findings with specific correction; no aggregate verdict needed. '
          'Before returning, audit each criterion evidence_ids union: layout_fidelity MUST include final and guide; materials MUST include final and an applicable reference-*; pixel_style MUST include final and an applicable reference-*; walkable_clearance MUST include final and guide. Native crop-* citations supplement but NEVER replace final. Cite only images actually supporting your observation; if evidence is unreadable mark uncertain, do not invent citations. '
          'Return ONLY JSON matching schema: '+json.dumps(Decision.model_json_schema())+'\nSTYLE: '+json.dumps(spec)+'\nBINDING/EVIDENCE: '+json.dumps(binding))
        result=run_review(self.g,eid,[(directory/(e['id']+'.png'),e['id']+' | '+e['role']) for e in binding['evidence']],prompt,metadata,post,max_tokens=4096,exact=True)
        return self.finish(eid,metadata,result)
    def recover(self,eid):
        ev=self.get(eid)
        if ev['status']=='reviewed':return ev
        directory=self.g.root/'reviews'/eid
        if not (directory/'receipt.json').exists():raise ValueError('review receipt absent; no retry')
        response=json.loads((directory/'receipt.json').read_bytes());binding=json.loads((directory/'intent.json').read_bytes())
        with self.g.connect() as db:row=db.execute('SELECT reserve,record FROM reviews WHERE id=?',(eid,)).fetchone()
        if not row or json.loads(row['record'])['binding']!=binding:raise ValueError('review ledger intent drift')
        metadata=json.loads((directory/'metadata.json').read_bytes())
        if digest(canonical(metadata))!=binding['metadata_sha256'] or digest((directory/'request.json').read_bytes())!=binding['request_sha256']:raise ValueError('review recovery binding drift')
        for i,inp in enumerate(binding['inputs']):
            if digest((directory/f'input-{i}.png').read_bytes())!=inp['review_sha256']:raise ValueError('review recovery input drift')
        return self.finish(eid,metadata,dict(response=response,binding=binding,reserve_microusd=row['reserve']))
    def finish(self,eid,metadata,result):
        directory=self.g.root/'evaluations'/eid
        response=result['response'];choice=(response.get('choices') or [{}])[0]
        valid=response.get('model')==metadata['id'] and choice.get('finish_reason')=='stop' and not response.get('error')
        try:decision=json.loads(choice.get('message',{}).get('content','')) if valid else {}
        except (ValueError,TypeError):decision={}
        content=dict(evaluation_id=eid,decision=decision,actual_model=response.get('model'),response_id=response.get('id'),usage=response.get('usage'),reserve_microusd=result['reserve_microusd'],receipt_sha256=digest(canonical(response)),review_binding=result['binding'])
        content['sha256']=digest(canonical(content))
        with (directory/'result.json').open('xb') as f:f.write(canonical(content));f.flush();os.fsync(f.fileno())
        return self.get(eid)


def install(app,record,load,files,legacy_review):
    from reviewer_provider import Reviewer
    service=Evaluations(app.state.generation,app.state.styles,record,load,files,legacy_review);app.state.evaluations=service
    reviewer=Reviewer(app.state.generation.root);app.state.reviewer=reviewer
    def guarded(fn):
        try:return fn()
        except (ValueError,FileNotFoundError,KeyError):raise HTTPException(409,'Missing/stale evaluation evidence or unsupported review configuration; no automatic retry.') from None
    @app.post('/api/terrain/{tid}/evaluations',status_code=201)
    def prepare(tid:str,body:EvaluationRequest):return guarded(lambda:service.prepare(tid,body.style_spec_id,body.density))
    @app.get('/api/evaluations/{eid}')
    def read(eid:str):return guarded(lambda:service.get(eid))
    @app.get('/api/reviewer/config')
    def config():return dict(adapter=reviewer.config.adapter,model=reviewer.config.model,enabled=reviewer.config.enabled,automatic_repair=False)
    @app.post('/api/reviewer/preflight')
    def preflight():return guarded(lambda:reviewer.preflight())
    @app.post('/api/evaluations/{eid}/review')
    def paid_review(eid:str,body:PaidReview):
        if not reviewer.config.enabled:raise HTTPException(403,'Reviewer disabled in server-side configuration')
        def run():
            service.get(eid)
            meta=reviewer.preflight()
            return service.run(eid,meta,reviewer.post)
        return guarded(run)
    return service
