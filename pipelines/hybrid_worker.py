"""Standalone persisted worker. Every paid call goes through Store's central intent."""
import base64,fcntl,io,json,os,time,argparse,subprocess,tempfile,zipfile
from pathlib import Path
from decimal import Decimal,ROUND_CEILING
from PIL import Image
from artifacts import canonical,digest
from generation import Generation
from hybrid_store import Store,TERMINAL
from hybrid_layout import compile_layout,Layout
from hybrid_render import render,PreviewMaterials
from hybrid_sampling import sample_world,correct_sampling
from hybrid_artifact import build,png,replay_materials,ROOT,ACTOR,artifact_binding,verify_artifact
from hybrid_models import OpenRouter,MaterialImage,Plan,CropMap,Review,validate_crops,review_gate,CRITERIA

def immutable(path,raw):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    try:
        with path.open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
    except FileExistsError:
        if path.read_bytes()!=raw:raise ValueError('Unveränderliche Evidenz verändert')
    return raw

def runtime_version():
    return digest(canonical({n:digest((ROOT/n).read_bytes()) for n in ['hybrid_reassessment.py','hybrid_reassessment_repair.py','hybrid_sampling_repair.py','hybrid_directive_repair.py','hybrid_material_repair.py','billing_settlement.py','hybrid_source_recovery.py','hybrid_worker.py','hybrid_target_layout.py','hybrid_recovery.py','hybrid_reference.py','hybrid_package.py','hybrid_sampling.py','hybrid_layout.py','hybrid_layout_review.py','hybrid_models.py','hybrid_render.py','hybrid_painted_terrain.py','hybrid_api.py','hybrid_artifact.py','hybrid_export.py','hybrid_store.py','static/hybrid-navigator.html']}))

def _target_contract_issues(layout,config):
    """Apply the opt-in target geometry gate only to runs bound to that contract."""
    from hybrid_target_layout import CONTRACT,target_layout_issues
    if config.get('layout_contract')!=CONTRACT:
        return []
    return target_layout_issues(layout)

def _paint_alignment_feedback(error,repairs):
    """Misaligned paint becomes a bounded corrective repaint, not a dead run."""
    if repairs>=2 or 'semantic alignment' not in error:return None
    return error.replace('painted semantic alignment mismatch: ','')+' was painted in the wrong material category'

def _review_repaint_feedback(raw):
    """Failed review corrections become corrective repaint text for the
    painted flow (the crop-sampling repair cannot apply to a frozen grid)."""
    parts=[]
    for c in raw.get('criteria',{}).values():
        correction=(c.get('correction') or '').strip()
        if c.get('verdict')=='fail' and correction and correction!='None.':parts.append(correction)
    return ' '.join(parts) or 'resolve the failed review criteria'

def _plan_contract_feedback(plan):
    """Unsupported/uncertainty findings become bounded planner feedback that
    spells out the deterministic derivations instead of aborting the run."""
    issues=[]
    if plan.get('unsupported') or plan.get('layout',{}).get('unsupported'):
        issues.append('unsupported must be empty; choose and state the closest representable interpretation')
    if plan.get('material_plan',{}).get('uncertainty'):
        issues.append('uncertainty must be empty; sandy shore, wall texture and stair treads/risers are derived automatically by the service')
    if issues:return 'PLAN CONTRACT FAIL: '+'; '.join(issues)+' Return an empty unsupported list and empty uncertainty list.'
    return None

def _material_contract_feedback(material_plan,layout):
    """Deterministic material-key contract; mismatches become bounded planner
    feedback instead of an abort after paid review calls."""
    from hybrid_recovery import normalize_material_plan
    required={c for row in layout['cells'] for c in row}|{'wall'}
    try:
        normalize_material_plan(material_plan,required)
    except ValueError as exc:
        return ('MATERIAL PLAN FAIL: '+str(exc)+' Provide exactly one materials entry per grid semantic plus wall; '
            'never merge wall into another entry. Required keys: '+', '.join(sorted(required)))
    return None

def _compile_feedback(raw):
    """Compiler failures (bad transitions, unsupported geometry) become
    bounded planner feedback instead of killing the run."""
    from hybrid_layout import compile_layout
    try:compile_layout(raw)
    except ValueError as exc:
        return 'GEOMETRY COMPILE FAIL: '+str(exc)+' Fix the grid/transitions exactly.'
    return None


def authorization(store,r):
    p=store.g.root/'hybrid-authorizations'/(r['id']+'.json')
    if not p.exists():raise ValueError('Neue explizite laufgebundene Budgetfreigabe fehlt')
    a=json.loads(p.read_bytes())
    c=r['config']
    if a.get('config_sha256')!=digest(canonical(c)) or a.get('expires',0)<=time.time():raise ValueError('Freigabe passt nicht/abgelaufen')
    for key in ['max_images','max_calls','budget_microusd']:
        if a.get(key)!=c[key]:raise ValueError('Freigabe-Limits stimmen nicht')
    if a.get('liability_authorization'):
        with store.g.connect() as db:
            ack=db.execute('SELECT record FROM hybrid_liability_authorizations WHERE id=? AND run=?',(a['liability_authorization'],r['id'])).fetchone()
            if not ack or digest(ack['record'].encode())!=a['liability_authorization']:raise ValueError('Liability-Freigabe fehlt/verändert')
            scope=json.loads(ack['record'])
            if scope.get('run_id')!=r['id'] or scope.get('config_sha256')!=a['config_sha256'] or scope.get('expires',0)<=time.time():raise ValueError('Liability-Freigabe falsch/abgelaufen')
            if any(scope.get(k)!=a.get(k) for k in ['budget_microusd','max_calls','max_images']):raise ValueError('Liability-Limits stimmen nicht')
            unknown={x['id'] for x in db.execute('SELECT id FROM hybrid_calls WHERE receipt IS NULL')}
            if unknown!={x['call_id'] for x in scope.get('liabilities',[])}:raise ValueError('Unbekannte Requests außerhalb der Haftungsfreigabe; Holds bleiben')
    return a

