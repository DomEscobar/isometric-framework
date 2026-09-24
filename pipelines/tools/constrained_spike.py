"""No-paid local spike + authenticated free metadata/price checks."""
import sys,json,io
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app import app
from artifacts import canonical,digest
from constrained_adapter import STRATEGY
from constrained_provider import MaskedWaveSpeed,preservation_check
from PIL import Image
import numpy as np
root=Path(__file__).resolve().parents[1]
out=root/'evidence/constrained-recovery';out.mkdir(exist_ok=True,parents=True)
s=app.state.auto_repair;a=s.adapter
parent=s.get('3c932cbd0832cc4707bc8281f828eb837930c89b9dd399ca90223df0f3c697da')
proof=a.constrained_seed(parent)
assert proof['eligible'],proof
w={**parent,'continuation':{'mode':'constrained-mask-recovery','seed_proof':proof},'latest_candidate_id':proof['candidate_id'],'evaluation_id':proof['evaluation_id']}
guide,refs=a.masked_inputs(w);plan=a.plan(w)
for name,raw in [('registered-input.png',refs[0]['raw']),('edit-mask.png',refs[1]['raw']),('guide.png',guide)]:
    (out/name).write_bytes(raw)
schema=MaskedWaveSpeed().discover()
request=dict(prompt=plan['prompt'],image='https://example.invalid/registered-input.png',mask_image='https://example.invalid/edit-mask.png',size='768*408')
price=MaskedWaveSpeed().quote(request)
# Reviewer preflight is free and must work even while paid enable stays closed.
meta=a.reviewer.preflight()
mask=np.array(Image.open(io.BytesIO(refs[1]['raw'])))>0
road=np.array(Image.open(io.BytesIO(a.files(w['frozen']['revision'])['masks/material-street.png'])))>0
assert not (mask&road).any()
result=dict(seed_proof=proof,control=a.control(w),plan=plan,schema=schema,price=price,
            reviewer_model=meta['id'],reviewer_preflight='authenticated_free_success',
            edited_pixels=int(mask.sum()),protected_pixels=int((~mask).sum()),road_edit_overlap=int((mask&road).sum()),
            frame=[768,408],source_identity_check=preservation_check(refs[0]['raw'],refs[0]['raw'],refs[1]['raw']),
            provider_support='live mask_image field; white edits / black preserves; no separate guide/reference field; native output preservation still unproven',
            source_sha256=digest(refs[0]['raw']),mask_sha256=digest(refs[1]['raw']),budget=s.g.status(),
            paid_calls=0,uploads=0)
(out/'free-spike.json').write_bytes(canonical(result))
print(json.dumps({k:v for k,v in result.items() if k not in ('seed_proof','plan','schema')},indent=2))
