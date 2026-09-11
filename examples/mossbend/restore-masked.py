from pathlib import Path
from PIL import Image, ImageChops
import json
A=Path(__file__).parent/'art'
base=Image.open(A/'scene-second.png').convert('RGBA')
edit=Image.open(A/'scene-addtrees-raw.png').convert('RGBA')
mask=Image.open(A/'missing-trees-mask.png').convert('L')
if edit.size!=base.size: raise ValueError('Edit resized source')
merged=Image.composite(edit,base,mask)
merged.save(A/'scene-composed.png')
merged.resize((768,672),Image.Resampling.NEAREST).save(A/'scene-composed-inspection.png')
outside=ImageChops.multiply(ImageChops.difference(merged.convert('RGB'),base.convert('RGB')).convert('L'),ImageChops.invert(mask))
assert outside.getbbox() is None
print(json.dumps({'outsideMaskUnchanged':True,'size':merged.size}))
