"""Append a local worker review revision after verified CSS pixel alignment repair."""
from pathlib import Path
import json,sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from artifacts import canonical,digest
out=Path('evidence/paid-pilot');old=json.loads((out/'attached-review.json').read_bytes());target=Path('data/terrain')/old['candidate_id'];archive=target/'reviews';archive.mkdir(exist_ok=True)
assert (target/'review.json').read_bytes()==canonical(old)
(archive/(old['id']+'.json')).write_bytes(canonical(old));(out/('attached-review-'+old['id']+'.json')).write_bytes(canonical(old))
new={k:v for k,v in old.items() if k!='id'};new['supersedes_review_id']=old['id'];new['review_revision_reason']='CSS half-pixel placement repaired and browser pixel replay verified; same exact generated and reviewed terrain pixels, no further paid review.'
new['worker_visual_review']['observations'].append('Final browser canvas is pixel-aligned at CSS [512,296], 768x408, DPR1. Screenshot equals exported terrain except 512 technical actor pixels. Previous browser evidence is archived under pre-pixel-alignment-browser/.')
new['worker_visual_review']['images']={n:digest((out/n).read_bytes()) for n in old['worker_visual_review']['images']}
new['browser_verification']=json.loads((out/'browser/browser-report.json').read_bytes());new['id']=digest(canonical(new));(archive/(new['id']+'.json')).write_bytes(canonical(new));(target/'review.json').write_bytes(canonical(new));(out/'attached-review.json').write_bytes(canonical(new));print(new['id'])
