"""Prepare the generated orthographic rock face; no replacement pixels painted."""
from pathlib import Path
from PIL import Image
import hashlib, json

root = Path(__file__).resolve().parent
source = root / 'cliff-source.png'
image = Image.open(source).convert('RGB')
# Omit the central dividing line and use the plain material for shared banks.
crop = (8, 8, image.width // 2 - 8, image.height - 8)
face = image.crop(crop).resize((64, 64), Image.Resampling.BOX)
face.save(root / 'cliff-material.png')
atlas = Image.new('RGB', (128, 64))
for phase in range(4):
    x0 = crop[0] + (crop[2] - crop[0]) * phase // 4
    x1 = crop[0] + (crop[2] - crop[0]) * (phase + 1) // 4
    patch = image.crop((x0, crop[1], x1, crop[3])).resize((32, 64), Image.Resampling.BOX)
    atlas.paste(patch, (phase * 32, 0))
atlas.save(root / 'cliff-atlas.png')
(root / 'cliff-recipe.json').write_text(json.dumps({
    'source': source.name, 'sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
    'crop': crop, 'size': [64, 64], 'filter': 'BOX',
    'phaseAtlas': {'size': [128, 64], 'frames': 4, 'frameSize': [32, 64],
                   'selection': '(c + r) modulo4; source horizontal quarters preserve broader rock masses'},
    'role': 'Vertical side material on raised dry terrain; collision comes from tile elevation.',
    'limits': ['The crop is not proven seamless; repeated cracks remain possible.']
}, indent=2) + '\n')
