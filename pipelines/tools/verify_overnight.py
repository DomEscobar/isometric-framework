"""Verify exact retained browser downloads, pixels, collision and one shared ledger."""
import sys,json,io,zipfile,sqlite3,re
from pathlib import Path
from decimal import Decimal
import numpy as np
from PIL import Image,ImageDraw
import httpx
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from artifacts import canonical,digest,export_files
from terrain import render_original
root=Path(__file__).resolve().parents[1];out=root/'evidence/overnight-two-styles';c=httpx.Client(base_url='http://127.0.0.1:59661',timeout=120)
w=json.loads((out/'batch-readback.json').read_bytes());assert c.get('/api/overnight-batch/'+w['id']).json()==w
old=c.get('/api/auto-repair/8e96cc6e6289256aead3f64d8ea86bfc132d7c47dee27898749bf43428cc1577').json();assert old==json.loads((out/'old-run-before.json').read_bytes())
report=json.loads((out/'browser/browser-report.json').read_bytes());layout=json.loads((out/'common/layout.json').read_bytes());canonical_files=export_files(layout);a=w['styles'][0];record=c.get('/api/terrain/'+a['candidate_id']).json();raw=(out/'warm/source.png').read_bytes();expected=render_original(layout,record,raw,1);zip_results=[]
for kind,name in report['downloads'].items():
 p=out/'browser'/name
 with zipfile.ZipFile(p) as z:
  assert z.testzip() is None;files={n:z.read(n) for n in z.namelist()}
  for n,sha in json.loads(files['checksums.json']).items():assert digest(files[n])==sha,(name,n)
  assert files['layout.json']==canonical_files['layout.json'];assert files['collision.json']==canonical_files['collision.json'];assert files['clean-guide.png']==canonical_files['clean-guide.png']
  if kind!='layout':
   actual=Image.open(io.BytesIO(files['terrain.png']));assert np.array_equal(np.array(expected),np.array(actual));prov=json.loads(files['terrain-provenance.json']);assert prov['evaluation_id']==a['evaluation_id'];assert prov['production_approved']==(kind=='production')
   assert any(b==raw for b in files.values()),'original source missing from ZIP'
  zip_results.append(dict(kind=kind,path=str(p.relative_to(root)),sha256=digest(p.read_bytes()),members=len(files),checksums=True,collision_unchanged=True,direct_source_pixel_replay=kind!='layout'))
# Exact browser pixels vs direct source replay; only the explicitly separate technical actor is excluded.
bg=tuple(map(int,re.findall(r'\d+',report['sampling']['background'])));composite=Image.new('RGBA',expected.size,(*bg,255));composite.alpha_composite(expected.convert('RGBA'));screen=Image.open(out/'browser/warm-gameplay-native.png').convert('RGB');assert screen.size==expected.size
screen_arr=np.array(screen);expected_arr=np.array(composite.convert('RGB'));delta=np.any(screen_arr!=expected_arr,axis=2);p=layout['projection'];col,row=[v+.5 for v in report['sampling']['actor']];x=p['origin_px'][0]+col*p['column_basis_px'][0]+row*p['row_basis_px'][0];y=p['origin_px'][1]+col*p['column_basis_px'][1]+row*p['row_basis_px'][1];mask=np.zeros(delta.shape,bool);mask[int(y)-24:int(y)+15,int(x)-24:int(x)+25]=True;assert not delta[~mask].any();assert delta[mask].any()
# New iteration receipts/requests were real and immutable, complete source retention.
db=sqlite3.connect('file:'+str(root/'data/generation.sqlite3')+'?mode=ro',uri=True);db.row_factory=sqlite3.Row
jobs=[dict(r) for r in db.execute('select id,reserve,record from jobs')];reviews=[dict(r) for r in db.execute('select id,reserve,record from reviews')];assert len(jobs)==5
iterations=[]
for label,s in zip(('warm','fantasy'),w['styles']):
 d=out/label;j=json.loads(next(x['record'] for x in jobs if x['id']==s['job_id']));rec=json.loads((d/'receipt.json').read_bytes());assert rec['request_sha256']==digest(canonical(j['request']));assert rec['prediction_id']==s['prediction_id'];assert j['binding']['layout_revision']==w['frozen']['revision'];assert j['binding']['style_spec_id']==s['style_spec_id'];assert set(j['request'])=={'prompt','image_urls','output_format'};assert len(j['request']['image_urls'])==3
 assert (root/'data/terrain'/s['source_candidate_id']/'source.png').read_bytes()==(d/'source.png').read_bytes()
 source=Image.open(d/'source.png');iterations.append(dict(style=label,job_id=s['job_id'],quote_id=s['quote_id'],prediction_id=s['prediction_id'],source_candidate_id=s['source_candidate_id'],candidate_id=s['candidate_id'],evaluation_id=s['evaluation_id'],source_size=source.size,source_sha256=digest((d/'source.png').read_bytes()),request_sha256=rec['request_sha256'],receipt_sha256=digest((d/'receipt.json').read_bytes()),quoted_hold_usd=str(Decimal(j['reserved_microusd'])/1000000),registration_max_px=max(f['max_residual_px'] for f in s['registration']['measurements']['fits']),stop_reason=s['stop_reason']))
 if s.get('evaluation_id'):
  eid=s['evaluation_id'];ed=c.get('/api/evaluations/'+eid);ed.raise_for_status();ev=ed.json();assert ev['gate']['production_approved'];rd=root/'data/reviews'/eid
  for name in ('receipt.json','metadata.json','intent.json'):(d/('review-'+name)).write_bytes((rd/name).read_bytes())
  rb=ev['result']['review_binding'];assert digest((rd/'request.json').read_bytes())==rb['request_sha256'];assert digest((rd/'receipt.json').read_bytes())==ev['result']['receipt_sha256'];(d/'review-request-binding.json').write_bytes(canonical(dict(request_sha256=rb['request_sha256'],path=str((rd/'request.json').relative_to(root)),max_tokens=json.loads((rd/'request.json').read_bytes())['max_tokens'])))
