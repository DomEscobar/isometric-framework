"""Read back exact batch and retain genuine evidence, without purchases."""
import json,sys,sqlite3,io
from pathlib import Path
import httpx
from PIL import Image,ImageDraw
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from artifacts import canonical,digest
root=Path(__file__).resolve().parents[1];out=root/'evidence/overnight-two-styles';c=httpx.Client(base_url='http://127.0.0.1:59661',timeout=120)
id=json.loads((out/'start-response.json').read_bytes())['id'];w=c.get('/api/overnight-batch/'+id).json();(out/'batch-readback.json').write_bytes(json.dumps(w,indent=2).encode());print('BATCH',w['status'])
old=c.get('/api/auto-repair/8e96cc6e6289256aead3f64d8ea86bfc132d7c47dee27898749bf43428cc1577').json();assert old==json.loads((out/'old-run-before.json').read_bytes())
status=c.get('/api/generation/status').json();(out/'budget-readback.json').write_bytes(canonical(status));print('ACCOUNTING',status)
db=sqlite3.connect('file:'+str(root/'data/generation.sqlite3')+'?mode=ro',uri=True)
for label,a in zip(('warm','fantasy'),w['styles']):
 d=out/label;(d/'iteration.json').write_bytes(json.dumps(a,indent=2).encode());print(label,a['phase'],a['status'],a.get('stop_reason'))
 if a.get('job_id'):
  j=json.loads(db.execute('select record from jobs where id=?',(a['job_id'],)).fetchone()[0]);q=c.get('/api/generation/quotes/'+j['quote_id']).json()
  (d/'job-public.json').write_bytes(canonical(c.get('/api/generation/jobs/'+j['id']).json()));(d/'quote.json').write_bytes(canonical(q));(d/'exact-quote.json').write_bytes(canonical(j.get('exact_quote',{})))
  req=j['request'];assert digest(canonical(req))==j['request_sha256'];redacted={**req,'image_urls':['OMITTED_TRANSIENT_PROVIDER_URL' for u in req['image_urls']]};(d/'request-redacted.json').write_bytes(canonical(redacted));(d/'request-binding.json').write_bytes(canonical(dict(request_sha256=j['request_sha256'],exact_request_location='data/generation.sqlite3 jobs '+j['id'],provider_fields=sorted(req),image_count=len(req['image_urls']))))
  receipt=(root/'data'/(j['id']+'.receipt.json')).read_bytes();(d/'receipt.json').write_bytes(receipt)
 if a.get('source_candidate_id'):
  source=c.get('/api/terrain/'+a['source_candidate_id']+'/source.png');source.raise_for_status();raw=source.content;(d/'source.png').write_bytes(raw);record=c.get('/api/terrain/'+a['source_candidate_id']).json();assert digest(raw)==record['source_sha256'];(d/'source-record.json').write_bytes(canonical(record))
  (d/'registration.json').write_bytes(json.dumps(a.get('registration'),indent=2).encode())
  im=Image.open(io.BytesIO(raw)).convert('RGB');ref=Image.open(d/'reference-decoded.png').convert('RGB');panel=Image.new('RGB',(1440,650),'#192329');draw=ImageDraw.Draw(panel)
  for x,src,text in [(0,ref,'STYLE ONLY - reference'),(720,im,'GENERATED SOURCE - NOT GAMEPLAY')]:
   draw.text((x+12,12),label+' / '+text,fill='white');src.thumbnail((700,580),Image.Resampling.LANCZOS);panel.paste(src,(x+(720-src.width)//2,60+(580-src.height)//2))
  panel.save(d/'reference-vs-source.png')
 if a.get('candidate_id') and a['candidate_id']!=a.get('source_candidate_id'):
  candidate=c.get('/api/terrain/'+a['candidate_id']).json();(d/'registered-record.json').write_bytes(canonical(candidate));preview=c.get('/api/terrain/'+a['candidate_id']+'/preview.png');preview.raise_for_status();(d/'final-density.png').write_bytes(preview.content)
 if a.get('evaluation_id'):
  e=c.get('/api/evaluations/'+a['evaluation_id']);e.raise_for_status();e=e.json();(d/'evaluation.json').write_bytes(json.dumps(e,indent=2).encode());print('GATE',e.get('status'),e.get('gate'))
