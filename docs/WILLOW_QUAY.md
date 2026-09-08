# Weidenkai: a coherent generated-art district

Open **http://127.0.0.1:4175/examples/willow-quay/** after `npm run dev`.
This is a small playable composition inspired by detailed cozy pixel towns:
two shops, a willow, canal, raised crossing, connected paving and planted borders.
It uses original generated buildings and tree art, not copied game assets.

Click a path or use WASD. The three destination buttons walk to the apothecary,
across the bridge, and back to the canal. Mobile has a held D-pad and Jump.
The +/− buttons zoom; Übersicht restores the whole map. Inspizieren shows
footprints and floor data; close its panel to use controls it covers.

## What creates consistency

| Concern | Implemented constraint |
| --- | --- |
| Camera | 64×32 world tiles; measured 2:1 foundation contacts |
| Architecture | Second house generated from the first as reference; shared roof, stone, light and door scale |
| Human scale | Actor ~44px including hat; measured door opening ~55px; house foundation 3×3 cells |
| Ground joins | 47 corner-aware paving states assembled from one generated material sheet |
| Borders | Existing generated-material bed atlas; shared stone materials for canal walls and parapets |
| Collision | Explicit building/trunk bodies, water blocked, sparse upper bridge floor, links and separate rail reservations |
| Motion | Existing registered generated river frames, common phase, elapsed-time shimmer; directional actor clips |

Scene content and assembly remain in `examples/willow-quay/`. Shared cross-floor
depth ordering and a footprint tie-break fix the reproduced failures below; no game-specific
engine branches or new scene fields were introduced. Sunflower and other labs remain
available. `art/DESIGN.md` records intended geometry before generation.
`art/art-contract.json` records measured house contacts and the reused actor's
reference height. `assembly-plan.json` compares those bindings and required routes
with the actual scene. Do not interpret metadata validation as visual approval.

## Generation and actual corrections

Three new images were generated with the built-in image tool: apothecary,
reference-guided bookbinder and willow. Exact prompts and hashes are in
`art/PROMPTS.md` and `art/provenance.json`. Source PNGs are retained unchanged.
The actor, flowers, potted shrubs, lanterns and registered river reuse the
project's previous generated assets with explicit atlas frames.

The apothecary and willow have usable alpha; their interior pixels are mostly
near-opaque, so their source alpha is retained. The bookbinder generation baked
in a checkerboard despite the prompt. Local `rembg 2.0.75`, model `u2netp`, removed
it without changing canvas dimensions. An alpha-matting candidate created ragged
edge fragments and was rejected. The ordinary cutout retains a small edge halo
visible against dark backgrounds; it is less apparent at the intended game scale.
This is a recorded limitation, not a claim of perfect masks.

The ground helper maps generated material crops onto fixed tile/stone geometry;
it does not paint replacement pixel textures or claim to generate finished tiles
independently. Material prefiltering, grading, mirrored repeat and source alpha
policy are explicit in `art/ground-provenance.json`. Repetition remains visible.
Water uses a documented tint to fit the district's muted palette.

The first willow placement at `(3,10)` concealed the starting actor and overlapped
the bridge. The former renderer drew upper-floor containers over ground art, so
the bridge incorrectly covered the foreground canopy. Final placement `(0,4)` keeps
the canopy outside that overlap and the starting actor visible. This is a scene
composition decision, not evidence that arbitrary canopy overlap is solved.
The initial failing screenshot remains in playtest evidence.

The movement trace also exposed a ground route beneath a low bridge end:
24px headroom was insufficient for the 44px actor. The host now fills both shore
ends with nonwalkable 24px abutments touching the upper slab. Two pots were moved
out of the approach corridors, keeping the rear-house route open. This prevents
that route in this scene; it does not add a general walking-ceiling check to the
engine. The final playtest rejects any ground visit to those six abutment cells.

A close-up exposed a second depth issue: house `(3,2)` with a 3×3 footprint and
actor `(4,5)` had equal front-contact depth. Pixi retained their previous order,
so arriving from `(5,5)` hid the actor's upper body while arriving from `(4,6)`
did not. `src/view.ts` now uses a bounded footprint bias smaller than 0.01: compact
footprints draw in front of larger ones on that same depth plane. A public-runtime
pixel regression failed before the change (248 of 768 actor pixels visible from
one direction) and passes after it (768 from both, identical final canvas images).
This resolves that tie; it is not a general intersecting-sprite depth solver.

The later stair close-up exposed the floor-container problem on the actor:
standing at `(7,10)`, feet at 16px, the 32px bridge painted over the head even though
the actor stood in front. All floors now share a painter order. Overlapping screen
bounds are ordered using separated world-space footprints and height intervals;
ambiguous or cyclic relationships fall back to stable contact/footprint order.
Floor cutaway visibility remains independent. `bodyHeight` also supplies the
render volume: flat water explicitly uses 1px, parapets 24px, and bank art 16px.
These nonblocking decorations do not change walkability. Do not derive a flat
surface's vertical height from its projected sprite rectangle.

This is bounded isometric ordering, not arbitrary 3D geometry: unsplit overhangs
can still require front/back pieces. The current overlap scan is quadratic in
display-node count and has only been exercised at these small scene sizes.

An adjacent-bank screenshot then exposed a host data mismatch at `(4,9)`:
`bankNear` was anchored on row9 with image offset `(-32,-16)`, which displays it
one row backward while leaving its depth footprint across the walking row.
It is now anchored on row8 with no image offset and its actual 16px height.
The image stays at precisely the same screen coordinates; the declared spatial
volume now agrees with it. Near-bank contacts at columns4 and10 are included in
`assembly-plan.json`, so the earlier offset/origin combination fails the checker.
The previous height-only metadata change did not fix this horizontal mismatch.

## Spatial scope

Both houses are exterior sprites with conservative full-height 3×3 collision;
their doors do not enter interiors. Their front/back exterior traversal is the
relevant occlusion check. Attached signs/flowers and roof eaves may overhang the
foundation. The willow has a solid trunk cell and decorative crown overhang.

The bridge is a flat raised slab with generated-material stone parapets, not an
ornate arched bridge. Rails reserve whole edge cells even though their art is
thinner. Water below is unwalkable; there is no promised pedestrian underpass.
Ground stairs are 16px step tiles linked to the 32px deck. End caps, textured
stair risers and detailed arch/support art are future visual work. Water shimmers;
it does not simulate a fluid, and the tree remains static.

This demonstrates a consistent district at prototype scope. Matching the
references' final quality also requires more natural material variants, authored
architectural transitions, better masks and richer lighting/animation. Adding
more independently generated objects would not solve those remaining issues.

## Reproduce

```sh
# From Runtime; authoring needs Playwright/Chromium, game needs no provider key.
node --experimental-strip-types examples/willow-quay/art/prepare-ground.mjs
node skills/isometric-art-integration/scripts/check-art.mjs examples/willow-quay/art/art-contract.json
npm run build
# Against an explicitly started standalone server:
node tests/quay-browser.mjs
# Focused renderer regression for equal front-contact depth:
node tests/footprint-depth.mjs
# Cross-floor foreground, supported actor, underpass and cutaway pixels:
node tests/bridge-occlusion.mjs
# Actual generated-art actor beside the repeated near-bank wall:
node tests/quay-bank-depth.mjs
```

The build includes this fourth HTML entry and resolves local PNG URLs. Executed
test status and evidence locations are recorded in [VERIFICATION.md](../VERIFICATION.md).
