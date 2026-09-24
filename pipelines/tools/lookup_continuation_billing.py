"""Free-only generation billing lookup. No chat POST or liability release."""
import os,sys,json,shlex
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from hybrid_models import OpenRouter
from hybrid_worker import immutable
from artifacts import canonical
for line in Path('/root/.config/layout-terrain-hybrid/environment').read_text().splitlines():
    if line.strip() and not line.lstrip().startswith('#'):
        key,value=line.split('=',1)
        if key=='OPENROUTER_API_KEY':os.environ[key]=shlex.split(value)[0]
p=OpenRouter('google/gemini-3.8-flash');out=ROOT/'evidence/hybrid-receipt-continuation'
meta=p.preflight();immutable(out/'model-current.json',canonical(meta))
print(json.dumps({k:meta.get(k) for k in ['id','supported_parameters','reasoning','top_provider']}))
for gid in ['gen-1790081788-rtA2eCqsJFNoXBzFMPqd','gen-1790083043-1CWqF1BmU0rWdmKXjH3n']:
    result=p.request('GET','/generation?id='+gid)
    immutable(out/(gid+'-billing.json'),canonical(result))
    data=result['data'];print(json.dumps({k:data.get(k) for k in ['id','model','total_cost','is_byok','provider_name','finish_reason','native_finish_reason','tokens_prompt','tokens_completion','native_tokens_reasoning']}))
