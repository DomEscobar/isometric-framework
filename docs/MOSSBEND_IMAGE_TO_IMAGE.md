# Image-to-image environment experiment: Mossbend

The experiment produced a playable layered scene with more coherent material
connections than independent asset generation, but **did not establish a fast,
accurate one-pass world-production technique**. Whole-image edit guidance did not
preserve the semantic layout. Layer extraction required manual masks and repairs.

Run the host using [its README](../examples/mossbend/README.md). The current local
dev URL is http://127.0.0.1:4196/; production preview is http://127.0.0.1:4197/.

## Actual sequence and costs

| Operation | Charge | Observed result |
| --- | ---: | --- |
| Engine-column guide + forest style reference → RD Pro Edit | $0.18 | Coherent illustration, five visible trees instead of six, shifted roots/outline. |
| Clearer tree-silhouette guide, lower strength → RD Pro Edit | $0.18 | Better rooted ground and bank composition, four trees instead of six, wider bridge. |
| Masked addition of missing trees | $0.18 | Red/black artifacts. Rejected and excluded from runtime. |
| Remove tall trees to obtain hidden ground | $0.18 | Usable clean plate under manually expanded object masks. |
| Local extraction, packing, animation and runtime binding | No provider charge | Four manual cutouts reused for six placements; code-authored water shimmer. |

Total provider charges: **$0.72 for four calls**. Exact prompts, request IDs and
processing choices are retained in
[experiment-log.json](../examples/mossbend/art/experiment-log.json).
From the first paid request to the completed review, **31.6 minutes** elapsed;
earlier layout preparation and the upload-approval pause are additional. This
includes integration and verification, not just provider generation latency.
The initial guide also contained an author error: oak-mid was planted on a water
cell. The current host corrects it to clear planting at (1,3). That error must not
be attributed to the image model. A direct semantic check now guards planting,
reserved paths and destination reachability. Original guide evidence remains.

## What works, and what still does not

Generating grass, dirt, bank lips, roots and shadows together gives them common
lighting and material treatment. The second generated illustration demonstrates
this. Its pixel clusters nevertheless remain finer/noisier than the supplied
reference; shared palette alone is not reference-style acceptance.

The runtime uses real textured terrain, separate anchored tree sprites and
nonblocking diamond-alpha water overlays. Bridge artwork is on terrain, so the
actor can draw above it. The diagnostic traveler is the neutral built-in actor,
not a claimed generated directional character. The water animation is a subtle
fixed-mask surface shimmer; it is not generated flowing water or a fluid simulation.

Original scene pixels outside the expanded background-repair mask are preserved
exactly in the composed ground image. The runtime image is not pixel-identical to
the generated master: objects have been registered to actual roots, two additional
instances reuse/rescale this host's new trees, and terrain clips the master to the
framework's diamond geometry. Traced overlapping crowns and resized duplicates
remain limitations. A last foreground-height correction was needed to expose the
actor's feet on the bridge. This is real manual integration work, not free extraction.

The painted bridge remains wider than its guide corridor. Restricting movement
to the intended cells does not make the picture geometrically accurate. The
independent review and final acceptance result must retain this distinction.

## Executed checks

- Strict host TypeScript and Vite production build pass. Build keeps the ordinary
  large-chunk warning; no threshold was relaxed.
- Actual desktop and mobile browser journeys pass: keyboard, held touch D-pad,
  crossing both ways, destination, blocked water and blocked tree cells; no browser
  exceptions. The production build also loads its artwork and completes the route.
- All six corrected roots are outside water/reserved paths, and the destination
  is reachable in the executable semantic layout check.
- Packed foreground cutout and all water clips pass their decoded structural
  inspections. These are not aesthetic verdicts.
- Twelve actual timed runtime frames are distinct; frame 12 exactly matches frame
  0. Paused desktop/mobile images are unchanged. The inspected sequence shows
  subtle brightness movement with stationary banks; no spatial flow is claimed.
- Whole-image geometry/reference-style acceptance remains failed. No full-world
  version-3 certification or renderer-performance benchmark is claimed.

Final independent visual review: composition **fail**, layers **fail**, narrowly
scoped water shimmer **pass**. The parent builder's actual input journey is
separately recorded as **pass**, not independently replayed. `verify-world.py
accept` was executed against the fresh final candidate and rejected it with
`Requirement not accepted: composition`. The remaining layer defect includes an
almost fully obscured actor near the added small tree despite readable deck poses.

Reproducible browser evidence and the independent comparison are in ignored
`test-results/mossbend/`, including `comparison-final/board.html`, the original
reference, intermediate failures, screenshots, timed frames and the water GIF.
This report stays outside skills so historical example artwork cannot become
an unrelated production agent's default.

## Implication for the next technique

The strongest reusable result is preserving a successful material composition
while editing only explicitly owned regions. The weak points are semantic layout
control and automatic separation of overlapping scenery. A dependable one-turn
workflow needs those two operations to be demonstrated on a representative
assembly before promising a whole generated world. Additional prose, seeds or
lower edit strength alone did not solve them here. Do not promote this trial as
the framework's default generation recipe yet.
