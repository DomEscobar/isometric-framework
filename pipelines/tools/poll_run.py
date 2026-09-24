"""Read-only run status poll via loopback API. No payments, no state changes."""
import json,sys
import httpx
rid=sys.argv[1]
r=httpx.get('http://127.0.0.1:48765/api/hybrid-runs/'+rid,timeout=30).json()
keep={k:r.get(k) for k in ['id','phase','stop_reason','call_count','image_count','local_count','attempt','source_sha256','latest','best','production_approved','sample_directory','gate','held_microusd','verification']}
print(json.dumps(keep,indent=1,default=str))
print('CALLS',json.dumps([{k:c[k] for k in ['role','amount','receipt_known']} for c in r['calls']]))
