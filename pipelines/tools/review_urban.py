"""Authorized single secondary reviewer call; main-session approval stays separate."""
import sys,os,json
from pathlib import Path
import httpx
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from review import run_review
from generation import Generation
from provider import WaveSpeed
from artifacts import digest,canonical
root=Path(__file__).resolve().parents[1];out=root/'evidence/urban-pilot'
review_id='urban-pilot-01';key=os.environ.get('OPENROUTER_API_KEY','')
if '--hermes-auth' in sys.argv:
 auth=json.loads((Path(os.environ.get('HERMES_HOME') or '/root/.hermes')/'auth.json').read_text())
 pool=[e for e in auth.get('credential_pool',{}).get('openrouter',[]) if isinstance(e,dict) and e.get('access_token') and e.get('label')=='OpenClaw imported']
 assert len(pool)==1 and (pool[0].get('base_url') or 'https://openrouter.ai/api/v1').rstrip('/')=='https://openrouter.ai/api/v1'
 key=pool[0]['access_token'];review_id='urban-pilot-01-verified-auth'
 probe=httpx.get('https://openrouter.ai/api/v1/auth/key',headers={'Authorization':'Bearer '+key},timeout=40);assert probe.status_code==200
assert '--hermes-auth' in sys.argv, 'Use explicitly verified authorized pool credential; no blind fallback'
with httpx.Client(timeout=60) as c:
 r=c.get('https://openrouter.ai/api/v1/models');r.raise_for_status();meta=next(m for m in r.json()['data'] if m['id']=='google/gemini-3.8-flash')
(out/'reviewer-live-metadata.json').write_bytes(canonical(meta))
reg=json.loads((out/'registered-candidate.json').read_bytes());local=json.loads((out/'registered-local-checks.json').read_bytes())
prompt='You are a secondary image evidence reviewer, not owner approval. Return JSON with semantic_verdict and visual_verdict (pass/reject/needs_attention), specific findings and uncertainty. Four images: 1 new canonical urban geometry guide (gray street, warm cream sidewalks, green protected planting); 2 actual direct-original uniform-scalar output at final 768x408 native game/export size; 3 real provider source (review thumbnail retains aspect); 4 user JPEG decoded losslessly to PNG STYLE ONLY, never arrangement. Assess ground-only urban style, crisp fine pixel detail, friendly light palette, no cars/buses/people/buildings/trees/upright props; no traffic simulation. Required pedestrian route stays on north sidewalk and is clear per proxy. Technical player CAN walk empty street; planting and reserved bench/kiosk rectangles are blocked, no production props yet. Independently assess painted gray road versus planned width, curb edges, paving, planting protrusions and all sidewalk clearances, not just required route. No blue-water heuristic applies. Exact scalar registration has frame residual below 2 canonical pixels per coordinate but does NOT prove material alignment. Ground-color proxies: '+json.dumps(local)+'. Color thresholds are not semantic truth; low foliage may protrude into otherwise traversable sidewalk. Report these caveats honestly. Do not infer full PASS from frame metadata or routes alone; no proposed collision changes to hide drift. Candidate '+reg['id']+' source SHA '+reg['source_sha256']+'. No final owner approval.'

def post(body):
 with httpx.Client(timeout=150,follow_redirects=False) as c:
  r=c.post('https://openrouter.ai/api/v1/chat/completions',headers={'Authorization':'Bearer '+key},json=body)
  # Never expose response exceptions/headers or retry an ambiguous charge.
  if r.status_code!=200:raise ValueError('review provider HTTP '+str(r.status_code)+'; liability retained; no retry')
  return r.json()
g=Generation(root/'data',WaveSpeed(),json.loads((root/'data/generation-policy.json').read_bytes()))
result=run_review(g,review_id,[(out/'guide.png','1 canonical urban geometry'),(out/'registered.png','2 exact final game/export image'),(out/'original.png','3 real retained provider source; aspect-preserving review thumbnail'),(out/'style-only.png','4 user supplied STYLE ONLY')],prompt,meta,post)
(out/'model-review.json').write_bytes(canonical(result))
print(json.dumps({'verdict':result['verdict'],'actual_model':result['response'].get('model'),'id':result['response'].get('id'),'usage':result['response'].get('usage'),'reserve_microusd':result['reserve_microusd'],'central_status':g.status()},indent=2))