class Worker:
    def __init__(self,store):self.s=store;self.root=store.g.root/'hybrid';self.root.mkdir(exist_ok=True)
    def accept(self,rid,raw):
        existing=self.s.get(rid)
        if existing['phase']!='layout_preview':raise ValueError('Layout bereits gesperrt')
        world=compile_layout(raw)
        guide=png(render(world,PreviewMaterials())[0]);guide_file='accepted-'+world['revision']+'.png'
        immutable(self.root/rid/guide_file,guide)
        with self.s.g.connect() as db:
            db.execute('BEGIN IMMEDIATE');r=db.execute('SELECT * FROM hybrid_runs WHERE id=?',(rid,)).fetchone()
            if not r or r['phase']!='layout_preview' or r['lease']>time.time() or r['cancel']:raise ValueError('Layout gesperrt/Worker aktiv')
            config=json.loads(r['config']);constraints=config.get('constraints',{})
            if constraints and any(world[k]!=constraints[k] for k in ['width','height','actor_width']):raise ValueError('Eingefrorene Größenconstraints verletzt')
            record=json.loads(r['record']);record.update(guide_file=guide_file,guide_sha256=digest(guide),world=world,accepted_layout=raw,frozen_sha256=digest(canonical({'config':config,'layout':raw})),accepted_at=time.time(),attempt=0)
            db.execute("UPDATE hybrid_runs SET record=?,phase='generating' WHERE id=?",(canonical(record).decode(),rid));self.s.event(db,rid,{'phase':'generating','layout_frozen':world['revision']})
        return self.s.get(rid)
    def tick(self):
        # Process lock fences lengthy local rendering too; DB token fences all writes.
        with (self.root/'worker.lock').open('a') as lock:
            try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            except BlockingIOError:return False
            r=self.s.claim()
            if not r:return False
            try:self.process(r)
            except Exception as exc:
                current=self.s.get(r['id'])
                if current['phase'] not in TERMINAL:
                    # Do not persist provider bodies/URLs/exceptions; validators use safe messages.
                    reason='Validierung/Provider/Verifikation fehlgeschlagen; Evidenz prüfen, kein Paid-Retry'
                    if isinstance(exc,ValueError):reason=str(exc)[:1000]
                    self.s.save(r,phase='cancelled' if current['cancel_requested'] else 'needs_attention',stop_reason=reason)
            finally:self.s.release(r)
            return True
    def process(self,r):
        cfg=r['config'];d=self.root/r['id'];d.mkdir(exist_ok=True)
        if r['cancel_requested']:self.s.save(r,phase='cancelled',stop_reason='Abbruch; bestehende Receipts/Holds bleiben');return
        if cfg.get('runtime_version') and cfg['runtime_version']!=runtime_version():raise ValueError('Runtime-/Rendererrevision verändert; neuen Lauf planen')
        if time.time()-r['created']>cfg['max_seconds']:raise ValueError('Laufzeitlimit erreicht')
        inherited_plan=None;inherited_cfg=None
        if cfg.get('continuation'):
            from hybrid_recovery import validated_parent
            _,inherited_plan,inherited_cfg=validated_parent(self.s,cfg['continuation'])
        if cfg['mode']=='live':
            try:auth=authorization(self.s,r)
            except ValueError:
                self.s.save(r,phase='await_authorization',stop_reason='Neue explizite laufgebundene Budgetfreigabe fehlt');return
            planner=OpenRouter(cfg['planner_model']);reviewer=OpenRouter(cfg['reviewer_model'])
            if not r.get('metadata'):
                metas={'planner':planner.preflight(),'reviewer':reviewer.preflight()}
                self.s.save(r,metadata=metas);r=self.s.get(r['id'])
            metas=r['metadata']
            from hybrid_reference import reference_bytes
            reference,_=reference_bytes(self.s.g.root,cfg)
            if digest(reference)!=cfg['reference_sha256']:raise ValueError('Stilreferenz verändert')
            actor=(ACTOR/'character.png').read_bytes()
            if cfg['actor_sha256']!=digest(actor):raise ValueError('Figur verändert')
        if r['phase']=='queued' and cfg.get('continuation',{}).get('kind')=='source_reassessment':
            from hybrid_reassessment import inherit_archive
            inherit_archive(self,r);return
        if r['phase']=='queued' and cfg.get('continuation',{}).get('kind')=='directive_repair':
            from hybrid_directive_repair import inherit_directive
            inherit_directive(self,r);return
        if r['phase']=='queued' and cfg.get('continuation',{}).get('kind')=='sampling_repair':
            from hybrid_sampling_repair import inherit_sampling_repair
            inherit_sampling_repair(self,r);return
        if r['phase']=='queued' and cfg.get('continuation',{}).get('kind')=='source_reassessment_repair':
            from hybrid_reassessment_repair import inherit_repair
            inherit_repair(self,r);return
        if r['phase']=='queued' and cfg.get('continuation',{}).get('kind')=='material_repair':
            from hybrid_material_repair import inherit_material
            inherit_material(self,r);return
        if r['phase']=='queued' and cfg.get('continuation',{}).get('kind')=='source':
            from hybrid_source_recovery import inherit_source
            inherit_source(self,r);return
        if r['phase'] in ['queued','planning']:
            self.s.save(r,phase='planning')
            if cfg['mode']=='replay':
                raw=cfg['layout_fixture'];material_plan={'intent':'REPLAY historical retained material pixels','materials':{},'avoid':[],'uncertainty':['Historical operator crop selection replayed; no model inference']};interpretation='REPLAY-Fixture: keine Sprachübersetzung'
                w=compile_layout(raw);image,*_=render(w,PreviewMaterials());preview=png(image)
            else:
                planner_cfg=inherited_cfg or cfg
                if inherited_plan is not None:
                    planner=OpenRouter(planner_cfg['planner_model'])
                    metas={**metas,'planner':inherited_cfg.get('metadata',{}).get('planner',metas['planner'])}
                    plan=inherited_plan;raw=plan['layout'];material_plan=plan['material_plan'];interpretation=plan['interpretation']
                    w=compile_layout(raw);image,*_=render(w,PreviewMaterials());preview=png(image)
                    immutable(d/'planner-result.json',canonical(plan));immutable(d/'layout-preview-1.png',preview)
                    immutable(d/'transition-normalization.json',canonical(w['normalization']))
                    from hybrid_recovery import normalize_material_plan
                    original_mp=material_plan;material_plan=normalize_material_plan(original_mp,{c for row in w['cells'] for c in row}|{'wall'})
                    immutable(d/'material-normalization.json',canonical(dict(input=original_mp,input_sha256=digest(canonical(original_mp)),canonical=material_plan,canonical_sha256=digest(canonical(material_plan)),contract='cliff-wall-alias/1')))
                    immutable(d/'layout-preview.png',preview)
                    if not material_plan['uncertainty'] and not plan['unsupported'] and not raw['unsupported']:
                        self.s.save(r,phase='layout_preview',layout=raw,world=w,material_plan=material_plan,interpretation=interpretation,layout_iteration=1,layout_candidate=raw,stop_reason=None)
                        if cfg.get('auto_continue'):
                            self.s.release(r);self.accept(r['id'],raw)
                    else:self.s.save(r,phase='needs_attention',stop_reason='Geometrie/Materialplan benötigt Owner Review')
                    return
                from hybrid_layout_review import LayoutAssessment,layout_planner_prompt,layout_review_prompt,validate_assessment
                maximum=min(5,int(cfg.get('layout_review_iterations',5)))
                for model_name in ['planner_model','reviewer_model']:
                    if not cfg.get(model_name):raise ValueError('Planner-/Reviewer-Modell fehlt')
                if inherited_plan is None and (cfg['planner_model']==cfg['reviewer_model'] or planner.model==reviewer.model):
                    raise ValueError('Unabhängige Layoutbewertung erfordert getrennte Planner-/Reviewer-Modelle')
                for key in ['planner','reviewer']:
                    if metas[key].get('id')!=cfg[key+'_model']:raise ValueError('Modellrollen-Metadaten stimmen nicht')
                if 'image' not in metas['reviewer'].get('architecture',{}).get('input_modalities',[]):raise ValueError('Layout-Reviewer muss Vorschau-Bilder sehen können')
                if r.get('layout_iteration',0)>=maximum:raise ValueError('Circuit breaker: Layout-review iteration limit reached')
                available=sum(x['amount'] for x in self.s.calls(r['id']))
                estimated=0
                for policy_role,model_obj,key in [('planner',planner,'planner'),('layout_review',reviewer,'reviewer')]:
                    token_policy=model_obj.policy(cfg,policy_role,metas[key])
                    estimated+=model_obj.cost(metas[key],token_policy['max_tokens'])
                run_spent=sum(x['amount'] for x in self.s.calls(r['id']))
                if r['call_count']+2>cfg['max_calls'] or run_spent+estimated>cfg['budget_microusd']:
                    raise ValueError('Aufruf-/Budget-Circuit-Breaker vor nächster Planner-/Reviewrunde')
                ledger=self.s.g.status()
                if Decimal(str(ledger['reserved_usd']))*1_000_000+estimated>int(Decimal(str(ledger['total_budget_usd']))*1_000_000):
                    raise ValueError('Projektbudget reicht für Planner plus unabhängigen Reviewer nicht aus')
                if not auth.get('liability_authorization'):
                    with self.s.g.connect() as db:
                        if db.execute('SELECT 1 FROM hybrid_calls WHERE receipt IS NULL').fetchone():
                            raise ValueError('Unbekannte bezahlte Requests blockieren neue Runde; Holds bleiben')
                else:
                    with self.s.g.connect() as db:
                        row=db.execute('SELECT record FROM hybrid_liability_authorizations WHERE id=? AND run=?',(auth['liability_authorization'],r['id'])).fetchone()
                        if not row or digest(row['record'].encode())!=auth['liability_authorization']:
                            raise ValueError('Liability-Freigabe fehlt/verändert')
                        scope=json.loads(row['record'])
                        if scope.get('config_sha256')!=digest(canonical(cfg)) or scope.get('expires',0)<=time.time():
                            raise ValueError('Liability-Freigabe falsch/abgelaufen')
                        acknowledged={x['call_id'] for x in scope.get('liabilities',[])}
                        unknown={x['id'] for x in db.execute('SELECT id FROM hybrid_calls WHERE receipt IS NULL')}
                        if unknown!=acknowledged:
                            raise ValueError('Unbekannte bezahlte Requests außerhalb der gebundenen Haftungsfreigabe; Holds bleiben')
                r=self.s.get(r['id'])
                
                iteration=int(r.get('layout_iteration',0))+1
                if iteration>maximum:raise ValueError('Circuit breaker: Layout-review iteration cap reached')
                feedback=r.get('layout_review_feedback','')
                prior=r.get('layout_candidate')
                prompt=layout_planner_prompt(cfg['description'],cfg['constraints'],iteration,maximum,feedback,prior)
                role='planner' if iteration==1 else 'planner-'+str(iteration)
                if inherited_plan is not None:raise ValueError('Layout-review loop requires its own fresh, independently reviewed planner proposal')
                reviewer_policy=reviewer.policy(cfg,'layout_review',metas['reviewer'])
                reviewer_hold=reviewer.cost(metas['reviewer'],reviewer_policy['max_tokens'])
                result=planner.call(self.s,r,role,prompt,{'reference':reference,'actor':actor},Plan.model_json_schema(),auth,metas['planner'],reserve_headroom=reviewer_hold)
                plan=Plan.model_validate(result).model_dump();immutable(d/f'planner-result-{iteration}.json',canonical(plan))
                if iteration==1:immutable(d/'planner-result.json',canonical(plan))
                plan_issue=_plan_contract_feedback(plan)
                if plan_issue:
                    if iteration>=maximum:raise ValueError('Circuit breaker: '+plan_issue)
                    self.s.save(r,phase='planning',layout_iteration=iteration,layout_candidate=plan['layout'],layout_review_feedback=plan_issue,layout_review={'decision':'revise','failed_criteria':['plan_contract'],'plan_issue':plan_issue,'reviewer_skipped':'deterministic plan contract; checked before buying a review'},stop_reason=None)
                    return
                raw=plan['layout'];material_plan=plan['material_plan'];interpretation=plan['interpretation']
                if any(raw[k]!=cfg['constraints'][k] for k in ['width','height','actor_width']):raise ValueError('Planner verletzt Größenconstraints')
                structural_issues=_target_contract_issues(raw,cfg)
                # Fail locally before spending a reviewer call on layouts that cannot meet the requested physical contract.
                if structural_issues:
                    if iteration>=maximum:raise ValueError('Circuit breaker nach fünf Geometriekorrekturen: '+'; '.join(structural_issues))
                    feedback='STRUCTURAL CONTRACT FAIL: '+'; '.join(structural_issues)+' Fix these exact layout-grid constraints; do not explain or relax them.'
                    self.s.save(r,phase='planning',layout_iteration=iteration,layout_candidate=raw,layout_review_feedback=feedback,layout_review={'decision':'revise','failed_criteria':['structural_contract'],'structural_issues':structural_issues,'reviewer_skipped':'deterministic geometry guard; no need to buy review of invalid raster'},stop_reason=None)
                    return
                material_feedback=_material_contract_feedback(material_plan,raw)
                if material_feedback:
                    if iteration>=maximum:raise ValueError('Circuit breaker: '+material_feedback)
                    self.s.save(r,phase='planning',layout_iteration=iteration,layout_candidate=raw,layout_review_feedback=material_feedback,layout_review={'decision':'revise','failed_criteria':['material_contract'],'material_issues':[material_feedback],'reviewer_skipped':'deterministic material contract; checked before buying a review'},stop_reason=None)
                    return
                compile_issue=_compile_feedback(raw)
                if compile_issue:
                    if iteration>=maximum:raise ValueError('Circuit breaker: '+compile_issue)
                    self.s.save(r,phase='planning',layout_iteration=iteration,layout_candidate=raw,layout_review_feedback=compile_issue,layout_review={'decision':'revise','failed_criteria':['geometry_compile'],'compile_issue':compile_issue,'reviewer_skipped':'deterministic compiler; checked before buying a review'},stop_reason=None)
                    return
                w=compile_layout(raw);immutable(d/f'transition-normalization-{iteration}.json',canonical(w['normalization']))
                image,*_=render(w,PreviewMaterials());preview=png(image);immutable(d/f'layout-preview-{iteration}.png',preview)
                layout_sha=digest(canonical(raw));preview_sha=digest(preview)
                reviewer_prompt=layout_review_prompt(cfg['description'],raw,layout_sha,preview_sha,iteration,maximum)
                assessment_raw=reviewer.call(self.s,r,'layout_review-'+str(iteration),reviewer_prompt,{'layout_preview':preview},LayoutAssessment.model_json_schema(),auth,metas['reviewer'],reserve_headroom=reviewer_hold)
                assessment=validate_assessment(assessment_raw,layout_sha,preview_sha)
                deterministic=_target_contract_issues(raw,cfg)
                assessment['structural_issues']=deterministic
                if deterministic:assessment['approved']=False;assessment['review']['decision']='revise'
                immutable(d/f'layout-review-{iteration}.json',canonical(assessment))
                self.s.save(r,layout_iteration=iteration,layout_candidate=raw,layout_review=assessment)
                if not assessment['approved']:
                    corrections=[]
                    for name,criterion in assessment['review']['criteria'].items():
                        if criterion['verdict']!='pass':corrections.append(f"{name}: {criterion['verdict']} — {criterion['correction']}")
                    if iteration>=maximum:raise ValueError(f'Circuit breaker: unabhängige Layoutprüfung nach {maximum} Iterationen nicht bestanden; '+ '; '.join(corrections))
                    self.s.save(r,phase='planning',layout_review_feedback='\n'.join(corrections),stop_reason=None);return
            if cfg['mode']=='live':
                from hybrid_recovery import normalize_material_plan
                original_mp=material_plan;material_plan=normalize_material_plan(original_mp,{c for row in w['cells'] for c in row}|{'wall'})
                immutable(d/'material-normalization.json',canonical(dict(input=original_mp,input_sha256=digest(canonical(original_mp)),canonical=material_plan,canonical_sha256=digest(canonical(material_plan)),contract='cliff-wall-alias/1')))
            immutable(d/'layout-preview.png',preview)
            self.s.save(r,phase='layout_preview',layout=raw,world=w,material_plan=material_plan,interpretation=interpretation,stop_reason=None,layout_iteration=(1 if cfg['mode']=='replay' else iteration))
            self.s.release(r)
            if cfg.get('auto_continue'):self.accept(r['id'],raw)
            return
        if r['phase']=='await_authorization':return
        if r.get('frozen_sha256')!=digest(canonical({'config':cfg,'layout':r['accepted_layout']})):raise ValueError('Eingefrorene Eingaben verändert')
        w=compile_layout(r['accepted_layout']);attempt=r.get('attempt',0);out=d/('candidate-'+str(attempt*3+r.get('local_count',0)))
        if cfg['mode']=='replay':
            source,binding=replay_materials()
            sd=d/'sample-0-0';sw=sample_world(w)
            build(sd,sw,source,binding,{'mode':'replay_sample','production_approved':False,'target_revision':w['revision']})
            immutable(sd/'guide.png',png(render(sw,PreviewMaterials())[0]))
            self.s.save(r,sample_directory=sd.name,sample_binding=artifact_binding(sd),sample_guide_sha256=digest((sd/'guide.png').read_bytes()))
            build(out,w,source,binding,{'mode':'replay','production_approved':False,'limitations':['retained manual crops; not autonomous selection','no fresh planner or review']})
            self.s.save(r,phase='needs_attention',artifact_binding=artifact_binding(out),latest='candidate-'+str(attempt),stop_reason='REPLAY abgeschlossen: echte historische Pixel, keine autonome Crop-/Modellprüfung und keine Produktionsfreigabe')
            return
        if r['phase']=='generating' and cfg.get('terrain_flow')=='painted_flat':
            from hybrid_painted_terrain import make_guide,prompt,GUIDE_SIZE
            role='image-'+str(attempt)
            guide=make_guide(w);immutable(d/f'flat-guide-{attempt}.png',guide)
            self.s.save(r,flat_guide_file=f'flat-guide-{attempt}.png',flat_guide_sha256=digest(guide),phase='generating')
            if r.get('painted_request'):
                prepared=r['painted_request']
            else:
                prepared=None
            with self.s.g.connect() as db:
                known=db.execute('SELECT * FROM hybrid_calls WHERE run=? AND role=?',(r['id'],role)).fetchone()
            if known:
                if prepared is None:
                    request_file=d/f'painted-request-{attempt}.json'
                    if not request_file.exists():raise ValueError('Bekannter terrain-image intent ohne Requestartefakt; kein Retry')
                    prepared=json.loads(request_file.read_bytes())
                if known['request']!=canonical(prepared).decode() or known['amount']!=prepared['amount'] or known['id']!=digest(canonical([r['id'],role,prepared])):raise ValueError('Painted terrain request drift')
                ledger=None
                with self.s.g.connect() as db:ledger=db.execute('SELECT * FROM reviews WHERE id=?',(known['id'],)).fetchone()
                if not ledger or ledger['reserve']!=known['amount'] or json.loads(ledger['record'])['binding']['request_sha256']!=digest(known['request'].encode()):raise ValueError('Painted terrain ledger drift')
                receipt=json.loads(known['receipt']) if known['receipt'] else None
                if not receipt or not receipt.get('id'):raise ValueError('Terrain-image receipt unbekannt; kein Retry')
                self.s.save(r,phase='polling',prediction_id=receipt['id'],image_started=r.get('image_started',time.time()),painted_request=prepared,painted_image=True);return
            if prepared is None:
                p=MaterialImage();schema=p.discover()
                inputs={'flat_layout':guide,'style_reference':reference}
                urls=[p.upload(raw,name+'.png') for name,raw in inputs.items()]
                body=p.inputs(prompt(w,r.get('paint_correction')),urls,size=GUIDE_SIZE)
                import jsonschema
                jsonschema.validate(body,schema)
                quote=p.quote(body)
                if quote.get('currency')!='USD':raise ValueError('Kein USD-Preis')
                amount=int((Decimal(str(quote['price']))*1_000_000).to_integral_value(rounding=ROUND_CEILING))
                prepared={'attempt':attempt,'body':body,'schema':schema,'quote':quote,'amount':amount,'inputs':[dict(id=k,sha256=digest(v)) for k,v in sorted(inputs.items())]}
                immutable(d/f'painted-request-{attempt}.json',canonical(prepared))
                reviewer=OpenRouter(cfg['reviewer_model']);review_meta=metas['reviewer']
                headroom=2*reviewer.cost(review_meta,reviewer.policy(cfg,'review_sample',review_meta)['max_tokens'])
                intent=self.s.reserve_call(r,role,prepared,amount,auth,headroom)
                if not intent['new']:raise ValueError('Unexpected existing image identity; no retry')
                receipt=p.submit(body);self.s.receipt(intent['id'],receipt)
                if not receipt or not receipt.get('id'):raise ValueError('Terrain-image receipt unbekannt; kein Retry')
                self.s.save(r,phase='polling',prediction_id=receipt['id'],image_started=time.time(),painted_request=prepared,painted_image=True);return
        if r['phase']=='generating' and r.get('correction_kind')=='scene_concept' and not (d/f'concept-{attempt}.png').exists():
            # Stage 1 of the owner scene-concept flow: paint the whole scene first.
            role='image-'+str(attempt)+'-concept'
            guide=(d/r['guide_file']).read_bytes()
            if digest(guide)!=r['guide_sha256']:raise ValueError('Guide drift')
            prompt=('PAINT this exact isometric scene as one beautiful coherent 16-bit pixel art painting: follow the guide zones, heights, stair transitions, water and path positions EXACTLY, styled like the reference. Rich painterly material texture, natural colors, gorgeous look. Output the full scene painting only.')
            images={'reference':reference,'guide':guide}
            inputs=[dict(id=k,sha256=digest(v)) for k,v in images.items()]
            p=MaterialImage();schema=p.discover()
            urls=[p.upload(raw,name+'.png') for name,raw in images.items()]
            body=p.inputs(prompt,urls)
            import jsonschema
            jsonschema.validate(body,schema)
            q=p.quote(body)
            if q.get('currency')!='USD':raise ValueError('Kein USD-Preis')
            amount=int((Decimal(str(q['price']))*1_000_000).to_integral_value(rounding=ROUND_CEILING))
            prepared={'attempt':attempt,'body':body,'schema':schema,'quote':q,'amount':amount,'inputs':inputs}
            immutable(d/f'image-request-{attempt}-concept.json',canonical(prepared))
            if r['call_count']+3>cfg['max_calls']:raise ValueError('Aufruflimit fuer Konzeptfluss')
            intent=self.s.reserve_call(r,role,prepared,prepared['amount'],auth,0)
            if intent['new']:
                receipt=p.submit(prepared['body']);self.s.receipt(intent['id'],receipt)
            else:receipt=intent['receipt']
            if not receipt or not receipt.get('id'):raise ValueError('Bildreceipt unbekannt; nicht wiederholen')
            deadline=time.time()+600
            while True:
                result=p.poll(receipt['id'])
                if result.get('status') in ['failed','cancelled','deleted','timeout']:raise ValueError('Provider hat Szene nicht geliefert')
                if result.get('status')=='completed':break
                if time.time()>deadline:raise ValueError('Pollingzeitlimit Konzept; Receipt bleibt erhalten')
                time.sleep(5)
            if len(result.get('outputs',[]))!=1:raise ValueError('Bildanzahl falsch')
            raw=p.download(result['outputs'][0]);im=Image.open(io.BytesIO(raw))
            if im.format!='PNG' or im.width*im.height>8_000_000:raise ValueError('Bildformat/Pixelgrenze falsch')
            im.verify();immutable(d/f'concept-{attempt}.png',raw)
            self.s.save(r,concept_sha256=digest(raw));return
        if r['phase']=='generating':
            if cfg.get('no_new_images'):raise ValueError('Retained-source reassessment forbids image generation')
            # Recover the exact durable image intent before any provider metadata.
            role='image-'+str(attempt)
            with self.s.g.connect() as db:
                known=db.execute('SELECT * FROM hybrid_calls WHERE run=? AND role=?',(r['id'],role)).fetchone()
                if known:
                    prepared=r.get('prepared_image')
                    if not prepared or known['request']!=canonical(prepared).decode() or known['id']!=digest(canonical([r['id'],role,prepared])) or known['amount']!=prepared['amount']:raise ValueError('Bildrequest-Drift')
                    ledger=db.execute('SELECT * FROM reviews WHERE id=?',(known['id'],)).fetchone()
                    if not ledger or ledger['reserve']!=known['amount'] or json.loads(ledger['record'])['binding']['request_sha256']!=digest(known['request'].encode()):raise ValueError('Bildledger-Drift')
                    receipt=json.loads(known['receipt']) if known['receipt'] else None
                    if not receipt or not receipt.get('id'):raise ValueError('Bildreceipt unbekannt; nicht wiederholen')
                    self.s.save(r,phase='polling',prediction_id=receipt['id'],image_started=time.time());return
            required={c for row in w['cells'] for c in row}|{'wall'};mp=r['material_plan']
            if set(mp['materials'])!=required:raise ValueError('Materialplan muss exakt alle Geometriesemantiken plus wall abdecken')
            p=MaterialImage();schema=p.discover()
            from hybrid_material_repair import image_request
            guide=(d/r['guide_file']).read_bytes()
            if digest(guide)!=r['guide_sha256']:raise ValueError('Guide drift')
            previous=(d/r['previous_source']).read_bytes() if attempt and r.get('previous_source') else None
            if r.get('correction_kind')=='scene_concept':
                previous=(d/f'concept-{attempt}.png').read_bytes() if (d/f'concept-{attempt}.png').exists() else None
            prompt,images=image_request(mp,reference,guide,previous,r.get('correction'))
            inputs=[dict(id=k,sha256=digest(v)) for k,v in images.items()]
            prepared=r.get('prepared_image')
            if not prepared or prepared['attempt']!=attempt:
                if r['call_count']+4>cfg['max_calls']:raise ValueError('Aufruflimit: Bild plus Extraktion und beide Reviews reserviert')
                urls=[p.upload(raw,name+'.png') for name,raw in images.items()]
                body=p.inputs(prompt,urls)
                import jsonschema
                jsonschema.validate(body,schema)
                q=p.quote(body)
                if q.get('currency')!='USD':raise ValueError('Kein USD-Preis')
                amount=int((Decimal(str(q['price']))*1_000_000).to_integral_value(rounding=ROUND_CEILING))
                prepared={'attempt':attempt,'body':body,'schema':schema,'quote':q,'amount':amount,'inputs':inputs}
                immutable(d/f'image-request-{attempt}.json',canonical(prepared))
                self.s.save(r,prepared_image=prepared)
            if prepared.get('inputs')!=inputs or prepared['body']['prompt']!=prompt:raise ValueError('Image input/prompt drift')
            if schema!=prepared['schema']:raise ValueError('Bildmodell-Schema verändert')
            exact=p.quote(prepared['body'])
            if exact.get('currency')!='USD' or Decimal(str(exact['price']))*1_000_000>prepared['amount']:raise ValueError('Bildpreis gestiegen')
            headroom=planner.cost(metas['planner'],planner.policy(cfg,'extraction',metas['planner'])['max_tokens'])+2*reviewer.cost(metas['reviewer'],reviewer.policy(cfg,'review_sample',metas['reviewer'])['max_tokens'])
            intent=self.s.reserve_call(r,'image-'+str(attempt),prepared,prepared['amount'],auth,headroom)
            if intent['new']:
                receipt=p.submit(prepared['body']);self.s.receipt(intent['id'],receipt)
            else:receipt=intent['receipt']
            if not receipt or not receipt.get('id'):raise ValueError('Bildreceipt unbekannt; nicht wiederholen')
            self.s.save(r,phase='polling',prediction_id=receipt['id'],image_started=time.time());return
        if r['phase']=='polling':
            p=MaterialImage();result=p.poll(r['prediction_id'])
            if result.get('id')!=r['prediction_id']:raise ValueError('Prediction-Drift')
            if result.get('status') in ['failed','cancelled','deleted','timeout']:raise ValueError('Provider hat Bild nicht geliefert')
            if result.get('status')!='completed':
                if time.time()-r['image_started']>600:raise ValueError('Pollingzeitlimit; Receipt bleibt erhalten')
                return
            if len(result.get('outputs',[]))!=1:raise ValueError('Bildanzahl falsch')
            source=p.download(result['outputs'][0]);im=Image.open(io.BytesIO(source))
            if im.format!='PNG' or im.width*im.height>8_000_000:raise ValueError('Bildformat/Pixelgrenze falsch')
            im.verify();immutable(d/f'source-{attempt}.png',source)
            if r.get('previous_source') and digest((d/r['previous_source']).read_bytes())==digest(source):raise ValueError('Korrekturquelle identisch; keine weiteren Käufe')
            if r.get('painted_image'):
                from hybrid_painted_terrain import bind_source,validate_painted_source
                binding=bind_source(w,source)
                try:
                    alignment=validate_painted_source(w,binding,source)
                except ValueError as exc:
                    feedback=_paint_alignment_feedback(str(exc),r.get('paint_repairs',0))
                    if not feedback:raise
                    immutable(d/f'paint-alignment-repair-{attempt+1}.json',canonical({'error':str(exc),'feedback':feedback}))
                    self.s.save(r,phase='generating',attempt=attempt+1,paint_repairs=int(r.get('paint_repairs',0))+1,
                        paint_correction=feedback,painted_request=None,prediction_id=None,painted_image=True,stop_reason=None)
                    return
                immutable(d/f'painted-binding-{attempt}.json',canonical({'binding':binding,'alignment':alignment}))
                self.s.save(r,phase='sampling',source_sha256=digest(source),crop_binding=binding,painted_alignment=alignment,painted_image=False);return
            self.s.save(r,phase='extracting',source_sha256=digest(source));return
        source=(d/f'source-{attempt}.png').read_bytes()
        if digest(source)!=r['source_sha256']:raise ValueError('Quellbild verändert')
        required={c for row in w['cells'] for c in row}|{'wall'}
        if r['phase']=='extracting':
            size=list(Image.open(io.BytesIO(source)).size)
            from hybrid_material_repair import extraction_prompt
            prompt=extraction_prompt(r['material_plan'],digest(source),size,required)
            raw=planner.call(self.s,r,'extraction-'+str(attempt),prompt,{'board':source,'reference':reference,'actor':actor},CropMap.model_json_schema(),auth,metas['planner'])
            immutable(d/f'crop-decision-{attempt}.json',canonical(raw))
            try:binding=validate_crops(raw,digest(source),size,required)
            except ValueError:
                if cfg.get('no_new_images'):raise ValueError('Fresh extraction rejected retained source; no further images authorized; see crop decision')
                from hybrid_material_repair import queue_material_defect
                queue_material_defect(self,self.s.get(r['id']),raw,source,required);return
            self.s.save(r,phase='sampling',crop_binding=binding);return
        if r['phase']=='sampling':
            sw=sample_world(w);sd=d/('sample-'+str(attempt)+'-'+str(r.get('local_count',0)))
            build(sd,sw,source,r['crop_binding'],{'mode':'material_sample','production_approved':False,'target_revision':w['revision']})
            immutable(sd/'guide.png',png(render(sw,PreviewMaterials())[0]))
            self.s.save(r,phase='review_sample',sample_directory=sd.name,sample_binding=artifact_binding(sd),sample_guide_sha256=digest((sd/'guide.png').read_bytes()));return
        if r['phase']=='assembling':
            build(out,w,source,r['crop_binding'],{'mode':'live','production_approved':False,'run_id':r['id'],'calls':self.s.calls(r['id'])})
            self.s.save(r,phase='review_final',artifact_binding=artifact_binding(out),latest=out.name);return
        if r['phase'] in ['review_sample','review_final']:
            review_out=d/r['sample_directory'] if r['phase']=='review_sample' else out
            verify_artifact(review_out,r['sample_binding'] if r['phase']=='review_sample' else r['artifact_binding'])
            guide=review_out/'guide.png' if r['phase']=='review_sample' else d/r['guide_file']
            if r['phase']=='review_sample' and digest(guide.read_bytes())!=r['sample_guide_sha256']:raise ValueError('Sampleguide-Drift')
            if digest((d/r['guide_file']).read_bytes())!=r['guide_sha256']:raise ValueError('Guide-Drift')
            images={'final':(review_out/'scene.png').read_bytes(),'guide':guide.read_bytes(),'reference':reference}
            for name in required:images['crop-'+name]=(review_out/(name+'-crop.png')).read_bytes()
            # Sample geography is independent; final review uses the frozen target, both native.
            prompt=('Independent visual review, stage '+r['phase']+'. All seven criteria '+str(CRITERIA)+'. Each verdict pass/fail/uncertain with concrete observation and correction. Every criterion cite final; layout_fidelity/walkable_clearance must also cite guide; all other criteria must also cite reference. Crop citations supplement, never replace final. Guide preview colors are technical placeholders, never material identity: judge layout_fidelity by zone positions, heights and material-slot semantics, not by preview color. The renderer builds all elevations and stair tread/riser geometry from the world; judge the stairs material as a flat stone texture where absence of tread/riser shapes is required and never a materials failure. Assess actual scale, repetition, joints, lighting, reference similarity and actor visibility. No automatic approval from deterministic geometry. Do not accept tall foliage/objects in walkable ground. Reference is style-only. '+json.dumps(r['material_plan']))
            prompt+=' For scale/repetition-only FAIL, propose local_sampling bound to source_sha256 and binding_sha256, materials mapping to integer source_pixels_per_unit (1..512, max factor2 change) and offset within existing crop. Never move/replace crops or geometry. Otherwise local_sampling=null. Current binding: '+json.dumps(r['crop_binding'])+' binding_sha256='+digest(canonical(r['crop_binding']))
            role=r['phase']+'-'+str(attempt)+('-local-'+str(r['local_count']) if r.get('local_count') else '')
            raw=reviewer.call(self.s,r,role,prompt,images,Review.model_json_schema(),auth,metas['reviewer'])
            immutable(d/(role+'.json'),canonical(raw));gate=review_gate(raw,images)
            self.s.save(r,gate=gate)
            if not gate['approved']:
                if cfg.get('no_local_retries'):raise ValueError('Fresh review rejected retained-source assembly; no extra review or image authorized: '+', '.join(gate['reasons']))
                signature=digest(canonical(raw))
                if any('Belege' in x or 'JSON' in x or 'fehlen' in x for x in gate['reasons']):raise ValueError('Ungültige Reviewbelege; keine erfundene Reparatur')
                if any(c.get('verdict')=='uncertain' for c in raw.get('criteria',{}).values()):raise ValueError('Review unsicher; Aufmerksamkeit erforderlich')
                if signature in r.get('correction_signatures',[]):raise ValueError('Keine Änderung/Stagnation; kein identischer Reroll')
                failed={k for k,c in raw['criteria'].items() if c['verdict']=='fail'}
                if failed<= {'scale','repetition'}:
                    if not raw.get('local_sampling'):raise ValueError('Lokaler Befund ohne sichere Samplingkorrektur; kein Bild-Reroll')
                    if r.get('local_count',0)>=cfg.get('max_local_corrections',2):raise ValueError('Lokales Korrekturlimit erreicht')
                    binding=correct_sampling(r['crop_binding'],raw['local_sampling'])
                    hashes=r.get('sampling_history',[digest(canonical(r['crop_binding']))])
                    sha=digest(canonical(binding))
                    if sha in hashes:raise ValueError('Sampling-Zyklus; kein Retry')
                    self.s.save(r,phase='sampling',local_count=r.get('local_count',0)+1,crop_binding=binding,sampling_history=hashes+[sha],correction_kind='local_sampling',correction_signatures=r.get('correction_signatures',[])+[signature]);return
                if failed & {'layout_fidelity','walkable_clearance'}:raise ValueError('Geometrie-/Clearancebefund nicht sicher lokal reparierbar')
                if attempt+1>=cfg['max_images']:raise ValueError('Bildlimit erreicht; beste Evidenz bleibt diagnostisch')
                if cfg.get('terrain_flow')=='painted_flat':
                    self.s.save(r,phase='generating',attempt=attempt+1,paint_repairs=int(r.get('paint_repairs',0)),
                        paint_correction=_review_repaint_feedback(raw),painted_request=None,prediction_id=None,painted_image=True,
                        correction_signatures=r.get('correction_signatures',[])+[signature],stop_reason=None);return
                self.s.save(r,phase='generating',attempt=attempt+1,correction=raw,correction_signatures=r.get('correction_signatures',[])+[signature],previous_source=f'source-{attempt}.png',prepared_image=None,correction_kind='generated_material');return
            if r['phase']=='review_sample':self.s.save(r,phase='assembling',sample_review_role=role);return
            self.s.save(r,phase='verifying',best=out.name,final_review_role=role);return
        if r['phase']=='verifying':
            verify_artifact(out,r['artifact_binding'])
            # Real headless offline navigation; failure cannot become production approval.
            result=subprocess.run(['node',str(ROOT/'tools/hybrid_artifact_probe.mjs'),str(out)],capture_output=True,timeout=120)
            if result.returncode:raise ValueError('Browser-/Exportverifikation fehlgeschlagen')
            with tempfile.TemporaryDirectory(prefix='hybrid-verify-') as temp:
                td=Path(temp)
                with zipfile.ZipFile(out/'diagnostic.zip') as z:z.extractall(td/'extracted')
                rebuild=subprocess.run(['python3',str(td/'extracted/source/rebuild.py'),str(td/'rebuilt')],capture_output=True,timeout=180)
                if rebuild.returncode or (td/'rebuilt/diagnostic.zip').read_bytes()!=(out/'diagnostic.zip').read_bytes():raise ValueError('Export-Rebuild nicht exakt')
            proof={'rebuild_exact':True,'production_rebuild_exact':True,'browser':json.loads((out/'browser-proof.json').read_bytes())}
            from hybrid_export import production_bundle
            proposed={**self.s.get(r['id']),'phase':'succeeded','production_approved':True,'verification':proof}
            bundle=production_bundle(self.s,proposed)
            with tempfile.TemporaryDirectory(prefix='hybrid-production-verify-') as temp:
                td=Path(temp)
                with zipfile.ZipFile(io.BytesIO(bundle)) as z:z.extractall(td/'extracted')
                result=subprocess.run(['python3',str(td/'extracted/source/rebuild.py'),str(td/'rebuilt')],capture_output=True,timeout=180)
                if result.returncode or (td/'rebuilt/production.zip').read_bytes()!=bundle:raise ValueError('Produktions-Rebuild nicht exakt')
            self.s.save(r,phase='succeeded',production_approved=True,verification=proof,stop_reason='Modellgate und lokale Prüfungen bestanden; Nutzerfreigabe offen')
            return
        raise ValueError('Unbekannte Phase')

def default_store():
    root=Path(os.environ.get('HYBRID_DATA',str(ROOT/'data')));policy=json.loads((root/'generation-policy.json').read_bytes()) if (root/'generation-policy.json').exists() else {'approved':False,'total_usd':'0','max_attempts':0}
    return Store(Generation(root,MaterialImage(),policy))
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--once',action='store_true');args=parser.parse_args();w=Worker(default_store())
    while True:
        w.tick()
        if args.once:return
        time.sleep(2)
if __name__=='__main__':main()