usage=[];unknown=[]
for r in reviews:
 p=root/'data/reviews'/r['id']/'receipt.json'
 if p.exists():
  receipt=json.loads(p.read_bytes());usage.append(dict(id=r['id'],reported_cost_usd=str(receipt.get('usage',{}).get('cost')),held_usd=str(Decimal(r['reserve'])/1000000)))
 else:unknown.append(dict(id=r['id'],held_usd=str(Decimal(r['reserve'])/1000000)))
assert any(x['held_usd']=='0.794112' for x in unknown)
status=c.get('/api/generation/status').json();reviewer=c.get('/api/reviewer/config').json();assert not status['enabled'] and not reviewer['enabled'];assert Decimal(status['reserved_usd'])==Decimal(sum(r['reserve'] for r in jobs+reviews))/1000000
known=sum((Decimal(u['reported_cost_usd']) for u in usage if u['reported_cost_usd']!='None'),Decimal(0))
result=dict(batch=w['id'],result='VERIFIED; warm automatic gate pass, fantasy blocked, user acceptance pending',old_run_unchanged=True,iterations=iterations,zips=zip_results,pixel_replay=dict(width=expected.width,height=expected.height,browser_non_actor_differences=int(delta[~mask].sum()),actor_pixel_differences=int(delta[mask].sum()),collision_sha256=digest(canonical_files['collision.json'])),budget=status,reviewer=reviewer,known_review_usage_usd=str(known),review_usage=usage,unknown_review_holds=unknown,remaining_conservative_usd=str(Decimal('10')-Decimal(status['reserved_usd'])),held_eur_conservative_plus_fees=str(Decimal(status['reserved_usd'])*Decimal('1.25')+Decimal('2.5')),note='Reported usage is contained within holds, never added. Image prices are estimates not invoices. No holds released.')
(out/'verification.json').write_bytes(json.dumps(result,indent=2).encode())
# Before/after is fresh planned guide vs genuine registered final, both native; no false repair claim.
board=Image.new('RGB',(1440,430),'#10191e');draw=ImageDraw.Draw(board);draw.text((10,10),'BEFORE: new canonical guide / 720x384 native',fill='white');draw.text((730,10),'AFTER: warm registered generated terrain / native / user acceptance pending',fill='white');guide=Image.open(io.BytesIO(canonical_files['clean-guide.png']));board.paste(guide,(0,40),guide);board.paste(expected,(720,40),expected);board.save(out/'before-after-native.png')
print(json.dumps(result,indent=2))
