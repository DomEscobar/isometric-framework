"""Free live metadata discovery only: never upload or submit a prediction."""
import sys,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from provider import WaveSpeed
from artifacts import canonical
out=Path(__file__).resolve().parents[1]/'evidence/constrained-recovery';out.mkdir(parents=True,exist_ok=True)
p=WaveSpeed();models=p.request('GET','/models')
ids=['wavespeed-ai/z-image/turbo-inpaint','wavespeed-ai/flux-fill-dev','openai/gpt-image-1.5/edit']
for model in models:
    if model['model_id'] in ids:
        (out/(model['model_id'].replace('/','_')+'.json')).write_bytes(canonical(model))
        print(model['model_id'],[(s['type'], list(s.keys())) for s in model['api_schema']['api_schemas']])
print('Authenticated free catalog; retained',len(ids),'models; no uploads or paid calls')
