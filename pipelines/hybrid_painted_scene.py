"""Organic whole-scene route: frozen grid -> organic isometric guide -> one painted scene.

The frozen cell grid stays the only collision authority. The guide lets walkable material
boundaries meander across cell edges; water only shrinks inside its own cells and stair stone
stays exactly on stair cells, so a faithful painting never shows walkable ground as water.
The provider image is registered back onto the world canvas with one uniform scale.
"""
import io
import json
import numpy as np
from PIL import Image, ImageDraw

ASPECT_RATIO = '3:2'
ASPECT = (3, 2)
ASPECT_TOLERANCE = 0.01
RES = 16
SKIRT = 16
BACKGROUND = (28, 43, 40)
SURFACE = {'land': 'grass', 'plateau': 'grass', 'path': 'path', 'water': 'water', 'stairs': 'stone', 'square': 'paving'}
COLORS = {'grass': (98, 145, 82), 'path': (168, 127, 77), 'sand': (206, 184, 132), 'water': (49, 120, 166),
          'stone': (182, 174, 156), 'paving': (191, 177, 139), 'cliff': (118, 106, 92), 'soil': (104, 74, 50)}
CLIFF_EDGE = (58, 92, 50)
FACE_SHADE = {'east': 0.78, 'south': 0.92}
RISER_SHADE = 0.8
LIP_SHADE = 0.86
BLUR_CELLS = 0.42
WARP_CELLS = 0.18
SHORE_CELLS = 0.38
SEED = 7


def _blur(a, sigma):
    radius = int(3 * sigma) + 1
    kernel = np.exp(-0.5 * (np.arange(-radius, radius + 1) / sigma) ** 2)
    kernel /= kernel.sum()
    for axis in (0, 1):
        pad = [(0, 0), (0, 0)]
        pad[axis] = (radius, radius)
        padded = np.pad(a, pad, mode='reflect')
        out = np.zeros(a.shape)
        for i, weight in enumerate(kernel):
            window = [slice(None), slice(None)]
            window[axis] = slice(i, i + a.shape[axis])
            out += weight * padded[tuple(window)]
        a = out
    return a


def _bilinear(grid, y, x):
    y = np.clip(y, 0, grid.shape[0] - 1.001)
    x = np.clip(x, 0, grid.shape[1] - 1.001)
    y0, x0 = y.astype(int), x.astype(int)
    fy, fx = y - y0, x - x0
    top = grid[y0, x0] * (1 - fx) + grid[y0, x0 + 1] * fx
    bottom = grid[y0 + 1, x0] * (1 - fx) + grid[y0 + 1, x0 + 1] * fx
    return top * (1 - fy) + bottom * fy


def _noise(shape, period, seed, octaves=3):
    rng = np.random.default_rng(seed)
    yy, xx = np.mgrid[:shape[0], :shape[1]].astype(float)
    total = np.zeros(shape)
    for octave in range(octaves):
        p = period / 2 ** octave
        grid = rng.standard_normal((int(shape[0] / p) + 3, int(shape[1] / p) + 3))
        total += _blur(_bilinear(grid, yy / p, xx / p), max(p / 4, 1)) * 0.5 ** octave
    return total / total.std()


def _nearest_same_level(labels, heights, level):
    same = np.argwhere(heights == level)
    out = labels.copy()
    for y, x in np.argwhere(heights != level):
        ny, nx = same[np.argmin(((same - (y, x)) ** 2).sum(axis=1))]
        out[y, x] = labels[ny, nx]
    return out


