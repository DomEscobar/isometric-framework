import { createRuntime, createDebugOverlay, createDpad, createJumpButton, type Cell } from '../../src/index';
import { createQuayScene } from './scene';
import './style.css';

const destinations: Record<string, { label: string; cell: Cell; arrival: string }> = {
  apothecary: { label: 'Apotheke', cell: { c: 4, r: 5 }, arrival: 'Vor der Apotheke duftet es nach Kräutern.' },
  bridge: { label: 'Über die Brücke', cell: { c: 7, r: 11 }, arrival: 'Ein ruhiger Platz am anderen Ufer.' },
  canal: { label: 'Am Kanal', cell: { c: 11, r: 6 }, arrival: 'Das Wasser glitzert im Spätsommerlicht.' },
};

document.querySelector('#app')!.innerHTML = `
<main class="quay">
  <header class="masthead">
    <div class="wordmark"><span class="eyebrow">Ein kleiner Ort am Wasser</span><h1>Weidenkai<span>.</span></h1></div>
    <nav class="tools" aria-label="Ansicht">
      <button id="pause" type="button" disabled>Pause</button>
      <button id="fit" type="button" disabled>Übersicht</button>
      <button id="debug-toggle" type="button" aria-pressed="false" disabled>Inspizieren</button>
    </nav>
  </header>
  <section class="landscape" aria-label="Weidenkai erkunden">
    <div id="world" tabindex="0" role="application" aria-busy="true" aria-label="Weidenkai. Klicke einen freien Weg zum Gehen. W bewegt nach rechts oben, D nach rechts unten, S nach links unten, A nach links oben. Leertaste zum Springen. Ziehen verschiebt die Karte, Mausrad vergrößert sie."></div>
    <div class="loading" id="loading"><span class="loading-dot"></span>Weidenkai erwacht …</div>
    <aside class="places" aria-label="Spaziergänge">
      <span class="eyebrow">Wohin zieht es dich?</span>
      <div class="destination-list">${Object.entries(destinations).map(([key, place], index) => `<button type="button" data-destination="${key}" disabled><span class="place-number">0${index + 1}</span>${place.label}<span class="place-arrow" aria-hidden="true">↗</span></button>`).join('')}</div>
      <p id="status" role="status">Der Ort wird geladen.</p>
    </aside>
    <div class="map-caption"><span class="season">Spätsommer</span><span id="position">—</span></div>
    <div class="zoom-controls" role="group" aria-label="Kartenvergrößerung"><button id="zoom-out" type="button" aria-label="Karte verkleinern" title="Karte verkleinern" disabled>−</button><button id="zoom-in" type="button" aria-label="Karte vergrößern" title="Karte vergrößern" disabled>+</button></div>
    <div id="debug-panel" hidden></div>
  </section>
  <footer class="explore-bar">
    <div class="walk-help"><span class="eyebrow">Einfach losgehen</span><p class="desktop-help">Klicken oder WASD <span>W ↗ · D ↘ · S ↙ · A ↖</span></p><p class="touch-help">Tippe auf einen Weg<br>oder halte eine Richtung.</p><small>Ziehen zum Umschauen · <span class="desktop-help">Scrollen zum Vergrößern · Leertaste zum Springen</span><span class="touch-help">Zoom mit + / −</span></small></div>
    <div id="touch-controls" aria-label="Bewegung und Sprung"></div>
    <span class="quiet-note">Nimm dir einen Augenblick.</span>
  </footer>
</main>`;

const el = <T extends HTMLElement = HTMLElement>(id: string) => document.getElementById(id) as T;
const lifecycle = new AbortController();
let disposed = false;
let cleanup: (() => void) | undefined;
const dispose = () => {
  if (disposed) return;
  disposed = true;
  lifecycle.abort();
  cleanup?.();
};
window.addEventListener('pagehide', event => { if (!event.persisted) dispose(); }, { signal: lifecycle.signal });
if (import.meta.hot) import.meta.hot.dispose(dispose);

