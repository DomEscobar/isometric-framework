# Executed production stages

Use acceptance-plan **version 4** for new world production. It retains protected
images and the required `production` object, and adds the mandatory generated-art
[asset policy](asset-policy.md), character video provenance and actual blockout
image review. Freeze, snapshot and accept reject a production object on versions
1–3. Versions 1–2 remain for focused packed-art work without production stages;
they do not establish compliance with the version 4 policy.
Use the existing requirements, not a second artistic brief. Adapt the `production` object in the complete
[version 4 plan example](acceptance-plan.example.json); its neutral feature IDs
are illustrative. The agent prepares technical checks from the approved contract.

The tool controls its own tickets, receipts, candidate snapshot and acceptance.
It cannot prevent an arbitrary agent from editing files or calling a generator
outside this workflow. Implement eligible work first; call `begin` when that
candidate is stable, immediately before executing its check/capture. `begin`
hashes existing inputs: it opens an evidence attempt, not an implementation task.
Expand only after prior stages pass. A changed candidate needs a new ticket and
fresh evidence; keep the failed attempt's observations when repairing it.

Before this stage sequence, use the approved contract to resolve any missing
concept and rough composition within authorized scope/budget. Fixed layout
constraints guide the art; a flexible concept can propose geometry which the host
then derives and validates. Select initial visual references before freezing.
Store selection/provenance in host production data, not routine edits to the
contract. This preparation does not require a production ticket or authorize a
full pack. Acceptance remains frozen before calibration implementation/expansion.

| Stage | Required work before expansion |
| --- | --- |
| preflight | One selected generated asset decodes and loads in dev and production; projection, pixel scale and approved generation access/budget established |
| layout | Semantic regions, reserved routes, supports and entrances; spatial check plus actual blockout image review of grouping, open space and hierarchy |
| assembly | A representative connected area in the live host: related objects/surfaces, measured rigid bindings, usable approaches and controllable actor |
| static | All placed instances and full generated-asset provenance checked; separate composition, relationships/variation, connections and style reviews across ground-only/dressed views and required mobile regions |
| motion | Complete requested cycles, occlusion, interactions, input and contextual timing |
| final | Current whole-image judgment against the original target, followed by prior findings and full acceptance |

All configured checks block their next stage until passed. Whole-scene visual
requirements need static review coverage; nonvisual requirements need motion-stage
review coverage, including every protected view. Rigid assets require an assembly
geometry check. A passing alpha/animation inspection is not a geometry check.

Apply [environment composition](environment-composition.md) within these existing
stages. Plan areas before deriving asset families; inspect different area types
and their boundaries during expansion. Reuse images for multiple review criteria,
but retain separate outcomes so good style cannot waive a failed relationship or
contact. Focused repairs keep their affected scope; intentional regularity and
quiet space do not require additional variants or decoration.

For an unchanged candidate, begin the independent checks in the same stage before
capturing their shared images; then submit each criterion's own observations.
Evidence must postdate every ticket using it. This permits one capture session
without repeating the browser journey for each visual criterion.

## Protected check schema

Version 4 also requires the fixed `assetPolicy` shown in the complete example:
generated world/character/environment sources, image-to-video character animation,
a coverage ledger and actual runtime manifest/binding paths. All paths must be
inside `inputRoots`; they need not yet exist at freeze. Record the schema and source
chain as described in [asset policy](asset-policy.md). The full production inventory
must exist and validate by static-stage submission and remain valid through final
acceptance. Every static/motion/final check must include the ledger, runtime
manifest and binding in its source dependencies (directly or through a parent
directory). This makes a valid replacement chain invalidate prior observations,
even when the replacement itself passes provenance.

For version 4, a `layout` check in the layout stage uses `evidenceKind: "image"`:
its `source` still supplies spatial measurements, while the reviewer inspects the
actual blockout image and records the observed grouping/readability. A JSON-only
layout report cannot satisfy it. Hash the actual blockout host and projection
alongside the layout export so changes invalidate this evidence.

