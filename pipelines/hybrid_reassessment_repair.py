"""One bounded image-to-image material repair after a failed reassessment review.

Findings demanding forbidden architecture in flat sources are excluded, geometry
findings are deferred to the renderer; only cited actionable material findings
guide the edit. The owner style directive is bound in the immutable child config.
"""
import base64,io,json,re
from PIL import Image
from artifacts import canonical,digest
from hybrid_models import Review,validate_crops,review_gate

ARCH_CONFLICT=re.compile(r'\b(without|lacking|lacks|missing|no)\b[^.]{0,120}\b(risers?|treads?|staircase)\b',re.I)
GEOMETRY={'layout_fidelity','walkable_clearance'}

def review_correction(decision,evidence,source_sha256):
    value=Review.model_validate(decision).model_dump()
    actionable={};excluded=[];deferred=[]
    for name,c in sorted(value['criteria'].items()):
        if c['verdict']!='fail':continue
        ids=set(c['evidence_ids'])
        if not ids<=set(evidence) or 'final' not in ids:raise ValueError('Ungültige Reviewbelege; keine Generierung')
        if name in GEOMETRY:deferred.append(dict(criterion=name,reason='geometry/renderer finding; never a source material edit'));continue
        if ARCH_CONFLICT.search(c['observation']):excluded.append(dict(criterion=name,reason='architecture-role conflict: demands forbidden geometry in flat source material'));continue
        targets=sorted(i[5:] for i in ids if i.startswith('crop-'))
        if not targets:raise ValueError('Materialbefund ohne Materialbeleg')
        for t in targets:actionable.setdefault(t,dict(criterion=name,observation=c['observation'],correction=c['correction']))
    if not actionable:raise ValueError('Kein handlungsrelevanter Materialbefund; kein Bildkauf')
    materials=sorted(i[5:] for i in evidence if i.startswith('crop-'))
    return dict(kind='review_material_correction/1',source_sha256=source_sha256,failed_materials=actionable,
        preserve_materials=[m for m in materials if m not in actionable],excluded=excluded,deferred=deferred)

def validated_repair(store,binding=None,parent_id=None,db=None):
    from hybrid_reassessment import validated_archive
    if db is None:
        with store.g.connect() as conn:return validated_repair(store,binding,parent_id,conn)
    pid=binding['parent_id'] if binding else parent_id
    row=db.execute('SELECT * FROM hybrid_runs WHERE id=?',(pid,)).fetchone()
    if not row or row['phase']!='needs_attention' or row['lease'] or row['cancel']:raise ValueError('Repair parent must be sealed')
    cfg=json.loads(row['config']);r=json.loads(row['record']);d=store.g.root/'hybrid'/pid
    if cfg.get('continuation',{}).get('kind')!='source_reassessment' or cfg['mode']!='live':raise ValueError('Expected reassessment parent')
    inherited,plan,_=validated_archive(store,cfg['continuation'],db=db)
    if (d/'source-reassessment.json').read_bytes()!=canonical(inherited):raise ValueError('Reassessment proof artifact drift')
    attempt=r['attempt'];sha=r['source_sha256']
    if r.get('reassessment')!=inherited['selected']['invalidation'] or sha!=inherited['selected']['source_sha256'] or attempt!=inherited['selected']['attempt']:raise ValueError('Reassessment record drift')
    if r['frozen_sha256']!=digest(canonical(dict(config=cfg,layout=r['accepted_layout']))):raise ValueError('Frozen input drift')
    files={}
    for name,fsha in inherited['files'].items():
        name='historical-'+name if name.startswith('crop-decision-') else name
        if digest((d/name).read_bytes())!=fsha:raise ValueError('Inherited archive drift')
        files[name]=fsha
    files['source-reassessment.json']=digest(canonical(inherited))
    source=(d/f'source-{attempt}.png').read_bytes()
    if digest(source)!=sha:raise ValueError('Source drift')
    calls={c['role']:dict(c) for c in db.execute('SELECT * FROM hybrid_calls WHERE run=?',(pid,))}
    roles=[f'extraction-{attempt}',f'review_sample-{attempt}']
    if sorted(calls)!=sorted(roles):raise ValueError('Expected exactly extraction plus sample review')
    proofs=[]
    for role in roles:
        call=calls[role];req=json.loads(call['request']);receipt=json.loads(call['receipt'] or 'null')
        ledger=db.execute('SELECT * FROM reviews WHERE id=?',(call['id'],)).fetchone()
        if not receipt or not ledger or call['id']!=digest(canonical([pid,role,req])) or ledger['reserve']!=call['amount'] or json.loads(ledger['record'])['binding']['request_sha256']!=digest(call['request'].encode()):raise ValueError('Call/ledger drift')
        model=cfg['planner_model'] if role.startswith('extraction') else cfg['reviewer_model']
        if receipt.get('model')!=model or receipt['choices'][0]['finish_reason']!='stop':raise ValueError('Incomplete/model drift')
        proofs.append(dict(call_id=call['id'],call_sha256=digest(canonical(call)),ledger_sha256=digest(canonical(dict(ledger)))))
    eq=json.loads(calls[roles[0]]['request']);er=json.loads(calls[roles[0]]['receipt'])
    expected={'actor':cfg['actor_sha256'],'board':sha,'reference':cfg['reference_sha256']}
    decoded={};name=None
    for item in eq['body']['messages'][1]['content']:
        if item['type']=='text' and item['text'].startswith('evidence_id='):name=item['text'].split('=',1)[1]
        elif item['type']=='image_url':
            if not name or name in decoded:raise ValueError('Duplicate image role')
            decoded[name]=digest(base64.b64decode(item['image_url']['url'].split(',',1)[1],validate=True));name=None
    if decoded!=expected or eq['inputs']!=[dict(id=k,sha256=v) for k,v in sorted(expected.items())]:raise ValueError('Extraction role/source binding drift')
    decision=json.loads(er['choices'][0]['message']['content'])
    if (d/f'crop-decision-{attempt}.json').read_bytes()!=canonical(decision):raise ValueError('Fresh decision drift')
    crops=validate_crops(decision,sha,list(Image.open(io.BytesIO(source)).size),set(r['material_plan']['materials']))
    if r.get('crop_binding')!=crops:raise ValueError('Crop binding drift')
    for n,raw in [(f'crop-decision-{attempt}.json',(d/f'crop-decision-{attempt}.json').read_bytes())]:files[n]=digest(raw)
    from hybrid_artifact import verify_artifact
    sd=d/r['sample_directory'];verify_artifact(sd,r['sample_binding'])
    materials=set(r['material_plan']['materials'])
    review_images={'final':(sd/'scene.png').read_bytes(),'guide':(sd/'guide.png').read_bytes(),'reference':None}
    expected_v={'final':digest(review_images['final']),'guide':digest(review_images['guide']),'reference':cfg['reference_sha256']}
    for m in materials:expected_v['crop-'+m]=digest((sd/(m+'-crop.png')).read_bytes())
    vq=json.loads(calls[roles[1]]['request']);vr=json.loads(calls[roles[1]]['receipt'])
    if vq['inputs']!=[dict(id=k,sha256=v) for k,v in sorted(expected_v.items())]:raise ValueError('Review input binding drift')
    if r.get('sample_guide_sha256')!=expected_v['guide']:raise ValueError('Sample guide drift')
    review_raw=json.loads(vr['choices'][0]['message']['content'])
    if (d/f'review_sample-{attempt}.json').read_bytes()!=canonical(review_raw):raise ValueError('Review decision drift')
    if not r.get('gate') or r['gate'].get('approved') is not False or r['gate'].get('decision')!=review_raw:raise ValueError('Gate/decision drift')
    files[f'review_sample-{attempt}.json']=digest(canonical(review_raw))
    correction=review_correction(review_raw,set(expected_v),sha)
    p=dict(kind='source_reassessment_repair',parent_id=pid,parent_sha256=digest(canonical(dict(row))),calls=proofs,
        files=files,correction=correction,decision_sha256=digest(canonical(review_raw)),
        inherited_calls=r['call_count'],inherited_images=r['image_count'],inherited_local=r['local_count'])
    if binding and binding!=p:raise ValueError('Repair continuation drift')
    return p,plan,cfg

