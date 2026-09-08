import { createRuntime, createDebugOverlay, createDpad, type Cell } from '../../src/index';
import { ACTOR_ID, createAutotileScene, createLabState, toggleBed, type LabState, type Preset } from './scene';
import tileset from './art/tileset.json';
import atlasUrl from './art/bed-atlas.png?url';
import './style.css';

document.querySelector('#app')!.innerHTML = `
<main>
  <header><a href="../../">little worlds.</a><span>AUTOTILE LAB</span></header>
  <h1>One tile. Many gardens.</h1>
  <p class="intro">Paint a flowerbed. Its edges and corners find their place.</p>
  <section class="workspace">
    <div class="map-shell">
      <div id="world" tabindex="0" role="application" aria-label="Autotile garden. Click grass to walk, or enable Paint tiles to edit. WASD moves along tile axes. Drag to pan and scroll to zoom."></div>
      <div id="touch"><span>Hold a direction<br>to explore.</span><div id="pad"></div></div>
    </div>
    <aside>
      <label for="preset">Start with a shape</label>
      <select id="preset"><option value="straight">Straight bed</option><option value="l">L-shaped bed</option><option value="rectangle">Filled rectangle</option><option value="ring" selected>Hollow ring</option><option value="diagonal">Diagonal pair</option></select>
      <button id="edit" class="primary" aria-pressed="false">Paint tiles</button>
      <p id="mode-help" class="note">Click grass to walk. Beds block the path.</p>
      <p id="status" role="status">Loading the garden…</p>
      <div class="readout"><span id="count"></span><p id="selection">Click a tile to inspect its connection.</p><p id="position"></p></div>
      <div class="buttons"><button id="fit">Fit map</button><button id="pause">Pause</button><button id="reset">Reset shape</button></div>
      <button id="debug-toggle" aria-pressed="false">Inspect footprints</button>
      <div id="debug-panel" hidden></div>
      <p class="note">W ↗ · D ↘ · S ↙ · A ↖<br>Drag to pan · Scroll to zoom</p>
      <p class="caption">47 connections, one shared material.<br>Exposed soil keeps every join visible.</p>
    </aside>
  </section>
</main>`;
const el = <T extends HTMLElement = HTMLElement>(id: string) => document.getElementById(id) as T;
const message = (value: string) => { el('status').textContent = value; };

