# World production flow and check schema

Status: the core stage, spatial, geometry-binding and freshness checks are now
implemented for version 3 acceptance plans. Use the self-contained
[operational schema, examples and commands](../skills/isometric-visual-loop/references/production-flow.md).
This document retains the design rationale; the operational reference defines the
implemented format and its discrete-grid/trust limits. Existing comparison and packed-art gates remain supported.
Examples below are illustrative and contain no artwork or defaults from a game.

## Six stages

Each stage produces one result and names the next permitted action. Failed or
unverified blocking checks prevent expansion. Local repair inside the failed stage
remains allowed. A polished screenshot cannot override a failed spatial check.

| Stage | Work and minimum checks | Exit evidence | Blocked next action |
| --- | --- | --- | --- |
| 0. Preflight | Confirm target role, scope, provider, pixel/projection contract; decode one asset; minimal host loads in dev and production | One working host and asset, build/load receipt | Full asset requests |
| 1. Layout | Author regions, routes, planting, entrances and camera framing; validate root placement, clearances and landmark connectivity | Semantic layout, whole-map blockout and relevant mobile framing | Decorative production |
| 2. Representative assembly | Actor + rigid prop + connected materials + riskiest structure; measured contacts, alpha, proportions, depth, short traversal and representative motion | Packed/contact preview and a small live assembly accepted against the target | Remaining asset families and full dressing |
| 3. Complete static world | Complete authored scope; apply placement checks to every placed instance; inspect ground-only and dressed views | Full-scene verdict plus localized defects, with regions/entrances covered | Full motion/evidence sweep |
| 4. Motion and play | Complete requested clips/actions; observe wraps, fixed roots, occlusion, interactions, input and timing | Current scene journey, relevant packed playback and timing context | Delivery |
| 5. Final review | Compare original target/current/previous; assess overall effect as well as prior fixes; verify freshness and complete scope | Independent visual judgment, separate domain verdicts and acceptance receipt | Completion claim if anything required remains open |

The blockout and assembly are internal milestones; they do not reduce the requested
final scope. A visual-only project marks non-applicable gameplay work explicitly in
its contract. It cannot silently remove requested animation or interaction.

## One spatial source of truth

Keep a host-owned semantic layout, separate from renderer objects. It owns:

- Terrain regions and their intended materials.
- Reserved route corridors and minimum clearance, including actor body dimensions.
- Planting areas, soil pits, water, supports and no-placement areas.
- Object instances with support footprints, entrances and interaction approaches.
- Assembly parts, deck/water exclusions, depth planes and attachment points.

Derive artwork placement and occupancy from this data. Generated textures can
decorate a region. An image classifier can propose a region but cannot silently
replace it. Do not use incidental pixel color as authoritative collision data.

Illustrative constraints:

| Check | Observable rule | Method |
| --- | --- | --- |
| Root support | A tree's root footprint is contained in a declared planting surface | Deterministic containment; canopy overhang reviewed separately |
| Route clearance | Solid footprints do not intersect reserved circulation, expanded for the actor's required clearance | Deterministic geometry/path test |
| Entrance access | Every required entrance has an appropriate approach area connected to its intended route | Deterministic reachability plus visible doorway/approach inspection |
| Prop support | Bench/stall/building base contacts lie on the declared support, with no unsupported corners | Measured contact fit and live overlay |
| Projection | Rigid base axes agree with the projection; vertical structures remain vertical; repeated constructed parts retain intended spacing | Existing art checker where supported, plus source-pixel landmarks and visual review |
| Bridge assembly | Both landings connect through the support surface; water excludes the deck; actor/rails order correctly at entry, middle and exit | Geometry plus the same live views with/without optional art |
| Pixel treatment | Logical pixel scale, outlines and proportions form a coherent family | Shared-scale preview and in-game visual review |
| Whole composition | Regions, focal point, route, density and lived-in situations satisfy the target at a useful scale | Independent whole-image judgment, before defect-by-defect scoring |

