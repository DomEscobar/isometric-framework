"""One bounded local-sampling repair continuation after a capped scale-only stop.

Reuses the reviewer's own hash-bound sampling plan; no image, no crop changes,
exactly the two mandatory re-reviews after a deterministic re-sampling.
"""
import io,json
from PIL import Image
from artifacts import canonical,digest
from hybrid_sampling import correct_sampling
from hybrid_models import review_gate,validate_crops

SCALE_ONLY={'scale','repetition'}

def sampling_repair(decision,binding,source_sha256,evidence):
    plan=decision.get('local_sampling')
    if not plan:raise ValueError('Kein lokaler Samplingplan; kein Reparaturstart')
    failed={k for k,c in decision['criteria'].items() if c['verdict']=='fail'}
    if not failed or not failed<=SCALE_ONLY:raise ValueError('Nur scale/repetition ist lokal reparierbar')
    if any(c.get('verdict')=='uncertain' for c in decision['criteria'].values()):raise ValueError('Review unsicher; keine Reparatur')
    if review_gate(decision,evidence)['approved']:raise ValueError('Gate bereits bestanden')
    return correct_sampling(binding,plan)

def validated_sampling_repair(store,binding=None,parent_id=None,db=None):
    if db is None:
        with store.g.connect() as conn:return validated_sampling_repair(store,binding,parent_id,conn)
    pid=binding['parent_id'] if binding else parent_id
    row=db.execute('SELECT * FROM hybrid_runs WHERE id=?',(pid,)).fetchone()
    if not row or row['phase']!='needs_attention' or row['lease'] or row['cancel']:raise ValueError('Sampling parent must be sealed')
    cfg=json.loads(row['config']);r=json.loads(row['record']);d=store.g.root/'hybrid'/pid
    attempt=r.get('attempt',0)
    if r.get('local_count')!=0:raise ValueError('Samplingkorrektur bereits verwendet')
    calls={c['role']:dict(c) for c in db.execute('SELECT * FROM hybrid_calls WHERE run=?',(pid,))}
    roles=[f'image-{attempt}',f'extraction-{attempt}',f'review_sample-{attempt}',f'review_final-{attempt}']
    expected=set(roles)
    if not cfg.get('continuation'):
        expected.add('planner')
        if cfg.get('layout_review_iterations'):expected.add('layout_review-1')
    if set(calls)!=expected:raise ValueError('Expected layout approval plus image, extraction and both reviews')
    proofs=[]
    if 'layout_review-1' in expected:
        review_call=calls['layout_review-1'];receipt=json.loads(review_call['receipt'] or 'null')
        review_path=d/'layout-review-1.json'
        if not receipt or not review_path.exists():raise ValueError('Independent layout review receipt/artifact missing')
        layout_review=json.loads(review_path.read_bytes())
        layout=json.loads((d/'planner-result-1.json').read_bytes())['layout']
        preview=(d/'layout-preview-1.png').read_bytes()
        if layout_review.get('approved') is not True or layout_review.get('layout_sha256')!=digest(canonical(layout)) or layout_review.get('preview_sha256')!=digest(preview):
            raise ValueError('Independent layout review binding/approval mismatch')
        ledger=db.execute('SELECT * FROM reviews WHERE id=?',(review_call['id'],)).fetchone()
        if not ledger or not receipt.get('id') or ledger['reserve']!=review_call['amount'] or json.loads(ledger['record'])['binding']['request_sha256']!=digest(review_call['request'].encode()):
            raise ValueError('Independent layout review ledger drift')
        proofs.append(dict(call_id=review_call['id'],call_sha256=digest(canonical(review_call)),ledger_sha256=digest(canonical(dict(ledger))),layout_sha256=layout_review['layout_sha256'],preview_sha256=layout_review['preview_sha256']))
    for role in roles:
        call=calls[role];req=json.loads(call['request']);receipt=json.loads(call['receipt'] or 'null')
        ledger=db.execute('SELECT * FROM reviews WHERE id=?',(call['id'],)).fetchone()
        if not receipt or not ledger or call['id']!=digest(canonical([pid,role,req])) or ledger['reserve']!=call['amount'] or json.loads(ledger['record'])['binding']['request_sha256']!=digest(call['request'].encode()):raise ValueError('Call/ledger drift')
        proofs.append(dict(call_id=call['id'],call_sha256=digest(canonical(call)),ledger_sha256=digest(canonical(dict(ledger)))))
    source=(d/f'source-{attempt}.png').read_bytes()
    if digest(source)!=r['source_sha256']:raise ValueError('Source drift')
    def content(role):return json.loads(calls[role]['receipt'])['choices'][0]['message']['content']
    decision=json.loads(content(roles[1]))
    if (d/f'crop-decision-{attempt}.json').read_bytes()!=canonical(decision):raise ValueError('Extraction artifact drift')
    crops=validate_crops(decision,digest(source),list(Image.open(io.BytesIO(source)).size),set(r['material_plan']['materials']))
    if r.get('crop_binding')!=crops:raise ValueError('Crop binding drift')
    from hybrid_artifact import verify_artifact
    materials=set(r['material_plan']['materials'])
    evidence={'final','guide','reference'}|{'crop-'+m for m in materials}
    verify_artifact(d/r['sample_directory'],r['sample_binding'])
    if r.get('sample_review_role')!=roles[2]:raise ValueError('Sample review role drift')
    sample_raw=json.loads(content(roles[2]))
    if (d/(roles[2]+'.json')).read_bytes()!=canonical(sample_raw):raise ValueError('Sample review artifact drift')
    if not review_gate(sample_raw,evidence)['approved']:raise ValueError('Sample gate freigegeben erwartet')
    verify_artifact(d/r['latest'],r['artifact_binding'])
    final_raw=json.loads(content(roles[3]))
    if (d/(roles[3]+'.json')).read_bytes()!=canonical(final_raw):raise ValueError('Final review artifact drift')
    if not r.get('gate') or r['gate'].get('approved') is not False or r['gate'].get('decision')!=final_raw:raise ValueError('Final gate drift')
    corrected=sampling_repair(final_raw,crops,digest(source),evidence)
    files={f'source-{attempt}.png':digest(source),r['guide_file']:digest((d/r['guide_file']).read_bytes()),
        f'crop-decision-{attempt}.json':digest(canonical(decision)),roles[2]+'.json':digest(canonical(sample_raw)),roles[3]+'.json':digest(canonical(final_raw))}
    p=dict(kind='sampling_repair',parent_id=pid,parent_sha256=digest(canonical(dict(row))),calls=proofs,files=files,
        corrected_binding=corrected,old_binding_sha256=digest(canonical(crops)),binding_sha256=digest(canonical(corrected)),
        decision_sha256=digest(canonical(final_raw)),attempt=attempt,
        inherited_calls=r['call_count'],inherited_images=r['image_count'],inherited_local=r['local_count'])
    if binding and binding!=p:raise ValueError('Sampling repair continuation drift')
    return p,None,cfg

