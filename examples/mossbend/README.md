# Mossbend image-to-image experiment

A playable experiment in generating an environment together, separating its
original pixels into ground/objects, then binding them to the public runtime.
No previous example artwork is reused. This is a failed exact-layout experiment
with a working technical prototype, not an accepted finished game.

```sh
node node_modules/vite/bin/vite.js --config examples/mossbend/vite.config.ts --host 127.0.0.1 --port 4196 --strictPort
node --experimental-strip-types examples/mossbend/check-layout.mjs
node node_modules/typescript/bin/tsc -p examples/mossbend/tsconfig.json
node node_modules/vite/bin/vite.js build --config examples/mossbend/vite.config.ts
```

Open http://127.0.0.1:4196/. WASD/arrows, path clicks and mobile D-pad move the
diagnostic traveler. The buttons cross the bridge and return. Pause freezes water
and travel. `?ground` hides upright tree art while retaining blocking footprints;
`?native` captures the 256 x 224 scene. `?guide` shows the current neutral layout.
Builds and browser evidence stay in ignored `test-results/mossbend/`.

## What this established

- RD Pro Edit made coherent root beds, banks and grass/path materials together.
- Both full-image attempts changed geometry and omitted trees. The source images
  are preserved. A masked attempt to add missing trees returned red/black artifacts
  and is excluded from runtime. Four paid calls cost $0.72 total.
- Four manually traced original-image tree cutouts supply six placed instances;
  two smaller instances explicitly reuse those new host-owned trees.
- A generated clean plate supplies hidden ground only inside an expanded tree
  mask. Pixels outside that repair mask are copied unchanged from the second image.
- The original authoring layout also mistakenly planted one tree in water. The
  current layout fixes that author error and has a small executable semantic check.
  Original reference/guide evidence is retained; the error is not blamed on RD.
- The traveler is the framework's neutral built-in diagnostic actor. Water is a
  code-authored 12-frame surface shimmer, not AI-generated flowing-water animation.
- Pixel sampling stays nearest. Two scaled tree instances and partially traced
  overlapping crowns remain visual limitations. The generated bridge is wider
  than the protected walking corridor. The full visual gate is not passed.

The native projection, initial guide and exact prompts are in `layout.ts`,
`art/layout-guide*.png` and `art/scene-request*.json`. `art/experiment-log.json`
records requests, charges, failures and manual correction. Rebuild processed art
with Pillow using `extract-layers.py` then `pack-layers.py`; retain the original
provider outputs. The user's external style reference stays in ignored evidence.

No engine or public API changes were required. This host is not an art library
or default template for unrelated new games.

The separate [single-tree layer test](../../docs/ONE_TREE_LAYER_TEST.md) is at
`/one-tree.html`. It preserves the original composition and tests front/behind
movement with one manually masked tree. Exposed-ground artifacts remain; it is
not evidence of clean automatic extraction.

The later [SAM 3 ZeroGPU trial](../../docs/SAM3_ZEROGPU_TRIAL.md) is available at
`/one-tree.html?sam3`. It uses the first model-produced western-tree mask with no
manual mask correction and preserves the complete original background.
