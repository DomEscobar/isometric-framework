"""Deterministic flat semantic layouts. No external generation or artwork."""
from collections import deque
import math
import random
import re

MATERIALS = {'grass': '#709867', 'soil': '#a78b61', 'path': '#d5bb86', 'water': '#488baf',
             'street':'#858991', 'sidewalk':'#dfd4b9', 'planting':'#8bb764'}


def coordinate_manifest(layout):
    w, h = layout['width'], layout['height']
    tw, d = layout.get('tile_width', 48), layout.get('density', 1)
    th, pad = tw // 2, 24
    return dict(projection='2:1-flat', floor=0, tile_width=tw, tile_height=th,
                density=d, padding_logical_px=pad, origin_convention='grid-vertex-0-0',
                origin_px=[(pad+h*tw/2)*d, pad*d],
                column_basis_px=[tw/2*d, th/2*d], row_basis_px=[-tw/2*d, th/2*d],
                image_size=[int(((w+h)*tw/2+2*pad)*d), int(((w+h)*th/2+2*pad)*d)],
                cell_sampling='center=(column+0.5,row+0.5); image samples at pixel centers',
                logical_units='one cell; world bounds [0,width] x [0,height]',
                camera='not baked; UI CSS scale independent of texture density')


def project(layout, c, r):
    p = layout['projection']
    return [p['origin_px'][i]+c*p['column_basis_px'][i]+r*p['row_basis_px'][i] for i in (0, 1)]


def interpret(params):
    p = dict(params)
    clauses = {'wiese': ('kind', 'meadow'), 'platz': ('kind', 'plaza'),
               'teich im nordosten': ('kind', 'pond-ne'), 'teich im südwesten': ('kind', 'pond-sw'),
               'weg west-ost': ('path', 'west-east'), 'weg nord-süd': ('path', 'north-south'),
               'weg kreuz': ('path', 'cross'), 'kein weg': ('path', 'none')}
    understood = []
    for raw in p.get('brief', '').split(';'):
        clause = raw.strip().lower()
        if not clause:
            continue
        if clause in clauses:
            key, value = clauses[clause]
        elif re.fullmatch(r'[0-8] bäume', clause):
            key, value = 'trees', int(clause[0])
        elif re.fullmatch(r'[01] haus', clause):
            key, value = 'houses', int(clause[0])
        else:
            raise ValueError('unsupported clause: '+raw.strip()+' — only documented exact clauses are supported')
        if key in p and p[key] != value:
            raise ValueError('conflict: '+key)
        p[key] = value
        understood.append(raw.strip())
    p = dict(dict(width=16, height=14, seed=17, tile_width=48, density=1, actor_width=0.8,
                  kind='meadow', path='none', trees=0, houses=0), **p)
    for key, low, high in [('width',10,28),('height',10,28),('seed',0,2147483647),('trees',0,8),('houses',0,1)]:
        if type(p[key]) is not int or not low <= p[key] <= high:
            raise ValueError('invalid '+key)
    if p['kind'] not in ('meadow','plaza','pond-ne','pond-sw','urban') or p['path'] not in ('none','west-east','north-south','cross'):
        raise ValueError('unsupported kind/path')
    if p['tile_width'] not in (32,48,64) or p['density'] not in (1,2) or type(p['actor_width']) not in (int,float) or not 0.2 <= p['actor_width'] <= 2:
        raise ValueError('invalid projection/actor width')
    unknown = set(p)-{'width','height','seed','tile_width','density','actor_width','kind','path','trees','houses','brief'}
    if unknown:
        raise ValueError('unsupported parameters: '+', '.join(sorted(unknown)))
    return p, understood


