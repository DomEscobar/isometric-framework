"""Witchhollow Tactics — procedural pixel-art sprite authoring.

Generates unit frames (idle/walk/hit/cast) for the witch and familiar models in
the four iso facings the runtime uses (ne/se/sw/nw). All art is original and
authored from the component palette below; nothing is copied or bundled.

Canvas: witch 40x52, familiar 32x36. Feet on the bottom row; frames anchor at
(0.5, 1). Facing variants use mirrored profiles with asymmetric details.
"""
from __future__ import annotations
import os
import numpy as np
from PIL import Image

HOST = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SPRITES = os.path.join(HOST, 'art', 'sprites')
os.makedirs(SPRITES, exist_ok=True)

OUTLINE = (58, 55, 56)          # near-black slate
SKIN = ((255, 217, 176), (227, 177, 129))   # light, shade

def canv(w, h):
    return np.zeros((h, w, 4), dtype=np.uint8)

def px(S, x, y, c):
    if 0 <= x < S.shape[1] and 0 <= y < S.shape[0]:
        S[y, x] = (*c, 255)

def rect(S, x0, y0, w, h, c, outline=True):
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
        x, y = round(x0 + (x1 - x0) * t), round(y0 + (y1 - y0) * t)
        for dy in range(thick):
            for dx in range(thick):
                px(S, x + dx - thick // 2, y + dy - thick // 2, c)

def outline_pass(S, c=OUTLINE):
    """Draw a 1px outline around every opaque pixel so sprites read clearly."""
    A = S[:, :, 3] > 0
    from scipy import ndimage
    neigh = ndimage.binary_dilation(A) & ~A
    S[neigh] = (*c, 255)

def save(S, path):
    Image.fromarray(S).save(path)

# ---------------------------------------------------------------- palettes
def palette(team):
    if team == 'player':   # periwinkle academy robe, violet trim
        return dict(
            robe=((232, 243, 251), (205, 221, 240), (165, 183, 208), (127, 144, 173)),
            trim=(111, 107, 181), hat=((122, 90, 168), (95, 70, 138), (72, 52, 108)),
            hair=((232, 179, 78), (197, 145, 58)), boots=((90, 74, 60), (68, 55, 44)),
            wand=(171, 138, 89))
    return dict(             # warm academy robe, rust trim (enemy team)
        robe=((247, 221, 168), (232, 184, 138), (197, 143, 95), (156, 109, 66)),
        trim=(181, 97, 58), hat=((150, 100, 60), (118, 76, 44), (90, 58, 32)),
        hair=((122, 74, 47), (96, 56, 35)), boots=((82, 62, 42), (60, 44, 30)),
        wand=(150, 190, 120))

def familiar_palette(kind):
    if kind == 'leaf':       # leaf sprite familiar
        return dict(body=((217, 224, 143), (159, 182, 90), (111, 143, 63), (74, 98, 41)),
                    accent=(226, 240, 190), sprout=((166, 200, 84), (96, 134, 50)))
    return dict(             # ember pup familiar
        body=((255, 217, 160), (245, 154, 74), (217, 97, 46), (163, 61, 28)),
        accent=(255, 228, 190), sprout=((255, 190, 90), (219, 130, 46)))

# ---------------------------------------------------------------- witch body
def draw_witch(frame, team, facing, state):
    """Draw a witch into a 40x52 canvas, facing 'r' (ne/se) or 'l' (sw/nw).
    States: idle0 idle1 walk0 walk1 hit cast0 cast1."""
    P = palette(team)
    S = frame if facing == 'r' else frame[:, ::-1]
    ground_y = 51
    bob = -1 if state in ('idle1', 'walk1') else 0
    if state == 'cast1': bob = -2
    lean = -1 if state == 'hit' else (1 if state in ('cast0', 'cast1') else 0)
    if state.startswith('walk'):
        stride, lift = ((-4, 0), (0, 1)) if state == 'walk0' else ((4, 0), (0, 1))
    elif state == 'hit':
        stride, lift = (3, 0), 0
    else:
        stride, lift = (0, 0), 0
    base_y = ground_y + bob
    boot = P['boots']
    # legs
    rect(S, 18 + stride[0] + lean, base_y - 7, 3, 7, boot[0])
    rect(S, 21 - stride[0] + lean, base_y - 7, 3, 7, boot[1])
    # skirt: rounded trapezoid 13 -> 19 wide
    robe = P['robe']
    skirt_top = base_y - 20
    for i in range(13):
        widen = 1 + i // 2
        rect(S, 17 - widen + lean + 1, skirt_top + i, 12 + 2 * widen, 1, robe[2] if i > 8 else robe[1])
    rect(S, 14 + lean, skirt_top + 11, 14, 1, robe[0])
    rect(S, 13 + lean, skirt_top + 0, 2, 12, robe[3])   # left shade edge
    # torso
    rect(S, 16 + lean, skirt_top - 10, 10, 10, robe[1])
    rect(S, 16 + lean, skirt_top - 10, 10, 2, robe[0])
    rect(S, 16 + lean, skirt_top - 5, 10, 1, P['trim'])
    # collar
    rect(S, 17 + lean, skirt_top - 8, 8, 2, P['trim'])
    # arms
    if state in ('cast0', 'cast1'):
        rect(S, 14 + lean, skirt_top - 9, 2, 8, robe[2])          # back arm
        rect(S, 25 + lean, skirt_top - 11, 3, 6, robe[1])         # cast arm up
        rect(S, 26 + lean, skirt_top - 13, 2, 3, robe[0])
        line(S, 28 + lean, skirt_top - 12, 34 + lean, skirt_top - 19, P['wand'], 1)
        spark = (255, 236, 160)
        px(S, 35 + lean, skirt_top - 20, spark)
        if state == 'cast1':
            px(S, 36 + lean, skirt_top - 18, (255, 246, 200))
            px(S, 33 + lean, skirt_top - 16, spark)
            px(S, 35 + lean, skirt_top - 23, spark)
    elif state == 'hit':
        rect(S, 12 + lean, skirt_top - 8, 2, 5, robe[2])          # arm up (surprised)
        rect(S, 28 + lean, skirt_top - 8, 2, 5, robe[2])
        px(S, 12 + lean, skirt_top - 10, SKIN[0])
        px(S, 29 + lean, skirt_top - 10, SKIN[0])
    else:
        rect(S, 13 + lean, skirt_top - 6, 2, 6, robe[2])          # far arm
        rect(S, 26 + lean, skirt_top - 5, 2, 6, robe[1])          # near arm
        # folded hand
        px(S, 15 + lean, skirt_top + 1, SKIN[0])
    # head
    head_y = skirt_top - 19
    skin = SKIN
    ellipse(S, 20 + lean, head_y, 5.6, 5.0, skin[0])
    rect(S, 16 + lean, head_y - 2, 8, 2, skin[1])
    # face (right-facing: eyes toward +x)
    px(S, 19 + lean, head_y, (60, 58, 74))
    px(S, 22 + lean, head_y, (60, 58, 74))
    px(S, 20 + lean, head_y + 1, (222, 148, 148))
    px(S, 24 + lean, head_y + 1, (202, 132, 120))
    if state == 'hit':
        px(S, 18 + lean, head_y, (58, 55, 56)); px(S, 19 + lean, head_y + 1, (58, 55, 56))
        px(S, 21 + lean, head_y, (58, 55, 56)); px(S, 22 + lean, head_y + 2, (58, 55, 56))
    # hair
    hair = P['hair']
    rect(S, 14 + lean, head_y - 4, 13, 2, hair[0])
    px(S, 13 + lean, head_y + 1, hair[1])
    px(S, 25 + lean, head_y + 2, hair[1])
    px(S, 15 + lean, head_y + 4, hair[1])
    # hat: brim + floppy cone
    hat = P['hat']
    hat_y = head_y - 5
    rect(S, 13 + lean, hat_y - 1, 15, 1, hat[1])
    rect(S, 12 + lean, hat_y, 17, 1, hat[0])
    px(S, 14 + lean, hat_y - 2, hat[1])
    # cone leaning slightly back
    for i in range(5):
        w = 7 - i
        rect(S, 17 + lean - (i // 2), hat_y - 7 + i * 2, w, 2 if i < 4 else 3, hat[2])
    px(S, 20 + lean, hat_y - 8, hat[0])
    px(S, 22 + lean, hat_y - 10, hat[1])
    return frame

# ---------------------------------------------------------------- familiar body
def draw_familiar(frame, kind, facing, state):
    """Round familiar into a 32x36 canvas. States differ by bob/feet/lean."""
    S = frame if facing == 'r' else frame[:, ::-1]
    P = familiar_palette(kind)
    base_y = 35
    if state.startswith('walk'):
        bob, squash = (0, 0) if state == 'walk0' else (-1, 1)
        fdx = ((-5, 4), (6, -2))[1 if state == 'walk1' else 0]
    elif state == 'hit':
        bob, squash, fdx = 0, 2, (-2, 4)
    elif state in ('cast0', 'cast1'):
        bob, squash = (-1, 0) if state == 'cast0' else (-2, 1)
        fdx = (-6, 6)
    else:
        bob = -1 if state == 'idle1' else 0
        squash, fdx = 0, (-4, 3)
    body = P['body']
    ry = 9.6 + squash
    # feet
    for fx in fdx:
        rect(S, 16 + fx, base_y - 2, 4, 2, body[3])
    # body
    ellipse(S, 16, base_y - 10 + bob, 9.4, ry, body[2])
    ellipse(S, 16, base_y - 11 + bob, 7.8, ry - 1, body[1])
    ellipse(S, 16, base_y - 12 + bob, 6.2, ry - 2, body[0])
    ellipse(S, 16, base_y - 9 + bob, 4.4, ry - 4, P['accent'])
    # sprout ears
    sprout = P['sprout']
    if kind == 'leaf':
        rect(S, 12, base_y - 18 + bob, 2, 3, sprout[1])
        rect(S, 20, base_y - 18 + bob, 2, 3, sprout[1])
        rect(S, 11, base_y - 21 + bob, 2, 2, sprout[0])
        rect(S, 21, base_y - 21 + bob, 2, 2, sprout[0])
    else:
        rect(S, 12, base_y - 18 + bob, 2, 3, sprout[1])
        rect(S, 20, base_y - 18 + bob, 2, 3, sprout[1])
        px(S, 13, base_y - 21 + bob, (255, 240, 150))
        px(S, 19, base_y - 21 + bob, (255, 240, 150))
    # face
    if state == 'hit':
        px(S, 14, base_y - 11 + bob, (58, 55, 56)); px(S, 15, base_y - 10 + bob, (58, 55, 56))
        px(S, 18, base_y - 11 + bob, (58, 55, 56)); px(S, 19, base_y - 10 + bob, (58, 55, 56))
    else:
        px(S, 14, base_y - 11 + bob, (52, 50, 66))
        px(S, 18, base_y - 11 + bob, (52, 50, 66))
    px(S, 16, base_y - 9 + bob, (214, 128, 122))
    return frame

# ---------------------------------------------------------------- export
STATES = ['idle0', 'idle1', 'walk0', 'walk1', 'hit', 'cast0', 'cast1']
DIRS = {'ne': 'r', 'se': 'r', 'sw': 'l', 'nw': 'l'}

def export_units():
    for team in ('player', 'enemy'):
        for d in ('ne', 'se', 'sw', 'nw'):
            facing = DIRS[d]
            for st in STATES:
                fr = canv(40, 52)
                draw_witch(fr, team, facing, st)
                outline_pass(fr)
                save(fr, os.path.join(SPRITES, f'witch_{team}_{d}_{st}.png'))
            print(f'witch {team} {d} ok')
    for kind in ('leaf', 'ember'):
        for d in ('ne', 'se', 'sw', 'nw'):
            facing = DIRS[d]
            for st in STATES:
                fr = canv(32, 36)
                draw_familiar(fr, kind, facing, st)
                outline_pass(fr)
                save(fr, os.path.join(SPRITES, f'fam_{kind}_{d}_{st}.png'))
            print(f'fam {kind} {d} ok')

if __name__ == '__main__':
    export_units()
