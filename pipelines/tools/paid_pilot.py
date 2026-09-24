"""Operator-driven pilot. Separate prepare/confirm/poll stages; never retries paid POST."""
import sys,json,base64,hashlib
from pathlib import Path
import httpx
root=Path(__file__).resolve().parents[1];out=root/'evidence/paid-pilot';out.mkdir(exist_ok=True)
c=httpx.Client(base_url='http://127.0.0.1:33009',timeout=180)
def save(name,obj): (out/name).write_text(json.dumps(obj,indent=2));return obj
def api(method,path,body=None):
 r=c.request(method,path,json=body);r.raise_for_status();return r.json()
if sys.argv[1]=='prepare':
 status=save('status-before.json',api('GET','/api/generation/status'));assert status['attempts']==0
 req={'width':16,'height':14,'seed':20260921,'tile_width':48,'density':1,'actor_width':0.8,'brief':'Teich im Nordosten; Weg West-Ost; 1 Haus; 3 Bäume'}
 save('layout-request.json',req);v=save('layout-response.json',api('POST','/api/layouts',req));rid=v['revision']
 save('layout-readback.json',api('GET','/api/layouts/'+rid))
 raw=c.get('/api/layouts/'+rid+'/artifacts/clean-guide.png').content;(out/'guide.png').write_bytes(raw)
 source=Path('/root/games/waldlicht/art/terrain-pilot/source-01.png');raw=source.read_bytes();assert hashlib.sha256(raw).hexdigest()=='3acd9a8f629bc77a4fc97d25331ea87a31a58ac00cc6ae5281b86e14157d05c7'
 (out/'style-only.png').write_bytes(raw)
 save('style-selection.json',{'path':str(source),'sha256':hashlib.sha256(raw).hexdigest(),'authority':'art/art-direction.json selectedConcept; treatment C is accepted rendering reference','role':'style_only','layout_authority':False})
 s=save('style.json',api('POST','/api/styles',{'png_base64':base64.b64encode(raw).decode(),'role':'style_only'}))
 prompt='Render the FIRST image exactly as the new terrain layout: green grass/moss ground, brown west-east walking path, blue pond in logical northeast. The SECOND image is ONLY the accepted Waldlicht forest-floor style: petrol shadows, moss green, ochre earth, warm restrained highlights, crisp dark outlines, clustered flat tones. Do NOT copy its map or introduce its water positions. Keep the path clear and continuous, keep water strictly within the blue guide region, keep the outer diamond and margins unchanged. Fine low moss, small leaf litter and pebbles only; no upright vegetation, rocks that block passage, trees, houses or props. Flat 2:1 isometric ground. Calm readable walkable surfaces. Transparent or plain dark neutral surround. No text, labels, tile grid, new roads or additional water. Full frame, no zoom/crop.'
 q=save('quote.json',api('POST','/api/generation/quote',{'revision':rid,'style_id':s['id'],'prompt':prompt}))
 save('quote-readback.json',api('GET','/api/generation/quotes/'+q['id']))
 print(json.dumps({'revision':rid,'quote':q['id'],'price':q['quote'],'schema':q['schema']}))
elif sys.argv[1]=='confirm':
 assert not (out/'confirm-intent.json').exists(),'paid confirmation already attempted; inspect exact job, never retry'
 q=json.loads((out/'quote.json').read_text());body={'revision':q['binding']['layout_revision'],'quote_id':q['id']}
 save('confirm-intent.json',body);j=save('job-submit.json',api('POST','/api/generation/confirm',body));save('job-readback.json',api('GET','/api/generation/jobs/'+j['id']));print(json.dumps(j))
elif sys.argv[1]=='poll':
 j=json.loads((out/'job-submit.json').read_text());j=save('job-current.json',api('POST','/api/generation/jobs/'+j['id']+'/resume',{}));print(json.dumps(j))
 if j.get('candidate_id'):
  t=save('candidate.json',api('GET','/api/terrain/'+j['candidate_id']));(out/'original.png').write_bytes(c.get('/api/terrain/'+t['id']+'/source.png').content);print(json.dumps(t))
