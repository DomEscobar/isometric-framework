"""Real service adapter. Corrections use current pixels + unchanged guide/style inputs.
Registration is deliberately narrow: stable dark-surround extrema and one scalar;
ambiguous geometry stops the run, never invents a warp or operator handoff.
"""
import io
import json
from decimal import Decimal
from pathlib import Path
import numpy as np
from PIL import Image
from fastapi import HTTPException
from artifacts import canonical,digest,png
from terrain import render_original
from production_gate import CRITERIA
from auto_repair import AutoRepair,Start
from evaluations import PaidReview

QUALITY_AUTHORIZATION=Path(__file__).with_name('QUALITY_RECOVERY_AUTHORIZATION.md')


def is_hash(value):
    return isinstance(value,str) and len(value)==64 and all(c in '0123456789abcdef' for c in value)


def is_review_id(value):
    # Original pilot reviews predate content-addressed evaluations. Preserve
    # those literal ledger identities, never normalize or guess replacements.
    return is_hash(value) or value in ('paid-pilot-01','paid-pilot-02-verified-auth','urban-pilot-01-verified-auth')


def reference_prompt(refs):
    roles=['Image 1: immutable geometry guide']
    roles += [f"Image {i+2}: {r['role']}"+(' '+r['material'] if r.get('material') else '') for i,r in enumerate(refs)]
    return ('Exact submitted image order: '+'; '.join(roles)+'. '
            'For each named material, its material_only crop takes priority over unrelated surfaces visible in the full style_only scene. '
            'Use the full scene only for coherent rendering language, never copy its objects, geography or another material. '
            'The correction_target is the actual current terrain, never a style authority. Preserve passing materials and boundaries; '
            'change only the properties identified by the cited findings. Ground-only details must remain inside their planned regions.')


def measure_registration(source,guide):
    src=np.array(Image.open(io.BytesIO(source)).convert('RGBA'))
    target=np.array(Image.open(io.BytesIO(guide)).convert('RGBA'))[:,:,3]>0
    def corners(mask):
        y,x=np.where(mask)
        if len(x)<100:raise ValueError('insufficient foreground')
        return np.array([[x[i],y[i]] for i in (np.argmin(x),np.argmin(y),np.argmax(x),np.argmax(y))],float)
    g=corners(target);gc=g-g.mean(0);fits=[]
    border=np.concatenate([src[0,:,:3],src[-1,:,:3],src[:,0,:3],src[:,-1,:3]])
    if np.quantile(border.max(1),.99)>40 and src[:,:,3].min()>0:
        return {'blocker':'registration_ambiguous: no isolated dark/transparent surround'}
    for threshold in (60,80,100):
        mask=(src[:,:,:3].max(2)>threshold)&(src[:,:,3]>0)
        try:s=corners(mask)
        except ValueError:return {'blocker':'registration_ambiguous: foreground missing'}
        k=float(((s-s.mean(0))*gc).sum()/(gc*gc).sum())
        if k<=0:return {'blocker':'registration_ambiguous: invalid scalar'}
        t=s.mean(0)-k*g.mean(0);res=(s-(k*g+t))/k
        fits.append(dict(threshold=threshold,source_corners=s.tolist(),scale=1/k,translation=(-t/k).tolist(),max_residual_px=float(np.linalg.norm(res,axis=1).max())))
    r=fits[1];spread=max(abs(f['scale']/r['scale']-1) for f in fits)
    translation_spread=max(float(np.linalg.norm(np.array(f['translation'])-r['translation'])) for f in fits)
    result=dict(scale=r['scale'],translation=r['translation'],measurements=dict(canonical_corners=g.tolist(),fits=fits,relative_scale_spread=spread,translation_spread_px=translation_spread,limits=dict(residual_px=2.5,relative_scale=.01,translation_px=1.5),scope='frame compatibility ONLY; independent semantic gate still required'))
    if max(f['max_residual_px'] for f in fits)>2.5 or spread>.01 or translation_spread>1.5:
        result['blocker']='registration_ambiguous: nonuniform or threshold-unstable landmarks; no safe automatic registration'
    return result

