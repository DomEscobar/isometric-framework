# Create a game: calibrate, then complete the requested world

Build one room, one actor and one observable rule to calibrate before expanding.
This guide's tiny room is a technical starting point, not a size limit for the
finished game. For a composed environment requested in ordinary language, use
[isometric-visual-loop](../skills/isometric-visual-loop/SKILL.md) to infer the
appropriate effort, plan full content and animation, then execute beyond the
calibration. A local repair or explicitly small prototype keeps its narrow scope.
Start with [AGENTS.md](../AGENTS.md) and [ARCHITECTURE.md](./ARCHITECTURE.md). In the source checkout, `demo/main.ts` is the working host reference; `demo/scenes.ts` shows floors, stairs and jumps. Installed packages include built exports and these guides; source development requires the checkout or a copied framework repository.

## 1. Choose the host location

For a separate game, copy this repository without `.git/`, `node_modules/`, `dist/`,
`demo-dist/`, `.world-build/` or `test-results/`. Keep the lockfile, use Node.js
22.18 or newer, run `npm ci`, and replace `demo/` with your host code. The existing
`index.html` and Vite configuration give that copy a working entry point.

To add an example to this framework checkout, create `examples/<game-id>/` for scene, rules and entry code, and explicitly configure its HTML/Vite entry and TypeScript coverage. `examples/environment-lab/` is a working second host with its own entry and scene data. Preserve the current demo and its browser checks.

For a world with animated water or large structures, combine the bundled
[environment animation](../skills/animated-environments/SKILL.md) and
[multi-tile assembly](../skills/multi-tile-asset-assembly/SKILL.md) skills. Prove a
small assembly's contacts, solid heights and required passage before expanding
the map or commissioning detailed artwork.

For connected beds, paths, walls or water, use the public
[autotiling resolver](AUTOTILING.md) and
[consistent-tileset-authoring skill](../skills/consistent-tileset-authoring/SKILL.md).
The editable `examples/autotile-lab/` demonstrates generated materials, shared
edge geometry, corner-aware selection and colliders from the same cell set.

A separate bundled application can instead run `npm run build` in this repository,
then `npm install ../isometric-framework` from its own project, adjusting the path.
Package examples below use its public root import. When writing inside `demo/`,
use `../src/index` for the same exports. Use a bundler to resolve `pixi.js`.

## 2. Define a three-by-three scene

Keep this in a host scene module. All art below uses built-in graphics, so the first slice has no external asset dependency.

```ts
import { createRuntime, sameCell, type Scene } from 'isometric-framework';

const firstRoom: Scene = {
  version: 1,
  name: 'Find the light',
  tileWidth: 72,
  tileHeight: 36,
  map: [
    ['grass', 'grass', 'grass'],
    ['grass', 'grass', 'grass'],
    ['grass', 'grass', 'grass'],
  ],
  tiles: { grass: { color: 0xadc59b } },
  entityTypes: {
    player: { visual: { kind: 'actor', color: 0xd96e52 }, blocking: true },
    rock: { visual: { kind: 'box', color: 0x92978a, height: 22 }, blocking: true },
    light: { visual: { kind: 'gem', color: 0xf6c75b }, blocking: false },
  },
  entities: [
    { id: 'hero', type: 'player', c: 0, r: 0 },
    { id: 'rock-1', type: 'rock', c: 1, r: 1 },
    { id: 'light-1', type: 'light', c: 2, r: 2 },
  ],
  controlledId: 'hero',
};
```

IDs identify entities; types define their visuals and blocking. Keep the light nonblocking so the hero can arrive on its cell. Larger footprints extend toward positive columns and rows.

## 3. Mount and add one host rule

Provide a focusable container with actual dimensions, for example `<div id="game" tabindex="0" style="width:100%;height:420px"></div>`, plus `<p id="status" role="status"></p>`. Continue the TypeScript example in your host module:

```ts
async function mountGame(container: HTMLElement, status: HTMLElement) {
  const runtime = await createRuntime({ container, scene: firstRoom, speed: 3 });
  status.textContent = 'Reach the golden light.';

  const unsubscribeError = runtime.on('error', ({ error }) => {
    status.textContent = `Runtime error: ${error.message}`;
  });
  const unsubscribeArrival = runtime.on('arrive', ({ id, cell }) => {
    if (id !== 'hero') return;
    const light = runtime.getEntity('light-1');
    if (light && sameCell(light, cell) && runtime.remove(light.id)) {
      status.textContent = 'Light collected. You win!';
    }
  });

  container.focus({ preventScroll: true });
  let disposed = false;
  return () => {
    if (disposed) return;
    disposed = true;
    unsubscribeArrival();
    unsubscribeError();
    runtime.destroy();
  };
}

const container = document.querySelector<HTMLElement>('#game');
const status = document.querySelector<HTMLElement>('#status');
if (!container || !status) throw new Error('Missing game host elements');

// A plain page mount. An SPA should call dispose from its unmount lifecycle.
const dispose = await mountGame(container, status);
window.addEventListener('pagehide', () => dispose(), { once: true });
```

