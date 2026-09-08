# Runtime architecture

Runtime is the first working slice of a modular framework for coding agents to build isometric games. Today it is one TypeScript package with explicit module boundaries and a playable host application. There is no plugin registry, system scheduler, editor, or full 3D physics engine. Compose games through scene data, public methods, events, and host-owned modules; introduce further framework abstractions only when a concrete game needs them.

Read [../AGENTS.md](../AGENTS.md) for contributor rules and [CREATE_GAME.md](./CREATE_GAME.md) for the first game recipe. All source paths below are relative to the repository root.

## Ownership and dependencies

| Boundary | Current files | Owns |
| --- | --- | --- |
| Data contract | `src/types.ts`, `src/scene.ts` | Versioned scenes, entities, options, events, validation and normalization. Scene input is data, never executable game code. |
| Renderer-independent core | `src/geometry.ts`, `src/levels.ts`, `src/model.ts`, `src/pathfinding.ts`, `src/level-pathfinding.ts` | Projection, floor identity, authoritative integer cells, occupancy, footprints, support and traversable routes. No Pixi or DOM dependency. |
| Physics helpers | `src/physics.ts` | Flight poses, supported landings, clearance and swept collision calculations. Renderer-independent internal helpers; not an exported plugin system. |
| Runtime orchestration | `src/runtime.ts`, `src/events.ts` | Instance lifecycle, asynchronous scene loading, stepping, movement, jumps, projectiles, camera, picking, default pointer input and event delivery. `Runtime` currently depends directly on Pixi. |
| Art contract | `src/art.ts` | Named image/texture/clip manifests, validation, deterministic tile variants and directional clip resolution; independent of Pixi and DOM. |
| Autotiling | `src/autotiling.ts` | Cardinal16/blob47 topology and seeded host variant selection; no rendering or scene mutation. See [AUTOTILING.md](AUTOTILING.md). |
| Sprite presentation | `src/sprites.ts` | Frame anchors, display size, tint/offset, facing and elapsed-time clip playback. Physical dimensions stay in entity definitions. |
| Pixi adapter | `src/view.ts`, `src/assets.ts` | Display objects, floor cutaways, masked terrain tops, image loading, atlas frames and scene-owned disposal. Rendering does not decide scores, quests or damage. |
| Controls | `src/controls.ts` | Focus-scoped keyboard input and DOM D-pad, joystick and jump controls. Uses a structural input target instead of importing the renderer. |
| Interactions | `src/interactions.ts` | Headless approach/prepare/effect/recovery controller using a structural public runtime interface; host supplies synchronous effects. See [INTERACTIONS.md](./INTERACTIONS.md). |
| Diagnostics | `src/debug.ts` | Optional DOM/SVG overlay reading detached public snapshots; does not intercept game input. See [DEBUGGING.md](./DEBUGGING.md). |
| Inventory and checkpoints | `src/inventory.ts`, `src/saves.ts` | Headless quantity/capacity model and versioned scene + host-state records. Host defines items, state schema, storage adapter and checkpoint timing. See [INVENTORY_AND_SAVES.md](./INVENTORY_AND_SAVES.md). |
| Host game | `demo/main.ts`, `demo/scenes.ts`, `demo/style.css` | Content, collection rules, trap timing, hit counter, HUD, scene selection, import/export UI and host teardown. |

Dependency direction is host -> public runtime API -> core and Pixi adapter. Controls issue public input commands. Core must stay usable without a browser. `Runtime` composes these pieces; renderer replacement would require adapter/orchestration work because a renderer injection interface does not exist yet.

In the source checkout, `npm run check:boundaries` runs `scripts/check-boundaries.mjs`; `npm run check` includes it before TypeScript checking. Its dependency groups are headless (including physics and events), renderer, controls and orchestration. It rejects imports from `src/` into host/legacy code, reverse dependencies into rendering/orchestration from headless modules, and external imports except Pixi in renderer/orchestration. Classify new source modules by responsibility in the checker. It examines import/re-export syntax, including literal dynamic and type imports; it is not a proof against arbitrary JavaScript behavior. Run `node scripts/check-boundaries.mjs --self-test` when changing its rules.

## Public extension seams

The package root `isometric-framework` is defined by `src/index.ts`: `Runtime`, `createRuntime`, public types, core exports and control helpers. The `isometric-framework/core` entry is defined by `src/core.ts`: selected scene types, `levelOf`, `sameCell`, `levelMaps`, `levelHeight`, `project`, `unproject`, `validateScene`, `findPath`, and `WorldModel`. Files being exported internally does not make them package subpaths; do not deep-import private runtime modules from a host game.

The headless `isometric-framework/art` entry exposes asset manifest types plus
`validateAssetManifest`, `selectTileTexture`, and `resolveAnimation`. Root and core
also re-export them. Pixi texture objects and `EntitySprite` remain internal;
agents supply data through these public contracts instead of managing GPU objects.

Root and core also export `createInteractions` and its structural target/action
types. The root additionally exports `createDebugOverlay`; diagnostic snapshots
come from `Runtime.getDebugSnapshot()`. These optional helpers add no scene scripts
or plugin registry. `clickToMove: false` gives host interactions ownership of
tile-click routing while the runtime retains picking and camera input.

