# Historical example artwork provenance

These records concern source-checkout examples. Their artwork is not distributed
with the consumer package and is not a default input for new games.
Paths below are relative to the framework source checkout.

The Sunflower courtyard adds two PNG atlases generated with the built-in image
generation tool, inspired by the user's garden reference. They contain new garden
props, terrain, and a matching gardener; no reference-image pixels or downloaded
asset pack were copied. The exact prompts are retained in
`demo/art/pixel-cafe/README.md`. Both actual outputs are 1254 × 1254 RGBA images;
`demo/pixel-cafe.ts` records manually inspected source rectangles, contact anchors,
animation mappings, and scene placement. This content stays outside `src/`.

The calibration revision retains those originals and adds `flowers-v2.png`, a
1774 × 887 RGBA foliage atlas generated with the same built-in tool, and
`planter-bases.png`, original deterministic pixel geometry authored in
`demo/art/pixel-cafe/build-planters.mjs`. The generator does not process or edit
the original images. The 16 stone/soil variants have exact ground footprints and
neighbor-aware walls. Accepted and rejected generation prompts and the measured
integration are documented in `demo/art/pixel-cafe/CALIBRATION.md`.

The Woodland atelier example adds a locally authored SVG atlas in
`demo/art/woodland.svg`, reproducible through `demo/art/build-atlas.mjs`.
Its palette, terrain patterns, ranger frames, trees and props were created for
this example. It contains no downloaded asset pack or external image references.
`demo/art-pack.ts` records source frame rectangles and contact anchors. This is
host-owned example artwork, not a dependency of the engine or a new license grant.
