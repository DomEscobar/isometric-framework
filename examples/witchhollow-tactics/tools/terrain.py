"""Witchhollow Tactics — continuous terrain authoring.

Paints one continuous landscape canvas (2:1 iso, 72x36 tiles) and slices it into
aligned per-tile PNGs so the engine reassembles a seamless ground.

Layout (8 cols x 7 rows, r0 = top):
r0: G G G G E E E W
r1: G G G G G E E W
r2: G G P P D D G W
r3: G P P P D D G W
r4: G P P P F G G W
r5: Y Y P P G G G G
r6: Y Y Y P G G G G
G grass, Y yard, P path, D dais (elevated), F fountain (prop), E enemy grass, W water.
"""
from __future__ import annotations
import os, math
import numpy as np
from scipy import ndimage
from PIL import Image

HOST = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ART = os.path.join(HOST, 'art')
TERRAIN = os.path.join(ART, 'terrain')
TARGETS = os.path.join(ART, 'targets')
os.makedirs(TERRAIN, exist_ok=True)
os.makedirs(TARGETS, exist_ok=True)

PAD = 40
TW, TH = 72, 36
COLS, ROWS = 8, 7
WATER_TILES = [(7, r) for r in range(7)]
DAIS_TILES = [(4, 2), (5, 2), (4, 3), (5, 3)]
STEP_TILE = (3, 3)