`production` has `version: 1`, nonempty unique `rigidAssets`, and `checks: object[]`.
An empty `rigidAssets` list cannot skip geometry calibration: every listed ID needs
an assembly-stage `art` check.
Each check has a unique `id`, `stage`, `method` (`review`, `layout`, `art`),
`requirements`, `views`, `inputs`, and `evidenceKind` (`image`, `motion`,
`measurement`). All paths are project-root-relative and use forward slashes.
Inputs may be files/directories, must be under the acceptance plan's `inputRoots`,
and are hashed including additions/removals. They may be created after freezing
the plan but must exist before beginning that check. Include host code, shared
renderer, layout and packed art wherever they can change its observed behavior.
Final-stage checks must cover every plan `inputRoot`; local receipt reuse cannot
replace a fresh overall review after any source change. Adapt example requirement
IDs (`style`, `motion`, `play`, `timing`) and paths to your existing protected plan.

Keep calibration inputs scoped to the real modules, art families and shared
dependencies that render that patch. The example separates startup, calibration
modules and selected art from later content; these paths must be actual host
dependencies, not copies of a disconnected demonstration. Include layout, camera,
renderer and export code when they affect the observation. Adding an unrelated
asset must not stale a rigid contact check; changing its renderer or footprint
must. Static/motion/final checks still cover the complete requested world. The
tool invalidates declared dependencies, so broad directory inputs will legitimately
repeat earlier stages; fix the dependency design rather than skipping validation.