class SurfaceField:
    def __init__(self, world):
        cells = np.array(world['cells'])
        heights = np.array(world['heights'])
        self.names = sorted({SURFACE[c] for c in cells.flat} | ({'sand'} if 'water' in cells else set()))
        index = {n: i for i, n in enumerate(self.names)}
        labels = np.vectorize(lambda c: index[SURFACE[c]])(cells)
        up = lambda a: a.repeat(RES, axis=0).repeat(RES, axis=1)
        fine_cells, fine_heights = up(cells), up(heights)
        shape = fine_cells.shape
        yy, xx = np.mgrid[:shape[0], :shape[1]].astype(float)
        warp_y = yy + _noise(shape, 1.2 * RES, SEED) * WARP_CELLS * RES
        warp_x = xx + _noise(shape, 1.2 * RES, SEED + 1) * WARP_CELLS * RES
        field = np.zeros(shape, dtype=np.int8)
        for level in np.unique(heights):
            level_labels = up(_nearest_same_level(labels, heights, level))
            weights = np.stack([_bilinear(_blur((level_labels == i).astype(float), BLUR_CELLS * RES), warp_y, warp_x)
                                for i in range(len(self.names))])
            self._constrain(weights, fine_cells, index)
            at_level = fine_heights == level
            field[at_level] = np.argmax(weights, axis=0)[at_level]
        if 'water' in index:
            water = field == index['water']
            reach = _blur(water.astype(float), SHORE_CELLS * RES / 1.55)
            threshold = 0.06 * np.exp(0.45 * _noise(shape, 0.8 * RES, SEED + 2))
            field[(reach > threshold) & (field == index['grass']) & (fine_heights == 0)] = index['sand']
        self.field = field

    @staticmethod
    def _constrain(weights, fine_cells, index):
        if 'water' in index:
            weights[index['water']][fine_cells != 'water'] = -np.inf
        if 'stone' in index:
            weights[index['stone']][fine_cells != 'stairs'] = -np.inf
            weights[:, fine_cells == 'stairs'] = -np.inf
            weights[index['stone']][fine_cells == 'stairs'] = 1

    def labels_at(self, wx, wy):
        fy = np.clip((np.asarray(wy) * RES).astype(int), 0, self.field.shape[0] - 1)
        fx = np.clip((np.asarray(wx) * RES).astype(int), 0, self.field.shape[1] - 1)
        return self.field[fy, fx]


def project(world, wx, wy, z):
    return world['origin'][0] + (wx - wy) * 24, world['origin'][1] + (wx + wy) * 12 - z


class _Canvas:
    def __init__(self, world):
        self.world = world
        self.width, self.height = world['canvas']
        self.image = np.zeros((self.height, self.width, 3), np.uint8)
        self.image[:] = BACKGROUND
        self.depth = np.full((self.height, self.width), -1000, dtype='<f4')

    def window(self, sx0, sx1, sy0, sy1):
        sx0, sy0 = max(int(np.floor(sx0)), 0), max(int(np.floor(sy0)), 0)
        sx1, sy1 = min(int(np.ceil(sx1)), self.width), min(int(np.ceil(sy1)), self.height)
        SY, SX = np.mgrid[sy0:sy1, sx0:sx1]
        return (slice(sy0, sy1), slice(sx0, sx1)), SX + 0.5, SY + 0.5

    def paint(self, window, mask, depth, rgb):
        hit = mask & (depth > self.depth[window])
        self.image[window][hit] = rgb[hit]
        self.depth[window][hit] = depth[hit]


def _shade(rgb, factor):
    return (np.asarray(rgb, np.float32) * factor).clip(0, 255).astype(np.uint8)


def _paint_top(canvas, field, x, y, z):
    ox, oy = canvas.world['origin']
    window, SX, SY = canvas.window(ox + (x - y - 1) * 24, ox + (x - y + 1) * 24,
                                   oy + (x + y) * 12 - z, oy + (x + y + 2) * 12 - z)
    a, b = (SX - ox) / 24, (SY - oy + z) / 12
    wx, wy = (a + b) / 2, (b - a) / 2
    mask = (wx >= x) & (wx < x + 1) & (wy >= y) & (wy < y + 1)
    palette = np.array([COLORS[n] for n in field.names], np.uint8)
    canvas.paint(window, mask, (wx + wy).astype('<f4'), palette[field.labels_at(wx, wy)])


def _faces(world):
    W, H = world['width'], world['height']
    heights, cells = world['heights'], world['cells']
    transitions = {tuple(sorted(map(tuple, pair))) for pair in world['transitions']}
    for y in range(H):
        for x in range(W):
            z = heights[y][x]
            for side, nx, ny in (('east', x + 1, y), ('south', x, y + 1)):
                outer = nx >= W or ny >= H
                low = -SKIRT if outer else heights[ny][nx]
                if z <= low:
                    continue
                if outer:
                    kind = 'soil'
                elif cells[y][x] == 'stairs' or tuple(sorted([(x, y), (nx, ny)])) in transitions:
                    kind = 'stone'
                else:
                    kind = 'cliff'
                yield x, y, side, z, low, kind


