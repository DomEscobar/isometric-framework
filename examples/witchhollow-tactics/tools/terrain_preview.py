"""Witchhollow Tactics — continuous terrain authoring (v1)."""
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

def world_to_canvas(x, y): return (x + PAD, y + PAD + 126)
def tile_center(c, r): return world_to_canvas((c + r) * TW // 2, (r - c) * TH // 2)
CANVAS_W = (COLS + ROWS) * 36 + 2 * PAD
CANVAS_H = 126 + 108 + 2 * PAD

# ---------------------------------------------------------------- noise
def octave(shape, seed, scale, strength):
    rng = np.random.default_rng(seed)
    gs = (max(2, int(np.ceil(shape[0]/scale))+1), max(2, int(np.ceil(shape[1]/scale))+1))
    f = ndimage.zoom(rng.random(gs), (shape[0]/gs[0], shape[1]/gs[1]), order=1)[:shape[0], :shape[1]]
    return np.clip(f * strength, 0, 1)

def make_noise(shape, seed, octs=((30, 1.0), (10, 0.55), (3.5, 0.28))):
    acc = sum(octave(shape, seed + i*131, s, st) for i, (s, st) in enumerate(octs))
    return np.clip(acc / sum(st for _, st in octs), 0, 1)

# 4 bands x 2 variants per material
R = {}
def hx(*v): return tuple(int(x) for x in v)
R['grass'] = [hx(0xb9,0xd1,0x94), hx(0xcf,0xe6,0xa8), hx(0x9f,0xbf,0x7f), hx(0x80,0xa2,0x69), hx(0x64,0x88,0x5a), hx(0x55,0x75,0x4b), hx(0x47,0x65,0x4a), hx(0x3c,0x55,0x40)]
R['path'] =  [hx(0xd4,0xbd,0x94), hx(0xe0,0xc7,0x9c), hx(0xc2,0xa5,0x7c), hx(0xd0,0xb2,0x86), hx(0xa8,0x89,0x5f), hx(0xb8,0x96,0x6a), hx(0x8a,0x6d,0x48), hx(0x77,0x55,0x3a)]
R['yard'] =  [hx(0xef,0xdf,0xba), hx(0xf7,0xe8,0xc4), hx(0xe0,0xca,0x99), hx(0xec,0xd9,0xa8), hx(0xc7,0xae,0x7a), hx(0xd8,0xc2,0x8e), hx(0xa9,0x8f,0x5f), hx(0x93,0x78,0x47)]
R['water'] = [hx(0xa9,0xe4,0xe2), hx(0xc4,0xf0,0xea), hx(0x8a,0xd0,0xd2), hx(0x9b,0xdc,0xdc), hx(0x63,0xb6,0xbd), hx(0x74,0xc6,0xc8), hx(0x42,0x96,0xa6), hx(0x33,0x7f,0x90)]
R['bank'] =  [hx(0xc9,0xbd,0x90), hx(0xdb,0xcb,0xa0), hx(0xab,0x9c,0x72), hx(0xbb,0xaa,0x7e), hx(0x8d,0x80,0x57), hx(0x9d,0x90,0x64), hx(0x71,0x65,0x3f), hx(0x5f,0x52,0x32)]
R['dais'] =  [hx(0xec,0xdd,0xb8), hx(0xf6,0xe8,0xc2), hx(0xdb,0xc6,0x96), hx(0xea,0xd7,0xa9), hx(0xc0,0xa8,0x78), hx(0xd0,0xbb,0x8c), hx(0xa1,0x8d,0x5e), hx(0x8b,0x74,0x49)]

def material_pixels(name, noise, seed):
    """Return HxWx3 color field for material using band+variant noise."""
    idx = np.digitize(noise, np.cumsum([0.15, 0.32, 0.33, 0.20]), right=True)
    idx = np.clip(idx, 0, 3)
    v = (octave(noise.shape, seed, 4.5, 1.0) > 0.5).astype(np.uint8)
    tone = np.array(R[name], dtype=np.uint8).reshape(4, 2, 3)
    return tone[idx, v]

def paint_where(canvas, color_field, mask):
    m = mask[..., None] if mask.ndim == 2 else mask
    canvas[:] = np.where(m > 0, color_field, canvas)

# ---------------------------------------------------------------- primitives
def ellipse_mask(shape, cx, cy, rx, ry, soft=0.0):
    yy, xx = np.mgrid[0:shape[0], 0:shape[1]]
    d = np.sqrt(((xx - cx) / rx) ** 2 + ((yy - cy) / ry) ** 2)
    m = (d <= 1.0).astype(np.float64)
    if soft > 0:
        band = np.clip((1.0 - d) / (soft / max(rx, ry)), 0, 1)
        m = np.clip(band, 0, 1)
    return m

def ribbon_mask(shape, points, width, seed, wobble=0.0):
    """Distance to polyline <= width, plus optional noise wobble."""
    yy, xx = np.mgrid[0:shape[0], 0:shape[1]]
    dist = np.full(shape, 1e9, dtype=np.float64)
    for (x0, y0), (x1, y1) in zip(points[:-1], points[1:]):
        vx, vy = x1 - x0, y1 - y0
        L2 = vx*vx + vy*vy
        t = np.clip(((xx - x0) * vx + (yy - y0) * vy) / L2, 0, 1)
        px, py = x0 + t * vx, y0 + t * vy
        dist = np.minimum(dist, np.hypot(xx - px, yy - py))
    if wobble > 0:
        n = make_noise(shape, seed, ((14, 1.0), (5, 0.6)))
        dist = dist + (n - 0.5) * 2 * wobble
    return (dist <= width).astype(np.float64)

def blur_mask(mask, sigma=1.4):
    b = ndimage.gaussian_filter(mask.astype(np.float64), sigma)
    return (b > 0.5).astype(np.float64)

def dilate(mask, px, mode='constant'):
    return ndimage.binary_dilation(mask > 0, iterations=px).astype(np.float64)

# ---------------------------------------------------------------- main paint
GRID = [
    'GGGGEEEW',
    'GGGGGEEW',
    'GGPPDDGW',
    'GPPPDDGW',
    'GPPPFGGW',
    'YYPPGGGG',
    'YYYPGGGG',
]

def build_canvas(seed=20260910):
    H, W = CANVAS_H, CANVAS_W
    canvas = np.zeros((H, W, 3), dtype=np.uint8)
    grass_n = make_noise((H, W), seed)
    # grass base everywhere
    paint_where(canvas, material_pixels('grass', grass_n, seed + 1), np.ones((H, W)))

    # ---- water band: vertical stream at c7, wobbled ----
    wp = [tile_center(7, r) for r in range(5)]
    water_mask = ribbon_mask((H, W), wp, 30, seed + 40, wobble=4.5)
    water_n = make_noise((H, W), seed + 2)
    paint_where(canvas, material_pixels('water', water_n, seed + 3), water_mask)

    # ---- wet bank ribbon around water, into grass ----
    bank_core = dilate(water_mask, 6)
    bank_mask = bank_core - water_mask
    bank_n = make_noise((H, W), seed + 4)
    paint_where(canvas, material_pixels('bank', bank_n, seed + 5), blur_mask(bank_mask, 1.2))

    # ---- yard (courtyard paving) south-west ----
    yd = [tile_center(c, r) for r in (5, 6) for c in (0, 1, 2)]
    yard_mask = np.zeros((H, W))
    for cx, cy in yd:
        yard_mask = np.maximum(yard_mask, ellipse_mask((H, W), cx, cy, 44, 30, soft=0.0))
    yard_mask = blur_mask(yard_mask, 1.5)
    yard_n = make_noise((H, W), seed + 6)
    paint_where(canvas, material_pixels('yard', yard_n, seed + 7), yard_mask)

    # ---- path ribbon from yard up through cols 2-3 ----
    pp = [tile_center(2, 6), tile_center(2, 5), tile_center(2, 4), tile_center(3, 3), tile_center(2, 3), tile_center(2, 2)]
    pp = [tile_center(2, 6), tile_center(2.4, 5), tile_center(2.2, 4), tile_center(3.1, 3), tile_center(2.6, 2.1)]
    path_mask = ribbon_mask((H, W), pp, 21, seed + 8, wobble=3.2)
    path_n = make_noise((H, W), seed + 9)
    paint_where(canvas, material_pixels('path', path_n, seed + 10), blur_mask(path_mask, 1.1))

    # ---- dais top ----
    dais_mask = np.zeros((H, W))
    for c in (4, 5):
        for r in (2, 3):
            dais_mask = np.maximum(dais_mask, ellipse_mask((H, W), *tile_center(c, r), 41, 24, soft=0.0))
    paint_where(canvas, material_pixels('dais', make_noise((H, W), seed + 11), seed + 12), dais_mask)

    # ---- worn fringe tufts: light grass clusters on path/yard edges ----
    # boundary = pixels within path/yard mask but near its edge
    return canvas, {'water_mask': water_mask, 'dais_binary': dais_mask.astype(bool)}

canvas, meta = build_canvas()
Image.fromarray(canvas).resize((CANVAS_W * 2, CANVAS_H * 2), Image.NEAREST).save('/tmp/ground_v1_2x.png')
print("canvas", canvas.shape, "saved preview")