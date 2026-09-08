# Raised-bed material recipe

Run from the Runtime folder, or use absolute paths to the helper and recipe.
Node.js 22.18+, Playwright and its Chromium binary are authoring dependencies:
the source checkout provides Playwright through `npm ci`; run
`npx playwright install chromium` once if absent. An installed npm runtime does
not install these development dependencies: install Playwright in the authoring
workspace so the helper can resolve it. No provider key is used by preparation.

```json
{
  "version": 1,
  "source": "material-source.png",
  "tileWidth": 64,
  "tileHeight": 32,
  "wallHeight": 12,
  "rimWidth": 0.125,
  "materialResolution": 32,
  "alphaMode": "require-opaque",
  "materials": {
    "soil": [16, 16, 590, 590],
    "cap": [644, 16, 590, 590],
    "wall": [16, 644, 590, 590],
    "grass": [644, 644, 590, 590]
  }
}
```

These crop coordinates fit the lab's actual 1254×1254 source. Measure your own
decoded image; do not assume a provider returned requested dimensions.
`source` resolves relative to the recipe. Rectangles are `[x,y,width,height]` in
source pixels. All crop pixels must be opaque unless the explicit material-only
alpha policy in the skill applies; the lab uses that policy for its source.

- Tile width: integer 32–256, multiple of four. Tile height: exactly width/2.
- Wall height: integer 1–tileHeight in the same world pixels as actors.
- Rim width: fraction of a tile, greater than zero and at most 0.25.
- Material resolution: integer 8–256, default 32. Each crop is prefiltered to this
  square before nearest sampling into the output. This controls source detail
  density separately from tile geometry; changing it needs a rendered check.
- Defaults: 64×32 tile, 12px wall, 0.125 rim, strict opacity. Renderer sampling is
  `nearest`. Face shading is fixed in this helper: front-left RGB×0.84.

Outputs overwrite only the named output artifacts in the given directory:

| File | Meaning |
| --- | --- |
| `bed-atlas.png` | 47 bed frames and one grass region |
| `tileset.json` | Mask-to-texture catalog, frames, anchors, world tile/body dimensions |
| `preparation.json` | Source hash, decoded dimensions, recipe and per-mask signatures |

At64×32 with12px walls, bed frames are80×72, with contact at (40,48).
The top is raised 12px above that ground contact. Grass uses a tight64×32 region.
Use emitted metadata; do not auto-trim frames or guess bottom-center anchors.
Texture IDs are `bed-<mask>`; mask 255 is surrounded soil, mask 0 is isolated.

The helper imports the package's public core source in a checkout, or built
`dist/core.js` in an installed package. It fails for bad geometry, crops, alpha
or identical generated variant signatures. Signature uniqueness is a smoke check,
not a proof of compatible edges. Repeat output is deterministic in the same
Node/Chromium environment; browser image filtering is not a cross-version binary
reproducibility guarantee.
