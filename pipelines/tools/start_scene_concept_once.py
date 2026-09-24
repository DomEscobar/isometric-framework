"""ONE authorized owner-directed board-variant run. Never a regression test."""
import os,sys,json,time,shlex
from pathlib import Path
import httpx
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from artifacts import canonical,digest
from hybrid_worker import default_store,immutable
from hybrid_directive_repair import validated_directive
from hybrid_models import OpenRouter
from billing_settlement import totals
out=ROOT/'evidence/hybrid-scene-concept';out.mkdir(exist_ok=True)
if (out/'new-run.json').exists():raise SystemExit('Already launched; no duplicate child')
for line in Path('/root/.config/layout-terrain-hybrid/environment').read_text().splitlines():
    if line.strip() and not line.lstrip().startswith('#'):
        key,value=line.split('=',1)
        if key in ['OPENROUTER_API_KEY','WAVESPEED_API_KEY']:os.environ[key]=shlex.split(value)[0]
s=default_store();pid='2222f03c528e47a099e17606ef6e0307'
p,_,cfg=validated_directive(s,parent_id=pid)
assert p['inherited_calls']==11 and p['inherited_images']==3
assert cfg['token_policy']['extraction']['max_tokens']==32768
with s.g.connect() as db:
    before={table:[dict(x) for x in db.execute('SELECT * FROM '+table+' ORDER BY rowid')] for table in ['jobs','reviews','hybrid_runs','hybrid_calls','hybrid_events','hybrid_liability_authorizations','billing_settlements']}
    account=totals(db);unknown=[dict(x) for x in db.execute('SELECT * FROM hybrid_calls WHERE receipt IS NULL')]
assert account['effective_microusd']==15725765 and account['settled_calls']==9 and len(unknown)==2
assert not s.g.policy['approved'] and s.g.policy['total_usd']=='20.00'
private=ROOT/'data/hybrid-scene-concept-before.json'
immutable(private,canonical(dict(tables=before,policy=s.g.policy)));private.chmod(0o600)
budget=2900000
assert budget+account['effective_microusd']<=20000000
approval=(ROOT/'HYBRID_COMPLEX_TERRAIN_AUTHORIZATION.md').read_text()
assert 10<=len(approval.strip())<=4000
directive=('Owner explicit choice 2026-09-22 scene-concept pipeline: FIRST paint this exact isometric scene as one gorgeous coherent painting (rich painterly textures, natural colors), THEN derive from that painting a FLAT orthographic material board with all seven separated slots (land, path, plateau, square, stairs, wall, water) in the same palette and texture character - all strictly FLAT face-on, NO perspective, NO cliff, NO tread/riser objects, NO plants or props in any slot. The renderer builds all geometry.')
with httpx.Client(base_url='http://127.0.0.1:48765',timeout=180) as c:
    response=c.post('/api/hybrid-runs/'+pid+'/continue-directive',json=dict(budget_microusd=budget,max_seconds=7200,confirm_paid=True,approval_text=approval,owner_style_directive=directive,flow='scene_concept'),headers={'Idempotency-Key':'scene-concept-calls5-images2-once-v1'})
    response.raise_for_status();r=response.json();immutable(out/'new-run.json',canonical(r))
    assert (r['call_count'],r['image_count'])==(11,3) and r['config']['max_images']==5 and r['config']['max_calls']==16
    assert r['config']['continuation']['kind']=='directive_repair' and r['config']['followup_call_limit']==4
    scope=dict(run_id=r['id'],config_sha256=r['config_sha256'],approval_text=approval,owner_style_directive=directive,
        amendment=r['config']['authorization_amendment'],parent_id=pid,project_cap_microusd=20000000,budget_microusd=budget,
        max_calls=16,max_images=5,new_images=2,followup_calls=5,settled_calls=9,expires=time.time()+7200,
        liabilities=[dict(call_id=x['id'],request_sha256=digest(x['request'].encode()),amount=x['amount']) for x in unknown])
    aid=s.acknowledge_liabilities(scope)
    with s.g.connect() as db:assert json.loads(db.execute('SELECT record FROM hybrid_liability_authorizations WHERE id=?',(aid,)).fetchone()[0])==scope
    auth={k:scope[k] for k in ['config_sha256','budget_microusd','max_calls','max_images','expires']};auth['liability_authorization']=aid
    immutable(ROOT/'data/hybrid-authorizations'/(r['id']+'.json'),canonical(auth));immutable(out/'authorization.json',canonical(scope))
    c.post('/api/hybrid-runs/'+r['id']+'/resume',json={}).raise_for_status()
    got=c.get('/api/hybrid-runs/'+r['id']);got.raise_for_status();immutable(out/'launch-readback.json',canonical(got.json()))
    print(json.dumps(dict(run_id=r['id'],phase=got.json()['phase'],acknowledgment_id=aid,budget_microusd=budget,held_effective_before=account['effective_microusd'])))
