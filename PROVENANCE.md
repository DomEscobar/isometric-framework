# Source lineage

This extraction starts from the Traviso-based engine in `Client/engine/traviso.js` in the AI-Pixel-World repository. The standalone implementation is rewritten into typed modules and a smaller scene/runtime contract. It is not a verbatim vendoring of that file or a compatible replacement for its full application API.

The source areas informing the extraction include these locations in the original checkout (line numbers are orientation aids and may move):

| Original source | Retained concept / treatment |
| --- | --- |
| `Client/engine/traviso.js`, around line 2915 | Isometric column/row projection and inverse tile picking; extracted into explicit geometry functions. |
| `Client/engine/traviso.js`, around lines 1838–2413 | Grid pathfinding and A*; reworked into a renderer-independent typed core. |
| `Client/engine/traviso.js`, around line 3491 and its occupancy helpers | Solid footprints, tile walkability, and occupied cells; represented with explicit scene/entity data. |
| `Client/engine/traviso.js`, movement/tween and rendering sections | Actor movement, depth ordering, and camera responsibilities; movement rewritten around elapsed seconds and runtime-owned state. |
| `Client/engine/move-handler.js`, `handlePress`, around line 152 | Original control orientation retained: W increases columns (northeast), D increases rows (southeast), S decreases columns (southwest), A decreases rows (northwest). Keyboard and mobile directional pad share this mapping. |
| `Client/components/panels/builder/` and application engine integration | Evidence of editor/application coupling; these UI modules are not dependencies of this package. |

The extraction introduces per-instance ownership, explicit destruction, a versioned JSON format, validation, and event-based gameplay integration. The demo's garden data, generated visual shapes, page, and collection rule are separate application examples. No existing bitmap asset pack is copied into this folder.

## Licensing

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

This file records technical provenance, not a new grant of rights. Preserve the repository's applicable notices and review the original Traviso/upstream and repository licensing before redistributing or publishing a derived package. This extraction does not assert that original project code or assets are public domain or grant a license the repository has not established. Pixi.js and other installed dependencies retain their own licenses and notices.
