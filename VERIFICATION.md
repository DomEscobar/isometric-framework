# Runtime verification — 2026-09-10

## Executed production-stage checks

Acceptance-plan version 3 now requires six stages: preflight, layout, assembly,
static world, motion and final review. `production begin/finish/status` records
source-bound tickets and immutable receipts; missing/failed prerequisites block
the next stage and version 3 candidate/acceptance commands. Versions 1/2 remain
compatible and do not retroactively certify stage execution.

- Python/Pillow suite passed **41/41**, including CLI version 3 final acceptance
  with the existing comparison gate. Deliberate failures cover roots on paths,
  blocked entrances/clearance, isolated routes, disconnected bridge support,
  water over deck, incompatible rigid geometry, changed host bindings, missing
  mobile evidence, removed scope, stale inputs/evidence and ticket reuse.
- Unchanged check dependencies preserve their receipts. Final review covers all
  source roots. Two failed attempts require a recorded strategy change; consumed
  or superseded tickets cannot bypass it.
- A fresh independent read-only agent reproduced four false passes during review
  (old evidence, removed placement scope, isolated routes and ticket reuse).
  After repairs it independently confirmed all four reject. Local probes remain
  under `test-results/production-flow-audit/` and are not package content.
- The existing art-integration suite passed **23/23**. `npm run check` passed
  22 module boundaries and strict TypeScript. Skill metadata, neutral JSON
  examples and 76 skill-local links were verified.
- Runtime APIs and host gameplay are unchanged by this stage patch. No new game
  generation or browser playtest was needed for this headless authoring change.
  The prior generated world remains visually unaccepted and paused.

Limits: spatial checks use declared discrete cells and host exports, not inferred
sprite geometry or live renderer introspection. Rigid contracts are checked against
exported host settings and the existing Node checker; truthful measurements and
export correspondence still need visual review. Evidence mtimes enforce local
ordering, not capture authenticity. Stage tooling cannot prevent unrelated agent
tool calls. See the [operational schema](skills/isometric-visual-loop/references/production-flow.md).

## Executed visual comparison workflow

Version 2 authoring plans protect actual target images for every visual requirement
and view. The new `compare` command copies reference/current/previous images into
a self-contained board and review packet. Reviews record localized observations,
concrete repairs and the fresh resolution of earlier open findings. Acceptance
rejects incomplete or stale comparisons. Version 1 remains compatible and reports
zero comparisons when none were required; that does not establish image review.

- Python/Pillow regressions passed 23/23: existing packed-art gates plus target
  coverage, source/reference freshness, decoded-image integrity, localized review,
  previous findings, reviewer ordering, immutable outputs and layout dimensions.
  The review packet retains protected requirement descriptions and rejects changes
  to those criteria; the board displays them beside the relevant images.
  A calibration-group regression also proves that a passing subset cannot bypass
  missing clips in final acceptance. The art-integration suite passed 23/23.
  Wide assemblies retain the previous per-frame pixel budget and crop-padding
  checks. Explicit art-check baseline corrections preserve requirements, target
  hashes, previous images and findings; changed criteria or targets are rejected.
- Chromium passed both first-round and previous-round board probes: decoding,
  shared zoom, source-pixel rectangle selection, clearing overlays, previous state,
  mobile stacking/overflow and an injected decode failure. A mobile overflow found
  during testing was repaired. Boards were also visually inspected.
- The independent production session exposed a calibration problem: inspecting
  the initial actor pack stopped at a planned creature clip that did not exist yet.
  Added `inspect --groups` with an explicit calibration label, preserving the full
  frozen spec and unconditional full inspection at acceptance. Its preview was
  exercised in Chromium against the real generated actor atlas: decoding, subset
  warning, pause, shared zoom, changing clip pixels and dark background passed.
  These presentation checks do not approve pose quality or extraction fringes.
- `npm run check` passed module boundaries and strict TypeScript. Skill metadata
  validation passed, all 71 local skill links stay within `skills/`, and the JSON
  examples parse. The npm dry run includes the comparison module, HTML and guide,
  and excludes local evidence and Python caches.
- Ownership is authoring tools and guides; runtime APIs are unchanged. The tool
  validates coverage and freshness, not aesthetic truth, capture origin or reviewer
  identity. It does not invoke a vision model. Actual image inspection remains a
  required agent action; stills cannot approve motion or gameplay.
- The neutral terrain fixture exercises mechanics only. It is not evidence for
  generated-sprite world quality. A separately started Codex CLI session is testing
  the workflow against the user's actual target with a new generated-art host;
  that production evaluation is recorded in [the real trial](docs/PIXEL_BOROUGH_TRIAL.md).
  Its first independent image review fails, and the reviewed repair is in progress;
  no final world acceptance is claimed. The actual seven-comparison board passed
  its browser controls probe. A separate 22-check keyboard/touch probe passed but
  exposed a visible mobile Restart camera defect, retained for repair.

## Connected landscape authoring guidance

The terrain workflow now starts with regions, material-pair boundaries and
variation across cells for natural ground. The rigid raised-bed helper is
explicitly scoped to its supported geometry. Added a neutral landscape reference,
variant-array binding example, ground-only review views and separate terrain
requirements in the acceptance example and README starter prompt.

- Three affected skill entrypoints passed metadata validation; all 68 local skill
  links resolve within `skills/`. Markdown fences and the acceptance JSON parse.
  The single-variant and alternative-array examples compile against public core.
- A separate agent's read-only planning probe selected shared ground patches and
  material-pair transitions, rejected the bed helper for natural banks, and kept
  missing reference fidelity unverified. Its response placed acceptance setup too
  late in the numbered plan; the landscape reference now explicitly puts protected
  requirements before implementation. This probe is workflow evidence only.
- No terrain compositor or engine feature was added. No art was generated and no
  rendered landscape was accepted. Runtime/browser suites were not rerun for these
  documentation-only edits; a real host build is still needed to assess results.

## Retro Diffusion provider option

Added a provider-specific reference within the generation skill and exposed Retro
Diffusion MCP alongside WaveSpeed and other project-selected techniques. Removed
the blanket Seedream preference. Guidance follows the provider's current MCP and
compatibility documentation; no remote generation, installation or authentication
was performed, and generated quality has not been benchmarked here.

