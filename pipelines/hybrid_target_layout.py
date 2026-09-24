"""Deterministic structural contract for the flat-water meadow target."""
from collections import deque

CONTRACT = 'flat-pond-path-plateau/1'


def _components(points):
    remaining = set(points)
    parts = []
    while remaining:
        seed = remaining.pop()
        part = {seed}
        queue = deque([seed])
        while queue:
            x, y = queue.popleft()
            for q in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if q in remaining:
                    remaining.remove(q)
                    part.add(q)
                    queue.append(q)
        parts.append(part)
    return parts


def target_layout_issues(layout):
    """Return deterministic target-contract violations; never infer visual quality."""
    issues = []
    width, height = layout['width'], layout['height']
    cells, heights = layout['cells'], layout['heights']
    water = {(x, y) for y in range(min(height, len(cells))) for x in range(min(width, len(cells[y]))) if cells[y][x] == 'water'}
    if len(water) != 9:
        issues.append('water must be exactly one compact 3x3 patch')
    elif (max(x for x, _ in water) - min(x for x, _ in water) != 2 or
          max(y for _, y in water) - min(y for _, y in water) != 2 or
          len(water) != (max(x for x, _ in water) - min(x for x, _ in water) + 1) *
                         (max(y for _, y in water) - min(y for _, y in water) + 1)):
        issues.append('water must form one axis-aligned 3x3 patch')
    if any(y < len(heights) and x < len(heights[y]) and heights[y][x] != 0 for x, y in water):
        issues.append('water must stay at base height')
    for x, y in water:
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if 0 <= nx < width and 0 <= ny < height and (nx, ny) not in water and ny < len(cells) and nx < len(cells[ny]):
                if cells[ny][nx] != 'land' or ny >= len(heights) or nx >= len(heights[ny]) or heights[ny][nx] != 0:
                    issues.append('water needs a continuous base-level land shoreline')
                    break
        else:
            continue
        break

    plateau = {(x, y) for y in range(min(height, len(cells))) for x in range(min(width, len(cells[y]))) if cells[y][x] in ('plateau', 'square')}
    stairs = {(x, y) for y in range(min(height, len(cells))) for x in range(min(width, len(cells[y]))) if cells[y][x] == 'stairs'}
    paths = {(x, y) for y in range(min(height, len(cells))) for x in range(min(width, len(cells[y]))) if cells[y][x] == 'path'}
    if not plateau:
        issues.append('one raised plateau is required')
    else:
        xs, ys = [x for x, _ in plateau], [y for _, y in plateau]
        x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
        if len(plateau) != (x1 - x0 + 1) * (y1 - y0 + 1):
            issues.append('plateau must be one coherent rectangle')
        if x0 < 1 or y0 < 1 or x1 > width - 2 or y1 > height - 2:
            issues.append('plateau must leave a one-cell walkable margin at the board edges')
        plateau_levels = {heights[y][x] for x, y in plateau if y < len(heights) and x < len(heights[y])}
        if len(plateau_levels) != 1 or next(iter(plateau_levels), 0) == 0:
            issues.append('plateau must be one flat raised level')
        plateau_level = next(iter(plateau_levels), 0)

    if not stairs:
        issues.append('exactly one stair strip is required')
    if stairs:
        parts = _components(stairs)
        if len(parts) != 1:
            issues.append('stairs must be one contiguous strip; no extra stair runs')
        sx, sy = [x for x, _ in stairs], [y for _, y in stairs]
        sx0, sx1, sy0, sy1 = min(sx), max(sx), min(sy), max(sy)
        if len(stairs) != (sx1 - sx0 + 1) * (sy1 - sy0 + 1):
            issues.append('stairs must form one straight rectangular strip')
        transitions = []
        for a, b in layout['transitions']:
            ax, ay = a; bx, by = b
            if ay < len(heights) and by < len(heights) and ax < len(heights[ay]) and bx < len(heights[by]) and abs(heights[ay][ax] - heights[by][bx]) == 8:
                transitions.append((tuple(a), tuple(b)))
        stair_to_plateau = [(a, b) for a, b in transitions if (a in stairs and b in plateau) or (b in stairs and a in plateau)]
        stair_risers = [(a, b) for a, b in transitions if a in stairs or b in stairs]
        # A supported step is a one-cell-height edge into the plateau; the
        # staircase ribbon itself is rendered by the compiler, not every tread
        # encoded as a separate elevated cell.
        stair_levels = {heights[y][x] for x,y in stairs if y < len(heights) and x < len(heights[y])}
        stair_reaches_plateau = any(
            (a in stairs and b in plateau and abs(heights[a[1]][a[0]]-heights[b[1]][b[0]]) == 8) or
            (b in stairs and a in plateau and abs(heights[b[1]][b[0]]-heights[a[1]][a[0]]) == 8)
            for a,b in transitions
        )
        if not stair_reaches_plateau:
            issues.append('stair strip must have an explicit traversable 8px rise to the plateau')
        if plateau and not stair_to_plateau:
            issues.append('stair strip must connect directly to the raised plateau')
        if stair_to_plateau:
            plateau_levels_at_steps = [heights[p[1]][p[0]] for edge in stair_to_plateau for p in edge if p in plateau]
            if any(level != plateau_level for level in plateau_levels_at_steps):
                issues.append('staircase must reach the plateau level')
        if any(a not in stairs and b not in stairs for a, b in transitions):
            issues.append('every height transition must touch the stair strip')

    if not paths:
        issues.append('one straight path from spawn to stairs is required')
    else:
        px, py = [x for x, _ in paths], [y for _, y in paths]
        if min(py) != max(py) and min(px) != max(px):
            issues.append('path must be one-cell-wide and straight')
        if min(px) != max(px) and min(py) != max(py):
            issues.append('path must be one-cell-wide and straight')
        if not any(abs(x - sx) + abs(y - sy) == 1 for x, y in paths for sx, sy in stairs):
            issues.append('path must end adjacent to the single stair strip')
        spawn = tuple(layout['spawn'])
        if min(abs(spawn[0] - x) + abs(spawn[1] - y) for x, y in paths) > 1:
            issues.append('path must begin at the spawn')
        if any(y >= len(heights) or x >= len(heights[y]) or heights[y][x] != 0 for x, y in paths):
            issues.append('path must remain at base height')
    return sorted(set(issues))
