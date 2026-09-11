# Contributing to Isometric Framework

This document is for framework maintenance. People creating a game should use the
standalone scaffold and [docs/CREATE_GAME.md](docs/CREATE_GAME.md).

## Start here

Read [README.md](README.md), [docs/RUNTIME_API.md](docs/RUNTIME_API.md), and
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md). Use `APP_GUIDE.md` and
`VERIFICATION.md` as records, then inspect source when they may be stale.

Framework checkout commands:

```sh
npm ci
npm run check
npm test
npm run test:browser
npm run build
```

`check` includes strict TypeScript and import boundaries. Core changes need focused
headless coverage; rendering, input, or lifecycle changes need relevant Chromium
coverage. A framework release needs the full existing suite. Documentation changes
need link, path, command, and API-example checks. The demo uses port 4175 and
browser tests normally own 4176.

## Ownership and boundaries

| Change | Owner |
| --- | --- |
| Maps, quests, enemies, scores, item rewards, UI | Game host |
| Scene schema and validation | `src/types.ts`, `src/scene.ts` |
| Geometry, occupancy, routes, floor identity | Headless `src/`, `src/core.ts` |
| Jump and collision calculations | `src/physics.ts` |
| Simulation and lifecycle | `src/runtime.ts` |
| Art manifests and deterministic variants | `src/art.ts`, scene validation |
| Connected-tile selection | `src/autotiling.ts` |
| Sprite rendering and clips | `src/sprites.ts` |
| Pixi composition and assets | `src/view.ts`, `src/assets.ts` |
| Input controls | `src/controls.ts` |
| Approaches and action timing | `src/interactions.ts` |
| Debug overlay | `src/debug.ts` |
| Inventory and checkpoints | `src/inventory.ts`, `src/saves.ts` |
| Public exports | `src/index.ts`, `src/core.ts` |

New games use public APIs, scene data, and events. Do not add game branches to
`Runtime`, reach into private runtime state, or import `SceneView` from a host.
`src/` cannot import hosts, examples, or files outside this package. Rendering may
depend on core; core cannot depend on rendering, controls, or orchestration. Add
new modules to `scripts/check-boundaries.mjs` according to their actual role.

## Preserve runtime contracts

- W/Up moves `c + 1`, D/Right `r + 1`, S/Down `c - 1`, and A/Left `r - 1`.
- Built-in click/tap routing uses `diagonal: false`: each routed walking step
  changes only one tile axis. Held input is a separate runtime capability.
- A cell is `(c, r, level)`; an omitted level is `ground`; map indexing is `map[r][c]`.
- Tile elevation is local to a floor; pose elevation is absolute feet height; jump
  rise is relative to takeoff.
- Scene versions 1 and 2 remain serializable. Scene JSON cannot contain functions,
  Pixi objects, timers, flights, or projectiles.
- Art packs stay host-owned and declare dimensions, contact anchors, facing, and
  sampling. Render size cannot silently alter footprint or `bodyHeight`.
- Preserve elapsed-seconds simulation, `autoStart: false` with `step()`, pause,
  per-instance ownership, and repeatable destruction.
- Event callbacks may change lifecycle state. Recheck after each callback and
  unsubscribe host listeners and controls during teardown.
- Snapshots are copies; mutate through public methods. Keep landing support,
  ceiling collision, and occupancy reservations intact.

## Reference hosts and skills

Maintain `demo/` and `examples/` only when their stated behavior is in scope.
They are not source material for a new game's assets or identity. Historical trial
documents record framework evaluation and limitations. The trial recorder belongs
to that evaluation only, never the normal game-production checklist.

For a substantial framework world or skill change, use the applicable skills and
their acceptance requirements. The visual loop requires fresh image inspection
and separate visual, motion, gameplay, and performance verdicts; a build alone is
not world acceptance. Keep generated builds, dependencies, and evidence out of
source control. Preserve provenance and notices.

Changes to the art checker or preview require `npm run test:art-skill`; open a
generated preview and verify decoding, shared scale, overlays, playback and failure
labels after preview changes. Run the relevant Python tests when changing visual
acceptance or production helpers. Starter/distribution changes require
`npm run build:package`, `npm run test:starter`, and a fresh generated project's
install, check, build and desktop/touch browser journey. Verify packed paths too;
a source-checkout pass does not establish a working consumer package.
Against an explicitly served generated project, set `RUNTIME_QA_URL` and run
`node tests/create-game-browser.mjs test-results/starter-browser` for the keyboard
and touch journeys. Inspect the saved screenshots; the script does not judge art.

Use [FRAMEWORK_TRIALS.md](docs/FRAMEWORK_TRIALS.md) only when evaluating an
independent session. Historical host artwork has its own
[provenance record](docs/history/example-art-provenance.md); these files stay out
of consumer onboarding and distribution.