def continue_repair(store,pid,idem,budget,seconds,approval,directive):
    from decimal import Decimal
    from hybrid_worker import runtime_version
    from hybrid_source_recovery import TOKEN_POLICY
    p,_,_=validated_repair(store,parent_id=pid)
    cap=int(Decimal(str(store.g.policy['total_usd']))*1_000_000)
    if not isinstance(approval,str) or len(approval.strip())<10:raise ValueError('Explicit bounded repair authority required')
    if not isinstance(directive,str) or len(directive.strip())<10:raise ValueError('Explicit owner style directive required')
    if type(budget)!=int or not 0<budget<=cap or type(seconds)!=int or not 60<=seconds<=7200:raise ValueError('Repair limits invalid')
    if p['inherited_calls']+4>15 or p['inherited_images']+1>4:raise ValueError('Lifetime image/call amendment exhausted')
    parent=store.get(pid)
    amendment=dict(kind='bounded-reassessment-repair/1',approval_text=approval,owner_style_directive=directive,parent_id=pid,
        previous_max_calls=parent['config']['max_calls'],previous_max_images=parent['config']['max_images'],
        max_calls=15,max_images=4,new_images=1,followup_calls=4,project_cap_microusd=cap,source='review findings + explicit owner wish for image-to-image material repair')
    child={**parent['config'],'continuation':p,'authorization_amendment':amendment,'runtime_version':runtime_version(),
        'budget_microusd':budget,'max_seconds':seconds,'max_calls':15,'max_images':4,'max_local_corrections':0,
        'token_policy':TOKEN_POLICY,'followup_call_limit':4,'no_local_retries':True}
    child.pop('no_new_images',None)
    return store.create(idem,child)

def inherit_repair(worker,r):
    from hybrid_worker import immutable
    p,_,_=validated_repair(worker.s,r['config']['continuation'])
    parent=worker.s.get(p['parent_id']);src=worker.root/p['parent_id'];dest=worker.root/r['id']
    for name,sha in p['files'].items():
        raw=(src/name).read_bytes()
        if digest(raw)!=sha:raise ValueError('Repair inheritance drift')
        immutable(dest/name,raw)
    correction=dict(p['correction'],owner_style_directive=r['config']['authorization_amendment']['owner_style_directive'])
    immutable(dest/'review-correction.json',canonical(correction))
    fields=['layout','world','material_plan','interpretation','guide_file','guide_sha256','accepted_layout','crop_binding']
    changes={k:parent[k] for k in fields}
    # Next lifetime image index keeps artifact names collision-free (source-0..2 exist).
    attempt=parent['image_count']
    changes.update(attempt=attempt,previous_source=f"source-{parent['attempt']}.png",source_sha256=parent['source_sha256'],
        correction=correction,correction_kind='review_material_repair',
        frozen_sha256=digest(canonical(dict(config=r['config'],layout=parent['accepted_layout']))),stop_reason=None)
    worker.s.save(r,phase='generating',**changes)
