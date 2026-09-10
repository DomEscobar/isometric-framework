"""Witchhollow Tactics — authored props (transparent sprites).

Upper-left light, slate outlines, warm academy palette. Every prop is drawn
here from primitives; no bundled or generated artwork.
"""
from __future__ import annotations
import os
import numpy as np
from PIL import Image
from random import Random

HOST = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROPS = os.path.join(HOST, 'art', 'props')
os.makedirs(PROPS, exist_ok=True)

OUT = (58, 55, 56)

def canv(w, h):
    return np.zeros((h, w, 4), dtype=np.uint8)

def px(S, x, y, c):
    if 0 <= x < S.shape[1] and 0 <= y < S.shape[0]:
        S[y, x] = (*c, 255)

def rect(S, x0, y0, w, h, c):
    for y in range(max(0, y0), min(S.shape[0], y0 + h)):
        for x in range(max(0, x0), min(S.shape[1], x0 + w)):
            S[y, x] = (*c, 255)

def ellipse(S, cx, cy, rx, ry, c):
    x0, x1 = int(cx - rx), int(cx + rx + 1)
    y0, y1 = int(cy - ry), int(cy + ry + 1)
    for y in range(max(0, y0), min(S.shape[0], y1)):
        for x in range(max(0, x0), min(S.shape[1], x1)):
            if ((x + 0.0 - cx) / rx) ** 2 + ((y + 0.0 - cy) / ry) ** 2 <= 1:
                S[y, x] = (*c, 255)

