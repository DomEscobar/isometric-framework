"""Verify exact browser-downloaded genuine pilot ZIP and fresh central accounting."""
from pathlib import Path
import sys,json,zipfile,io,sqlite3
from decimal import Decimal
import numpy as np,httpx
from PIL import Image,ImageDraw
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from artifacts import digest,canonical
from terrain import render_original
out=Path('evidence/paid-pilot');browser=json.loads((out/'browser/browser-report.json').read_bytes());zip_path=out/'browser'/browser['download'];raw=zip_path.read_bytes();z=zipfile.ZipFile(io.BytesIO(raw));assert z.testzip() is None
checks=json.loads(z.read('checksums.json'))
for name,sha in checks.items():assert digest(z.read(name))==sha
layout=json.loads(z.read('layout.json'));candidate=json.loads(z.read('candidate.json'));provenance=json.loads(z.read('terrain-provenance.json'));review=json.loads(z.read('review.json'));request=json.loads(z.read('generation/request-provenance.json'))
assert z.read('sources/original.png')==(out/'original.png').read_bytes()
assert z.read('sources/style-only.png')==(out/'style-only.png').read_bytes()
assert digest(canonical(layout))==candidate['layout_revision']
assert layout==json.loads((out/'layout-response.json').read_bytes())['layout']
expected=render_original(layout,candidate,z.read('sources/original.png'),1);exported=Image.open(io.BytesIO(z.read('terrain.png'))).convert('RGBA')
assert np.array_equal(np.array(expected),np.array(exported))
assert digest(z.read('terrain.png'))==review['reviewed_terrain_sha256']
assert not provenance['production_approved'] and not review['production_approved']
assert request['prediction_id']=='9e033c5172104cc08e2a302b7a1e5883'
(out/'terrain.png').write_bytes(z.read('terrain.png'));(out/'manifest.json').write_bytes(z.read('manifest.json'));(out/'terrain-provenance.json').write_bytes(z.read('terrain-provenance.json'))
# Actual browser pixels are output pixels plus the separately rendered technical actor.
screen=np.array(Image.open(out/'browser/canvas-native.png').convert('RGB'));art=np.array(exported.convert('RGB'));different=np.any(screen!=art,axis=2);yy,xx=np.where(different)
p=layout['projection'];c,r=browser['sampling']['actor'];x=p['origin_px'][0]+(c+.5)*p['column_basis_px'][0]+(r+.5)*p['row_basis_px'][0];y=p['origin_px'][1]+(c+.5)*p['column_basis_px'][1]+(r+.5)*p['row_basis_px'][1]
assert all((abs(xx-x)<=22)&(yy>=y-23)&(yy<=y+13)), 'browser differs outside actor footprint/head'
with httpx.Client(base_url='http://127.0.0.1:33009',timeout=60) as client:
 status=client.get('/api/generation/status').json()
 assert client.get('/api/terrain/'+candidate['id']).json()==candidate
 assert client.get('/api/terrain/'+candidate['id']+'/review').json()==review
 assert client.get('/api/layouts/'+candidate['layout_revision']).json()['layout']==layout
 assert client.get('/api/terrain/'+candidate['id']+'/source.png').content==z.read('sources/original.png')
 assert client.get('/api/terrain/'+candidate['id']+'/download',params={'revision':candidate['layout_revision'],'density':1}).content==raw
with sqlite3.connect('data/generation.sqlite3') as db:
 jobs=[json.loads(r[0]) for r in db.execute('select record from jobs')];reviews=[json.loads(r[0]) for r in db.execute('select record from reviews')]
assert len(jobs)==1 and jobs[0]['status']=='candidate_ready'
assert len(reviews)==2
actual_review=Decimal(str(review['model_review']['response']['usage']['cost']));gen_quote=Decimal(str(request['exact_quote']['price']))
accounting=dict(status_readback=status,generation_completed=len(jobs),generation_quote_usd=str(gen_quote),generation_billed_cost='not exposed by prediction endpoint; quote retained conservatively, NOT asserted as reconciled invoice',review_reported_cost_usd=str(actual_review),known_review_cost_plus_generation_quote_usd=str(actual_review+gen_quote),central_held_total_usd=status['reserved_usd'],held_includes_known_charges=True,unspent_headroom_under_conservative_hold_usd=str(Decimal(status['total_budget_usd'])-Decimal(status['reserved_usd'])),unreconciled_review_attempt={'id':'paid-pilot-01','http_status':401,'held_usd':'0.794112','actual_cost':'no model response; unverified billing; full liability retained'},successful_review={'id':review['model_review']['response']['id'],'held_usd':'0.794112','reported_cost_usd':str(actual_review),'reservation_not_released':True},outstanding_remote_generation_jobs=[],automatic_paid_retries=0)
(out/'accounting-final.json').write_bytes(canonical(accounting))
summary=dict(zip=str(zip_path),zip_sha256=digest(raw),zip_bytes=len(raw),zip_members=len(z.namelist()),checksums_verified=len(checks),candidate_id=candidate['id'],revision=candidate['layout_revision'],source_sha256=digest(z.read('sources/original.png')),terrain_sha256=digest(z.read('terrain.png')),terrain_size=list(exported.size),request_sha256=request['request_sha256'],prediction_id=request['prediction_id'],review_id=review['id'],source_size=list(Image.open(io.BytesIO(z.read('sources/original.png'))).size),registration=candidate['processing_registration'],browser_sampling=browser['sampling'],browser_difference_pixels=int(different.sum()),browser_differences_confined_to_technical_actor=True,navigation=browser['navigation'],accounting=accounting,verdict={'technical':'pass','semantic':'needs_attention','visual':'secondary_pass_parent_pending','production_approved':False},screenshots={n:digest((out/n).read_bytes()) for n in ['browser/play-scale-clean.png','browser/playable-diagnostics.png','guide-vs-registered.png','browser/original-vs-guide.png']})
(out/'verification-final.json').write_bytes(canonical(summary));print(json.dumps(summary,indent=2))