async function start() {
  const runtime = await createRuntime({ container: el('world'), scene: createQuayScene(), background: 0xe8ebde, speed: 3.2, clickToMove: false, jump: { height: 40, duration: .7, distance: 1 } });
  if (disposed) { runtime.destroy(); return; }
  const debug = createDebugOverlay(runtime, { container: el('world'), panel: el('debug-panel') });
  const dpad = createDpad(runtime, el('touch-controls'));
  const jump = createJumpButton(runtime, el('touch-controls'));
  jump.element.textContent = 'Sprung';
  jump.element.setAttribute('aria-label', 'Springen');
  let inspected = false;
  let destination: string | null = null;
  const focus = () => el('world').focus({ preventScroll: true });
  const message = (text: string) => { el('status').textContent = text; };
  const readPosition = () => {
    const actor = runtime.getEntity('traveler');
    if (!actor) return;
    el('position').textContent = `${actor.c}, ${actor.r} · ${actor.level === 'bridge' ? 'Brücke' : 'Ufer'}`;
    el('position').dataset.level = actor.level ?? 'ground';
  };
  const go = (cell: Cell, key: string | null = null) => {
    destination = key;
    const result = runtime.moveTo('traveler', cell);
    if (result === 'started') message(key ? `Auf dem Weg: ${destinations[key]!.label}.` : 'Ein kleiner Spaziergang.');
    else if (result === 'paused') message('Setze den Spaziergang fort, um weiterzugehen.');
    else if (result === 'arrived') message(key ? destinations[key]!.arrival : 'Du bist schon hier.');
    else if (result === 'blocked') message('Hier führt kein begehbarer Weg hin.');
    focus();
  };
  const unsubscribers = [
    runtime.on('tileclick', ({ cell }) => go(cell)),
    runtime.on('move', ({ id }) => { if (id === 'traveler') readPosition(); }),
    runtime.on('arrive', ({ id }) => {
      if (id !== 'traveler') return;
      readPosition();
      message(destination ? destinations[destination]!.arrival : 'Wo soll es als Nächstes hingehen?');
      destination = null;
    }),
    runtime.on('land', ({ id }) => { if (id === 'traveler') readPosition(); }),
    runtime.on('command', ({ id, kind }) => { if (id === 'traveler' && (kind === 'input' || kind === 'jump')) destination = null; }),
    runtime.on('blocked', ({ id }) => { if (id === 'traveler') message('Hier führt kein begehbarer Weg hin.'); }),
    runtime.on('pausechange', ({ paused }) => {
      el('pause').textContent = paused ? 'Weiter' : 'Pause';
      el('pause').setAttribute('aria-pressed', String(paused));
      message(paused ? 'Der Augenblick bleibt stehen.' : 'Der Spaziergang geht weiter.');
    }),
    runtime.on('error', ({ error }) => message(`Der Spaziergang wurde unterbrochen: ${error.message}`)),
  ];
  document.querySelectorAll<HTMLButtonElement>('[data-destination]').forEach(button => {
    button.addEventListener('click', () => { const key = button.dataset.destination!; go(destinations[key]!.cell, key); }, { signal: lifecycle.signal });
  });
  el('pause').addEventListener('click', () => { if (runtime.isPaused) runtime.resume(); else runtime.pause(); focus(); }, { signal: lifecycle.signal });
  el('fit').addEventListener('click', () => { runtime.fit(); focus(); }, { signal: lifecycle.signal });
  const zoom = (factor: number) => {
    const camera = runtime.getCamera(), world = el('world');
    const nextZoom = Math.max(.05, Math.min(4, camera.zoom * factor));
    const ratio = nextZoom / camera.zoom, centerX = world.clientWidth / 2, centerY = world.clientHeight / 2;
    runtime.setCamera({ zoom: nextZoom, x: centerX + (camera.x - centerX) * ratio, y: centerY + (camera.y - centerY) * ratio });
    focus();
  };
  el('zoom-in').addEventListener('click', () => zoom(1.3), { signal: lifecycle.signal });
  el('zoom-out').addEventListener('click', () => zoom(1 / 1.3), { signal: lifecycle.signal });
  el('debug-toggle').addEventListener('click', () => {
    inspected = !inspected;
    debug.setEnabled(inspected);
    el('debug-toggle').setAttribute('aria-pressed', String(inspected));
  }, { signal: lifecycle.signal });
  cleanup = () => { unsubscribers.forEach(off => off()); debug.destroy(); dpad.destroy(); jump.destroy(); runtime.destroy(); };
  el('world').setAttribute('aria-busy', 'false');
  el('loading').hidden = true;
  document.querySelectorAll<HTMLButtonElement>('.tools button, .zoom-controls button, [data-destination]').forEach(button => { button.disabled = false; });
  readPosition();
  message('Folge den Wegen, über die Brücke und ans Wasser.');
  focus();
}

void start().catch(error => {
  if (disposed) return;
  el('world').setAttribute('aria-busy', 'false');
  el('loading').hidden = true;
  el('status').textContent = `Weidenkai konnte nicht geladen werden: ${error instanceof Error ? error.message : String(error)}`;
});
