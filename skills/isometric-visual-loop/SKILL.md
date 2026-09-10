---
name: isometric-visual-loop
description: Build or refine complete isometric environments from ordinary user prompts or references, matching intended scope and quality through generated art, complex assemblies, environmental animation and independent visual review.
---

# Isometric World Production

Use for creating a composed environment from a normal user prompt, substantial
visual refinement, or an explicitly requested visual workflow trial. A local bug
fix still belongs to its existing module; it does not require rebuilding a world.
This is the Runtime's world-production workflow: interpret intent, calibrate,
build the complete environment, animate it and verify the actual playable result.
Keep the user's chosen art style, tools and task scope. All operational guidance
is maintained here with the bundled specialist skills; no external workflow is
required. The skill ID remains `isometric-visual-loop` for existing integrations.

## Translate intent into the deliverable

A short prompt can request a rich finished world. Infer effort from the desired
experience and references, not prompt length or whether the user knows technical
terms. "A lively village with shops, a river and a bridge" warrants a
composed, animated, traversable environment. "A quick bridge collision test"
warrants a small functional fixture. A carefully finished courtyard can require
high effort without a large map.

Choose reasonable art, layout and implementation defaults from the prompt and
existing project; briefly state consequential assumptions and proceed. The user
need not order autotiles, depth planes, colliders or animation clips separately.
Ask only for missing information that materially changes the intended outcome.
Explicit constraints on assets, style, motion, time or provider spending prevail.
Atmosphere does not by itself authorize new quest, combat or NPC simulation systems.

Keep one short host-owned production brief using
[this outline](references/production-brief.md). Record the full intended outcome
before calibrating: regions/landmarks, visual hierarchy, traversal, complex
assemblies, appropriate motion and observable completion evidence. Distinguish
user requirements from inferred supporting details. Update existing project
plans rather than duplicating them. The brief is authoring data, not scene JSON.

For world production, follow the [acceptance gate](references/acceptance.md).
Freeze the approved requirements and art-check coverage before implementation.
Keep every promised direction/action and visual quality criterion explicit; do
not narrow them to what an initial generated sheet happens to contain. The gate
checks packed pixels, requirement coverage and evidence freshness. Its exit code
does not replace visual judgment. Focused repairs use a correspondingly small plan.

## Establish the target and calibrate

- Preserve the supplied reference. A generated concept may clarify implementation,
  but cannot silently replace the user's target or prove reference parity.
- Establish whether the reference supplies a style, a layout to reproduce, or
  both. For a style reference, do not penalize a different bench/fence position
  as a failed replica. Without an image, use the brief and shared art direction;
  a concept is useful when it resolves uncertainty, not a mandatory approval step.
- Record camera, output size, shared pixel density, palette, player scale and
  major landmark positions. Compare actual game captures at the target aspect.
- Block out the overall layout, then prove the riskiest assembly with the actor
  and one representative material/loop. Check width, clearances, contacts and
  intended views before producing the full asset set. Reuse already validated
  calibration when appropriate. Simple diagnostic shapes are internal fixtures
  unless the user explicitly requests a diagnostic fixture as the final result.
- Calibration is a checkpoint, never a reduced final deliverable. After it passes,
  continue directly into the complete planned environment. Do not pause to ask
  whether to continue work already requested by the user.
- An explicitly requested experiment may have a stated bounded round budget.
  Do not assign a three-round cap to a finished-world request, or retroactively
  rename an unfinished build a trial. Respect actual user budgets, carry pending
  work across continuations, and report concrete blockers without declaring success.

## Build the complete environment

Use [consistent-tileset-authoring](../consistent-tileset-authoring/SKILL.md) for
shared materials/edges and [multi-tile-asset-assembly](../multi-tile-asset-assembly/SKILL.md)
for bridges and buildings. Use [game-asset-generation](../game-asset-generation/SKILL.md)
with an available provider. A generated-asset task needs actual generated media.
Use [animated-environments](../animated-environments/SKILL.md) for the scene's
moving scenery, even when the prompt describes the experience rather than clips.

- Expand the calibrated assembly into the brief's full layout: all requested
  landmarks, connected terrain, readable approaches, supporting vegetation and
  required views. Spend extra effort on dominant structures and weak assets;
  additional tiles or generation attempts alone do not establish higher quality.
- Build connected paths, banks, walls and water from shared boundaries. Derive
  art placements and collision reservations from the same assembly data. Keep
  density and asymmetry intentional without breaking joints or route clearance.
- For natural ground, establish [landscape composition](../consistent-tileset-authoring/references/landscape-composition.md)
  before tile production: material regions, path/grass and bank transitions, and
  variation spanning cells. Inspect the ground without optional props before
  decoration. A connected mask or shared palette does not approve a repetitive
  diamond pattern, uniformly hard natural edge or mismatched pixel treatment.
- Resolve capability gaps before detailed asset production. Check actual public
  APIs; do not invent thin-edge colliders, tile-animation fields or phase controls.
  Prefer a valid host assembly. If the intended form needs a reusable engine
  extension, implement a scoped module change and its meaningful checks when
  authorized. Never silently widen a bridge or fill its passage to fit the API.
- Generate coherent material families and a few hero assets. Derive tile geometry,
  neighbor masks and world-space phase deterministically; independent full-tile
  generation does not establish seamless connections.
- Inspect a joined material patch for repeats as well as seams. Mirroring can
  create unnatural symmetric motifs. Keep large rocks and other recognizable
  objects separate from quiet base textures where appropriate. Pack used variants
  and deduplicate identical frames instead of multiplying every mask/phase blindly.
- Record whether a source is orthographic material or already projected art.
  Projecting already-isometric water stones again creates stretched diagonal bands.
