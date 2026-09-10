---
name: animated-environments
description: Author and integrate looping isometric environments such as rivers, fountains, waterfalls and wind-driven plants, keeping rigid geometry, joins, collision and simulation timing stable across frames.
---

# Animated environments

When the request calls for **generated assets**, perform actual generation
and integrate those outputs. An authored SVG fixture can isolate geometry, but
cannot substitute for the requested provider/source/animation workflow. Keep
original outputs and exact prompts, including rejected candidates.

Use this for scenery loops. Character facings and action poses belong to
[directional-sprite-authoring](../directional-sprite-authoring/SKILL.md).
For large footprints, passages or raised surfaces, pair this with
[multi-tile-asset-assembly](../multi-tile-asset-assembly/SKILL.md) before final art.
For a complete environment from a broad prompt, follow the host brief from
[isometric-visual-loop](../isometric-visual-loop/SKILL.md). Infer fitting motion
from the requested experience; the user need not name sprite clips. Honor an
explicit static-art request. Coordinate connected motion and vary independent
accents using supported clips; do not animate every object just to signal effort.

## Establish what moves

Record the rigid structure, moving region, frame canvas/contact, world scale,
frame count, FPS and loop duration beside the host asset. For water, distinguish
surface shimmer from directional flow. Define flow in grid axes and project it
to screen; do not assume screen-horizontal ripples follow the river channel.
Specify which adjoining edges must match and whether their phases must agree.

Calibrate the stationary structure with the
[art integration contract](../isometric-art-integration/SKILL.md). A larger image
does not imply a larger collider. Stone columns, banks and supports remain solid
even when water is decorative; record their actual physical heights separately.

## Build a stable loop

Prefer a fixed base with a moving overlay when their depth ordering permits it.
Otherwise copy the identical base into every frame and change only the moving
region. Keep one canvas, scale and measured contact; independent tight crops or
per-frame recentering cause swimming. Inspect stationary landmarks in every frame.
Do not assume the returned sheet has the requested dimensions or evenly aligned
content: a 2x2 layout can have different row spacing. Measure decoded windows and
contacts. Equal-size atlas crops with per-frame measured anchors can register
existing content without repainting it; they cannot fix perspective or texture
flicker. Changes to scale per frame are not registration.
Frame count and motion step must make the last-to-first transition intentional.

Use existing art, authored graphics or the provider-neutral
[asset generation workflow](../game-asset-generation/SKILL.md). A generated sheet
is a candidate, not proof of temporal consistency. Reference the same approved
base and constrain changes to the moving region; repair or composite drifting
stonework. Background removal can erase pale water, spray and translucent edges:
review decoded alpha on light and dark backgrounds before packing.
If extraction repeatedly paints a checkerboard instead of alpha, reject those
outputs and change the approach. Small independently generated splash/ripple
layers on a fixed generated base can be useful; explicitly report that any jets
baked into that base remain static. Do not call this a fully animated water jet.

Use [loop recipes](references/loop-recipes.md) for river joins, fountain masks and
other environmental motion. Do not regenerate unrelated scene artwork.

## Bind to this runtime

Use named textures and `assets.animations` clips with explicit `frames`, `fps`
and `loop: true`; a sprite's `visual.animation` selects its base loop. Current
terrain tiles have static textures, so animated water uses nonblocking sprite
entities over terrain whose `walkable` setting owns water traversal. Do not invent
a tile animation field, shader API or wall-clock timer. Sprite loops advance with
runtime simulation and freeze with pause.

Terrain diamond clipping does not apply to entity sprites. A tile-sized animated
overlay must carry its own diamond alpha (or use an explicitly measured host
composition). An opaque rectangular material suitable for a static terrain tile
is not automatically a valid overlay frame. Preserve clipping when replacing
procedural artwork and inspect the channel boundary, bends and map edge. Use the
[packed-art inspector](../isometric-visual-loop/references/acceptance.md)'s
`diamond-overlay` check for overlays intended to occupy one tile diamond.

Place joined modules together with compatible frame sequences/FPS. The runtime
has no public phase-seek API; do not promise seamless phase after independently
adding or restarting pieces. A single strip or phase-authored clips may suit the
host better than many independently managed sprites. Collision stays unchanged
while decorative frames advance. Replacing a clip must not resize its footprint.

## Calibrate, then verify the integrated environment

Check actual rendered pixels advance, pause freezes them, and one full cycle
returns to the initial frame without a structural snap. Inspect a joined edge,
the rigid base against the grid, and the actor beside/behind the asset. Combine
this with the assembly skill's relevant walking and jump route rather than
creating dozens of unrelated checks. Separate verdicts for frame metadata,
visible alignment/loop quality, and gameplay; report anything not observed.
Changing frame IDs, nonidentical pixels and printed wrap differences do not approve
motion quality. Observe playback and record an explicit verdict on the complete
cycle, rigid landmarks, joins and pause; still-image review leaves motion unverified.
This representative check does not cap a larger world's content. Integrate the
planned motion families across the full scene and inspect their joins, phases
and occlusion there before marking the host's animation work complete.

For a neutral worked example of registration and motion acceptance, use
[the loop recipes](references/loop-recipes.md#registration-example). Apply the
method to the current host's own art and measurements.
