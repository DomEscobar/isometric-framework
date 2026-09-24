"""Assemble block-silhouette terrain from a frozen world grid.

usage:
  terrain_assemble.py quote <world.json> <style.png> <out-dir> --ledger <ledger.jsonl>
  terrain_assemble.py buy   <world.json> <style.png> <out-dir> --ledger <ledger.jsonl> --paid
  terrain_assemble.py scene <world.json> <materials-dir> <plate.png> <out-dir> [--stairs <stairs.png>]
Cap is 11 USD (~10 EUR). Existing materials may be copied into out-dir before buy.
"""
import json
import os
import sys
import time
from decimal import Decimal
from pathlib import Path

import numpy as np
from PIL import Image

from terrain_block import BASE_DEPTH, HALF_H, HALF_W, OUTSIDE, SEAM, STRIP_HEIGHT, TILE_H, TILE_W
from terrain_block import composite, flat, textured_plate
from hybrid_painted_scene import register
from provider import WaveSpeed
from terrain_llm import Ledger


def crop_wall(path):
    """Keep the painted wall band; dark provider padding is not part of the face."""
    image = np.asarray(Image.open(path).convert('RGB'))
    lit = image.max(-1) > 40
    rows = np.flatnonzero(lit.any(1))
    cols = np.flatnonzero(lit.any(0))
    return Image.fromarray(image[rows[0]:rows[-1] + 1, cols[0]:cols[-1] + 1])


def strip(path, height):
    wall = crop_wall(path)
    image = np.asarray(wall.resize((max(SEAM + 1, round(wall.width * height / wall.height)), height),
                                   Image.Resampling.LANCZOS), np.float32)
    ramp = np.linspace(0, 1, SEAM)[None, :, None]
    body = image[:, :-SEAM].copy()
    body[:, :SEAM] = image[:, -SEAM:] * (1 - ramp) + body[:, :SEAM] * ramp
    return body.astype(np.uint8)

ENV = Path(os.environ.get('TERRAIN_ENV_FILE', '/mnt/c/Users/dhuec/.config/layout-terrain-hybrid/environment'))
MODEL = 'meta/muse-image/edit'
MAX_USD = '11'
STYLE = ('Image 1 is STYLE ONLY: match its pixel-art palette, pixel clusters, outlines and lighting; never copy its '
         'layout, island, objects or camera. ')
JOBS = {
    'material-cliff': {
        'aspect_ratio': '21:9',
        'prompt': (STYLE + 'Fill the entire image edge to edge with one flat orthographic FRONT VIEW of a rock-and-soil '
                   'cliff wall for a game tile side face. The wall must touch the top and bottom edges with no empty '
                   'margin. Horizontally seamless. Top 15 percent is a short fringe of overhanging grass blades only; '
                   'the rest is packed brown soil with pebbles. No sky, no ground plane, no path, no boulders sitting '
                   'in front, no perspective, no vignette, no border, text or characters.'),
    },
    'material-soil': {
        'aspect_ratio': '21:9',
        'prompt': (STYLE + 'Fill the entire image edge to edge with one flat orthographic FRONT VIEW of an earthen '
                   'island rim for a game tile side face. Wall touches top and bottom edges, no empty margin. '
                   'Horizontally seamless. Thin grass fringe in the top 10 percent; below that packed soil, roots and '
                   'pebbles. No sky, no ground plane, no path, no perspective, no border, text or characters.'),
    },
    'material-stone-riser': {
        'aspect_ratio': '21:9',
        'prompt': (STYLE + 'Fill the entire image edge to edge with one flat orthographic FRONT VIEW of a weathered grey '
                   'stone stair riser wall for a game tile side face. Wall touches top and bottom edges, no empty '
                   'margin. Horizontally seamless blocks with moss in the cracks. No grass fringe, no sky, no ground '
                   'plane, no stairs in perspective, no border, text or characters.'),
    },
    'stair-top': {
        'aspect_ratio': '1:1',
        'prompt': (STYLE + 'Exactly ONE isometric diamond, nothing else. A single flat TOP FACE of one grey stone stair '
                   'tile, 2:1 isometric, about filling the middle of the frame. Flat weathered stone with tiny moss in '
                   'cracks, no vertical thickness, no stacked blocks, no platform of many tiles. Every pixel outside that '
                   'one diamond is solid magenta #FF00FF. No side faces, cliff, grass, characters or border.'),
    },
}


def load_key():
    if os.environ.get('WAVESPEED_API_KEY'):
        return
    for line in ENV.read_text().splitlines():
        name, _, value = line.partition('=')
        if name.strip() == 'WAVESPEED_API_KEY':
            os.environ['WAVESPEED_API_KEY'] = value.strip()


