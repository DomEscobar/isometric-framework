"""Deterministic offline image quilting. No runtime or provider dependency."""
from __future__ import annotations

import hashlib
import io
import json
import re
from pathlib import Path

import numpy as np
from PIL import Image, __version__ as PILLOW_VERSION


def minimum_cut(cost):
    """Minimum summed-error top-to-bottom path; stable leftmost tie breaking."""
    height, width = cost.shape
    totals = cost.astype(np.float64).copy()
    parents = np.zeros((height, width), dtype=np.int32)
    for row in range(1, height):
        previous = np.pad(totals[row - 1], (1, 1), constant_values=np.inf)
        choices = np.stack((previous[:width], previous[1:width + 1], previous[2:]))
        parents[row] = np.arange(width) + choices.argmin(axis=0) - 1
        totals[row] += choices.min(axis=0)
    route = np.empty(height, dtype=np.int32)
    route[-1] = totals[-1].argmin()
    for row in range(height - 1, 0, -1):
        route[row - 1] = parents[row, route[row]]
    return route


def quilt(source, width, height, seed, patch=96, overlap=24, candidates=24):
    """Copy non-wrapping source patches, joining overlaps with minimum-error cuts.

    Left/top cuts are unioned at their intersection (not a global graph cut).
    Source RGB is never tinted, blurred, interpolated or synthesized.
    """
    integer(width, 'width', 1, 8192)
    integer(height, 'height', 1, 8192)
    integer(seed, 'seed', 0, 2**32 - 1)
    integer(patch, 'patch', 2, 512)
    integer(overlap, 'overlap', 1, patch - 1)
    integer(candidates, 'candidates', 1, 128)
    if not isinstance(source, np.ndarray) or source.dtype != np.uint8 or source.ndim != 3 or source.shape[2] != 3 or min(source.shape[:2]) < patch:
        raise ValueError('source must be uint8 RGB with both dimensions at least patch')
    if width * height > 16_000_000:
        raise ValueError('output exceeds pixel cap')
    rng = np.random.default_rng(seed)
    output = np.zeros((height, width, 3), dtype=np.uint8)
    costs = []
    for y in range(0, height, patch - overlap):
        for x in range(0, width, patch - overlap):
            h, w = min(patch, height - y), min(patch, width - x)
            current = output[y:y + h, x:x + w]
            occupied = np.zeros((h, w), dtype=bool)
            if x:
                occupied[:, :overlap] = True
            if y:
                occupied[:overlap] = True
            best, best_cost = None, float('inf')
            for _ in range(candidates):
                sy = int(rng.integers(0, source.shape[0] - patch + 1))
                sx = int(rng.integers(0, source.shape[1] - patch + 1))
                candidate = source[sy:sy + h, sx:sx + w]
                delta = np.mean((candidate.astype(float) - current.astype(float)) ** 2, axis=2)
                cost = float(delta[occupied].mean()) if occupied.any() else 0.0
                if cost < best_cost:
                    best, best_cost = candidate.copy(), cost
            delta = np.mean((best.astype(float) - current.astype(float)) ** 2, axis=2)
            keep = np.zeros((h, w), dtype=bool)
            if x:
                keep |= np.arange(w)[None, :] < minimum_cut(delta[:, :overlap])[:, None]
            if y:
                keep |= np.arange(h)[:, None] < minimum_cut(delta[:overlap].T)[None, :]
            output[y:y + h, x:x + w] = np.where(keep[:, :, None], current, best)
            costs.append(best_cost)
    return output, {'patches': len(costs), 'meanOverlapCost': float(np.mean(costs))}



def integer(value, name, low, high):
    if type(value) is not int or not low <= value <= high:
        raise ValueError(f'{name} must be an integer between {low} and {high}')
    return value


def fields(value, allowed, name):
    if not isinstance(value, dict) or set(value) - set(allowed):
        raise ValueError(f'{name} must be an object with only: {", ".join(allowed)}')


def digest(data):
    return hashlib.sha256(data).hexdigest()


def encoded(data):
    return (json.dumps(data, sort_keys=True, separators=(',', ':')) + '\n').encode()


