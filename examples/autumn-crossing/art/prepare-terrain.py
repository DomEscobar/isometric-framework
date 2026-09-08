"""Project one generated material sheet into a continuous, host-owned tile catalog.

Authoring only: uv run --with pillow python prepare-terrain.py
No replacement artwork is painted. RGB comes from the preserved generated source;
deterministic noise only changes the narrow terrain transition mask.
"""
from pathlib import Path
from PIL import Image, ImageEnhance
from functools import cache
import hashlib
import json
import math

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / 'materials-source.png'
source = Image.open(SOURCE).convert('RGB')
assert source.size == (1254, 1254), source.size
CROPS = {'grass': (12, 12, 615, 615), 'dirt': (639, 12, 1242, 615),
         'paving': (12, 639, 615, 1242), 'water': (639, 790, 1242, 1091)}
materials = {}
for name, crop in CROPS.items():
    # A 64px half period reflected into128px preserves edge samples at repeats.
    # Whole source regions are filtered first: sparse sampling causes speckle.
    # Water is already drawn as seen from the camera. A2:1 crop downsampled
    # isotropically to128×64 retains round stones in SCREEN space instead of
    # shearing the image a second time through the ground-plane projection.
    size = (128, 64) if name == 'water' else (64, 64)
    swatch = source.crop(crop).resize(size, Image.Resampling.BOX)
    swatch = ImageEnhance.Color(swatch).enhance(.79 if name == 'dirt' else .88)
    swatch = ImageEnhance.Contrast(swatch).enhance(.88 if name in ('grass', 'dirt') else .95)
    materials[name] = (swatch.load(), size)

@cache
def sample(name, c, r):
    pixels, (width, height) = materials[name]
    def reflected(value, length):
        n = math.floor(value) % (length * 2)
        return n if n < length else length * 2 - 1 - n
    x, y = ((c + r) * 32, (r - c) * 16) if name == 'water' else (c * 32, r * 32)
    return pixels[reflected(x, width), reflected(y, height)]

@cache
def noise(c, r):
    # Continuous at every tile and at the4×4 material repetition boundary.
    return .042 * math.sin(c * math.pi * 3 + math.sin(r * math.pi * 2)) + .026 * math.sin(r * math.pi * 5 - c * math.pi * 2)

def smooth(value):
    t = max(0, min(1, value))
    return t * t * (3 - 2 * t)

@cache
def tile_coordinates(pc, pr):
    points = []
    for y in range(32):
        for x in range(64):
            sx, sy = (x + .5 - 32) / 32, (y + .5 - 16) / 16
            u, v = (sx - sy) / 2 + .5, (sx + sy) / 2 + .5
            points.append((pc + u, pr + v, u, v))
    return points

@cache
def material_tile(name, pc, pr):
    tile = Image.new('RGBA', (64, 32))
    tile.putdata([(*sample(name, c, r), 255) for c, r, _, _ in tile_coordinates(pc, pr)])
    return tile

@cache
def transition_mask(mask, pc, pr):
    values = []
    for c, r, u, v in tile_coordinates(pc, pr):
        n = noise(c, r)
        distances = []
        if not mask & 1: distances.append(u + n)
        if not mask & 2: distances.append(1 - u - n)
        if not mask & 4: distances.append(v + n)
        if not mask & 8: distances.append(1 - v - n)
        values.append(round(smooth(.5 + min(distances) / .24) * 255))
    result = Image.new('L', (64, 32))
    result.putdata(values)
    return result

families = {'grass-dirt': ('grass', 'dirt'), 'dirt-grass': ('dirt', 'grass'),
            'grass-water': ('grass', 'water'), 'water-grass': ('water', 'grass'),
            'dirt-water': ('dirt', 'water'), 'water-dirt': ('water', 'dirt'),
            'paving': ('paving', None)}
frames = {}
catalog = []
for family in families:
    period = 8 if 'water' in family else 4
    for mask in ([15] if family == 'paving' else range(16)):
        for pr in range(period):
            for pc in range(period):
                catalog.append((family, mask, pc, pr))
