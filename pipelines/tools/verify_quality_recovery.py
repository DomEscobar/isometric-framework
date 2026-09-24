"""Verify genuine recovery artifacts, downloaded ZIPs, native pixels and closed controls.
No paid calls; failed-fit rendering is diagnostic ONLY, never a persisted candidate.
"""
import io,json,re,sys,zipfile,os
from pathlib import Path
from decimal import Decimal
import numpy as np
import httpx
from PIL import Image,ImageDraw
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app import create_app
from artifacts import canonical,digest
from terrain import render_original
root=Path(__file__).resolve().parents[1];out=root/'evidence/quality-recovery'
app=create_app();s=app.state.auto_repair;g=s.g;rid=(out/'run-id.txt').read_text().strip();w=s.get(rid)
assert w['status']=='needs_attention' and w['phase']=='register'
parent_id=w['continuation']['parent_run_id'];parent=s.get(parent_id)
assert parent==json.loads((out/'parent-before.json').read_bytes())
assert len(s.history(w))==w['inherited_iterations']+len(w['iterations'])==3
assert not g.policy['approved'] and not app.state.reviewer.config.enabled
assert not json.loads((g.root/'quality-recovery-policy.json').read_bytes())['enabled']
assert s.adapter.liability_blockers()==[]  # only HTTP uncertainty resolved, never billing settled
from transport_reconciliation import verified_rejection
event=verified_rejection(g,'paid-pilot-01');assert event==json.loads((out/'transport-reconciliation-event.json').read_bytes())
assert event['reserve_microusd']==794112 and event['released_microusd']==0
zips=[];images={}
for directory,cid in [('verification',w['best_candidate_id']),('registered-reviewed-navigation',w['iterations'][0]['candidate_id'])]:
    bd=out/directory;br=json.loads((bd/'browser-report.json').read_bytes());zp=bd/br['download']
    with zipfile.ZipFile(zp) as z:
        assert z.testzip() is None;files={n:z.read(n) for n in z.namelist()}
    for name,sha in json.loads(files['checksums.json']).items():assert digest(files[name])==sha,name
    r=json.loads(files['candidate.json']);layout=json.loads(files['layout.json']);prov=json.loads(files['terrain-provenance.json'])
    assert r['id']==cid and digest(canonical(layout))==w['frozen']['revision'] and not prov['production_approved']
    assert files['sources/original.png']==(g.root/'terrain'/cid/'source.png').read_bytes()
    im=Image.open(io.BytesIO(files['terrain.png'])).convert('RGBA');expected=render_original(layout,r,files['sources/original.png'],1)
    assert np.array_equal(np.array(im),np.array(expected));images[directory]=im
    guide=np.array(Image.open(io.BytesIO(files['clean-guide.png'])).convert('RGBA'))
    assert not np.any((guide[:,:,3]>0)&(np.array(im)[:,:,3]<255))
    if directory=='registered-reviewed-navigation':
        assert prov['evaluation_id']==w['iterations'][0]['review']['id']
        rgb=tuple(map(int,re.findall(r'\d+',br['sampling']['stageBackground'])));assert len(rgb)==3
        composite=Image.new('RGBA',im.size,(*rgb,255));composite.alpha_composite(im)
        a=np.array(composite.convert('RGB'));b=np.array(Image.open(bd/'canvas-native.png').convert('RGB'));assert a.shape==b.shape
        yy,xx=np.where(np.any(a!=b,axis=2));p=layout['projection'];cx,cy=br['sampling']['actor']
        x=p['origin_px'][0]+(cx+.5)*p['column_basis_px'][0]+(cy+.5)*p['row_basis_px'][0]
        y=p['origin_px'][1]+(cx+.5)*p['column_basis_px'][1]+(cy+.5)*p['row_basis_px'][1]
        assert np.all((abs(xx-x)<=22)&(yy>=y-23)&(yy<=y+13)),'non-actor native pixel drift'
        pixel_proof=dict(canvas=br['sampling']['canvas'],css=br['sampling']['css'],dpr=br['sampling']['dpr'],actor_only_differences=len(xx),non_actor_differences=0)
    zips.append(dict(path=str(zp.relative_to(root)),sha256=digest(zp.read_bytes()),members=len(files),candidate_id=cid,production_approved=False,checksums_verified=True,direct_original_pixel_replay=True))
