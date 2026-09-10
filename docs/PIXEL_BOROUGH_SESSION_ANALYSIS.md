# Session analysis: Pixel Borough

Date: 2026-09-10. Scope: the separate builder session, its two production passes,
current host source, retained captures/reviews and the user's latest defect crops.
The game remains paused. This analysis does not resume production or grant acceptance.

## Finding

The main failure was expanding an unproven spatial/art assembly, then spending
substantial effort repairing symptoms and collecting evidence. The workflow had
instructions for calibration and geometry, but no enforced dependency between
passing those checks and producing the full world. The final comparison preserved
findings, yet did not prevent an incoherent scene from reaching expensive review.

The user is right about trees occupying paved circulation and inconsistent rigid
object geometry. Natural scenes need intentional asymmetry; the missing constraint
is consistent projection, construction and placement logic, not universal symmetry.
The supplied crops show the problem, but exact angle/contact errors still require
measurements on the packed sprites. No numerical geometry verdict is inferred from
those screenshots alone.

This is an audit by the parent who participated in the trial, not a new blind
independent benchmark. Builder failures, framework gaps and parent/reviewer mistakes
are distinguished below. No private model reasoning was used.

## Measured session record

Source session: `01a08b75-7e59-75e0-b868-3b05e51f359e`.
Times below are UTC; local Berlin time is two hours later.

| Evidence | Observation |
| --- | --- |
| Session timestamps | 13:15:28 to 14:47:02: 91 minutes 34 seconds |
| First live calibration | Captured at about 13:26; actor, shop and ground |
| Pack expansion | Plants generated at 13:26:40; buildings at 13:27:31; bridge first generated at 13:29:51 |
| First formal comparison | About 13:59, roughly 44 minutes after session start |
| External review and resume | First reviewed repair read at 14:07:43; comparison-2 handover at 14:47 |
| Image generation | 16 completed generation calls; their recorded call intervals total about 641 seconds, or 10.7 minutes |
| Tool activity | 105 outer tool calls; 113 completed shell-command events; 57 image-view events |
| Nonzero shell exits | 11, including expected incomplete calibration, schema/startup errors and environment/probe failures |
| Rigid-art checker | Zero command invocations of `check-art.mjs` or `preview-art.mjs` in the builder session |
| Capture volume | Round 1: 80 PNGs; intermediate round 2: 151; final round 2: 161. Total 392 PNGs across these folders |
| Transport problems | 14 retry warnings and two HTTP fallbacks across the two CLI stderr logs |

The 92 minutes include an external-review interruption and network retries. They
exclude later parent and independent-review work. Generation duration is approximate
wall time, not billable compute. Tool counts are different event layers and must
not be added together. Video files include renamed copies; file counts are not
unique tests. No controlled speed baseline or cost measurement exists, so the logs
cannot establish a percentage of time wasted or a promised future speedup.

Nevertheless, generation was only about twelve percent of this wall interval.
The recorded work supports a diagnosis of late integration, repeated repairs and
verification overhead; provider generation latency alone does not explain it.
Initial guidance reading took roughly a minute, so blaming document reading as
the principal time sink would also be unsupported.

Local extracted metadata: `test-results/real-visual-session/session-analysis-metrics.json`.
It retains tool timestamps and public progress messages, without private reasoning.
The original CLI logs and source snapshots remain unchanged.

## Causal failures

### 1. The picture became the authority for the world

In `examples/pixel-borough/prepare-art.py`, a generated full ground image is resized
to 1152 by 576 and cut into 24 by 24 runtime cells. Nine color samples per cell
classify it as water or land. The session explicitly reports that dark paving was
initially misclassified as water (13:41:50), prompting another classifier adjustment.

This provides no semantic distinction between paving, meadow, planting beds,
entrances or reserved circulation. In `scene.ts`, tree and shrub coordinates are
separate handwritten lists. Nothing checks whether a tree root occupies a path.
Late ternary coordinate exceptions move selected trees individually; they do not
repair the missing relationship between vegetation and ground.

Consequence: color edits can alter navigation; moving decorative assets does not
update ground intent; route existence can pass while the scene remains nonsensical.
Trees in paving are valid only with an intentional planting pit/planter and retained
clearance. Canopy overhang is a separate visual/occlusion question, not automatically
a forbidden root placement.

Correction: an authored semantic layout must own terrain regions, circulation,
planting, object supports and entrances. Artwork and occupancy are derived from
that layout. Image segmentation may propose masks, but cannot silently become the
authoritative map.

### 2. Calibration did not include the promised risky assembly

The contract required actor, building, connected terrain and bridge/water calibration
before expansion. The live calibration inspected at 13:26 preceded even the first
bridge generation. Full vegetation/building production began immediately afterwards.
Bridge support, water ordering and actor visibility were investigated during full
integration and again during repair.

The problem was not an absent instruction. The agent advanced without evidence
for the complete calibration gate, and orchestration did not stop that transition.

Correction: completion of a calibration stage must be a prerequisite to expansion.
Any representative bridge must demonstrate near approach, middle, far landing,
both sides, underlying support and actor occlusion before multiplying assets.

### 3. Pixel validity was substituted for geometric compatibility

