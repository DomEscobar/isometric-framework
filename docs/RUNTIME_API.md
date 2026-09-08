# Runtime API

## Use it in another game

Sunflower now demonstrates the reusable [interaction module](./INTERACTIONS.md):
click a small path flower to approach, face it, play a short gesture, and put one
flower in the basket. Pause freezes the action; Escape or Cancel stops it.
The gesture reuses grounded gardener frames; dedicated picking artwork is still
an asset-authoring task. Walking onto a flower alone no longer collects it.

The optional **Debug overlay** toggle shows tile coordinates, blocking footprints,
the selected actor's route, sprite origin/bounds, and actual clip/frame/facing.
See [DEBUGGING.md](./DEBUGGING.md) for integration in other hosts.

Copy the framework repository, install its dependencies, and replace `demo/` with your own application. Alternatively build it and install the package by local path in another project:

When copying sources, omit `.git/`, `.world-build/`, and the generated `node_modules/`, `dist/`, `demo-dist/`, and `test-results/` folders. Keep `package-lock.json` and use `npm ci` for the recorded dependency versions.

```sh
# In the framework repository:
npm ci
npm run build

# In your game's project (adjust the path):
npm install ../isometric-framework
```

The library output is `dist/runtime.js`, its declarations are in `dist/types/`, and the renderer-independent helpers are available through `isometric-framework/core`. The library keeps Pixi.js as an external dependency; use a bundler such as Vite to resolve the installed `pixi.js` package. `demo-dist/` is the separate browser demo build and can be served by a static HTTP server.

```ts
import { createRuntime, type Scene } from 'isometric-framework';

const scene: Scene = {
  version: 1,
  name: 'My first room',
  tileWidth: 72,
  tileHeight: 36,
  map: [
    ['grass', 'grass', 'grass'],
    ['grass', 'grass', 'grass'],
    ['grass', 'grass', 'grass'],
  ],
  tiles: { grass: { color: 0xadc59b } },
  entityTypes: {
    player: {
      visual: { kind: 'actor', color: 0xd96e52, height: 32 },
      blocking: true,
    },
    rock: {
      visual: { kind: 'box', color: 0x92978a, height: 22 },
      blocking: true,
    },
  },
  entities: [
    { id: 'hero', type: 'player', c: 0, r: 0 },
    { id: 'rock-1', type: 'rock', c: 1, r: 1 },
  ],
  controlledId: 'hero',
};

// Give this element a real width and height before mounting.
const container = document.querySelector<HTMLElement>('#game')!;
const runtime = await createRuntime({ container, scene, speed: 3 });
const unsubscribe = runtime.on('arrive', ({ id, cell }) => {
  console.log(`${id} arrived at ${cell.c}, ${cell.r}`);
});

runtime.moveTo('hero', { c: 2, r: 2 });
const saved = runtime.serializeScene();
await runtime.loadScene(saved);

// During application teardown:
unsubscribe();
runtime.destroy();
```

### Runtime API

- `createInventory(definitions, options?)` manages item quantities and capacity,
  with detached snapshots and atomic restore.
- `createSaveSlot({ key, gameId, storage, validateState })` reads/writes validated
  scene + host-state records. See [inventory and saves](./INVENTORY_AND_SAVES.md).
  Sunflower demonstrates a real flower inventory and automatic local checkpoints;
  reload resumes a saved garden, and Restart resets it. Save/Continue controls are
  below scene export. Other presets retain their existing collection behavior.

- `createInteractions(runtime, options?)` returns a headless controller with
  `request`, `cancel`, `getState`, and `destroy`. It owns action phases and invokes
  host effects; it does not own inventory or execute scene JSON scripts.
- `setFacing(id, direction)` explicitly faces a sprite without moving it.
- `getDebugSnapshot()` returns detached diagnostic data. `createDebugOverlay`
  renders it in optional host-owned DOM containers; neither edits game state.
- `clickToMove: false` in runtime options lets a host own `tileclick` routing
  while retaining picking and camera controls. It defaults to `true`.
- `command` reports explicit actor movement/input/jump/stop intent before it is
  applied. `camerachange` and `viewchange` report completed camera/floor-view changes;
  `destroy` announces disposal for owned helper cleanup. Callbacks are synchronous.