The generation skill passed metadata validation; all 62 local skill links remain
inside `skills/`. This is a documentation change with no runtime API impact. A
larger guided project-contract workflow remains a proposal under discussion.

## Self-contained skill references

Production skills now use neutral, skill-owned examples instead of named trial
reports, game captures or inherited asset measurements. Runtime binding examples
for art, autotiles and timed gestures live beside their owning skills. Historical
comparison instructions, their challenge and synthetic artwork moved unchanged to
`docs/history/environment-workflows/`; the existing lab and evaluator use that path.

- All seven production skills passed the skill metadata validator. All 57 local
  skill links resolve inside `skills/`; 111 local links across skills and changed
  guides resolve. No named example hosts or trial-report links remain in skills.
- Three new TypeScript examples passed strict compilation against public source
  exports, with their stated host prerequisites supplied by temporary declarations.
- `npm run check`, all 23 art-skill tests and the demo Vite build passed. The build
  retains its existing large-chunk warning. Runtime APIs and artwork are unchanged.
- The accepted environment fixture passed assembly, negative probes, animated
  pixel/pause/wrap, crossing, underpass and stone-collision checks. The lab's desktop
  and mobile journeys passed with no page errors. These used an explicitly started
  server on 4187 because another checkout owned 4175; the temporary server was stopped.
- Package inspection finds exactly seven `SKILL.md` entries, the new references,
  and no historical challenge assets, comparison variants or Python caches under
  `skills/`. All seven archived files retain their prior contents.

## Authoring acceptance gates

Added `skills/isometric-visual-loop/scripts/verify-world.py` and its workflow
reference. Ownership is authoring tools and guides; there is no runtime API change.
The workflow protects requirements and art thresholds, inspects decoded runtime
crops, and requires complete reviews with current source/evidence hashes.

- Python/Pillow regressions passed 12/12, including CLI failure/acceptance exit
  codes, neighbor fragments, crop margins, opaque overlays, repeated-pixel clips,
  stale inputs/evidence, omitted verdicts/views and altered protected requirements.
- The generated preview passed 12 Chromium checks: image decoding, frame/clip
  display, actual animated pixels, pause, shared zoom, anchor/frame overlays,
  backgrounds, failure labels, real failing art, one-shot stop/hold and replay.
  Rendered captures were self-inspected. Local evidence and the browser probe are
  under ignored `test-results/visual-gate-qa/`; no independent art verdict claimed.
- A read-only check of the external Fernwild atlas found neighbor components in
  12 ranger frames and pixels outside the diamond in all 12 inspected water frames.
  The source artwork was neither changed nor added to this package or its tests.
- `npm run test:art-skill` passed 23/23; `npm run check` passed boundaries for 22
  source modules and strict TypeScript. The npm dry run includes the portable tool
  and reference, and excludes Python caches and local test-results evidence.
- Full runtime/game suites were not rerun for this authoring-only change. The
  gate verifies structural checks, declared coverage and freshness; it cannot
  authenticate reviewers, understand attached media or certify artistic quality.
  Existing game verification below is historical, not retroactively gate-approved.

## Mossbell and Bellshade example

Added a host-owned two-world twilight example at `examples/mossbell/`. The complete
desktop and mobile journey crosses the town bridge, enters Bellshade, crosses its
log, receives a seed at the spring, returns to town, plants the seed and restores
the resulting bloom after reload. Sound begins on a gesture and uses original Web
Audio synthesis; no recorded samples are represented as natural ambience.

- `tests/mossbell-browser.mjs` passed 33 checks across desktop 1440x960 and mobile
  390x844: movement, touch D-pad, routes, collision, two-way transitions, story,
  persistence, animation, pause, audio signal/controls and browser errors. It kept
  screenshots, video and town/forest WebM mix captures under
  `test-results/mossbell/playtest-v4/`.
- Actual-scene assembly checks passed 15/15 town and 12/12 forest assertions.
  The environment lab desktop/mobile journey also passed with no page errors;
  the generated-layered workflow fixture passed animation loop/pause and assembly.
- Independent static review accepted the forest-material, phone-arrival and mobile
  overview repairs. Remaining visual limits are broad angular forest paths,
  repeated conifers and a subtle ending bloom at full-map desktop scale.
- Frame timing was approximately 16.7ms median and 16.8-16.9ms p95 in all four
  desktop/mobile-town/forest samples, essentially matching the 16.7/16.9ms blank
  baseline. Browser: Chrome 152, ANGLE/D3D11 on Radeon RX 9070 XT; mobile is Chrome
  emulation on that desktop GPU, not physical phone hardware.
- Automated checks establish a non-silent mix, attenuation state and audio control
  behavior. Human listening was unavailable, so subjective mix quality and speaker
  playback remain unapproved.

## Current: near-bank wall anchor

Reproduced the user's wall-through-torso image at `(4,9)`, ground0, facing NE,
idle with route none. `bankNear` placed its image one row behind its declared
entity using offset `(-32,-16)`. Corrected all near-bank instances to row8,
removed the image offset, and declared the true 16px height. Projected artwork
coordinates are preserved; depth footprints now lie behind the walking row.
No renderer or collision-rule change was needed. The assembly skill now warns
that visual offsets do not translate spatial metadata.

Added representative wall contacts/origins to the host assembly plan. The
baseline fails those checks with a one-row (35.777px projected) mismatch.
Evidence is kept separately under `test-results/willow-quay/bank-repair/`.

- Final actual-scene assembly check passed; sampled wall contacts have 0px error.
  All eleven near-bank image origins are mathematically unchanged. The same
  expectations reject the saved baseline; `assembly-results.json` retains both.
- Focused real-host browser checks passed: desktop `(4,9)` from both directions,
  walking the bank to `(1,9)`, and the other section at `(10,9)`; mobile `(4,9)`.
  All captures prove exact ground0 idle poses and were visually inspected against
  the baseline; no page errors. Desktop rerun and first-run mobile are separate
  reports. An optional mid-walk capture missed the short walking state and timed
  out; that instrumentation failure is retained, and no frozen midframe approval
  is claimed. `tests/quay-bank-depth.mjs` now uses completed physical approaches.
- `npm run check` passed (22 boundaries and strict TypeScript).
- `npx vite build --config vite.demo.config.ts` passed for all four hosts;
  the existing shared chunk-size warning remains. No broad engine suites rerun.