The builder read the art-integration skill but did not run its contact/projection
checker. `packed-art.json` checks actor, creature, fountain and river animation
groups. It does not cover the rigid bases of buildings, stalls, benches or fences.
Alpha padding and distinct frames cannot establish a common ground projection.

`prepare-art.py` chooses separate sprite widths and anchors. Buildings receive
3-by-3 footprints and similar offsets in `scene.ts`; market stalls and benches use
one-cell footprints. The logs contain no executed measurement binding those
footprints to each rigid sprite's visible base. This is an unchecked fit, not proof
that every assigned footprint is wrong.

A 2:1 request in an image prompt and nearest-neighbor sampling do not guarantee
parallel base edges, consistent post spacing or shared logical pixel density.
Non-integer reductions can produce irregular pixel clusters even with nearest
sampling. Moving an anchor cannot repair incompatible perspective.

Correction: measure rigid base contacts against the selected projection, inspect
parallel faces and verticals, and bind approved measurements to actual runtime
scale/anchor/footprint. Curved roofs and deliberately organic objects need suitable
landmarks, not a blanket symmetry requirement.

### 4. Repairs accumulated separate representations

The river moved from cell overlays to one joined strip. The current host uses a
24-by-24 carrier with a tiny physical height and a lowered corner for depth ordering.
Bridge route cells, image splitting, stone deck samples and visual offsets are
declared separately. The final ground-only view still has water over the middle
supports, acknowledged by the builder at 14:46:30.

The manifest also retains 86 unused per-cell water animation entries and 680
per-cell water textures, although the scene uses `river.flow`. This is avoidable
authoring/manifest clutter. Its actual loading or runtime cost has not been profiled.

Correction: one assembly definition owns deck, bank cuts, water exclusion and depth
parts. After changing representation, remove unused derived runtime entries while
preserving generated originals and provenance. Repeated local offsets indicate a
need to revisit the representation, not merely another pixel repair.

### 5. Integration failures appeared late

Full integration exposed invalid zero/undefined `bodyHeight` values and capture
timeouts. The repair pass later fixed top-level-await incompatibility and dynamic
asset URLs missing from the production bundle. A supplemental server then returned
the wrong MIME/path behavior. The first builder full-build invocation appears only
at approximately 14:32, long after asset production began.

Correction: preflight a minimal generated asset through both dev and production
builds, with visible startup failure handling. A failing startup should terminate
the capture step with its actual error, rather than wait repeatedly for a runtime
that will never initialize.

### 6. Many checks answered narrower questions than the user asked

The builder's movement checks primarily compare coordinates before and after input.
They do not inspect every path, entrance or decorative root. Later independent
inspection had to add Follow-camera sequences because existing walking screenshots
lost the actor behind objects or outside the frame. Extra mobile habitat images
were captured but omitted from the formal comparison definitions.

Across three rounds, 392 PNG files accumulated while obvious spatial defects remained.
Some reruns were necessary after source changes; the excess was starting comprehensive
capture before scene assembly was stable, then repeating it after further repairs.

Correction: each check declares its observable, protected scenario, evidence and
dependency. Use a small fixed view set for early visual gates. Run complete motion
and gameplay acceptance after assembly approval, while retaining an early traversal
smoke test during calibration. Invalidate affected evidence by dependency, rather
than either rerunning everything or reusing stale results.

## Framework and parent responsibility

- The existing skills already say to calibrate, preserve shared geometry and inspect
  the ground. More prose repeating these duties is insufficient. The missing piece
  is explicit stage dependency and coverage of spatial semantics/rigid assets.
- The new comparison tool checks record completeness and freshness; it does not
  choose what deserves scrutiny or recognize a tree planted in paving.
- Parent reviews focused on actor size, water seams and bridge continuity. They
  missed the broader placement/projection defects now highlighted by the user.
  Resolving eight old findings did not mean the scene approached the target enough.
- Parent development of the checker during production made this a moving-framework
  trial. Wide-frame limits, calibration subsets, baseline changes and preview issues
  created real friction. This was not an immutable benchmark of a finished framework.
- Repeated independent gameplay and UI probes added overhead. Independent visual
  judgment remains useful, but deterministic results should be shared and spot-checked
  where justified rather than recreated without a new risk or source change.

## Proposed replacement flow

The generalized [production flow and check schema](WORLD_PRODUCTION_FLOW.md) defines
six stages, explicit spatial rules, evidence dependencies and repair limits. It is
an implementation design, not a claim that the current tool enforces those rules.

Priority order for the next framework patch:

1. Host-owned semantic layout and reusable placement/contact checks.
2. Stage transitions that block expansion after failed or unverified calibration.
3. Rigid-art coverage bound to the actual host; use the existing geometry checker.
4. One small capture matrix with a full-scene verdict, plus scoped invalidation.
5. Preflight and a documented strategy-change checkpoint after repeated failures.

Success must be tested with deliberate defects: a tree root in circulation,
blocked doorway, incompatible rigid base, interrupted bridge support, water over
deck and omitted mobile region. The affected gate must reject each. Then a fresh
independent session must execute the flow from a clean contract. Neither that
implementation nor that new trial has been performed by this analysis.
