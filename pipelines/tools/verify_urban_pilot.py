"""Read-only exact downloaded urban ZIP, pixels, lineage and shared ledger verification."""
from pathlib import Path
import os,sys,json,zipfile,io,sqlite3,re
from decimal import Decimal
import numpy as np,httpx
from PIL import Image
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from artifacts import canonical,digest,export_files
from terrain import render_original
out=Path(os.environ.get('EVIDENCE','evidence/urban-pilot'));bd=Path(os.environ.get('BROWSER_EVIDENCE',str(out/'browser-final')));br=json.loads((bd/'browser-report.json').read_bytes());zp=bd/br['download'];raw=zp.read_bytes();z=zipfile.ZipFile(io.BytesIO(raw));assert z.testzip() is None
checks=json.loads(z.read('checksums.json'))
for n,h in checks.items():assert digest(z.read(n))==h
l=json.loads(z.read('layout.json'));r=json.loads(z.read('candidate.json'));review=json.loads(z.read('review.json'));req=json.loads(z.read('generation/request-provenance.json'))
assert digest(canonical(l))==r['layout_revision'];assert l==json.loads((out/'layout-response.json').read_bytes())['layout']
assert z.read('sources/original.png')==(out/'original.png').read_bytes();assert z.read('sources/style-only.png')==(out/'style-only.png').read_bytes()
lineage=json.loads((out/'style-lineage.json').read_bytes());assert digest((out/'style-original.jpg').read_bytes())==lineage['original_sha256']
assert Image.open(out/'style-original.jpg').convert('RGB').tobytes()==Image.open(out/'style-only.png').tobytes()
expected=render_original(l,r,z.read('sources/original.png'),1);im=Image.open(io.BytesIO(z.read('terrain.png'))).convert('RGBA');assert np.array_equal(np.array(expected),np.array(im))
assert digest(z.read('terrain.png'))==review['reviewed_terrain_sha256'];assert req['prediction_id']==r['provider_origin']['prediction_id'];assert not review['production_approved']
(out/'terrain.png').write_bytes(z.read('terrain.png'));(out/'terrain-provenance.json').write_bytes(z.read('terrain-provenance.json'))
# Compare actual composited browser RGB against exported RGBA over independently read CSS background.
bg=br['sampling']['stageBackground'];rgb=tuple(map(int,re.findall(r'\d+',bg)));assert len(rgb)==3
assert br['sampling']['canvasBackground']=='rgba(0, 0, 0, 0)'
composite=Image.new('RGBA',im.size,(*rgb,255));composite.alpha_composite(im);a=np.array(composite.convert('RGB'));b=np.array(Image.open(bd/'canvas-native.png').convert('RGB'));assert a.shape==b.shape
diff=np.any(a!=b,axis=2);yy,xx=np.where(diff);p=l['projection'];cx,cy=br['sampling']['actor'];x=p['origin_px'][0]+(cx+.5)*p['column_basis_px'][0]+(cy+.5)*p['row_basis_px'][0];y=p['origin_px'][1]+(cx+.5)*p['column_basis_px'][1]+(cy+.5)*p['row_basis_px'][1]
assert np.all((abs(xx-x)<=22)&(yy>=y-23)&(yy<=y+13)), 'non-actor pixel drift'
# Every canonical planned pixel remains opaque; transparent margins are outside the map.
guide=np.array(Image.open(io.BytesIO(z.read('clean-guide.png'))).convert('RGBA'));assert not np.any((guide[:,:,3]>0)&(np.array(im)[:,:,3]<255))
# Previous paid forest guide/export semantics are unchanged.
forest=json.loads(Path('evidence/paid-pilot/layout-response.json').read_bytes());assert export_files(forest['layout'])['clean-guide.png']==Path('evidence/paid-pilot/guide.png').read_bytes()
with httpx.Client(base_url=os.environ.get('BASE_URL','http://127.0.0.1:53047'),timeout=60) as c:
 status=c.get('/api/generation/status').json();assert c.get('/api/terrain/'+r['id']).json()==r;assert c.get('/api/terrain/'+r['id']+'/review').json()==review
 assert c.get('/api/terrain/'+r['id']+'/download',params={'revision':r['layout_revision'],'density':1}).content==raw
 assert c.get('/api/layouts/'+r['layout_revision']).json()['layout']==l
 # Independently replay density 2 directly from retained original, never chained from d1.
 z2=zipfile.ZipFile(io.BytesIO(c.get('/api/terrain/'+r['id']+'/download',params={'revision':r['layout_revision'],'density':2}).content))
 assert np.array_equal(np.array(render_original(l,r,z.read('sources/original.png'),2)),np.array(Image.open(io.BytesIO(z2.read('terrain.png')))))
with sqlite3.connect('data/generation.sqlite3') as db:
 ledger={t:[{'id':i,'reserve_microusd':v,'status':json.loads(d).get('status')} for i,v,d in db.execute('select id,reserve,record from '+t)] for t in ('jobs','reviews')}
assert len(ledger['jobs'])==2 and len(ledger['reviews'])==3
before=json.loads((out/'ledger-before.json').read_bytes())
for t in before:
 for entry in before[t]:assert entry in ledger[t]
held=sum(e['reserve_microusd'] for entries in ledger.values() for e in entries);assert Decimal(held)/1000000==Decimal(status['reserved_usd']);assert held<=10000000
accounting={'status_readback':status,'ledger':ledger,'prior_liabilities_preserved':True,'central_held_total_usd':str(Decimal(held)/1000000),'remaining_under_holds_usd':str(Decimal(10)-Decimal(held)/1000000),'urban_generation_quote_usd':str(req['exact_quote']['price']),'urban_review_reported_cost_usd':str(review['model_review']['response']['usage']['cost']),'known_charges_included_in_holds':True,'billing_caveat':'Generation quote is not invoice; prior HTTP401 liability and unused review reservations retained; no reconciliation or automatic release.'}
(out/'accounting-final.json').write_bytes(canonical(accounting))
summary={'technical_verdict':'pass','semantic_verdict':'needs_attention','visual_verdict':'secondary_pass_parent_pending','production_approved':False,'zip':str(zp.resolve()),'zip_sha256':digest(raw),'zip_members':len(z.namelist()),'checksums_verified':len(checks),'source_sha256':r['source_sha256'],'terrain_sha256':digest(z.read('terrain.png')),'candidate_id':r['id'],'source_candidate_id':r['parent_candidate_id'],'layout_revision':r['layout_revision'],'prediction_id':req['prediction_id'],'request_sha256':req['request_sha256'],'review_id':review['id'],'sampling':br['sampling'],'browser_pixel_differences':int(diff.sum()),'differences_confined_to_separate_technical_actor':True,'RGBA_compositing_background':bg,'transparent_margin_pixels':int((np.array(im)[:,:,3]==0).sum()),'transparent_pixels_inside_canonical_map':0,'direct_original_density_1_and_2_replay':True,'previous_forest_guide_unchanged':True,'navigation':br['navigation'],'accounting':accounting,'style_lineage':lineage}
(out/'verification-final.json').write_bytes(canonical(summary));print(json.dumps(summary,indent=2))
