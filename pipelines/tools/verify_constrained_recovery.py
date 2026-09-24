"""Read-only verification of retained constrained result. NEVER submits.
Only free prediction/input readbacks, artifact checks and closed HTTP endpoints.
"""
import sys,json,io,urllib.request,urllib.error
from pathlib import Path
from decimal import Decimal
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from generation import Generation
from provider import WaveSpeed
from artifacts import canonical,digest
from PIL import Image,ImageDraw
root=Path(__file__).resolve().parents[1];out=root/'evidence/constrained-recovery';data=root/'data'
run=json.loads((out/'run.json').read_bytes());a=run['iterations'][0]
g=Generation(data,WaveSpeed(),json.loads((data/'generation-policy.json').read_bytes()));j=g.get(a['job_id'])
p=WaveSpeed();remote=p.poll(j['prediction_id'])
# Retain full raw result server-side, not public signed CDN links.
(data/'constrained-outputs'/j['id']/'provider-result.json').write_bytes(canonical(remote))
assert remote['id']==j['prediction_id'] and remote['status']=='completed'
raw=(data/'constrained-outputs'/j['id']/'provider-original.bin').read_bytes()
assert p.download(remote['outputs'][0])==raw
inputs={}
for field,filename,sha in [('image','registered-input.png',a['plan']['control']['source_sha256']),('mask_image','edit-mask.png',a['plan']['control']['mask_sha256'])]:
    downloaded=p.download(j['request'][field]);assert digest(downloaded)==sha
    assert downloaded==(out/filename).read_bytes()
    inputs[field]={'sha256':sha,'matches_uploaded_url_readback':True}
assert j['request']['size']=='768*408' and set(j['request'])=={'prompt','image','mask_image','size'}
assert digest(raw)==a['preservation']['provider_original_sha256']
(out/'provider-original.jpg').write_bytes(raw)
source=Image.open(out/'registered-input.png').convert('RGBA');after=Image.open(io.BytesIO(raw)).convert('RGB')
# Comparison ONLY: native 1:1 panels, no fitting, cropping or geometry changes.
board=Image.new('RGB',(1560,580),'#121719');draw=ImageDraw.Draw(board)
draw.text((12,12),'BEFORE: exact registered input 768 x 408, 1:1; unapproved',fill='white')
draw.text((792,12),'AFTER: provider JPEG 768 x 512, 1:1; REJECTED / NOT GAMEPLAY',fill='white')
board.paste(source,(12,46),source.getchannel('A'));board.paste(after,(792,46))
board.save(out/'before-after-native.png')
base='http://127.0.0.1:45567'
def http(path,body=None):
    req=urllib.request.Request(base+path,data=canonical(body) if body is not None else None,headers={'Content-Type':'application/json'})
    try:
        with urllib.request.urlopen(req,timeout=90) as r:return r.status,r.read(),dict(r.headers)
    except urllib.error.HTTPError as e:return e.code,e.read(),dict(e.headers)
status,download,headers=http('/api/generation/jobs/'+j['id']+'/constrained-original')
assert status==200 and download==raw
(out/'http-downloaded-original.jpg').write_bytes(download)
checks={'original':dict(status=status,sha256=digest(download),content_type=headers.get('content-type'))}
for label,path,body in [('run','/api/auto-repair/'+run['id'],None),('status','/api/generation/status',None),('closed_start','/api/auto-repair/'+run['continuation']['parent_run_id']+'/constrained',{'confirm_paid':True}),('closed_generation','/api/generation/confirm',{'quote_id':j['quote_id'],'revision':run['frozen']['revision'],'style_spec_id':run['frozen']['style']})]:
    code,b,h=http(path,body);checks[label]=dict(status=code,body=json.loads(b))
assert checks['closed_start']['status']==409 and checks['closed_generation']['status']==403
assert checks['status']['body']['enabled'] is False
assert checks['run']['body']==run
summary=dict(run_id=run['id'],job_id=j['id'],prediction_id=j['prediction_id'],provider_actual_status=remote['status'],
             local_result='rejected: provider changed canvas and content; original retained; no import, review or production export',
             requested_size=j['request']['size'],actual_size=list(after.size),actual_format='JPEG',
             inputs_readback=inputs,original_sha256=digest(raw),request_sha256=j['request_sha256'],
             preservation=a['preservation'],lifetime_iterations=run['inherited_iterations']+len(run['iterations']),
             image_price=j['exact_quote']['price'],held_usd=g.status()['reserved_usd'],remaining_usd=str(Decimal('10')-Decimal(g.status()['reserved_usd'])),
             new_reviews=0,gate_relaxed=False,output_composited_or_warped=False,http=checks)
(out/'verification.json').write_bytes(canonical(summary))
print(json.dumps({k:v for k,v in summary.items() if k!='http'},indent=2))
