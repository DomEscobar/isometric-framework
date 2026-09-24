"""Read-only verification of real token-recovery run; no purchase or settlement."""
import os,sys,json,shlex,sqlite3
from pathlib import Path
from decimal import Decimal,ROUND_CEILING
import httpx
from PIL import Image,ImageChops
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from artifacts import canonical,digest
from hybrid_models import OpenRouter,validate_crops
from hybrid_source_recovery import validated_source
from hybrid_worker import immutable,default_store
from billing_settlement import totals
out=ROOT/'evidence/hybrid-source-continuation';rid=json.loads((out/'new-run.json').read_bytes())['id'];s=default_store()
before=json.loads((ROOT/'data/hybrid-source-continuation-before.json').read_bytes())
with s.g.connect() as db:
    unchanged={}
    for table,rows in before['tables'].items():
        key='seq' if table=='hybrid_events' else 'id'
        for old in rows:
            current=db.execute('SELECT * FROM '+table+' WHERE '+key+'=?',(old[key],)).fetchone()
            assert dict(current)==old,(table,old[key])
        unchanged[table]=len(rows)
    account=totals(db);calls=[dict(x) for x in db.execute('SELECT * FROM hybrid_calls WHERE run=?',(rid,))]
    assert account['released_microusd']==0 and account['original_microusd']==9095632
assert s.g.policy=={**before['policy'],'total_usd':'20.00'} and not s.g.policy['approved']
r=s.get(rid);validated_source(s,r['config']['continuation'])
assert r['phase']=='needs_attention' and r['call_count']==4 and r['image_count']==1 and r['latest'] is None and r['best'] is None
assert len(calls)==1 and calls[0]['role']=='extraction-0'
call=calls[0];req=json.loads(call['request']);receipt=json.loads(call['receipt']);choice=receipt['choices'][0]
assert req['body']['max_tokens']==32768 and req['body']['reasoning']=={'effort':'medium'} and choice['finish_reason']=='stop'
assert req['metadata']['top_provider']['max_completion_tokens']==65536
raw=json.loads(choice['message']['content']);decision=json.loads((s.g.root/'hybrid'/rid/'crop-decision-0.json').read_bytes());assert raw==decision
assert {k:v['verdict'] for k,v in raw['crops'].items()}=={'land':'pass','path':'pass','square':'pass','stairs':'fail','wall':'pass'}
try:validate_crops(raw,r['source_sha256'],[1920,1280],raw['crops'])
except ValueError as exc:validation_error=str(exc)
else:raise AssertionError('Real stairs FAIL was accepted')
source=s.g.root/'hybrid'/rid/'source-0.png';parent=s.g.root/'hybrid'/r['config']['continuation']['parent_id']/'source-0.png'
assert source.read_bytes()==parent.read_bytes() and digest(source.read_bytes())==r['source_sha256']
a=Image.open(source).convert('RGB');b=Image.open(out/'source-native-browser.png').convert('RGB');assert a.size==b.size==(1920,1280) and ImageChops.difference(a,b).getbbox() is None
http={}
with httpx.Client(base_url='http://127.0.0.1:48765') as c:
    config=c.get('/api/hybrid/config').json();assert config['ledger']['total_budget_usd']=='20.00' and not config['ledger']['enabled']
    for mode in ['diagnostic','production']:
        response=c.get('/api/hybrid-runs/'+rid+'/download',params={'mode':mode});assert response.status_code==409
        http[mode]={'status':response.status_code,'detail':response.json()}
for line in Path('/root/.config/layout-terrain-hybrid/environment').read_text().splitlines():
    if line.strip() and not line.lstrip().startswith('#'):
        key,value=line.split('=',1)
        if key=='OPENROUTER_API_KEY':os.environ[key]=shlex.split(value)[0]
p=OpenRouter(r['config']['planner_model']);billing=p.request('GET','/generation?id='+receipt['id'])
immutable(out/(receipt['id']+'-billing.json'),canonical(billing))
assert billing['data']['id']==receipt['id'] and Decimal(str(billing['data']['total_cost']))==Decimal(str(receipt['usage']['cost']))
report=dict(run_id=rid,phase=r['phase'],result='REAL COMPLETE EXTRACTION; STAIRS FAIL; NO PRODUCTION',project_cap_microusd=20000000,original_rows_unchanged=unchanged,accounting=account,remaining_microusd=20000000-account['effective_microusd'],token_policy=req['body']['max_tokens'],reasoning=req['body']['reasoning'],call_id=call['id'],provider_id=receipt['id'],held_microusd=call['amount'],usage=receipt['usage'],actual_billing_usd=str(billing['data']['total_cost']),actual_billing_ceil_microusd=int((Decimal(str(billing['data']['total_cost']))*1000000).to_integral_value(rounding=ROUND_CEILING)),billing_settlement_applied=False,crop_decision=decision,validation_error=validation_error,source_native_browser_pixels_exact=True,source_original_sha256=r['source_sha256'],download=http,lifetime=dict(calls=r['call_count'],images=r['image_count'],max_calls=6,max_images=1),sample_or_final_purchased=False)
immutable(out/'verification.json',canonical(report));print(json.dumps(report,indent=2))
