"""Immutable continuation from known image + incomplete extraction, never new image."""
import json,io
from decimal import Decimal
from PIL import Image
from artifacts import canonical,digest
from hybrid_layout import compile_layout

TOKEN_POLICY={k:{'max_tokens':32768,'reasoning_effort':'medium'} for k in ['extraction','review']}

def validated_source(store,binding=None,parent_id=None,db=None):
    from hybrid_recovery import validated_parent,normalize_material_plan
    if db is None:
        with store.g.connect() as conn:return validated_source(store,binding,parent_id,conn)
    pid=binding['parent_id'] if binding else parent_id
    row=db.execute('SELECT * FROM hybrid_runs WHERE id=?',(pid,)).fetchone()
    if not row or row['phase']!='needs_attention' or row['lease'] or row['cancel']:raise ValueError('Source parent must be sealed')
    cfg=json.loads(row['config']);r=json.loads(row['record']);d=store.g.root/'hybrid'/pid
    if cfg.get('continuation',{}).get('kind')=='source' or not cfg.get('continuation') or cfg['mode']!='live':raise ValueError('Only first source continuation allowed')
    _,plan,_=validated_parent(store,cfg['continuation'],db=db)
    if r['call_count']!=3 or r['image_count']!=1 or r['local_count']!=0 or r.get('attempt')!=0 or r.get('latest'):raise ValueError('Unexpected inherited attempt history')
    calls=db.execute('SELECT * FROM hybrid_calls WHERE run=? ORDER BY role',(pid,)).fetchall()
    if {x['role'] for x in calls}!={'image-0','extraction-0'}:raise ValueError('Image/extraction history mismatch')
    proofs=[]
    for call in calls:
        request=json.loads(call['request']);receipt=json.loads(call['receipt'] or 'null')
        ledger=db.execute('SELECT * FROM reviews WHERE id=?',(call['id'],)).fetchone()
        if call['id']!=digest(canonical([pid,call['role'],request])) or not ledger or ledger['reserve']!=call['amount'] or json.loads(ledger['record'])['binding']['request_sha256']!=digest(call['request'].encode()) or not receipt:raise ValueError('Source call/ledger/receipt drift')
        if call['role']=='image-0':
            if request!=r['prepared_image'] or request['amount']!=call['amount'] or receipt.get('id')!=r['prediction_id']:raise ValueError('Prediction binding drift')
        else:
            if receipt.get('model')!=cfg['planner_model'] or request['body']['model']!=cfg['planner_model'] or receipt['choices'][0].get('finish_reason')!='length':raise ValueError('Only known truncated extraction can continue')
            if [x for x in request['inputs'] if x['id']=='board']!=[{'id':'board','sha256':r['source_sha256']}]:raise ValueError('Extraction source drift')
        proofs.append({'call_id':call['id'],'call_sha256':digest(canonical(dict(call))),'ledger_sha256':digest(canonical(dict(ledger)))})
    w=compile_layout(plan['layout'])
    if r['accepted_layout']!=plan['layout'] or r['world']!=w or r['frozen_sha256']!=digest(canonical({'config':cfg,'layout':r['accepted_layout']})):raise ValueError('Frozen layout drift')
    mp=normalize_material_plan(plan['material_plan'],{c for row in w['cells'] for c in row}|{'wall'})
    if r['material_plan']!=mp:raise ValueError('Material intent drift')
    names=['planner-result.json','transition-normalization.json','material-normalization.json','layout-preview.png',r['guide_file'],'source-0.png']
    files={n:digest((d/n).read_bytes()) for n in names}
    if files['source-0.png']!=r['source_sha256'] or files[r['guide_file']]!=r['guide_sha256'] or files['planner-result.json']!=digest(canonical(plan)):raise ValueError('Retained artifact drift')
    im=Image.open(io.BytesIO((d/'source-0.png').read_bytes()));im.verify()
    p=dict(kind='source',parent_id=pid,parent_sha256=digest(canonical(dict(row))),calls=proofs,files=files,prediction_id=r['prediction_id'],source_sha256=r['source_sha256'],inherited_calls=3,inherited_images=1,inherited_local=0)
    if binding and binding!=p:raise ValueError('Source continuation drift')
    return p,plan,cfg

def continue_source(store,pid,idem,budget,seconds,approval):
    from hybrid_worker import runtime_version
    p,plan,cfg=validated_source(store,parent_id=pid)
    cap=int(Decimal(str(store.g.policy.get('total_usd','0')))*1_000_000)
    if type(budget)!=int or not 0<budget<=cap or type(seconds)!=int or not 60<=seconds<=cfg['max_seconds'] or not isinstance(approval,str) or not approval.strip():raise ValueError('Explicit bounded continuation authority required')
    amendment=dict(kind='one-source-token-recovery/1',approval_text=approval,parent_id=pid,previous_max_calls=cfg['max_calls'],max_calls=6,max_images=1,max_local_corrections=0,project_cap_microusd=cap,previous_budget_microusd=cfg['budget_microusd'],budget_microusd=budget)
    cfg={**cfg,'continuation':p,'authorization_amendment':amendment,'runtime_version':runtime_version(),'budget_microusd':budget,'max_seconds':seconds,'max_calls':6,'max_images':1,'max_local_corrections':0,'token_policy':TOKEN_POLICY,'auto_continue':True}
    return store.create(idem,cfg)

def inherit_source(worker,r):
    from hybrid_worker import immutable
    p,_,_=validated_source(worker.s,r['config']['continuation'])
    parent=worker.s.get(p['parent_id']);src=worker.root/p['parent_id'];dest=worker.root/r['id']
    for name,sha in p['files'].items():
        raw=(src/name).read_bytes()
        if digest(raw)!=sha:raise ValueError('Source artifact changed during inheritance')
        immutable(dest/name,raw)
    fields=['layout','world','material_plan','interpretation','guide_file','guide_sha256','accepted_layout','attempt','source_sha256','prediction_id']
    changes={k:parent[k] for k in fields}
    changes['frozen_sha256']=digest(canonical({'config':r['config'],'layout':parent['accepted_layout']}))
    worker.s.save(r,phase='extracting',stop_reason=None,**changes)
