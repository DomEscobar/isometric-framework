"""Read-only verification of actual browser downloads, immutable bindings and central accounting."""
import io,json,sys,zipfile
from pathlib import Path
from decimal import Decimal
import numpy as np
from PIL import Image
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app import create_app
from fastapi.testclient import TestClient
from artifacts import canonical,digest
from terrain import render_original
root=Path(__file__).resolve().parents[1];out=root/'evidence/strict-style';app=create_app();c=TestClient(app)
report=json.loads((out/'browser/browser-report.json').read_bytes())
zip_path=out/'browser'/report['download'];raw=zip_path.read_bytes()
with zipfile.ZipFile(io.BytesIO(raw)) as z:
    assert z.testzip() is None
    hashes=json.loads(z.read('checksums.json'))
    for name,sha in hashes.items():assert digest(z.read(name))==sha,name
    prov=json.loads(z.read('terrain-provenance.json'));record=json.loads(z.read('candidate.json'));layout=json.loads(z.read('layout.json'))
    assert prov['production_approved'] is False and prov['export_mode']=='diagnostic'
    assert record['id']=='f3bdc310f809cf7a6b95015cc16af343e337a192e1865432ac530eb2b02fa96a'
    assert 'style_spec_id' not in record.get('provider_origin',{}),'never rewrite historical style generation claim'
    source=z.read('sources/original.png');replay=render_original(layout,record,source,1)
    assert np.array_equal(np.array(replay),np.array(Image.open(io.BytesIO(z.read('terrain.png')))))
    assert digest(z.read('terrain.png'))=='c8619f78c9a2c8356c7791d763400e884e537ee6e8d51616b7e2716b554df211'
    ev=json.loads(z.read('evaluation.json'))
    assert ev['id']==report['evaluation'] and ev['binding']['style_spec_id']==report['style']
    assert not ev['gate']['production_approved']
    for e in ev['binding']['evidence']:assert digest(z.read('review-inputs/'+e['id']+'.png'))==e['sha256']
    count=len(z.namelist())
current=c.get('/api/evaluations/'+report['evaluation']);assert current.status_code==200
review=current.json();(out/'evaluation-final-readback.json').write_bytes(canonical(review))
assert review['result']['actual_model']=='google/gemini-3.8-flash'
assert {k:v['verdict'] for k,v in review['result']['decision']['criteria'].items()}=={'layout_fidelity':'pass','materials':'fail','pixel_style':'pass','walkable_clearance':'fail'}
intent=json.loads((root/'data/reviews'/report['evaluation']/'intent.json').read_bytes())
for i in intent['inputs']:assert i['sha256']==i['review_sha256'] and i['source_size']==i['review_size']
status=c.get('/api/generation/status').json()
with app.state.generation.connect() as db:
    jobs=[{'id':r['id'],'reserve':r['reserve']} for r in db.execute('SELECT id,reserve FROM jobs')]
    reviews=[{'id':r['id'],'reserve':r['reserve']} for r in db.execute('SELECT id,reserve FROM reviews')]
assert len(jobs)==2 and len(reviews)==4
held=sum(x['reserve'] for x in jobs+reviews)
assert Decimal(status['reserved_usd'])==Decimal(held)/1000000
remaining=Decimal(status['total_budget_usd'])-Decimal(held)/1000000
accounting=dict(status=status,jobs=jobs,reviews=reviews,conservative_remaining_usd=str(remaining),new_review_reported_cost=review['result']['usage']['cost'],note='Actual known usage is included in conservative holds, never added twice. No prior liability released.')
(out/'accounting-final.json').write_bytes(canonical(accounting))
url=f"/api/terrain/{record['id']}/download?revision={record['layout_revision']}&density=1&style_spec_id={report['style']}&evaluation_id={report['evaluation']}&mode=production"
assert c.get(url).status_code==409
for directory in ('layout-regression','candidate-regression','urban-regression','forest-regression'):
    name='candidate-browser-report.json' if directory=='candidate-regression' else 'browser-report.json'
    browser=json.loads((out/directory/name).read_bytes())
    assert browser['errors']==[]
    if 'result' in browser:assert browser['result']=='PASS'
result=dict(result='PASS',download=str(zip_path),zip_sha256=digest(raw),members=count,verified_checksums=len(hashes),source_sha256=digest(source),final_sha256=prov['terrain_sha256'],evaluation_id=report['evaluation'],style_spec_id=report['style'],generation_claim_unchanged=True,exact_review_inputs=len(intent['inputs']),production_http=409,user_acceptance='pending',accounting=accounting,screenshots={str(p.relative_to(root)):digest(p.read_bytes()) for p in sorted((out/'browser').glob('*.png'))})
(out/'verification-final.json').write_bytes(canonical(result));print(json.dumps(result,indent=2))