def generate(params):
    p, understood = interpret(params)
    w, h = p['width'], p['height']
    layout = dict(schema='layout-terrain/1', width=w, height=h,
                  tile_width=p['tile_width'], density=p['density'], seed=p['seed'],
                  materials=[['grass'] * w for _ in range(h)], objects=[],
                  spawn=[2, 2], goals=[[w-3, h-3]], actor_width=p['actor_width'],
                  interpretation=dict(mode='exact-german-clauses-v1', understood=understood,
                                      resolved=p, unsupported=[], arbitrary_language=False))
    grid = layout['materials']
    for r in range(h):
        for c in range(w):
            if p['kind'] == 'plaza' and abs(c-w//2) <= 3 and abs(r-h//2) <= 3:
                grid[r][c] = 'soil'
            if p['kind'].startswith('pond'):
                cx, cy = (w-4, 2) if p['kind'] == 'pond-ne' else (3, h-3)
                if ((c-cx)/2)**2+((r-cy)/1.5)**2 <= 1:
                    grid[r][c] = 'water'
            path = (p['path'] in ('west-east','cross') and abs(r-h//2) <= 1) or (p['path'] in ('north-south','cross') and abs(c-w//2) <= 1)
            if path:
                if grid[r][c] == 'water':
                    raise ValueError('pond/path overlap: enlarge map or change orientation')
                grid[r][c] = 'path'
    if p['path'] in ('west-east','cross'):
        layout['spawn'], layout['goals'] = [2,h//2], [[w-3,h//2]]
    if p['path'] == 'north-south':
        layout['spawn'], layout['goals'] = [w//2,2], [[w//2,h-3]]
    if p['path'] == 'cross':
        layout['goals'].extend([[w//2,2],[w//2,h-3]])
    layout['projection'] = coordinate_manifest(layout)
    if p['kind'] == 'urban':
        if p['path'] != 'none' or p['trees'] or p['houses']:
            raise ValueError('urban preset owns its street and reservations; no path/tree/house overrides')
        # Original small promenade, not the style reference's intersection.
        # Three-cell carriageway, two-cell sidewalks, inset planting pockets.
        mid = h//2
        for r in range(h):
            for c in range(w):
                grid[r][c] = 'street' if mid-1 <= r <= mid+1 else 'sidewalk'
                if (1 <= r <= mid-4 or mid+4 <= r <= h-2) and 2 <= c <= w-3:
                    if c not in (w//2-1,w//2): grid[r][c] = 'planting'
        layout['spawn'], layout['goals'] = [1,mid-3], [[w-2,mid-3]]
        layout['urban_semantics'] = dict(street_walkable=True, planting_walkable=False,
            required_routes='north sidewalk only; no traffic crossing required',
            traffic='none; empty road traversable by technical test actor, NOT a traffic safety simulation',
            props='reserved only; no production props')
        layout['objects'] = [dict(id='bench-reservation-1',kind='bench',x=1,y=0,w=2,h=1,solid=True,
            support_materials=['sidewalk'],art_extent_status='unknown; reservation only; no production prop art'),
            dict(id='kiosk-reservation-1',kind='kiosk',x=w-4,y=h-1,w=2,h=1,solid=True,
            support_materials=['sidewalk'],art_extent_status='unknown; reservation only; no production prop art')]
    rng = random.Random(p['seed'])
    candidates = [(c,r) for r in range(2,h-3) for c in range(2,w-3)]
    rng.shuffle(candidates)
    for kind, count, size in [('house',p['houses'],2),('tree',p['trees'],1)]:
        for i in range(count):
            placed = False
            for x,y in candidates:
                rect = (x-1,y-1,x+size+1,y+size+1)
                if any(grid[r][c] in ('water','path') for r in range(y,y+size) for c in range(x,x+size)):
                    continue
                if any(overlaps(rect,(o['x'],o['y'],o['x']+o['w'],o['y']+o['h'])) for o in layout['objects']):
                    continue
                if any(overlaps(rect,(c,r,c+1,r+1)) for c,r in [layout['spawn']]+layout['goals']):
                    continue
                obj = dict(id=f'{kind}-{i+1}',kind=kind,x=x,y=y,w=size,h=size,solid=True,
                           support_materials=sorted({grid[r][c] for r in range(y,y+size) for c in range(x,x+size)}),
                           art_extent_status='unknown; reservation only; no production prop art')
                if kind == 'house':
                    obj['approach'] = [x,y-1]
                    layout['goals'].append(obj['approach'])
                layout['objects'].append(obj)
                if validate(layout)['valid']:
                    placed = True
                    break
                layout['objects'].pop()
                if kind == 'house':
                    layout['goals'].pop()
            if not placed:
                raise ValueError('cannot place requested object with actor clearance: '+kind)
    report = validate(layout)
    if not report['valid']:
        raise ValueError('layout invalid: '+', '.join(report['errors']))
    return layout


def overlaps(a, b):
    return a[0] < b[2]-1e-9 and a[2] > b[0]+1e-9 and a[1] < b[3]-1e-9 and a[3] > b[1]+1e-9


def validate(layout):
    errors = []
    try:
        if layout.get('schema') != 'layout-terrain/1':
            raise ValueError('schema')
        w, h = layout['width'], layout['height']
        if type(w) is not int or type(h) is not int or not (10 <= w <= 28 and 10 <= h <= 28):
            raise ValueError('bounds')
        if layout.get('tile_width') not in (32, 48, 64) or layout.get('density') not in (1, 2):
            raise ValueError('projection_parameters')
        aw = layout['actor_width']
        if type(aw) not in (float, int) or not math.isfinite(aw) or not 0.2 <= aw <= 2:
            raise ValueError('actor_width')
        grid = layout['materials']
        if len(grid) != h or any(len(row) != w or any(v not in MATERIALS for v in row) for row in grid):
            raise ValueError('material_partition')
        if layout['projection'] != coordinate_manifest(layout):
            errors.append('geometry_transform_mismatch')
        blocked = [(c, r, c+1, r+1) for r in range(h) for c in range(w) if grid[r][c] in ('water','planting')]
        reservations, ids = [], set()
        for obj in layout['objects']:
            if obj['id'] in ids:
                errors.append('duplicate_object_id')
            ids.add(obj['id'])
            x, y, ow, oh = [obj[k] for k in ('x', 'y', 'w', 'h')]
            if any(type(v) is not int for v in (x, y, ow, oh)) or ow < 1 or oh < 1 or x < 0 or y < 0 or x+ow > w or y+oh > h:
                raise ValueError('object_bounds')
            if type(obj['solid']) is not bool:
                raise ValueError('object_solid')
            rect = (x, y, x+ow, y+oh)
            if any(overlaps(rect, previous) for previous in reservations):
                errors.append('object_overlap')
            if any(grid[r][c] == 'water' for r in range(y, y+oh) for c in range(x, x+ow)):
                errors.append('object_support')
            support = sorted({grid[r][c] for r in range(y,y+oh) for c in range(x,x+ow)})
            if 'support_materials' in obj and obj['support_materials'] != support:
                errors.append('object_support_mismatch')
            if obj.get('kind') == 'house':
                a = obj.get('approach', [])
                adjacent = len(a) == 2 and ((a[1] in (y-1,y+oh) and x <= a[0] < x+ow) or (a[0] in (x-1,x+ow) and y <= a[1] < y+oh))
                if not adjacent or a not in layout['goals']:
                    errors.append('object_approach')
            reservations.append(rect)
            if obj['solid']:
                blocked.append(rect)
        def clear(a, b):
            half = aw / 2
            rect = (min(a[0], b[0])+.5-half, min(a[1], b[1])+.5-half,
                    max(a[0], b[0])+.5+half, max(a[1], b[1])+.5+half)
            return rect[0] >= 0 and rect[1] >= 0 and rect[2] <= w and rect[3] <= h and not any(overlaps(rect, box) for box in blocked)
        def cell(value):
            if not isinstance(value, list) or len(value) != 2 or any(type(v) is not int for v in value) or not (0 <= value[0] < w and 0 <= value[1] < h):
                raise ValueError('endpoint_bounds')
            return tuple(value)
        start = cell(layout['spawn'])
        goals = [cell(v) for v in layout['goals']]
        if not goals:
            raise ValueError('goals_required')
        safe = {(c, r) for r in range(h) for c in range(w) if clear((c, r), (c, r))}
        graph = {}
        for a in sorted(safe):
            graph[a] = [b for b in ((a[0]+1,a[1]),(a[0],a[1]+1),(a[0]-1,a[1]),(a[0],a[1]-1)) if b in safe and clear(a,b)]
        parent = {start: None} if start in safe else {}
        queue = deque(parent)
        while queue:
            a = queue.popleft()
            for b in graph[a]:
                if b not in parent:
                    parent[b] = a
                    queue.append(b)
        paths = []
        for goal in goals:
            if goal not in parent:
                errors.append('disconnected_route')
                continue
            path, at = [], goal
            while at is not None:
                path.append(list(at))
                at = parent[at]
            paths.append(path[::-1])
        return dict(valid=not errors, errors=sorted(set(errors)), reachable_goals=len(paths),
                    safe_cells=[list(v) for v in sorted(safe)], routes=paths,
                    graph={f'{a[0]},{a[1]}': [list(v) for v in bs] for a, bs in graph.items()},
                    clearance_model='axis-aligned square actor; exact swept AABB per cardinal center-to-center edge; no diagonals; touching allowed',
                    scope='semantic collision only; not image compliance or final-art approval')
    except (KeyError, TypeError, ValueError, IndexError) as exc:
        return dict(valid=False, errors=sorted(set(errors+[str(exc)])), reachable_goals=0)