def world_to_canvas(x, y): return (x + PAD, y + PAD + 126)
def tile_center(c, r): return world_to_canvas((c + r) * TW // 2, (r - c) * TH // 2)
CANVAS_W = (COLS + ROWS - 1) * 36 + 2 * PAD   # 548
CANVAS_H = 126 + 108 + 2 * PAD                # 314

def hex_rgb(v):
    return ((v >> 16) & 255, (v >> 8) & 255, v & 255)

# ---------------------------------------------------------------- noise
def octave(shape, seed, scale, strength):
    rng = np.random.default_rng(seed)
    gs = (max(2, int(np.ceil(shape[0]/scale))+1), max(2, int(np.ceil(shape[1]/scale))+1))
    f = ndimage.zoom(rng.random(gs), (shape[0]/gs[0], shape[1]/gs[1]), order=1)[:shape[0], :shape[1]]
    return np.clip(f * strength, 0, 1)

def make_noise(shape, seed, octs=((30, 1.0), (10, 0.55), (3.5, 0.28))):
    acc = sum(octave(shape, seed + i*131, s, st) for i, (s, st) in enumerate(octs))
    return np.clip(acc / sum(st for _, st in octs), 0, 1)

# 4 bands x 2 variants: (band, variant) -> rgb
R = {}
def _add(name, pairs):
    R[name] = [hex_rgb(c) for pair in pairs for c in pair]
_add('grass', [(0xb9d194,0xcfe6a8),(0x9fbf7f,0xb4d494),(0x80a269,0x97b880),(0x64885a,0x55754b)])
_add('path',  [(0xd4bd94,0xe0c79c),(0xc2a57c,0xd0b286),(0xa8895f,0xb8966a),(0x8a6d48,0x77553a)])
_add('yard',  [(0xefdfba,0xf7e8c4),(0xe0ca99,0xecd9a8),(0xc7ae7a,0xd8c28e),(0xa98f5f,0x937847)])
_add('water', [(0xa9e4e2,0xc4f0ea),(0x8ad0d2,0x9bdcda),(0x63b6bd,0x74c6c8),(0x4296a6,0x337f90)])
_add('bank',  [(0xc9bd90,0xdbcba0),(0xab9c72,0xbbaa7e),(0x8d8057,0x9d9064),(0x71653f,0x5f5232)])
_add('dais',  [(0xecddb8,0xf6e8c2),(0xdbc696,0xead7a9),(0xc0a878,0xd0bb8c),(0xa18d5e,0x8b7449)])

def material_field(name, noise, seed):
    idx = np.clip(np.digitize(noise, np.cumsum([0.15, 0.32, 0.33, 0.20]), right=True), 0, 3)
    v = (octave(noise.shape, seed, 4.5, 1.0) > 0.5).astype(np.uint8)
    tone = np.array(R[name], dtype=np.uint8).reshape(4, 2, 3)
    return tone[idx, v]

def paint_where(canvas, color_field, mask):
    canvas[:] = np.where((mask[..., None] if mask.ndim == 2 else mask) > 0, color_field, canvas)

# ---------------------------------------------------------------- primitives
def ellipse_mask(shape, cx, cy, rx, ry):
    yy, xx = np.mgrid[0:shape[0], 0:shape[1]]
    d = np.sqrt(((xx - cx) / rx) ** 2 + ((yy - cy) / ry) ** 2)
    return (d <= 1.0).astype(np.float64)

def ribbon_mask(shape, points, width, seed, wobble=0.0):
    yy, xx = np.mgrid[0:shape[0], 0:shape[1]]
    dist = np.full(shape, 1e9, dtype=np.float64)
    for (x0, y0), (x1, y1) in zip(points[:-1], points[1:]):
        vx, vy = x1 - x0, y1 - y0
        L2 = vx*vx + vy*vy
        t = np.clip(((xx - x0) * vx + (yy - y0) * vy) / L2, 0, 1)
        dist = np.minimum(dist, np.hypot(xx - (x0 + t * vx), yy - (y0 + t * vy)))
    if wobble > 0:
        n = make_noise(shape, seed, ((14, 1.0), (5, 0.6)))
        dist += (n - 0.5) * 2 * wobble
    return (dist <= width).astype(np.float64)

def blur_mask(mask, sigma=1.4):
    return (ndimage.gaussian_filter(mask.astype(np.float64), sigma) > 0.5).astype(np.float64)

def dilate_mask(mask, px):
    return ndimage.binary_dilation(mask > 0, iterations=px).astype(np.float64)

def tile_diamond_mask(shape, c, r):
    """Engine diamond for tile (c,r) within its own 72x36 slice coords."""
    H, W = shape
    yy, xx = np.mgrid[0:H, 0:W]
    d = np.abs(xx - W/2) / (W/2) + np.abs(yy - H/2) / (H/2)
    return (d <= 1.0).astype(np.float64)

# ---------------------------------------------------------------- painting
GRID = [
    'GGGGEEEW',
    'GGGGGEEW',
    'GGPPDDGW',
    'GPPPDDGW',
    'GPPPFGGW',
    'YYPPGGGW',
    'YYYPGGGW',
]

def build_canvas(seed=20260910):
    H, W = CANVAS_H, CANVAS_W
    canvas = np.zeros((H, W, 3), dtype=np.uint8)
    ones = np.ones((H, W))
    # 1. grass base
    paint_where(canvas, material_field('grass', make_noise((H, W), seed), seed + 1), ones)
    # 2. water stream (east edge, vertical, exits south edge)
    wp = [tile_center(7, r) for r in range(7)]
    water_mask = ribbon_mask((H, W), wp, 30, seed + 40, wobble=4.5)
    # keep every drop inside the c7 column diamonds so animated overlays join cleanly
    col7 = np.zeros((H, W))
    for r in range(7):
        cxx, cyy = tile_center(7, r)
        col7 = np.maximum(col7, ellipse_mask((H, W), cxx, cyy, 36, 18))
    water_mask = water_mask * (col7 > 0)
    paint_where(canvas, material_field('water', make_noise((H, W), seed + 2), seed + 3), water_mask)
    # 3. wet bank ribbon
    bank_mask = dilate_mask(water_mask, 6) - water_mask
    paint_where(canvas, material_field('bank', make_noise((H, W), seed + 4), seed + 5), blur_mask(bank_mask, 1.2))
    # 4. yard paving south-west
    yd = [tile_center(c, r) for r in (5, 6) for c in (0, 1, 2)]
    yard_mask = np.zeros((H, W))
    for cx, cy in yd:
        yard_mask = np.maximum(yard_mask, ellipse_mask((H, W), cx, cy, 46, 32))
    yard_mask = blur_mask(yard_mask, 1.6)
    paint_where(canvas, material_field('yard', make_noise((H, W), seed + 6), seed + 7), yard_mask)
    # 5. path ribbon from yard north-east, widening toward the fountain/dais
    pp = [tile_center(2, 6), tile_center(2.4, 5), tile_center(2.2, 4), tile_center(3.1, 3), tile_center(2.6, 2.1)]
    path_mask = blur_mask(ribbon_mask((H, W), pp, 21, seed + 8, wobble=3.2), 1.1)
    paint_where(canvas, material_field('path', make_noise((H, W), seed + 9), seed + 10), path_mask)
    # 6. worn path fringe: yard chips into path, grass tufts into path edge
    dais_mask = np.zeros((H, W))
    for c, r in DAIS_TILES:
        dais_mask = np.maximum(dais_mask, ellipse_mask((H, W), *tile_center(c, r), 41, 24))
    paint_where(canvas, material_field('dais', make_noise((H, W), seed + 11), seed + 12), dais_mask)
    # 7. pebble details: path + yard (sparse, lattice-hashed)
    return canvas, {'water_mask': water_mask > 0, 'bank_binary': (bank_mask > 0),
                    'yard_binary': yard_mask > 0, 'path_binary': path_mask > 0,
                    'dais_binary': dais_mask > 0}

def add_tuft_fringe(canvas, meta, seed=20260910):
    """Crisp interlocking clusters: light grass blades poke into path/yard edges,
    path-colored specks creep into the grass at the fringe."""
    H, W = canvas.shape[:2]
    rng = np.random.default_rng(seed + 700)
    path = meta['path_binary']; yard = meta['yard_binary']
    grass_light = np.array(R['grass'], dtype=np.uint8).reshape(4,2,3)[0][0]
    path_dark = np.array(R['path'], dtype=np.uint8).reshape(4,2,3)[3][0]
    # distance to material edge
    def edge_pixels(mat, band=2):
        eroded = ndimage.binary_erosion(mat, iterations=band)
        return mat & ~eroded
    pe = edge_pixels(path, band=2)
    ye = edge_pixels(yard, band=2)
    for y in range(1, H-1):
        for x in range(1, W-1):
            if pe[y, x] and rng.random() < 0.16:
                # grass tuft 1-2 px inside the path edge
                canvas[y, x] = grass_light
                if rng.random() < 0.5: canvas[y, x-1] = grass_light
            if ye[y, x] and rng.random() < 0.10:
                canvas[y, x] = grass_light
    # dirt specks creeping into grass just outside path
    pd = ndimage.binary_dilation(path, iterations=3) & ~path
    for y in range(1, H-1):
        for x in range(1, W-1):
            if pd[y, x] and rng.random() < 0.05:
                canvas[y, x] = path_dark
    return canvas

def add_details(canvas, meta, seed=20260910):
    """Sparse, deterministic, non-stamped details: path pebbles, worn yard chips."""
    H, W = canvas.shape[:2]
    rng = np.random.default_rng(seed + 900)
    path = meta['path_binary']; yard = meta['yard_binary']
    # path pebbles: small light stones on a coarse lattice, jittered
    pebbles = [hex_rgb(0xe6d2a4), hex_rgb(0xd3b98a), hex_rgb(0xbba06f)]
    for gx in range(0, W, 9):
        for gy in range(0, H, 7):
            jx, jy = rng.integers(-3, 4, 2)
            x, y = gx + jx, gy + jy
            if not (0 <= x < W and 0 <= y < H): continue
            if not path[y, x]: continue
            if rng.random() < 0.55:
                stone = pebbles[rng.integers(0, 3)]
                canvas[y, x] = stone
                if rng.random() < 0.4 and x + 1 < W: canvas[y, x + 1] = stone
    # yard worn chips: muted green seams between paving stones
    chips = [hex_rgb(0x8f9a63), hex_rgb(0x7d8a56), hex_rgb(0x6d7a4a)]
    for gx in range(0, W, 6):
        for gy in range(0, H, 5):
            jx, jy = rng.integers(-2, 3, 2)
            x, y = gx + jx, gy + jy
            if not (0 <= x < W and 0 <= y < H): continue
            if yard[y, x] and rng.random() < 0.28:
                canvas[y, x] = chips[rng.integers(0, 3)]
    return canvas

# ---------------------------------------------------------------- water overlays
def water_overlay_frames(canvas, meta, n_frames=3):
    """Per water tile: 72x36 RGBA frames with continuous down-flowing wave bands.

    Pattern period of 12 divides the 36-row frame and 4 divides 72 columns, so
    bands join seamlessly across tile seams; phase steps -1 per downstream tile.
    """
    crest = (0xc9, 0xee, 0xe8)   # light crest highlight
    mid = (0x7f, 0xc9, 0xce)     # mid water
    trough = (0x3d, 0x8d, 0x9e)  # dark trough
    frames = []
    for (c, r) in WATER_TILES:
        cx, cy = tile_center(c, r)
        x0, y0 = cx - 36, cy - 18
        slice_rgb = canvas[y0:y0+36, x0:x0+72].copy()
        mask = (meta['water_mask'][y0:y0+36, x0:x0+72]) & (tile_diamond_mask((36, 72), c, r) > 0)
        phase = (4 - r) % 12   # downstream phase decreases by 1 per row
        tile_frames = []
        for f in range(n_frames):
            img = slice_rgb.copy()
            shift = f * 2
            yy, xx = np.mgrid[0:36, 0:72]
            band = (yy + shift + phase) % 12
            tone = np.empty((36, 72, 3), dtype=np.uint8)
            tone[band < 4] = crest
            tone[(band >= 4) & (band < 8)] = mid
            tone[band >= 8] = trough
            # diagonal grain for flow direction: streaks drift down-right
            grain = (xx * 5 + yy * 7 + shift) % 9
            streak = (grain == 0) | (grain == 1)
            tone[streak] = crest
            img[mask] = tone[mask]
            out = np.dstack([img, (mask * 255).astype(np.uint8)])
            tile_frames.append(out)
        frames.append(((c, r), tile_frames))
    return frames

# ---------------------------------------------------------------- exports
def export_all(seed=20260910):
    canvas, meta = build_canvas(seed)
    canvas = add_tuft_fringe(canvas, meta, seed)
    canvas = add_details(canvas, meta, seed)
    # 2x preview (nearest) for review
    big = Image.fromarray(canvas).resize((CANVAS_W*2, CANVAS_H*2), Image.NEAREST)
    big.save(os.path.join(TARGETS, 'ground-target.png'))
    big.save('/tmp/ground_current.png')
    # tile slices
    for r in range(ROWS):
        for c in range(COLS):
            cx, cy = tile_center(c, r)
            x0, y0 = cx - 36, cy - 18
            Image.fromarray(canvas[y0:y0+36, x0:x0+72]).save(
                os.path.join(TERRAIN, f'tile_{c}_{r}.png'))
    # dais top slices (same surface; sides come from side strip)
    for (c, r) in DAIS_TILES:
        cx, cy = tile_center(c, r)
        x0, y0 = cx - 36, cy - 18
        Image.fromarray(canvas[y0:y0+36, x0:x0+72]).save(
            os.path.join(TERRAIN, f'dais_{c}_{r}.png'))
    # step top slice (stone slab under (3,3))
    cx, cy = tile_center(*STEP_TILE)
    x0, y0 = cx - 36, cy - 18
    Image.fromarray(canvas[y0:y0+36, x0:x0+72]).save(os.path.join(TERRAIN, 'step_top.png'))
    # side stone strip: repeatable 72x18 vertical face
    side = np.zeros((18, 72, 3), dtype=np.uint8)
    # three staggered rows of stones with mortar
    for row, (yy, off) in enumerate([(0, 0), (6, 12), (12, -6)]):
        x = off % 24 - 24
        while x < 72:
            w = 20 + (x * 7) % 5
            for dx in range(w):
                for dy in range(5):
                    px, py = x + dx, yy + dy
                    if 0 <= px < 72 and 0 <= py < 18:
                        edge = dy == 0 or dx == 0
                        mortar = (dy == 4) or (dx == w - 1)
                        mort = hex_rgb(0x8f7a4d); edg = hex_rgb(0xbfa878); mid8 = hex_rgb(0xdbc696)
                        if mortar:
                            side[py, px] = mort
                        elif edge:
                            side[py, px] = edg
                        else:
                            side[py, px] = mid8
            x += w + 2
    Image.fromarray(side).save(os.path.join(TERRAIN, 'side_stone.png'))
    # water overlays
    frames = water_overlay_frames(canvas, meta)
    for (c, r), tile_frames in frames:
        for f, fr in enumerate(tile_frames):
            Image.fromarray(fr).save(os.path.join(TERRAIN, f'water_{c}_{r}_f{f}.png'))
    np.save(os.path.join(TERRAIN, 'meta.npy'), canvas)
    print('exported tiles, dais, step, side, water, ground-target')

if __name__ == '__main__':
    export_all()