def line(S, x0, y0, x1, y1, c, thick=1):
    n = max(abs(x1 - x0), abs(y1 - y0), 1)
    for i in range(n + 1):
        t = i / n
        for dy in range(thick):
            for dx in range(thick):
                px(S, round(x0 + (x1 - x0) * t) + dx - thick // 2,
                   round(y0 + (y1 - y0) * t) + dy - thick // 2, c)

def outline_pass(S, c=OUT):
    from scipy import ndimage
    A = S[:, :, 3] > 0
    S[ndimage.binary_dilation(A) & ~A] = (*c, 255)

def save(S, name):
    Image.fromarray(S).save(os.path.join(PROPS, name))
    print("  ", name)

# ---------------------------------------------------------------- fountain
def fountain():
    S = canv(96, 64)
    gy = 63
    stone_light = (232, 218, 178); stone_mid = (214, 194, 148); stone_dark = (180, 156, 112)
    # three-step base (upper-left light: left/top faces brighter)
    for i, (w, h, lift) in enumerate([(46, 6, 12), (34, 5, 8), (26, 4, 4)]):
        y = gy - lift - h
        # left face (lighter)
        rect(S, 48 - w // 2, y, w // 2, h, stone_light)
        # right face (darker)
        rect(S, 48, y, w // 2, h, stone_dark)
        # top rim
        rect(S, 48 - w // 2, y, w, 1, (240, 228, 192))
    # basin bowl
    ellipse(S, 48, gy - 34, 12, 5, stone_mid)
    ellipse(S, 48, gy - 33, 9, 3, (150, 194, 200))  # water in bowl
    outline_pass(S)
    save(S, 'fountain_basin.png')
    # splash overlays (3 frames)
    for f in range(3):
        S = canv(40, 40)
        cy = 34
        spread = 3 + f * 3
        jet = (214, 244, 240); jet2 = (150, 200, 206)
        for i in range(5):
            yy = cy - i * 2 - f
            rect(S, 20 - spread + i * 2 - 1, yy, 2, 1, jet2)
            rect(S, 18 + spread - i * 2, yy, 2, 1, jet2)
        for i in range(4):
            yy = cy - i * 4 - 2
            rect(S, 20 - 2, yy, 2, 2, jet)
        px(S, 20 - spread, cy - 5, jet); px(S, 20 + spread - 2, cy - 5, jet)
        px(S, 20 - spread - 2, cy - 2, jet2); px(S, 20 + spread, cy - 2, jet2)
        outline_pass(S)
        save(S, f'fountain_splash_{f}.png')

# ---------------------------------------------------------------- tree & foliage
def tree():
    # trunk bottom at 96
    S = canv(104, 96)
    gy = 95
    trunk = (146, 118, 78); trunk_d = (116, 92, 60); trunk_l = (176, 146, 100)
    # trunk (1-6-1 tapered)
    for y in range(0, 30):
        w = 5 if y < 18 else 7 - (y - 18) // 6
        rect(S, 52 - w // 2, gy - 30 + y, w, 1, trunk)
    rect(S, 51, gy - 26, 2, 8, trunk_l)   # left highlight
    rect(S, 53, gy - 10, 1, 6, trunk_d)
    # roots
    rect(S, 47, gy - 2, 3, 2, trunk); rect(S, 55, gy - 2, 2, 2, trunk_d)
    # canopy: layered blob clusters
    from random import Random
    rng = Random(42)
    canopy = [(188, 214, 138), (160, 188, 112), (126, 158, 90), (96, 128, 70)]
    for cx in range(18, 86):
        pass
    # draw canopy as many overlapping circles
    centers = []
    for _ in range(26):
        cx = rng.randint(26, 78); cy = rng.randint(28, 62)
        r = rng.randint(7, 13)
        centers.append((cx, cy, r))
    for (cx, cy, r) in centers:
        ellipse(S, cx, gy - cy, r, r * 0.82, canopy[rng.randrange(4)])
    # bottom shade of canopy
    rect(S, 30, gy - 26, 44, 3, canopy[3])
    rect(S, 24, gy - 22, 56, 2, canopy[2])
    outline_pass(S)
    save(S, 'tree_0.png')
    # sway frame 1: shift canopy pixels up-right by 1
    S2 = S.copy()
    # simple sway: shift top portion
    S2[:, :, :] = 0
    S2[:68, 1:, :] = S[:68, :-1, :]
    S2[68:, :, :] = S[68:, :, :]
    # fix bottom contact pixels around trunk
    S2[70:74, 50:56] = S[70:74, 50:56]
    outline_pass(S2)
    save(S2, 'tree_1.png')

# ---------------------------------------------------------------- small props
def bush():
    S = canv(48, 34)
    gy = 33
    from random import Random
    rng = Random(7)
    cols = [(150, 180, 110), (122, 154, 88), (94, 126, 68)]
    for _ in range(14):
        cx = rng.randint(12, 36); cy = rng.randint(8, 22)
        r = rng.randint(5, 9)
        ellipse(S, cx, gy - cy, r, r * 0.8, cols[rng.randrange(3)])
    outline_pass(S)
    save(S, 'bush_0.png')
    S2 = S.copy(); S2[:, :, :] = 0
    S2[:26, 1:, :] = S[:26, :-1, :]
    S2[26:, :, :] = S[26:, :, :]
    outline_pass(S2)
    save(S2, 'bush_1.png')

def flowers():
    for variant in range(3):
        S = canv(26, 24)
        gy = 23
        palette = ((244, 208, 170), (236, 170, 196), (248, 236, 166))[variant]
        leafc = (126, 158, 90)
        rng = Random(100 + variant)
        # stems
        for _ in range(3):
            x = rng.randint(8, 18); h = rng.randint(7, 12)
            line(S, x, gy, x, gy - h, (90, 122, 62), 1)
            px(S, x + (1 if rng.random() < 0.5 else -1), gy - h // 2, leafc)
        # heads
        for x in (8, 14, 19):
            px(S, x + rng.randint(-1, 1), gy - rng.randint(8, 12), palette)
            px(S, x + rng.randint(-1, 1), gy - rng.randint(6, 9), palette[0] if isinstance(palette[0], tuple) else palette)
        outline_pass(S)
        save(S, f'flowers_{variant}_0.png')
        S2 = S.copy(); S2[:, :, :] = 0
        S2[:18, 1:, :] = S[:18, :-1, :]
        S2[18:, :, :] = S[18:, :, :]
        outline_pass(S2)
        save(S2, f'flowers_{variant}_1.png')

def lamp():
    S = canv(26, 62)
    gy = 61
    metal = (86, 82, 88); metal_l = (120, 116, 122); metal_d = (62, 58, 64)
    rect(S, 12, gy - 2, 2, 44, metal_d)
    rect(S, 11, gy - 1, 2, 44, metal)
    rect(S, 10, gy - 40, 2, 6, metal_l)
    # top finial
    rect(S, 11, gy - 50, 4, 3, metal_l)
    # lamp head
    rect(S, 7, gy - 47, 12, 8, (66, 60, 66))
    rect(S, 9, gy - 45, 8, 5, (255, 226, 150))
    rect(S, 8, gy - 46, 10, 1, metal_l)
    outline_pass(S)
    save(S, 'lamp_0.png')

def crates():
    S = canv(30, 24)
    gy = 23
    wood = (172, 142, 96); wood_l = (200, 172, 122); wood_d = (128, 102, 66)
    rect(S, 2, gy - 20, 10, 20, wood_d)
    rect(S, 3, gy - 20, 9, 20, wood)
    rect(S, 4, gy - 20, 8, 3, wood_l)
    rect(S, 16, gy - 14, 10, 14, wood_l)
    rect(S, 19, gy - 14, 7, 14, wood)
    rect(S, 20, gy - 14, 5, 4, wood[0] // 1 and (214, 190, 140))
    outline_pass(S)
    save(S, 'crates_0.png')

def bench():
    S = canv(48, 30)
    gy = 29
    wood = (160, 130, 88); wood_l = (190, 162, 112); wood_d = (118, 94, 62)
    # seat
    rect(S, 4, gy - 12, 40, 3, wood_l)
    rect(S, 5, gy - 10, 38, 3, wood)
    # backrest
    rect(S, 4, gy - 24, 40, 3, wood)
    for x in (8, 16, 24, 32, 40):
        rect(S, x, gy - 21, 2, 10, wood)
    # legs
    rect(S, 6, gy - 7, 3, 7, wood_d)
    rect(S, 39, gy - 7, 3, 7, wood_d)
    outline_pass(S)
    save(S, 'bench_0.png')

def signpost():
    S = canv(44, 56)
    gy = 55
    wood = (140, 112, 74); wood_l = (172, 142, 96); wood_d = (100, 78, 50)
    rect(S, 21, gy - 2, 2, 34, wood_d)
    rect(S, 20, gy - 1, 2, 34, wood)
    # board
    rect(S, 4, gy - 44, 36, 12, wood_l)
    rect(S, 5, gy - 43, 34, 10, (226, 208, 170))
    # runes (simple marks)
    for (x, y) in [(10, gy - 40), (18, gy - 39), (26, gy - 40), (34, gy - 39)]:
        px(S, x, y, (120, 74, 52))
        px(S, x, y + 2, (120, 74, 52))
    px(S, 14, gy - 37, (120, 74, 52)); px(S, 22, gy - 38, (120, 74, 52)); px(S, 30, gy - 37, (120, 74, 52))
    outline_pass(S)
    save(S, 'signpost_0.png')

if __name__ == '__main__':
    fountain()
    tree()
    bush()
    flowers()
    lamp()
    crates()
    bench()
    signpost()
    print("props done")