class Adapter:
    def __init__(self,app,files,record,load,register,poll):
        self.app=app;self.g=app.state.generation;self.ev=app.state.evaluations;self.styles=app.state.styles;self.reviewer=app.state.reviewer
        self.files=files;self.record=record;self.load=load;self.register_call=register;self.poll_call=poll
    def freeze(self,eid):
        e=self.ev.get(eid);b=e['binding']
        if e['status']!='reviewed':raise ValueError('initial reviewed candidate required')
        return dict(evaluation_id=eid,candidate_id=b['candidate_id'],revision=b['layout_revision'],style=b['style_spec_id'],density=b['density'],binding_sha256=digest(canonical(b)),gate_sha256=digest(Path(__file__).with_name('production_gate.py').read_bytes()),registration_limits=dict(residual_px=2.5,relative_scale=.01,translation_px=1.5),authorization_sha256=digest(Path(__file__).with_name('AUTO_REPAIR_AUTHORIZATION.md').read_bytes()))
    def validate(self,w):
        if self.freeze(w['frozen']['evaluation_id'])!=w['frozen']:raise ValueError('stale frozen layout/style/reference/gate/authorization')
        e=self.ev.get(w['evaluation_id'])
        if (e['binding']['layout_revision'],e['binding']['style_spec_id'],e['binding']['density'])!=(w['frozen']['revision'],w['frozen']['style'],w['frozen']['density']):raise ValueError('stale active evaluation')
    def summary(self,e):
        gate=e['gate'];criteria=gate['criteria']
        invalid=any(any(word in b for word in ('citation','invalid','unknown')) for b in gate['blockers'])
        return dict(id=e['id'],approved=gate['production_approved'],score=[{'fail':0,'uncertain':0,'pass':1}.get(criteria.get(k,{}).get('verdict'),0) for k in CRITERIA],source_sha256=e['binding']['source_sha256'],blockers=gate['blockers'],valid=len(criteria)==4 and not invalid)
    def continuation_seed(self,parent):
        """Read-only proof, not approval, authorization, recovery or a ledger reset.

        A valid FAIL review can seed correction; a malformed/uncited verdict
        cannot. Historical freezes are compared, never upgraded in place.
        """
        proof=dict(eligible=False,blockers=[],registered=False,reviewed=False,
                   valid=False,no_unknown_liabilities=False)
        blockers=proof['blockers']
        def require(condition,reason):
            if not condition:raise ValueError(reason)
        def checked(label,fn):
            try:return fn()
            except Exception as exc:
                # Only exact, locally authored integrity reasons are public;
                # arbitrary exceptions may contain paths, URLs or credentials.
                safe={'evaluation missing','evaluation integrity failure',
                      'stale candidate/style/layout/output/evidence binding',
                      'review evidence integrity failure','review result integrity failure',
                      'review receipt drift','review request/metadata drift',
                      'review intent drift','submitted review image drift'}
                detail=str(exc) if type(exc) is ValueError and str(exc) in safe else None
                blockers.append(label+(': '+detail if detail else ''))
                return None
        def identity():
            require(isinstance(parent,dict),'parent')
            for key in ('best_candidate_id','best_evaluation_id','latest_candidate_id','evaluation_id'):
                require(is_hash(parent.get(key)),'id')
            f=parent['frozen']
            for key in ('evaluation_id','candidate_id','revision','style'):
                require(is_hash(f.get(key)),'frozen id')
            require(type(f['density']) is int and f['density'] in (1,2),'density')
            proof.update(candidate_id=parent['best_candidate_id'],evaluation_id=parent['best_evaluation_id'],frozen_sha256=digest(canonical(f)))
            return f
        f=checked('malformed retained seed identity or frozen contract',identity)
        if f is None:return proof
        checked('stale frozen layout/style/density/gate/authorization or active evaluation',lambda:self.validate(parent))
        def candidate():
            tid=proof['candidate_id'];r=self.record(tid)
            require(r.get('id')==tid and digest(canonical({k:v for k,v in r.items() if k!='id'}))==tid,'record')
            raw=(self.g.root/'terrain'/tid/'source.png').read_bytes()
            require(digest(raw)==r['source_sha256'],'source')
            require(r['layout_revision']==f['revision'],'revision')
            return r,raw
        retained=checked('retained best candidate/source integrity or revision mismatch',candidate)
        def registration():
            r,raw=retained
            reg=r['processing_registration'];pid=r['parent_candidate_id']
            require(is_hash(pid),'parent')
            original=self.record(pid)
            require(not original.get('processing_registration'),'chained registration')
            require(original['source_sha256']==r['source_sha256'] and original['layout_revision']==f['revision'],'original binding')
            require((self.g.root/'terrain'/pid/'source.png').read_bytes()==raw,'original bytes')
            guide=self.files(f['revision'])['clean-guide.png']
            require(digest(guide)==r['guide_sha256'],'guide')
            measured=measure_registration(raw,guide)
            proof['registration']=measured
            if measured.get('blocker'):
                blockers.append(measured['blocker'])
                return
            require(measured['measurements']['limits']==f['registration_limits'],'limits')
            require(type(reg['scale']) in (int,float) and np.isfinite(reg['scale']) and reg['scale']>0,'scale')
            require(np.asarray(reg['translation']).shape==(2,) and np.isfinite(reg['translation']).all(),'translation')
            require(abs(reg['scale']-measured['scale'])<=1e-9 and np.allclose(reg['translation'],measured['translation'],rtol=0,atol=1e-7),'retained transform differs from measured safe fit')
            from terrain import image_checks
            rendered=png(np.array(render_original(self.load(f['revision']),r,raw,f['density'])))
            # Coverage is measured in the canonical guide's density, as at registration.
            layout=self.load(f['revision'])
            native=png(np.array(render_original(layout,r,raw,layout['projection']['density'])))
            checks=image_checks(native,guide,self.files(f['revision']))
            require(checks.get('measurable') and not checks.get('uncovered_guide_pixels') and not checks.get('uncovered_route_pixels'),'coverage')
            proof.update(registered=True,output_sha256=digest(rendered))
        if retained:checked('retained best registration missing, unsafe, mismatched or uncovered',registration)
        def evaluation():
            e=self.ev.get(proof['evaluation_id']);b=e['binding']
            require(e['id']==proof['evaluation_id'] and e['status']=='reviewed','reviewed')
            require((b['candidate_id'],b['layout_revision'],b['style_spec_id'],b['density'])==(proof['candidate_id'],f['revision'],f['style'],f['density']),'binding')
            if retained:
                require(b['source_sha256']==retained[0]['source_sha256'] and b['candidate_record_sha256']==digest(canonical(retained[0])),'source binding')
            if proof.get('output_sha256'):require(b['output_sha256']==proof['output_sha256'],'output binding')
            return e
        e=checked('best evaluation missing, unreviewed, stale or review evidence/receipt integrity failure',evaluation)
        if e:
            def reviewed():
                self._continuation_review_receipt(e['id'],e)
                proof['reviewed']=True
            checked('best review central ledger/receipt/request/input/decision binding mismatch',reviewed)
            # Reassess the real decision under today's unchanged strict gate.
            # Verdict FAILs and structured blocking findings are actionable, not
            # evidence-contract failures. Never repair a missing final citation.
            from production_gate import assess
            gate=assess(e['result']['decision'],{i['id'] for i in e['binding']['evidence']},[])
            allowed={k+': '+suffix for k in CRITERIA for suffix in ('fail','uncertain','blocking model finding')}
            invalid=[reason for reason in gate['blockers'] if reason not in allowed]
            blockers.extend(invalid)
            proof['valid']=not invalid
        def ledger():
            # All project unknowns are relevant to the shared ceiling, including
            # old reviewer holds unrelated to this run. A diagnosis releases none.
            with self.g.connect() as db:
                reviews=db.execute('SELECT id FROM reviews').fetchall()
                jobs=db.execute('SELECT id FROM jobs').fetchall()
            for row in reviews:
                rid=row[0]
                if not is_review_id(rid):
                    blockers.append('central review ledger contains malformed identity');continue
                checked('unknown or unverifiable paid review receipt: '+rid,lambda rid=rid:self._continuation_review_receipt(rid))
            for row in jobs:
                jid=row[0]
                if not is_hash(jid):
                    blockers.append('central generation ledger contains malformed identity');continue
                def job(jid=jid):
                    j=self.g.get(jid)
                    require(j.get('prediction_id') and j['status'] in ('candidate_ready','failed','cancelled','deleted','timeout'),'unresolved job')
                checked('unknown or unresolved paid generation intent: '+jid,job)
            return True
        before=len(blockers)
        ok=checked('central paid ledger unavailable or malformed',ledger)
        proof['no_unknown_liabilities']=ok is True and len(blockers)==before
        # The engine consumes these booleans, not the diagnostic eligible field.
        # Never emit its acceptance tuple when any part of the proof failed.
        proof['valid']=proof['valid'] and not blockers
        proof['eligible']=not blockers and all(proof[k] is True for k in ('registered','reviewed','valid','no_unknown_liabilities'))
        return proof

    def _continuation_review_receipt(self,rid,evaluation=None):
        """Validate receipt without recovering it or changing reserved status."""
        def require(value):
            if not value:raise ValueError('review receipt proof failed')
        require(is_review_id(rid))
        with self.g.connect() as db:row=db.execute('SELECT reserve,record FROM reviews WHERE id=?',(rid,)).fetchone()
        require(row is not None)
        record=json.loads(row['record']);binding=record['binding'];d=self.g.root/'reviews'/rid
        require(record['id']==rid and record['reserve_microusd']==row['reserve'] and row['reserve']>0)
        require(json.loads((d/'intent.json').read_bytes())==binding)
        request_raw=(d/'request.json').read_bytes();metadata_raw=(d/'metadata.json').read_bytes()
        require(digest(request_raw)==binding['request_sha256'] and digest(metadata_raw)==binding['metadata_sha256'])
        request=json.loads(request_raw);metadata=json.loads(metadata_raw)
        require(request['model']==binding['model']==metadata['id'])
        content=request['messages'][0]['content']
        require(digest(content[0]['text'].encode())==binding['prompt_sha256'])
        require(len(content)==1+2*len(binding['inputs']))
        import base64
        for i,inp in enumerate(binding['inputs']):
            raw=(d/f'input-{i}.png').read_bytes()
            require(digest(raw)==inp['review_sha256'])
            require(content[1+2*i]['text']==inp['role'])
            require(content[2+2*i]['image_url']['url']=='data:image/png;base64,'+base64.b64encode(raw).decode())
        if rid=='paid-pilot-01' and evaluation is None and not (d/'receipt.json').exists():
            from transport_reconciliation import verified_rejection
            verified_rejection(self.g,rid)
            return True  # rejected TRANSPORT only; full hold remains, no model verdict
        receipt_raw=(d/'receipt.json').read_bytes();receipt=json.loads(receipt_raw)
        require(receipt.get('model')==binding['model'] and not receipt.get('error'))
        choice=receipt['choices'][0];require(choice['finish_reason']=='stop')
        if evaluation:
            result=evaluation['result'];evidence=evaluation['binding']['evidence']
            require(result['review_binding']==binding and result['receipt_sha256']==digest(receipt_raw))
            require(result['reserve_microusd']==row['reserve'])
            require(json.loads(choice['message']['content'])==result['decision'])
            require(len(evidence)==len(binding['inputs']))
            for ev,inp in zip(evidence,binding['inputs']):
                require(inp['role']==ev['id']+' | '+ev['role'])
                require(inp['sha256']==inp['review_sha256']==ev['sha256'])
                require(inp['source_size']==inp['review_size']==ev['size'])
        return True

    def quality_authorization(self,rid):
        policy=json.loads((self.g.root/'quality-recovery-policy.json').read_bytes())
        if (not is_hash(rid) or policy.get('enabled') is not True or policy.get('parent_run_id')!=rid
            or policy.get('authorization_sha256')!=digest(QUALITY_AUTHORIZATION.read_bytes())):
            raise ValueError('server-side recovery authorization missing or drifted')
        return dict(parent_run_id=rid,authorization_sha256=policy['authorization_sha256'],
                    document=QUALITY_AUTHORIZATION.name,reason='Measured retained-source registration then new exact-density review; no old verdict repair')

    def recovery_plan(self,w):
        r=self.record(w['best_candidate_id']);tid=r.get('parent_candidate_id',r['id'])
        original=self.record(tid);raw=(self.g.root/'terrain'/tid/'source.png').read_bytes()
        if (original.get('processing_registration') or original['source_sha256']!=r['source_sha256']
            or digest(raw)!=r['source_sha256'] or r['layout_revision']!=w['frozen']['revision']):
            raise ValueError('recovery source provenance mismatch')
        guide=self.files(w['frozen']['revision'])['clean-guide.png']
        measured=measure_registration(raw,guide)
        if measured.get('blocker'):raise ValueError(measured['blocker'])
        if measured['measurements']['limits']!=w['frozen']['registration_limits']:raise ValueError('registration limits drift')
        reg=r.get('processing_registration',{})
        if (abs(reg.get('scale',0)-measured['scale'])<=1e-9 and
            np.allclose(reg.get('translation',[float('inf')]*2),measured['translation'],rtol=0,atol=1e-7)):
            raise ValueError('retained registration already matches; no identity-only review retry')
        finding=dict(criterion='layout_fidelity',observation='Stored original-to-canonical transform differs from frozen conservative measurement',
                     correction='Re-derive from unchanged original with measured single positive scalar and translation; independently review exact new pixels')
        return dict(action='register',findings=[finding],source_candidate_id=r['id'],source_original_id=tid,
                    source_sha256=digest(raw),guide_sha256=digest(guide),measurement=measured,
                    strategy_reason='free measured transform repair; not semantic or visual approval',requires_semantic_review=True)

    def liability_blockers(self):
        blockers=[]
        with self.g.connect() as db:
            reviews=db.execute('SELECT id FROM reviews').fetchall();jobs=db.execute('SELECT id FROM jobs').fetchall()
        for row in reviews:
            try:self._continuation_review_receipt(row[0])
            except Exception:blockers.append('unknown or unverifiable paid review receipt: '+row[0])
        for row in jobs:
            try:
                j=self.g.get(row[0])
                if not is_hash(row[0]) or not j.get('prediction_id') or j['status'] not in ('candidate_ready','failed','cancelled','deleted','timeout'):
                    raise ValueError('unresolved')
            except Exception:blockers.append('unknown or unresolved paid generation intent: '+row[0])
        return blockers

    def recovery_prerequisites(self,w,a):
        # Preparing immutable evidence is free and keeps the new review identity
        # distinct even when an unrelated historical liability still blocks POST.
        e=self.ev.prepare(a['candidate_id'],w['frozen']['style'],w['frozen']['density'])
        w['prepared_evaluation_id']=e['id']
        if e['id']==w['frozen']['evaluation_id']:raise ValueError('recovery did not produce new evidence')
        blockers=self.liability_blockers()
        if e['status']!='prepared_unreviewed':blockers.append('recovery review already attempted; no paid retry')
        if not self.g.policy.get('approved'):blockers.append('central paid policy closed')
        if not self.reviewer.config.enabled:blockers.append('reviewer disabled')
        return blockers

    def baseline(self,w):return self.summary(self.ev.get(w['evaluation_id']))
    def plan(self,w):
        e=self.ev.get(w['evaluation_id'])
        if e['gate']['production_approved']:return {'approved':True}
        findings=[f for f in e['gate']['findings'] if f.get('blocking')]
        if not findings:raise ValueError('no actionable structured findings; review invalid or uncertain')
        classes=sorted({f['criterion'] for f in findings})
        # This is a FREE measurement trial, not a claim that a local defect
        # is a global transform. Registration and independent final review
        # must still pass; unsafe geometry stops without purchasing a reroll.
        only_transform=classes==['layout_fidelity']
        previous=w['iterations'][-1].get('review',{}) if w['iterations'] else {}
        prompt=('Correction target is the LAST image: the actual current candidate, not a style reference. Keep its correct regions but repair the following observed defects. Image 1 remains exact geometry authority; all intermediate images retain their declared style/material roles. '
            'Preserve output framing, canonical geometry, collision, density and immutable intended style. Change only the cited defective regions and properties; preserve all passing criteria. Do not introduce materials or palette choices absent from the immutable specification. '
            +'\nObserved findings and precise corrections: '+canonical(findings).decode()
            +'\nPrevious attempt evidence: '+canonical(previous).decode()
            + '\nDo not reproduce these observed defects: '+canonical([f['observation'] for f in findings]).decode())
        return dict(correction_signature=digest(canonical(sorted((f['criterion'],f['observation'],f['correction']) for f in findings))),action='register' if only_transform else 'generate',strategy_reason='free frame measurement before any layout-only image purchase' if only_transform else 'cited semantic defects require targeted source correction',requires_semantic_review=True,classification=classes,findings=findings,prompt=prompt,prompt_sha256=digest(prompt.encode()),material_changes=[f['correction'] for f in findings if f['criterion']=='materials'] or {},avoid_changes=[f['observation'] for f in findings],reference_changes='unchanged immutable style/material crops; current candidate appended as correction target, not style',provider_fields=['prompt','image_urls','output_format'],source_candidate_id=w['latest_candidate_id'],source_evaluation_id=w['evaluation_id'])
    def inputs(self,w):
        sid=w['frozen']['style'];refs=self.styles.inputs(sid);tid=w['latest_candidate_id'];r=self.record(tid)
        source=(self.g.root/'terrain'/tid/'source.png').read_bytes()
        raw=png(np.array(render_original(self.load(w['frozen']['revision']),r,source,w['frozen']['density'])))
        refs=refs+[dict(reference_id=tid,role='correction_target',material=None,crop=None,source_sha256=r['source_sha256'],input_sha256=digest(raw),raw=raw)]
        return self.files(w['frozen']['revision'])['clean-guide.png'],refs
    def preflight(self):
        if not self.reviewer.config.enabled:raise ValueError('reviewer disabled; no image purchase without review path')
        meta=self.reviewer.preflight();self.g.provider.discover()
        return meta
    def quality_paid_guard(self,w):
        if w.get('continuation',{}).get('mode')!='seed-registration-recovery':return
        if self.quality_authorization(w['continuation']['parent_run_id'])!=w['continuation']['authorization']:
            raise ValueError('recovery authorization drift')
        if self.liability_blockers():raise ValueError('unresolved project liabilities; no paid recovery boundary')
        total=Decimal(str(self.g.policy.get('total_usd','0')))
        if not total.is_finite() or not 0<total<=10:raise ValueError('recovery requires original shared USD10 or lower ceiling')

    def prepare(self,w,a):
        self.quality_paid_guard(w)
        meta=self.preflight();guide,refs=self.inputs(w)
        binding=dict(layout_revision=w['frozen']['revision'],guide_sha256=digest(guide),style_spec_id=w['frozen']['style'],style_id=refs[0]['reference_id'],style_sha256=refs[0]['input_sha256'],style_references=[{k:v for k,v in r.items() if k!='raw'} for r in refs],prompt=self.styles.prompt(w['frozen']['style'])+'\n'+reference_prompt(refs)+'\n'+a['plan']['prompt'],auto_run_id=w['id'],auto_iteration_id=a['id'],correction_candidate_id=w['latest_candidate_id'])
        q=self.g.quote(binding)
        reserve=Decimal(meta['pricing']['prompt'])*meta['context_length']+Decimal(meta['pricing']['completion'])*4096
        if Decimal(self.g.status()['reserved_usd'])+reserve+Decimal(q['reserve_microusd'])/1000000>Decimal(self.g.policy['total_usd']):raise ValueError('budget insufficient for image plus conservative final review; prior holds retained')
        a['review_reservation_estimate_usd']=str(reserve);a['preflight_metadata_sha256']=digest(canonical(meta));return q
    def submit(self,w,a):
        self.quality_paid_guard(w)
        self.preflight();guide,refs=self.inputs(w)
        return self.g.confirm(a['quote_id'],w['frozen']['revision'],guide,refs[0]['raw'],[r['raw'] for r in refs[1:]])
    def recover(self,w,a):
        with self.g.connect() as db:row=db.execute('SELECT id FROM jobs WHERE id=?',(a['quote_id'],)).fetchone()
        if not row:return None
        j=self.g.resume(row[0])
        return j if j.get('prediction_id') else None
    def poll(self,w,a):return self.poll_call(a['job_id'])
    def register(self,w,a):
        tid=a['candidate_id'];r=self.record(tid)
        if r.get('processing_registration'):
            tid=r['parent_candidate_id'];r=self.record(tid)
        source=(self.g.root/'terrain'/tid/'source.png').read_bytes();guide=self.files(w['frozen']['revision'])['clean-guide.png']
        result=measure_registration(source,guide)
        if result.get('blocker'):return result
        from app import RegistrationRequest
        new=self.register_call(tid,RegistrationRequest(scale=result['scale'],translation=result['translation'],notes='Automatic conservative scalar registration, never axis warp. '+json.dumps(result['measurements'],separators=(',',':'))[:1700]))
        result['candidate_id']=new['id']
        if new['image_checks'].get('uncovered_guide_pixels') or new['image_checks'].get('uncovered_route_pixels'):
            result['blocker']='registration_coverage_failed; no extrapolation or masking permitted'
        return result
    def review(self,w,a):
        self.quality_paid_guard(w)
        e=self.ev.prepare(a['candidate_id'],w['frozen']['style'],w['frozen']['density'])
        if e['status']=='prepared_unreviewed':e=self.ev.run(e['id'],self.preflight(),self.reviewer.post)
        elif e['status']!='reviewed':e=self.ev.recover(e['id'])
        if e['status']!='reviewed':raise ValueError('review_unknown_submission; retained liability; no retry')
        return self.summary(e)

