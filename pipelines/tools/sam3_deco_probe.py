"""Flat-plate deco probe: Muse plate -> marker edit -> SAM3 cutouts.

usage:
  sam3_deco_probe.py <run-dir> <simple|village|grove|all> [--paid|--resplit|--sam-retry]
Without --paid only quotes are printed. Cap 0.20 USD per run directory.
--resplit re-extracts sprites from existing deco+masks (free).
--sam-retry rebuys SAM with point+box for failed objects only.
"""
import io
import json
import os
import sys
import time
from decimal import Decimal
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from hybrid_layout import compile_layout
from hybrid_painted_scene import provider_frame
from provider import WaveSpeed
from terrain_block import flat, guide
from terrain_llm import Ledger

ENV = Path(os.environ.get('TERRAIN_ENV_FILE', r'C:\Users\dhuec\.config\layout-terrain-hybrid\environment'))
MUSE = 'meta/muse-image/edit'
SAM3 = 'wavespeed-ai/sam3-image'
MAX_USD = '0.20'
HALF_W, HALF_H = 24, 12

VARIANTS = {
    'simple': {
        'rows': [
            '..........',
            '..LLLLLL..',
            '..LPPPLL..',
            '..LPWWPL..',
            '..LPWWPL..',
            '..LPPPLL..',
            '..LLLLLL..',
            '..........',
        ],
        'spawn': [2, 5],
        'goals': [[7, 2]],
        'objects': [
            {'id': 'tree', 'cell': [2, 2], 'prompt': 'tree', 'marker': (0, 220, 60), 'label': 'one leafy green deciduous tree'},
            {'id': 'bush', 'cell': [6, 2], 'prompt': 'bush', 'marker': (220, 220, 0), 'label': 'one small round green bush'},
            {'id': 'house', 'cell': [7, 5], 'prompt': 'house', 'marker': (220, 40, 40), 'label': 'one tiny wooden cottage'},
            {'id': 'rock', 'cell': [3, 6], 'prompt': 'boulder', 'marker': (160, 160, 180), 'label': 'one grey boulder pile'},
        ],
    },
    'village': {
        'rows': [
            '............',
            '..LLLLLLLL..',
            '..LLPPPLLL..',
            '..LLPWWPLL..',
            '..LLPWWPLL..',
            '..LLPPPPPL..',
            '..LLLLLLLL..',
            '..LLLLLLLL..',
            '............',
        ],
        'spawn': [3, 5],
        'goals': [[9, 2]],
        'objects': [
            {'id': 'oak', 'cell': [2, 2], 'prompt': 'oak tree', 'marker': (0, 200, 40),
             'label': 'one tall leafy oak tree'},
            {'id': 'pine', 'cell': [9, 2], 'prompt': 'pine tree', 'marker': (0, 120, 60),
             'label': 'one dark green pine tree'},
            {'id': 'bush-a', 'cell': [3, 3], 'prompt': 'bush', 'marker': (200, 220, 0),
             'label': 'one small round green bush'},
            {'id': 'bush-b', 'cell': [8, 3], 'prompt': 'flowering bush', 'marker': (255, 100, 180),
             'label': 'one flowering bush with tiny pink blossoms'},
            {'id': 'house', 'cell': [6, 6], 'prompt': 'cottage', 'marker': (220, 40, 40),
             'label': 'one small wooden cottage with a warm window, no chimney smoke'},
            {'id': 'well', 'cell': [4, 6], 'prompt': 'stone well', 'marker': (80, 80, 220),
             'label': 'one round stone water well with a wooden roof'},
            {'id': 'crate', 'cell': [8, 6], 'prompt': 'wooden crate', 'marker': (180, 100, 40),
             'label': 'one closed wooden crate'},
            {'id': 'boulder', 'cell': [2, 7], 'prompt': 'boulder', 'marker': (140, 140, 150),
             'label': 'one single grey boulder, no smoke'},
        ],
    },
    'grove': {
        'rows': [
            '............',
            '..LLLLLLLL..',
            '..LLLLLLLL..',
            '..LLWWLLLL..',
            '..LLWWPPLL..',
            '..LLLLPPLL..',
            '..LLLLLLLL..',
            '..LLLLLLLL..',
            '............',
        ],
        'spawn': [8, 5],
        'goals': [[3, 2]],
        'objects': [
            {'id': 'oak-a', 'cell': [2, 2], 'prompt': 'oak tree', 'marker': (0, 210, 50),
             'label': 'one leafy oak tree'},
            {'id': 'oak-b', 'cell': [5, 2], 'prompt': 'oak tree', 'marker': (40, 180, 40),
             'label': 'one leafy oak tree'},
            {'id': 'pine-a', 'cell': [8, 2], 'prompt': 'pine tree', 'marker': (0, 100, 50),
             'label': 'one pointed pine tree'},
            {'id': 'pine-b', 'cell': [9, 4], 'prompt': 'pine tree', 'marker': (20, 130, 70),
             'label': 'one pointed pine tree'},
            {'id': 'bush-a', 'cell': [2, 5], 'prompt': 'bush', 'marker': (210, 220, 0),
             'label': 'one round green bush'},
            {'id': 'bush-b', 'cell': [3, 7], 'prompt': 'bush', 'marker': (180, 200, 20),
             'label': 'one round green bush'},
            {'id': 'stump', 'cell': [6, 6], 'prompt': 'tree stump', 'marker': (120, 70, 30),
             'label': 'one cut wooden tree stump'},
            {'id': 'boulder', 'cell': [8, 7], 'prompt': 'boulder', 'marker': (150, 150, 160),
             'label': 'one grey boulder beside the path'},
        ],
    },
}