In an SPA, also handle unmounting while the mount promise is pending: mark the host cancelled and dispose immediately if it resolves after unmount. For pages restored from the back/forward cache, either remount on `pageshow` or retain the runtime on a persisted `pagehide`. Development HMR also needs the returned disposer.

The rule uses only exported API. It compares floor-aware identity and checks removal, so repeated arrival cannot award the same light twice. Keep event callbacks synchronous and small. Do not call `step()` recursively or replace/destroy the runtime from this collection callback. Trigger scene transitions through host lifecycle code after event delivery; catch rejected `loadScene()` promises. The runtime's event dispatcher does not catch rejected promises from `async` listeners.

## 4. Add only the next required capability

- Inventory and persistence: use [createInventory and createSaveSlot](./INVENTORY_AND_SAVES.md)
  for quantities and validated scene + host-state checkpoints. Define rewards,
  storage and autosave timing in your game; do not mistake scene export for a
  complete progress save.

- Timed interactions: use [createInteractions](./INTERACTIONS.md) for adjacent
  approach, facing, preparation, one host effect, recovery, and cancellation.
  Supply your inventory rule and directional clips. Keep click routing host-owned
  with `clickToMove: false` when selecting an object starts an action.
- Authoring diagnostics: mount the optional [debug overlay](./DEBUGGING.md)
  behind a toggle to inspect actual routes, footprints, anchors, and clip frames.
  Use rendered art checks as well; accurate metadata alone cannot certify art.

- Inputs: defaults provide click routing, camera dragging/zoom, WASD/arrows and Space. W moves `+c` northeast, D `+r` southeast, S `-c` southwest and A `-r` northwest. Focus stays inside the game container and editable controls are ignored. Add `createDpad` and `createJumpButton` in positioned HUD containers with reserved space for touch; destroy them during host teardown.
- Content: add scene tile/entity definitions. Named asset manifests support image sources, atlas frames, tile textures, anchors and directional clips; follow [ART_PIPELINE.md](./ART_PIPELINE.md). Legacy sprite `url` and `frames` still refer to individual images. Keep art owned by the host and validate loading failures.
- Rules: keep score, inventory and trap cadence in host modules. Use `frame` elapsed seconds for simulation-based timers, and `projectilehit` for host damage rules. Add engine behavior only when the public API cannot express a reusable capability.
- Floors: move to scene version 2 and add `levels`/`links`. A level ID is identity; its `height` plus tile-local `elevation` gives absolute surface height. Always compare `(c, r, level ?? 'ground')`. Use [ARCHITECTURE.md](./ARCHITECTURE.md) before introducing stacked interactions.
- Saves: `serializeScene()` preserves remaining entities and committed positions. Store host progress separately; it does not serialize a complete game session. Catch and display invalid-import errors without discarding the current game.

## 5. Validate the slice and report evidence

From the repository root, `npm run dev` serves `http://127.0.0.1:4175`. Validate a new host at its configured local URL. This standalone package does not require the legacy Client/Server application, a VPS, login, deployment or an agent provider.

For this room, demonstrate a route around the center rock, blocked movement into it, exactly one collection at the light, correct WASD axes, release/focus-loss stopping and clean unmount/remount. If adding touch controls, verify them on a narrow viewport with simultaneous held movement and Jump. If changing floors or projectiles, verify their affected interactions visibly as well as in core logic.

Use checks appropriate to the change:

```sh
npm run check
npm test
# Once per environment when browser checks are needed:
npx playwright install chromium
npm run test:browser
npm run build
```

`check` verifies module import boundaries and checks configured TypeScript files; ensure any new example is included. New engine modules must be classified in `scripts/check-boundaries.mjs`. `test` runs core tests. `test:browser` owns an isolated local Vite server on port 4176 and runs existing browser/API scenarios, with evidence under `test-results/`; it does not automatically test a new game or replace a playtest of its rule. Add or run targeted checks for changed behavior. `build` creates library bundles, the existing demo build and declarations. A new example needs its own build integration.

Documentation-only changes need verified links, paths, commands and API examples, not a full browser run. Report which checks actually ran, their results, and any missing evidence. Keep framework capabilities separate from desired future features.

## 6. Complete the planned environment

After calibration, continue with the requested regions, connected terrain,
complex structures, art and fitting environmental motion. Keep the full brief's
completion evidence alongside the host. Validate overview composition, important
routes and overlaps, and actual animation over time in the integrated world.
Do not stop at this tutorial's room when the user asked for a finished environment,
or substitute static scenery for requested flow. Reuse the bundled specialist
skills and public modules; extend the runtime only for an actual capability gap.
