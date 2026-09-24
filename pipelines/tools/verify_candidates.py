"""Verify exact browser candidate ZIP, not a replacement export. No paid calls."""
import io,json,os,sys,zipfile,hashlib,urllib.request,subprocess
from pathlib import Path
import numpy as np
from PIL import Image
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from artifacts import canonical,digest
import verify_exports
BASE=os.environ.get('BASE_URL','http://127.0.0.1:48493')
BROWSER=ROOT/os.environ.get('CANDIDATE_EVIDENCE','evidence/candidate-browser-final')
OUT=ROOT/'evidence/milestone-2-verification'
OUT.mkdir(parents=True,exist_ok=True)

def get(route):return urllib.request.urlopen(BASE+route).read()

report=json.loads((BROWSER/'candidate-browser-report.json').read_bytes())
raw=(BROWSER/report['download']).read_bytes()
with zipfile.ZipFile(io.BytesIO(raw)) as z:
    assert z.testzip() is None
    checks=json.loads(z.read('checksums.json'))
    assert set(checks)==set(z.namelist())-{'checksums.json'}
    for n,sha in checks.items():assert digest(z.read(n))==sha,n
    record=json.loads(z.read('candidate.json'))
    provenance=json.loads(z.read('terrain-provenance.json'))
    original=z.read('sources/original.png')
    assert original==(BROWSER/'TECHNICAL-FIXTURE-NOT-ART.png').read_bytes()
    assert digest(original)==record['source_sha256']==provenance['source_sha256']
    assert digest(z.read('clean-guide.png'))==record['guide_sha256']
    assert record['production_approved'] is False
    assert record['registration']['image_alignment']=='unverified'
    assert record['image_checks']['semantic_verdict']=='unverified'
    assert provenance['status']=='needs_attention' and provenance['visual_review']=='unreviewed'
    target=provenance['processing']['output_size']
    expected=Image.open(io.BytesIO(original)).convert('RGBA').resize(target,Image.Resampling.NEAREST)
    final=Image.open(io.BytesIO(z.read('terrain.png'))).convert('RGBA')
    assert np.array_equal(np.array(expected),np.array(final))
    assert provenance['processing']['from_original'] is True
    layout=json.loads(z.read('layout.json'));p=layout['projection'];out=provenance['output_projection']
    for c in range(layout['width']):
        for r in range(layout['height']):
            for i in (0,1):
                a=(p['origin_px'][i]+(c+.5)*p['column_basis_px'][i]+(r+.5)*p['row_basis_px'][i])/p['density']
                b=(out['origin_px'][i]+(c+.5)*out['column_basis_px'][i]+(r+.5)*out['row_basis_px'][i])/out['density']
                assert a==b
    assert raw==get(f"/api/terrain/{record['id']}/download?revision={record['layout_revision']}&density=2")
    members=len(z.namelist())
status=json.loads(get('/api/generation/status'))
assert status['enabled'] is False and status['attempts']==0 and status['reserved_usd']=='0'
quote_summary=json.loads(report['quote'])
quote=json.loads(get('/api/generation/quotes/'+quote_summary['id']))
assert quote['quote']['currency']=='USD'
assert 'image_urls' in quote['schema']['required']
(OUT/'live-schema-price.json').write_bytes(canonical(quote))
(OUT/'zero-spend-status.json').write_bytes(canonical(status))
verify_exports.BASE=BASE
verify_exports.OUT=OUT/'three-layouts'
# Original verifier also independently checks its preserved browser-03 ZIP.
verify_exports.main()
regression=ROOT/'evidence/regression-browser-final'
r=json.loads((regression/'browser-report.json').read_bytes())
reg=verify_exports.verify_zip((regression/r['download']).read_bytes())
assert reg['revision']==r['revision']
summary=dict(candidate_zip=str(BROWSER/report['download']),sha256=digest(raw),bytes=len(raw),members=members,
             original_sha256=digest(original),output_size=target,production_approved=False,
             semantic_verdict='unverified',fixture='TECHNICAL GUIDE ONLY; NOT PRODUCTION ART',
             same_world_projection=True,direct_original_nearest_replay=True,regression_browser=reg,
             provider=dict(live_metadata=True,paid_calls=0,attempts=status['attempts'],budget_usd=status['total_budget_usd'],quote_usd=quote['quote']['price']),
             screenshots={str(p.relative_to(ROOT)):digest(p.read_bytes()) for p in sorted(BROWSER.glob('*.png'))})
(OUT/'verification.json').write_text(json.dumps(summary,indent=2))
print(json.dumps(summary,indent=2))
