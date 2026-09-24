"""Deterministic TerrainSpec -> hybrid-layout/1 grid. Violations are collected as actionable issues."""
import heapq
import math
from terrain_spec import TerrainSpec

ACTOR_WIDTH = .64
STEP = 8
LEVEL_STEPS = 3
OUTWARD = {'north': (0, -1), 'south': (0, 1), 'west': (-1, 0), 'east': (1, 0)}


class SpecError(ValueError):
    def __init__(self, issues):
        super().__init__('; '.join(issues))
        self.issues = issues


LINE_WEIGHT = .15
NETWORK_STEP = .25
BESIDE_NETWORK = 1


def _ring(p):
    return [(p[0] + dx, p[1] + dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1) if dx or dy]


def _line_distance(p, a, b):
    (px, py), (ax, ay), (bx, by) = p, a, b
    length = math.hypot(bx - ax, by - ay)
    return math.hypot(px - ax, py - ay) if not length else abs((bx - ax) * (ay - py) - (ax - px) * (by - ay)) / length


def _widens(p, chain, occupied):
    """True when adding p would complete a 2x2 block of path cells."""
    taken = occupied | set(chain)
    return any(all(c == p or c in taken for c in ((x, y), (x + 1, y), (x, y + 1), (x + 1, y + 1)))
               for x in (p[0] - 1, p[0]) for y in (p[1] - 1, p[1]))


class _Grid:
    def __init__(self, spec):
        self.spec = spec
        self.cells = [['land'] * spec.width for _ in range(spec.height)]
        self.heights = [[0] * spec.width for _ in range(spec.height)]
        self.transitions = []
        self.path_cells = set()
        self.issues = []

    def inside(self, p):
        return 0 <= p[0] < self.spec.width and 0 <= p[1] < self.spec.height

    def cell(self, p):
        return self.cells[p[1]][p[0]]

    def set(self, p, kind, height=None):
        self.cells[p[1]][p[0]] = kind
        if height is not None:
            self.heights[p[1]][p[0]] = height

    def height(self, p):
        return self.heights[p[1]][p[0]]

    def fail(self, message):
        self.issues.append(message)

    def walkable(self, p, q):
        if not self.inside(q) or self.cell(q) == 'water':
            return False
        return self.height(p) == self.height(q) or [list(p), list(q)] in self.transitions or [list(q), list(p)] in self.transitions

    def _step_cost(self, p, q, a, b):
        """Earlier paths are cheap to follow; a new cell beside them costs extra, so branches leave instead of running parallel."""
        if q in self.path_cells:
            return NETWORK_STEP
        beside = sum(1 for n in _ring(q) if n != p and n in self.path_cells)
        return 1 + LINE_WEIGHT * _line_distance(q, a, b) + BESIDE_NETWORK * beside

    def route(self, sources, b, occupied):
        """Cheapest edge-connected route from any source to b near the straight line, never widening the path network."""
        a = min(sources, key=lambda s: (abs(s[0] - b[0]) + abs(s[1] - b[1]), s))
        frontier, best, came = [(0, 0, s) for s in sorted(sources)], {s: 0 for s in sources}, {s: None for s in sources}
        heapq.heapify(frontier)
        while frontier:
            _, cost, p = heapq.heappop(frontier)
            if p == b:
                out = [p]
                while came[out[-1]] is not None:
                    out.append(came[out[-1]])
                return out[::-1]
            if cost > best[p]:
                continue
            chain = [p] + ([came[p]] if came[p] is not None else [])
            for q in ((p[0] + 1, p[1]), (p[0] - 1, p[1]), (p[0], p[1] + 1), (p[0], p[1] - 1)):
                if not self.walkable(p, q) or (q not in occupied and _widens(q, chain, occupied)):
                    continue
                step = cost + self._step_cost(p, q, a, b)
                if step < best.get(q, math.inf):
                    best[q], came[q] = step, p
                    heapq.heappush(frontier, (step + NETWORK_STEP * (abs(q[0] - b[0]) + abs(q[1] - b[1])), step, q))
        return None


def _plateau(grid, index, plateau):
    name = f'plateau {index}'
    if any(not grid.inside(p) for p in plateau.cells()):
        return grid.fail(f'{name} reicht über den Rand')
    if any(grid.cell(p) != 'land' for p in plateau.cells()):
        return grid.fail(f'{name} überlappt ein anderes Plateau')
    for p in plateau.cells():
        grid.set(p, 'plateau', plateau.levels * LEVEL_STEPS * STEP)
    _stairs(grid, name, plateau)