async function start() {
  let state = createLabState(), built = createAutotileScene(state, tileset, atlasUrl);
  const runtime = await createRuntime({ container: el('world'), scene: built.scene, background: 0xe8eddf, speed: 3, clickToMove: false });
  const debug = createDebugOverlay(runtime, { container: el('world'), panel: el('debug-panel') });
  const dpad = createDpad(runtime, el('pad'));
  let editing = false, loading = false, inspected = false, destroyed = false;
  let selected: Cell | null = null, preset: Preset = 'ring';
  const focus = () => el('world').focus({ preventScroll: true });
  const refresh = () => {
    el('count').textContent = `${state.beds.length} bed tiles · ${new Set(built.resolution.tiles.map(tile => tile.mask)).size} active variants`;
    if (selected) {
      const tile = built.resolution.tiles.find(item => item.cell.c === selected!.c && item.cell.r === selected!.r);
      el('selection').textContent = `Tile ${selected.c}, ${selected.r} · ${tile ? `mask ${tile.mask} · ${tile.variant}` : 'grass · walkable'}`;
    }
    const actor = runtime.getEntity(ACTOR_ID);
    if (actor) el('position').textContent = `Traveler ${actor.c}, ${actor.r}`;
  };
  const busy = (value: boolean) => {
    loading = value;
    el('world').setAttribute('aria-busy', String(value));
    document.querySelectorAll<HTMLButtonElement | HTMLSelectElement>('aside button, aside select').forEach(control => { control.disabled = value; });
  };
  async function load(next: LabState, reset = false): Promise<boolean> {
    if (loading || destroyed) return false;
    busy(true);
    const camera = runtime.getCamera(), paused = runtime.isPaused;
    runtime.pause();
    try {
      const candidate = createAutotileScene(next, tileset, atlasUrl);
      await runtime.loadScene(candidate.scene);
      if (destroyed) return false;
      state = next; built = candidate;
      if (!reset) runtime.setCamera(camera);
      runtime.setControlled(editing ? null : ACTOR_ID);
      refresh();
      message(editing ? 'Click a tile to add or remove a bed.' : 'Click grass to walk around the beds.');
      return true;
    } catch (error) { if (!destroyed) message(String(error)); return false; }
    finally { if (!destroyed) { if (!paused) runtime.resume(); busy(false); focus(); } }
  }
  runtime.on('tileclick', ({ cell }) => {
    if (loading) return;
    selected = cell; refresh();
    if (editing) {
      try { void load(toggleBed(state, cell)); }
      catch (error) { message(error instanceof Error ? error.message : String(error)); }
    } else {
      const result = runtime.moveTo(ACTOR_ID, cell);
      if (result === 'started') message(`Walking to ${cell.c}, ${cell.r}.`);
      else if (result === 'paused') message('Resume to walk.');
    }
  });
  runtime.on('arrive', ({ id }) => { if (id === ACTOR_ID) { refresh(); message('Arrived. Choose another tile.'); } });
  runtime.on('move', () => { const actor = runtime.getEntity(ACTOR_ID); if (actor) el('position').textContent = `Traveler ${actor.c}, ${actor.r}`; });
  runtime.on('blocked', () => message('No walking route to that tile. Beds are solid.'));
  runtime.on('error', ({ error }) => message(error.message));
  el('edit').addEventListener('click', () => {
    if (loading) return;
    runtime.stop(ACTOR_ID);
    const actor = runtime.getEntity(ACTOR_ID)!;
    state = { ...state, actor: { c: actor.c, r: actor.r } };
    editing = !editing;
    runtime.setControlled(editing ? null : ACTOR_ID);
    el('edit').setAttribute('aria-pressed', String(editing));
    el('edit').textContent = editing ? 'Finish painting' : 'Paint tiles';
    el('mode-help').textContent = editing ? 'Click to add or remove a bed. The traveler stays in place.' : 'Click grass to walk. Beds block the path.';
    el('touch').classList.toggle('editing', editing);
    message(editing ? 'Paint mode. The traveler’s tile is protected.' : 'Play mode. Click grass to walk.');
    refresh(); focus();
  });
  el<HTMLSelectElement>('preset').addEventListener('change', async () => {
    const select = el<HTMLSelectElement>('preset'), nextPreset = select.value as Preset;
    if (await load(createLabState(nextPreset), true)) { preset = nextPreset; selected = null; el('selection').textContent = 'Click a tile to inspect its connection.'; }
    else select.value = preset;
  });
  el('reset').addEventListener('click', () => { void load(createLabState(preset), true); });
  el('fit').addEventListener('click', () => { runtime.fit(); focus(); });
  el('pause').addEventListener('click', () => { if (runtime.isPaused) runtime.resume(); else runtime.pause(); el('pause').textContent = runtime.isPaused ? 'Resume' : 'Pause'; focus(); });
  el('debug-toggle').addEventListener('click', () => { inspected = !inspected; debug.setEnabled(inspected); el('debug-toggle').setAttribute('aria-pressed', String(inspected)); });
  const destroy = () => { if (destroyed) return; destroyed = true; debug.destroy(); dpad.destroy(); runtime.destroy(); };
  window.addEventListener('pagehide', event => { if (!event.persisted) destroy(); }, { once: true });
  if (import.meta.hot) import.meta.hot.dispose(destroy);
  refresh(); message('Click grass to walk around the beds.'); focus();
}
void start().catch(error => { message(`The garden could not load: ${String(error)}`); });
