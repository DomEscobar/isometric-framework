"""Explicit urban pilot stages; confirm only once; poll is never a new paid request."""
import sys,os,json,base64,hashlib,io,sqlite3
from pathlib import Path
import httpx
from PIL import Image
root=Path(__file__).resolve().parents[1];out=root/os.environ.get('EVIDENCE','evidence/urban-pilot');out.mkdir(parents=True,exist_ok=True)
c=httpx.Client(base_url=os.environ.get('BASE_URL','http://127.0.0.1:53047'),timeout=180)
def save(name,obj): (out/name).write_text(json.dumps(obj,indent=2));return obj
def api(method,path,body=None):
 r=c.request(method,path,json=body);r.raise_for_status();return r.json()
if sys.argv[1]=='prepare':
 status=save('status-before.json',api('GET','/api/generation/status'));assert status['attempts']==1 and status['reserved_usd']=='1.599224'
 with sqlite3.connect(root/'data/generation.sqlite3') as db:
  save('ledger-before.json',{t:[{'id':a,'reserve_microusd':b,'status':json.loads(d).get('status')} for a,b,d in db.execute('select id,reserve,record from '+t)] for t in ('jobs','reviews')})
 req={'width':16,'height':14,'seed':20260922,'tile_width':48,'density':1,'actor_width':0.8,'kind':'urban','brief':''}
 save('layout-request.json',req);v=save('layout-response.json',api('POST','/api/layouts',req));rid=v['revision']
 assert api('GET','/api/layouts/'+rid)==v
 raw=c.get('/api/layouts/'+rid+'/artifacts/clean-guide.png').content;(out/'guide.png').write_bytes(raw)
 source=Path('/root/.hermes/cache/images/img_4a2bfeabebd9.jpg');raw=source.read_bytes();(out/'style-original.jpg').write_bytes(raw)
 im=Image.open(io.BytesIO(raw)).convert('RGB');im.save(out/'style-only.png');normalized=(out/'style-only.png').read_bytes()
 assert Image.open(io.BytesIO(normalized)).tobytes()==im.tobytes()
 save('style-lineage.json',{'original_path':str(source),'original_sha256':hashlib.sha256(raw).hexdigest(),'normalized_sha256':hashlib.sha256(normalized).hexdigest(),'normalization':'JPEG decoded once to RGB; lossless PNG encoding of identical decoded RGB pixels, no resizing or repaint. JPEG itself remains retained.','size':list(im.size),'role':'style_only','layout_authority':False})
 s=save('style.json',api('POST','/api/styles',{'png_base64':base64.b64encode(normalized).decode(),'role':'style_only'}));assert api('GET','/api/styles/'+s['id'])==s
 prompt='IMAGE 1 IS THE EXACT GEOMETRY AUTHORITY, a new small original urban promenade. Gray #858991 is one straight paved asphalt street three cells wide. Warm cream #dfd4b9 is pedestrian sidewalk/light warm square paving, NOT soil. Green #8bb764 means ONLY inset low flat planted green pockets; keep their precise footprints. Preserve all region boundaries, parallel curb lines, full diamond and margins. IMAGE 2 IS STYLE ONLY: light friendly city pixel art, warm cream paving, cool medium gray street, lively yellow-green planted ground, subtle cool outlines, small precise pixel clusters, fine crisp paving seams and restrained material texture. Do NOT copy its road intersection or arrangement. Paint an EMPTY ground layer: no cars, buses, people, buildings, trees, tree shadows, benches, lamp posts, bins, fences, upright bushes, props or text. Object spaces remain empty sidewalk for future separate props. Keep broad sidewalks unobstructed. Small flat ground cover only in green pockets. No traffic crossing marks or simulated traffic needed. Absolutely no forest soil/grass meadow substitution, no water, no new geometry. Flat 2:1 isometric ground, full frame, no crop or zoom. Use dark neutral plain surround outside the exact diamond. Fine readable pixel detail at game scale, not broad blurry brushwork.'
 q=save('quote.json',api('POST','/api/generation/quote',{'revision':rid,'style_id':s['id'],'prompt':prompt}));assert api('GET','/api/generation/quotes/'+q['id'])==q
 print(json.dumps({'revision':rid,'quote':q['id'],'price':q['quote'],'schema':q['schema']}))
elif sys.argv[1]=='confirm':
 assert not (out/'confirm-intent.json').exists(),'Already attempted: inspect exact job, never resubmit'
 q=json.loads((out/'quote.json').read_text());body={'revision':q['binding']['layout_revision'],'quote_id':q['id']}
 save('confirm-intent.json',body);j=save('job-submit.json',api('POST','/api/generation/confirm',body));save('job-readback.json',api('GET','/api/generation/jobs/'+j['id']));print(json.dumps(j))
elif sys.argv[1]=='poll':
 j=json.loads((out/'job-submit.json').read_text());j=save('job-current.json',api('POST','/api/generation/jobs/'+j['id']+'/resume',{}));print(json.dumps(j))
 if j.get('candidate_id'):
  t=save('candidate.json',api('GET','/api/terrain/'+j['candidate_id']));(out/'original.png').write_bytes(c.get('/api/terrain/'+t['id']+'/source.png').content);print(json.dumps({'candidate':t['id'],'size':t['decoded_size'],'status':t['status']}))