def read_png(root, value, name):
    if not isinstance(value, str) or not value or ':' in value or '\\' in value:
        raise ValueError(f'{name} must be a local relative PNG path')
    path = (root / value).resolve()
    if Path(value).is_absolute() or not path.is_relative_to(root):
        raise ValueError(f'{name} must stay inside the recipe directory')
    if not path.is_file() or path.stat().st_size > 64 * 1024 * 1024:
        raise ValueError(f'{name} missing or exceeds byte cap')
    data = path.read_bytes()
    try:
        with Image.open(io.BytesIO(data)) as image:
            if image.format != 'PNG' or getattr(image, 'n_frames', 1) != 1:
                raise ValueError(f'{name} must be a static PNG')
            if max(image.size) > 8192 or image.width * image.height > 16_000_000:
                raise ValueError(f'{name} exceeds image bounds')
            image = image.copy()
    except (OSError, Image.DecompressionBombError) as exc:
        raise ValueError(f'{name} is not a valid bounded PNG') from exc
    return image, {'file': value, 'sha256': digest(data), 'dimensions': list(image.size)}


def run(recipe_path, out_dir):
    """Validate before writing. Existing output directories are never overwritten."""
    recipe_path, out_dir = Path(recipe_path).resolve(), Path(out_dir).resolve()
    if out_dir.exists():
        raise ValueError('output directory already exists')
    if not recipe_path.is_file() or recipe_path.stat().st_size > 1024 * 1024:
        raise ValueError('recipe missing or exceeds 1 MiB')
    raw = recipe_path.read_bytes()
    try:
        recipe = json.loads(raw)
    except (ValueError, UnicodeError) as exc:
        raise ValueError('recipe must be valid JSON') from exc
    fields(recipe, ['version', 'map', 'cells', 'materials', 'seed', 'patch', 'overlap', 'candidates', 'materialMask', 'sourceScale'], 'recipe')
    integer(recipe.get('version'), 'version', 1, 1)
    grid = recipe.get('map')
    fields(grid, ['columns', 'rows', 'tileWidth', 'tileHeight'], 'map')
    cols = integer(grid.get('columns'), 'columns', 1, 256)
    rows = integer(grid.get('rows'), 'rows', 1, 256)
    tw = integer(grid.get('tileWidth'), 'tileWidth', 2, 1024)
    th = integer(grid.get('tileHeight'), 'tileHeight', 2, 1024)
    if tw % 2 or th % 2:
        raise ValueError('tile dimensions must be even for integral frames')
    scale = integer(recipe.get('sourceScale', 1), 'sourceScale', 1, 8)
    tw, th = tw * scale, th * scale
    width, height = (cols + rows) * tw // 2, (cols + rows) * th // 2
    if max(width, height) > 8192 or width * height > 16_000_000:
        raise ValueError('projected canvas exceeds image bounds')
    origin = [-tw // 2, -cols * th // 2]
    seed = integer(recipe.get('seed'), 'seed', 0, 2**32 - 1)
    patch = integer(recipe.get('patch'), 'patch', 2, 512)
    overlap = integer(recipe.get('overlap'), 'overlap', 1, patch - 1)
    candidates = integer(recipe.get('candidates'), 'candidates', 1, 128)
    materials = recipe.get('materials')
    if not isinstance(materials, dict) or not 2 <= len(materials) <= 32:
        raise ValueError('materials must contain 2..32 named sources')
    names = sorted(materials)
    if any(not re.fullmatch(r'[a-zA-Z][a-zA-Z0-9_-]{0,63}', name) for name in names):
        raise ValueError('material names must be simple identifiers')
    cells = recipe.get('cells')
    if not isinstance(cells, list) or len(cells) != rows or any(not isinstance(row, list) or len(row) != cols or any(not isinstance(v, str) or v not in materials for v in row) for row in cells):
        raise ValueError('cells must cover every map[r][c] with a known material')
    # Bound total candidate comparisons, including costly tiny strides.
    work = ((width + patch - overlap - 1) // (patch - overlap)) * ((height + patch - overlap - 1) // (patch - overlap)) * patch**2 * candidates * len(names)
    if work > 4_000_000_000:
        raise ValueError('quilting work exceeds cap; reduce candidates, density or pilot dimensions')
    sources, inputs = {}, {}
    for name in names:
        fields(materials[name], ['source'], f'materials.{name}')
        image, record = read_png(recipe_path.parent, materials[name].get('source'), name)
        if min(image.size) < patch:
            raise ValueError(f'{name} source is smaller than patch')
        rgba = np.array(image.convert('RGBA'))
        if np.any(rgba[:, :, 3] != 255):
            raise ValueError(f'{name} source must be opaque')
        sources[name], inputs[name] = rgba[:, :, :3], record
    # Raster ownership from pixel centres, using the framework c=NE/r=SE axes.
    yy = np.arange(height, dtype=np.float64)[:, None]
    xx = np.arange(width, dtype=np.float64)[None, :]
    u = (xx + .5 + origin[0]) / (tw / 2)
    v = (yy + .5 + origin[1]) / (th / 2)
    cc = np.floor((u - v) / 2 + .5).astype(int)
    rr = np.floor((u + v) / 2 + .5).astype(int)
    inside = (cc >= 0) & (cc < cols) & (rr >= 0) & (rr < rows)
    table = np.array([[names.index(value) for value in row] for row in cells], dtype=np.uint8)
    ownership = table[np.clip(rr, 0, rows - 1), np.clip(cc, 0, cols - 1)]
    mask_record = None
    if 'materialMask' in recipe:
        image, mask_record = read_png(recipe_path.parent, recipe['materialMask'], 'materialMask')
        if image.mode not in ('L', 'P') or image.size != (width, height):
            raise ValueError('materialMask must be canvas-sized indexed P or L PNG')
        ownership = np.array(image)
        if int(ownership.max()) >= len(names):
            raise ValueError('materialMask has unknown material index (alphabetical material order)')
    result = np.empty((height, width, 3), dtype=np.uint8)
    stats = {}
    for index, name in enumerate(names):
        plane, stats[name] = quilt(sources[name], width, height, (seed + index) % 2**32, patch, overlap, candidates)
        selected = ownership == index
        result[selected] = plane[selected]
        stats[name]['pixels'] = int(selected.sum())
        stats[name]['mapPixels'] = int((selected & inside).sum())
    provenance = {'version': 1, 'algorithm': 'minimum-error-quilt-v1', 'recipeSha256': digest(raw),
                  'parameters': recipe, 'inputs': inputs, 'mask': mask_record,
                  'tools': {'quilt_materials.py': digest(Path(__file__).read_bytes())},
                  'dependencies': {'numpy': np.__version__, 'Pillow': PILLOW_VERSION},
                  'cellCounts': {name: sum(row.count(name) for row in cells) for name in names},
                  'bounds': {'width': width, 'height': height, 'origin': origin, 'mapPixels': int(inside.sum()), 'cells': cols * rows},
                  'materials': stats, 'maskOwnership': 'host', 'sourcePixelsPerOutputPixel': 1, 'sourceScale': scale}
    provenance['cacheKey'] = digest(encoded(provenance))
    out_dir.mkdir(parents=True, exist_ok=False)
    Image.fromarray(result).save(out_dir / 'ground.png', compress_level=9)
    Image.fromarray(ownership).save(out_dir / 'material-mask.png', compress_level=9)
    manifest = {'version': 1, 'images': {'ground': {'url': 'ground.png', 'sampling': 'nearest', 'width': width, 'height': height}},
                'textures': {'ground': {'image': 'ground', 'frame': {'x': 0, 'y': 0, 'width': width, 'height': height}, 'anchor': {'x': 0, 'y': 0}}},
                'placements': {'ground': {'x': origin[0], 'y': origin[1]}}}
    (out_dir / 'manifest.json').write_bytes(encoded(manifest))
    pack = {'version': 1, 'manifest': 'manifest.json', 'groups': [{'id': 'quilted-ground', 'kind': 'surface', 'textures': ['ground'], 'composition': {'reference': 'ground.png', 'origin': origin, 'sourceScale': scale}}]}
    (out_dir / 'packed-art.json').write_bytes(encoded(pack))
    provenance['outputs'] = {name: digest((out_dir / name).read_bytes()) for name in ['ground.png', 'material-mask.png', 'packed-art.json', 'manifest.json']}
    (out_dir / 'provenance.json').write_bytes(encoded(provenance))
    return provenance