## Previous: foreground actors at raised bridge approaches

The user screenshot exposed actor-head clipping after arrival on Weidenkai's
south step `(7,10)`. Per-floor containers forced the entire upper bridge over
foreground ground actors and lamps. `src/view.ts` now shares a painter order
across floors, using overlapping screen bounds and declared footprint/height
volumes, with stable contact/footprint fallback for ambiguous relationships.
Cutaway visibility remains floor-specific. Flat water and stone decorations in
the host now declare their heights explicitly; walkability and step heights are
unchanged. The assembly skill now requires settled access-pose checks and
declared depth heights for nonblocking art.

- `node tests/bridge-occlusion.mjs` passed: both real 16px step approaches expose
  all 704 actor pixels and all 640 foreground lamp pixels. Deck support,
  underpass occlusion, ground cutaway, and exact image restoration also passed.
- `node tests/footprint-depth.mjs` passed: both house approaches preserve all
  768 actor pixels and identical final canvas images. Both depth regressions
  are now included in `npm run test:browser` (the broad runner was not rerun).
- `node tests/environment-lab-browser.mjs`: desktop and mobile passed with zero
  page errors, including crossing, underpass, cutaway, pause and restart.
- Quay desktop/mobile journeys passed on the final source with zero page errors;
  the first desktop attempt was interrupted by HMR and is retained. Inspection
  caught a mislabeled north-step capture (the actor had continued onto the deck).
  The focused `--north-only` rerun now proves exact `(7,5)`, ground, 16px, idle,
  route none, before/after zoom. South `(7,10)` and both mobile step poses were
  already correct. Corrected screenshots were visually inspected. See
  `desktop-rerun-results.json`, `results.json` (mobile), and
  `north-rerun-results.json` under `test-results/willow-quay/bridge-repair/`;
  these are separate runs, not a claimed single uninterrupted green run.
- `npm run build` passed: 22 module boundaries, strict types, library, four host
  HTML entries and declarations. Existing shared browser chunk warning remains.

Pixel evidence: `test-results/bridge-occlusion/` and
`test-results/footprint-depth/`. Real-asset stair screenshots and the independent
Quay playtest are recorded under `test-results/willow-quay/bridge-repair/`.
Read-only review found no further concrete ordering/lifecycle defect in these
scenes. The current pair scan is O(n²) per invalidated render; large maps require
spatial pruning/caching before this can be considered scalable. Unsplit
intersecting art and arbitrary curved geometry remain outside this guarantee.

## Previous: Weidenkai generated-art district

Added `examples/willow-quay/`: two reference-matched generated houses, generated
willow, shared-material paving/stonework, planted borders and a playable canal
crossing. New sources/prompts, rejected mask candidate, measured art contract,
assembly plan and processing provenance travel with the host. Details and scope
are in [WILLOW_QUAY.md](docs/WILLOW_QUAY.md).

- Final `node tests/quay-browser.mjs`: **2/2 desktop/mobile journeys in one fresh
  run**, zero page errors. Destination walking, both bridge directions on the
  actual upper floor, house/water blocking, pause, touch D-pad, jump and zoom.
  Routes exclude all six ground abutment cells. Screenshots inspected, including
  actor in front of the house from both approach axes and behind it.
- House and reference-actor art metadata passed `check-art.mjs`. Actual scene
  bindings passed `checkAssembly`: measured foundation contacts, blocked cells,
  solid building/trunk heights, exact bridge paths and rear-house reachability.
- Scoped renderer regression `node tests/footprint-depth.mjs` reproduces the
  original equal-depth failure: one approach exposed only 248 of 768 actor pixels.
  The bounded footprint tie-break shows all 768 from both approaches with identical
  final canvas images. It changes `src/view.ts` without game-specific branches.
- `npm run build` passed after the fix: **22 source boundaries**, strict
  TypeScript, library, **four host HTML entries** and declarations. Existing
  >500kB shared browser chunk warning remains; broad older suites were not rerun.
- Fresh production-build load checks for Weidenkai and Sunflower passed with no
  page errors or missing asset responses; final screenshots retained.

The final independent report is `test-results/willow-quay/playtest/final-results.json`
(source `post-depth-fix-results.json`) and its adjacent `README.md`. Previous
failed screenshots/results remain under the same directory. Other evidence:
`test-results/willow-quay/{art-results,assembly-results,production}.json` and
`test-results/footprint-depth/`.

Three concrete findings changed the result: willow/bridge cross-floor overlap
avoided by composition; insufficient bridge-end headroom filled by nonwalkable
abutments; approach-dependent actor/house depth tie fixed in the renderer. This
does not establish arbitrary cross-floor sorting or general walking-ceiling
collision. Bookbinder mask halo, repeated materials and simple slab-bridge art
remain documented. No building interiors, curved arch collision or simulated fluid.

## Previous: autotiling and generated-material bed assembly

Added headless `autotiling.ts` with cardinal16/blob47 masks, family/floor/elevation
boundaries, deterministic variant choices and explicit missing-catalog diagnostics.
Sunflower uses the common cardinal resolver with its existing art. A separate
editable `examples/autotile-lab/` uses 47 bed variants assembled from one actual
generated material sheet. The portable `consistent-tileset-authoring` skill and
assembler document the source, fixed geometry and authoring dependencies.

- **4 grouped core tests** passed: legacy mask compatibility, all 256 neighborhoods
  reduced to 47 states, concave/diagonal topology, floor/family/height boundaries,
  deterministic choices and rejected inputs. Boundary checker self-tests: **8**.
- **2/2 desktop/mobile browser journeys** via `node tests/autotile-browser.mjs`:
  closed ring blocks walking; removal opens a route into its center; actor-cell
  painting is rejected; preset shapes render; mobile held touch moves the actor;
  no horizontal overflow or page errors. Screenshots inspected. An initial test
  incorrectly used an instantaneous tap for a held D-pad; corrected to held touch.
- Sunflower default-load smoke passed with no page errors after mask migration;
  screenshot retained. This was not a repeat of the full Sunflower gameplay suite.
- Material preparation produced 47 distinct variants and a byte-identical atlas
  on repeat in the same environment. Strict opacity correctly rejects the actual
  source's partial alpha. The explicit recipe normalization is material-only.
