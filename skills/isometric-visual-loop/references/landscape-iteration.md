# Landscape iteration

For new landscapes, use [v5 landscape verification](landscape-verification.md)
inside the same six stages and [ground assembly](../../consistent-tileset-authoring/references/landscape-ground-assembly.md)
for the executable quilting/contact/underlay/binding chain. The v4 evidence mapping
below remains useful for existing plans; it does not satisfy v5 structured checks.

Use this reference for landscape-only work or a substantial environment revision.
It supplements the approved `PROJECT_CONTRACT.md`, the production stages, and the
selected specialist skills. It does not grant a new feature, asset, or spending
scope.

Use this within [production stages](production-flow.md) and [acceptance](acceptance.md).
Read [environment composition](environment-composition.md) when planning areas. For object contacts,
use [grounded assemblies](../../isometric-art-integration/references/grounded-assemblies.md).
For connected natural materials, use [landscape composition](../../consistent-tileset-authoring/references/landscape-composition.md).
For water and foliage loops, use [animated environments](../../animated-environments/SKILL.md).
The generated-art and character animation requirements remain in the
[production asset policy](asset-policy.md); do not restate or weaken them here.

## Keep the active scope visible

Record the currently authorized scope beside the host production data: affected
regions, allowed families, excluded systems, and the desired decision. Examples
of excluded systems include residents, pets, sound, quests, and combat.

Treat a user stop as authoritative. Stop the named experiment immediately, retain
its captures and measurements as **canceled, unaccepted evidence**, and identify
which changes are active. Revert an experiment only when that rollback is authorized
or is part of the agreed experiment; preserve unrelated and previously verified
work. A stop is not blanket permission to restore an old checkout. Do not present
a canceled optimization, variant, or benchmark as a recommended default or resume
the stopped work without subsequent authorization.

Do not edit the contract merely to track routine variants, failed attempts, or
selection history. The contract remains the human requirements source.

## Establish the whole map before multiplying detail

Start from one semantic whole-map layout. It must name at least:

- regions and their material roles;
- routes, entrances, crossings, and useful open ground;
- support, water, bridges, footprints, reservations, and access cells;
- landmarks, dense areas, quiet areas, and their intended hierarchy.

Render and inspect the whole map as a neutral blockout before commissioning a
large pack. A representative connected area is still useful, but it must include
the actor, an important route, a material boundary, and a meaningful contact.
It never reduces a promised full world to a small calibration slice.

Run a full-world stress review as soon as the principal families exist. Look for
repeated grass, uniform coast width, stranded landmarks, monotonous paths,
unreadable clearings, and seams that a small patch cannot reveal. Preserve the
semantic layout while comparing variants unless the variant intentionally tests
layout itself.

## Calibrate density before expansion

Separate three measurements:

1. **Source density**: decoded source pixels and export pixels per world unit.
2. **World projection**: logical tile dimensions, world coordinates, anchors, and
   object footprints.
3. **Presentation**: camera zoom, CSS viewport, canvas DPR, browser renderer, and
   device/GPU limits.

Build a small density matrix at the intended playing zoom before broad asset
placement. For each candidate record source dimensions, export dimensions, world
extent, viewport, zoom, DPR, atlas or texture limit, renderer, and fallback.
Capture the same landmark and contact at each candidate setting. A larger texture
frame is not automatically a larger logical tile or a higher phone resolution.

For a projected horizontal extent, expected display pixels are approximately
`world extent * camera zoom * effective canvas DPR`. Compare this with retained
source detail; use the runtime's actual DPR cap, not just the device's advertised
value. Re-export from accepted originals when earlier exports discarded useful
detail. Enlarging a small runtime PNG does not recover that information. Scale
atlas gutters, frames and alpha padding consistently, and check texture limits
before loading the selected atlas. RGBA size estimates are not measured total GPU
memory. Intentional coarse pixel art may need no density increase.

Choose the density from observed legibility and safe renderer limits. There is no
universal tile size, DPR, or scale default. Freeze the selected source/export path
with the corresponding host bindings before expanding the world.

## Run controlled visual comparisons

Give each study a descriptive name, such as `coast-grass` or `ground-contact`.
For every study, state:

- the question it answers;
- variables intentionally changed;
- invariants: layout, source family, actor scale, viewport, camera, time/period,
  motion state, and unrelated placement unless the study names an exception;
- the required views: whole map, playing view, ground-only, dressed, and contact
  detail when relevant;
- the pass/fail observations that decide the next step.

Use the protected board and finding history described in
[visual comparison](visual-comparison.md). Capture the same viewport, camera, zoom,
time/period, and motion state for alternatives. If two variables changed together,
label the result as a combined comparison; do not claim that one of them caused the
difference.

