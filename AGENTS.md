# Working on Isometric Framework

This repository is a portable first slice of a framework for coding agents to build
isometric games. It is a standalone TypeScript package, with a playable reference
game in `demo/`. It is not the legacy multiplayer client or a complete editor.

## Start here

1. Read `README.md` for setup and `docs/RUNTIME_API.md` for public API usage.
2. Read `docs/ARCHITECTURE.md` before changing engine code.
3. For a new game, follow `docs/CREATE_GAME.md`. Before art or environment work,
   consult the [skill catalog](skills/README.md) and read the relevant `SKILL.md`
   files. For complete worlds or substantial visual refinement, start with
   [isometric-visual-loop](skills/isometric-visual-loop/SKILL.md) and select its
   specialists by feature. For focused work, use the matching specialist directly.
   Infer relevant skills from the request; the user need not name them. Do not run
   every skill for every task. Calibrate a small assembly, then finish the full scope.
4. Use `APP_GUIDE.md` for current demo behavior and `VERIFICATION.md` for executed
   checks and their limits. Inspect actual source when those records may be stale.

These instructions travel with the folder. Do not require the original repo's
backend, accounts, memory files, agent provider, or deployment environment.
Use the user's authorized coding tools and follow their current scope.

All seven main skills and their supporting files travel in copied folders and npm
packages. Read the linked `SKILL.md` directly if your agent does not automatically
discover repository-local skills; no global installation is required. Some authoring tools
need additional dependencies or an available provider; see the selected skill.

An installed package contains built exports, guides, and the skills, not this development
checkout. Consumers use the public API in their own application; engine changes
and the development commands below require the source folder.

## Keep example content out of new games by default

`demo/` and existing `examples/` hosts are optional implementation references,
not a default asset library or art direction. Establish the new game's visual
identity from the user's brief and supplied references before choosing artwork.
Do not inherit example sprites, atlases, palettes, characters, names, maps or
story content merely because they are available locally. This includes using
example images as generation references or fallback artwork.

Start with public API docs and the relevant skills. Inspect only the example
code needed to answer a concrete implementation question; do not bulk-read
example art directories or provenance records for an unrelated new game.
Transfer API patterns, not another host's imports, asset URLs or content defaults.
Keep the new host's manifests and artwork self-contained.

Reuse example content when the user requests that example, its style or its
assets, or when modifying that existing host. Record intentional asset reuse and
preserve provenance; do not describe reused sprites as newly generated artwork.
For a new game's technical calibration, use neutral built-in graphics until its
own artwork is ready. Preserve unrelated examples in the framework checkout.

## Art workflows and example guidance

Keep skill instructions and supporting references independent of named games and
historical trials. Put needed generalized examples inside the owning skill, with
illustrative inputs explicitly identified. Extract reusable technical lessons;
do not send a production agent to trial reports, screenshots or example artwork.
Historical comparison instructions belong under documentation, outside `skills/`.

Consult the example records below only for the relevant capability or trial.
Their artwork and visual decisions are not defaults for the current task.

For a new game, follow `docs/CREATE_GAME.md`. Calibrate with one small playable
assembly, then complete the scope requested by the user. A rich environment
requested in a short prompt must not be reduced to a tiny final demo. For
prompt-driven world creation, use
[isometric-visual-loop](skills/isometric-visual-loop/SKILL.md) to infer appropriate
effort, plan the whole environment and coordinate art, assemblies and animation.
For sprites, textures, or a new visual theme, read `docs/ART_PIPELINE.md` and
apply [isometric-art-integration](skills/isometric-art-integration/SKILL.md).
To generate raster assets or prepare transparent cutouts, use
[game-asset-generation](skills/game-asset-generation/SKILL.md): the project's
chosen Retro Diffusion MCP, WaveSpeed Seedream, or other available provider,
with a compatible removal workflow where needed. Preserve existing provider,
technique and spending decisions; tool availability does not select art direction.
This does not require a GPT ImageGen skill or put provider keys in the game.
For directional character frames and action poses, apply
[directional-sprite-authoring](skills/directional-sprite-authoring/SKILL.md).
For rivers, fountains and other scenery loops, use
[animated-environments](skills/animated-environments/SKILL.md). For large assets,
buildings or bridges, pair it with
[multi-tile-asset-assembly](skills/multi-tile-asset-assembly/SKILL.md): declare
surfaces, openings and solid heights before fitting artwork. The environment
lab under `examples/environment-lab/` now defaults to real generated PNGs and
preserves raw/registered/layered stages plus the earlier SVG fixtures. Read
[the generated trial](docs/GENERATED_ENVIRONMENT_TRIAL.md) for source failures,
measured corrections and remaining limits. Generated-asset requests require
actual generated outputs; the SVG fixture alone is not evidence for that task.
For connected beds, paths, walls or water, read [AUTOTILING.md](docs/AUTOTILING.md)
and apply [consistent-tileset-authoring](skills/consistent-tileset-authoring/SKILL.md).
Approve shared edge geometry on a strip, L and hollow patch before decorating.
The visual loop also handles reference-driven improvement, distinguishing
style references from exact replicas and keeping visual, gameplay and performance
verdicts separate. See the generated [autumn crossing trial](docs/AUTUMN_CROSSING.md).
The generated-material bed lab is at `examples/autotile-lab/`; its assembler
needs authoring-only Playwright/Chromium, while the resolver remains headless.
For a composed generated-art district, see `examples/willow-quay/` and
[its trial record](docs/WILLOW_QUAY.md): reference-guided houses, shared material
geometry, measured scale and a playable canal crossing. Its stair regression
covers shared cross-floor depth ordering; read the limits for unsplit overhangs
and inspect idle access poses. It does not provide interiors/arched collision.
Approve visible facings, then bind explicit clips; a sheet's row order does
not establish direction. Custom effects remain host-owned; use the reusable
[interaction controller](docs/INTERACTIONS.md) for approach and action timing.
Inspect [debug snapshots and overlays](docs/DEBUGGING.md) when checking routes,
footprints, anchors, facing, and active clips.
For item quantities and resumable progress, use
[inventory and save modules](docs/INVENTORY_AND_SAVES.md); keep item definitions,
rewards, host state validation, and checkpoint timing in the game.
Calibrate projection, rigid footprints, and player/prop proportions before
accepting a pack. Metadata, visual compatibility, and gameplay need separate
verdicts; image bounds and collision tests do not prove visual correctness.

