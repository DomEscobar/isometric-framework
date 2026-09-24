"""One bounded owner-directed image-to-image board upgrade on a proven run.

The directive is bound in the immutable child config; the proof stays fully derived.
Exactly one image edit + full re-extraction + both mandatory reviews. No crops picked.
"""
import io,json
from PIL import Image
from artifacts import canonical,digest
from hybrid_models import validate_crops

def validated_directive(store,binding=None,parent_id=None,db=None):
    if db is None:
        with store.g.connect() as conn:return validated_directive(store,binding,parent_id,conn)
    pid=binding['parent_id'] if binding else parent_id
    row=db.execute('SELECT * FROM hybrid_runs WHERE id=?',(pid,)).fetchone()
    if not row or row['phase'] not in ('needs_attention','succeeded') or row['lease'] or row['cancel']:raise ValueError('Directive parent must be terminal')
    cfg=json.loads(row['config']);r=json.loads(row['record']);d=store.g.root/'hybrid'/pid
    # A parent's no_new_images flag bounds ITS scope; a new bounded amendment with
    # explicit owner directive is the only path that may authorize exactly one image.
    attempt=r.get('attempt',0)
    calls={c['role']:dict(c) for c in db.execute('SELECT * FROM hybrid_calls WHERE run=?',(pid,))}
    proofs=[]
    for role in sorted(calls):
        call=calls[role];req=json.loads(call['request']);receipt=json.loads(call['receipt'] or 'null')
        ledger=db.execute('SELECT * FROM reviews WHERE id=?',(call['id'],)).fetchone()
        if not receipt or not ledger or call['id']!=digest(canonical([pid,role,req])) or ledger['reserve']!=call['amount'] or json.loads(ledger['record'])['binding']['request_sha256']!=digest(call['request'].encode()):raise ValueError('Call/ledger drift')
        proofs.append(dict(call_id=call['id'],call_sha256=digest(canonical(call)),ledger_sha256=digest(canonical(dict(ledger)))))
    source=(d/f'source-{attempt}.png').read_bytes()
    if digest(source)!=r['source_sha256']:raise ValueError('Source drift')
    decision=json.loads((d/f'crop-decision-{attempt}.json').read_bytes())
    if f'extraction-{attempt}' in calls and json.loads(json.loads(calls[f'extraction-{attempt}']['receipt'])['choices'][0]['message']['content'])!=decision:raise ValueError('Extraction receipt drift')
    crops=None;defects=None
    try:
        crops=validate_crops(decision,digest(source),list(Image.open(io.BytesIO(source)).size),set(r['material_plan']['materials']))
        if r.get('crop_binding')!=crops:
            # A binding may differ only via the documented bounded sampling corrections.
            history=r.get('sampling_history') or []
            if not history or history[0]!=digest(canonical(crops)) or digest(canonical(r['crop_binding'])) not in history:raise ValueError('Crop binding drift')
    except ValueError as error:
        if crops is not None and 'binding' not in str(error):raise
        if crops is not None:raise
        # Failed-extraction parent: only cited concrete non-conflict defects may guide
        # the next edit; uncertainty and architecture demands stay excluded upstream.
        from hybrid_material_repair import material_defect
        defects=material_defect(decision,digest(source),list(Image.open(io.BytesIO(source)).size),set(r['material_plan']['materials']))
    from hybrid_artifact import verify_artifact
    if r.get('artifact_binding'):verify_artifact(d/r['latest'],r['artifact_binding'])
    if crops is not None and not r.get('production_approved') and r.get('gate',{}).get('approved') is not True:raise ValueError('No proven base run')
    files={f'source-{attempt}.png':digest(source),r['guide_file']:digest((d/r['guide_file']).read_bytes()),
        f'crop-decision-{attempt}.json':digest(canonical(decision))}
    p=dict(kind='directive_repair',parent_id=pid,parent_sha256=digest(canonical(dict(row))),calls=proofs,files=files,
        attempt=attempt,source_sha256=digest(source),binding_sha256=digest(canonical(crops)) if crops is not None else None,
        defects=defects,
        inherited_calls=r['call_count'],inherited_images=r['image_count'],inherited_local=r['local_count'])
    if binding and binding!=p:raise ValueError('Directive continuation drift')
    return p,None,cfg

def continue_directive(store,pid,idem,budget,seconds,approval,directive,flow='board'):
    from decimal import Decimal
    from hybrid_worker import runtime_version
    p,_,cfg=validated_directive(store,parent_id=pid)
    cap=int(Decimal(str(store.g.policy['total_usd']))*1_000_000)
    if flow not in ('board','scene_concept'):raise ValueError('Unknown directive flow')
    if not isinstance(approval,str) or len(approval.strip())<10:raise ValueError('Explicit bounded directive authority required')
    if not isinstance(directive,str) or len(directive.strip())<10:raise ValueError('Explicit owner style directive required')
    if type(budget)!=int or not 0<budget<=cap or type(seconds)!=int or not 60<=seconds<=7200:raise ValueError('Directive limits invalid')
    extra_images=2 if flow=='scene_concept' else 1
    followups=extra_images+3
    amendment=dict(kind='bounded-directive-repair/1',approval_text=approval,owner_style_directive=directive,parent_id=pid,
        previous_max_calls=cfg['max_calls'],previous_max_images=cfg['max_images'],flow=flow,
        max_calls=p['inherited_calls']+followups,max_images=p['inherited_images']+extra_images,new_images=extra_images,followup_calls=followups,
        project_cap_microusd=cap,source='explicit owner directive: scene concept then flat board' if flow=='scene_concept' else 'explicit owner directive for richer material board')
    child={**cfg,'continuation':p,'authorization_amendment':amendment,'runtime_version':runtime_version(),
        'budget_microusd':budget,'max_seconds':seconds,'max_calls':p['inherited_calls']+followups,'max_images':p['inherited_images']+extra_images,
        'max_local_corrections':0,'followup_call_limit':followups,'no_local_retries':True}
    child.pop('no_new_images',None)
    return store.create(idem,child)

def inherit_directive(worker,r):
    from hybrid_worker import immutable
    p,_,_=validated_directive(worker.s,r['config']['continuation'])
    parent=worker.s.get(p['parent_id']);src=worker.root/p['parent_id'];dest=worker.root/r['id']
    for name,sha in p['files'].items():
        raw=(src/name).read_bytes()
        if digest(raw)!=sha:raise ValueError('Directive inheritance drift')
        immutable(dest/name,raw)
    correction=dict(kind='owner_style_directive/1',source_sha256=p['source_sha256'],binding_sha256=p['binding_sha256'],
        directive=r['config']['authorization_amendment']['owner_style_directive'],preserve_all_semantics=True,
        evidence_based_defects=p.get('defects'))
    immutable(dest/'directive-correction.json',canonical(correction))
    fields=['layout','world','material_plan','interpretation','guide_file','guide_sha256','accepted_layout']
    changes={k:parent[k] for k in fields if parent.get(k) is not None}
    if parent.get('crop_binding') is not None:changes['crop_binding']=parent['crop_binding']
    attempt=p['inherited_images']
    changes.update(attempt=attempt,previous_source=f"source-{p['attempt']}.png",source_sha256=p['source_sha256'],
        correction=correction,correction_kind='scene_concept' if r['config']['authorization_amendment'].get('flow')=='scene_concept' else 'owner_style_directive',
        frozen_sha256=digest(canonical(dict(config=r['config'],layout=parent['accepted_layout']))),stop_reason=None)
    worker.s.save(r,phase='generating',**changes)
