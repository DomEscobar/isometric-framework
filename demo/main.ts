import { createDebugOverlay, createDpad, createInteractions, createJumpButton, createRuntime } from '../src/index';
import type { InteractionAction, InteractionState } from '../src/index';
import type { Cell, Scene } from '../src/types';
import { createScene, type Preset } from './scenes';
import { createGardenInventory, createGardenSave, isCollectible, type GardenSave } from './garden-progress';
import './style.css';

const app = document.querySelector<HTMLDivElement>('#app')!;
app.innerHTML = `
  <main class="shell">
    <header class="masthead">
      <a class="wordmark" href="./" aria-label="Little Worlds home"><span class="mark" aria-hidden="true">◇</span> little worlds<span class="wordmark-dot">.</span></a>
      <span class="edition">ISOMETRIC RUNTIME / 01</span>
    </header>
    <section class="intro" aria-labelledby="page-title">
      <p class="eyebrow">A SMALL PLACE TO START</p>
      <h1 id="page-title">A world of your own.</h1>
      <p class="lede">One tiny map. An independent engine. See where it takes you.</p>
    </section>
    <section class="workspace" aria-label="Playable isometric demo">
      <div class="stage-wrap">
        <div class="stage-heading"><span id="scene-name">Sunflower courtyard</span><span class="state-pill" id="run-state">Loading</span></div>
        <div id="world" tabindex="0" role="application" aria-label="Isometric map. Use WASD or arrow keys to walk, Space to jump. Click or tap a tile to find a route. Drag to pan. Use the zoom buttons to resize the view."></div>
        <div class="movement-hud" aria-label="Touch movement controls"><div class="dpad-guide"><div id="jump-host"></div><span id="jump-hint">Hold ↗ + Jump<br>to reach the bridge.</span><button id="cancel-action-touch" type="button" hidden disabled>Cancel picking</button></div><div id="dpad-host"></div></div>
        <div class="stage-tools">
          <span id="hover-cell" class="coordinate">Point to a tile</span>
          <div class="camera-tools" aria-label="Camera controls">
            <button id="zoom-out" type="button" aria-label="Zoom out">−</button>
            <button id="zoom-in" type="button" aria-label="Zoom in">+</button>
            <button id="fit" class="fit-button" type="button">Fit map</button>
          </div>
        </div>
      </div>
      <aside class="panel" aria-label="Game controls">
        <div><p class="eyebrow">SEVEN SCENES, ONE ENGINE</p><h2>A little garden escape.</h2></div>
        <label class="field-label" for="preset">Choose a scene</label>
        <select id="preset"><option value="cafe">06 — Sunflower courtyard</option><option value="cafe-calibration">07 — Art calibration</option><option value="jump">04 — Jump &amp; dodge</option><option value="levels">03 — Above &amp; below</option><option value="courtyard">01 — Quiet courtyard</option><option value="collection">02 — Collect the lights</option><option value="art">05 — Woodland atelier</option></select>
        <div class="transport"><button id="pause" class="primary" type="button">Pause</button><button id="restart" type="button">Restart</button></div>
        <div id="flower-action" class="flower-action" hidden>
          <div class="action-heading"><span id="action-status" role="status">Ready to pick</span><button id="cancel-action" type="button" disabled>Cancel action</button></div>
          <progress id="action-progress" max="1" value="0" aria-label="Flower picking progress"></progress>
          <p>Click a small path flower to pick it. Move, press Escape, or cancel to stop.</p>
        </div>
        <dl class="readouts">
          <div><dt>Traveler</dt><dd id="actor-cell">—</dd></div>
          <div><dt>Floor / height</dt><dd id="actor-floor">—</dd></div>
          <div><dt>Movement</dt><dd id="actor-state">Grounded</dd></div>
          <div><dt>Last arrival</dt><dd id="arrival-cell">—</dd></div>
          <div><dt id="collection-label">Flowers in basket</dt><dd id="collection-count">0 / 0</dd></div>
          <div id="trap-readout"><dt>Trap hits</dt><dd id="trap-hits">0</dd></div>
        </dl>
        <label class="field-label floor-label" for="view-level">Show floor</label>
        <select id="view-level"><option value="all">All floors</option></select>
        <p class="floor-note">Ground reveals the route under the bridge. Changing the view keeps your traveler in place.</p>
        <p id="mission" class="mission">Explore the garden. The traveler finds a way around hedges and stones.</p>
        <div id="trap-controls" class="trap-controls"><button id="trap-toggle" type="button" aria-pressed="true">Trap on</button><p id="trap-status" role="status">Amber bolts cross the rose-colored lane.</p></div>
        <p id="feedback" role="status" aria-live="polite">Opening the courtyard…</p>
        <div class="instructions"><h3>Find your way</h3><p>Follow the isometric tiles: W ↗, D ↘, S ↙, A ↖. Arrow keys use the same axes. On touch screens, hold a button on the bottom-right directional pad. Release to finish the current step.</p><p>Space jumps. Hold a direction + Space to leap forward, or press Space alone to hop over a low bolt. On mobile, hold ↗ with one finger and tap Jump with another.</p><p>Click or tap a tile to find a route. Stairs connect the floors; their lights and obstacles are separate. Choose a floor to target it, or Follow traveler for an automatic cutaway.</p><p>Drag the map to pan. Scroll or use + / − to zoom.</p></div>
        <div class="project-actions"><button id="export" type="button">↓ Export scene</button><label class="import-label" for="import">↑ Import scene<input id="import" type="file" accept=".json,application/json" /></label></div>
        <p class="file-note">Scene files keep floors, stairs, and entity positions. Game rules live in the demo.</p>
        <div class="garden-save-tools">
          <div id="inventory-items">Empty basket</div>
          <div class="project-actions"><button id="save-game" type="button">Save garden</button><button id="load-game" type="button">Continue garden</button></div>
          <p id="save-status" class="file-note" role="status">Garden progress saves on this browser.</p>
        </div>
        <div class="debug-tools"><button id="debug-toggle" type="button" aria-pressed="false" aria-controls="debug-panel">Debug overlay</button><div id="debug-panel" hidden></div></div>
      </aside>
    </section>
    <footer><span>Made of tiles. Ready for your ideas.</span><span>TypeScript · Pixi.js · Local scene files</span></footer>
  </main>`;

