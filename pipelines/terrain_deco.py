"""Flat-terrain deco: candidate extract, assign, place on plate, walkable navigator.

usage:
  terrain_deco.py candidates <run-dir>
  terrain_deco.py assign <run-dir> [--map assign.json]
  terrain_deco.py place <run-dir>
  terrain_deco.py navigate <run-dir>   # place (if needed) + hybrid navigator
  terrain_deco.py package <run-dir>    # assign (if map) + navigate

Expects in run-dir: plate.png, world.json, objects.json, sprite-<id>.png
Optional: assign.json mapping id -> {file} under candidates/, points.json for SAM overrides.
"""
from __future__ import annotations

import base64
import io
import json
import shutil
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from artifacts import canonical, digest
from hybrid_layout import compile_layout
from hybrid_painted_scene import provider_frame, register, render_guide
from terrain_block import flat

ROOT = Path(__file__).resolve().parent
ACTOR = ROOT / 'assets' / 'actor'
HALF_W, HALF_H = 24, 12


def cell_center_canvas(world, cell):
    x, y = cell
    ox, oy = world['origin']
    return ox + (x + 0.5 - (y + 0.5)) * HALF_W, oy + (x + 0.5 + y + 0.5) * HALF_H


def cell_xy_image(world, cell, image_size):
    frame, offset = provider_frame(world)
    cx, cy = cell_center_canvas(world, cell)
    sx = image_size[0] / frame[0]
    sy = image_size[1] / frame[1]
    return int((cx + offset[0]) * sx), int((cy + offset[1]) * sy)


def cell_box_image(world, cell, image_size, half_x=90, rise=200, drop=50):
    px, py = cell_xy_image(world, cell, image_size)
    w, h = image_size
    return {
        'x_min': max(0, px - half_x),
        'y_min': max(0, py - rise),
        'x_max': min(w - 1, px + half_x),
        'y_max': min(h - 1, py + drop),
    }


def label_components(binary):
    """4-connected component labels; returns label image and sizes dict."""
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
    """Clip SAM mask near foot; one connected component, never the whole class mask."""
    deco = np.array(Image.open(io.BytesIO(deco_bytes)).convert('RGBA'), copy=True)
    mask = np.asarray(Image.open(io.BytesIO(mask_bytes)).convert('L'))
    if mask.shape[:2] != deco.shape[:2]:
        mask = np.asarray(Image.fromarray(mask).resize((deco.shape[1], deco.shape[0]), Image.Resampling.NEAREST))
    h, w = mask.shape
    fx, fy = foot_xy

    def pick(binary, ox, oy):
        if not binary.any():
            return None, None
        labels, sizes = label_components(binary)
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
    best, score = pick(mask[y0:y1, x0:x1] > 200, x0, y0)
    mode = 'box'
    if best is None:
        sx0 = max(0, int(fx - search_radius))
        sy0 = max(0, int(fy - search_radius * 1.5))
        sx1 = min(w, int(fx + search_radius))
        sy1 = min(h, int(fy + search_radius * 0.5))
        best, score = pick(mask[sy0:sy1, sx0:sx1] > 200, sx0, sy0)
        mode = 'search'
    if best is None:
        return None, 'empty_near_foot'
    lab, labels, sizes, ox, oy, xs, ys = best
    cx = (xs.min() + xs.max()) / 2 + ox
    cy = float(ys.max()) + oy
    if (cx - fx) ** 2 + (cy - fy) ** 2 > search_radius ** 2 * 2.5:
        return None, 'nearest_too_far'
    alpha = np.zeros_like(mask, np.uint8)
    wh, ww = labels.shape
    alpha[oy:oy + wh, ox:ox + ww][labels == lab] = 255
    deco[:, :, 3] = alpha
    ys, xs = np.where(alpha > 0)
    x0, x1, y0, y1 = int(xs.min()), int(xs.max()) + 1, int(ys.min()), int(ys.max()) + 1
    if (x1 - x0) * (y1 - y0) > deco.shape[0] * deco.shape[1] * 0.12:
        return None, 'component_too_large'
    crop = Image.fromarray(deco[y0:y1, x0:x1])
    out = io.BytesIO()
    crop.save(out, format='PNG')
    return (out.getvalue(), [x0, y0, x1, y1], int(sizes[lab]), mode), None


