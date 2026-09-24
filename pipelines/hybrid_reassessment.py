"""Whole retained sources only; invalidating a rejection is never approval."""
import json,re
from artifacts import canonical,digest
from hybrid_material_repair import material_defect
from hybrid_models import CropMap,validate_crops

VALIDATOR='flat-material-role/2'

def select_candidate(candidates,required):
    eligible=[]
    for candidate in candidates:
        raw=CropMap.model_validate(candidate['decision']).model_dump()
        probe=json.loads(canonical(raw))
        if any(c['verdict']=='uncertain' for c in probe['crops'].values()):continue
        for c in probe['crops'].values():c['verdict']='pass'
        validate_crops(probe,candidate['source_sha256'],candidate['size'],required)
        failed={k:v for k,v in raw['crops'].items() if v['verdict']=='fail'}
        if not failed:continue
        try:material_defect(raw,candidate['source_sha256'],candidate['size'],required)
        except ValueError as error:
            if 'contract conflict' not in str(error):continue
        else:continue
        # Narrow forensic policy: every failing observation must be solely an
        # affirmative flat stone description followed by missing architecture.
        # Other defects/uncertainty cannot be overruled by this known bug.
        pattern=r'Flat [a-z ,/-]*(?:stone|concrete)[a-z ,/-]* (?:without|lacking) (?:any )?(?:cut stone )?(?:stair )?(?:treads?|risers?)(?: or (?:visible )?(?:risers?|treads?))?\.?'
        if not all(re.fullmatch(pattern,c['observation'].strip(),re.I) for c in failed.values()):continue
        eligible.append({**candidate,'invalidation':dict(validator_version=VALIDATOR,reason='sole rejection demands architecture forbidden in source materials',original_decision_sha256=digest(canonical(candidate['decision'])),invalidated_materials=sorted(failed),original_verdict_preserved=True,production_approved=False,requires_fresh_full_board_extraction=True)})
    if not eligible:raise ValueError('No archived source with solely proven architecture-role contradiction')
    return max(eligible,key=lambda c:c['attempt'])

def validated_archive(store,binding=None,parent_id=None,db=None):
    import io,base64
    from PIL import Image
    from hybrid_recovery import validated_parent
    from hybrid_layout import compile_layout
    if db is None:
        with store.g.connect() as conn:return validated_archive(store,binding,parent_id,conn)
    pid=binding['parent_id'] if binding else parent_id
    row=db.execute('SELECT * FROM hybrid_runs WHERE id=?',(pid,)).fetchone()
    if not row or row['phase']!='needs_attention' or row['lease'] or row['cancel']:raise ValueError('Archive parent must be sealed')
    cfg=json.loads(row['config']);r=json.loads(row['record']);d=store.g.root/'hybrid'/pid
    if cfg.get('continuation',{}).get('kind')!='material_repair' or cfg['mode']!='live':raise ValueError('Expected material repair archive')
    inherited,plan,_=validated_parent(store,cfg['continuation'],db=db)
    ancestor=store.get(inherited['parent_id'])
    if r['material_plan']!=ancestor['material_plan'] or r['accepted_layout']!=plan['layout'] or r['world']!=compile_layout(plan['layout']) or r['frozen_sha256']!=digest(canonical(dict(config=cfg,layout=plan['layout']))):raise ValueError('Archived intent/layout drift')
    calls=db.execute('SELECT * FROM hybrid_calls WHERE run=? ORDER BY role',(pid,)).fetchall()
    byrole={c['role']:c for c in calls};proofs=[];candidates=[]
    images=[c for c in calls if c['role'].startswith('image-')]
    if len(calls)!=2*len(images) or r['call_count']!=inherited['inherited_calls']+len(calls) or r['image_count']!=inherited['inherited_images']+len(images):raise ValueError('Archive lifetime drift')
    files=dict(inherited['files'])
    for name,sha in files.items():
        if digest((d/name).read_bytes())!=sha:raise ValueError('Inherited archive drift')
    for image in images:
        attempt=int(image['role'].split('-')[1]);extract=byrole.get(f'extraction-{attempt}')
        if not extract:raise ValueError('Missing complete paired extraction')
        for call in [image,extract]:
            req=json.loads(call['request']);receipt=json.loads(call['receipt'] or 'null')
            ledger=db.execute('SELECT * FROM reviews WHERE id=?',(call['id'],)).fetchone()
            if not receipt or not ledger or call['id']!=digest(canonical([pid,call['role'],req])) or ledger['reserve']!=call['amount'] or json.loads(ledger['record'])['binding']['request_sha256']!=digest(call['request'].encode()):raise ValueError('Archive call/ledger drift')
            proofs.append(dict(call_id=call['id'],call_sha256=digest(canonical(dict(call))),ledger_sha256=digest(canonical(dict(ledger)))))
        iq=json.loads(image['request']);ir=json.loads(image['receipt']);eq=json.loads(extract['request']);er=json.loads(extract['receipt'])
        source=(d/f'source-{attempt}.png').read_bytes();sha=digest(source)
        previous=digest((d/f'source-{attempt-1}.png').read_bytes())
        expected=[dict(id='reference',sha256=cfg['reference_sha256']),dict(id='guide',sha256=r['guide_sha256']),dict(id='correction_target',sha256=previous)]
        if iq['attempt']!=attempt or iq['amount']!=image['amount'] or iq['inputs']!=expected or ir.get('input')!=iq['body'] or not ir.get('id'):raise ValueError('Image role/prediction drift')
        if (d/f'image-request-{attempt}.json').read_bytes()!=canonical(iq):raise ValueError('Image request artifact drift')
        if eq['body']['model']!=cfg['planner_model'] or er.get('model')!=cfg['planner_model'] or er['choices'][0]['finish_reason']!='stop':raise ValueError('Extraction incomplete/model drift')
        expected={'actor':cfg['actor_sha256'],'board':sha,'reference':cfg['reference_sha256']}
        decoded={};name=None
        for item in eq['body']['messages'][1]['content']:
            if item['type']=='text' and item['text'].startswith('evidence_id='):name=item['text'].split('=',1)[1]
            elif item['type']=='image_url':
                if not name or name in decoded:raise ValueError('Duplicate image role')
                decoded[name]=digest(base64.b64decode(item['image_url']['url'].split(',',1)[1],validate=True));name=None
        if decoded!=expected or eq['inputs']!=[dict(id=k,sha256=v) for k,v in sorted(expected.items())]:raise ValueError('Extraction role/source binding drift')
        raw=json.loads(er['choices'][0]['message']['content'])
        if (d/f'crop-decision-{attempt}.json').read_bytes()!=canonical(raw):raise ValueError('Historical verdict drift')
        # A prediction was polled and this exact source then extracted by the
        # worker. Preserve the retained event chain as provenance, not a new
        # provider output attestation (the old submit receipt has no outputs).
        events=[json.loads(x[0]) for x in db.execute('SELECT record FROM hybrid_events WHERE run=? ORDER BY seq',(pid,))]
        if not any(e.get('changes',{}).get('prediction_id')==ir['id'] for e in events) or not any(e.get('changes',{}).get('source_sha256')==sha for e in events):raise ValueError('Missing worker prediction/source events')
        candidates.append(dict(attempt=attempt,decision=raw,source_sha256=sha,size=list(Image.open(io.BytesIO(source)).size),prediction_id=ir['id'],image_call_id=image['id'],extraction_call_id=extract['id']))
        for n in [f'source-{attempt}.png',f'image-request-{attempt}.json',f'crop-decision-{attempt}.json']:files[n]=digest((d/n).read_bytes())
    selected=select_candidate(candidates,set(r['material_plan']['materials']))
    p=dict(kind='source_reassessment',parent_id=pid,parent_sha256=digest(canonical(dict(row))),calls=proofs,files=files,events_sha256=digest(canonical(events)),selected=selected,inherited_calls=r['call_count'],inherited_images=r['image_count'],inherited_local=r['local_count'])
    if binding and binding!=p:raise ValueError('Archive continuation drift')
    return p,plan,cfg

