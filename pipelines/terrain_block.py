"""Frozen-grid blockout: guide, composite, plate helpers for terrain assembly.

usage:
  terrain_block.py guide <world.json> <out.png>
  terrain_block.py scene <world.json> <materials-dir> <out-dir> (--plate <painted.png> | --textured) [--exact water,sand] [--faces <height-painting.png>]
The pipeline projects (x-y, x+y), the framework (c+r, r-c): pipeline cell (x, y) becomes framework (c=H-1-y, r=x).
Tops are cut from a plate painted at ground level, so no painted cliff can land on a walkable cell. Stair tops and
all side faces are structure and come from generated materials. A tile has one sideTexture for both faces.
"""
import io
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

from hybrid_painted_scene import BACKGROUND, SurfaceField, _Canvas, _faces, _paint_face, _paint_top, provider_frame, register

TILE_W, TILE_H = 48, 24
HALF_W, HALF_H = TILE_W // 2, TILE_H // 2
BASE_DEPTH = 8
OUTSIDE = -8
SEAM = 12
FEATHER = 1.5
STRIP_HEIGHT = {'cliff': 40, 'soil': 20, 'stone': 24}
FACE_MATERIAL = {'plateau': 'cliff', 'stairs': 'stone'}


def flat(world):
    W, H = world['width'], world['height']
    return {**world, 'heights': [[0] * W for _ in range(H)], 'transitions': [],
            'origin': [H * HALF_W + HALF_W, 80], 'canvas': [(W + H) * HALF_W + 48, (W + H) * HALF_H + 112]}


def guide(world):
    """Technical-color plate of the real surface field, all cells drawn at ground level."""
    field, ground = SurfaceField(world), flat(world)
    canvas = _Canvas(ground)
    for y in range(world['height']):
        for x in range(world['width']):
            _paint_top(canvas, field, x, y, 0)
    for face in _faces(ground):
        _paint_face(canvas, field, *face)
    size, offset = provider_frame(ground)
    framed = Image.new('RGB', size, BACKGROUND)
    framed.paste(Image.fromarray(canvas.image), offset)
    out = io.BytesIO()
    framed.save(out, format='PNG')
    return out.getvalue()


def swatch(path, size):
    image = Image.open(path).convert('RGB')
    k = max(size[0] / image.width, size[1] / image.height)
    image = image.resize((round(image.width * k), round(image.height * k)), Image.Resampling.LANCZOS)
    return np.asarray(image)[:size[1], :size[0]]


def strip(path, height):
    """Material strip at the given height, made horizontally periodic by cross-fading its ends."""
    image = Image.open(path).convert('RGB')
    image = np.asarray(image.resize((round(image.width * height / image.height), height), Image.Resampling.LANCZOS), np.float32)
    ramp = np.linspace(0, 1, SEAM)[None, :, None]
    body = image[:, :-SEAM].copy()
    body[:, :SEAM] = image[:, -SEAM:] * (1 - ramp) + body[:, :SEAM] * ramp
    return body.astype(np.uint8)


def textured_plate(world, materials):
    """Surface field at ground level, each label sampled from its material swatch in screen space."""
    field, ground = SurfaceField(world), flat(world)
    width, height = ground['canvas']
    textures = np.stack([swatch(materials / f'material-{name}.png', (width, height)) for name in field.names])
    plate = np.zeros((height, width, 3), np.uint8)
    plate[:] = BACKGROUND
    labels = np.full((height, width), -1, np.int8)
    ox, oy = ground['origin']
    SY, SX = np.mgrid[:height, :width] + .5
    a, b = (SX - ox) / HALF_W, (SY - oy) / HALF_H
    wx, wy = (a + b) / 2, (b - a) / 2
    inside = (wx >= 0) & (wx < world['width']) & (wy >= 0) & (wy < world['height'])
    labels[inside] = field.labels_at(wx[inside], wy[inside])
    rows, cols = np.nonzero(inside)
    plate[rows, cols] = textures[labels[rows, cols], rows, cols]
    return plate, labels, field.names


def _face_material(cell, lift):
    return FACE_MATERIAL.get(cell, 'cliff' if lift > 0 else 'soil')


