# Material quilting: preferred continuous natural ground

For **new grass, earth, moss and leaf-floor worlds**, prefer generated shared
material swatches + deterministic overlap quilting + host-owned material masks +
explicit generated contact-edge art, then bind the assembled cache. This is not
whole-map generative painting, a shader, or runtime terrain synthesis. It keeps
large-map geography and playable geometry under host control. Preserve an already
approved composed painting or a contract that calls for another route.

## Choose the right responsibility

- **Quilting** extends a source material by selecting overlapping patches and
  minimum-error cuts. It reduces regular repetition within each material. It does
  not invent convincing material boundaries or choose routes.
- **Blob/cardinal autotiling** selects neighbor topology. **Wang tiles** enforce
  compatible edge labels; **WFC** solves catalog constraints. These remain useful
  for editable maps, discrete connections, paving and architectural modules.
  They are not synonyms for quilting or automatically worse alternatives.
- **Composed painting** remains valid when accepted as the layout's artwork.
  Full-world image-to-image is optional, not the default cure for repeatedly soft
  or drifting terrain. Test a small mixed-material window before the literal
  requested full-world dimensions; the pilot does not reduce the agreed world.

## Production sequence

1. Freeze host layout, protected routes, map dimensions, projection, player foot
   anchors and source-to-screen density. Export the layout guide. Never slide
   collision or object footprints to hide an art defect.
2. Generate compatible, opaque, cropped material swatches at the retained density.
   Keep source records in the host. Use image 1 as the **style/material authority**
   and image 2 as the **geometry/boundary guide**, explicitly naming those roles.
   Avoid objects, cast shadows and baked tile borders in interior swatches.
3. Generate the required **contact-edge family** for touching material pairs:
   straight, inside/outside corner and end, with a shared transition band and
   palette. See [modular prompts](modular-terrain-prompts.md). Boundary-family
   generation remains art work. The [landscape compositor](landscape-ground-assembly.md)
   applies the explicit orientation-aware catalog after quilting; the quilting CLI
   itself does **not** automatically stamp that catalog. An isotropic contact
   material can be an additional quilted material selected by a host-authored band
   in `materialMask`. Do not pass directional edge strips as interior swatches.
4. Assemble shared material planes with the shipped CLI. The required `cells`
   records semantic ownership; optional `materialMask` supplies exact raster
   ownership, including irregular bands and protected walking strips. No blending,
   inferred path width, random geography or per-cell tint is applied.
5. Run `compose-landscape-ground.py` when contacts/underlays are required, following
   [ground assembly](landscape-ground-assembly.md). It preserves protected path/water
   pixels during the object-underlay pass. Bind its cache with `bind-ground.mjs`. Keep flat ground elevation
   zero and top tile colors `0xffffff` **in the input scene**; the binder deliberately
   preserves host colors, collision, entities, side textures and gameplay fields.
   A host can retain an earth `sideTexture` for exterior faces instead of a white
   rim. Raised/multiple-floor terrain is not supported by this adapter.
6. Inspect ground-only native play-scale views, bends, junctions, protected routes
   and the whole-map overview; restore props and test keyboard/touch traversal.
   Assert every frame centre against public `project()` and no missing assets or
   unintended holes. Numeric coverage proves neither attractive art nor contact
   quality. Separate static terrain acceptance from animation and whole-game gates.

**Leaf litter is a material, not lighting.** Do not distribute default circular,
root-centred brown patches around every tree: they can look like fake shadows.
Author irregular, sparse, palette-compatible coverage separately from contact and
cast lighting, protect paths, and review the actual result. The tool has no tree
placement or shadow heuristic.

## Run from a standalone consumer

