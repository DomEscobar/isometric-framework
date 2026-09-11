---
name: isometric-visual-loop
description: Build or refine complete isometric environments from a brief or visual reference through composed terrain, grounded scenery, appropriate animation and independent review of the playable result.
---

# Isometric world production

Use for a complete environment or substantial visual refinement. A focused repair
keeps its affected scope; an unrelated engine/gameplay fix does not need this loop.
Honor the user's style, provider, budget and intended deliverable. A short prompt
can request a rich world; calibration is an internal checkpoint, not a smaller
replacement for the finished scene. Atmosphere alone does not authorize new
combat, quests or NPC simulation.

## Define the result once

Use the host's existing brief with [this short outline](references/production-brief.md).
Record the reference's role (style, layout or both), landmarks, routes, material
relationships, actor proportions and required motion. Infer supporting details
from the supplied image; ask only about consequential missing choices.

Protect the actual reference. A generated concept may clarify a design but cannot
replace the user's target. For a style reference, compare its pixel clusters,
outlines, light, material treatment, proportions and spatial hierarchy; do not
score a different layout as an inaccurate replica. Exact layout reproduction
additionally needs protected framing, landmark positions and scale.

For full world production, use the version 3 [acceptance plan](references/acceptance.md)
and [executed stages](references/production-flow.md): preflight, semantic layout,
representative assembly, complete static scene, motion and final review.
Begin each check before collecting evidence. Failed or unverified prerequisites
block expansion; unchanged dependencies retain their receipts. After two failed
attempts, record a changed strategy and a discriminating test. Scope dependencies
to what the check actually measures; do not make a grass edit invalidate an
unrelated building's geometry. Final review still covers the complete deliverable.
Focused repairs use the acceptance tool's focused scope and relevant views rather
than reconstructing unrelated production stages. Do not narrow promised quality
or action coverage to fit the first generated output.

Before proposing a framework patch, classify the failed production step: missing
tool, conflicting instruction, ignored rule, unsuitable generation, or bad review.
Repair the identified cause in the host or workflow first. Change the framework
only when the evidence shows its public behavior prevents the required result.

## Calibrate a composed patch

The unit of visual production is an object with its terrain connection, not an
isolated sprite followed by late decoration. Use
[grounded assemblies](../isometric-art-integration/references/grounded-assemblies.md)
for roots, foundations, worn approaches and banks. Record contact treatment in
the existing brief; no additional schema is needed.