def install(app,files,record,load,register,poll):
    from constrained_adapter import ConstrainedAdapter
    service=AutoRepair(app.state.generation,ConstrainedAdapter(app,files,record,load,register,poll));app.state.auto_repair=service
    def guarded(fn):
        try:return fn()
        except (ValueError,KeyError,FileNotFoundError):raise HTTPException(409,'Automatic run missing, stale, unauthorized or already bound; no reset/retry.') from None
    @app.post('/api/auto-repair/start',status_code=201)
    def start(body:Start):
        w=guarded(lambda:service.start(body));service.launch(w['id']);return service.get(w['id'])
    @app.get('/api/generation/jobs/{jid}/constrained-original')
    def constrained_original(jid:str):
        from fastapi.responses import Response
        def read():
            if not is_hash(jid):raise ValueError('invalid job identity')
            j=service.g.get(jid)
            if 'constrained' not in j['binding']:raise ValueError('not a constrained job')
            raw=(service.g.root/'constrained-outputs'/jid/'provider-original.bin').read_bytes()
            if digest(raw)!=j['preservation']['provider_original_sha256']:raise ValueError('provider original drift')
            kind=Image.open(io.BytesIO(raw)).format
            if kind not in ('JPEG','PNG'):raise ValueError('unsupported original format')
            return raw,kind
        raw,kind=guarded(read)
        return Response(raw,media_type='image/jpeg' if kind=='JPEG' else 'image/png',
                        headers={'X-Terrain-Status':'rejected-or-unapproved-provider-original'})
    @app.post('/api/auto-repair/{rid}/constrained',status_code=201)
    def constrained_start(rid:str,body:PaidReview):
        w=guarded(lambda:service.constrained_run(rid));service.launch(w['id']);return service.get(w['id'])
    @app.post('/api/auto-repair/{rid}/reconcile-transport')
    def reconcile_transport(rid:str,body:PaidReview):
        def apply():
            from transport_reconciliation import reconcile
            authority=service.adapter.quality_authorization(rid)
            service.get(rid)
            return reconcile(service.g,authority['authorization_sha256'])
        return guarded(apply)
    @app.get('/api/auto-repair/{rid}/reconcile-transport')
    def read_transport(rid:str):
        def read():
            from transport_reconciliation import verified_rejection
            service.get(rid)
            return verified_rejection(service.g,'paid-pilot-01')
        return guarded(read)
    @app.post('/api/auto-repair/{rid}/recover-seed',status_code=201)
    def recover_seed(rid:str,body:PaidReview):
        w=guarded(lambda:service.recover_seed(rid));service.launch(w['id']);return service.get(w['id'])
    @app.post('/api/auto-repair/{rid}/recover-seed/resume')
    def resume_seed(rid:str,body:PaidReview):
        w=guarded(lambda:service.resume_quality(rid));return service.launch(w['id'])
    @app.get('/api/auto-repair/{rid}')
    def get(rid:str):return guarded(lambda:service.get(rid))
    @app.get('/api/auto-repair/{rid}/continuation-readiness')
    def continuation_readiness(rid:str):
        result=dict(eligible=False,blockers=[],lifetime_iterations=None,lifetime_limit=15,
                    best_candidate_id=None,latest_candidate_id=None,best_evaluation_id=None,
                    latest_evaluation_id=None,read_only=True,authorization_required=True,
                    continuation_enabled=False)
        if not is_hash(rid):
            result['blockers']=['malformed run id: expected lowercase SHA256'];return result
        try:w=service.get(rid)
        except Exception:
            result['blockers']=['run missing, malformed or frozen contract integrity failure'];return result
        try:
            for output,key in (('best_candidate_id','best_candidate_id'),('latest_candidate_id','latest_candidate_id'),('best_evaluation_id','best_evaluation_id'),('latest_evaluation_id','evaluation_id')):
                result[output]=w[key] if is_hash(w.get(key)) else None
            count=len(service.history(w))
            inherited=w.get('inherited_iterations',0)
            if type(inherited) is not int or inherited<0 or count!=inherited+len(w['iterations']):raise ValueError('count')
            result['lifetime_iterations']=count
            attempts=w['iterations'];last=attempts[-1] if attempts else {}
            registration_stop=(w['phase']=='register' and last.get('registration',{}).get('blocker')==w['stop_reason']
                and str(w['stop_reason']).startswith('registration_')
                and (last.get('job_status')=='candidate_ready' or last.get('plan',{}).get('action')=='register'))
            capped=(w['phase']=='plan' and w['stop_reason']=='iteration_limit' and last.get('review',{}).get('valid') is True)
            if w['status']!='needs_attention' or w['cancel_requested'] or not (registration_stop or capped):
                result['blockers'].append('stop is not safely continuable; unknown outcomes and cancellation never retry')
            if count>=15:result['blockers'].append('lifetime iteration limit exhausted')
            proof=service.adapter.continuation_seed(w)
            result['seed_proof']=proof
            result['blockers'].extend(proof['blockers'])
            result['eligible']=proof['eligible'] and not result['blockers']
        except Exception:
            result['blockers'].append('retained run history or seed proof malformed/unverifiable')
        return result
    @app.post('/api/auto-repair/{rid}/resume')
    def resume(rid:str):
        guarded(lambda:service.resume(rid));return service.launch(rid)
    @app.post('/api/auto-repair/{rid}/cancel')
    def cancel(rid:str):return guarded(lambda:service.cancel(rid))
    @app.on_event('startup')
    def restart_workers():
        with service.g.connect() as db:ids=[r[0] for r in db.execute('SELECT id FROM auto_runs')]
        for rid in ids:
            if service.get(rid)['status']=='running':service.launch(rid)
    return service