- `npm run build` passed: **22 source boundaries**, strict TypeScript, library,
  **three HTML host entries** and declarations. Existing shared browser chunk
  warning (>500 kB) remains. Unrelated runtime suites were not rerun.
- Skill `quick_validate.py` passed. Independent read-only review found no blocking
  API, portability or documentation issues; this was not a fresh-agent skill trial.
- npm package dry run includes the skill, recipe, assembler, API guide and public
  autotiling declarations.

Evidence: `test-results/autotile-lab/`, `test-results/autotile-preparation/` and
`test-results/autotile-material-alpha/`. Source, exact prompt, recipe, source hash
and emitted metadata are retained in `examples/autotile-lab/art/`.

Visual review found noisy sparse source sampling; shared 32px material prefiltering
reduced it. Mirrored repetition and existing terrain outlines remain visible.
The actor is a built-in scale marker. This validates compatible bed assembly,
not final production art or a universal multi-terrain/bridge generator. See
[AUTOTILING.md](docs/AUTOTILING.md) for API, reproduction and scope.

## Previous: actual generated environment assets

The SVG-only exercise below did not satisfy generated-asset validation. The lab
now defaults to five used generated PNG sources: fountain, river, bridge kit,
replacement rail and splash sheet. Two opaque checkerboard extraction outputs
are retained as rejected candidates. Exact prompts and hashes live under
`examples/environment-lab/art/generated/`. No engine API/source changes.

- Compared raw, registered and layered versions of this generated pack in the
  actual renderer. Raw river placement fails as expected; measured windows fix
  its 4px/84px source offsets. Whole fountain frames retain stone texture drift;
  the final version binds a fixed generated base and animated splash layers.
- Final `node --experimental-strip-types tests/environment-skills.mjs
  generated-layered` passed declared fountain/river/pier/rail contacts, actual
  bridge/underpass traversal, center-stone jump stress, frame/pixel progression,
  pause and loop return. Negative anchor/solid-bridge probes were rejected.
- `node tests/environment-lab-browser.mjs`: **2/2 desktop/mobile journeys**, zero
  page errors; screenshots inspected after final rail joins/splash placement.
- `npm run build`: **21 source boundaries**, TypeScript, library, both host pages
  and declarations passed; existing large shared browser chunk warning remains.
  Both modified skills passed `quick_validate.py`. Unrelated suites were not rerun.

The retained small rail/projection residuals and conservative grid collision are
documented. Final fountain jets remain static; generated splash rings and river
frames animate. This is not a claim of perfectly seamless flow, a fully animated
jet or exact arch collision. See [GENERATED_ENVIRONMENT_TRIAL.md](docs/GENERATED_ENVIRONMENT_TRIAL.md)
for evidence paths, independent source measurements, comparison scope and limits.

## Previous: animated environment and multi-tile assembly skills

Added two portable skills, three independently exercised experimental workflows,
an assembly-plan checker, deterministic SVG calibration atlas and a separate
`examples/environment-lab/` host. Runtime public API and engine source are unchanged.
The lab retains the original three outputs and defaults to a refined scene with
separate basin/central-stone collision. Guides route future agents to the skills.

Focused evidence:

- Three independent trial scenes passed common source-contact, occupancy,
  bridge/underpass and rendered loop/pause checks. B/C failed the additional
  four-cell jump-through-stone stress probe; these findings remain in the
  comparison, alongside the ambiguous source label that contributed to them.
- The refined scene passed `node --experimental-strip-types
  tests/environment-skills.mjs accepted`: actual bridge/underpass routes,
  pixel advancement/pause/full-loop return, solid center and jump stress.
  Wrong-anchor and monolithic-bridge negative probes were rejected.
- A fresh agent applying the final skills to the withheld raw challenge produced
  separate low/high fountain solids and valid bridge traversal on its first
  submission. Scene validation and its assembly plan passed. Its scene was not
  separately browser-certified; rendered checks above concern the refined host.
- **2/2 desktop/mobile host journeys**, zero page errors, via
  `node tests/environment-lab-browser.mjs`: cross, walk beneath, pause/resume,
  inspect/reset and no horizontal overflow; mobile also taps Jump. Screenshots
  were inspected. The host's initially off-screen jump button was corrected.
- `check-assembly.mjs` CLI passed against the bundled example's assembly plan
  and scene. Five skill entrypoints passed `quick_validate.py`; npm package dry
  run includes both skills, all three variants, checker and calibration assets.
- `npm run build` passed: **21 module boundaries**, strict TypeScript, library,
  both demo entries and declarations. Existing >500 kB shared browser chunk
  warning remains. Full older gameplay suites were not rerun for this host/skill
  addition.

Evidence is under `test-results/environment-skill-comparison/` and
`test-results/environment-lab/`; durable method, comparison, input hashes and
reproduction commands are in [ENVIRONMENT_SKILL_COMPARISON.md](docs/ENVIRONMENT_SKILL_COMPARISON.md).
The three baseline outputs intentionally preserve their differences. These SVGs
prove a functional calibration fixture, not the supplied references' production
art quality, directional river flow or curved arch collision. Current floor
ordering and rectangular-body approximations remain documented limitations.

## Previous: inventory and local game checkpoints

New headless `inventory.ts` and `saves.ts` modules expose quantity/capacity handling
and validated versioned scene + host-state records through root/core. Game item
definitions and checkpoint rules live in `demo/garden-progress.ts` and the host.
Sunflower now awards flower items and stores its remaining world, original restart
scene, and inventory together. Reload resumes the local checkpoint. Save/Continue
buttons support explicit use; Restart replaces the checkpoint with the reset game.
Other presets do not overwrite the Sunflower slot. Agent guides explain the APIs
and proportional verification for incremental modules.

Verification was deliberately limited to this change:

- **3/3 focused module tests** (`node --experimental-strip-types --test tests/progress.test.ts`):
  inventory updates/limits and atomic restore; save roundtrip and invalid records;
  storage failures preserving the prior checkpoint.
- **3/3 browser journeys** (`node tests/progress-browser.mjs`, development server
  on 4175), zero browser errors: desktop collection/reload/cross-scene Continue/
  Restart; corrupt-save and refused-storage recovery; mobile touch collection and
  reload without horizontal overflow. Report and desktop/mobile screenshots:
  `test-results/progress-demo/`. Both rendered views were inspected.