def buy(out, style, ledger_path, paid):
    load_key()
    client = WaveSpeed()
    client.model_id, client.requires_size = MODEL, False
    client.discover()
    state_path = out / 'state.json'
    state = json.loads(state_path.read_text()) if state_path.exists() else {}
    if 'style' not in state:
        state['style'] = client.upload(style.read_bytes(), 'style.png')
        state_path.write_text(json.dumps({k: v for k, v in state.items() if k != 'style'} | {'uploaded': True}, indent=1))
    pending = {name: spec for name, spec in JOBS.items() if not (out / f'{name}.png').exists()}
    quotes = {}
    for name, spec in pending.items():
        inputs = {'prompt': spec['prompt'], 'image_urls': [state['style']], 'aspect_ratio': spec['aspect_ratio'],
                  'output_format': 'png'}
        quotes[name] = Decimal(str(client.quote(inputs)['discounted_price']))
    ledger = Ledger(ledger_path, MAX_USD)
    print(json.dumps({'quotes': {k: str(v) for k, v in quotes.items()}, 'total_usd': str(sum(quotes.values(), Decimal(0))),
                      'spent_usd': str(ledger.spent()), 'cap_usd': MAX_USD, 'remaining_usd': str(ledger.limit - ledger.spent())}))
    if not paid or not pending:
        return
    lock = ledger.path.with_suffix('.lock')
    lock.open('x').close()
    try:
        for name, spec in pending.items():
            inputs = {'prompt': spec['prompt'], 'image_urls': [state['style']], 'aspect_ratio': spec['aspect_ratio'],
                      'output_format': 'png'}
            call = ledger.reserve(name, quotes[name])
            prediction = client.submit(inputs)['id']
            state.setdefault('predictions', {})[name] = {'id': prediction, 'call': call, 'price': str(quotes[name])}
            state_path.write_text(json.dumps({k: v for k, v in state.items() if k != 'style'} | {'uploaded': True}, indent=1))
            deadline = time.time() + 600
            while (result := client.poll(prediction)).get('status') != 'completed':
                if result.get('status') in ('failed', 'cancelled', 'deleted', 'timeout') or time.time() > deadline:
                    raise SystemExit(f'{name} lieferte nicht ({result.get("status")}); Prediction {prediction} bleibt')
                time.sleep(5)
            (out / f'{name}.png').write_bytes(client.download(result['outputs'][0]))
            Ledger(ledger_path, MAX_USD).settle(call, quotes[name], 'wavespeed:' + prediction)
    finally:
        lock.unlink(missing_ok=True)


def stair_heights(world):
    """8 px steps along the frozen transitions, highest stair cell nearest the plateau."""
    W, H, heights, cells = world['width'], world['height'], world['heights'], world['cells']
    elev = [row[:] for row in heights]
    stairs = {(x, y) for y in range(H) for x in range(W) if cells[y][x] == 'stairs'}
    top = {(x, y) for y in range(H) for x in range(W) if heights[y][x] >= 24 and cells[y][x] != 'stairs'}
    neigh = lambda x, y: ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1))
    queue = [cell for cell in stairs if any(n in top for n in neigh(*cell))]
    step = {cell: 0 for cell in queue}
    while queue:
        cell = queue.pop(0)
        for n in neigh(*cell):
            if n in stairs and n not in step:
                step[n] = step[cell] + 1
                queue.append(n)
    for (x, y) in stairs:
        elev[y][x] = max(0, 24 - 8 * (step.get((x, y), 2) + 1))
    return elev


def punch_magenta(image):
    rgba = np.asarray(image.convert('RGBA')).copy()
    key = (rgba[..., 0] > 200) & (rgba[..., 1] < 80) & (rgba[..., 2] > 200)
    rgba[key, 3] = 0
    return Image.fromarray(rgba)


def stair_diamond(path):
    """One opaque diamond cropped to TILE_W x TILE_H for top faces."""
    stair = punch_magenta(Image.open(path))
    alpha = np.asarray(stair)[..., 3]
    ys, xs = np.nonzero(alpha > 128)
    crop = stair.crop((int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1))
    return crop.resize((TILE_W, TILE_H), Image.Resampling.NEAREST)


def paste_stair_tops(plate, world, heights, stair_path):
    """Stamp the generated stair-top diamond onto each stair cell in the flat plate."""
    stair = stair_diamond(stair_path)
    ox, oy = flat(world)['origin']
    canvas = Image.fromarray(plate).convert('RGBA')
    for y in range(world['height']):
        for x in range(world['width']):
            if world['cells'][y][x] != 'stairs':
                continue
            cx = ox + (x - y) * HALF_W - HALF_W
            cy = oy + (x + y + 1) * HALF_H - HALF_H
            canvas.alpha_composite(stair, (int(cx), int(cy)))
    return np.asarray(canvas.convert('RGB'))