- `createRuntime(options)` resolves when the initial scene is ready. `new Runtime(options)` exposes a `ready` promise for explicit lifecycle handling.
- `loadScene(input)` validates unknown input and loads its assets before replacing the current scene. Invalid data rejects the promise and preserves the current scene.
- `serializeScene()` returns scene data for JSON storage. `getEntities()` and `getEntity(id)` expose entity definitions.
- `moveTo(id, cell)` returns `started`, `arrived`, `blocked`, `missing`, or `paused`. `findPath(id, cell)` returns a route or `null`. `stop(id)` stops movement at the last completed grid cell. `setControlled(id)` selects the actor for default pointer movement; `null` disables that behavior.
- `setMoveInput({ x, y })` holds a screen-relative direction for the controlled actor, with each component in `[-1, 1]`. `setMoveInput(null)` releases it; movement finishes the current grid step. A new direction overrides a click route. Direct movement checks obstacles and avoids diagonal corner cutting. It supports eight directions independently of the scene's click-path `diagonal` setting.
- `getLevels()` lists `{ id, name, height }`, including `ground`. `getElevation(cell)` returns floor height plus that tile's local elevation. Cells and entities accept an optional `level` ID; omitted means `ground`.
- `setAnimation(id, clip)` overrides a named-asset sprite's automatic clip; `null` returns to idle/walk/jump selection. Repeating a non-null clip restarts it. It returns false for missing entities, built-ins, or legacy URL/frame sprites. An unknown non-null clip throws before changing the current clip. Non-looping clips hold their final frame until the host changes the override.
- `jump(id?)` starts a leap in the held direction or a vertical hop, returning `started`, `airborne`, `blocked`, `missing`, or `paused`. Defaults are a maximum rise of 84 pixels above takeoff, 0.8 seconds, and two grid steps; configure them with `RuntimeOptions.jump`. Neutral and same/lower-floor jumps use a 40-pixel hop. The first reachable raised surface is preferred. A jump requires supported landing space and a clear flight volume; ceilings and platform sides block it. Another jump requires touchdown.
- `getEntityPose(id)` returns continuous position, absolute feet elevation, and `airborne`. The committed entity cell remains reserved until landing; a newly blocked landing cancels the jump back to that cell. Flights are transient and are not exported in scene files.
- `spawnProjectile({ from, to, speed, elevation, radius?, color?, targetId? })` returns a projectile ID. Elevation is absolute pixels; speed is tiles per second. Swept collision checks the target actor's moving body, so low bolts can be jumped over. `removeProjectile(id)` cancels a bolt. Projectiles expire on arrival or hit and are cleared by scene replacement/destruction. Events `jumpstart`, `land`, and `projectilehit` let host games supply their own rules.
- `setViewLevel(id)` cuts away higher floors and restricts picking to the chosen floor. Lower floors remain visible for context. `setViewLevel(null)` restores all floors. `getViewLevel()` returns the active filter. View changes leave simulation and entity locations intact.
- `add(entity)` and `remove(id)` change scene entities. Entity type definitions live in the scene.
- `on(event, callback)` returns an unsubscribe function. Events include `tileclick`, `hover`, `move`, `arrive`, `blocked`, `frame`, `scenechange`, `pausechange`, and `error`.
- `move` provides `{ id, position, elevation }`; `elevation` interpolates during stair movement, while `position.level` changes when the destination step completes. `arrive.cell` carries the destination floor. `inputreset` lets custom input controls clear held state after lifecycle changes.
- `getCamera()`, `setCamera(partial)`, `fit()`, `resize()`, `pick(localPoint)`, and `cellToScreen(cell)` support camera and application integration. Screen points use coordinates local to the canvas in CSS pixels.
- `pause()`, `resume()`, and `isPaused` control simulation. `destroy()` releases the instance and can be called repeatedly.
- `step(deltaSeconds)` advances simulation and rendering by elapsed seconds. It accepts finite values from 0 through 60 and does not advance simulation while paused. Set `autoStart: false` when your application owns the frame loop, then call `step()` yourself; otherwise the runtime starts its own loop.

An `input: false` option disables default pointer and keyboard controls; exported `attachKeyboard`, `createDpad`, and `createJoystick` can still be mounted explicitly. `keyboard: false` disables only the default keyboard listener. WASD and arrows are scoped to focus inside the game container and ignore editable fields. Held input is reset on focus loss, pause, and scene changes. Movement speed is in tiles per second. `background` accepts a numeric RGB color. `assetTimeoutMs` bounds image-loading time (15 seconds by default).

For an application-owned touch HUD, mount the exported control in a positioned container with reserved layout space:

```ts
import { createDpad, createJumpButton } from 'isometric-framework';

const hud = document.querySelector<HTMLElement>('#movement-hud')!;
// For example: position: relative; width: 164px; height: 164px.
const dpad = createDpad(runtime, hud);
// Reserve a separate space beside the pad for the Jump button.
const jump = createJumpButton(runtime, document.querySelector<HTMLElement>('#jump-hud')!);
// During application teardown, before destroying the runtime:
jump.destroy();
dpad.destroy();
```

