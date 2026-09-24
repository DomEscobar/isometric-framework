"""ONE authorized live complex-terrain run (v2, planner 32768/medium). Never a regression test."""
import os,sys,json,time,shlex
from pathlib import Path
import httpx
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from artifacts import canonical,digest
from hybrid_worker import default_store,immutable
from billing_settlement import totals
out=ROOT/'evidence/hybrid-complex-terrain-v2';out.mkdir(exist_ok=True)
if (out/'new-run.json').exists():raise SystemExit('Already launched; no duplicate run')
for line in Path('/root/.config/layout-terrain-hybrid/environment').read_text().splitlines():
    if line.strip() and not line.lstrip().startswith('#'):
        key,value=line.split('=',1)
        if key in ['OPENROUTER_API_KEY','WAVESPEED_API_KEY']:os.environ[key]=shlex.split(value)[0]
s=default_store()
with s.g.connect() as db:
    before={table:[dict(x) for x in db.execute('SELECT * FROM '+table+' ORDER BY rowid')] for table in ['jobs','reviews','hybrid_runs','hybrid_calls','hybrid_events','hybrid_liability_authorizations','billing_settlements']}
    account=totals(db);unknown=[dict(x) for x in db.execute('SELECT * FROM hybrid_calls WHERE receipt IS NULL')]
assert account['effective_microusd']==14539038 and account['released_microusd']==1771930 and account['settled_calls']==2
assert len(unknown)==2 and not s.g.policy['approved'] and s.g.policy['total_usd']=='20.00'
private=ROOT/'data/hybrid-complex-terrain-v2-before.json'
immutable(private,canonical(dict(tables=before,policy=s.g.policy)));private.chmod(0o600)
prior=json.loads((ROOT/'evidence/hybrid-reassessment-repair/new-run.json').read_bytes())['config']
reference=dict(reference_sha256=prior['reference_sha256'],reference_original_sha256=prior['reference_original_sha256'])
description=('Mehrstufiges isometrisches Dorf-Terrain auf 24x20 Zellen mit drei Höhenebenen (Straßenniveau 0, '
 'mittleres Plateau auf 8px, oberes Terrassenplateau auf 16px). Zwei explizite Treppen verbinden die Ebenen: '
 'eine breite Dorftreppe vom Straßenniveau zum mittleren Plateau, eine weitere vom mittleren zum oberen Plateau. '
 'Unten links ein kleiner See aus Wasser mit sandigem Uferweg, nur auf Ebene 0. Geschwungene Erde-/Sand-Dorfwege '
 'verbinden den Startpunkt unten links mit zwei Pflichtzielen: dem gepflasterten Dorfplatz auf dem mittleren '
 'Plateau und dem erhöhten Terrassenplatz oben rechts. Grasland mit Wiesenflächen dazwischen, ein kleiner '
 'Plateaubereich als erhöhte Wiese. Keine Gebäude, Brücken, Props oder gestapelten Flächen. Der Weg über beide '
 'Treppen muss mit voller Actor-Figur sicher begehbar sein.')
budget=3800000
assert budget+account['effective_microusd']<=20000000
approval=(ROOT/'HYBRID_COMPLEX_TERRAIN_AUTHORIZATION.md').read_text()
assert 10<=len(approval.strip())<=4000
group=dict(max_tokens=32768,reasoning_effort='medium')
body=dict(mode='live',description=description,constraints=dict(width=24,height=20,actor_width=.64),
    budget_microusd=budget,max_images=1,max_calls=6,max_local_corrections=0,max_seconds=7200,
    auto_continue=True,confirm_paid=True,
    token_policy=dict(planner=group,extraction=group,review=group),
    **reference)
with httpx.Client(base_url='http://127.0.0.1:48765',timeout=180) as c:
    response=c.post('/api/hybrid-runs',json=body,headers={'Idempotency-Key':'complex-terrain-project20-calls6-images1-once-v2'})
    response.raise_for_status();r=response.json();immutable(out/'new-run.json',canonical(r))
    assert (r['config']['max_images'],r['config']['max_calls'],r['config']['max_local_corrections'])==(1,6,0)
    assert r['config']['auto_continue'] is True and r['config']['token_policy']['planner']['max_tokens']==32768
    scope=dict(run_id=r['id'],config_sha256=r['config_sha256'],approval_text=approval,amendment=None,
        project_cap_microusd=20000000,budget_microusd=budget,max_calls=6,max_images=1,new_images=1,
        description_sha256=digest(description.encode()),settled_calls=2,expires=time.time()+7200,
        liabilities=[dict(call_id=x['id'],request_sha256=digest(x['request'].encode()),amount=x['amount']) for x in unknown])
    aid=s.acknowledge_liabilities(scope)
    with s.g.connect() as db:assert json.loads(db.execute('SELECT record FROM hybrid_liability_authorizations WHERE id=?',(aid,)).fetchone()[0])==scope
    auth={k:scope[k] for k in ['config_sha256','budget_microusd','max_calls','max_images','expires']};auth['liability_authorization']=aid
    immutable(ROOT/'data/hybrid-authorizations'/(r['id']+'.json'),canonical(auth));immutable(out/'authorization.json',canonical(scope))
    c.post('/api/hybrid-runs/'+r['id']+'/resume',json={}).raise_for_status()
    got=c.get('/api/hybrid-runs/'+r['id']);got.raise_for_status();immutable(out/'launch-readback.json',canonical(got.json()))
    print(json.dumps(dict(run_id=r['id'],phase=got.json()['phase'],acknowledgment_id=aid,budget_microusd=budget,held_effective_before=account['effective_microusd'])))
