# Assembly plan and executable check

Keep this sidecar next to the host scene. It is not a new runtime scene format.
It describes **expected** placement and traversal, against which the checker reads
the actual scene. Choose expectations before fitting the art, and keep source
measurements distinct from inferred or authored geometry.

```json
{
  "version": 1,
  "actor": "traveler",
  "tolerancePx": 1,
  "placements": [{
    "entity": "fountain",
    "origin": { "c": 1, "r": 8 },
    "contacts": [{
      "texture": "fountain-0",
      "source": { "x": 16, "y": 160 },
      "grid": { "c": -0.5, "r": -0.5 }
    }]
  }],
  "blocked": [{ "c": 1, "r": 8 }],
  "open": [{ "c": 4, "r": 5 }],
  "routes": [{ "id": "cross", "from": {"c": 0, "r": 5}, "to": {"c": 12, "r": 5}, "reachable": true }],
  "paths": [{ "id": "under", "points": [{"c": 4, "r": 4}, {"c": 4, "r": 5}, {"c": 4, "r": 6}] }],
  "clearances": [{ "id": "under-deck", "cell": {"c": 4, "r": 5}, "height": 48 }],
  "solidHeights": [{ "id": "stone-center", "cell": {"c": 2, "r": 9}, "minHeight": 86 }]
}
```

These numbers illustrate the bundled calibration fixture, not universal asset
dimensions. Expand contacts to at least three noncollinear rigid landmarks and
include the frames that could drift. Contact `source` is frame-local pixels;
`grid` is relative to the entity's origin; optional `height` is the vertical
landmark height above that origin. Texture anchors and actual visual overrides,
width, scale and offset are read from the scene.

`blocked`/`open` inspect single-cell occupancy. `routes` checks reachability;
`paths` checks every specified consecutive walking segment, including actual
actor footprint and floor links. A route that detours does not establish that
the intended underpass works; declare its exact path. Floor IDs default to ground.
`clearances` checks the current engine's floor-slab thickness formula against a
body height. It is a static authoring check, not complete swept body collision.
`solidHeights` requires a blocking body on that cell/floor with an explicit height
at least the declared minimum. It checks body height, not floating absolute volume
or the visible silhouette. Keep those source heights in the asset measurements.
An actual jump probe remains necessary when vertical traversal matters.

From the repository root, with Node 22.18+:

```sh
node --experimental-strip-types skills/multi-tile-asset-assembly/scripts/check-assembly.mjs path/to/scene.json path/to/assembly-plan.json
```

The checker uses the public source core in a checkout or built core in an installed
package. It checks named static textures and base animation frames; directional
overrides and other runtime clip changes need an explicit rendered check. It
never changes the scene or moves a live actor. Nonzero exit means a declared
expectation failed. Passing an empty/sparse plan only proves those sparse claims.
Pair its output with one close-up overlay and the requested actual game route.