Keep a compact decision record in existing host production data or the comparison
round: study name, alternatives, variables, observations, agent recommendation,
user selection, rejected choices, and any invalidated evidence. The user's choice
supersedes an agent recommendation. Preserve both facts; never rewrite a historical
recommendation as the selected result.

A record can be a short section in the existing round notes:

```text
Study: coast-grass / round-2
Question: which bank treatment keeps the protected route clear?
Changed: bank/grass treatment. Fixed: layout, prop bindings, camera, density, time.
Candidates: narrow-bank, planted-bank (link each actual capture).
Observed: [specific locations and defects, plus invariant check results].
Recommendation: [choice and tradeoff]. Selection: [choice; user or delegated agent].
Supersedes: [earlier study decision, if any]. Still open: [unresolved findings].
Evidence: [comparison ID, source snapshot, capture profile and relevant receipt].
```

The example is a note format, not a new acceptance schema or mandatory file.
When authorized to choose autonomously, record the selection and proceed; do not
turn routine variants into another permission request. Different studies may
choose different methods: a clear geometric path can share a world with a soft
pond and an irregular coast.

## Ground contacts are physical and visual

Treat a contact as a relationship between a base, supporting material, route, and
depth order. Measure the visible foot/contact point in the runtime projection.
Then declare separately:

- physical footprint and blocking cells;
- build or decoration reserve;
- reachable approach or interaction forecourt;
- supporting surface and any actual height;
- rendered anchor, scale, layer, and depth behavior;
- visual treatment: roots, foundations, bank lip, worn approach, or local material
  transition.

Do not infer collision from an alpha silhouette. A crown, roof, or decorative
overhang may be visible beyond the physical foot. Conversely, a painted relief is
not a raised walking surface. Check the ground-only view and the dressed view with
the actor at the relevant approach, near/middle/far crossing positions, and both
landings where applicable.

`placement_checks.py` compares a calibrated **rectangular extent** with a declared
grid footprint. It does not enforce arbitrary polygons, per-instance scale, or a
host's access logic automatically. Add host-specific calibration and access checks
when those facts determine the result. Calibrate distinct size variants truthfully;
do not shrink a declared footprint or label a custom polygon check as a pass from
the packaged rectangle checker. Existing required art/layout checks still apply.

## Keep one host authority for geometry

The host's semantic layout/export must be the authority for transformation,
placement, blocking, reserve, access, support, and rendered binding. Generate
guides through public projection APIs and verify landmarks against the running
host. Do not maintain disconnected handwritten collision, art, and route copies.

Use explicit collision and depth declarations. A nonblocking presentation pattern
may be appropriate for a particular host, but `blocking: false` is not a universal
solution for water, decks, foregrounds, or tall props. Choose it only when that
host's terrain support, entity ordering, and route rules establish the required
behavior.

If polygon-derived terrain cells own solid blocking, avoid double-blocking them
with an unrelated entity rectangle. Retain appropriate entity dimensions and
body height for depth ordering. Keep walk blockers, build reserves and entrances
separate. Freeze a reviewed placement result; do not silently move or shrink
objects at load time to make a validator pass. Preserve semantic family metadata
when assigning instance-specific type IDs so lighting and motion still find it.

Use public runtime APIs, scene data, and events. Do not import private renderer
state, mutate private fields, or add game-specific branches to the engine.

## Make placement communicate the world

Each region needs a role: circulation, gathering, shelter, viewpoint, water edge,
planting, landmark, or open rest. Vary related forms because of those roles, not
because a checklist requests more sprites. Keep routes legible and reserve useful
open ground. Inspect the strongest repeated motif at playing zoom.

For each major landmark, test the actual approach, arrival, idle pose, visible
entrance, and an approach from another region. A technically reachable door hidden
behind a foreground object fails the visual interaction view. Capture clean views
without diagnostic overlays as well as the geometry/occupancy evidence.

## Animate rooted structures, not decoration everywhere

Name each motion family, its fixed base, moving region, contact, duration, frame
count, FPS, joins, and pause/reduced-motion behavior. Keep roots, banks,
foundations, bridge support, and other rigid landmarks fixed while leaves, water,
foam, or clouds move. Use local semantics: a water surface, flow direction, and
bank are different concerns.

Observe actual playback. Verify that pause freezes simulation-driven motion,
reduced motion follows the host policy, joined edges remain coherent, and a full
cycle returns without a structural snap. Frame IDs, still screenshots, or changing
pixels alone do not prove motion quality.

## Independent landscape rubric

Derive protected requirement IDs from the contract. For the applicable landscape
features, keep separate judgments for: reference/pixel treatment; meaningful
composition; readable connected routes; continuous materials and exterior path
edges; water/bank/grass transitions; object-ground integration; scale and physical
bases; visible usable entrances/crossings; variation without repeated pads; and
the complete promised extent. Motion, input and performance are separate domains.