def _paint_face(canvas, field, x, y, side, top, low, kind):
    ox, oy = canvas.world['origin']
    if side == 'east':
        window, SX, SY = canvas.window(ox + (x - y) * 24, ox + (x + 1 - y) * 24,
                                       oy + (x + 1 + y) * 12 - top, oy + (x + 2 + y) * 12 - low)
        wx = np.full(SX.shape, x + 1.0)
        wy = wx - (SX - ox) / 24
        along, mask = wy, (wy >= y) & (wy < y + 1)
    else:
        window, SX, SY = canvas.window(ox + (x - y - 1) * 24, ox + (x - y) * 24,
                                       oy + (x + y + 1) * 12 - top, oy + (x + y + 2) * 12 - low)
        wy = np.full(SX.shape, y + 1.0)
        wx = (SX - ox) / 24 + wy
        along, mask = wx, (wx >= x) & (wx < x + 1)
    h = (wx + wy) * 12 - (SY - oy)
    mask &= (h >= low) & (h < top)
    shade = FACE_SHADE[side] * (RISER_SHADE if kind == 'stone' else 1)
    rgb = np.broadcast_to(_shade(COLORS[kind], shade), (*SX.shape, 3)).copy()
    if kind != 'stone' and 'grass' in field.names:
        edge = field.labels_at(wx - (side == 'east') * 1e-3, wy - (side == 'south') * 1e-3) == field.names.index('grass')
        lip = (top - h) < 2 + 2.5 * np.abs(np.sin(along * 7.3 + x * 1.7) * np.cos(along * 3.1 + y))
        rgb[mask & edge & lip] = _shade(COLORS['grass'], LIP_SHADE)
    canvas.paint(window, mask, (wx + wy).astype('<f4'), rgb)


def cliff_edges(world):
    heights = world['heights']
    transitions = {tuple(sorted(map(tuple, p))) for p in world['transitions']}
    for y, row in enumerate(heights):
        for x, z in enumerate(row):
            for (nx, ny), a, b in (((x + 1, y), (x + 1, y), (x + 1, y + 1)), ((x, y + 1), (x, y + 1), (x + 1, y + 1)),
                                   ((x - 1, y), (x, y), (x, y + 1)), ((x, y - 1), (x, y), (x + 1, y))):
                inside = 0 <= nx < world['width'] and 0 <= ny < world['height']
                if inside and z > heights[ny][nx] and tuple(sorted([(x, y), (nx, ny)])) not in transitions:
                    yield a, b, z


def render_guide(world):
    """Technical-color organic blockout at the world canvas plus its per-pixel depth."""
    field = SurfaceField(world)
    canvas = _Canvas(world)
    for y, row in enumerate(world['heights']):
        for x, z in enumerate(row):
            _paint_top(canvas, field, x, y, z)
    for face in _faces(world):
        _paint_face(canvas, field, *face)
    image = Image.fromarray(canvas.image)
    draw = ImageDraw.Draw(image)
    for a, b, z in cliff_edges(world):
        draw.line([project(world, *a, z), project(world, *b, z)], fill=CLIFF_EDGE, width=1)
    return np.asarray(image), canvas.depth


