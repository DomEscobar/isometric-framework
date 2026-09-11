# Offline composed-ground preparation

Use this optional Pillow helper after a host exports a source image and any target-sized
masks. It prepares pixels only: it does not infer terrain topology, collision, or material
boundaries. The source may be authored, supplied, procedural, or generated.
Use Python 3.10+ with Pillow; `uv run --with Pillow python` can replace `python`
below when needed. No browser, provider connection or example assets are required.

```sh
python skills/consistent-tileset-authoring/scripts/prepare-ground.py recipe.json --out prepared-ground
python skills/isometric-visual-loop/scripts/verify-world.py inspect prepared-ground/packed-art.json --out review/ground-1
```

Recipes are version 1 and paths are local to the recipe. `outputToSource` is Pillow's
output-to-source pixel affine: `[a,b,c,d,e,f]` means `sx=a*x+b*y+c`, `sy=d*x+e*y+f`.
It must be invertible. Nearest sampling is supported. `outOfBounds` is `reject` by default
or explicitly `transparent`; source coordinates are never clamped.
The transform operates on output pixel centres `(x+0.5,y+0.5)`. It changes sampled
art, not host coordinates or collision. A bad interior boundary cannot be certified
by fitting the outer corners; local deformation or mask inference is not implemented.

```json
{
  "version": 1,
  "source": "master.png",
  "coverageMask": "coverage.png",
  "movingMask": "water.png",
  "output": {
    "width": 640,
    "height": 384,
    "origin": [-120, 48],
    "mode": "chunks",
    "chunkSize": [256, 192],
    "gutter": 2,
    "outOfBounds": "reject"
  },
  "outputToSource": [1, 0, 0, 0, 1, 0]
}
```

Omit output, transform, and masks for an identity plate. Coverage multiplies composed alpha;
exported `coverage.png` records final actual alpha, not a claim about source geometry. The
moving mask must be within final non-transparent support. The tool always writes `ground.png`
as a composition reference, positioned frames in `manifest.json`, `packed-art.json`, and
input/output hashes in `provenance.json`. A chunk's frame excludes its transparent gutter.
Placements are content top-left coordinates including the declared origin. The new output
directory is never overwritten; `manifest.json` is written last.

All numbers and files above are illustrative. Inputs must be static PNGs inside
the recipe directory; masks must be target-sized grayscale PNGs (L or 1).
Limits are 8192 pixels per axis, 16 million pixels per image, 64 MiB per PNG and
4096 chunks. A new output directory is required. Partial last-row/column chunks
keep their actual size. Provenance includes input/tool/output hashes and exact
decoded reconstruction; variable processing time is isolated in `timings.json`.

`manifest.json` uses the existing `images` and `textures` dictionaries. Its extra
`placements` dictionary is authoring/host metadata: draw each texture's declared
frame at that content origin, excluding gutters. A `surface` packed-art group
compares those pieces with `ground.png` and checks final coverage. These tests
verify extraction, not style, registration, movement, or interchangeable tile edges.

Choose a plate when the host displays one fixed image; choose positioned chunks
when its loading or composition needs them. Slicing alone does not save runtime
work. An editable/recombinable map may instead need compatible transition tiles.
Keep upright objects and moving overlays separate when depth or motion requires it.

## Bind registered ground to the public runtime

Prepared `placements` are authoring metadata, not a runtime plate-placement API.
For one flat ground plane, the optional adapter binds the registered `ground.png`
through existing `TileDefinition.texture` and manifest frames:

```sh
node --experimental-strip-types skills/consistent-tileset-authoring/scripts/bind-ground.mjs game/scene.json prepared-ground/packed-art.json --out review/ground-binding-1 --image-url ./art/prepared-ground/ground.png
```

Export `scene.json` from the host's actual scene definitions. Use the URL the
browser will resolve from the host document, not a path relative to this output
JSON. The adapter emits a validated `scene.json` and `binding.json` with each
cell's frame and source hashes. Import the bound scene into the host; preserve
the referenced image at the supplied runtime URL.

Every cell samples a different bounding rectangle of the same composed image;
the renderer clips it to the cell diamond. This preserves continuous source
artwork without generating individual tile designs. Collision and walking support
remain those of the input scene. The adapter changes neither source pixels nor
entity art. It rejects unaligned/out-of-image rectangles and unsupported elevated
or multiple-floor layouts rather than silently fitting them.

Register the source in projected world pixels before binding. Confirm interior
path, entrance and bridge landmarks, then inspect the actual host for seams,
occlusion and traversal. A valid frame map proves sampling geometry, not that the
generator placed the path correctly. A positioned rectangle or oversized entity
sprite is not an equivalent substitute for ground depth and support. Animate only
the requested water interior with fixed banks and deck coverage.

Focused synthetic tests, including preparer/inspector interoperability:

```sh
python -m unittest discover -s skills/consistent-tileset-authoring/tests -p test_prepare_ground.py
```