For a 48-by-24 illustrative grid, horizontal ground axes have screen slopes +0.5
and -0.5. That does not constrain an organic crown or a curved roof to a straight
line. Choose measurement tolerance from actual source-pixel uncertainty before
testing; do not widen it until an incompatible asset passes. Prefer correcting or
replacing the asset over distorting its whole image.

## Check record schema

Use the existing protected acceptance requirements and art contracts. The proposed
orchestrator adds stage/dependency records; it does not create a second competing
list of artistic requirements. A check record has this shape (illustrative):

```json
{
  "id": "layout.root-support",
  "stage": "layout",
  "requirementIds": ["spatial-coherence"],
  "method": "deterministic",
  "blocking": true,
  "scope": {"instances": ["tree-a"], "views": ["overview"]},
  "inputs": [
    {"path": "world-layout.json", "sha256": "<actual source hash>"}
  ],
  "status": "fail",
  "observed": "Root footprint intersects a reserved route.",
  "evidence": [
    {"path": "review/placement-overlay.png", "sha256": "<actual capture hash>"}
  ],
  "findings": [
    {
      "id": "root-route-overlap",
      "severity": "blocker",
      "location": {"instance": "tree-a", "region": "main-path"},
      "repair": "Place the root inside a planting region and preserve route clearance."
    }
  ],
  "reviewer": "layout-checker",
  "nextAction": "repair-layout"
}
```

Validation rules for the proposed runner:

1. Unique check IDs; stage is one of preflight/layout/assembly/static/motion/final.
   Method is deterministic, visual or interaction; status is pass/fail/unverified.
2. Every check links to protected requirements and declared input dependencies.
   Empty required scope, missing evidence or unavailable vision means unverified.
3. Visual findings locate their source pixels; spatial findings locate instances,
   regions or contacts. Failure needs a concrete observed difference and repair.
4. Every blocking check required by a stage must pass before the next stage opens.
   A pass belongs to matching input/evidence hashes, not to a mutable filename.
5. Changing layout invalidates placement, composition and affected routes; changing
   a sprite invalidates its alpha/contact/proportion and affected rendered views.
   A shared renderer change invalidates all dependent rendered evidence.
6. Carry forward earlier evidence only when every declared dependency remains equal;
   record that reuse explicitly. A new candidate still needs fresh overall captures.
   Dependency completeness is a trust boundary and needs review.
7. Old finding IDs survive repairs. Every required region remains covered even when
   a finding moves to a newly added comparison. No silently narrowed criteria.
8. An orchestrator enforces these transitions when it controls execution. Files
   alone cannot force an arbitrary agent to follow them or authenticate vision.

## Efficient capture and repair

Derive a small capture matrix from the contract: one matched overview, the worst
material transition, a ground-only/dressed pair, and mobile views covering each
required region. One image may cover several requirements. The number of files is
not a quality score. Add a view only when it closes a named coverage gap.

During assembly, capture a short traversal and representative cycle. After the
static gate passes, record one indexed journey per required viewport with timestamps
for interactions and full cycles. Select frames for actual occlusion/wrap questions;
do not create dozens of near-identical screenshots by default. An independent critic
can request a missing state rather than rerunning every deterministic test.

For each repair round:

1. State at most three root causes and the observable changes that will address them.
2. Fix the owning representation; run its cheapest meaningful check first.
3. Capture affected views and one current overview; compare with the original target.
4. Assess the whole image before resolving individual previous findings.
5. After two failed attempts at the same defect, stop parameter tuning and revise the
   asset/assembly approach. Record the new hypothesis and one discriminating test.

Two attempts is a strategy-change checkpoint, not permission to accept a failure or
abandon authorized work. Respect any user-defined generation/spend limits. Do not
invent an automatic time-based quality waiver. Report phase time, provider calls,
repairs and evidence reuse so efficiency can be measured in a subsequent trial.

## Verification of the implementation

The implementation's regression suite includes deliberate failures: tree root on a
path, blocked entrance, incompatible rigid base, disconnected landing, water over
deck and missing mobile region. Require the appropriate stage to reject each;
tests dependency invalidation and honest reuse after a local correction. Review
actual images for aesthetic outcomes. Then run a fresh independent production
session. A valid JSON record alone is not proof that this flow works.