function element<T extends HTMLElement>(id: string): T {
  return document.getElementById(id) as T;
}
const feedback = element('feedback');
const presetSelect = element<HTMLSelectElement>('preset');
const floorSelect = element<HTMLSelectElement>('view-level');
const pauseButton = element<HTMLButtonElement>('pause');
const fileInput = element<HTMLInputElement>('import');
const formatCell = (cell: Cell) => `${Number(cell.c.toFixed(1))}, ${Number(cell.r.toFixed(1))}`;
let baseline: Scene = createScene('cafe');
let collected = 0;
let total = 0;
let loading = true;

function setLoading(value: boolean): void {
  loading = value;
  app.querySelectorAll<HTMLButtonElement | HTMLSelectElement | HTMLInputElement>('button, select, input').forEach(control => { control.disabled = value; });
  element('world').setAttribute('aria-busy', String(value));
}

async function start(): Promise<void> {
  setLoading(true);
  const runtime = await createRuntime({ container: element('world'), scene: baseline, background: 0xe9eee2, speed: 3, clickToMove: false });
  const dpad = createDpad(runtime, element('dpad-host'));
  const jumpButton = createJumpButton(runtime, element('jump-host'));
  jumpButton.element.style.right = '0';
  jumpButton.element.style.bottom = '0';
  const trapToggle = element<HTMLButtonElement>('trap-toggle');
  const cancelAction = element<HTMLButtonElement>('cancel-action');
  const cancelActionTouch = element<HTMLButtonElement>('cancel-action-touch');
  const debugToggle = element<HTMLButtonElement>('debug-toggle');
  const debugPanel = element('debug-panel');
  const debug = createDebugOverlay(runtime, { container: element('world'), panel: debugPanel });
  let debugEnabled = false;
  const flowerScene = () => baseline.name === 'Sunflower courtyard';
  const inventory = createGardenInventory();
  const gardenSave = createGardenSave({
    getItem: key => localStorage.getItem(key),
    setItem: (key, value) => localStorage.setItem(key, value),
    removeItem: key => localStorage.removeItem(key),
  });
  const saveButton = element<HTMLButtonElement>('save-game');
  const saveStatus = element('save-status');
  function updateInventory(): void {
    element('inventory-items').textContent = flowerScene()
      ? inventory.count('flower') ? `Garden flowers × ${inventory.count('flower')}` : 'Empty basket'
      : 'Continue your saved Sunflower garden.';
    saveButton.disabled = loading || !flowerScene();
  }
  function saveGarden(): void {
    if (loading || !flowerScene()) return;
    try {
      gardenSave.write(runtime.serializeScene(), { baseline, inventory: inventory.snapshot() });
      saveStatus.textContent = 'Garden saved on this browser.';
    } catch (error) {
      saveStatus.textContent = `Could not save: ${error instanceof Error ? error.message : String(error)}. Your game is still playable.`;
    }
  }
  const flowerAction: InteractionAction = {
    id: 'pick-flower', prepareSeconds: .9, recoverSeconds: .45,
    clips: { ne: 'pick-ne', se: 'pick-se', sw: 'pick-sw', nw: 'pick-nw' },
    recoveryClips: { ne: 'pick-recover-ne', se: 'pick-recover-se', sw: 'pick-recover-sw', nw: 'pick-recover-nw' },
    canPerform: ({ target }) => flowerScene() && isCollectible(target, baseline),
    perform: ({ target }) => {
      if (!inventory.canAdd('flower') || !runtime.remove(target.id)) return false;
      inventory.add('flower');
      collected = inventory.count('flower');
      updateInventory();
      saveGarden();
      element('collection-count').textContent = `${collected} / ${total}`;
      feedback.textContent = collected === total ? 'All flowers are in your basket. Time for a rest under the parasol.' : 'One flower added to your basket.';
      return true;
    },
  };
  function updateActionUi(state: InteractionState): void {
    const active = state.phase !== 'idle';
    cancelAction.disabled = loading || !active;
    cancelActionTouch.disabled = loading || !active;
    element('flower-action').dataset.phase = state.phase;
    const progress = element<HTMLProgressElement>('action-progress');
    progress.value = state.phase === 'preparing' ? Math.min(1, state.elapsedSeconds / flowerAction.prepareSeconds)
      : state.phase === 'recovering' || state.reason === 'completed' ? 1 : 0;
    element('action-status').textContent = state.phase === 'approaching' ? runtime.isPaused ? 'Walk to flower paused' : 'Walking to the flower'
      : state.phase === 'preparing' ? runtime.isPaused ? 'Picking paused' : 'Picking flower…'
      : state.phase === 'recovering' ? runtime.isPaused ? 'Settling paused' : 'Flower in basket · settling'
      : state.reason === 'completed' ? 'Flower picked' : state.reason ? 'Action stopped' : 'Ready to pick';
    if (active && state.phase !== 'recovering') feedback.textContent = state.phase === 'approaching'
      ? 'Walking to a clear tile beside the flower.' : 'Picking the flower. You can cancel before it reaches the basket.';
    if (!active && state.reason && state.reason !== 'completed' && flowerScene()) {
      feedback.textContent = state.effectApplied ? 'Action stopped. The picked flower stays in your basket.' : 'Picking stopped. The flower is still in the garden.';
    }
  }
  const interactions = createInteractions(runtime, {
    onChange: updateActionUi,
    onError: error => { feedback.textContent = `Could not pick flower: ${error.message}`; },
  });
  const readyHint = () => flowerScene() ? 'Ready. Click a small flower on the path to pick it for your basket.' : 'Ready. Use WASD, the directional pad, or pick a tile.';
  let trapScenario = false;
  let trapEnabled = true;
  let trapElapsed = 0;
  let nextShot = 1.6;
  let hits = 0;
  let projectiles: { id: string; expires: number }[] = [];
  function resetTrap(resetHits = true): void {
    for (const projectile of projectiles) runtime.removeProjectile(projectile.id);
    projectiles = [];
    trapElapsed = 0;
    nextShot = 1.6;
    if (resetHits) { hits = 0; element('trap-hits').textContent = '0'; }
  }
  const focusWorld = () => element('world').focus({ preventScroll: true });
  const floorId = (cell: Cell) => cell.level ?? 'ground';
  const floorName = (cell: Cell) => runtime.getLevels().find(level => level.id === floorId(cell))?.name ?? floorId(cell);
  function updateActor(cell: Cell, elevation = runtime.getElevation(cell)): void {
    element('actor-cell').textContent = formatCell(cell);
    element('actor-floor').textContent = `${floorName(cell)} / ${Math.round(elevation)} px`;
    if (floorSelect.value === 'follow' && runtime.getViewLevel() !== floorId(cell)) runtime.setViewLevel(floorId(cell));
  }

  function updateSceneUi(scene: Scene, isTrapScene = trapScenario): void {
    resetTrap();
    trapScenario = isTrapScene;
    trapEnabled = isTrapScene;
    element('trap-controls').hidden = !isTrapScene;
    element('trap-readout').hidden = !isTrapScene;
    trapToggle.textContent = 'Trap on';
    trapToggle.setAttribute('aria-pressed', String(trapEnabled));
    element('trap-status').textContent = 'Amber bolts cross the rose-colored lane. First shot in 1.6 seconds.';
    element('actor-state').textContent = 'Grounded';
    collected = 0;
    inventory.restore({ version: 1, items: [] });
    total = scene.entities.filter(entity => isCollectible(entity, scene)).length;
    element('scene-name').textContent = scene.name;
    const cafe = scene.name === 'Sunflower courtyard';
    saveStatus.textContent = cafe ? 'Progress saves after each step and picked flower.' : 'Your Sunflower save stays available here.';
    const calibration = scene.name === 'Sunflower art calibration';
    element('world').setAttribute('aria-label', `Isometric map. Use WASD or arrow keys to walk, Space to jump. ${cafe ? 'Click or tap a small path flower to pick it. Escape cancels picking. ' : ''}Click or tap a tile to find a route. Drag to pan. Use the zoom buttons to resize the view.`);
    element('collection-label').textContent = cafe ? 'Flowers in basket' : 'Lights collected';
    element('flower-action').hidden = !cafe;
    cancelActionTouch.hidden = !cafe;
    updateActionUi(interactions.getState());
    element('jump-hint').innerHTML = cafe || calibration || scene.assets?.images.woodland ? 'Follow the path.<br>Jump for joy.' : 'Hold ↗ + Jump<br>to reach the bridge.';
    element('arrival-cell').textContent = '—';
    element('hover-cell').textContent = 'Point to a tile';
    const actor = scene.controlledId ? runtime.getEntity(scene.controlledId) : undefined;
    floorSelect.replaceChildren(new Option('All floors', 'all'), new Option('Follow traveler', 'follow'));
    for (const level of runtime.getLevels()) floorSelect.add(new Option(level.name, `floor:${level.id}`));
    floorSelect.value = 'all';
    runtime.setViewLevel(null);
    element('actor-cell').textContent = 'No traveler';
    element('actor-floor').textContent = '—';
    if (actor) updateActor(actor);
    element('collection-count').textContent = `0 / ${total}`;
    element('mission').textContent = isTrapScene
      ? 'From the starting tile, hold W ↗ and press Space to leap onto the bridge. Hop over low bolts with Space alone. Turn the trap off to practice.'
      : calibration
      ? 'Walk beside the furniture and around the flowerbeds. Inspect both straight borders, their corner, and the empty stone bed. Zoom in to compare their edges with the paving.'
      : cafe
      ? `Click or tap the ${total} small flowers on the paths. The gardener walks beside each one, picks it, and adds it to your basket. The planted borders stay in the garden.`
      : scene.assets?.images.woodland
      ? 'A mossy clearing, a little ranger, and one lost firefly lantern. Follow the warm path to bring its light home. Notice the swaying cloak and the oak leaves overhead.'
      : scene.levels?.length
      ? `Find ${total} lights above and below the bridge. Walk up either amber stair flight. Two lights share a tile on different floors.`
      : total > 0
      ? `Walk onto all ${total} golden lights to collect them. Your route goes around solid objects.`
      : 'Explore the garden. The traveler finds a way around hedges and stones.';
    element('run-state').textContent = runtime.isPaused ? 'Paused' : 'Running';
    pauseButton.textContent = runtime.isPaused ? 'Resume' : 'Pause';
    updateInventory();
  }

  async function load(scene: unknown, imported = false, saved?: GardenSave): Promise<void> {
    if (loading) return;
    interactions.cancel('scene-loading');
    setLoading(true);
    feedback.textContent = 'Loading scene…';
    try {
      await runtime.loadScene(scene);
      baseline = saved?.state.baseline ?? runtime.serializeScene();
      runtime.resume();
      updateSceneUi(baseline, !saved && !imported && presetSelect.value === 'jump');
      if (saved) {
        inventory.restore(saved.state.inventory);
        collected = inventory.count('flower');
        element('collection-count').textContent = `${collected} / ${total}`;
        presetSelect.value = 'cafe';
        saveStatus.textContent = 'Saved garden restored.';
      }
      if (imported) {
        if (!presetSelect.querySelector('option[value="imported"]')) {
          presetSelect.add(new Option('08 — Imported scene', 'imported'));
        }
        presetSelect.value = 'imported';
      }
      feedback.textContent = imported ? 'Scene imported. Ready to explore.' : readyHint();
    } catch (error) {
      feedback.textContent = `Could not load scene: ${error instanceof Error ? error.message : String(error)}. Your current scene is preserved.`;
    } finally {
      setLoading(false);
      updateActionUi(interactions.getState());
      updateInventory();
      focusWorld();
    }
  }

  runtime.on('hover', ({ cell }) => {
    element('hover-cell').textContent = cell ? `Tile ${formatCell(cell)} · ${floorName(cell)}` : 'Point to a tile';
  });
  runtime.on('tileclick', ({ cell, entityIds }) => {
    if (loading || runtime.isPaused || !baseline.controlledId) return;
    const target = flowerScene() ? entityIds.map(id => runtime.getEntity(id)).find(entity => entity && isCollectible(entity, baseline)) : undefined;
    if (target) {
      if (!interactions.request({ actorId: baseline.controlledId, targetId: target.id, action: flowerAction })) {
        feedback.textContent = 'This flower has no reachable picking spot. Try another flower.';
      }
    } else {
      interactions.cancel('ground-click');
      runtime.moveTo(baseline.controlledId, cell);
    }
  });
  runtime.on('move', ({ id, position, elevation }) => {
    if (id === baseline.controlledId) updateActor(position, elevation);
  });
  runtime.on('jumpstart', ({ id }) => {
    if (id !== baseline.controlledId) return;
    element('actor-state').textContent = 'Airborne';
    feedback.textContent = 'Airborne. Clear the low bolts or reach a higher floor.';
  });
  runtime.on('land', ({ id, cell }) => {
    if (id !== baseline.controlledId) return;
    updateActor(cell);
    element('actor-state').textContent = 'Grounded';
    feedback.textContent = `Landed on ${floorName(cell)} at ${formatCell(cell)}.`;
    saveGarden();
  });
  runtime.on('projectilehit', ({ projectileId, entityId }) => {
    projectiles = projectiles.filter(projectile => projectile.id !== projectileId);
    if (!trapScenario || entityId !== baseline.controlledId) return;
    hits++;
    element('trap-hits').textContent = String(hits);
    element('trap-status').textContent = `Hit ${hits}! Jump as a bolt approaches, or reach the bridge above its path.`;
    feedback.textContent = 'A bolt hit the traveler. Keep practicing — there is no life limit.';
  });
  runtime.on('frame', ({ deltaSeconds }) => {
    if (loading || runtime.isPaused) return;
    const pose = baseline.controlledId ? runtime.getEntityPose(baseline.controlledId) : undefined;
    if (pose) {
      updateActor(pose.position, pose.elevation);
      element('actor-state').textContent = pose.airborne ? 'Airborne' : 'Grounded';
    }
    if (!trapScenario || !trapEnabled) return;
    trapElapsed += deltaSeconds;
    projectiles = projectiles.filter(projectile => projectile.expires > trapElapsed);
    if (trapElapsed >= nextShot) {
      nextShot = trapElapsed + 2.4;
      const id = runtime.spawnProjectile({
        from: { c: 0, r: 6 }, to: { c: 10, r: 6 }, speed: 5,
        elevation: 20, radius: 5, color: 0xef7846, targetId: baseline.controlledId,
      });
      projectiles.push({ id, expires: trapElapsed + 2.1 });
    }
  });
  runtime.on('arrive', ({ id, cell }) => {
    if (id !== baseline.controlledId) return;
    updateActor(cell);
    element('arrival-cell').textContent = formatCell(cell);
    if (flowerScene()) {
      saveGarden();
      if (interactions.getState().phase === 'idle') feedback.textContent = `Arrived at ${formatCell(cell)}. Click a small path flower to pick it.`;
      return;
    }
    const gems = runtime.getEntities().filter(entity =>
      entity.c === cell.c && entity.r === cell.r && floorId(entity) === floorId(cell) && isCollectible(entity, baseline),
    );
    for (const gem of gems) if (runtime.remove(gem.id)) collected++;
    element('collection-count').textContent = `${collected} / ${total}`;
    feedback.textContent = total > 0 && collected === total
      ? 'All lights collected. A little world, a complete adventure.'
      : gems.length > 0 ? 'A little light, collected.' : `Arrived at ${formatCell(cell)}.`;
  });
  runtime.on('blocked', () => { feedback.textContent = 'That tile is blocked or unreachable. Try an open ground tile.'; });
  runtime.on('pausechange', ({ paused }) => {
    if (paused) {
      resetTrap();
      element('trap-status').textContent = 'Paused. Bolts cleared and hits reset.';
    } else if (trapScenario && trapEnabled) {
      element('trap-status').textContent = 'Trap ready. Next bolt in 1.6 seconds.';
    }
    element('run-state').textContent = paused ? 'Paused' : 'Running';
    pauseButton.textContent = paused ? 'Resume' : 'Pause';
    updateActionUi(interactions.getState());
    feedback.textContent = paused ? flowerScene() ? 'Paused. Resume to continue walking or picking.' : 'Paused. Resume to continue walking.'
      : flowerScene() ? 'Running. Pick a tile to walk or a flower to gather.' : 'Running. Pick a tile to walk.';
  });
  runtime.on('error', ({ error }) => { feedback.textContent = `Runtime error: ${error.message}`; });

  cancelAction.addEventListener('click', () => { interactions.cancel('cancel-button'); focusWorld(); });
  cancelActionTouch.addEventListener('click', () => { interactions.cancel('cancel-button'); focusWorld(); });
  const cancelWithEscape = (event: KeyboardEvent) => {
    if (event.key === 'Escape' && interactions.getState().phase !== 'idle') {
      event.preventDefault();
      interactions.cancel('escape');
    }
  };
  element('world').addEventListener('keydown', cancelWithEscape);
  debugToggle.addEventListener('click', () => {
    debugEnabled = !debugEnabled;
    debugToggle.setAttribute('aria-pressed', String(debugEnabled));
    debugPanel.hidden = !debugEnabled;
    debug.setEnabled(debugEnabled);
  });

  pauseButton.addEventListener('click', () => {
    if (runtime.isPaused) { runtime.resume(); focusWorld(); } else runtime.pause();
  });
  trapToggle.addEventListener('click', () => {
    trapEnabled = !trapEnabled;
    resetTrap(false);
    trapToggle.textContent = trapEnabled ? 'Trap on' : 'Trap off';
    trapToggle.setAttribute('aria-pressed', String(trapEnabled));
    element('trap-status').textContent = trapEnabled ? 'Trap ready. Next bolt in 1.6 seconds.' : 'Trap off. Practice your jump to the bridge.';
    focusWorld();
  });
  floorSelect.addEventListener('change', () => {
    const actor = baseline.controlledId ? runtime.getEntity(baseline.controlledId) : undefined;
    runtime.setViewLevel(floorSelect.value === 'all' ? null : floorSelect.value === 'follow' ? actor ? floorId(actor) : 'ground' : floorSelect.value.slice(6));
    focusWorld();
  });
  element('restart').addEventListener('click', () => { void load(baseline).then(saveGarden); });
  saveButton.addEventListener('click', saveGarden);
  async function continueGarden(): Promise<void> {
    if (loading) return;
    try {
      const saved = gardenSave.read();
      if (!saved) { saveStatus.textContent = 'No saved garden yet. Pick a flower to begin.'; return; }
      await load(saved.scene, false, saved);
    } catch (error) {
      saveStatus.textContent = `Could not restore: ${error instanceof Error ? error.message : String(error)}. Current garden kept.`;
    }
  }
  element('load-game').addEventListener('click', () => { void continueGarden(); });
  presetSelect.addEventListener('change', () => {
    if (presetSelect.value !== 'imported') void load(createScene(presetSelect.value as Preset));
  });
  element('fit').addEventListener('click', () => runtime.fit());
  element('zoom-in').addEventListener('click', () => runtime.setCamera({ zoom: runtime.getCamera().zoom * 1.2 }));
  element('zoom-out').addEventListener('click', () => runtime.setCamera({ zoom: runtime.getCamera().zoom / 1.2 }));
  element('export').addEventListener('click', () => {
    const scene = runtime.serializeScene();
    const blob = new Blob([JSON.stringify(scene, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = `${scene.name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '') || 'little-world'}.json`;
    anchor.click();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
    feedback.textContent = 'Scene exported with current entity positions.';
  });
  fileInput.addEventListener('change', async () => {
    const file = fileInput.files?.[0];
    if (!file || loading) return;
    try {
      if (file.size > 5 * 1024 * 1024) throw new Error('Scene files must be smaller than 5 MB');
      const parsed: unknown = JSON.parse(await file.text());
      await load(parsed, true);
    } catch (error) {
      feedback.textContent = `Could not import scene: ${error instanceof Error ? error.message : String(error)}. Your current scene is preserved.`;
    } finally {
      fileInput.value = '';
    }
  });

  updateSceneUi(baseline);
  setLoading(false);
  updateActionUi(interactions.getState());
  updateInventory();
  feedback.textContent = readyHint();
  focusWorld();
  await continueGarden();
  const destroy = () => {
    element('world').removeEventListener('keydown', cancelWithEscape);
    interactions.destroy(); debug.destroy(); jumpButton.destroy(); dpad.destroy(); runtime.destroy();
  };
  window.addEventListener('pagehide', event => { if (!event.persisted) destroy(); }, { once: true });
  if (import.meta.hot) import.meta.hot.dispose(destroy);
}

void start().catch(error => {
  element('run-state').textContent = 'Unavailable';
  feedback.textContent = `Could not start the world: ${error instanceof Error ? error.message : String(error)}. Reload the page to retry.`;
});