def sprite_foot_anchor(rgba: Image.Image):
    """Bottom-center of opaque pixels (isometric foot)."""
    a = np.asarray(rgba)
    ys, xs = np.where(a[:, :, 3] > 8)
    if len(xs) == 0:
        return rgba.width / 2, rgba.height
    return float((xs.min() + xs.max()) / 2), float(ys.max())


def extract_candidates(run: Path, min_px=80):
    """Union all mask-*.png into unique connected components under candidates/."""
    run = Path(run)
    deco = np.array(Image.open(run / 'deco.png').convert('RGBA'), copy=True)
    h, w = deco.shape[:2]
    union = np.zeros((h, w), bool)
    for path in sorted(run.glob('mask-*.png')):
        mask = np.asarray(Image.open(path).convert('L'))
        if mask.shape != (h, w):
            mask = np.asarray(Image.fromarray(mask).resize((w, h), Image.Resampling.NEAREST))
        union |= mask > 200
    labels, sizes = label_components(union)
    out = run / 'candidates'
    out.mkdir(exist_ok=True)
    for old in out.glob('c*-*px.png'):
        old.unlink()
    cands = []
    for lab, count in sorted(sizes.items(), key=lambda x: -x[1]):
        if count < min_px:
            continue
        ys, xs = np.where(labels == lab)
        x0, x1 = int(xs.min()), int(xs.max()) + 1
        y0, y1 = int(ys.min()), int(ys.max()) + 1
        if (x1 - x0) * (y1 - y0) > w * h * 0.25:
            continue
        alpha = np.zeros((h, w), np.uint8)
        alpha[ys, xs] = 255
        rgba = deco.copy()
        rgba[:, :, 3] = alpha
        name = f'c{lab:02d}-{count}px'
        Image.fromarray(rgba[y0:y1, x0:x1]).save(out / f'{name}.png')
        cands.append({
            'id': name, 'lab': lab, 'count': count,
            'bbox': [x0, y0, x1, y1],
            'foot': [float((x0 + x1) / 2), float(y1)],
        })
    overview = Image.open(run / 'deco.png').convert('RGBA')
    draw = ImageDraw.Draw(overview)
    for c in cands:
        x0, y0, x1, y1 = c['bbox']
        draw.rectangle([x0, y0, x1, y1], outline=(255, 0, 255), width=2)
        draw.text((x0, max(0, y0 - 12)), c['id'].split('-')[0], fill=(255, 0, 255))
    overview.save(run / 'candidates-overview.png')
    (out / 'index.json').write_text(json.dumps(cands, indent=1))
    return cands


def apply_assign(run: Path, assign_path: Path | None = None):
    """Copy candidates/<file> -> sprite-<id>.png from assign.json."""
    run = Path(run)
    assign_path = Path(assign_path) if assign_path else run / 'assign.json'
    assign = json.loads(assign_path.read_text())
    written = {}
    for oid, meta in assign.items():
        src = run / 'candidates' / meta['file']
        if not src.exists():
            raise SystemExit(f'assign missing candidate: {src}')
        dst = run / f'sprite-{oid}.png'
        shutil.copyfile(src, dst)
        im = Image.open(src)
        written[oid] = {**meta, 'size': list(im.size)}
    (run / 'assign.json').write_text(json.dumps(written, indent=1))
    return written


def load_objects(run: Path):
    data = json.loads((run / 'objects.json').read_text())
    return data['objects'] if isinstance(data, dict) and 'objects' in data else data


