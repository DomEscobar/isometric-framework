"""Production export requires exact final bytes and two actual bound review receipts."""
import io,json,zipfile
from artifacts import canonical,digest
from hybrid_artifact import verify_artifact
from hybrid_models import review_gate

def production_bundle(s,r):
    if r['phase']!='succeeded' or r['config']['mode']!='live' or not r.get('production_approved') or not r.get('latest') or r.get('best')!=r['latest']:raise ValueError('Produktion nicht freigegeben')
    d=s.g.root/'hybrid'/r['id'];out=d/r['latest'];verify_artifact(out,r.get('artifact_binding'))
    proof=r.get('verification')
    if not proof or not proof.get('rebuild_exact') or not proof.get('browser'):raise ValueError('Paket-/Browserbeweis fehlt')
    if r.get('sample_directory') and not proof.get('production_rebuild_exact'):raise ValueError('Produktions-Rebuildbeweis fehlt')
    receipts=[];attempt=r['attempt']
    for role in [r.get('sample_review_role','review_sample-'+str(attempt)),r.get('final_review_role','review_final-'+str(attempt))]:
        with s.g.connect() as db:rows=db.execute('SELECT * FROM hybrid_calls WHERE run=? AND role=?',(r['id'],role)).fetchall()
        if len(rows)!=1 or not rows[0]['receipt']:raise ValueError('Reviewreceipt fehlt/mehrdeutig')
        row=rows[0];req=json.loads(row['request']);response=json.loads(row['receipt'])
        if row['id']!=digest(canonical([r['id'],role,req])):raise ValueError('Reviewrequest-Drift')
        with s.g.connect() as db:ledger=db.execute('SELECT record FROM reviews WHERE id=?',(row['id'],)).fetchone()
        if not ledger or json.loads(ledger[0])['binding']['request_sha256']!=digest(row['request'].encode()):raise ValueError('Zentrale Ledgerbindung fehlt')
        model=r['config']['reviewer_model'];choice=(response.get('choices') or [{}])[0]
        if response.get('model')!=model or req['metadata']['id']!=model or choice.get('finish_reason')!='stop':raise ValueError('Reviewmodell/Finish ungültig')
        inputs={x['id']:x['sha256'] for x in req['inputs']}
        review_out=d/r['sample_directory'] if role.startswith('review_sample') and r.get('sample_directory') else out
        if review_out!=out:verify_artifact(review_out,r['sample_binding'])
        required={'final':review_out/'scene.png','guide':review_out/'guide.png' if review_out!=out else d/r['guide_file'],'reference':s.g.root/'hybrid-uploads'/(r['config']['reference_sha256']+'.png')}
        for name,sha in inputs.items():
            p=required.get(name,review_out/(name.removeprefix('crop-')+'-crop.png'))
            if digest(p.read_bytes())!=sha:raise ValueError('Revieweingabe verändert')
        if not set(required)<=set(inputs):raise ValueError('Reviewbilder fehlen')
        decision=json.loads(choice['message']['content']);gate=review_gate(decision,inputs)
        if not gate['approved']:raise ValueError('Reviewgate abgewiesen')
        receipts.append({'role':role,'call_id':row['id'],'request_sha256':digest(row['request'].encode()),'receipt_sha256':digest(row['receipt'].encode()),'inputs':req['inputs'],'decision':decision,'model':model,'usage':response.get('usage')})
    with zipfile.ZipFile(out/'diagnostic.zip') as z:files={n:z.read(n) for n in z.namelist()}
    from hybrid_package import extend
    from hybrid_reference import reference_bytes
    normalized,original=reference_bytes(s.g.root,r['config'])
    prov=json.loads(files['provenance.json']);prov.update(production_approved=True,export_mode='production',user_acceptance='pending')
    extra={'provenance.json':canonical(prov),'approval.json':canonical({'reviews':receipts,'verification':proof,'owner_acceptance':'pending'}),
           'reference.png':normalized,'reference-original.image':original,
           'reference-binding.json':canonical({'role':'style_only','normalized_sha256':digest(normalized),'original_sha256':digest(original),'original_bytes_preserved':True}),
           'accepted-guide.png':(d/r['guide_file']).read_bytes()}
    if r.get('sample_directory'):
        sd=d/r['sample_directory']
        for n in r['sample_binding']:extra['sample/'+n]=(sd/n).read_bytes()
        extra['sample/guide.png']=(sd/'guide.png').read_bytes()
    return extend((out/'diagnostic.zip').read_bytes(),extra)
