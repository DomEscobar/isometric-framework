"""Free-only billing lookup for the reassessment child calls. No POST, no liability release."""
import os,sys,json,shlex
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from hybrid_models import OpenRouter
from hybrid_worker import immutable,default_store
from artifacts import canonical
for line in Path('/root/.config/layout-terrain-hybrid/environment').read_text().splitlines():
    if line.strip() and not line.lstrip().startswith('#'):
        key,value=line.split('=',1)
        if key=='OPENROUTER_API_KEY':os.environ[key]=shlex.split(value)[0]
s=default_store();rid='b9a94348e6404358b353d3b3c5fd5f24'
out=ROOT/'evidence/hybrid-source-reassessment'
p=OpenRouter('google/gemini-3.8-flash')
result=[]
with s.g.connect() as db:
    for call in db.execute('SELECT id,role,request,receipt,amount FROM hybrid_calls WHERE run=? ORDER BY rowid',(rid,)):
        receipt=json.loads(call['receipt']);gid=receipt.get('id')
        billing=p.request('GET','/generation?id='+gid)
        immutable(out/(gid+'-billing.json'),canonical(billing))
        data=billing['data']
        entry=dict(call_id=call['id'],role=call['role'],generation_id=gid,held_microusd=call['amount'],receipt_usage_cost=str(receipt.get('usage',{}).get('cost')),billing_total_cost=str(data.get('total_cost')),model=data.get('model'),finish_reason=data.get('finish_reason'),tokens_prompt=data.get('tokens_prompt'),tokens_completion=data.get('tokens_completion'),native_tokens_reasoning=data.get('native_tokens_reasoning'))
        result.append(entry);print(json.dumps(entry))
immutable(out/'billing-summary.json',canonical(result))