def place_sprites(run: Path):
    """Stamp sprite-<id>.png onto plate.png at grid feet; write scene + preview."""
    run = Path(run)
    ground = _load_world(run)

    plate = Image.open(run / 'plate.png').convert('RGBA')
    objects = load_objects(run)
    placements = []
    layers = []
    for obj in objects:
        path = run / f"sprite-{obj['id']}.png"
        if not path.exists():
            placements.append({'id': obj['id'], 'ok': False, 'reason': 'no_sprite'})
            continue
        sprite = Image.open(path).convert('RGBA')
        ax, ay = sprite_foot_anchor(sprite)
        fx, fy = cell_xy_image(ground, obj['cell'], plate.size)
        dx, dy = int(fx - ax), int(fy - ay)
        layers.append({
            'id': obj['id'], 'sprite': sprite, 'dx': dx, 'dy': dy,
            'foot': [fx, fy], 'anchor': [ax, ay],
            'depth': obj['cell'][0] + obj['cell'][1],
            'cell': obj['cell'],
        })
        placements.append({
            'id': obj['id'], 'ok': True, 'cell': obj['cell'],
            'foot': [fx, fy], 'anchor': [round(ax, 1), round(ay, 1)],
            'paste': [dx, dy], 'size': list(sprite.size),
        })

    scene = plate.copy()
    for layer in sorted(layers, key=lambda L: L['depth']):
        dx, dy = layer['dx'], layer['dy']
        spr = layer['sprite']
        # Clip paste to plate bounds (Muse feet can push tall trees past the top).
        sx0 = max(0, -dx)
        sy0 = max(0, -dy)
        sx1 = min(spr.width, plate.width - dx)
        sy1 = min(spr.height, plate.height - dy)
        if sx1 <= sx0 or sy1 <= sy0:
            continue
        crop = spr.crop((sx0, sy0, sx1, sy1))
        scene.paste(crop, (dx + sx0, dy + sy0), crop)
    scene.save(run / 'scene.png')

    summary = {
        'objects': placements,
        'ok_count': sum(1 for p in placements if p.get('ok')),
        'all_ok': all(p.get('ok') for p in placements),
        'plate_size': list(plate.size),
    }
    (run / 'placement.json').write_text(json.dumps(summary, indent=1))
    (run / 'preview.html').write_text(_preview_html(run.name, summary), encoding='utf-8')
    return summary


def _load_world(run: Path):
    raw = json.loads((run / 'world.json').read_text())
    world = raw if 'origin' in raw else compile_layout(raw)
    return flat(world)


def stamp_deco_depth(depth: np.ndarray, run: Path, registration: dict, objects: list):
    """Raise depth under deco sprites so the actor occludes behind them.

    Hybrid navigator compares depth[p] to actor (x+y); larger depth = in front.
    """
    place = json.loads((run / 'placement.json').read_text()) if (run / 'placement.json').exists() else None
    if not place:
        return depth
    src_w, src_h = registration['source_size']
    frame_w, frame_h = registration['frame_size']
    ox, oy = registration['canvas_offset']
    cw, ch = registration['canvas']
    sx = frame_w / src_w
    sy = frame_h / src_h
    by_id = {p['id']: p for p in place['objects'] if p.get('ok')}
    for obj in objects:
        meta = by_id.get(obj['id'])
        if not meta:
            continue
        sprite = Image.open(run / f"sprite-{obj['id']}.png").convert('RGBA')
        alpha = np.asarray(sprite)[:, :, 3] > 8
        dx, dy = meta['paste']
        # Object depth above its cell so actor on/behind the cell is occluded.
        z = float(obj['cell'][0] + obj['cell'][1]) + 1.15
        ys, xs = np.where(alpha)
        for py, px in zip(ys, xs):
            fx = (dx + px) * sx - ox
            fy = (dy + py) * sy - oy
            cx, cy = int(fx), int(fy)
            if 0 <= cx < cw and 0 <= cy < ch and z > depth[cy, cx]:
                depth[cy, cx] = z
    return depth


def build_navigator(run: Path):
    """Register scene.png onto the flat world canvas and emit a walkable hybrid navigator."""
    run = Path(run)
    if not (run / 'scene.png').exists():
        place_sprites(run)
    world = _load_world(run)
    objects = load_objects(run)
    source = (run / 'scene.png').read_bytes()
    terrain, registration = register(world, source)
    _, depth = render_guide(world)
    depth = stamp_deco_depth(depth, run, registration, objects)
    actor = (ACTOR / 'character.png').read_bytes()
    shadow = (ACTOR / 'shadow.png').read_bytes()
    manifest = json.loads((ACTOR / 'character-manifest.json').read_bytes())

    def png_bytes(arr):
        buf = io.BytesIO()
        Image.fromarray(arr).save(buf, format='PNG')
        return buf.getvalue()

    terrain_png = png_bytes(terrain)
    (run / 'terrain.png').write_bytes(terrain_png)
    (run / 'character.png').write_bytes(actor)
    (run / 'shadow.png').write_bytes(shadow)
    (run / 'character-manifest.json').write_text(json.dumps(manifest, indent=1))
    (run / 'depth.f32').write_bytes(depth.tobytes())
    (run / 'scene-registration.json').write_text(json.dumps(registration, indent=1))

    data = {
        'world': world,
        'character': manifest,
        'depth': base64.b64encode(depth.tobytes()).decode(),
        'terrain': 'data:image/png;base64,' + base64.b64encode(terrain_png).decode(),
        'sprite': 'data:image/png;base64,' + base64.b64encode(actor).decode(),
        'shadow': 'data:image/png;base64,' + base64.b64encode(shadow).decode(),
    }
    template = (ROOT / 'static' / 'hybrid-navigator.html').read_text(encoding='utf-8')
    html = (
        template
        .replace('__SCENE_DATA__', canonical(data).decode())
        .replace('__WIDTH__', str(world['canvas'][0]))
        .replace('__HEIGHT__', str(world['canvas'][1]))
        .replace(
            'Nur die Treppe verbindet die Ebenen.',
            'Flaches Deco-Terrain: eine Ebene, Deco-Sprites occludieren den Actor.',
        )
    )
    (run / 'index.html').write_text(html, encoding='utf-8')
    provenance = {
        'kind': 'flat-deco-navigator/1',
        'source': 'scene.png',
        'layout_revision': world.get('revision'),
        'registration': registration,
        'deco_occlusion': True,
        'actor_sha256': digest(actor),
        'scene_sha256': digest(source),
        'user_acceptance': 'pending',
    }
    (run / 'provenance.json').write_text(json.dumps(provenance, indent=1))
    return {
        'canvas': world['canvas'],
        'spawn': world['spawn'],
        'registration': registration,
        'deco_occlusion': True,
        'index': str(run / 'index.html'),
    }