def load_env():
    if 'WAVESPEED_API_KEY' in os.environ:
        return
    if not ENV.exists():
        raise SystemExit(f'Env fehlt: {ENV}')
    for line in ENV.read_text().splitlines():
        name, _, value = line.partition('=')
        if name.strip() == 'WAVESPEED_API_KEY':
            os.environ['WAVESPEED_API_KEY'] = value.strip()


def world_raw(variant):
    cfg = VARIANTS[variant]
    mapping = {'.': 'land', 'L': 'land', 'P': 'path', 'W': 'water'}
    cells = [[mapping[c] for c in row] for row in cfg['rows']]
    H, W = len(cells), len(cells[0])
    return dict(
        schema='hybrid-layout/1', width=W, height=H, actor_width=0.64,
        spawn=cfg['spawn'], goals=cfg['goals'], cells=cells,
        heights=[[0] * W for _ in range(H)], transitions=[], unsupported=[],
    )


def cell_center_canvas(world, cell):
    x, y = cell
    ox, oy = world['origin']
    return ox + (x + 0.5 - (y + 0.5)) * HALF_W, oy + (x + 0.5 + y + 0.5) * HALF_H


def cell_xy_image(world, cell, image_size):
    """Map a world cell footpoint into pixels of an actual Muse/provider image."""
    frame, offset = provider_frame(world)
    cx, cy = cell_center_canvas(world, cell)
    sx = image_size[0] / frame[0]
    sy = image_size[1] / frame[1]
    return int((cx + offset[0]) * sx), int((cy + offset[1]) * sy)


def cell_box_image(world, cell, image_size, half_x=90, rise=200, drop=50):
    """SAM box around a cell, in the deco image's pixel space."""
    px, py = cell_xy_image(world, cell, image_size)
    w, h = image_size
    return {
        'x_min': max(0, px - half_x),
        'y_min': max(0, py - rise),
        'x_max': min(w - 1, px + half_x),
        'y_max': min(h - 1, py + drop),
    }


