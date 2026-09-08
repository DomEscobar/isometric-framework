import { createRuntime, createDebugOverlay, createDpad, createJumpButton, type Cell } from '../../src/index';
import { createAutumnScene } from './scene';
import './style.css';

const destinations: Record<string, { label: string; cell: Cell; arrival: string }> = {
  north: { label: 'Zum Waldweg', cell: { c: 7, r: 6 }, arrival: 'Goldene Blätter rascheln am alten Waldweg.' },
  bridge: { label: 'Auf die Brücke', cell: { c: 10, r: 11, level: 'bridge' }, arrival: 'Unter dir zieht der Fluss langsam vorbei.' },
  south: { label: 'Zum anderen Ufer', cell: { c: 13, r: 17 }, arrival: 'Am anderen Ufer liegt der Herbst ganz still.' },
};

document.querySelector('#app')!.innerHTML = `
<main class="crossing">
  <div id="world" tabindex="0" role="application" aria-busy="true" aria-label="Goldlaub erkunden. Klicke einen Weg zum Gehen. W rechts oben, D rechts unten, S links unten, A links oben. Leertaste springt. Ziehen verschiebt die Ansicht."></div>
  <header class="masthead"><div class="wordmark"><span>Ein Nachmittag im Oktober</span><h1>Goldlaub</h1></div><nav class="tools" aria-label="Ansicht"><button id="pause" disabled>Pause</button><button id="fit" disabled>Ansicht</button><button id="debug-toggle" aria-pressed="false" disabled>Inspizieren</button></nav></header>
  <div id="loading" class="loading"><span></span>Der Wald erwacht …</div>
  <aside class="journey" aria-label="Spaziergänge"><nav>${Object.entries(destinations).map(([key, value]) => `<button data-destination="${key}" disabled>${value.label}<span aria-hidden="true">↗</span></button>`).join('')}</nav><p id="status" role="status">Der Wald wird geladen.</p></aside>
  <div class="map-tools"><span id="position">—</span><div class="zoom-controls" role="group" aria-label="Vergrößerung"><button id="zoom-out" aria-label="Verkleinern" disabled>−</button><button id="zoom-in" aria-label="Vergrößern" disabled>+</button></div></div>
  <p class="walk-hint">Klicken oder WASD <span>W ↗ · D ↘ · S ↙ · A ↖</span></p>
  <div id="touch-controls" aria-label="Bewegung und Sprung"></div>
  <div id="debug-panel" hidden></div>
</main>`;

const el = <T extends HTMLElement = HTMLElement>(id: string) => document.getElementById(id) as T;
const lifecycle = new AbortController();
let disposed = false;
let cleanup: (() => void) | undefined;
const dispose = () => { if (disposed) return; disposed = true; lifecycle.abort(); cleanup?.(); };
window.addEventListener('pagehide', event => { if (!event.persisted) dispose(); }, { signal: lifecycle.signal });
if (import.meta.hot) import.meta.hot.dispose(dispose);

