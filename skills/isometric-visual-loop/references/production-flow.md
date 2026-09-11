# Executed production stages

Use acceptance-plan **version 3** for new world production. It retains version 2's
protected images and adds a required `production` object. Versions 1/2 remain
compatible for historical/focused work; they do not prove these stage gates ran.
Use the existing requirements, not a second artistic brief. Copy and adapt the
[illustrative production section](production.example.json) into the plan.

The tool controls its own tickets, receipts, candidate snapshot and acceptance.
It cannot prevent an arbitrary agent from editing files or calling a generator
outside this workflow. Agents must call `begin` **before** the work/evidence for
the check, and expand only after all prior stages pass.

| Stage | Required work before expansion |
| --- | --- |
| preflight | One actual asset decodes and loads in dev and production; provider, projection and pixel scale established |
| layout | Semantic regions, reserved routes, supports, entrances and blockout in the runtime's actual projection |
| assembly | Actual selected artwork, measured rigid contact/scale binding, controllable actor, materials and riskiest structure in the live host |
| static | All placed instances checked; complete ground-only/dressed composition and required mobile regions |
| motion | Complete requested cycles, occlusion, interactions, input and contextual timing |
| final | Current whole-image judgment against the original target, followed by prior findings and full acceptance |

All configured checks block their next stage until passed. Whole-scene visual
requirements need static review coverage; nonvisual requirements need motion-stage
review coverage, including every protected view. Rigid assets require an assembly
geometry check. A passing alpha/animation inspection is not a geometry check.

## Protected check schema

`production` has `version: 1`, `rigidAssets: string[]`, and `checks: object[]`.
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

`layout` also requires `source` and `requiredScope` with region/instance/route/bridge
ID lists. Every protected ID must remain present; extra instances are checked too.
`art` also requires `source` (existing art-integration contract), `assets` (protected
asset IDs) and `binding` (the host's exported image/frame/anchor/render/footprint).
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
python skills/isometric-visual-loop/scripts/verify-world.py production begin review/baseline.json --check preflight --receipts review/receipts --out review/preflight-ticket.json
```

Run the scoped check/capture after `begin`. Make an evidence mapping containing
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
the final-stage check. Run `accept` with the same receipt-directory option. Version 3
blocks a candidate before prerequisite stages pass and blocks acceptance until all
stages and the existing complete visual/motion/gameplay/performance gates pass.

Version 2 comparison baseline corrections do not silently migrate production
receipts: receipts bind to the frozen baseline. An explicit new production baseline
requires revalidation. Spatial and rigid metadata still require correspondence
with the real game. Successful synthetic defect tests validate this machinery;
they do not certify a generated world's visual quality.
