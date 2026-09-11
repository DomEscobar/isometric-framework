# Single-tree layer test

This bounded experiment preserves a generated scene while allowing a traveler
to pass in front of and behind one tree. The fixed-camera composition works;
clean automatic extraction has **not** been demonstrated.

This describes the earlier manual-mask test. The subsequent
[SAM 3 ZeroGPU trial](SAM3_ZEROGPU_TRIAL.md) produced a first automatic tree mask
and tests a variant that keeps the complete background image.

## Run

From the repository root:

```sh
node node_modules/vite/bin/vite.js --config examples/mossbend/vite.one-tree.config.ts --host 127.0.0.1 --port 4198 --strictPort
```

Open http://127.0.0.1:4198/one-tree.html. Use the front/behind buttons, arrows,
or ground clicks. Switch to the exposed-ground view to inspect the extraction.
Disable the figure when comparing the assembled and original images.

## Method and ownership

- Source: `examples/mossbend/art/scene-second.png`; hidden ground reuses the
  previously generated `ground-raw.png`. This test made zero new provider calls.
  The earlier clean-plate generation was paid; this is not a zero-cost end-to-end
  generation claim.
- `one-tree-prepare.py` copies source pixels into a binary foreground mask and
  inserts the clean plate underneath. The measured root is at native pixel
  `(45, 130)`; the foreground ends at `y=124`, retaining roots in the ground.
- Two manual mask iterations were tried. A local u2netp extraction attempt did
  not complete within the test window and was interrupted. The final mask is
  manually constrained, not an automatic segmentation result.
- Public Runtime APIs supply movement and trunk collision. Host-owned Canvas2D
  draws the scene and neutral diagnostic traveler in front/behind order. This
  does not verify Pixi depth ordering or change the engine/public API.

## Executed checks and limits

Host TypeScript and the standalone Vite build passed. The build retains Vite's
large-chunk warning. Desktop and mobile browser checks passed exact canvas
recomposition with the actor disabled, visible front pose, fully occluded rear
pose, return movement, blocked trunk, keyboard movement and stable pause. Mobile
buttons were exercised through touch. The production build loaded and completed
the rear route without browser errors.

Recomposition changes **zero pixels**, both in prepared images and browser
comparison. This verifies reconstruction of the original image, not mask quality:
opaque source pixels can hide an incorrect ground plate.

Independent inspection of the actual desktop/mobile images found floating leaf
remnants in the exposed ground and a detached green chip in the extracted tree.
The author also inspected the exposed-ground capture and confirmed the remnants.
Clean cutout/ground visual acceptance therefore remains open. The independent
reviewer did not inspect motion video; automated route completion and screenshots
are separate evidence. Arbitrary camera views, relocatable trees, a complete
world and performance acceptance were outside this test.

Evidence stays under ignored `test-results/mossbend/one-tree/`: `checks.json`,
`production.json`, desktop/mobile captures and `visual-review.md`. Asset hashes,
mask method and reconstruction count are in `art/one-tree/processing.json`.

## Decision

The layering technique can preserve the desired joined terrain/object appearance
for a fixed composition. This implementation still requires manual silhouette
work and contains visible extraction defects. It does not yet meet the requested
fast automatic production workflow, so this test stops here rather than expanding
the same process to a whole world.