Python is an optional **offline authoring** dependency, not a runtime dependency.
Use Python 3.12+ for the pinned dependencies below:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install Pillow==12.3.0 numpy==2.5.0
# From the generated game's root after npm install:
.venv/bin/python -B node_modules/isometric-framework/skills/consistent-tileset-authoring/scripts/create-quilting-fixture.py diagnostics/quilt
.venv/bin/python -B node_modules/isometric-framework/skills/consistent-tileset-authoring/scripts/quilt-materials.py diagnostics/quilt/recipe.json --out public/art/quilt-diagnostic
node node_modules/isometric-framework/skills/consistent-tileset-authoring/scripts/bind-ground.mjs diagnostics/quilt/scene.json public/art/quilt-diagnostic/packed-art.json --out diagnostics/bound --image-url ./art/quilt-diagnostic/ground.png
.venv/bin/python -B node_modules/isometric-framework/skills/isometric-visual-loop/scripts/verify-world.py inspect public/art/quilt-diagnostic/packed-art.json --out diagnostics/inspection
```

The fixture is deliberately flat synthetic color, **not production art**. Import
`diagnostics/bound/scene.json` as the host scene to see the diagnostic. Replace the
recipe and fixtures with the game's own generated sources for production. No
example or source-game assets ship with this workflow. No provider calls occur.

## Version 1 recipe

Paths are relative to the recipe directory and must remain inside it (symlinks
are resolved). Sources must be static, fully opaque PNGs at least `patch` pixels
on both axes. Crop/reduce generated swatches **once** before compiling, using an
integer reduction and the selected pixel treatment. The compiler copies source
pixels at 1:1; it does not resize sources or increase their detail.

```json
{
  "version": 1,
  "map": {"columns": 3, "rows": 2, "tileWidth": 32, "tileHeight": 16},
  "cells": [["grass", "earth", "grass"], ["grass", "earth", "grass"]],
  "materials": {
    "grass": {"source": "grass.png"},
    "earth": {"source": "earth.png"}
  },
  "sourceScale": 2,
  "seed": 27,
  "patch": 24,
  "overlap": 6,
  "candidates": 16
}
```

Unknown fields reject. Required fields are shown; only `sourceScale` defaults to
1 and `materialMask` is optional. Map dimensions are 1..256 per axis, logical tile
dimensions are even integers 2..1024. `sourceScale` is an integer 1..8 source pixels
per logical world pixel, **not** a world-size change. Measure camera zoom, CSS,
canvas backing resolution and DPR too. Keep actor foot anchors and logical sizes
unchanged; use nearest sampling and review at the actual screen transform.

`seed` is 0..2^32-1, `patch` is 2..512, `overlap` is 1..patch-1, `candidates` is
1..128. At least two and at most 32 named materials are required. Material seeds
are the base seed plus alphabetical material index, wrapping at 2^32. Every cell
must name a material. A mask does not rewrite semantic cell ownership or collision.

Optional `materialMask` is a canvas-sized L or indexed P PNG whose values are
zero-based indices into **alphabetically sorted material names** (earth=0,
grass=1 above); every pixel must name a material. It **replaces** raster ownership,
not just a partial overlay. The host must protect paths and establish agreement
between semantic cells and its mask. Palette colors and alpha do not select IDs.
There is no automatic feathering or artistic edge guarantee.

Canvas dimensions are `(columns+rows)*tileWidth*sourceScale/2` by
`(columns+rows)*tileHeight*sourceScale/2`. Origin is
`[-tileWidth*sourceScale/2, -columns*tileHeight*sourceScale/2]` in source pixels.
Pixel-centre inverse projection uses c northeast and r southeast. Outside the
map diamond, ownership clamps to the nearest cell indices to supply opaque crop
margins; runtime diamond clipping determines the visible map boundary.

## Output, caching and limits

- `ground.png`: opaque continuous cache, not a tile variant pool.
- `material-mask.png`: exact raster ownership for auditing.
- `manifest.json` and `packed-art.json`: existing prepared-ground surface format;
  `composition.sourceScale` is understood by the binder (absent means 1).
- `provenance.json`: recipe/source/tool/output hashes, dependency versions, seed
  and parameters, per-material semantic cell counts and raster pixel counts,
  canvas bounds and overlap costs. No absolute host paths or provider credentials.

`cacheKey` identifies recipe bytes, sources, tool revision, dependency versions,
parameters and measurements. Keep outputs under that key in host build storage;
reusing the immutable directory avoids recompilation. The CLI prints the key and
refuses an existing output directory rather than silently trusting stale output.
It does not provide a network cache or automatic cache lookup. Identical inputs
and pinned dependencies replay deterministically; changing a recipe, source,
seed or tool invalidates the key.

Limits: 1 MiB recipe, 64 MiB/source PNG, 8192 pixels/axis, 16 million pixels/image,
4 billion estimated candidate-pixel comparisons across materials. CPU and memory
cost grow with canvas size, candidates and overlap; test a small window first.
Quilting uses contiguous **non-wrapping** source patches, lowest overlap mean
squared error, and dynamic-programming left/top minimum cuts. Their masks are
unioned in a corner, not solved as a global graph cut. It preserves source RGB,
not a promise of invisible seams or a mathematical global optimum.

For chunk preparation, feed `ground.png` to [prepare-ground](composed-ground.md)
with its recorded source-pixel origin; retain the quilting provenance alongside
that transform and carry `composition.sourceScale` to the final packed surface
before binding. Never change logical scene dimensions to emulate source density.

Importable helper: add the installed scripts directory to Python's import path,
then `from quilt_materials import quilt, run`. `quilt` accepts a uint8 RGB NumPy
array plus width, height, seed, patch, overlap and candidates; `run(recipe, out)`
validates and emits the files above. Neither mutates the input scene.
