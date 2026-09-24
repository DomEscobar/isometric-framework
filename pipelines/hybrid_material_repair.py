"""Concrete, cited source defects only; never convert uncertain crops to PASS."""
import json,io
from PIL import Image
from artifacts import canonical,digest
from hybrid_models import CropMap,validate_crops

def validated_material(store,binding=None,parent_id=None,db=None):
    from hybrid_recovery import validated_parent
    from hybrid_layout import compile_layout
    if db is None:
        with store.g.connect() as conn:return validated_material(store,binding,parent_id,conn)
    pid=binding['parent_id'] if binding else parent_id
    row=db.execute('SELECT * FROM hybrid_runs WHERE id=?',(pid,)).fetchone()
    if not row or row['phase']!='needs_attention' or row['lease'] or row['cancel']:raise ValueError('Material parent must be sealed')
    cfg=json.loads(row['config']);r=json.loads(row['record']);d=store.g.root/'hybrid'/pid
    if cfg.get('continuation',{}).get('kind')!='source':raise ValueError('Expected retained-source lineage')
    inherited,plan,_=validated_parent(store,cfg['continuation'],db=db)
    attempt=r['attempt'];source=(d/f'source-{attempt}.png').read_bytes();sha=digest(source)
    if sha!=inherited['source_sha256'] or sha!=r['source_sha256']:raise ValueError('Source drift')
    calls=db.execute('SELECT * FROM hybrid_calls WHERE run=?',(pid,)).fetchall()
    if len(calls)!=1 or calls[0]['role']!=f'extraction-{attempt}':raise ValueError('Expected sole complete extraction')
    call=calls[0];req=json.loads(call['request']);receipt=json.loads(call['receipt'] or 'null')
    ledger=db.execute('SELECT * FROM reviews WHERE id=?',(call['id'],)).fetchone()
    if not receipt or call['id']!=digest(canonical([pid,call['role'],req])) or not ledger or ledger['reserve']!=call['amount'] or json.loads(ledger['record'])['binding']['request_sha256']!=digest(call['request'].encode()):raise ValueError('Extraction ledger drift')
    if req['body']['model']!=cfg['planner_model'] or receipt.get('model')!=cfg['planner_model'] or receipt['choices'][0]['finish_reason']!='stop':raise ValueError('Incomplete extraction')
    if [x for x in req['inputs'] if x['id']=='board']!=[dict(id='board',sha256=sha)]:raise ValueError('Extraction source mismatch')
    raw=json.loads(receipt['choices'][0]['message']['content']);decision=(d/f'crop-decision-{attempt}.json').read_bytes()
    if decision!=canonical(raw):raise ValueError('Crop decision drift')
    world=compile_layout(plan['layout'])
    if r['accepted_layout']!=plan['layout'] or r['world']!=world or r['frozen_sha256']!=digest(canonical(dict(config=cfg,layout=plan['layout']))):raise ValueError('Layout drift')
    parent_record=json.loads(db.execute('SELECT record FROM hybrid_runs WHERE id=?',(inherited['parent_id'],)).fetchone()[0])
    if r['material_plan']!=parent_record['material_plan']:raise ValueError('Material intent drift')
    correction=material_defect(raw,sha,list(Image.open(io.BytesIO(source)).size),set(r['material_plan']['materials']))
    files={n:digest((d/n).read_bytes()) for n in [*inherited['files'],f'crop-decision-{attempt}.json']}
    if any(files[n]!=h for n,h in inherited['files'].items()):raise ValueError('Inherited file drift')
    if r['call_count']!=inherited['inherited_calls']+1 or r['image_count']!=inherited['inherited_images']:raise ValueError('Lifetime drift')
    p=dict(kind='material_repair',parent_id=pid,parent_sha256=digest(canonical(dict(row))),call_sha256=digest(canonical(dict(call))),ledger_sha256=digest(canonical(dict(ledger))),files=files,correction=correction,inherited_calls=r['call_count'],inherited_images=r['image_count'],inherited_local=r['local_count'])
    if binding and binding!=p:raise ValueError('Material continuation drift')
    return p,plan,cfg

def continue_material(store,pid,idem,budget,seconds,approval):
    from decimal import Decimal
    from hybrid_worker import runtime_version
    from hybrid_source_recovery import TOKEN_POLICY
    p,plan,cfg=validated_material(store,parent_id=pid)
    cap=int(Decimal(str(store.g.policy['total_usd']))*1_000_000)
    if not isinstance(approval,str) or len(approval.strip())<10 or type(budget)!=int or not 0<budget<=cap or type(seconds)!=int or not 60<=seconds<=7200:raise ValueError('Bounded explicit repair authority required')
    amendment=dict(kind='bounded-material-repair/1',reason='pipeline livefix',approval_text=approval,parent_id=pid,previous_max_calls=cfg['max_calls'],previous_max_images=cfg['max_images'],previous_max_local_corrections=cfg['max_local_corrections'],max_calls=12,max_images=3,max_local_corrections=2,project_cap_microusd=cap,previous_budget_microusd=cfg['budget_microusd'],budget_microusd=budget)
    return store.create(idem,{**cfg,'continuation':p,'authorization_amendment':amendment,'runtime_version':runtime_version(),'max_calls':12,'max_images':3,'max_local_corrections':2,'budget_microusd':budget,'max_seconds':seconds,'token_policy':TOKEN_POLICY})