`layout` also requires `source` and `requiredScope` with region/instance/route/bridge
ID lists. Every protected ID must remain present; extra instances are checked too.
A `layout` check at the `static` stage must additionally declare `artContract`, the
measured art-integration contract, as a dependency. Art exists by then, so every
exported instance's reserved cells are compared against the footprint its calibrated
asset measures. Grid semantics alone cannot see that a wall covers the square; the
comparison is what makes the existing water, route and overlap checks act on truthful
footprints instead of understated ones. The `layout` stage check runs before art and
therefore takes no `artContract`.
`art` also requires `source` (existing art-integration contract), `assets` (protected
asset IDs) and `binding` (the host's exported image/frame/anchor/render/footprint).
Every asset the host exports in that binding must appear in `assets`: calibrating one
prop cannot leave another exported rigid asset unchecked. Split unrelated families into
separate bindings with their own `art` checks rather than narrowing the protected list.
Every inspected image and binding must be covered by dependencies. The existing
Node `check-art.mjs` runs automatically; no shell command from a plan is executed.

Example binding, using the measured contract's exact projection and values:

```json
{
  "projection": {"tileWidth": 48, "tileHeight": 24, "heightPixelsPerUnit": 24},
  "assets": {
    "market": {
      "image": "host/art/market.png",
      "frame": {"x": 0, "y": 0, "width": 96, "height": 96},
      "anchor": {"x": 0.5, "y": 0.75},
      "render": {"width": 96},
      "footprint": {"columns": 2, "rows": 2}
    }
  }
}
```

These numbers are illustrative, not calibrated. Export binding from the same
host definitions used to render the scene. Matching two handwritten copies does
not prove host correspondence. Include the exporter/host source in review inputs
and inspect contacts in the actual game.

## Semantic layout schema

See [the neutral layout example](spatial-layout.example.json). Version 1 uses
integer cells `[column, row, floorId]`; different floors are different cells.

- `spawn`: starting cell for global reachability.
- `regions`: unique `id`, `kind` (planting/paving/grass/soil/water/deck), nonempty
  `cells`. Base regions must not overlap; bridges supply deck overlays.
  Each water region describes one axis-connected body. Separate ponds use separate
  IDs; diagonal corner contact does not connect a channel. If deck cells replace
  underlying water in the base regions, declare the water region's optional
  `underBridgeCells`: water cells hidden under declared bridge decks. These cells
  participate only in channel connectivity, not rendered overlays or walking support.
  Omit them when the water base region already continues beneath a deck overlay.
- `instances`: unique `id`, `kind` (tree/prop/building), nonempty `footprint`,
  `support` region ID, boolean `solid`, and `approaches` cells. Buildings require
  at least one approach; every approach must adjoin the footprint and a reachable
  reserved route. A tree's root belongs to a planting region, never circulation.
  `asset` names the calibrated contract asset the instance renders. A static
  placement check reads it for every exported instance, so an unnamed or unknown
  asset is a finding rather than an unchecked pass. Several instances may share one
  asset; the footprint's bounding box must equal that asset's measured
  `footprint`. Deliberate overhang belongs in the contract's `overhangPx`, not in a
  smaller reservation here.
- `routes`: unique `id`, nonempty `cells`, `start`, nonempty `goals`, integer
  `clearanceCells` (0..8). Cells must form one axis-connected route reachable from
  spawn. Clearance conservatively expands in both axes; solids/water/void block it.
- `bridges`: unique `id`, connected `deck` cells, two distinct supported `landings`
  included in the deck, and `waterOverlayCells`. Water overlay occupancy must
  exclude the deck. The host exports its actual overlay support mask, not merely
  the underlying water region.

All collections are required; use empty arrays where a feature is absent. Protect
expected IDs in the check. The layout should generate host placements/colliders;
image color classification can propose data but must not become silent authority.
Tree crowns may overhang paths: roots, physical clearance and visual occlusion are
separate checks. This first checker covers a discrete axis-connected grid; it does
not simulate slopes, cross-floor portals, subcell polygons or rendered alpha masks.
Use host-specific checks and actual views for those capabilities. Do not flatten
an intended multi-floor game to satisfy this check.

For example, water at `[2,0,"ground"]` and `[2,2,"ground"]` can connect through
`underBridgeCells: [[2,1,"ground"]]` only if that cell belongs to a declared bridge
deck. Water at `[2,0,"ground"]` and `[3,1,"ground"]` alone is disconnected. These
illustrative cells establish topology, not a preferred map design. Inspect the
rendered channel at bends and crossings as well: axis connectivity guarantees
shared cell edges, not sufficient pixel width after banks and masks are applied.

## Run one check

Ask for the next eligible work before opening a capture ticket:

```sh
python skills/isometric-visual-loop/scripts/verify-world.py production next review/baseline.json --receipts review/receipts
```

The JSON reports `nextStage`, `eligibleChecks`, expected evidence/views, missing
inputs and blockers. `state: "ready-to-work"` means a check can begin; it is not
production acceptance. `state: "complete"` means the configured production
receipts pass; final snapshot/comparison/acceptance are still separate commands.
Exit 0 means work is eligible or these receipts are complete; exit 1 means blocked
or invalid. The command creates no tickets, evidence or verdicts.

Before generating from a layout, compare its spawn, distant entrance and both
bridge landings with the neutral runtime view under the same camera transform.
Equal cell IDs do not prove equal image positions. If the host converts coordinates,
apply that conversion to all regions, routes, footprints and landmarks before
export; preserve one authority for collision and appearance.

### Render the layout in the runtime projection

The framework's public `project` maps increasing columns upper-right and increasing
rows lower-right. Do not substitute another commonly used isometric axis convention
when drawing a generation guide. The optional renderer imports that public function:

```sh
node --experimental-strip-types skills/isometric-visual-loop/scripts/render-layout.mjs host/layout.json --out review/layout-1 --tile-width 64 --tile-height 32 --png
```

The dimensions are illustrative; use the actual host settings. The new output
folder contains a clean `layout.svg`, a labeled `layout-debug.svg`, and
`projection.json` with projected landmarks and output origin. `--png` adds browser
captures using authoring-only Playwright/Chromium; omit it for SVG/JSON export
without browser dependencies. Supply the clean image to generation; diagnostic
labels and cell borders are evidence, not intended artwork. Compare the exported
landmarks with the host before spending on appearance. This utility does not
register a generated image, infer elevation, or prove rendered material alignment.
It exports one flat plane; for elevated or multiple-floor scenes, use a host export
with actual floor heights instead of flattening the intended environment.

### Execute a stage check

Python/Pillow and Node are the existing authoring dependencies. Keep tickets,
submissions and receipt directories outside all source `inputRoots`.

```sh
python skills/isometric-visual-loop/scripts/verify-world.py freeze host/acceptance.json review/baseline.json
```

Implement the eligible candidate and ensure its input files exist. Then:

```sh
python skills/isometric-visual-loop/scripts/verify-world.py production begin review/baseline.json --check preflight --receipts review/receipts --out review/preflight-ticket.json
```

Run the scoped check/capture after `begin`, keeping candidate inputs unchanged.
Make an evidence mapping containing
only local `path` and required `view` entries, then create the exact submission
template. `draft` reuses the finish-time evidence checks: each file must be fresh,
the declared kind, and cover every required view. It writes `unverified` with blank
reviewer and observations; fill those fields from the actual review and never turn
the template into an automatic pass.

For example, `preflight-evidence.json` contains
`{"evidence":[{"path":"review/dev-and-production.json","view":"desktop"}]}`.
Add an entry for each required view; multiple files may describe the same view.

```sh
python skills/isometric-visual-loop/scripts/verify-world.py production draft review/baseline.json --ticket review/preflight-ticket.json --evidence-mapping review/preflight-evidence.json --receipts review/receipts --out review/preflight-review.json
```

The resulting submission has the actual ticket and evidence hashes, plus `status`
(pass/fail/unverified), `reviewer`, `observed` and evidence:

```json
{
  "ticketSha256": "<actual ticket SHA-256>",
  "status": "unverified",
  "reviewer": "",
  "observed": "",
  "evidence": [
    {"path": "review/dev-and-production.json", "sha256": "<actual file SHA-256>", "view": "desktop"}
  ]
}
```

```sh
python skills/isometric-visual-loop/scripts/verify-world.py production finish review/baseline.json --ticket review/preflight-ticket.json --submission review/preflight-review.json --receipts review/receipts --out review/receipts/preflight-1.json
python skills/isometric-visual-loop/scripts/verify-world.py production status review/baseline.json --receipts review/receipts
```

`finish` is the only command that writes a receipt. It reruns automatic geometry/layout checks and rejects a claimed pass when
they fail. Image evidence must decode; every required view must be covered. Evidence
must be written after the ticket, and sources must still match the ticket. Receipt
files are immutable outputs. A ticket is single-use and cannot finish after a newer
attempt for that check. Serialize attempts for the same check; parallel work on
different eligible checks is possible when input ownership is disjoint.

The latest receipt wins, including failures. `status` reports the earliest open
stage and, for every check, its eligible flag, concrete blockers, required views,
evidence kind, declared inputs and whether a strategy is required. Unchanged checks can reuse their existing receipts;
changed inputs invalidate only declared dependents. Do not recapture everything
automatically. Missing dependencies, altered file timestamps, copied images or
forged records are outside this local tool's capture/authentication trust boundary.

After two failed attempts at one check, `begin` requires `--strategy PATH`:

```json
{
  "check": "assembly-view",
  "previousReceiptSha256": "<latest failed receipt SHA-256>",
  "hypothesis": "Explain the changed asset or assembly approach.",
  "test": "One observation that can distinguish the new explanation."
}
```

This is a strategy checkpoint, not a quality waiver or permission to stop. Preserve
original targets and scope. Work on at most three root causes per round. Inspect
the overall image before closing old findings; file counts are not a quality score.

## Candidate and final acceptance

After stages through motion pass, snapshot with `--production-receipts review/receipts`,
capture current whole-world views, execute the existing `compare` loop and complete
the final-stage check. Run `accept` with the same receipt-directory option. Version 4
blocks a candidate before prerequisite stages pass and blocks acceptance until all
stages and the existing complete visual/motion/gameplay/performance gates pass.
Generated-source and character-video provenance are checked against the actual
runtime inventory as part of this acceptance. Focused version 1–2 plans without
production stages are reported as legacy, never as version 4 provenance acceptance.

Version 2 comparison baseline corrections do not silently migrate production
receipts: receipts bind to the frozen baseline. An explicit new production baseline
requires revalidation. Spatial and rigid metadata still require correspondence
with the real game. Successful synthetic defect tests validate this machinery;
they do not certify a generated world's visual quality.