def _preview_html(title: str, summary: dict) -> str:
    rows = ''.join(
        f"<tr><td>{p['id']}</td><td>{'ok' if p.get('ok') else p.get('reason')}</td>"
        f"<td>{p.get('cell')}</td><td>{p.get('foot')}</td></tr>"
        for p in summary['objects']
    )
    return f"""<!DOCTYPE html>
<html lang="de"><head><meta charset="utf-8"><title>deco preview {title}</title>
<style>
  body {{ margin:0; background:#1a1a1a; color:#ddd; font:14px/1.4 system-ui,sans-serif; }}
  main {{ max-width:1200px; margin:0 auto; padding:16px; }}
  h1 {{ font-size:1.2rem; font-weight:600; }}
  .stage {{ background:#111; border:1px solid #333; overflow:auto; }}
  img {{ display:block; max-width:100%; height:auto; image-rendering:pixelated; }}
  table {{ border-collapse:collapse; margin-top:16px; width:100%; }}
  td,th {{ border:1px solid #444; padding:4px 8px; text-align:left; }}
</style></head><body><main>
<h1>Deco preview — {title}</h1>
<p>{summary['ok_count']} Objekte · plate {summary['plate_size'][0]}×{summary['plate_size'][1]} ·
<a href="index.html">Navigator (WASD)</a></p>
<div class="stage"><img src="scene.png" alt="placed deco scene"></div>
<table><thead><tr><th>id</th><th>status</th><th>cell</th><th>foot</th></tr></thead>
<tbody>{rows}</tbody></table>
</main></body></html>
"""


def package(run: Path):
    """Assign from map when present, place sprites, emit walkable navigator."""
    run = Path(run)
    assign_path = run / 'assign.json'
    if assign_path.exists() and (run / 'candidates').is_dir():
        assign = json.loads(assign_path.read_text())
        if assign and all(isinstance(m, dict) and m.get('file') for m in assign.values()):
            apply_assign(run)
    missing = [
        o['id'] for o in load_objects(run)
        if not (run / f"sprite-{o['id']}.png").exists()
    ]
    if missing:
        print(json.dumps({'warning': 'missing_sprites', 'ids': missing}))
    place = place_sprites(run)
    if place['ok_count'] == 0:
        raise SystemExit('no sprites to place')
    nav = build_navigator(run)
    return {'placement': place, 'navigator': nav, 'missing_sprites': missing}


def main():
    if len(sys.argv) < 3:
        raise SystemExit(__doc__)
    cmd, run = sys.argv[1], Path(sys.argv[2])
    if cmd == 'candidates':
        cands = extract_candidates(run)
        print(json.dumps({'count': len(cands), 'ids': [c['id'] for c in cands]}, indent=1))
    elif cmd == 'assign':
        path = None
        if '--map' in sys.argv:
            path = Path(sys.argv[sys.argv.index('--map') + 1])
        print(json.dumps(apply_assign(run, path), indent=1))
    elif cmd == 'place':
        print(json.dumps(place_sprites(run), indent=1))
    elif cmd == 'navigate':
        print(json.dumps(build_navigator(run), indent=1))
    elif cmd == 'package':
        print(json.dumps(package(run), indent=1))
    else:
        raise SystemExit(__doc__)


if __name__ == '__main__':
    main()