async function start() {
  const runtime = await createRuntime({ container: el('world'), scene: createAutumnScene(), background: 0x31392a, speed: 3.2, clickToMove: false, jump: { height: 40, duration: .7, distance: 1 } });
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
  const compose = () => {
    const world = el('world');
    // A composed view of the crossing. Pan and zoom remain freely available.
    const zoom = world.clientWidth < 650 ? Math.min(1.15, world.clientWidth / 410) : Math.min(2.4, world.clientWidth / 580);
    runtime.setCamera({ zoom, x: world.clientWidth * .55 - 704 * zoom, y: world.clientHeight * .40 + 48 * zoom });
  };
  const go = (cell: Cell, key: string | null = null) => {
    destination = key;
    const result = runtime.moveTo('traveler', cell);
    if (result === 'started') message(key ? `${destinations[key]!.label} …` : 'Ein kleiner Spaziergang.');
    else if (result === 'paused') message('Setze den Spaziergang fort, um weiterzugehen.');
    else if (result === 'arrived') message(key ? destinations[key]!.arrival : 'Du bist schon hier.');
    else if (result === 'blocked') message('Hier führt kein begehbarer Weg hin.');
    focus();
  };
  let previousPose = runtime.getEntityPose('traveler');
  const followOnSmallScreens = () => {
    const pose = runtime.getEntityPose('traveler'), prior = previousPose;
    previousPose = pose;
    if (!pose || !prior || el('world').clientWidth >= 650) return;
    if (pose.position.c === prior.position.c && pose.position.r === prior.position.r && pose.elevation === prior.elevation) return;
    // Follow only actual motion. Idle panning and the initial composed view stay
    // available; the lower HUD is outside the actor's comfortable screen area.
    const world = el('world'), camera = runtime.getCamera();
    const x = (pose.position.c + pose.position.r) * 32 * camera.zoom + camera.x;
    const y = ((pose.position.r - pose.position.c) * 16 - pose.elevation) * camera.zoom + camera.y;
    const targetX = Math.max(world.clientWidth * .22, Math.min(world.clientWidth * .78, x));
    const targetY = Math.max(world.clientHeight * .22, Math.min(world.clientHeight * .58, y));
    if (targetX !== x || targetY !== y) runtime.setCamera({ ...camera, x: camera.x + targetX - x, y: camera.y + targetY - y });
  };
  const unsubscribe = [
    runtime.on('frame', followOnSmallScreens),
    runtime.on('tileclick', ({ cell }) => go(cell)),
    runtime.on('move', ({ id }) => { if (id === 'traveler') readPosition(); }),
    runtime.on('arrive', ({ id }) => { if (id !== 'traveler') return; readPosition(); message(destination ? destinations[destination]!.arrival : 'Folge dem Fluss oder dem goldenen Laub.'); destination = null; }),
    runtime.on('land', ({ id }) => { if (id === 'traveler') readPosition(); }),
    runtime.on('command', ({ id, kind }) => { if (id === 'traveler' && (kind === 'input' || kind === 'jump')) destination = null; }),
    runtime.on('blocked', ({ id }) => { if (id === 'traveler') message('Hier führt kein begehbarer Weg hin.'); }),
    runtime.on('pausechange', ({ paused }) => { el('pause').textContent = paused ? 'Weiter' : 'Pause'; el('pause').setAttribute('aria-pressed', String(paused)); message(paused ? 'Ein stiller Augenblick.' : 'Der Spaziergang geht weiter.'); }),
    runtime.on('error', ({ error }) => message(`Der Spaziergang wurde unterbrochen: ${error.message}`)),
  ];
  document.querySelectorAll<HTMLButtonElement>('[data-destination]').forEach(button => button.addEventListener('click', () => { const key = button.dataset.destination!; go(destinations[key]!.cell, key); }, { signal: lifecycle.signal }));
  el('pause').addEventListener('click', () => { if (runtime.isPaused) runtime.resume(); else runtime.pause(); focus(); }, { signal: lifecycle.signal });
  el('fit').addEventListener('click', () => { compose(); focus(); }, { signal: lifecycle.signal });
  const zoomBy = (factor: number) => { const camera = runtime.getCamera(), world = el('world'); const zoom = Math.max(.25, Math.min(4, camera.zoom * factor)), ratio = zoom / camera.zoom; runtime.setCamera({ zoom, x: world.clientWidth / 2 + (camera.x - world.clientWidth / 2) * ratio, y: world.clientHeight / 2 + (camera.y - world.clientHeight / 2) * ratio }); focus(); };
  el('zoom-in').addEventListener('click', () => zoomBy(1.25), { signal: lifecycle.signal });
  el('zoom-out').addEventListener('click', () => zoomBy(.8), { signal: lifecycle.signal });
  el('debug-toggle').addEventListener('click', () => { inspected = !inspected; debug.setEnabled(inspected); el('debug-toggle').setAttribute('aria-pressed', String(inspected)); }, { signal: lifecycle.signal });
  window.addEventListener('resize', compose, { signal: lifecycle.signal });
  cleanup = () => { unsubscribe.forEach(off => off()); debug.destroy(); dpad.destroy(); jump.destroy(); runtime.destroy(); };
  compose();
  el('world').setAttribute('aria-busy', 'false');
  el('loading').hidden = true;
  document.querySelectorAll<HTMLButtonElement>('.tools button, .zoom-controls button, [data-destination]').forEach(button => { button.disabled = false; });
  readPosition(); message('Über die alte Brücke, dem Herbst entgegen.'); focus();
}

void start().catch(error => { if (disposed) return; el('world').setAttribute('aria-busy', 'false'); el('loading').hidden = true; el('status').textContent = `Goldlaub konnte nicht geladen werden: ${error instanceof Error ? error.message : String(error)}`; });