def continue_sampling_repair(store,pid,idem,budget,seconds,approval):
    from decimal import Decimal
    from hybrid_worker import runtime_version
    p,_,cfg=validated_sampling_repair(store,parent_id=pid)
    cap=int(Decimal(str(store.g.policy['total_usd']))*1_000_000)
    if not isinstance(approval,str) or len(approval.strip())<10:raise ValueError('Explicit bounded sampling-repair authority required')
    if type(budget)!=int or not 0<budget<=cap or type(seconds)!=int or not 60<=seconds<=7200:raise ValueError('Sampling-repair limits invalid')
    if cfg.get('no_local_retries'):raise ValueError('Sampling repair requires the bounded local loop')
    amendment=dict(kind='bounded-sampling-repair/1',approval_text=approval,parent_id=pid,
        previous_max_calls=cfg['max_calls'],previous_max_local_corrections=cfg.get('max_local_corrections',0),
        max_calls=p['inherited_calls']+2,max_images=cfg['max_images'],max_local_corrections=1,new_images=0,
        followup_calls=2,project_cap_microusd=cap,source='reviewer local_sampling plan, factor<=2, crops unchanged')
    child={**cfg,'continuation':p,'authorization_amendment':amendment,'runtime_version':runtime_version(),
        'budget_microusd':budget,'max_seconds':seconds,'max_calls':p['inherited_calls']+2,'max_images':cfg['max_images'],
        'max_local_corrections':1,'followup_call_limit':2,'no_new_images':True}
    return store.create(idem,child)

def inherit_sampling_repair(worker,r):
    from hybrid_worker import immutable
    p,_,_=validated_sampling_repair(worker.s,r['config']['continuation'])
    parent=worker.s.get(p['parent_id']);src=worker.root/p['parent_id'];dest=worker.root/r['id']
    for name,sha in p['files'].items():
        raw=(src/name).read_bytes()
        if digest(raw)!=sha:raise ValueError('Sampling-repair inheritance drift')
        immutable(dest/name,raw)
    immutable(dest/'sampling-repair.json',canonical(p))
    fields=['layout','world','material_plan','interpretation','guide_file','guide_sha256','accepted_layout','source_sha256','attempt']
    changes={k:parent[k] for k in fields}
    changes.update(crop_binding=p['corrected_binding'],local_count=1,
        sampling_history=[p['old_binding_sha256'],p['binding_sha256']],correction_signatures=[p['decision_sha256']],
        correction_kind='local_sampling_repair',prepared_image=None,
        frozen_sha256=digest(canonical(dict(config=r['config'],layout=parent['accepted_layout']))),stop_reason=None)
    worker.s.save(r,phase='sampling',**changes)
