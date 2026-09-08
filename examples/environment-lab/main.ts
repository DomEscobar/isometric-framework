import { createRuntime, createDebugOverlay, createDpad, createJumpButton } from '../../src/index';
import { createEnvironmentScene, type Variant } from './variants';
import './style.css';

document.querySelector('#app')!.innerHTML = `
<main><header><a href="../../">little worlds.</a><span>ENVIRONMENT LAB</span></header>
<h1>Water & stone.</h1><p class="intro">Animated water, a fountain, and a bridge you can cross or walk beneath.</p>
<section class="workspace"><div><div id="world" tabindex="0" role="application" aria-label="Environment map. WASD walks along tiles. Space jumps. Drag to pan."></div>
<div class="touch"><div id="jump"></div><div id="pad"></div></div></div>
<aside><label for="variant">Workflow variant</label><select id="variant"><option value="generated-layered" selected>Generated · Fixed stone + splashes</option><option value="generated-registered">Generated · Registered frames</option><option value="generated-raw">Generated · Raw sheet assumptions</option><optgroup label="Earlier geometric fixtures"><option value="accepted">Combined calibration</option><option value="a">A · Animation first</option><option value="b">B · Shared contract first</option><option value="c">C · Traversal and parts first</option></optgroup></select>
<p class="note">Generated PNG artwork, measured in the actual renderer. Compare untreated sheets, corrected frame registration, and a fixed fountain with animated splashes.</p>
<div class="buttons"><button id="pause">Pause</button><button id="restart">Reset scene</button></div>
<label for="floor">Show floor</label><select id="floor"><option value="all">All floors</option><option value="ground">Ground / underpass</option><option value="bridge">Bridge</option></select>
<div class="buttons"><button id="cross">Cross bridge</button><button id="under">Walk underneath</button></div>
<p id="position" role="status"></p><p id="status" role="status">W ↗ · D ↘ · S ↙ · A ↖. Click a tile to walk.</p>
<div class="buttons"><button id="fit">Fit map</button><button id="zoom">Zoom in</button><button id="debug-toggle" aria-pressed="false">Inspect</button></div>
<div id="debug-panel" hidden></div><p class="note">Ground view reveals the towpath. Rails reserve whole edge rows. The raw variant deliberately exposes sheet drift; registered fountain frames still change stone texture. Fixed stone keeps the original jets static while splash ripples animate.</p>
</aside></section></main>`;
const el = <T extends HTMLElement = HTMLElement>(id: string) => document.getElementById(id) as T;

async function start() {
  const runtime = await createRuntime({ container: el('world'), scene: createEnvironmentScene('generated-layered'), background: 0xe9eee2, speed: 4 });
  const debug = createDebugOverlay(runtime, { container: el('world'), panel: el('debug-panel') });
  const dpad = createDpad(runtime, el('pad')), jump = createJumpButton(runtime, el('jump'));
  Object.assign(jump.element.style, { right: '6px', bottom: '6px' });
  const variant = el<HTMLSelectElement>('variant'), floor = el<HTMLSelectElement>('floor');
  let loading = false, inspected = false, underEntrance = false;
  const focus = () => el('world').focus({ preventScroll: true });
  runtime.on('frame', () => {
    const pose = runtime.getEntityPose('traveler');
    if (pose) el('position').textContent = `${pose.position.c.toFixed(1)}, ${pose.position.r.toFixed(1)} · ${pose.position.level ?? 'ground'} · ${pose.elevation.toFixed(0)} px`;
  });
  runtime.on('arrive', ({ id, cell }) => {
    if (id === 'traveler' && underEntrance && cell.c === 4 && cell.r === 7 && (cell.level ?? 'ground') === 'ground') {
      underEntrance = false; runtime.moveTo(id, { c: 4, r: 3 });
    }
  });
  runtime.on('tileclick', () => { underEntrance = false; });
  runtime.on('blocked', () => { el('status').textContent = 'Blocked here. Use the center of the deck or the dry towpath.'; });
  runtime.on('error', ({ error }) => { el('status').textContent = error.message; });
  async function load() {
    if (loading) return;
    loading = true; underEntrance = false;
    try { await runtime.loadScene(createEnvironmentScene(variant.value as Variant)); floor.value = 'all'; runtime.resume(); el('pause').textContent = 'Pause'; }
    catch (error) { el('status').textContent = String(error); }
    finally { loading = false; focus(); }
  }
  variant.addEventListener('change', () => { void load(); });
  el('restart').addEventListener('click', () => { void load(); });
  el('pause').addEventListener('click', () => { if (runtime.isPaused) runtime.resume(); else runtime.pause(); el('pause').textContent = runtime.isPaused ? 'Resume' : 'Pause'; });
  floor.addEventListener('change', () => { runtime.setViewLevel(floor.value === 'all' ? null : floor.value); focus(); });
  el('cross').addEventListener('click', () => { underEntrance = false; floor.value = 'all'; runtime.setViewLevel(null); runtime.moveTo('traveler', { c: 12, r: 5 }); focus(); });
  el('under').addEventListener('click', () => { underEntrance = true; floor.value = 'ground'; runtime.setViewLevel('ground'); runtime.moveTo('traveler', { c: 4, r: 7 }); focus(); });
  el('fit').addEventListener('click', () => runtime.fit());
  el('zoom').addEventListener('click', () => runtime.setCamera({ zoom: runtime.getCamera().zoom * 1.2 }));
  el('debug-toggle').addEventListener('click', () => { inspected = !inspected; debug.setEnabled(inspected); el('debug-toggle').setAttribute('aria-pressed', String(inspected)); });
  const destroy = () => { debug.destroy(); dpad.destroy(); jump.destroy(); runtime.destroy(); };
  window.addEventListener('pagehide', event => { if (!event.persisted) destroy(); }, { once: true });
  if (import.meta.hot) import.meta.hot.dispose(destroy);
  focus();
}
void start().catch(error => { el('status').textContent = String(error); });