def composite(plate, textured, labels, names, exact):
    """Exact labels come from the textured plate; a narrow feather hides the seam without moving it past the cell."""
    mask = np.isin(labels, [names.index(n) for n in exact if n in names])
    soft = np.asarray(Image.fromarray((mask * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(FEATHER)), np.float32) / 255
    soft = np.maximum(soft, mask)[..., None]
    return (plate * (1 - soft) + textured * soft).astype(np.uint8)


def _sample(canvas, x, y):
    height, width = canvas.shape[:2]
    xi, yi = np.floor(x).astype(int), np.floor(y).astype(int)
    inside = (xi >= 0) & (xi < width) & (yi >= 0) & (yi < height)
    out = np.zeros(x.shape + (3,), np.uint8)
    out[inside] = canvas[yi[inside], xi[inside]]
    return out


def face_from_painting(canvas, origin, x, y, lift, south):
    """Side strip at the true face. Pre-brightened because the framework darkens both faces from one texture."""
    ox, oy = origin
    cx, cy = ox + (x - y) * HALF_W, oy + (x + y + 1) * HALF_H - lift
    tu, tv = np.meshgrid(np.arange(HALF_W) + .5, np.arange(BASE_DEPTH + lift) + .5)
    if south:
        strip, shade = _sample(canvas, cx - HALF_W + tu, cy + tu * HALF_H / HALF_W + tv), .68
    else:
        strip, shade = _sample(canvas, cx + tu, cy + HALF_H - tu * HALF_H / HALF_W + tv), .82
    return np.clip(strip / shade, 0, 255).astype(np.uint8)


def scene(world, materials, plate, name, exact=('stone',), painted=None):
    W, H, cells, heights = world['width'], world['height'], world['cells'], world['heights']
    textured, labels, names = textured_plate(world, materials)
    plate = composite(plate if plate is not None else textured, textured, labels, names, exact)
    strips = {m: strip(materials / f'material-{m}.png', h) for m, h in STRIP_HEIGHT.items()}
    ox, oy = flat(world)['origin']

    def z(x, y):
        return heights[y][x] if 0 <= x < W and 0 <= y < H else OUTSIDE

    faces, textures, tiles = [], {}, {}
    scene_map = [[None] * H for _ in range(W)]
    for y in range(H):
        for x in range(W):
            c, r, lift = H - 1 - y, x, z(x, y)
            cx, cy = ox + (x - y) * HALF_W, oy + (x + y + 1) * HALF_H
            key = f'c{c}r{r}'
            textures[key + '-top'] = {'image': 'atlas', 'frame': {'x': cx - HALF_W, 'y': cy - HALF_H, 'width': TILE_W, 'height': TILE_H}}
            south = lift - z(x, y + 1) >= lift - z(x + 1, y)
            if painted is not None:
                faces.append((key + '-side', face_from_painting(painted, world['origin'], x, y, lift, south)))
            else:
                material = strips[_face_material(cells[y][x], lift)]
                depth = min(BASE_DEPTH + lift, material.shape[0])
                start = (x if south else -y) * HALF_W % material.shape[1]
                columns = (np.arange(HALF_W) + start) % material.shape[1]
                faces.append((key + '-side', material[:depth, columns]))
            top = plate[cy - HALF_H // 2:cy + HALF_H // 2, cx - HALF_W // 2:cx + HALF_W // 2].reshape(-1, 3).mean(0)
            tiles[key] = {'color': int(top[0]) << 16 | int(top[1]) << 8 | int(top[2]), 'walkable': cells[y][x] != 'water',
                          'elevation': lift, 'texture': key + '-top', 'sideTexture': key + '-side'}
            scene_map[r][c] = key
    per_row = plate.shape[1] // HALF_W
    tallest = max(f.shape[0] for _, f in faces)
    atlas = np.zeros((plate.shape[0] + -(-len(faces) // per_row) * tallest, plate.shape[1], 3), np.uint8)
    atlas[:plate.shape[0]] = plate
    for i, (key, face) in enumerate(faces):
        ax, ay = (i % per_row) * HALF_W, plate.shape[0] + (i // per_row) * tallest
        atlas[ay:ay + face.shape[0], ax:ax + HALF_W] = face
        textures[key] = {'image': 'atlas', 'frame': {'x': ax, 'y': ay, 'width': HALF_W, 'height': face.shape[0]}}
    sx, sy = world['spawn']
    return atlas, {'version': 1, 'name': name, 'tileWidth': TILE_W, 'tileHeight': TILE_H,
                   'assets': {'images': {'atlas': {'url': 'atlas.png', 'sampling': 'nearest'}}, 'textures': textures},
                   'map': scene_map, 'tiles': tiles, 'maxStepHeight': 8,
                   'entityTypes': {'probe': {'visual': {'kind': 'actor', 'color': 0xe0403a}, 'bodyHeight': 48}},
                   'entities': [{'id': 'probe', 'type': 'probe', 'c': H - 1 - sy, 'r': sx}], 'controlledId': 'probe'}


def main():
    command, world = sys.argv[1], json.loads(Path(sys.argv[2]).read_text())
    if command == 'guide':
        Path(sys.argv[3]).parent.mkdir(parents=True, exist_ok=True)
        Path(sys.argv[3]).write_bytes(guide(world))
        return
    materials, out = Path(sys.argv[3]), Path(sys.argv[4])
    plate = register(flat(world), Path(sys.argv[sys.argv.index('--plate') + 1]).read_bytes())[0] if '--plate' in sys.argv else None
    exact = ('stone', *sys.argv[sys.argv.index('--exact') + 1].split(',')) if '--exact' in sys.argv else ('stone',)
    painted = register(world, Path(sys.argv[sys.argv.index('--faces') + 1]).read_bytes())[0] if '--faces' in sys.argv else None
    atlas, data = scene(world, materials, plate, out.name, exact, painted)
    out.mkdir(parents=True, exist_ok=True)
    Image.fromarray(atlas).save(out / 'atlas.png')
    Image.fromarray(atlas[:flat(world)['canvas'][1]]).save(out / 'plate.png')
    (out / 'scene.json').write_text(json.dumps(data))
    print(json.dumps({'scene': out.name, 'atlas': list(atlas.shape[:2])}))


if __name__ == '__main__':
    main()