- `npm run build`: **21 module boundaries**, strict TypeScript, library/demo builds
  and declarations passed. The existing >500 kB demo chunk warning remains.

The full older movement, jump, rendering and interaction suites were not rerun
for this isolated addition. `progress-browser` is included in the full browser
runner for future release runs. Saves are local to the browser origin, use one
Sunflower slot, and restore committed cells rather than transient actions/flights.
Cloud sync, schema migration, equipment and crafting are outside this slice.

## Previous milestone: reusable interactions and optional debug overlay

`createInteractions` composes public methods to approach a reachable footprint
edge, face the target, prepare, apply one synchronous host effect, and recover.
Default reach requires the same floor and equal feet heights; hosts can explicitly
configure vertical tolerance. Timing follows simulation pause. Sunflower supplies
a flower-basket effect and existing grounded gesture clips. Other demos retain
their arrival-based collection. `createDebugOverlay` reads detached public
snapshots for grid/footprints/routes/origins and actual sprite clip/frame/facing.
Both helpers have per-instance teardown. Guides and the bundled directional
sprite reference document the public APIs and ownership boundaries.

Executed against the current source:

- `npm test`: **68/68** headless tests, including **31 interaction tests**.
- `npm run test:browser`: **179/179** Chromium checks across runtime (22),
  levels/input (63), jump/projectiles (48), art (23), and interactions/debug (23).
  Zero page errors. The new suite also checks runtime error events. Evidence:
  `test-results/interactions-api/results.json` and the existing four API folders.
- `npm run build`: strict TypeScript, **19 module boundaries**, library, demo,
  and declarations pass. The demo still emits the known >500 kB chunk warning.
- `npm pack --dry-run --json`: new interaction/debug declarations and guides,
  AGENTS, and updated directional reference are included. Relative documentation
  links pass for seven updated guide/reference files.
- Independent code review reproduced and then verified fixes for held-input
  release after cancellation, unreachable vertical targets, reentrant effect
  result reporting, and destruction during a camera callback in scene loading.
  Native keyboard and D-pad release now finish one step without continued drift;
  camera-triggered destroyed/superseded loads reject with `AbortError`.
- Independent native demo playtest: **30 checks passed** at 1280×900 desktop and
  390×844 touch emulation, with no browser errors. It covered all three visible
  flower-head clicks, a visible-head touch, repeated clicks, pause/clip freezing,
  cancellation before and after the effect, input interruption/release, completion,
  restart, debug camera/resize alignment and pointer passthrough, mobile HUD spacing,
  and W+Space landing on the 72-pixel bridge in scene 04. Screenshots and replay:
  `test-results/interaction-demo/`; exact results in `report.json`.
  The final replay includes the control reorder that keeps desktop Pause, Cancel,
  progress, and basket alongside the map. The optional debug readout remains lower
  in the sidebar and requires scrolling. Touch emulation does not certify hardware.
- The built `/core` bundle imports `createInteractions` and `WorldModel` in plain
  Node without a DOM or renderer initialization.

These checks concern the standalone runtime, not the legacy VPS application.
The demo gesture reuses existing art rather than supplying newly drawn picking
poses. The debug grid is capped at 2,000 tiles, image bounds include transparent
margins, and route readouts are current plans rather than motion history.

## Previous milestone: click/tap routes follow tile axes

Sunflower (including its calibration variant) and Woodland mistakenly opted into
diagonal click paths. Their scene definitions now use `diagonal: false`, matching
the other built-in demos. The engine's existing configurable routing API and
direct-input behavior are unchanged. Imported scenes retain their own setting.
AGENTS and the demo/authoring guides record the tile-axis routing policy.

Strict TypeScript, 17 module boundaries, and library/demo/declaration builds pass.
The actual seven scene factories were checked through WorldModel: all 403
reachable destination paths from their respective spawn points contain only
single-axis steps (2,139 total steps, including 22 floor transitions). Evidence:
`test-results/click-routing-api.json`. This is one returned path per destination,
not every possible start/destination pair.

Independent native browser checks passed at 1280×900 and 390×844: Sunflower mouse
and touch `(2,6) -> (6,4)`, mouse detour around furniture `(6,4) -> (4,2)`, Art
calibration `(2,6) -> (6,4)`, and Woodland `(4,6) -> (5,3)`. Visible interpolated
Traveler coordinates showed no motion with both coordinates fractional; recorded
cell transitions followed the axes. All destinations were reached, with zero
page errors. Paths, poses, screenshots, and report are retained under
`test-results/click-routing/`. No broader gameplay or VPS acceptance is claimed.

## Previous milestone: directional poses and deterministic spritesheets

The portable `skills/directional-sprite-authoring/` skill now covers approved
turnarounds, the exact WASD/eight-direction mapping, reference-guided action
phases, common roots and canvas sizes, and explicit runtime clip binding. It
includes a Pillow packer and instructions distinguishing automatic idle/walk/jump
from host-driven attack/cast/interact actions. AGENTS, README, the art pipeline,
and the generation skill link to it. All six new skill files ship in npm pack
dry-run output; frontmatter validation and relative-link checks passed.

The WaveSpeed helper now supports `bytedance/seedream-v5.0-pro/edit` with ordered
HTTPS references and safe resume. Its 28 mocked API tests passed, including the
five new edit/reference cases. No paid generation or image-edit request was made,
so Seedream pose quality and temporal consistency are not verified here.

The sheet packer passed 11 offline tests for pixel preservation, transparent
gutters, repeated frame order, dimensions and alpha, duplicate/missing clips,
allocation limits, custom actions, deterministic output, and refusing overwrite.
A synthetic 16-clip/32-frame sheet also passed the actual runtime asset validator:
all four tile-axis vectors selected the correct idle/walk/jump clip through the
real direction/resolver functions, and attack remained a non-looping host action.
This is layout/mapping evidence, not visible character-facing or gameplay proof.
Evidence: `test-results/pose-authoring/`. The cross-check uses Node's
`--experimental-transform-types` because sprites.ts contains parameter properties;
the initial strip-only invocation failed before running assertions.

Independent read-only review found no material mismatch with runtime APIs. It
confirmed the documented limitation that undeclared directions can use the first
supplied general fallback; four views do not establish eight-way visual coverage.
No engine behavior, existing game sprite, or scene was changed in this task.