The directional pad uses the same tile axes as WASD. It supports holding two directions together, pointer capture, release/cancellation, and pressed feedback. Keep camera controls outside its hit area. The separate `createJoystick` export remains available for screen-relative analog controls; the demo uses `createDpad`. You can also build custom inputs with `setMoveInput`.

### Scene data and assets

`Scene` accepts version 1 and version 2; see `src/types.ts` for the full typed contract and `demo/scenes.ts` for complete examples. Existing version-1 scenes remain supported as a single ground floor. The map is row-major: `map[r][c]`. Tile definitions specify color, walkability, and optional elevation in screen pixels. Entity types specify a visual, blocking behavior, and a rectangular footprint extending toward positive columns and rows.

Version 2 adds independent stacked floors and explicit connections. Each upper map has the ground map's dimensions, with `null` where that floor does not exist. Floor IDs must be unique; `ground` is reserved for the base map. Entity collision, pathfinding, picking, and gameplay lookups distinguish floor IDs, so a rock below a bridge does not obstruct an actor above it.

```ts
const stackedScene: Scene = {
  ...scene, // The three-by-three room above.
  version: 2,
  levels: [{
    id: 'bridge', name: 'Bridge', height: 72,
    map: [
      [null, 'grass', 'grass'],
      [null, 'grass', 'grass'],
      [null, null, null],
    ],
  }],
  links: [{
    from: { c: 0, r: 0 },
    to: { c: 1, r: 0, level: 'bridge' },
    bidirectional: true,
  }],
};
await runtime.loadScene(stackedScene);
runtime.moveTo('hero', { c: 2, r: 1, level: 'bridge' });
```

Stair endpoints must be walkable cardinally adjacent cells on different floors. Links are explicit transitions; overlapping surfaces alone do not connect. `bidirectional: true` allows travel in both directions. Ordinary terrain steps obey `maxStepHeight`; links permit floor changes and interpolate their elevation difference. The demo adds 18/36/54-pixel ground steps before each 72-pixel bridge entrance for a visible stair flight. Serialized scenes preserve levels, links, and each entity's floor. When writing collection or interaction rules, compare `(c, r, level ?? 'ground')`, not just `(c, r)`.

Built-in `box`, `actor`, and `gem` visuals use generated graphics. Legacy image art still accepts `visual: { kind: 'sprite', url: '/assets/hero.png' }` or individual-image `frames` with optional `fps`. Named art packs add `scene.assets` with image sources, atlas texture rectangles, contact anchors and animation clips. Tile `texture` or deterministic `textures` variants cover diamond tops; sprite `texture`/`animation` plus directional state mappings provide idle, walking and jumping art. Display width, tint and offsets are separate from `EntityType.bodyHeight` and grid footprints.

Use the [art pipeline guide](./ART_PIPELINE.md) for a complete manifest, coordinate conventions, asset preparation, and visual checks. `isometric-framework/art` exports headless manifest types and `validateAssetManifest`, `selectTileTexture`, and `resolveAnimation`; these helpers are also available from the root/core entries. Select **05 — Woodland atelier** for the local atlas example. URLs resolve against the hosting document; keep art with the game and bundle it with the host. External atlas JSON formats, rotated frames, and automatic trim recovery are not implemented.

Keep gameplay rules outside the engine. The primitive and Woodland demos collect on `arrive`; Sunflower uses `createInteractions` with a host-owned basket effect. Both compose public APIs. For multiple games or mounted instances, create separate runtime instances and tear each one down when its host is removed.

## Scope and compatibility

This is a cleaned and reworked source-derived core, not a byte-compatible copy of Traviso or the existing world database. Existing application worlds need a deliberate migration into the new scene format. The original client remains separate.

The runtime provides stacked 2.5D floors, stair connections, tile elevation, pathfinding, keyboard/touch movement, bounded jumps, and straight projectile traps. It does not model full 3D physics, navigation meshes, or an editor. Multiplayer, authentication, uploads, application UI, chat, undo/redo, and `eval`-based scripts are excluded. The examples demonstrate runtime composition, not a complete game-maker authoring tool.

See [PROVENANCE.md](../PROVENANCE.md) for source lineage, [APP_GUIDE.md](../APP_GUIDE.md) for observable demo checks, and [VERIFICATION.md](../VERIFICATION.md) for executed checks, retained evidence, and limitations.