def mark_plate(plate_bytes, world, objects):
    """Paint numbered diamond markers on the plate at full Muse resolution.

    White crosshair + id digit force Muse to keep each object at the exact foot.
    """
    im = Image.open(io.BytesIO(plate_bytes)).convert('RGB')
    draw = ImageDraw.Draw(im)
    r = max(16, im.width // 70)
    for i, obj in enumerate(objects, start=1):
        cx, cy = cell_xy_image(world, obj['cell'], im.size)
        # Outer ring (black) then filled diamond for contrast on grass.
        draw.polygon([(cx, cy - r - 2), (cx + r + 2, cy), (cx, cy + r + 2), (cx - r - 2, cy)], outline=(0, 0, 0))
        draw.polygon([(cx, cy - r), (cx + r, cy), (cx, cy + r), (cx - r, cy)], fill=obj['marker'])
        draw.line([(cx - r // 2, cy), (cx + r // 2, cy)], fill=(255, 255, 255), width=3)
        draw.line([(cx, cy - r // 2), (cx, cy + r // 2)], fill=(255, 255, 255), width=3)
        draw.rectangle([cx - 4, cy - 4, cx + 4, cy + 4], fill=(255, 255, 255))
        # Tiny id above the diamond so Muse cannot swap similar trees/bushes.
        label = str(i)
        tx, ty = cx - 4 * len(label), cy - r - 18
        draw.rectangle([tx - 2, ty - 2, tx + 8 * len(label), ty + 14], fill=(0, 0, 0))
        draw.text((tx, ty), label, fill=(255, 255, 255))
    out = io.BytesIO()
    im.save(out, format='PNG')
    return out.getvalue()


def muse(client):
    client.model_id, client.requires_size = MUSE, False
    return client


def sam(client):
    client.model_id, client.requires_size = SAM3, False
    return client


def wait(client, prediction_id, timeout=600):
    deadline = time.time() + timeout
    while time.time() < deadline:
        result = client.poll(prediction_id)
        status = result.get('status')
        if status == 'completed':
            return result
        if status in ('failed', 'cancelled', 'timeout', 'deleted'):
            raise ValueError(f'Prediction {prediction_id} ended: {status} {result.get("error")}')
        time.sleep(2)
    raise ValueError(f'Timeout waiting for {prediction_id}')


def buy_image(client, ledger, role, inputs, dest: Path, state, state_path):
    if dest.exists():
        return dest.read_bytes()
    tickets = state.setdefault('predictions', {})
    if role not in tickets:
        quote = Decimal(str(client.quote(inputs)['discounted_price']))
        call = ledger.reserve(role, quote)
        tickets[role] = {'id': client.submit(inputs)['id'], 'call': call, 'price': str(quote)}
        state_path.write_text(json.dumps(state, indent=1))
    result = wait(client, tickets[role]['id'])
    ledger.settle(tickets[role]['call'], Decimal(tickets[role]['price']), tickets[role]['id'])
    raw = client.download(result['outputs'][0])
    dest.write_bytes(raw)
    return raw


def mask_stats(raw):
    im = np.asarray(Image.open(io.BytesIO(raw)).convert('L'))
    white = int((im > 200).sum())
    return {'white_px': white, 'coverage': round(white / im.size, 4), 'size': list(im.shape[::-1])}


def _label_components(binary):
    """4-connected component labels; returns label image and sizes dict (label->count)."""
    h, w = binary.shape
    labels = np.zeros((h, w), np.int32)
    sizes = {}
    current = 0
    for y in range(h):
        for x in range(w):
            if not binary[y, x] or labels[y, x]:
                continue
            current += 1
            stack = [(y, x)]
            labels[y, x] = current
            count = 0
            while stack:
                cy, cx = stack.pop()
                count += 1
                for ny, nx in ((cy - 1, cx), (cy + 1, cx), (cy, cx - 1), (cy, cx + 1)):
                    if 0 <= ny < h and 0 <= nx < w and binary[ny, nx] and not labels[ny, nx]:
                        labels[ny, nx] = current
                        stack.append((ny, nx))
            sizes[current] = count
    return labels, sizes


def instance_cutout(deco_bytes, mask_bytes, box, foot_xy, pad=24, min_px=60, search_radius=280):
    """Clip SAM mask to the object box, keep the component nearest the footpoint.

    If the box is empty (Muse drifted), fall back to the nearest component in the
    full mask within search_radius of the footpoint — still one instance, never the whole class.
    """
    deco = np.array(Image.open(io.BytesIO(deco_bytes)).convert('RGBA'), copy=True)
    mask = np.asarray(Image.open(io.BytesIO(mask_bytes)).convert('L'))
    if mask.shape[:2] != deco.shape[:2]:
        mask = np.asarray(Image.fromarray(mask).resize((deco.shape[1], deco.shape[0]), Image.Resampling.NEAREST))
    h, w = mask.shape
    fx, fy = foot_xy

    def pick(binary, ox, oy):
        if not binary.any():
            return None, None
        labels, sizes = _label_components(binary)
        best, best_score = None, None
        for lab, count in sizes.items():
            if count < min_px:
                continue
            ys, xs = np.where(labels == lab)
            cx = (xs.min() + xs.max()) / 2 + ox
            cy = float(ys.max()) + oy
            score = (cx - fx) ** 2 + (cy - fy) ** 2 - count * 0.01
            if best_score is None or score < best_score:
                best_score, best = score, (lab, labels, sizes, ox, oy, xs, ys)
        return best, best_score

    x0 = max(0, box['x_min'] - pad)
    y0 = max(0, box['y_min'] - pad)
    x1 = min(w, box['x_max'] + pad)
    y1 = min(h, box['y_max'] + pad)
    region = (mask[y0:y1, x0:x1] > 200)
    best, score = pick(region, x0, y0)
    mode = 'box'
    if best is None:
        # Search a window around the footpoint on the full mask.
        sx0 = max(0, int(fx - search_radius))
        sy0 = max(0, int(fy - search_radius * 1.5))
        sx1 = min(w, int(fx + search_radius))
        sy1 = min(h, int(fy + search_radius * 0.5))
        window = (mask[sy0:sy1, sx0:sx1] > 200)
        best, score = pick(window, sx0, sy0)
        mode = 'search'
    if best is None:
        return None, 'empty_near_foot'
    lab, labels, sizes, ox, oy, xs, ys = best
    # Reject if still absurdly far from foot (wrong object).
    cx = (xs.min() + xs.max()) / 2 + ox
    cy = float(ys.max()) + oy
    if (cx - fx) ** 2 + (cy - fy) ** 2 > search_radius ** 2 * 2.5:
        return None, 'nearest_too_far'
    alpha = np.zeros_like(mask, np.uint8)
    # Map local labels back: labels is local to the picked window
    local = labels == lab
    # reconstruct window origin from ox,oy — labels shape equals window
    wh, ww = labels.shape
    alpha[oy:oy + wh, ox:ox + ww][local] = 255
    deco[:, :, 3] = alpha
    ys, xs = np.where(alpha > 0)
    bx0, bx1, by0, by1 = int(xs.min()), int(xs.max()) + 1, int(ys.min()), int(ys.max()) + 1
    crop = Image.fromarray(deco[by0:by1, bx0:bx1])
    out = io.BytesIO()
    crop.save(out, format='PNG')
    return (out.getvalue(), [bx0, by0, bx1, by1], int(sizes[lab]), mode), None


def cutout(deco_bytes, mask_bytes):
    """Legacy full-mask cutout; prefer instance_cutout for multi-object scenes."""
    deco = np.array(Image.open(io.BytesIO(deco_bytes)).convert('RGBA'), copy=True)
    mask = np.asarray(Image.open(io.BytesIO(mask_bytes)).convert('L'))
    if mask.shape[:2] != deco.shape[:2]:
        mask = np.asarray(Image.fromarray(mask).resize((deco.shape[1], deco.shape[0]), Image.Resampling.NEAREST))
    alpha = (mask > 200).astype(np.uint8) * 255
    deco[:, :, 3] = alpha
    ys, xs = np.where(alpha > 0)
    if len(xs) == 0:
        return None
    x0, x1, y0, y1 = xs.min(), xs.max() + 1, ys.min(), ys.max() + 1
    if (x1 - x0) * (y1 - y0) > deco.shape[0] * deco.shape[1] * 0.12:
        return None
    crop = Image.fromarray(deco[y0:y1, x0:x1])
    out = io.BytesIO()
    crop.save(out, format='PNG')
    return out.getvalue(), [int(x0), int(y0), int(x1), int(y1)]


def resplit_run(run: Path, variant: str):
    """Re-extract sprites from existing deco+masks; no provider calls.

    Each object uses only its own SAM mask, clipped near its cell foot via
    instance_cutout. Already-claimed pixels are blanked so class-mask bleed
    cannot hand the same instance to two ids or swap pine↔bush via orphans.
    """
    objects = VARIANTS[variant]['objects']
    world = compile_layout(world_raw(variant))
    ground = flat(world)
    deco = (run / 'deco.png').read_bytes()
    deco_arr = np.array(Image.open(io.BytesIO(deco)).convert('RGBA'), copy=True)
    deco_size = deco_arr.shape[1], deco_arr.shape[0]
    claimed = np.zeros(deco_arr.shape[:2], dtype=bool)
    results = []
    for obj in objects:
        box = cell_box_image(ground, obj['cell'], deco_size)
        foot = cell_xy_image(ground, obj['cell'], deco_size)
        mask_path = run / f"mask-{obj['id']}.png"
        entry = {
            'id': obj['id'], 'box': box, 'foot': list(foot),
            'mask': mask_stats(mask_path.read_bytes()) if mask_path.exists() else None,
        }
        if not mask_path.exists():
            entry.update(ok=False, reason='no_mask')
            results.append(entry)
            continue
        mask = np.asarray(Image.open(mask_path).convert('L'))
        if mask.shape[:2] != deco_arr.shape[:2]:
            mask = np.asarray(Image.fromarray(mask).resize(deco_size, Image.Resampling.NEAREST))
        mask = mask.copy()
        mask[claimed] = 0
        buf = io.BytesIO()
        Image.fromarray(mask).save(buf, format='PNG')
        cut, err = instance_cutout(deco, buf.getvalue(), box, foot)
        if not cut:
            entry.update(ok=False, reason=err or 'empty_near_foot')
            results.append(entry)
            continue
        sprite, bbox, cpx, mode = cut
        (run / f"sprite-{obj['id']}.png").write_bytes(sprite)
        bx0, by0, bx1, by1 = bbox
        # Mark the written alpha so the next object cannot reclaim this instance.
        crop_alpha = np.asarray(Image.open(io.BytesIO(sprite)).convert('RGBA'))[:, :, 3] > 0
        claimed[by0:by1, bx0:bx1] |= crop_alpha
        entry.update(
            ok=True, sprite_bbox=bbox, component_px=cpx, extract=mode,
            dist=round((( (bx0 + bx1) / 2 - foot[0]) ** 2 + (by1 - foot[1]) ** 2) ** 0.5, 1),
        )
        results.append(entry)

    summary = {
        'variant': variant, 'mode': 'resplit-box-own',
        'results': results,
        'ok_count': sum(1 for r in results if r['ok']),
        'all_ok': all(r['ok'] for r in results),
        'claimed_px': int(claimed.sum()),
        'deco_size': list(deco_size),
    }
    (run / 'summary-resplit.json').write_text(json.dumps(summary, indent=1))
    try:
        from terrain_deco import package as deco_package
        summary['package'] = deco_package(run)
    except Exception as exc:
        summary['placement_error'] = str(exc)
    print(json.dumps(summary, indent=1))
    return summary


def sam_retry_points(run: Path, variant: str, only_failed=True, points_override=None):
    """Re-buy SAM with point prompt at footpoint (no text) for failed objects.

    points_override: optional {id: [x,y]} in deco pixel space (manual Muse-drift fix).
    """
    load_env()
    objects = VARIANTS[variant]['objects']
    world = compile_layout(world_raw(variant))
    ground = flat(world)
    state_path = run / 'state.json'
    state = json.loads(state_path.read_text())
    if 'deco' not in state.get('urls', {}):
        raise SystemExit('deco URL fehlt; erst --paid laufen')
    deco = (run / 'deco.png').read_bytes()
    deco_size = Image.open(io.BytesIO(deco)).size
    prev = {}
    if (run / 'summary-resplit.json').exists():
        prev = {r['id']: r for r in json.loads((run / 'summary-resplit.json').read_text())['results']}
    elif (run / 'summary.json').exists():
        prev = {r['id']: r for r in json.loads((run / 'summary.json').read_text())['results']}
    if points_override:
        by_id = {o['id']: o for o in objects}
        targets = [by_id[i] for i in points_override if i in by_id]
    else:
        targets = [o for o in objects if not only_failed or not prev.get(o['id'], {}).get('ok')]
    if not targets:
        print(json.dumps({'variant': variant, 'retry': 'nothing_failed'}))
        return
    client = WaveSpeed()
    ledger = Ledger(run / 'ledger.jsonl', MAX_USD)
    quotes = {}
    feet = {}
    for obj in targets:
        if points_override and obj['id'] in points_override:
            px, py = [int(v) for v in points_override[obj['id']]]
        else:
            px, py = cell_xy_image(ground, obj['cell'], deco_size)
        feet[obj['id']] = (px, py)
        box = {
            'x_min': max(0, px - 90), 'y_min': max(0, py - 200),
            'x_max': min(deco_size[0] - 1, px + 90), 'y_max': min(deco_size[1] - 1, py + 50),
        }
        inputs = {
            'image': state['urls']['deco'],
            'point_prompts': [{'x': px, 'y': py, 'label': 1}],
            'box_prompts': [box],
            'apply_mask': False,
            'output_format': 'png',
        }
        quotes[obj['id']] = Decimal(str(sam(client).quote(inputs)['discounted_price']))
    print(json.dumps({'variant': variant, 'retry_quote_usd': {k: str(v) for k, v in quotes.items()},
                      'total': str(sum(quotes.values())), 'targets': [o['id'] for o in targets],
                      'feet': {k: list(v) for k, v in feet.items()}}, indent=1))
    results = []
    for obj in targets:
        px, py = feet[obj['id']]
        box = {
            'x_min': max(0, px - 90), 'y_min': max(0, py - 200),
            'x_max': min(deco_size[0] - 1, px + 90), 'y_max': min(deco_size[1] - 1, py + 50),
        }
        role = f"sam-pt-{obj['id']}"
        dest = run / f"mask-{obj['id']}.png"
        state.setdefault('predictions', {}).pop(role, None)
        if dest.exists():
            dest.unlink()
        mask = buy_image(sam(client), ledger, role, {
            'image': state['urls']['deco'],
            'point_prompts': [{'x': px, 'y': py, 'label': 1}],
            'box_prompts': [box],
            'apply_mask': False,
            'output_format': 'png',
        }, dest, state, state_path)
        cut, err = instance_cutout(deco, mask, box, (px, py))
        entry = {'id': obj['id'], 'box': box, 'foot': [px, py], 'mask': mask_stats(mask)}
        if cut:
            sprite, bbox, cpx, mode = cut
            (run / f"sprite-{obj['id']}.png").write_bytes(sprite)
            entry.update(ok=True, sprite_bbox=bbox, component_px=cpx, extract=mode)
        else:
            entry.update(ok=False, reason=err)
        results.append(entry)
    summary = {
        'variant': variant, 'mode': 'sam-point-retry',
        'spent_usd': str(ledger.spent()),
        'results': results,
        'ok_count': sum(1 for r in results if r['ok']),
        'all_ok': all(r['ok'] for r in results),
    }
    (run / 'summary-retry.json').write_text(json.dumps(summary, indent=1))
    try:
        from terrain_deco import package as deco_package
        summary['package'] = deco_package(run)
    except Exception as exc:
        summary['placement_error'] = str(exc)
    print(json.dumps(summary, indent=1))


def main():
    load_env()
    if len(sys.argv) < 3:
        raise SystemExit('usage: sam3_deco_probe.py <run-dir> <simple|village|grove|all> [--paid|--resplit|--sam-retry]')
    run = Path(sys.argv[1])
    variant = sys.argv[2]
    if variant == 'all':
        base = run
        for name in VARIANTS:
            args = [str(base / f'sam3-{name}'), name] + [a for a in sys.argv[3:] if a != 'all']
            print('===', name, '===')
            sys.argv = [sys.argv[0]] + args
            main()
        return
    if variant not in VARIANTS:
        raise SystemExit('usage: sam3_deco_probe.py <run-dir> <simple|village|grove|all> [--paid|--resplit|--sam-retry]')
    if '--resplit' in sys.argv:
        resplit_run(run, variant)
        return
    if '--sam-retry' in sys.argv:
        points = None
        if '--points' in sys.argv:
            pi = sys.argv.index('--points')
            points = json.loads(Path(sys.argv[pi + 1]).read_text())
        sam_retry_points(run, variant, points_override=points)
        return
    paid = '--paid' in sys.argv
    objects = VARIANTS[variant]['objects']
    run.mkdir(parents=True, exist_ok=True)
    state_path = run / 'state.json'
    state = json.loads(state_path.read_text()) if state_path.exists() else {}

    world = compile_layout(world_raw(variant))
    ground = flat(world)
    (run / 'world.json').write_text(json.dumps(world, indent=1))
    (run / 'objects.json').write_text(json.dumps({'variant': variant, 'objects': objects}, indent=1))
    guide_png = guide(world)
    (run / 'guide.png').write_bytes(guide_png)

    client = WaveSpeed()
    muse(client).discover()
    if 'urls' not in state:
        state['urls'] = {'guide': client.upload(guide_png, 'guide.png')}
        state_path.write_text(json.dumps(state, indent=1))

    plate_inputs = {
        'prompt': (
            'Image 1 is a flat-colored isometric blockout and the exact geometry authority. '
            'Paint it with the same camera, framing and scale. Finished hand-painted pixel-art isometric game map '
            'like a classic handheld monster RPG: one completely flat grassy island on a flat dark background, '
            'dirt path and water with sandy bank exactly where drawn. Everything on one flat ground level: no cliffs, '
            'stairs, buildings, trees, bushes, props, characters, text or cast shadows.'
        ),
        'image_urls': [state['urls']['guide']],
        'aspect_ratio': '3:2',
        'output_format': 'png',
    }
    deco_parts = [
        'Image 1 is an already finished flat isometric ground plate with numbered colored diamond markers. '
        'Keep the camera, framing, ground textures, path and water EXACTLY unchanged. '
        'Replace EACH numbered diamond with exactly ONE upright object as listed; remove marker colors and numbers completely. '
        'The base/foot of each object must sit EXACTLY on the white crosshair center of its own diamond — '
        'do not slide, swap, or merge objects between diamonds. One object per diamond, no extras. '
        'Objects sit upright on the ground, same pixel-art palette as the plate. '
        'No chimney smoke, no extra props, no text, no new paths.'
    ]
    for i, obj in enumerate(objects, start=1):
        deco_parts.append(
            f"Diamond #{i} (RGB{obj['marker']} at its marked cell) becomes {obj['label']}."
        )
    deco_template = {'prompt': ' '.join(deco_parts), 'aspect_ratio': '3:2', 'output_format': 'png'}

    sam_client = WaveSpeed()
    quotes = {
        'plate': Decimal(str(muse(client).quote(plate_inputs)['discounted_price'])),
        'deco': Decimal(str(muse(client).quote({**deco_template, 'image_urls': [state['urls']['guide']]})['discounted_price'])),
    }
    guide_size = Image.open(io.BytesIO(guide_png)).size
    for obj in objects:
        box = cell_box_image(ground, obj['cell'], guide_size)
        quotes[f"sam-{obj['id']}"] = Decimal(str(sam(sam_client).quote({
            'image': state['urls']['guide'], 'prompt': obj['prompt'], 'box_prompts': [box],
            'apply_mask': False, 'output_format': 'png',
        })['discounted_price']))

    ledger = Ledger(run / 'ledger.jsonl', MAX_USD)
    report = {
        'variant': variant,
        'quotes_usd': {k: str(v) for k, v in quotes.items()},
        'total_quote_usd': str(sum(quotes.values())),
        'spent_usd': str(ledger.spent()),
        'cap_usd': MAX_USD,
        'object_count': len(objects),
    }
    (run / 'quote.json').write_text(json.dumps(report, indent=1))
    print(json.dumps(report, indent=1))
    if not paid:
        return

    lock = run / 'buy.lock'
    try:
        lock.open('x').close()
    except FileExistsError:
        raise SystemExit(f'{lock} existiert')
    try:
        plate = buy_image(muse(client), ledger, 'plate', plate_inputs, run / 'plate.png', state, state_path)
        marked = mark_plate(plate, ground, objects)
        (run / 'plate-marked.png').write_bytes(marked)
        if 'marked' not in state['urls']:
            state['urls']['marked'] = client.upload(marked, 'plate-marked.png')
            state_path.write_text(json.dumps(state, indent=1))
        deco = buy_image(muse(client), ledger, 'deco', {**deco_template, 'image_urls': [state['urls']['marked']]},
                         run / 'deco.png', state, state_path)
        if 'deco' not in state['urls']:
            state['urls']['deco'] = client.upload(deco, 'deco.png')
            state_path.write_text(json.dumps(state, indent=1))

        deco_size = Image.open(io.BytesIO(deco)).size
        results = []
        for obj in objects:
            box = cell_box_image(ground, obj['cell'], deco_size)
            foot = cell_xy_image(ground, obj['cell'], deco_size)
            mask = buy_image(sam(sam_client), ledger, f"sam-{obj['id']}", {
                'image': state['urls']['deco'], 'prompt': obj['prompt'], 'box_prompts': [box],
                'apply_mask': False, 'output_format': 'png',
            }, run / f"mask-{obj['id']}.png", state, state_path)
            stats = mask_stats(mask)
            cut, err = instance_cutout(deco, mask, box, foot)
            entry = {'id': obj['id'], 'box': box, 'foot': list(foot), 'mask': stats}
            if cut:
                sprite, bbox, px, mode = cut
                (run / f"sprite-{obj['id']}.png").write_bytes(sprite)
                entry.update(ok=True, sprite_bbox=bbox, component_px=px, extract=mode)
            else:
                entry.update(ok=False, reason=err)
            results.append(entry)

        summary = {
            'variant': variant,
            'spent_usd': str(ledger.spent()),
            'results': results,
            'ok_count': sum(1 for r in results if r['ok']),
            'all_ok': all(r['ok'] for r in results),
            'deco_size': list(deco_size),
        }
        (run / 'summary.json').write_text(json.dumps(summary, indent=1))
        try:
            from terrain_deco import package as deco_package
            summary['package'] = deco_package(run)
        except Exception as exc:
            summary['placement_error'] = str(exc)
        print(json.dumps(summary, indent=1))
    finally:
        lock.unlink(missing_ok=True)


if __name__ == '__main__':
    main()
