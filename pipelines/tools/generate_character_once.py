"""Explicit one-shot authorized image; paid work ONLY through shared Generation."""
import sys,json,time,io,hashlib,shutil
from pathlib import Path
from PIL import Image
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from artifacts import canonical,digest
from generation import Generation
from character_provider import CharacterProvider
E=ROOT/'assets/character/runs';E.mkdir(parents=True,exist_ok=True)
def save(name,obj): (E/name).write_bytes(canonical(obj))
p=CharacterProvider();g=Generation(ROOT/'data',p,{'approved':False,'total_usd':'10.00','max_attempts':8})
assert not json.loads((ROOT/'data/generation-policy.json').read_bytes())['approved']
if not (E/'binding.json').exists():
    before=g.status();assert before['attempts']==7 and before['reserved_usd']=='4.873712';save('ledger-before.json',before)
    terrain=ROOT/'assets/character/composed.png'
    save('preserved-character-asset.json',{str(terrain.relative_to(ROOT)):digest(terrain.read_bytes())})
    ref=Path('/root/.hermes/cache/images/img_994a0a414b3e.jpg');shutil.copyfile(ref,E/'style-reference-original.jpg')
    Image.open(ref).convert('RGB').save(E/'style-reference.png')
    Image.new('RGB',(768,768),(255,0,255)).save(E/'blank-framing-guide.png')
    prompt='''Create ONE isolated game character, NOT a scene. Input image 1 is ONLY the square framing and perfectly flat magenta background authority; it contains no character geometry. Input image 2 is STYLE ONLY: use its warm cream / terracotta and muted mint JRPG pixel-art design, dark colored stepped contours, charming compact proportions, two or three solid tones per material, carefully designed contiguous pixel clusters. Do NOT reproduce its buildings, terrain, other people or layout.
Draw one full-body medieval village traveller in a neutral standing pose, front three-quarter view facing screen-down-right, viewed from an elevated isometric game camera. Readable rounded chestnut hair silhouette and expressive face; head roughly one third of body height, visibly designed neck/shoulders/arms; warm ochre-rust tunic with cream collar, muted teal short shoulder cape, narrow leather belt and small brown satchel, separate short legs and two distinct leather boots grounded on the same baseline. Both hands readable. Friendly young adult villager, not a warrior. Purposeful asymmetry, clean anatomy, clear recognizable outfit. Match the appealing little characters in input2, not a generic block man.
Render like a carefully enlarged classic 32-bit RPG pixel sprite: solid flat color clusters, hard dark colored pixel contours, 3 tones maximum per fabric, stepped pixel silhouette, deliberate highlights, no dithering or noisy microtexture. No photorealism, smooth anime painting, gradients, blurry antialiasing, 3D render, stick figure, primitive rectangles or blockout. Compose the whole character centered occupying about 65 percent of frame height, with generous empty margins and both complete boots. Single character only, no sheet, no extra views, no labels/text/watermark, no ground patch, no cast shadow. Background must be perfectly solid pure magenta #FF00FF. Never use pink/magenta in the character. Keep character design readable when later reduced to about 40-48 pixels tall against 48x24 ground tiles, while retaining designed source detail now.'''
    binding={'scope':'single-static-character-v1','layout_revision':digest(canonical({'scope':'static-character','authorization':digest((ROOT/'GENERATED_CHARACTER_AUTHORIZATION.md').read_bytes())})),'guide_sha256':digest((E/'blank-framing-guide.png').read_bytes()),'style_sha256':digest((E/'style-reference.png').read_bytes()),'original_jpeg_sha256':digest(ref.read_bytes()),'authorization_sha256':digest((ROOT/'GENERATED_CHARACTER_AUTHORIZATION.md').read_bytes()),'terrain_sha256':digest(terrain.read_bytes()),'prompt':prompt,'roles_explained':['immutable empty framing/background guide, NOT a pose or character','full reference STYLE ONLY'],'attempt_limit':1}
    save('binding.json',binding)
binding=json.loads((E/'binding.json').read_bytes())
if sys.argv[-1]=='prepare':
    schema=p.discover();save('live-schema.json',schema);q=g.quote(binding);save('quote.json',q);print('FREE_AUTH_SCHEMA_QUOTE_OK',q['quote'],q['id']);sys.exit(0)
if sys.argv[-1]=='generate':
    q=json.loads((E/'quote.json').read_bytes());g.policy['approved']=True
    try:
        j=g.confirm(q['id'],binding['layout_revision'],(E/'blank-framing-guide.png').read_bytes(),(E/'style-reference.png').read_bytes());save('generation.json',j)
        print('GENERATION',j['id'],j['status'],j.get('prediction_id'),flush=True)
    finally:
        g.policy['approved']=False;save('ledger-closed.json',g.status())
    if not j.get('prediction_id'):raise RuntimeError('No receipt. STOP. No retry.')
else:j=g.get(json.loads((E/'generation.json').read_bytes())['id'])
for _ in range(120):
    j=g.resume(j['id']);save('generation.json',j)
    print(j['status'],flush=True)
    if j['status'] in ('completed','failed','cancelled','deleted'):break
    time.sleep(3)
if j['status']!='completed':raise RuntimeError('Known receipt not completed; poll this identity only.')
result=p.poll(j['prediction_id']);assert result['id']==j['prediction_id'] and result['status']=='completed';save('provider-readback.json',result)
raw=p.download(j['output_url']);path=E/'provider-original.png'
if path.exists():assert path.read_bytes()==raw
else:path.write_bytes(raw)
im=Image.open(io.BytesIO(raw));assert im.format=='PNG';im.verify()
shutil.copyfile(ROOT/'data'/(j['id']+'.receipt.json'),E/'receipt.json')
save('original-integrity.json',{'sha256':digest(raw),'size':Image.open(io.BytesIO(raw)).size,'prediction_id':j['prediction_id'],'generation_id':j['id'],'quoted_usd':j['exact_quote']['price'],'actual_billing':'not separately reported by provider'})
print('RETAINED_REAL_PROVIDER_OUTPUT',digest(raw),flush=True)
