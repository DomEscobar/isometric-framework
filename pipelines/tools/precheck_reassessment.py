"""Read-only precheck of the real archive + ledger. No writes beyond idempotent migration DDL."""
import json,sys,traceback
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from artifacts import canonical,digest
from hybrid_worker import default_store
from billing_settlement import totals

s=default_store()
pid='a3d4ce60a6db4bc7a2702217d62ce2db'
with s.g.connect() as db:
    t=totals(db)
    print('TOTALS',json.dumps(t))
    print('POLICY',json.dumps(s.g.policy))
    unknown=[dict(x) for x in db.execute('SELECT id,run,role,amount,request FROM hybrid_calls WHERE receipt IS NULL')]
    for u in unknown:
        u['request_sha256']=digest(u.pop('request').encode())
        print('UNKNOWN_CALL',json.dumps(u))
    print('ACKS',[r[0] for r in db.execute('SELECT id FROM hybrid_liability_authorizations')])
    for r in db.execute('SELECT id,phase,fence,lease,cancel,record,config FROM hybrid_runs ORDER BY rowid'):
        rec=json.loads(r['record'])
        print('RUN',r['id'],r['phase'],'calls',rec.get('call_count'),'images',rec.get('image_count'),'local',rec.get('local_count'),'lease',r['lease'],'cancel',r['cancel'],'cont_kind',json.loads(r['config']).get('continuation',{}).get('kind'))
    children=[r[0] for r in db.execute('SELECT id FROM hybrid_runs') ]
    for rid in children:
        row=db.execute('SELECT config FROM hybrid_runs WHERE id=?',(rid,)).fetchone()
        if json.loads(row[0]).get('continuation',{}).get('parent_id')==pid:
            print('EXISTING_CHILD_OF_PARENT',rid)
    calls=db.execute('SELECT id,role,amount FROM hybrid_calls WHERE run=? ORDER BY rowid',(pid,)).fetchall()
    print('PARENT_CALLS',[dict(c) for c in calls])
try:
    from hybrid_reassessment import validated_archive,select_candidate
    p,plan,cfg=validated_archive(s,parent_id=pid)
    sel=p['selected']
    print('ARCHIVE_OK','selected_attempt',sel['attempt'],'selected_sha',sel['source_sha256'])
    print('INVALIDATION',json.dumps(sel['invalidation']))
    print('INHERITED',p['inherited_calls'],p['inherited_images'],p['inherited_local'])
    print('FOLLOWUPS_FIT',p['inherited_calls']+3,'<=',cfg['max_calls'])
    print('BINDING_SHA',digest(canonical(p)))
except Exception:
    print('ARCHIVE_FAIL');traceback.print_exc()