def face_kind(cell, lift):
    if cell == 'stairs':
        return 'stone-riser'
    if lift > 0:
        return 'cliff'
    return 'soil'


def build_scene(world, materials, plate_path, out, stairs_path=None):
    W, H, cells = world['width'], world['height'], world['cells']
    heights = stair_heights(world)
    plate = register(flat(world), Path(plate_path).read_bytes())[0]
    textured, labels, names = textured_plate(world, materials)
    plate = composite(plate, textured, labels, names, ('water', 'sand'))
    if stairs_path and Path(stairs_path).exists():
        plate = paste_stair_tops(plate, world, heights, stairs_path)
    strip_heights = {**STRIP_HEIGHT, 'stone-riser': 24}
    strips = {}
    for name, height in strip_heights.items():
        path = materials / f'material-{name}.png'
        if path.exists():
            strips[name] = strip(path, height)
    if 'stone-riser' not in strips and 'stone' in strips:
        strips['stone-riser'] = strips['stone']
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
            textures[key + '-top'] = {'image': 'atlas', 'frame': {'x': int(cx - HALF_W), 'y': int(cy - HALF_H),
                                                                  'width': TILE_W, 'height': TILE_H}}
            south = lift - z(x, y + 1) >= lift - z(x + 1, y)
            material = strips[face_kind(cells[y][x], lift)]
            depth = min(BASE_DEPTH + max(lift, 0), material.shape[0])
            start = (x if south else -y) * HALF_W % material.shape[1]
            columns = (np.arange(HALF_W) + start) % material.shape[1]
            faces.append((key + '-side', material[:depth, columns]))
            window = plate[max(0, int(cy) - 6):int(cy) + 6, max(0, int(cx) - 12):int(cx) + 12]
            top = window.reshape(-1, 3).mean(0) if window.size else np.array([0, 0, 0])
            tiles[key] = {'color': int(top[0]) << 16 | int(top[1]) << 8 | int(top[2]),
                          'walkable': cells[y][x] != 'water', 'elevation': int(lift),
                          'texture': key + '-top', 'sideTexture': key + '-side'}
            scene_map[r][c] = key
    per_row = max(1, plate.shape[1] // HALF_W)
    tallest = max(face.shape[0] for _, face in faces)
    atlas = np.zeros((plate.shape[0] + -(-len(faces) // per_row) * tallest, plate.shape[1], 3), np.uint8)
    atlas[:plate.shape[0]] = plate
    for i, (key, face) in enumerate(faces):
        ax, ay = (i % per_row) * HALF_W, plate.shape[0] + (i // per_row) * tallest
        atlas[ay:ay + face.shape[0], ax:ax + HALF_W] = face
        textures[key] = {'image': 'atlas', 'frame': {'x': ax, 'y': ay, 'width': HALF_W, 'height': face.shape[0]}}
    sx, sy = world['spawn']
    data = {'version': 1, 'name': out.name, 'tileWidth': TILE_W, 'tileHeight': TILE_H,
            'assets': {'images': {'atlas': {'url': 'atlas.png', 'sampling': 'nearest'}}, 'textures': textures},
            'map': scene_map, 'tiles': tiles, 'maxStepHeight': 8,
            'entityTypes': {'probe': {'visual': {'kind': 'actor', 'color': 0xe0403a}, 'bodyHeight': 48}},
            'entities': [{'id': 'probe', 'type': 'probe', 'c': H - 1 - sy, 'r': sx}], 'controlledId': 'probe'}
    out.mkdir(parents=True, exist_ok=True)
    Image.fromarray(atlas).save(out / 'atlas.png')
    (out / 'scene.json').write_text(json.dumps(data))
    print(json.dumps({'scene': str(out), 'stair_heights': sorted({heights[y][x] for y in range(H) for x in range(W)
                                                                  if cells[y][x] == 'stairs'})}))


def main():
    command = sys.argv[1]
    out = Path(sys.argv[4] if command != 'scene' else sys.argv[5])
    out.mkdir(parents=True, exist_ok=True)
    if command in ('quote', 'buy'):
        world, style = Path(sys.argv[2]), Path(sys.argv[3])
        ledger = Path(sys.argv[sys.argv.index('--ledger') + 1])
        buy(out, style, ledger, command == 'buy' and '--paid' in sys.argv)
        return
    world = json.loads(Path(sys.argv[2]).read_text())
    materials, plate, scene_dir = Path(sys.argv[3]), Path(sys.argv[4]), Path(sys.argv[5])
    stairs = Path(sys.argv[sys.argv.index('--stairs') + 1]) if '--stairs' in sys.argv else materials / 'stair-top.png'
    if not stairs.exists():
        stairs = None
    build_scene(world, materials, plate, scene_dir, stairs)


if __name__ == '__main__':
    main()