def inherit_material(worker,r):
    from hybrid_worker import immutable
    p,_,_=validated_material(worker.s,r['config']['continuation'])
    parent=worker.s.get(p['parent_id']);src=worker.root/p['parent_id'];dest=worker.root/r['id']
    for name,sha in p['files'].items():
        raw=(src/name).read_bytes()
        if digest(raw)!=sha:raise ValueError('Material inheritance drift')
        immutable(dest/name,raw)
    changes={k:parent[k] for k in ['layout','world','material_plan','interpretation','guide_file','guide_sha256','accepted_layout','source_sha256']}
    changes['frozen_sha256']=digest(canonical(dict(config=r['config'],layout=parent['accepted_layout'])))
    immutable(dest/'source-correction-1.json',canonical(p['correction']))
    worker.s.save(r,phase='generating',attempt=parent['attempt']+1,previous_source=f"source-{parent['attempt']}.png",correction=p['correction'],correction_kind='material_source_defect',stop_reason=None,**changes)

def image_request(material_plan,reference,guide,source=None,correction=None):
    images={'reference':reference,'guide':guide}
    if source is not None:images['correction_target']=source
    prompt=('Image1 is STYLE ONLY: palette, stone and grass treatment. Image2 is frozen GEOMETRY GUIDE only: do NOT draw its scene or stairs. '
        'Create a material swatch board, NOT a scene or architectural illustration. Named semantic slots: '+', '.join(sorted(material_plan['materials']))+'. '
        'Each slot is a separated large flat unlit rectangular material interior with generous gaps; no text. '
        'For stairs use FLAT FACE-ON STONE TEXTURE, NO perspective staircase, NO risers, NO tread arrangement, NO beveled slab object or highlights suggesting steps. '
        'A single broad rectangular stone surface interior, subtle stone grain only; the renderer builds all elevation and stair geometry. '
        'For wall provide flat face-on masonry; all other slots flat orthographic ground material. Actor visible64px, target tile48x24. '
        'Frozen planner style/material intent (material identity only, never architecture): '+json.dumps(material_plan)+'. ')
    if source is not None:
        prompt+=('Image3 is the current material BOARD CORRECTION TARGET, never style authority. '
            'Change ONLY explicitly failed material slots from the cited findings below. Preserve the passing materials, palette, scale, treatment and slot placement. '
            'Exact preservation is not guaranteed by this edit API: all materials will be automatically re-extracted and reviewed. '
            'Evidence-based correction: '+json.dumps(correction or {})+'. ')
    return prompt,images

def queue_material_defect(worker,r,raw,source,required):
    from hybrid_worker import immutable
    correction=material_defect(raw,digest(source),list(Image.open(io.BytesIO(source)).size),required)
    cfg=r['config'];attempt=r['attempt'];signature=digest(canonical(correction))
    if r['image_count']>=cfg['max_images'] or attempt+1>=cfg['max_images']:raise ValueError('Bildlimit erreicht; Materialdefekt bleibt erhalten')
    if r['call_count']+4>cfg['max_calls']:raise ValueError('Aufruflimit: Bild, Extraktion und beide Reviews müssen passen')
    if signature in r.get('correction_signatures',[]):raise ValueError('Stagnation: identische Materialdefekte')
    immutable(worker.root/r['id']/f'source-correction-{attempt+1}.json',canonical(correction))
    worker.s.save(r,phase='generating',attempt=attempt+1,previous_source=f'source-{attempt}.png',prepared_image=None,correction=correction,correction_kind='material_source_defect',correction_signatures=r.get('correction_signatures',[])+[signature])

def extraction_prompt(material_plan,sha,size,required):
    return ('Locate and evaluate actual clean flat orthographic interior crops for each material. Do not assume board positions from prompt. '
        'SOURCE CONTRACT: planner architecture describes the FINAL SCENE, not the material board. The deterministic renderer builds all steps, risers, elevations and lighting. '
        'For stairs assess a flat face-on unlit stone surface interior ONLY. Absence of treads and risers is REQUIRED and never a reason to FAIL. '
        'Visible architectural steps, perspective, tread arrangements, risers or cast shadows are source defects even if they resemble the final scene. '
        'For wall require flat face-on masonry material, not staircase architecture. Reject objects/text/perspective; uncertainty must remain uncertain. '
        'Exactly these semantic keys: '+json.dumps(sorted(required))+'. Source SHA '+sha+'. Pixel size '+str(size)+'. '
        'Return source_sha256 and crops with xywh, integer source_pixels_per_unit (1..512), verdict, evidence_ids=[board], observation. '
        'Match reference material identity and scale; interpret the unchanged planner below under the SOURCE CONTRACT above: '+json.dumps(material_plan))

def material_defect(raw,sha,size,required):
    value=CropMap.model_validate(raw).model_dump()
    # Validate the entire evidence contract without treating FAIL as a crop approval.
    probe=json.loads(canonical(value))
    for crop in probe['crops'].values():
        if crop['verdict']=='uncertain':raise ValueError('Uncertain crop; no automatic source correction')
        crop['verdict']='pass'
    validate_crops(probe,sha,size,required)
    failed={k:v for k,v in value['crops'].items() if v['verdict']=='fail'}
    # Conservative veto only: this never grants PASS or supplies a crop.
    import re
    for crop in failed.values():
        if re.search(r'\b(without|lacking|lacks|missing|no)\b[^.]{0,120}\b(risers?|treads?|staircase)\b',crop['observation'],re.I):
            raise ValueError('Material contract conflict: missing architecture is not a source defect; no image purchase')
    if not failed:raise ValueError('No concrete material source defect')
    return dict(kind='material_source_defect/1',source_sha256=sha,decision_sha256=digest(canonical(raw)),failed_materials=failed,preserve_materials={k:v for k,v in value['crops'].items() if v['verdict']=='pass'})
