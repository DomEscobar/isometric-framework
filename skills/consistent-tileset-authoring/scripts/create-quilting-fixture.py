#!/usr/bin/env python3
"""Create synthetic algorithm diagnostics ONLY, never production artwork."""
import argparse
import json
from pathlib import Path
from PIL import Image

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('out', type=Path)
args = parser.parse_args()
args.out.mkdir(parents=True, exist_ok=False)
for name, color in [('grass', (32, 100, 60)), ('earth', (150, 110, 70))]:
    Image.new('RGB', (32, 32), color).save(args.out / f'{name}.png')
cells = [['earth' if c == 2 else 'grass' for c in range(7)] for _ in range(5)]
recipe = {'version': 1, 'map': {'columns': 7, 'rows': 5, 'tileWidth': 32, 'tileHeight': 16},
          'cells': cells, 'materials': {name: {'source': f'{name}.png'} for name in ['grass', 'earth']},
          'sourceScale': 2, 'seed': 27, 'patch': 24, 'overlap': 6, 'candidates': 4}
scene = {'version': 1, 'name': 'Synthetic quilting diagnostic (not production art)',
         'tileWidth': 32, 'tileHeight': 16, 'map': cells,
         'tiles': {'grass': {'color': 16777215, 'walkable': True}, 'earth': {'color': 16777215, 'walkable': False}},
         'entityTypes': {'actor': {'visual': {'kind': 'box', 'color': 16711680}, 'blocking': True}},
         'entities': [{'id': 'hero', 'type': 'actor', 'c': 0, 'r': 0}], 'controlledId': 'hero'}
for filename, value in [('recipe.json', recipe), ('scene.json', scene)]:
    (args.out / filename).write_text(json.dumps(value, indent=2) + '\n')
print('Synthetic fixtures created; no production-art approval implied.')