atlas = Image.new('RGBA', (4096, math.ceil(len(catalog) / 64) * 32))
for index, (family, mask, pc, pr) in enumerate(catalog):
    base, other = families[family]
    # Reuse sampled source rectangles/masks and let Pillow composite in C.
    # Fill the whole rectangle: the runtime owns the sole diamond clip.
    tile = material_tile(base, pc, pr)
    if other is not None and mask != 15:
        tile = Image.composite(tile, material_tile(other, pc, pr), transition_mask(mask, pc, pr))
    x, y = (index % 64) * 64, (index // 64) * 32
    atlas.paste(tile, (x, y))
    key = f'terrain-{family}-{mask}-{pc}-{pr}'
    frames[key] = {'image': 'autumn-terrain', 'frame': {'x': x, 'y': y, 'width': 64, 'height': 32}, 'anchor': {'x': .5, 'y': .5}}
atlas.save(ROOT / 'terrain-atlas.png', optimize=True)
# A small joined patch makes world phase and transition density inspectable.
preview = Image.new('RGBA', (640, 360), (30, 35, 27, 255))
patch = [['water' if r in (4, 5) else 'dirt' if 2 <= c <= 5 and 1 <= r <= 6 else 'grass' for c in range(8)] for r in range(8)]
for r in range(8):
    for c in range(7, -1, -1):
        base = patch[r][c]
        neighbors = [(c - 1, r), (c + 1, r), (c, r - 1), (c, r + 1)]
        def neighbor(nc, nr):
            return patch[nr][nc] if 0 <= nc < 8 and 0 <= nr < 8 else base
        nearby = [neighbor(*p) for p in neighbors]
        alternative = ('water' if 'water' in nearby else 'dirt') if base == 'grass' else ('water' if 'water' in nearby else 'grass') if base == 'dirt' else ('grass' if 'grass' in nearby else 'dirt' if 'dirt' in nearby else 'grass')
        mask = sum(1 << i for i, p in enumerate(neighbors) if neighbor(*p) != alternative)
        period = 8 if 'water' in (base, alternative) else 4
        frame = frames[f'terrain-{base}-{alternative}-{mask}-{c % period}-{r % period}']['frame']
        tile = atlas.crop((frame['x'], frame['y'], frame['x'] + 64, frame['y'] + 32))
        # Authoring preview emulates the renderer's diamond clip exactly once.
        alpha = Image.new('L', (64, 32))
        for py in range(32):
            for px in range(64):
                sx, sy = (px + .5 - 32) / 32, (py + .5 - 16) / 16
                if abs(sx) + abs(sy) <= 1: alpha.putpixel((px, py), 255)
        tile.putalpha(alpha)
        preview.alpha_composite(tile, (64 + (c + r) * 32, 160 + (r - c) * 16))
preview.save(ROOT / 'terrain-preview.png')
(ROOT / 'terrain-frames.json').write_text(json.dumps(frames, separators=(',', ':')) + '\n')
(ROOT / 'terrain-recipe.json').write_text(json.dumps({
    'source': SOURCE.name, 'sha256': hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
    'description': 'Generated material RGB with deterministic projection, phase selection and neighbor transition masks; no independent generated tiles.',
    'sourceCrops': CROPS, 'tileSize': [64, 32],
    'worldPeriod': {'waterAndShoreFamilies': [8, 8], 'otherFamilies': [4, 4]},
    'prefilterSize': {'grassDirtPaving': [64, 64], 'water': [128, 64]},
    'reflectedMaterialSize': {'grassDirtPaving': [128, 128], 'water': [256, 128]},
    'waterSampling': 'Continuous screen space: x=(c+r)*32, y=(r-c)*16. Isotropic source crop preserves stone shape.',
    'alpha': 'Full opaque64×32 rectangles; the runtime applies the sole diamond clip.',
    'maskBits': {'c-1': 1, 'c+1': 2, 'r-1': 4, 'r+1': 8},
    'transitionWidthWorldTiles': .24, 'maximumMaskPerturbationWorldTiles': .068,
    'atlasSize': list(atlas.size), 'textureCount': len(frames),
    'limits': ['Cardinal boundaries only; diagonal concave corners are not a blob47 catalog.',
               'Mirrored periods remain finite: eight tiles for water/shore, four for other materials.',
               'At three-material junctions shore takes priority; water chooses grass before dirt.',
               'Geometry and walking cells remain authoritative; soft artwork edges are not collision outlines.']
}, indent=2) + '\n')
print(json.dumps({'frames': len(frames), 'atlas': atlas.size, 'bytes': (ROOT / 'terrain-atlas.png').stat().st_size}))