Reproduce from Runtime:

```sh
npm run test:asset-generation
uv run --python 3.12 --with "Pillow==11.3.0" python -B skills/directional-sprite-authoring/tests/test_pack_sprites.py
```

## Previous milestone: portable generation and background-removal skill

`skills/game-asset-generation/` now provides WaveSpeed Seedream generation and
background-remover instructions, a dependency-free resumable Node API client,
version/model-pinned local CPU rembg commands, and a Pillow alpha inspector.
The existing integration skill, AGENTS, README, and art pipeline link to it.
Both skills pass frontmatter validation and all seven new skill files appear in
the npm package dry run. No runtime dependencies, engine code, or game images
were changed for this addition.

The API helper passed 23 offline mocked tests, including ID persistence before
polling, terminal failures, timeout/resume without POST, bounded GET retries,
ambiguous submission without duplicate charges, input validation, key redaction,
Windows UTF-8 BOM files, and processing responses with code 5004. No live or paid
WaveSpeed requests were made. API schemas were checked against official model
documentation; real provider generation and mask quality remain unverified.

Four alpha-inspection tests passed. The actual old RGB checkerboard candidate
was rejected with exit 1; the shipped RGBA foliage passed the numeric cutout check
and retained its original hash/dimensions. Light/dark/magenta boards were produced
and the accepted board inspected. These checks establish decoded alpha, not
perfect segmentation. Evidence: `test-results/asset-generation-alpha/`.

A bounded local rembg 2.0.75 / u2netp trial installed 84 CPU dependencies but
produced no PNG or model-download log before its owned process tree was stopped
at 4m45s. The internal cause is unconfirmed. Local output quality is therefore
unverified, not failed visual acceptance; no game asset was replaced. See
`test-results/asset-generation-local/results.txt`. The documented local path is
supported upstream, but not demonstrated end-to-end in this environment.

An independent read-only forward trial prepared the provider/local command flow
without a GPT tool. It exposed missing download examples, provenance scaffolding,
target-scale handoff, and an ambiguous resume example; the references were
updated. This trial did not call a provider or execute local segmentation.

Reproduce helper checks from Runtime:

```sh
npm run test:asset-generation
uv run --python 3.12 --with "Pillow==11.3.0" python -B skills/game-asset-generation/tests/test_inspect_alpha.py
```

## Previous milestone: Sunflower repair and skill reflection

The host now separates generated foliage from 16 authored planter-base adjacency
variants, adjusts furniture scale and selected ground anchors, and includes the
small playable **07 — Art calibration** scene. Four local PNGs are used. Engine
source and its movement/jump contracts are unchanged.

The current art sidecar passes for 28 entries at 2 px ground / 4 px height
tolerances. The preserved original planter fails with 5 errors at those same
tolerances. This is retrospective metadata calibration: inferred support grids
and measured-result height references are not independent proof of projection
or intended proportions. Four idle facings are measured; other animation frames,
fences, and foliage are not covered by that geometric result.

The independent GUI round passed all five frozen checks: rigid joins on both
axes/corner, player/prop scale, depth and visible motion, collection/restart/scene
round-trip, and mobile controls. The 390/719/720/721/1280 viewport probes found
no configured clipping, control-occlusion, or viewport-overflow failures. Real
simultaneous touch movement/jump and release passed. Strict evidence validation
and the acceptance gate both returned success. Retained evidence is under
`test-results/sunflower-calibration-gui/evidence/round-1/`, with the frozen goal,
integrity manifest, and before image in its parent QA folder. This is standalone
local Runtime acceptance, not VPS/deployment validation. Small-text, contrast,
and style observations remain advisory; this does not certify every art detail
or every animation contact. Furniture remains a blocked composite, with canopy
clearance limits documented in the pack's measurement notes.

For the repair, strict TypeScript, 17 module boundaries, the library/demo/type
build, and 37 core tests passed. A production preview loaded all four PNGs with
HTTP 200, exercised northeast W movement and export, and had no page errors;
see `test-results/sunflower-production.json`. The temporary preview was stopped.
The earlier 156-check API/browser suite was not rerun for this host-art repair.
The temporary `sunflower-contract-check.mjs` result compared selected scene
definitions, but skipped terrain anchors and served-image hash binding; do not
describe it as complete host binding verification.

The [task reflection](demo/art/pixel-cafe/TASK_REFLECTION.md) led to focused skill
updates: independently chosen proportion targets, decoded alpha preflight,
explicit evidence classes, coupled furniture dimensions, complete host binding
guidance, and exact asset/state coverage. An independent instruction review found
no material issues. Skill frontmatter validation and all 23 checker tests passed
again; npm pack dry-run includes all seven skill files. No checker/schema behavior
changed in the reflection pass, and no new behavioral trial of the revised
instructions is claimed.

## Previous milestone: portable art calibration skill

`skills/isometric-art-integration/` now contains the skill, authoring contract,
visual acceptance procedure, PNG metadata checker, HTML overlay board, and
23 focused checker tests. All 23 passed, including valid geometry, projection
mismatch, rigid footprint spill, incorrect heights, nonuniform prop scaling,
source hash drift, malformed metadata, and CLI exit status. Skill frontmatter
validation passed. Package dry-run inspection includes the entire skill and its
tools; `AGENTS.md`, README, and the art pipeline link to it. The starter contract
was validated against its documented synthetic atlas geometry.

An independent agent applied the skill to the existing planter, found a measured
ground containment failure, and kept gameplay/delivery unverified. That trial
exposed Windows UTF-8 BOM handling and first-use contract gaps; the checker now
accepts a leading BOM and the skill includes a starter JSON. Direct inverse
projection checks measured footprint spill separately from chosen ground-point
correspondences. Regression tests cover these cases and allowed measurement error.

The preview was exercised in Chromium with a diagnostic measurement of the
existing purple planter. It rejected the ground mismatch, decoded the PNG,
displayed the footprint/contact overlays, and responded to shared zoom and
overlay toggling with zero page errors. Desktop and mobile-width captures are
retained at `test-results/art-skill-calibration.png` and
`test-results/art-skill-calibration-mobile.png`; the diagnostic contract, HTML,
and browser result are alongside them. Those approximate annotations are a
failure probe, not an approved production asset contract. An initial preview
smoke exposed an inline JavaScript escaping error; it was fixed and the browser
check rerun successfully.

