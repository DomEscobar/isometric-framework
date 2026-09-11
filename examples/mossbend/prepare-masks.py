"""Host-owned measured masks. No generated scenery is repainted by this script."""
from pathlib import Path
from PIL import Image, ImageDraw
import json
A=Path(__file__).parent/'art'
im=Image.open(A/'scene-second.png').convert('RGB')
mask=Image.new('RGB',im.size); d=ImageDraw.Draw(mask)
# Missing guide trees. Masks deliberately overlap foliage/ground in these areas;
# all pixels outside these author-selected regions are restored after editing.
d.polygon([(64,74),(87,72),(96,90),(89,106),(85,114),(71,116),(68,108),(59,92)],fill='white')
d.polygon([(119,133),(141,129),(157,143),(155,160),(145,168),(147,174),(137,178),(127,174),(127,164),(115,154)],fill='white')
mask.save(A/'missing-trees-mask.png')
im.resize((768,672),Image.Resampling.NEAREST).save(A/'scene-second-inspection.png')
print(json.dumps({'image':im.size,'mask':'missing-trees-mask.png'}))
