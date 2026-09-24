"""Local setup and free preflight only. No generation confirm or paid review."""
import base64,json,sys
from pathlib import Path
import httpx
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from artifacts import canonical,digest
ROOT=Path(__file__).resolve().parents[1];out=ROOT/'evidence/overnight-two-styles';base='http://127.0.0.1:59661'
c=httpx.Client(base_url=base,timeout=180)
def save(path,obj):path.write_bytes(canonical(obj));return obj
def post(path,obj):
 r=c.post(path,json=obj);r.raise_for_status();return r.json()
status=c.get('/api/generation/status').json();save(out/'budget-before.json',status)
old=c.get('/api/auto-repair/8e96cc6e6289256aead3f64d8ea86bfc132d7c47dee27898749bf43428cc1577').json();save(out/'old-run-before.json',old)
for label in ('common','second-seed-free-only'):
 p=json.loads((out/label/'request.json').read_bytes());created=post('/api/layouts',p);assert created['validation']['valid'];read=c.get('/api/layouts/'+created['revision']).json();assert read==created;save(out/label/'api-layout.json',read)
rev=json.loads((out/'common/api-layout.json').read_bytes())['revision'];style_ids=[]
for label in ('warm','fantasy'):
 d=out/label;raw=(d/'reference-decoded.png').read_bytes();ref=post('/api/styles',dict(png_base64=base64.b64encode(raw).decode(),role='style_only'));assert c.get('/api/styles/'+ref['id']).json()==ref;assert c.get('/api/styles/'+ref['id']+'/source.png').content==raw;save(d/'reference-api.json',ref)
 warm=label=='warm';material=dict(path=('Warm luminous cream paving, broad calm slabs, restrained mint seam accents, sparse crisp dark seams, coherent pixel clusters.' if warm else 'Earthy warm ochre and tan irregular cobblestones, substantial distinct clusters, muted amber highlights and dark brown joint outlines, medieval fantasy plaza, not asphalt.'),grass=('Flat low restrained mint-green turf, sparse coherent clusters, no bushes or raised foliage. Mint paving accents in reference inform palette only; this is a deliberate ground-cover interpretation.' if warm else 'Flat low olive and moss-green grass with deep olive outline clusters, restrained warm highlights, no shrubs, trunks or upright leaves; clear walkable surface.'),soil=('Warm quiet compacted sandy ochre earth in soil regions, broad sparse clusters. Interpret warm stone palette as flat soil, no copied objects or geometry.' if warm else 'Warm earthy brown compacted soil, low-contrast ochre clusters, no gravel noise or raised stones. Palette interpretation, not copied geometry.'))
 crop=json.loads((out/'reference-review.json').read_bytes())['approved_material_crops'][label]['path']
 spec=dict(version=1,prompt=('Bright warm cream-and-mint coherent isometric pixel-cluster ground.' if warm else 'Dark outlined warm earthy fantasy isometric pixel-cluster ground.')+' Image1 is the sole geometry authority. Preserve the exact full diamond, all material boundaries, 2:1 projection and dark surround; paint every planned pixel without cropping, changing scale or inventing geometry. Ground only, flat. Following image is STYLE ONLY: never copy its scene or objects. The last image is a paving material crop, not a layout. Follow each material instruction explicitly; SAME planned material regions. No changes to canonical routes or clearances.',avoid=['figures','buildings','trees and bushes','height, steps or bridges','HUD, lettering, logos and watermark','copied reference composition','asphalt or traffic markings','speckled noise and smooth painterly gradients','material spill across boundaries'],materials={k:dict(prompt=v,reference_ids=[ref['id']] if k=='path' else []) for k,v in material.items()},references=[dict(reference_id=ref['id'],role='style_only',material=None,crop=None),dict(reference_id=ref['id'],role='material_only',material='path',crop=crop)])
 save(d/'style-spec-request.json',spec);s=post('/api/style-specs',spec);assert c.get('/api/style-specs/'+s['id']).json()==s;save(d/'style-spec.json',s);style_ids.append(s['id'])
 q=post('/api/generation/quote',dict(revision=rev,style_spec_id=s['id']));assert c.get('/api/generation/quotes/'+q['id']).json()==q;save(d/'free-quote.json',q)
pre=post('/api/reviewer/preflight',{});save(out/'free-reviewer-preflight.json',pre)
body=dict(revision=rev,style_spec_ids=style_ids,density=1,confirm_paid=True);save(out/'start-request.json',body)
print(json.dumps(dict(status=status,revision=rev,styles=style_ids,reviewer_preflight=pre),indent=2))