# Render actual latest source with the FAILED frozen fit for a fair native-scale diagnostic.
latest=json.loads((g.root/'terrain'/w['latest_candidate_id']/'record.json').read_bytes());raw=(g.root/'terrain'/latest['id']/'source.png').read_bytes()
assert raw==(out/'verification/latest-original.png').read_bytes()
a=w['iterations'][-1];reg=a['registration'];assert reg.get('blocker')
after=render_original(layout,{**latest,'processing_registration':{'scale':reg['scale'],'translation':reg['translation']}},raw,1).convert('RGBA')
before=images['verification'];board=Image.new('RGB',(before.width*2,before.height+68),'#18212a');board.paste(before,(0,68),before);board.paste(after,(before.width,68),after)
d=ImageDraw.Draw(board);d.text((12,10),'BEFORE: retained urban best / 768x408 / 48x24 logical tiles',fill='white');d.text((12,32),'Unapproved: dense stones and grass fringes. Technical actor omitted.',fill='white');d.text((before.width+12,10),'NEW REAL SOURCE: FAILED-FIT DIAGNOSTIC / NOT GAMEPLAY',fill='white');d.text((before.width+12,32),'Broad slabs improved; geometry gate and grass-edge concerns remain.',fill='white');board.save(out/'before-after-native-diagnostic.png')
for name,image,label in [('latest-native-diagnostic',after,'FAILED-FIT DIAGNOSTIC - NOT GAMEPLAY'),('registered-native',images['registered-reviewed-navigation'],'NEW CONSERVATIVE REGISTRATION - SAME OLD ART / NOT APPROVED')]:
    panel=Image.new('RGB',(image.width,image.height+34),'#18212a');panel.paste(image,(0,34),image);ImageDraw.Draw(panel).text((12,10),label,fill='white');panel.save(out/(name+'.png'))
# Exact provider request/quote/receipt bindings; never export signed URLs.
j=g.get(a['job_id']);q=g.get_quote(a['quote_id']);receipt=(g.root/(j['id']+'.receipt.json')).read_bytes()
assert set(j['request'])=={'image_urls','prompt','output_format'} and len(j['request']['image_urls'])==6
assert digest(canonical(j['request']))==j['request_sha256']
assert j['binding']['style_references'][-1]['reference_id']==a['input_candidate_id']
assert 'Image 3: material_only sidewalk' in j['request']['prompt']
assert 'material_only crop takes priority' in j['request']['prompt']
job=dict(id=j['id'],prediction_id=j['prediction_id'],request_sha256=j['request_sha256'],receipt_sha256=digest(receipt),source_sha256=digest(raw),schema_sha256=q['schema_sha256'],quote=j['exact_quote'],reserved_microusd=j['reserved_microusd'])
review=s.adapter.ev.get(w['iterations'][0]['review']['id']);s.adapter._continuation_review_receipt(review['id'],review)
(out/'new-review.json').write_bytes(canonical(review))
with g.connect() as db:
    jobs=[dict(r) for r in db.execute('SELECT id,reserve FROM jobs')];reviews=[dict(r) for r in db.execute('SELECT id,reserve FROM reviews')]
usage=[]
for r in reviews:
    path=g.root/'reviews'/r['id']/'receipt.json'
    if path.exists():
        receipt=json.loads(path.read_bytes());cost=receipt.get('usage',{}).get('cost')
        usage.append(dict(id=r['id'],reported_cost_usd=None if cost is None else str(cost),reserve_microusd=r['reserve']))
held=sum(r['reserve'] for r in jobs+reviews);assert held==4853712 and held<=10000000
base=os.environ.get('BASE_URL','http://127.0.0.1:38363')
with httpx.Client(base_url=base,timeout=60) as c:
    assert c.get('/').status_code==200
    budget=c.get('/api/generation/status').json();assert not budget['enabled'] and Decimal(budget['reserved_usd'])==Decimal(held)/1000000
    assert c.get('/api/reviewer/config').json()['enabled'] is False
    assert c.get('/api/auto-repair/'+rid).json()==w
    assert c.post('/api/auto-repair/'+rid+'/resume').json()==w
    assert c.post('/api/evaluations/'+review['id']+'/review',json={'confirm_paid':True}).status_code==403
    assert c.post('/api/generation/confirm',json={'quote_id':q['id'],'revision':w['frozen']['revision']}).status_code==403
    assert c.get('/api/terrain/'+latest['id']+'/download',params={'revision':w['frozen']['revision'],'density':1}).status_code==422
summary=dict(outcome='real targeted correction improved slab scale but remains unsafe/unapproved',run_id=rid,parent_run_id=parent_id,parent_unchanged=True,
 lifetime_attempts=len(s.history(w)),new_registration_attempts=1,new_image_attempts=1,new_review_attempts=1,status=w['status'],stop_reason=w['stop_reason'],
 best_candidate_id=w['best_candidate_id'],new_registered_candidate_id=w['iterations'][0]['candidate_id'],latest_candidate_id=w['latest_candidate_id'],new_evaluation_id=review['id'],
 best_evaluation_id=w['best_evaluation_id'],new_review_criteria=review['gate']['criteria'],worst_registration_residual_px=max(f['max_residual_px'] for f in reg['measurements']['fits']),registration_limit_px=2.5,
 job=job,zip_artifacts=zips,native_pixel_proof=pixel_proof,accounting=budget,new_review_reported_usage_usd=str(review['result']['usage']['cost']),
 all_review_reported_usage_usd=str(sum((Decimal(u['reported_cost_usd']) for u in usage if u['reported_cost_usd'] is not None),Decimal(0))),review_usage_records=usage,
 transport_reconciliation_id=event['id'],historical_401_hold_usd='0.794112',billing_unverified_hold_retained=True,paid_controls_closed=True,
 production_approved=False,note='Reported usage is INCLUDED in held totals, not additive. Right-side before/after is labelled failed-fit diagnostic, never gameplay or a candidate fed back to the run.')
(out/'verification.json').write_bytes(canonical(summary));print(json.dumps(summary,indent=2))
