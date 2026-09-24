"""Poll one hybrid run until terminal; persist final run + events. Read-only over HTTP."""
import json,sys,time
from pathlib import Path
import httpx
ROOT=Path(__file__).resolve().parents[1]
out=ROOT/'evidence/hybrid-source-reassessment';out.mkdir(exist_ok=True)
rid=sys.argv[1];last=None
with httpx.Client(base_url='http://127.0.0.1:48765',timeout=60) as c:
    while True:
        r=c.get('/api/hybrid-runs/'+rid).json()
        state=(r['phase'],r.get('stop_reason'))
        if state!=last:
            print(json.dumps(dict(at=time.time(),phase=r['phase'],calls=r['call_count'],images=r['image_count'],local=r.get('local_count'),stop=r.get('stop_reason'))),flush=True);last=state
        if r['phase'] in ['succeeded','needs_attention','cancelled']:
            (out/'terminal-run.json').write_text(json.dumps(r,indent=1))
            (out/'events.json').write_text(json.dumps(c.get('/api/hybrid-runs/'+rid+'/events').json(),indent=1))
            break
        time.sleep(10)
