"""Verify retained real run, exact browser ZIP and ledger WITHOUT paid calls."""
import sys,io,json,zipfile
from pathlib import Path
from decimal import Decimal
import numpy as np
from PIL import Image,ImageDraw
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app import create_app
from artifacts import canonical,digest
from terrain import render_original
root=Path(__file__).resolve().parents[1];out=root/'evidence/auto-repair';app=create_app();s=app.state.auto_repair;g=app.state.generation
rid=(out/'run-id.txt').read_text();w=s.get(rid);assert w['status']!='running'
zip_path=out/'verification/diagnostic-candidate-f3bdc310f809-d1.zip'
with zipfile.ZipFile(zip_path) as z:
    assert z.testzip() is None
    files={n:z.read(n) for n in z.namelist()}
    for name,sha in json.loads(files['checksums.json']).items():assert digest(files[name])==sha,name
    prov=json.loads(files['terrain-provenance.json']);assert prov['production_approved'] is False
    assert prov['evaluation_id']==w['best_evaluation_id']
    r=json.loads((g.root/'terrain'/w['best_candidate_id']/'record.json').read_bytes());source=(g.root/'terrain'/r['id']/'source.png').read_bytes()
    layout=json.loads(files['layout.json']);replay=render_original(layout,r,source,w['frozen']['density'])
    assert np.array_equal(np.array(replay),np.array(Image.open(io.BytesIO(files['terrain.png']))))
    before=Image.open(io.BytesIO(files['terrain.png'])).convert('RGBA')
    (out/'best-final.png').write_bytes(files['terrain.png'])
    assert digest(canonical(layout))==w['frozen']['revision']
job_evidence=[]
for a in w['iterations']:
    if not a.get('job_id'):continue
    j=g.get(a['job_id']);receipt=(g.root/(j['id']+'.receipt.json')).read_bytes();q=g.get_quote(j['quote_id'])
    assert len(j['request']['image_urls'])==6
    assert set(j['request'])=={'image_urls','prompt','output_format'}
    assert digest(canonical(j['request']))==j['request_sha256']
    correction=j['binding']['style_references'][-1];assert correction['role']=='correction_target'
    assert correction['reference_id']==a['input_candidate_id']
    source_path=g.root/'terrain'/a['candidate_id']/'source.png'
    assert source_path.read_bytes()==(out/'verification/latest-original.png').read_bytes()
    job_evidence.append(dict(iteration_id=a['id'],job_id=j['id'],prediction_id=j['prediction_id'],request_sha256=j['request_sha256'],receipt_sha256=digest(receipt),source_sha256=digest(source_path.read_bytes()),reserved_microusd=j['reserved_microusd'],exact_quote=j['exact_quote']))
# Comparison is diagnostic only, NEVER a persisted candidate or a gate input.
a=w['iterations'][-1];latest=json.loads((g.root/'terrain'/w['latest_candidate_id']/'record.json').read_bytes());raw=(g.root/'terrain'/latest['id']/'source.png').read_bytes()
registration=a.get('registration',{})
if registration.get('scale'):
    diagnostic={**latest,'processing_registration':{'scale':registration['scale'],'translation':registration['translation']}}
    after=render_original(layout,diagnostic,raw,w['frozen']['density']).convert('RGBA')
    board=Image.new('RGB',(before.width*2,before.height+64),'#18212a');board.paste(before,(0,64),before);board.paste(after,(before.width,64),after);d=ImageDraw.Draw(board)
    d.text((12,8),'BEFORE / retained best / native 48x24 tiles',fill='white')
    d.text((before.width+12,8),'AFTER SOURCE / FAILED FIT DIAGNOSTIC - NOT GAMEPLAY',fill='white')
    d.text((before.width+12,28),'One measured scalar only; residual exceeds frozen 2.5px limit.',fill='white')
    d.text((12,28),'Both unapproved. No manual candidate was fed back into the run.',fill='white')
    board.save(out/'before-after-diagnostic.png')
# All reservations remain authoritative; reported usage is a subset, not extra spend.
with g.connect() as db:
    jobs=[dict(r) for r in db.execute('SELECT id,reserve,record FROM jobs')];reviews=[dict(r) for r in db.execute('SELECT id,reserve,record FROM reviews')]
usage=[]
for r in reviews:
    receipt=g.root/'reviews'/r['id']/'receipt.json'
    if receipt.exists():
        response=json.loads(receipt.read_bytes());cost=response.get('usage',{}).get('cost')
        usage.append(dict(id=r['id'],reported_cost_usd=str(cost) if cost is not None else None,reserve_microusd=r['reserve'],receipt_sha256=digest(receipt.read_bytes())))
known=sum((Decimal(x['reported_cost_usd']) for x in usage if x['reported_cost_usd'] is not None),Decimal(0))
report=dict(run_id=rid,status=w['status'],stop_reason=w['stop_reason'],iterations=len(w['iterations']),best_candidate_id=w['best_candidate_id'],latest_candidate_id=w['latest_candidate_id'],job_evidence=job_evidence,zip=dict(path=str(zip_path.relative_to(root)),sha256=digest(zip_path.read_bytes()),files=len(files),checksums='all verified',direct_original_pixel_replay=True),accounting=g.status(),review_reported_usage_usd=str(known),review_usage_records=usage,review_holds_without_receipt=[dict(id=r['id'],reserved_microusd=r['reserve']) for r in reviews if not (g.root/'reviews'/r['id']/'receipt.json').exists()],remaining_conservative_usd=str(Decimal(g.policy['total_usd'])-Decimal(g.status()['reserved_usd'])),unsettled_generation_quote_total_usd=str(Decimal(sum(r['reserve'] for r in jobs))/1000000),note='Held totals INCLUDE known/reported costs; do not add them. Provider quotes are not billing receipts. No holds released. Latest is unregistered; diagnostic candidate ZIP HTTP422; production HTTP409. No new final-density paid review was purchased after registration failed.')
(out/'verification.json').write_bytes(canonical(report));(out/'run-final.json').write_bytes(canonical(w))
print(json.dumps(report,indent=2))
