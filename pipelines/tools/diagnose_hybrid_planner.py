"""Read-only forensic snapshot; public GET only, never completion/auth/ledger writes."""
import base64,hashlib,io,json,sqlite3,subprocess,sys
from pathlib import Path
import httpx
from PIL import Image
ROOT=Path(__file__).resolve().parents[1]
RID='603c561c946e48efa2ba77a62e4b5848'
OUT=ROOT/'evidence/hybrid-planner-diagnosis'
OUT.mkdir(exist_ok=True)
sha=lambda b:hashlib.sha256(b).hexdigest()
db=sqlite3.connect(f'file:{ROOT}/data/generation.sqlite3?mode=ro',uri=True)
db.row_factory=sqlite3.Row
run=db.execute('SELECT * FROM hybrid_runs WHERE id=?',(RID,)).fetchone()
call=db.execute('SELECT * FROM hybrid_calls WHERE run=?',(RID,)).fetchone()
request=json.loads(call['request']);body=request['body']
events=[json.loads(r[0]) for r in db.execute('SELECT record FROM hybrid_events WHERE run=? ORDER BY seq',(RID,))]
inputs=[]
for part in body['messages'][1]['content']:
    if part['type']=='image_url':
        raw=base64.b64decode(part['image_url']['url'].split(',',1)[1],validate=True)
        with Image.open(io.BytesIO(raw)) as im:
            inputs.append(dict(sha256=sha(raw),bytes=len(raw),size=list(im.size),format=im.format))
ledger={}
for table in ['jobs','reviews','hybrid_calls','hybrid_runs','hybrid_events']:
    rows=[tuple(r) for r in db.execute('SELECT * FROM '+table+' ORDER BY rowid')]
    ledger[table]={'count':len(rows),'rows_sha256':sha(json.dumps(rows,separators=(',',':'),ensure_ascii=False).encode())}
held=sum(db.execute('SELECT coalesce(sum(reserve),0) FROM '+t).fetchone()[0] for t in ['jobs','reviews'])
cmd=['journalctl','-u','layout-terrain-hybrid-worker.service','-u','layout-terrain-hybrid-api.service','--since','@1790077880','--until','@1790077920','--output=json','--no-pager']
journal=subprocess.run(cmd,capture_output=True,text=True,check=True)
logs=[json.loads(l) for l in journal.stdout.splitlines() if l.startswith('{')]
endpoint=httpx.get('https://openrouter.ai/api/v1/models/google/gemini-3.8-flash/endpoints',timeout=30)
endpoint.raise_for_status(); endpoints=endpoint.json()['data']['endpoints']
result=dict(run_id=RID,phase=run['phase'],call_id=call['id'],receipt_known=call['receipt'] is not None,
    request_sha256=sha(call['request'].encode()),request_body_keys=sorted(body),
    schema=body['response_format'],image_inputs=inputs,input_bindings=request['inputs'],
    user_prompt_present=bool(body['messages'][1]['content'][0]['text']),
    held_microusd=call['amount'],central_held_microusd=held,ledger=ledger,
    journal_window_entries=len(logs),journal_window_epoch=[1790077880,1790077920],
    seconds_reservation_to_terminal=events[-1]['at']-next(e['at'] for e in events if 'call_id' in e),
    current_public_endpoints=[{'tag':e['tag'],'supported_parameters':e['supported_parameters']} for e in endpoints],
    proven='Old adapter discarded every HTTP status, server body and exception category. No historical response recovered.',
    unknown=['HTTP status','remote error body','whether any provider billed the request'],
    excluded=['Missing image inputs','Missing user prompt','Malformed response_format envelope'],
    unproven_hypotheses=['Provider schema dialect/complexity rejection','Upstream HTTP error including auth/rate-limit/availability','Early network failure or invalid JSON response'],
    safety='No paid POST, no credential read/change, no live ledger write, no retry or hold release')
target=OUT/(sys.argv[1] if len(sys.argv)>1 else 'diagnostic.json')
with target.open('x') as f:json.dump(result,f,indent=2)
print(json.dumps({k:result[k] for k in ['run_id','phase','receipt_known','request_sha256','central_held_microusd','journal_window_entries','seconds_reservation_to_terminal']},indent=2))
print('Saved sanitized artifact:',target)
