"""Authorized single secondary reviewer call; main-session approval stays separate."""
import sys,os,json
from pathlib import Path
import httpx
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from review import run_review
from generation import Generation
from provider import WaveSpeed
from artifacts import digest,canonical
root=Path(__file__).resolve().parents[1];out=root/'evidence/paid-pilot'
review_id='paid-pilot-01';key=os.environ.get('OPENROUTER_API_KEY','')
if '--hermes-auth' in sys.argv:
 auth=json.loads((Path(os.environ.get('HERMES_HOME') or '/root/.hermes')/'auth.json').read_text())
 pool=[e for e in auth.get('credential_pool',{}).get('openrouter',[]) if isinstance(e,dict) and e.get('access_token') and e.get('label')=='OpenClaw imported']
 assert len(pool)==1 and (pool[0].get('base_url') or 'https://openrouter.ai/api/v1').rstrip('/')=='https://openrouter.ai/api/v1'
 key=pool[0]['access_token'];review_id='paid-pilot-02-verified-auth'
 probe=httpx.get('https://openrouter.ai/api/v1/auth/key',headers={'Authorization':'Bearer '+key},timeout=40);assert probe.status_code==200
with httpx.Client(timeout=60) as c:
 r=c.get('https://openrouter.ai/api/v1/models');r.raise_for_status();meta=next(m for m in r.json()['data'] if m['id']=='google/gemini-3.8-flash')
(out/'reviewer-live-metadata.json').write_bytes(canonical(meta))
reg=json.loads((out/'registered-candidate.json').read_bytes());local=json.loads((out/'registered-local-checks.json').read_bytes())
prompt='You are a secondary evidence reviewer, not owner approval. Return JSON with semantic_verdict and visual_verdict (pass/reject/needs_attention), findings list with specific locations, and uncertainty. Inspect all four actual images. Image 1 is the new canonical geometry GUIDE, not art. Image 2 is the registered genuine generated terrain at final 768x408 play/export resolution; no procedural repaint or masking. Image 3 shows that same output with CYAN authoritative water edge and PINK required swept-actor route edges. Image 4 is STYLE ONLY, never geometry. Assess: water versus canonical water boundary, main path continuity, ground cover that looks like an upright obstacle on required routes, invented tall objects, complete diamond framing, style/palette, final-scale readability and low foliage density. Small grass edge texture is not collision authority. Identify any visibly unacceptable spill, alignment or layer-split defect; unclear => needs_attention, no invented PASS from matching metadata. Technical engine collision tests are separate and not to be inferred from images. State whether suggested repair needs regeneration or can be registered uniformly; do not propose changing collision to hide art drift. Local color-proxy measurements (not semantic truth): '+json.dumps(local)+'. One uniform mapping source->canonical scale '+str(reg['processing_registration']['scale'])+' translation '+str(reg['processing_registration']['translation'])+'. Candidate '+reg['id']+' source sha256 '+reg['source_sha256']+'. No final parent/user approval.'
def post(body):
 with httpx.Client(timeout=150,follow_redirects=False) as c:
  r=c.post('https://openrouter.ai/api/v1/chat/completions',headers={'Authorization':'Bearer '+key},json=body)
  # Never expose response exceptions/headers or retry an ambiguous charge.
  if r.status_code!=200:raise ValueError('review provider HTTP '+str(r.status_code)+'; liability retained; no retry')
  return r.json()
g=Generation(root/'data',WaveSpeed(),json.loads((root/'data/generation-policy.json').read_bytes()))
result=run_review(g,review_id,[(out/'guide.png','1 canonical geometry guide'),(out/'registered.png','2 actual final-resolution registered output'),(out/'registered-boundary-diagnostic.png','3 authoritative water and required route boundary diagnostic'),(out/'style-only.png','4 accepted Waldlicht STYLE ONLY')],prompt,meta,post)
(out/'model-review.json').write_bytes(canonical(result))
print(json.dumps({'verdict':result['verdict'],'actual_model':result['response'].get('model'),'id':result['response'].get('id'),'usage':result['response'].get('usage'),'reserve_microusd':result['reserve_microusd'],'central_status':g.status()},indent=2))