## Choose the owner before editing

| Change | Owner |
| --- | --- |
| Maps, quests, enemies, scores, item definitions/rewards, trap cadence, UI | Host game (`demo/`, or its replacement) |
| Scene schema and validation | `src/types.ts`, `src/scene.ts` |
| Grid geometry, occupancy, routing, floor identity | Headless modules in `src/`; public entry `src/core.ts` |
| Reusable jump/collision calculations | `src/physics.ts` |
| Simulation and lifecycle orchestration | `src/runtime.ts` |
| Asset manifests, references, deterministic variants | `src/art.ts`, scene validation |
| Neighbor masks and connected tile-family variant selection | `src/autotiling.ts` (headless; host owns art and colliders) |
| Sprite presentation and animation | `src/sprites.ts` |
| Pixi composition, depth ordering, image ownership | `src/view.ts`, `src/assets.ts` |
| Keyboard, D-pad, jump button, optional joystick | `src/controls.ts` |
| Approach, action phases, cancellation, effect timing | `src/interactions.ts` (headless; host supplies effects) |
| Optional diagnostic overlay | `src/debug.ts` (DOM adapter; public snapshots only) |
| Item quantities, capacity, inventory snapshots | `src/inventory.ts` (headless) |
| Versioned scene + host-state checkpoints, storage interface | `src/saves.ts` (headless; host injects storage/schema) |
| Public package exports | `src/index.ts`, `src/core.ts` |

New games use public APIs, scene data, and events. Do not add game-specific
branches to `Runtime`, reach into its private fields, or import `SceneView` from
game code. In a copied folder, replace `demo/` with the new host. When retaining
multiple examples here, keep each in `examples/<game-id>/` with its own entry,
scene data, rules, and host configuration; that directory is a convention, not
an existing example launcher.

Keep dependencies pointing toward the headless core. `src/` must not import
`demo/`, examples, legacy Client/Server modules, or files outside this package.
Rendering may depend on core; core must not depend on rendering, controls, or
runtime orchestration. Controls consume their small structural runtime interface.
`npm run check:boundaries` enforces static import boundaries. When adding a source
module, classify it in `scripts/check-boundaries.mjs` according to its actual
responsibility; do not weaken the allowed dependency directions to pass a check.

The runtime currently owns motion, flight, projectile, and camera state. There is
no plugin/ECS interface yet. Extract a cohesive subsystem when a concrete second
use needs it; avoid speculative managers, empty abstractions, and large bundles
of unrelated changes.

## Preserve these contracts

- W / Up = `c + 1` (upper-right); D / Right = `r + 1` (lower-right);
  S / Down = `c - 1` (lower-left); A / Left = `r - 1` (upper-left).
  Mobile controls use these same axes. Do not infer a different isometric mapping.
- Built-in demo click/tap routes use `diagonal: false`: every walking step follows
  one tile axis, never changing column and row together. Preserve this policy when
  adding or replacing demo art. Direct held input is a separate runtime capability.
- A cell is `(c, r, level)`, with omitted level meaning `ground`. Equal coordinates
  on different floors are different cells. Map indexing is `map[r][c]`.
- Tile elevation is local to its floor. `getElevation` and entity pose elevation
  are absolute feet heights. A jump's maximum rise is relative to takeoff.
