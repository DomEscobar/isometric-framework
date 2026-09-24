"""Deterministic acceptance of a TerrainSpec: generation, path width, parallel strands, reachability and feature counts."""
from hybrid_layout import compile_layout
from hybrid_painted_scene import inventory
from terrain_generate import SpecError, generate
from terrain_spec import TerrainSpec

TRAIL = ('path', 'stairs')
POCKET_CELLS = 3


def wide_path_blocks(layout):
    cells = layout['cells']
    return [[x, y] for y in range(layout['height'] - 1) for x in range(layout['width'] - 1)
            if all(cells[y + dy][x + dx] == 'path' for dx in (0, 1) for dy in (0, 1))]


def enclosed_pockets(layout, max_cells=POCKET_CELLS):
    """Small non-path regions whose every edge neighbour is path: parallel strands that read as one smeared road."""
    cells, width, height = layout['cells'], layout['width'], layout['height']
    walked = set()
    pockets = []
    for start in ((x, y) for y in range(height) for x in range(width)):
        if start in walked or cells[start[1]][start[0]] in TRAIL:
            continue
        region, stack, open_edge = [], [start], False
        walked.add(start)
        while stack:
            x, y = stack.pop()
            region.append([x, y])
            for n in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if not (0 <= n[0] < width and 0 <= n[1] < height):
                    open_edge = True
                elif cells[n[1]][n[0]] not in TRAIL and n not in walked:
                    walked.add(n)
                    stack.append(n)
        if not open_edge and len(region) <= max_cells:
            pockets.append(sorted(region)[0])
    return pockets


def check(spec: TerrainSpec):
    """Returns (compiled world, []) when the spec is accepted, otherwise (None, issues)."""
    try:
        layout = generate(spec)
    except SpecError as error:
        return None, error.issues
    issues = [f'Weg ist bei {b} breiter als eine Zelle (2x2-Block); Wegpunkte oder Abzweig verschieben' for b in wide_path_blocks(layout)]
    issues += [f'Wege laufen parallel und schließen bei {p} eine Grasinsel ein; Abzweig früher oder weiter entfernt ansetzen'
               for p in enclosed_pockets(layout)]
    try:
        world = compile_layout(layout)
    except ValueError as error:
        return None, issues + [str(error)]
    counts = inventory(world)
    expected = {'ponds': len(spec.ponds), 'raised_areas': len(spec.plateaus), 'stair_flights': len(spec.plateaus)}
    issues += [f'{name}: erwartet {want}, erzeugt {counts[name]} (Flächen berühren sich)' for name, want in expected.items() if counts[name] != want]
    return (None, issues) if issues else (world, [])