- Let one stage own the diamond silhouette. Static terrain material frames may
  be opaque rectangles because the terrain renderer draws a diamond. Entity
  sprites, including animated water overlays, receive no terrain clipping: their
  pixels must already have the intended transparent silhouette, or a measured
  host composition must provide it. Verify this when replacing procedural art.
  Inspect underlying debug/procedural strokes before blaming the generator.
- Split large artwork at meaningful depth planes. Rectify each vertical face
  while preserving vertical posts; a whole-image shear changes physical appearance.
- Close visible gaps with declared terrain/support geometry. A painted band over
  a gap is not a bridge support. Keep walkable surfaces, underside clearance and
  sprite contacts consistent after every elevation change.

For a lively environment, choose motion that explains the scene: water flowing
through bends, localized fountain spray, foliage around fixed roots, occasional
leaves or other fitting accents. Record each loop's rigid base, moving region,
direction, timing and join dependencies. Connected water requires coherent joins;
separate plants can use varied authored phases/cadences rather than move in unison.
Use supported clips and simulation timing. Current terrain textures are static;
water motion uses nonblocking sprite layers over authoritative terrain. The runtime
has no phase-seek API. Do not substitute unrelated ambient sparkles for a requested
flowing river, or count static water as complete animated scenery.

## Critique and repair

Run the acceptance tool's `inspect` command on the actual runtime atlas and open
its preview. Check all used frames at shared scale, clip playback, roots and
silhouettes before requesting a full-world critique. Reject neighboring sprite
fragments, cut-off bodies, wrong facings and rectangular overlay leakage first.
Inspect the same actor and joined animated patch in the running game; a source
sheet is not the delivered atlas and a preview is not in-game acceptance.

Self-inspect a live capture first. Fix obvious loading, missing textures and
misplaced landmarks before paying for a critic. Never judge an asset sheet as
evidence that the playable scene is correct.

Use a fresh independent agent when available and authorized by the workflow;
otherwise label the review as self-review. Give it the original brief, reference
role, target, live captures and previous verdict after the first round, without
the builder's preferred verdict. Assess composition/readability, style coherence,
materials and visible defects; use clips or timed captures for animation.
Require a verdict against every protected requirement: pass, fail or unverified.
Motion needs observed playback, including all required actor directions/actions
and complete environmental cycles. A still-image critic cannot approve it through
separate frame-counter tests. For style references, judge pixel treatment, terrain
edges, density, layering and player readability as well as palette and object types.
For natural landscapes, issue separate terrain-composition and material-transition
verdicts from ground-only and dressed views. Identify the strongest repeated motif
and worst boundary; reject visible grid stamping even if the landmarks look good.
Report layout similarity separately when exact replication was not requested.
For an explicit replica, use the gated similarity rubric below;
its numeric cap is not a universal beauty score.

| Gate | Cap until satisfied |
| --- | --- |
| Shape: camera and all major forms present, within about 10% frame position and 25% scale | 3 |
| Overall light, palette, contrast and atmosphere | 5 |
| Every important surface reads as its intended material | 7 |
| Fine detail and consistent treatment | 9 |
| Side-by-side indistinguishability | 10 |

The next critic marks each prior directive LANDED, PARTIAL or NOT DONE. Select
at most three concrete corrections for a round and state how each will be visible.
Keep the complete defect list open; the three-correction limit schedules repairs,
not acceptance scope. LANDED confirms one repair only. After repairs, capture a
new candidate and rerun the complete relevant acceptance scope before declaring done.
Fix major shape blockers before decorative polish. Do not submit another material
iteration against an unchanged bridge-width blocker. If two rounds repeat a
major defect, change the composition, geometry or asset strategy and verify that
change first. In replica mode, a stalled one-point gain is an additional signal.
An infeasible directive needs a concrete capability finding, not silent omission.

## Independent acceptance evidence

Check the complete brief before declaring done; a finished calibration assembly
does not stand in for missing regions, structures or animation. Capture the whole
scene and the meaningful traversal/occlusion views, not only a favorable opening
frame. Where motion is part of the brief, check one full environmental cycle, its
wrap, joined pieces and pause; sample distinct motion families without testing
every decorative leaf separately. For explicitly static work, verify that scope
instead of adding animation to satisfy a generic checklist.

Keep four verdicts separate: visual quality, motion quality, gameplay, performance. A score of 8+
does not validate routes, and passing collision tests does not establish beauty.
For bridges, a focused walk both ways, blocked rail/water attempt, idle overlap
capture and mobile control check normally suffice. Run broader checks only when
engine changes justify them.

For a full environment's performance acceptance or a performance investigation,
record median/p95 frame intervals, viewport, browser channel and actual renderer.
Compare an idle blank page and close only positively identified stale test
processes owned by this task/project. Native GPU and SwiftShader results are not
interchangeable; concurrent software-rendered tests can invalidate both timings.
Retain a finally/cleanup path in browser scripts.
An isolated asset repair or simple collision fixture needs its affected checks;
do not turn it into an unrelated full-world benchmark or broad regression rerun.

Deliver the playable result, live capture/animation evidence, completed brief
coverage, checks and material limits. Explicitly identify any missing requirement.
Run the [acceptance command](references/acceptance.md) on the final candidate.
Missing, failed, unverified or stale requirements block completion; report them
as open work. Neither a passing build nor an unaudited review JSON proves quality.
Accept a replica against this rubric only at 8+ with acceptable observed
performance. For original worlds, accept against the brief and observed quality,
not invented positional similarity to a generated concept. A bounded experiment
may demonstrate a failed strategy; it does not satisfy a finished-world request.

License notices: [NOTICE.txt](NOTICE.txt).