def provider_frame(world):
    """Smallest 3:2 frame around the world canvas and the canvas offset inside it."""
    width, height = world['canvas']
    k = max(-(-width // ASPECT[0]), -(-height // ASPECT[1]))
    size = (ASPECT[0] * k, ASPECT[1] * k)
    return size, ((size[0] - width) // 2, (size[1] - height) // 2)


def guide_png(world):
    size, offset = provider_frame(world)
    framed = Image.new('RGB', size, BACKGROUND)
    framed.paste(Image.fromarray(render_guide(world)[0]), offset)
    out = io.BytesIO()
    framed.save(out, format='PNG', optimize=False)
    return out.getvalue()


def register(world, source):
    """Uniformly rescales the painted frame to the guide frame and crops the world canvas."""
    image = Image.open(io.BytesIO(source))
    if image.format != 'PNG':
        raise ValueError('Szenenbild muss PNG sein')
    image = image.convert('RGB')
    size, offset = provider_frame(world)
    target = size[0] / size[1]
    if abs(image.width / image.height - target) > ASPECT_TOLERANCE * target:
        raise ValueError('Szenenbild hat nicht das angeforderte Seitenverhältnis ' + ASPECT_RATIO)
    width, height = world['canvas']
    framed = image.resize(size, Image.Resampling.LANCZOS)
    terrain = np.asarray(framed.crop((offset[0], offset[1], offset[0] + width, offset[1] + height)))
    return terrain, {'mode': 'painted-scene/1', 'source_size': list(image.size), 'frame_size': list(size),
                     'canvas_offset': list(offset), 'canvas': [width, height], 'resample': 'uniform-lanczos'}


def _materials(material_plan):
    return '; '.join(f'{k}: {v}' for k, v in sorted(material_plan.get('materials', {}).items()))


def _regions(world, member):
    seen, count = set(), 0
    for start in ((x, y) for y in range(world['height']) for x in range(world['width'])):
        if start in seen or not member(*start):
            continue
        count += 1
        seen.add(start)
        stack = [start]
        while stack:
            x, y = stack.pop()
            for n in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if 0 <= n[0] < world['width'] and 0 <= n[1] < world['height'] and n not in seen and member(*n):
                    seen.add(n)
                    stack.append(n)
    return count


def inventory(world):
    """Countable terrain features of the frozen grid that a faithful painting must reproduce exactly."""
    cells, heights = world['cells'], world['heights']
    return {'ponds': _regions(world, lambda x, y: cells[y][x] == 'water'),
            'raised_areas': _regions(world, lambda x, y: heights[y][x] > 0 and cells[y][x] != 'stairs'),
            'stair_flights': _regions(world, lambda x, y: cells[y][x] == 'stairs'),
            'height_levels': len({heights[y][x] for y, row in enumerate(cells) for x, cell in enumerate(row) if cell != 'stairs'})}


def _inventory_text(world):
    counts = inventory(world)
    return (f"exactly {counts['ponds']} pond(s), {counts['raised_areas']} raised area(s), "
            f"{counts['stair_flights']} stair flight(s) and {counts['height_levels']} height level(s)")


def prompt(world, material_plan, correction=None):
    return (
        'Image 1 is a flat-colored 2:1 isometric blockout of a small terrain island and is the exact geometry '
        'authority. Its colors are technical placeholders, not materials. Repaint it as one finished, detailed '
        'pixel-art isometric game map with the same camera, framing and scale. Image 2 is STYLE ONLY: copy its '
        'palette, pixel clusters, outlines and shading technique; never copy its buildings, trees, characters, '
        'fences, objects or layout. Keep every region exactly where it is: island outline, water, paths and paved '
        'areas, raised plateaus with their cliff faces and the stair steps keep their position, size and shape. '
        'Image 1 contains ' + _inventory_text(world) + '; the painting contains exactly these, with no added '
        'ponds, terraces, walls, ledges or notches in the island edge, even where image 2 shows them. Cliff faces '
        'keep exactly the height drawn in image 1 and stay natural rock and soil, never masonry. '
        'Material intent: ' + material_plan.get('intent', '') + ' Materials by blockout region: '
        + _materials(material_plan) + '. Make the terrain look natural: soft irregular edges between ground '
        'materials, small ground detail overhanging path edges, a natural bank around water, layered cliff faces '
        'with a lip of the top ground material, clear individual stair steps, and a soil side edge around the '
        'island. No buildings, trees, bushes, fences, props, characters, text or cast shadows. Keep the flat '
        'dark background.'
        + ((' CORRECTIVE REPAINT: ' + correction + ' Fix only these findings and keep everything else.') if correction else ''))


def review_prompt(world, material_plan, criteria):
    return (
        'Independent visual review, stage review_final, painted-scene route. All seven criteria ' + str(list(criteria))
        + '. Each verdict pass/fail/uncertain with concrete observation and correction. Every criterion cites '
        'final; layout_fidelity and walkable_clearance also cite guide; all other criteria also cite reference. '
        'final is one painted isometric scene; guide is the technical-color blockout of the frozen collision grid '
        '(green ground, brown path, sand bank, blue water, pale stone stairs, grey-brown cliff faces, dark-green '
        'cliff top edges); its colors are placeholders, never material identity. layout_fidelity: every water '
        'area, path, plateau, cliff face and stair in final sits where the guide has it, with no added or missing '
        'height levels; the guide contains ' + _inventory_text(world) + ', and any extra or missing pond, raised '
        'area, wall, terrace or edge notch in final fails layout_fidelity. walkable_clearance: no water, cliff, object or tall foliage covers ground that is walkable '
        'in the guide, and stairs are readable as the only connection between levels. Also judge materials, '
        'pixel_style, scale, repetition and lighting against the reference, which is style only. Soft natural '
        'edges that stay within about a quarter cell of the guide boundaries are intended, not a failure. '
        'local_sampling must be null. Material plan: ' + json.dumps(material_plan, sort_keys=True))