def _stairs(grid, name, plateau):
    stairs = plateau.stairs
    dx, dy = OUTWARD[stairs.side]
    along = range(stairs.offset, stairs.offset + stairs.width)
    span = range(plateau.x, plateau.x + plateau.width) if dx == 0 else range(plateau.y, plateau.y + plateau.height)
    if any(v not in span for v in along):
        return grid.fail(f'{name}: Treppe liegt nicht vollständig an der {stairs.side}-Seite (offset {stairs.offset}, Breite {stairs.width})')
    for v in along:
        if dx == 0:
            top = (v, plateau.y if dy < 0 else plateau.y + plateau.height - 1)
        else:
            top = (plateau.x if dx < 0 else plateau.x + plateau.width - 1, v)
        previous, steps = top, plateau.levels * LEVEL_STEPS
        for step in range(steps):
            p = (top[0] + dx * (step + 1), top[1] + dy * (step + 1))
            if not grid.inside(p) or grid.cell(p) != 'land':
                return grid.fail(f'{name}: Treppe ({steps} Zellen) trifft bei {list(p)} auf Rand oder belegte Zelle')
            grid.set(p, 'stairs', (steps - 1 - step) * STEP)
            grid.transitions.append([list(previous), list(p)])
            previous = p


def _snap_targets(b):
    """A waypoint is intent: its exact cell first, then its edge neighbours in fixed order."""
    x, y = b
    return [b, (x, y - 1), (x + 1, y), (x, y + 1), (x - 1, y)]


def _pond(grid, index, pond):
    name = f'pond {index}'
    ring = {(x, y) for y in range(pond.y - 1, pond.y + pond.height + 1) for x in range(pond.x - 1, pond.x + pond.width + 1)}
    if any(not grid.inside(p) for p in ring):
        return grid.fail(f'{name} braucht einen Landring und darf den Rand nicht berühren')
    if any(grid.cell(p) != 'land' or grid.height(p) for p in ring):
        return grid.fail(f'{name} berührt ein Plateau, eine Treppe oder einen anderen Teich; mindestens eine Landzelle Abstand')
    for p in pond.cells():
        grid.set(p, 'water')


def _path(grid, index, path):
    name = f'path {index}'
    points = [tuple(p) for p in path.waypoints]
    if any(not grid.inside(p) for p in points):
        return grid.fail(f'{name}: Wegpunkt außerhalb des Rasters')
    if any(grid.cell(p) == 'water' for p in points):
        return grid.fail(f'{name}: Wegpunkt liegt im Wasser')
    branch = points[0] in grid.path_cells
    if branch:
        points = [points[0]] + [p for p in points[1:-1] if not any(n in grid.path_cells for n in [p, *_ring(p)])] + [points[-1]]
    cells = []
    for b in points[1:]:
        sources = grid.path_cells if branch and not cells else {cells[-1] if cells else points[0]}
        segment = next(filter(None, (grid.route(sources, t, grid.path_cells | set(cells)) for t in _snap_targets(b))), None)
        if segment is None:
            start = 'dem Wegnetz' if branch and not cells else str(list(cells[-1] if cells else points[0]))
            return grid.fail(f'{name}: kein einzelliger Weg von {start} nach {list(b)} ohne Wasser, Klippe oder Wegverbreiterung')
        cells += segment if not cells else segment[1:]
    for p in cells:
        if grid.cell(p) != 'stairs':
            grid.set(p, 'path')
    grid.path_cells |= set(cells)


def generate(spec: TerrainSpec):
    """Returns a raw hybrid-layout/1 dict or raises SpecError listing every violation found."""
    grid = _Grid(spec)
    for i, plateau in enumerate(spec.plateaus):
        _plateau(grid, i, plateau)
    for i, pond in enumerate(spec.ponds):
        _pond(grid, i, pond)
    for i, path in enumerate(spec.paths):
        _path(grid, i, path)
    if grid.issues:
        raise SpecError(grid.issues)
    return dict(schema='hybrid-layout/1', width=spec.width, height=spec.height, actor_width=ACTOR_WIDTH,
                spawn=list(spec.spawn), goals=[list(g) for g in spec.goals], cells=grid.cells, heights=grid.heights,
                transitions=grid.transitions, unsupported=[])