The checker validates supplied annotations and PNG metadata, not actual physical
landmark recognition or pixel decoding. The browser board aids visual inspection;
host-scene joins, animation, occlusion, and gameplay still need real playtests.
No engine, game scene, or artwork was changed for this skill addition.

## Previous example: Sunflower courtyard — visual acceptance failed

The user identified misaligned/protruding planter bases and inconsistent player
versus furniture proportions. Source inspection confirmed uncalibrated ground
geometry and independent image-width scaling. The build and collision results
below remain valid within their scope, but do not establish visual compatibility.
That original version was not an approved art reference. Repair and fresh review
were outstanding at this milestone; see the current result above. The original
GUI playtest was interrupted before completion.

The default demo now uses a 9 × 9 courtyard, two local generated PNG atlases,
32 texture definitions, and 12 gardener clips. New host scene content and UI
integration use the existing art/runtime APIs; no engine source changed.

Strict TypeScript and all 17 module boundaries passed. All 37 core tests and
the library/demo/declaration build passed. The decoded source-frame checks found
all 32 rectangles inside their 1254 × 1254 atlases; all three collectible cells
are reachable and blocking footprints do not overlap.

A production preview on port 4193 loaded both emitted PNGs with HTTP 200 and
no page errors. Native W movement increased the column while keeping the row,
and a scene export completed. Evidence: `test-results/cafe-production.json`,
`cafe-production-scene.json`, and `cafe-production.png`. The temporary preview
server was stopped afterward. The first smoke attempt assumed a short timed
key hold would always yield exactly one step; it yielded two under load. The
check now verifies the intended axis without assuming wall-clock precision;
the initial result is retained as `cafe-production-initial.json`.

Both PNGs total approximately 3.0 MB. Vite retains its JavaScript bundle-size
advisory (approximately 603 kB). Generated poses have small authored asymmetries;
this is a playable art proof, with manually inspected frame metadata. The earlier
156-check runtime browser suite below was not rerun for this host-content change.

## Previous milestone: sprite and texture module

Strict TypeScript, all 17 module import boundaries, and library/demo production
builds passed. The headless suite passed 37 tests; the combined Chromium run
passed 156 checks (22 API/pixel, 63 levels/input, 48 jump/projectile, 23 art), with
zero page errors. Browser suites used the running standalone server on 4175.

The independent visible playtest passed all six behavior checks and strict
evidence validation/gating. It verified the art scene, facing and animation,
ground contact and tree occlusion, mobile multitouch movement/jump, scene
round-trip and invalid-asset recovery, plus legacy collection, stacked floors,
stairs, bridge landing and low-bolt dodging. All five 390/719/720/721/1280-pixel
viewport probes passed configured overflow, clipping and control-occlusion gates.
Small-text and contrast findings remain advisory. The sealed 91 screenshots,
335 action rows, report and gate are retained at
`test-results/art-gui/evidence/round-1/`.

The art checks cover exact atlas crops, nearest sampling, contact anchors,
width/scale/tint/offset, idle/walk/jump and native directional facing, pause,
non-loop playback and replay, static/manual overrides, deduplicated image loads,
independent-instance resource ownership, failed and superseded scene loads,
decoded-frame bounds, terrain masks, stable texture variants, and independent
physical dimensions. Review found and fixed reversed facing on a cancellation
snap; regression checks now preserve northeast facing after both a partial walk
stop and a blocked-flight rollback. Report: `test-results/art-api/results.json`.

An independent source copy matched all 17 runtime source hashes. Its build,
37 core tests, strict public root/core/art declaration consumer, and Node imports
of the built headless art/core entries passed. Its production preview loaded the
emitted 37,345-byte SVG with HTTP 200, rendered and moved the woodland traveler,
exported 39 textures and 12 animation clips, and rendered a mobile canvas without
page errors or failed requests. This was a production artifact smoke check; the
full browser suites ran in the primary checkout. The temporary preview server
was stopped. Report: `test-results/portability-art.json`.

The new art guide's TypeScript examples compile against public declarations.
Package dry-run inspection confirms the art entry/declarations, `AGENTS.md`, and
art pipeline guide are included. Reports: `test-results/art-package.json` and
the retained `test-results/art-guide-consumer.mts` example. The woodland atlas
is local authored vector art; no network art service is required. The production
demo retains Vite's bundle-size advisory (approximately 599 kB JavaScript).

## Previous milestone: agent-facing framework contract

The portable `AGENTS.md`, architecture guide, and new-game recipe describe module ownership, public extension points, lifecycle, coordinate invariants, and validation. The recipe's combined TypeScript example was checked against public package declarations; links and API names were verified. `npm pack --dry-run --json` confirmed that `AGENTS.md` and both guides ship alongside the built exports.

`npm run check` now runs the static module-boundary checker before strict TypeScript. All 15 source modules pass; eight positive/negative checker probes also pass. The checker covers imports, re-exports, and literal dynamic/type imports. It prevents classified core modules from importing rendering/orchestration and prevents source modules from importing host-game or legacy code; it does not prove the absence of arbitrary DOM usage or validate gameplay semantics. No simulation or demo behavior changed for this documentation/tooling step.

## Previous milestone: jumping and flying projectile traps

Strict TypeScript, the library/demo production build, 28 core tests, and all 133 Chromium checks passed (22 existing API/pixel, 63 levels/input, 48 jump/projectile). The final combined browser run used `RUNTIME_QA_URL=http://127.0.0.1:4175` because the default isolated port 4176 was occupied; the initial default invocation failed before tests started. All three suites reported zero page errors. Jump results and screenshots are in `test-results/jump-api/`.

The exact reported route in scene 04, ground `(3,6)` toward `(3,5)`, was compared with adjacent stairs present and removed, using both native A+Space and API input. All four cases landed on the 54-pixel step in one jump, with peak at most 84 pixels. That target is within the configured jump range; no neighbor-dependent increase was reproduced. Separate fixtures reject a 144-pixel landing from ground even beside a reachable 72-pixel platform, while allowing a second jump after landing at 72.

Regression fixes cover continuous mid-walk takeoff, negative-height airborne rendering, correct destination floor rendering after touchdown, and upper-platform underside thickness matching its visible geometry. Tests also exercise low-shot avoidance, fast swept projectile hits at 30/60/120 Hz, first raised landing selection, blocked landings, ceiling collisions, pause/load/destruction, and two-finger D-pad plus Jump input.

