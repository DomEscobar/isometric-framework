# Generated terrain slice experiment

Open http://127.0.0.1:4203/?terrain=generated with the village production preview
running, or use the development host on4202. **Boden: generiert / vorher** switches
the full ground and water material while keeping the same actors, camera and
collision data. `?terrain=original` opens the prior procedural ground.

One built-in ImageGen edit produced `source-v1.png` using `layout-input.png` as
the fixed layout, the user's original forest image as style, and the existing
village as object context. The exact request is `prompt.txt`.

The model did not preserve geometry exactly. An affine fit aligns its outer
diamond; a continuous world-coordinate image registration then aligns both
riverbanks. `registration.json` retains measured source/target points and the
affine transform. This is image resampling, not a navigation change or new paint.
The registration leaves a small sampled blue fringe at the bank; it is measured
separately from seam correctness.

`prepare.mjs` exports24 adjacent256x256 crops with1px transparent padding.
The host loads those actual PNG slices from `slices.json`; their composition
reconstructs `registered-v1.png` exactly. These are positioned pieces of this map,
not an interchangeable autotile library. The runtime clips land with the existing
support alpha. It unwraps generated water pixels, joins a64px head/tail overlap
and scrolls the resulting704px texture through the fixed channel (22-second loop).
There is no procedural water painting in generated mode.

Authoring from the repository root:

```sh
uv run --with Pillow --with numpy --with scipy python examples/quellbrunn/terrain-trial/analyze-registration.py
node examples/quellbrunn/terrain-trial/prepare.mjs
node tests/quellbrunn-ground-browser.mjs
```

The first two commands use the preserved PNGs and an explicitly running dev server
on4202. Browser checks target production preview4203. Runtime PNGs and source
provenance are host-owned; captures and review receipts live outside source under
`test-results/quellbrunn/ground-trial/`.

This focused trial replaces the rejected ground presentation. The previous
whole-world acceptance receipt no longer describes current source. The focused
plan checks generated ground style, registration/seams/traversal and water motion.
Bridge structures, crop plants, actors and smoke remain authored; this experiment
does not claim that every visible asset is now generated. Remaining polish limits
include strong cyan wave bands and a comparatively dark bank rim.