1. Block out the whole intended scene from one semantic layout: routes, planting,
   entrances, water and walking support. Resolve public API limitations before art.
   Render generation guides with the runtime's public `project` function. Use the
   [layout renderer](references/production-flow.md#render-the-layout-in-the-runtime-projection)
   or an equivalent host export; a generic isometric formula can rotate the map.
   Check each water body's continuity as well as walking routes; point-touching
   cells can block a route while failing to form a flowing channel. The layout
   schema supports explicit water hidden beneath bridge decks.
2. Choose the riskiest representative patch with the actor, an object, its ground
   transition and any relevant motion. Match playing zoom, pixel density and
   stylized proportions to the reference.
3. Inspect both physical support and visible integration. The same coordinates
   can hold incompatible art; an attractive shadow cannot repair unsupported land.
4. Review the ground with upright/optional props hidden, retaining its contact
   beds, wear and bank lips. Then inspect the dressed patch and actual arrival
   poses. A bare ground test and an isolated sprite sheet are insufficient alone.
5. Expand directly into the complete requested scope when this patch works.
   Reuse valid existing calibration; do not create new approval ceremonies.

An explicitly bounded experiment may have a round budget. Do not impose an
arbitrary round cap on a finished-world request or relabel unfinished work a trial.

## Use specialists where they change the work

| Need | Owner |
| --- | --- |
| Shared style, physical measurements and object-ground connections | [Art integration](../isometric-art-integration/SKILL.md) |
| Connected regions, natural edges and material variation | [Tileset authoring](../consistent-tileset-authoring/SKILL.md), starting with its landscape composition reference |
| New raster candidates or layered contact artwork | [Asset generation](../game-asset-generation/SKILL.md), using the chosen provider |
| Walkable decks, rigid structures, openings and depth parts | [Multi-tile assemblies](../multi-tile-asset-assembly/SKILL.md) |
| Character facings and action poses | [Directional sprites](../directional-sprite-authoring/SKILL.md) |
| Joined water or anchored foliage motion | [Animated environments](../animated-environments/SKILL.md) |

Read the selected specialist's relevant recipe, not every provider or fixture.
Generated-art requests require actual generated outputs and honest provenance.
Example hosts are not default art libraries.

Compose terrain boundaries once in world space and use them for both appearance
and navigation. Quiet areas, dense planting and worn circulation have different
roles; more noise or more sprites do not establish richness. Preserve deliberate
formal geometry where the brief calls for it. Inspect the worst material boundary
and strongest repeated motif at playing zoom.

Separate visual layers where support, depth or movement requires it. Walkable
surfaces need actual floor support and an actor that draws correctly on top.
Grounded roots and stationary banks stay fixed while nearby leaves or water move.
Choose scene-relevant motion; do not animate everything or substitute ambient
sparkles for requested flowing water. The specialists own runtime-specific
clipping, phase and assembly constraints.

## Compare, repair, and verify

Run the packed-art `inspect` command on the actual runtime manifest when sprites
or overlays change. Open its preview and inspect the affected clips at shared
scale before a scene review. During calibration, `--groups` may inspect built
families; it cannot replace full protected coverage at delivery. A structural
pass establishes neither anatomy nor in-game depth.

Capture the actual playable host, then run the
[image comparison loop](references/visual-comparison.md). Supply original
reference, current and previous images. Self-inspect obvious loading/crop errors
before requesting an independent critic.

Use a fresh independent agent when available under this workflow; otherwise
label self-review. Give it the brief, reference role and actual images without
the builder's preferred verdict. The critic must inspect pixels, locate defects,
and issue pass/fail/unverified against every protected requirement. Keep physical
support, terrain/material connection, style/readability and motion distinct.
Never infer visual acceptance from a receipt, frame counter or effect count.

Inspect functional poses as pictures: actor feet on the near/middle/far crossing,
both landings, and actual interaction endpoints from relevant approaches. Include
a route from another landmark to the interaction. A hidden actor or feet drawn
behind a walking surface fails even if navigation and rewards work.

Prioritize a few concrete defects per repair round while retaining the entire
open list. After a repair, inspect fresh captures, account for prior findings and
check affected views for regressions. Two rounds repeating a major defect call
for a changed asset, geometry or composition strategy. More detail cannot repair
a failed primary form or contact.

Motion requires observed playback or a sufficient timed image sequence covering
the actual full cycle and wrap, joined parts and pause. Isolated stills and changing
frame IDs are insufficient. For focused work, cover only affected motion families
and retain valid evidence for unchanged art.

## Deliver with honest limits

Keep visual, motion, gameplay and performance verdicts separate. Test the relevant
desktop/mobile journey with real input. For crossings and interactions, cover
their actual arrival/idle poses as well as route success. Broaden regression
checks only for shared-engine changes or actual failures.

For full-world performance acceptance, record median/p95 frame intervals, viewport,
browser and actual renderer against a blank baseline. Native GPU and SwiftShader
results are not interchangeable; avoid concurrent software-rendered timings.
A focused visual repair does not require an unrelated performance investigation.

Run the [acceptance command](references/acceptance.md) on the final candidate.
Report open, failed, unverified or stale requirements as such. Passing local
validation does not authenticate a critic's judgment or guarantee reference quality.
Deliver the runnable host, relevant before/after and motion evidence, executed
checks, provenance and remaining limitations.

License notices: [NOTICE.txt](NOTICE.txt).