The separate folder verification passed again with all 15 runtime source hashes matching. The copied package built successfully, passed 28 core and 133 Chromium tests, resolved root/core TypeScript exports including the jump/projectile APIs, and executed the built core in Node without a DOM. Existing installed dependencies were reused only after an exact lockfile match; this final pass did not repeat `npm ci`. Its dedicated browser server used port 4180 and was stopped after testing. Evidence: `test-results/portability-jump.json`.

The independent visible GUI playtest passed all 10 required checks and strict evidence validation/gating. It captured a raised jump peak of 84 pixels and stable 72-pixel bridge landing, a nearest-platform landing, blocked low ceiling, desktop/mobile idle-hit versus successful dodge, and two-finger directional cross plus Jump. The five 390/719/720/721/1280-pixel probes had no configured overflow, clipping, or control-occlusion failures. Small-text/contrast/style findings remain advisory. Its sealed report, 67 screenshots, action log, probes and gate are retained in `test-results/jump-gui/evidence/round-1/`.

## Previous milestone: stacked floors, tile-axis WASD, and mobile directional pad

WASD and arrow keys follow tile axes: W northeast, D southeast, S southwest, A northwest. The mobile demo mounts a four-button cross at the bottom right of its reserved game HUD. The optional joystick API remains available separately.

| Check | Result |
| --- | --- |
| Strict TypeScript and library/demo production builds | Passed |
| Core tests, including stacked floors, stairs and independent occupancy | 28 passed |
| Existing Chromium API and pixel regressions | 22 passed; zero page errors |
| Levels, native keyboard, joystick and directional-pad browser checks | 63 passed; zero page errors |
| Independent current visible GUI playtest | 7/7 passed; strict validator and gate passed |
| Mobile/desktop and breakpoint layout probes | 390, 719, 720, 721, 1280px passed selected gates |
| Fresh folder install, build, core tests and both browser suites | Passed; all 14 runtime source hashes match |
| Built package declaration consumer and Node core import | Passed, including `createDpad` and floor types |

The new tests cover both stair directions, floor cutaways, interpolated height, floor-specific obstacles, scene round-trips, focused keyboard ownership, editable controls, simultaneous D-pad touches, release/cancellation/lost capture, pause, scene replacement and destruction. Direction fixtures preserve the original `Client/engine/move-handler.js` mapping, including arrow aliases and all adjacent key combinations. Regression checks reproduce and prevent stale actor layers after stair descent, disappearing actors when changing cutaway during a paused ascent, and reentrant resume leaving the ticker stopped.

Repeatable reports for this control/floor milestone are `test-results/browser-api/results.json`, `test-results/levels-api/results.json`, and `test-results/portability-levels.json`. The sealed visible report, screenshots and gate are retained at `test-results/controls-gui/evidence/round-1/`. Earlier stair-render failures are retained under `test-results/levels-before-repair/`. Browser tests run on their own local Vite server and do not certify or deploy the legacy multiplayer application. Subsequent jump/projectile work requires separate verification.

## Historical: initial extraction

The standalone TypeScript package was verified independently of the original multiplayer application.

| Check | Result |
| --- | --- |
| Strict TypeScript check and library/demo production builds | Passed |
| Core unit tests | 13 passed |
| Real Chromium runtime API/pixel tests | 22 passed; zero page errors |
| Independent visible demo playtest | 7 required behaviors passed |
| Desktop/mobile and breakpoint probes | 390, 719, 720, 721, 1280px; selected gates passed |
| Final GUI evidence validation and regression gate | Passed, round 3 |
| Fresh install/build/tests outside this monorepo | Passed; final runtime source hashes match |
| Package consumer TypeScript checks | Root and `/core` exports resolve; core imports in Node |

## Reproduce

```sh
npm ci
npm run check
npm test
npx playwright install chromium
npm run test:browser
npm run build
npm run dev
```

The demo runs at `http://127.0.0.1:4175`. Browser API tests own a separate temporary Vite process on port 4176 and stop it afterward. They do not require a running development server. `RUNTIME_QA_URL` can instead target an already running standalone runtime development server.

The API tests cover isolated instances, asynchronous load cancellation/failure, replacement races, independent texture ownership, animation pixels, 30/60/120 Hz movement, pause/resume, dynamic blockers, serialization, camera picking, and destruction or scene replacement inside callbacks. A 24-position silhouette probe checks intermediate movement in both axes on flat and raised terrain.

The visible playtest exercised movement and collision, camera pan/zoom/fit, pause/resume/restart, both example scenes and collection, actual downloaded scene import, malformed-file recovery, and mobile tapping. Fresh diagnostic interactions found no application errors or failed requests.

## Evidence retained in this checkout

- `test-results/browser-api/results.json`: latest repeatable browser API run, with pixel captures.
- `test-results/before-flat-floor-repair/`: reproduced actor-clipping failure before correction.
- `test-results/portability.json`: independent copy/install/build/test result and matching source hashes.
- `test-results/gui/evidence/round-3/`: final report, gate, validator output, action log, diagnostics, and desktop/mobile screenshots.
- Earlier GUI rounds are preserved beside the final round. Round 1 had an incomplete protection manifest; a complete manifest was sealed before round 2. Final round 3 uses that unchanged complete manifest. No failing evidence was overwritten.

Generated evidence and build outputs are ignored by Git; test source and this verification record are part of the package folder.

## Limits

This is a source-derived runtime extraction with a new scene format; existing application world data needs conversion. It is not a deployment or end-to-end certification of the legacy VPS application. The original client/server files were not changed.

Depth sorting supports upright isometric sprites, terrain elevation, rectangular blocking footprints, and now stacked floors with explicit stair links and cutaway views. Arbitrary intersecting 3D geometry remains outside the model. The old combat, wearables, audio, multiplayer, scripting, and editor integrations are not ported. The demo uses original procedural shapes rather than the original asset library.

Small-text/contrast findings remain advisory in the demo's visual report. Vite reports a bundle-size advisory for the current demo's approximately 571 kB JavaScript bundle including Pixi; production compilation succeeds. Chromium's GPU-driver readback warnings are retained in diagnostic evidence.