Assign a reviewer other than the builder after captures stabilize. Give that
reviewer the original reference, requirements and actual ground-only/dressed,
detail and overview images, not only a builder summary. Require image inspection,
specific evidence locations, `pass`, `fail` or `unverified` per criterion, and
reinspection of earlier findings. A missing image tool cannot yield a visual pass.
Do not average scores: every required criterion must pass before its expansion.
The v5 [verification schema](landscape-verification.md) binds those judgments to
the author, reviewer, source state and capture metadata. It cannot prove honest
image viewing or stop tool calls outside the workflow.

## Map evidence to independent version-4 gates

Keep these verdicts distinct:

| Gate | Required evidence |
| --- | --- |
| Geometry | Semantic layout/export, footprint/reserve/access/support checks, and real arrival poses. |
| Visual | Protected whole-map, playing, ground-only, dressed, and contact comparisons with current observations. |
| Motion | Observed full-cycle playback, joins, pause, and reduced-motion behavior for promised families. |
| Gameplay | Actual input journeys through routes, crossings, and interaction endpoints on the contracted controls. |
| Touch | Emulated touch may prove the browser journey only; record viewport, DPR, pointer evidence, and overflow. A real device is a separate claim. |
| Performance, when in scope | Baseline and candidate intervals with viewport, browser, renderer/GPU, scene state, and workload. Distinguish native clip FPS, runtime update calls, uncapped RAF intervals and actual render/presentation counts. RAF cadence is not rendered FPS. |
| Provenance | The existing runtime inventory, ledger, and frozen source chain required by the production asset policy. |

Hash the host code, layout/export, asset bindings, images, and configuration that
can change each observation. Keep evidence outside protected inputs. A build or a
technical test is not visual, motion, touch, performance, or production acceptance.

For an existing v4 plan, use its checks rather than inventing a `landscape` domain:
preflight `review` covers density/loading evidence; layout `layout` plus image
review covers the map; assembly `art` and `review` cover calibrated bindings and
contacts; static checks cover full-world geometry and comparisons; motion reviews
cover actual cycles/input; final review covers the complete current deliverable.
Host polygon/access reports can support a `review` with `evidenceKind: "measurement"`;
they supplement, rather than replace, required layout/art checks. Put the report's
source modules and bindings in that check's inputs. Do not add a pet or character
production requirement to a landscape-only contract: a diagnostic probe proves
only its own poses, not a future character's occlusion or animation.

## Invalidate only what changed, then recheck honestly

| Change | Evidence to refresh |
| --- | --- |
| Source/export density, atlas, camera projection, or fallback | Density matrix, affected captures and packed-art inspection; a matching workload comparison if performance is in scope. |
| Ground mask, coast, path material, or contact treatment | Ground-only, dressed, contact-detail, and affected route/support checks. |
| Footprint, anchor, scale, collision, reserve, access, or depth | Layout/export, placement/access checks, actual arrival poses, and affected visual views. |
| Motion frame, phase, base, or pause behavior | Full-cycle, joins, pause/reduced-motion, and affected runtime views. |
| Layout, route, bridge, water, or landmark position | Whole-map stress, geometry, route/arrival, and all affected comparisons. |
| User scope or visual decision | Reconcile changed requirements with the approved contract/plan; routine selections update production data and affected inputs. Preserve the prior baseline/decision. |
| Canceled experiment | Record cancellation and the actual active source state. Do not submit canceled measurements as passing evidence or silently restore unrelated files. |

Use the production-stage carryover mechanism for valid unchanged receipts. Never
claim that an old capture proves a changed dependency. After two failed repairs of
the same defect, change strategy: geometry, contact method, source family,
composition, or motion technique. State the discriminating next observation.

## Diagnose visible failures before adding detail

| Symptom | Inspect first | Decide next |
| --- | --- | --- |
| Visible grain or chunky zoom | Source/export density matrix at the same world extent and zoom. | If source detail was discarded, re-export from accepted originals; if it is inherent, change the selected density or art treatment. |
| Sticker-like props | Ground-only/dressed contact, measured foot, anchor, base material, and duplicate shadows. | Repair the physical base and local contact treatment; do not add a universal oval pad. |
| Inaccessible or hidden entrance | Semantic approach/route, solid/reserve separation, arrival pose, and clean rendered view. | Correct the shared host authority or placement; a passing path alone is insufficient. |
| Repetitive grass or flat hierarchy | Whole-map stress view, repeated motif, region roles, and open-space rhythm. | Vary families and material roles where the composition needs them; do not scatter random decorations. |
| Coast seams or floating water | Shared masks/world origin, bank contacts, joins, edge alpha, and rendered boundary at bends. | Repair the common coast system and inspect all affected densities; do not patch one screenshot. |

Finish by reporting accepted, failed, unverified, and canceled work separately.