def continue_archive(store,pid,idem,budget,seconds,approval):
    from decimal import Decimal
    from hybrid_worker import runtime_version
    from hybrid_source_recovery import TOKEN_POLICY
    p,_,cfg=validated_archive(store,parent_id=pid)
    cap=int(Decimal(str(store.g.policy['total_usd']))*1_000_000)
    if type(budget)!=int or not 0<budget<=cap or type(seconds)!=int or not 60<=seconds<=7200 or not isinstance(approval,str) or len(approval.strip())<10:raise ValueError('Explicit bounded reassessment authority required')
    if p['inherited_calls']+3>cfg['max_calls']:raise ValueError('Three followup calls must fit lifetime cap')
    amendment=dict(kind='retained-source-reassessment/1',approval_text=approval,parent_id=pid,project_cap_microusd=cap,budget_microusd=budget,max_calls=cfg['max_calls'],max_images=cfg['max_images'],new_images=0,followup_calls=3,validator_version=VALIDATOR)
    return store.create(idem,{**cfg,'continuation':p,'authorization_amendment':amendment,'runtime_version':runtime_version(),'budget_microusd':budget,'max_seconds':seconds,'token_policy':TOKEN_POLICY,'followup_call_limit':3,'no_new_images':True,'no_local_retries':True})

def inherit_archive(worker,r):
    from hybrid_worker import immutable
    p,_,_=validated_archive(worker.s,r['config']['continuation'])
    parent=worker.s.get(p['parent_id']);src=worker.root/p['parent_id'];dest=worker.root/r['id']
    for name,sha in p['files'].items():
        raw=(src/name).read_bytes()
        if digest(raw)!=sha:raise ValueError('Archive inheritance drift')
        target='historical-'+name if name.startswith('crop-decision-') else name
        immutable(dest/target,raw)
    immutable(dest/'source-reassessment.json',canonical(p))
    fields=['layout','world','material_plan','interpretation','guide_file','guide_sha256','accepted_layout']
    changes={k:parent[k] for k in fields};chosen=p['selected']
    changes.update(attempt=chosen['attempt'],source_sha256=chosen['source_sha256'],prediction_id=chosen['prediction_id'],frozen_sha256=digest(canonical(dict(config=r['config'],layout=parent['accepted_layout']))))
    worker.s.save(r,phase='extracting',stop_reason=None,reassessment=chosen['invalidation'],**changes)
