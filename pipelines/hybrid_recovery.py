"""Free, receipt-bound planner continuation; never accepts an operator plan."""
import base64,json
from artifacts import canonical,digest
from hybrid_models import Plan

def normalize_material_plan(plan,required):
    # A named cliff/walls wall is the renderer's exposed vertical face, not a cell.
    materials=dict(plan['materials'])
    for alias in ['cliff_wall','walls']:
        if alias in materials and 'wall' not in materials:
            materials['wall']=materials.pop(alias);break
    if 'ground' in materials and 'land' not in materials:
        materials['land']=materials.pop('ground')
    if set(materials)!=set(required):raise ValueError('Materialplan muss exakt alle Geometriesemantiken plus wall abdecken')
    return {**plan,'materials':materials}

def validated_parent(store,binding=None,parent_id=None,db=None):
    if binding and binding.get('kind')=='directive_repair':
        from hybrid_directive_repair import validated_directive
        return validated_directive(store,binding,parent_id,db)
    if binding and binding.get('kind')=='sampling_repair':
        from hybrid_sampling_repair import validated_sampling_repair
        return validated_sampling_repair(store,binding,parent_id,db)
    if binding and binding.get('kind')=='source_reassessment_repair':
        from hybrid_reassessment_repair import validated_repair
        return validated_repair(store,binding,parent_id,db)
    if binding and binding.get('kind')=='source_reassessment':
        from hybrid_reassessment import validated_archive
        return validated_archive(store,binding,parent_id,db)
    if binding and binding.get('kind')=='material_repair':
        from hybrid_material_repair import validated_material
        return validated_material(store,binding,parent_id,db)
    if binding and binding.get('kind')=='source':
        from hybrid_source_recovery import validated_source
        return validated_source(store,binding,parent_id,db)
    if db is None:
        with store.g.connect() as conn:return validated_parent(store,binding,parent_id,conn)
    pid=binding['parent_id'] if binding else parent_id
    row=db.execute('SELECT * FROM hybrid_runs WHERE id=?',(pid,)).fetchone()
    if not row or row['phase']!='needs_attention' or row['lease'] or row['cancel']:raise ValueError('Nur versiegelter nicht abgebrochener Parent')
    cfg=json.loads(row['config']);record=json.loads(row['record'])
    calls=db.execute('SELECT * FROM hybrid_calls WHERE run=?',(pid,)).fetchall()
    if cfg['mode']!='live' or len(calls)!=1 or calls[0]['role']!='planner' or not calls[0]['receipt'] or cfg.get('continuation'):raise ValueError('Nur bekannter alleiniger Plannerreceipt fortsetzbar')
    call=dict(calls[0]);req=json.loads(call['request']);receipt=json.loads(call['receipt'])
    if call['id']!=digest(canonical([pid,'planner',req])):raise ValueError('Call-Request-Drift')
    ledger=db.execute('SELECT * FROM reviews WHERE id=?',(call['id'],)).fetchone()
    if not ledger or ledger['reserve']!=call['amount'] or json.loads(ledger['record'])['binding']['request_sha256']!=digest(call['request'].encode()):raise ValueError('Ledger-Drift')
    if req['body']['model']!=cfg['planner_model'] or req['metadata']['id']!=cfg['planner_model'] or receipt.get('model')!=cfg['planner_model'] or not receipt.get('id'):raise ValueError('Modell-/Receipt-Drift')
    choice=receipt['choices'][0]
    if choice.get('finish_reason')!='stop':raise ValueError('Unvollständiger Receipt')
    images={};name=None
    for item in req['body']['messages'][1]['content']:
        if item['type']=='text' and item['text'].startswith('evidence_id='):name=item['text'].split('=',1)[1]
        if item['type']=='image_url':
            if name in images or name is None:raise ValueError('Bildrollen falsch')
            images[name]=digest(base64.b64decode(item['image_url']['url'].split(',',1)[1],validate=True));name=None
    expected={'actor':cfg['actor_sha256'],'reference':cfg['reference_sha256']}
    if images!=expected or req['inputs']!=[dict(id=k,sha256=v) for k,v in sorted(expected.items())]:raise ValueError('Planner-Input-Drift')
    plan=Plan.model_validate(json.loads(choice['message']['content'])).model_dump()
    retained=(store.g.root/'hybrid'/pid/'planner-result.json').read_bytes()
    if retained!=canonical(plan):raise ValueError('Planartefakt-Drift')
    proof=dict(parent_id=pid,parent_sha256=digest(canonical(dict(row))),call_id=call['id'],request_sha256=digest(call['request'].encode()),receipt_sha256=digest(call['receipt'].encode()),plan_sha256=digest(retained),inherited_calls=record['call_count'],inherited_images=record['image_count'],inherited_local=record['local_count'])
    if binding and binding!=proof:raise ValueError('Continuation-Drift')
    return proof,plan,cfg

def continue_planner(store,pid,idem,budget,seconds):
    from hybrid_worker import runtime_version
    proof,plan,cfg=validated_parent(store,parent_id=pid)
    if type(budget)!=int or not 0<budget<=cfg['budget_microusd'] or type(seconds)!=int or not 60<=seconds<=cfg['max_seconds']:raise ValueError('Continuation-Limits dürfen nicht wachsen')
    cfg={**cfg,'continuation':proof,'runtime_version':runtime_version(),'budget_microusd':budget,'max_seconds':seconds,'auto_continue':True}
    return store.create(idem,cfg)