| Need | Where to implement |
| --- | --- |
| A different map, obstacles, collectibles or actor art | Host scene definitions and named asset packs; see [ART_PIPELINE.md](./ART_PIPELINE.md). |
| Inventory, score, trap cadence, health, quests, win conditions | Host rule modules subscribing to events and calling public methods. `EntityDefinition.data` can carry host metadata; the engine does not execute it. |
| A different HUD or input device | Host DOM and control mounting; custom input calls `setMoveInput`, `jump`, or `moveTo`. |
| Persistence or networking | Host adapters. Save scene data and host state explicitly; no backend is required by this package. |
| Reusable missing collision, floor, movement or rendering behavior | A scoped engine change in the owning module, with public types/validation/exports and regression evidence as needed. |

Keep a new game's rules outside `src/`. In a copied framework repository, replace `demo/` with that game's host. In the framework checkout, additional games belong in `examples/<game-id>/` with their own entry, scene and rules plus required host configuration. That directory and a multi-example launcher are not scaffolded today. Do not imply that adding a folder automatically builds or serves it.

## Coordinate contract

Maps are row-major: `map[r][c]`. Positive columns project northeast; positive rows project southeast. Preserve these original axes across keyboard, D-pad, pathfinding and documentation:

| Key / arrow alias | Grid delta | Visible direction |
| --- | --- | --- |
| W / Up | `c + 1` | Northeast |
| D / Right | `r + 1` | Southeast |
| S / Down | `c - 1` | Southwest |
| A / Left | `r - 1` | Northwest |

`setMoveInput({ x, y })` takes a screen-direction vector, not grid deltas. For W-like movement use a northeast vector such as `{ x: 1, y: -1 }`; keyboard and D-pad perform this conversion themselves. Releasing input with `null` finishes the current step. Direct input supports eight directions; scene `diagonal` governs click-path routing.

Floor identity is `(c, r, level ?? 'ground')`, independent of height. Use `sameCell` for host interactions. Version 1 has one ground map. Version 2 adds same-sized floor maps with `null` for absent surfaces and explicit stair links between walkable cardinally adjacent cells on different floors. Walk routing changes floors through links; jumps separately evaluate reachable landing surfaces.

`TileDefinition.elevation` is local to its floor. Absolute surface elevation is floor `height` plus tile elevation; `runtime.getElevation(cell)` returns that sum. `getEntityPose()` supplies continuous position, absolute feet elevation and airborne status. During flight the committed entity cell remains reserved until landing. Projectile `elevation` is also absolute pixels. Equal heights do not merge floor identities. `setViewLevel()` only changes rendering and picking; it does not move actors or change collision.

`project()` returns world projection coordinates; `unproject()` is a ground-plane inverse, not stacked-floor picking. Use `runtime.pick()` and `cellToScreen()` for camera-aware canvas-local CSS pixel coordinates.

## Lifecycle and event conventions

- Await `createRuntime(options)` before scene calls, or await `new Runtime(options).ready`. A host that can unmount during startup must track cancellation and destroy the pending instance. The factory destroys its instance when initial loading fails.
- `loadScene(unknown)` validates and prepares assets before replacing the current scene. Catch its rejection. A newer load or destruction cancels pending loading; failed validation/asset loading preserves the existing scene. Successful replacement clears transient movement, flights and projectiles, resets floor view and fits the camera. Input is reset during loading.
- `on(name, listener)` returns a disposer. Delivery is synchronous; synchronous listener exceptions are routed to `error`. Async listener promises are not awaited or caught. Keep callbacks bounded, and catch any host asynchronous work explicitly. Avoid recursive `step`, scene loading or destruction inside simulation callbacks; let the host schedule lifecycle work after the callback returns.
- Use `arrive` for committed-cell collection/interaction and `move`/`getEntityPose` for continuous presentation. Arrival can also occur for an already-reached `moveTo` target; rules should be idempotent. `projectilehit` reports contact; host code decides damage. `frame.deltaSeconds` supports host timers that follow simulation pause. `inputreset` tells custom controls to clear held state.
- Default automatic stepping belongs to the runtime. With `autoStart: false`, the host owns its loop and calls `step(seconds)` with finite values in `[0, 60]`. Do not run both loops. Paused instances do not advance simulation.
- Dispose host subscriptions, DOM listeners, timers and separately mounted controls, then call `destroy()`. Runtime destruction is idempotent and releases its renderer, observer, default listeners, subscriptions and assets. Host resources remain the host's responsibility.

`serializeScene()` captures scene definitions and committed entity state, including floors and links. It does not save in-progress motion/jumps/projectiles, camera, pause/view settings, or host score/inventory. A complete game save needs a host-owned versioned envelope around the scene and game state.

`createSaveSlot` supplies that versioned envelope and validates scenes plus a
host-supplied state schema. `createInventory` supplies portable quantity snapshots.
Both are root/core exports. They do not implicitly change the runtime, choose a
database, or own a game's rewards.