- Scene versions 1 and 2 remain validated and serializable. Do not store functions,
  Pixi objects, timers, or transient flights/projectiles in scene JSON.
- Art packs are named scene data and host-owned files. Keep atlas dimensions,
  contact anchors, facing conventions and pixel sampling explicit. Rendering size
  must not silently change grid footprint or an explicit physical `bodyHeight`.
  Do not add a game's texture names or palette to engine branches.
- Use elapsed seconds. Preserve `autoStart: false` plus `step()` for deterministic
  simulation, pause behavior, per-instance ownership, and repeatable destruction.
- Event callbacks can remove actors, pause, destroy, or load a scene. Recheck state
  after callbacks before continuing work. Unsubscribe host listeners and dispose
  controls/timers when replacing their owning game.
- Treat `getEntity`/scene snapshots as data copies. Use public methods to change
  engine state. Keep flight landing support, ceiling collision, and occupancy
  reservations intact when changing movement.

## Work and verification

For new worlds and substantial visual production, completion requires the
[world acceptance gate](skills/isometric-visual-loop/references/acceptance.md).
Protect the approved requirements and packed-art checks before implementation;
inspect the exact packed actor clips and joined animated overlays before expanding.
Run `verify-world.py accept` against fresh source/capture hashes and complete
visual, motion, gameplay and performance verdicts for the requested scope.
New world production uses a version 3 acceptance plan with
[executed stage gates](skills/isometric-visual-loop/references/production-flow.md):
preflight, semantic layout, representative assembly, complete static world, motion,
and final review. Begin a capture ticket before each check; failed or unverified
prerequisites block expansion. Use one semantic layout for routes, planting,
entrances and bridge support, and bind measured rigid art to actual host settings.
Retain unchanged receipts; changed dependencies require fresh checks. After two
failed attempts at a check, record a changed strategy before retrying.
Version 3 retains protected target images and the
[image comparison loop](skills/isometric-visual-loop/references/visual-comparison.md).
Run `verify-world.py compare`, have its actual reference/current/previous images
visually inspected, repair located defects and repeat. A written review without
image inspection does not satisfy this workflow.
Failed or unverified requirements remain open. Two repaired review comments, a
passing build or changing frame IDs do not establish overall visual acceptance.
For focused repairs, cover the affected assets/actions and playable views only.
These authoring checks enforce coverage and freshness, not subjective quality or
the truthfulness of a reviewer; report self-review when independence is unavailable.

State the observable behavior and module ownership before a substantial change.
Inspect neighboring code and existing tests; preserve unrelated work. If tasks
are delegated, give each worker disjoint ownership and integrate their results.

The builder owns implementation and required evidence; the reviewer owns observed
findings and verdicts. For an explicitly independent framework trial, the supervisor
may patch reusable framework gaps but must record host implementation help as an
intervention. Do not claim independent execution after supplying the solution.
The optional [trial recorder](docs/FRAMEWORK_TRIALS.md) belongs to framework testing,
not the normal game-production checklist.

For incremental additions, keep verification proportional: type/build checks,
a few meaningful tests of the changed module, and the affected playable journey.
Do not repeat unrelated input/rendering/physics matrices or expand every assertion
into a separate test. Broaden checks only for actual failures, shared-engine
changes, or a framework release.

For the environment skills, run the relevant assembly plan and the lab journey
(`node tests/environment-lab-browser.mjs` against an explicitly started 4175).
`node --experimental-strip-types tests/environment-skills.mjs accepted` checks the
refined fixture. Omit `accepted` to reproduce the three historical workflow
comparisons, which intentionally retain the B/C fountain height omission; that
comparison reports findings rather than treating every trial as a passing gate.
Use `generated-layered` instead of `accepted` for the current generated-art host.

From this folder:

```sh
npm ci
npm run check
npm test
npm run test:browser
npm run build
```

`check` includes import boundaries and strict TypeScript. Core behavior changes
need focused headless tests; rendering, input, and lifecycle changes need relevant
Chromium checks. For interactive changes, also play the actual game in a browser
at desktop and mobile sizes and retain evidence. Run the full existing suites
before a framework release. Documentation-only edits need API/path/example
verification, not a gratuitous simulation rerun.

The standalone demo runs locally on port 4175. Browser tests normally own 4176;
`RUNTIME_QA_URL` may target an explicitly started standalone server instead.
These checks do not certify or deploy the original VPS application.

For changes to the art calibration skill or checker, run `npm run test:art-skill`.
After changing the preview generator, open its generated HTML in a browser and
verify image decoding, shared zoom, overlays, and failure labels. These tools
produce authoring evidence; they do not certify the demo's art or gameplay.

When delivering, report what changed, the public API impact, checks actually run,
and remaining limits. Update guides when contracts change. Keep generated builds,
dependencies, and evidence out of source control. Preserve provenance and notices.
