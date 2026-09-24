"""EXPLICIT PAID harness: one constrained service start, never regression.
All image/review POSTs remain inside durable service with central reservations.
Closes paid policies and verifies a fresh closed server even on failure.
"""
import json,sys,time,subprocess,socket,urllib.request,urllib.error
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from artifacts import canonical,digest
root=Path(__file__).resolve().parents[1];data=root/'data';out=root/'evidence/constrained-recovery'
parent='3c932cbd0832cc4707bc8281f828eb837930c89b9dd399ca90223df0f3c697da'
with socket.socket() as s:s.bind(('127.0.0.1',0));port=s.getsockname()[1]
base=f'http://127.0.0.1:{port}';proc=None
p=json.loads((data/'generation-policy.json').read_bytes());review=json.loads((data/'reviewer-config.json').read_bytes())
assert not p['approved'] and not review['enabled'] and p['total_usd']=='10.00' and p['max_attempts']==6
assert json.loads((out/'free-spike.json').read_bytes())['paid_calls']==0
policy=dict(enabled=True,parent_run_id=parent,authorization_sha256=digest((root/'QUALITY_RECOVERY_AUTHORIZATION.md').read_bytes()),strategy='canonical-sidewalk-mask-v1')

def save(name,obj):
    (out/name).write_bytes(canonical(obj))

def http(path,body=None):
    req=urllib.request.Request(base+path,data=canonical(body) if body is not None else None,headers={'Content-Type':'application/json'})
    try:
        with urllib.request.urlopen(req,timeout=180) as r:return r.status,json.loads(r.read())
    except urllib.error.HTTPError as e:return e.code,json.loads(e.read())

def server():
    log=(out/'server.log').open('ab')
    pr=subprocess.Popen([sys.executable,'-m','uvicorn','app:app','--host','127.0.0.1','--port',str(port),'--no-access-log'],cwd=root,stdout=log,stderr=log)
    for _ in range(80):
        if pr.poll() is not None:raise RuntimeError('server exited')
        try:
            status,value=http('/api/generation/status')
            if status==200:return pr
        except (OSError,ValueError):pass
        time.sleep(.2)
    pr.terminate();raise RuntimeError('server not ready')

try:
    p.update(approved=True,max_attempts=7,scope='ONE constrained masked urban correction plus conditional valid review; same inclusive USD10 ceiling and all old holds')
    review['enabled']=True
    (data/'generation-policy.json').write_bytes(canonical(p));(data/'reviewer-config.json').write_bytes(canonical(review));(data/'constrained-recovery-policy.json').write_bytes(canonical(policy))
    proc=server()
    before=http('/api/generation/status');save('http-before.json',dict(base_url=base,status=before[0],body=before[1]))
    status,w=http('/api/auto-repair/'+parent+'/constrained',{'confirm_paid':True})
    save('http-start.json',dict(status=status,body=w))
    if status!=201:raise RuntimeError('start rejected; inspect retained exact HTTP response')
    rid=w['id'];print('run',rid,flush=True)
    deadline=time.monotonic()+650
    while time.monotonic()<deadline:
        status,w=http('/api/auto-repair/'+rid)
        save('run.json',w)
        with (out/'progress.jsonl').open('ab') as f:f.write(canonical(dict(status=w['status'],phase=w['phase'],stop_reason=w['stop_reason'],iterations=len(w['iterations'])))+b'\n')
        print(w['status'],w['phase'],w['stop_reason'],flush=True)
        if w['status']!='running':break
        time.sleep(3)
    else:
        http('/api/auto-repair/'+rid+'/cancel',{})
        raise RuntimeError('known durable run timeout; cancelled future stages, no retry')
    save('http-after.json',http('/api/generation/status')[1])
finally:
    if proc:
        proc.terminate()
        try:proc.wait(timeout=10)
        except subprocess.TimeoutExpired:proc.kill();proc.wait()
    p.update(approved=False,max_attempts=7,scope='CLOSED after one constrained-mask recovery; retain every original and liability; no reroll')
    review['enabled']=False;policy['enabled']=False
    (data/'generation-policy.json').write_bytes(canonical(p));(data/'reviewer-config.json').write_bytes(canonical(review));(data/'constrained-recovery-policy.json').write_bytes(canonical(policy))
    proc=server()
    try:
        checks={'generation':http('/api/generation/status'),'closed_constrained_start':http('/api/auto-repair/'+parent+'/constrained',{'confirm_paid':True})}
        if 'rid' in locals():checks['terminal_readback']=http('/api/auto-repair/'+rid);checks['terminal_resume']=http('/api/auto-repair/'+rid+'/resume',{})
        save('http-closed.json',checks)
        assert checks['generation'][1]['enabled'] is False and checks['closed_constrained_start'][0]==409
        print('Closed controls verified',checks['generation'][1]['reserved_usd'],flush=True)
    finally:proc.terminate();proc.wait(timeout=10)
