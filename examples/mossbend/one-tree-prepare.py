"""Bounded image-first extraction test; uses existing generated inputs only.

One measured foreground mask, roots/contact bed retained in the ground. An exact
recomposition check is necessary but not sufficient: inspect the hidden ground
and actor occlusion separately. No claim of automatic segmentation.
"""
from pathlib import Path
from PIL import Image, ImageDraw, ImageChops
import json, hashlib
A=Path(__file__).parent/'art'; O=A/'one-tree';O.mkdir(exist_ok=True)
source=Image.open(A/'scene-second.png').convert('RGBA')
clean=Image.open(A/'ground-raw.png').convert('RGBA')
mask=Image.new('L',source.size);d=ImageDraw.Draw(mask)
# The chosen western tree is isolated from the other crowns. Trace an envelope
# around its foliage, then its trunk. Root fingers and ground shadows stay below.
points=[(5,59),(12,43),(23,36),(28,27),(46,26),(58,34),(72,36),(83,44),(89,62),(89,85),(77,100),(58,105),(55,116),(57,124),(35,124),(35,110),(33,101),(19,98),(8,83)]
d.rectangle((3,25,88,101),fill=255)
d.polygon([(33,97),(60,97),(55,116),(57,124),(35,124),(35,110)],fill=255)
bg=source.getpixel((0,0))[:3]
for y in range(source.height):
 for x in range(source.width):
  red,green,blue=source.getpixel((x,y))[:3]
  if (red,green,blue)==bg or (blue>green and green>red*1.2) or (y>=98 and x>61):mask.putpixel((x,y),0)
ground=Image.composite(clean,source,mask)
tree=source.copy();tree.putalpha(mask)
recomposed=ground.copy();recomposed.alpha_composite(tree)
assert ImageChops.difference(source,recomposed).getbbox() is None
source.save(O/'original.png');ground.save(O/'ground.png');tree.save(O/'tree.png');mask.save(O/'mask.png');recomposed.save(O/'recomposed.png')
delta=ImageChops.difference(source.convert('RGB'),recomposed.convert('RGB'))
report={'technique':'Original-image pixels plus binary foreground mask; prior generated clean plate only under that mask','providerCallsThisTest':0,'manualMasks':1,'maskMethod':'Hand-selected isolated crown rectangle [3,25,88,101] plus six-point trunk polygon; exclude exact exterior RGB, blue water, and lower-right bank. Earlier polygon envelope was replaced after visible residual leaves/water sliver.','rootPixels':[45,130],'foregroundStopsAtY':124,'changedRecomposedPixels':sum(1 for p in delta.getdata() if p!=(0,0,0)),'sourceSHA256':hashlib.sha256((A/'scene-second.png').read_bytes()).hexdigest(),'cleanPlateSHA256':hashlib.sha256((A/'ground-raw.png').read_bytes()).hexdigest(),'limitation':'Exact recomposition alone does not certify a correct silhouette or reconstructed hidden ground. Local u2netp attempt timed out operationally and was interrupted; final mask is manually constrained.'}
(O/'processing.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
board=Image.new('RGBA',(256*3,224),'#183c36');board.alpha_composite(source,(0,0));board.alpha_composite(ground,(256,0));board.alpha_composite(tree,(512,0));board.resize((1152,336),Image.Resampling.NEAREST).save(O/'inspection.png')
print(json.dumps(report))
