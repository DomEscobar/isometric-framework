import { createRequire } from 'node:module';
import { mkdir, writeFile } from 'node:fs/promises';
import { resolve } from 'node:path';
import assert from 'node:assert/strict';

const require = createRequire(resolve(process.env.RUNTIME_QA_PACKAGE ?? 'package.json'));
const { chromium } = require('playwright');
const output = resolve(process.env.RUNTIME_QA_OUTPUT ?? 'test-results/levels-api');
await mkdir(output, { recursive: true });
const browser = await chromium.launch({ headless: true });
const context = await browser.newContext({ viewport: { width: 1100, height: 850 }, hasTouch: true });
const page = await context.newPage();
const errors = [], results = [];
page.on('pageerror', error => errors.push(error.message));
await page.route('**/levels-qa-host', route => route.fulfill({ contentType: 'text/html', body: '<!doctype html><html><body style="margin:0"><button id="outside">Outside game</button></body></html>' }));
await page.goto(`${process.env.RUNTIME_QA_URL ?? 'http://127.0.0.1:4175'}/levels-qa-host`);
// Browser-side handles are API instrumentation, not production QA globals.
const fixture = await page.evaluateHandle(async () => {
  const { Runtime, createJoystick, createDpad } = await import('/src/index.ts');
  const owned = [];
  const scene = () => ({ version: 2, levels: [], links: [], name: 'levels fixture', tileWidth: 64, tileHeight: 32,
    map: Array.from({ length: 9 }, () => Array(9).fill('grass')),
    tiles: { grass: { color: 0x719654 }, upper: { color: 0xf0bd67 }, cliff: { color: 0x224499, elevation: 32 } },
    entityTypes: { actor: { visual: { kind: 'actor', color: 0xdf3355 }, blocking: true }, wall: { visual: { kind: 'box' }, blocking: true } },
    entities: [{ id: 'actor', type: 'actor', c: 4, r: 4 }], controlledId: 'actor', diagonal: true });
  const stacked = () => { const data = scene(); data.levels = [{ id: 'bridge', name: 'Bridge', height: 32, map: Array.from({ length: 9 }, () => Array(9).fill('upper')) }]; data.links = [{ from: { c: 4, r: 4 }, to: { c: 5, r: 4, level: 'bridge' } }]; return data; };
  return { scene, stacked, owned,
    async spawn(data = scene(), options = {}) {
      const host = document.createElement('div'); host.id = `game-${owned.length}`; host.style.cssText = 'position:relative;width:520px;height:390px;display:inline-block;vertical-align:top'; document.body.append(host);
      const runtime = new Runtime({ container: host, scene: data, autoStart: false, input: false, speed: 1, ...options });
      const item = { host, runtime, joystick: null }; owned.push(item); await runtime.ready; return item;
    },
    stick(item) { item.joystick = createJoystick(item.runtime, item.host); item.joystick.element.addEventListener('pointerdown', event => { item.lastPointerId = event.pointerId; }); return item.joystick; },
    pad(item) { item.dpad = createDpad(item.runtime, item.host); item.pointerTrace = []; item.dpad.element.addEventListener('pointerdown', event => { item.lastDpadPointer = { id: event.pointerId, button: event.target.closest('button') }; }); for (const name of ['pointerdown', 'pointerup', 'pointercancel', 'lostpointercapture']) item.dpad.element.addEventListener(name, event => item.pointerTrace.push({ name, id: event.pointerId, key: event.target.closest('button')?.dataset.key })); return item.dpad; },
    cleanup() { for (const item of owned) { try { item.joystick?.destroy(); item.dpad?.destroy(); item.runtime.destroy(); } catch {} item.host.remove(); } owned.length = 0; },
  };
});
const run = async (name, test) => {
  try { const evidence = await test(); results.push({ name, pass: true, evidence }); }
  catch (error) { results.push({ name, pass: false, error: error.stack }); await page.screenshot({ path: resolve(output, `failure-${results.length}.png`) }).catch(() => {}); }
  finally { await fixture.evaluate(f => f.cleanup()); await page.keyboard.up('KeyW'); await page.keyboard.up('KeyA'); await page.keyboard.up('KeyS'); await page.keyboard.up('KeyD'); }
};
const api = (name, test) => run(name, () => fixture.evaluate(test));

await api('stacked occupancy, stair paths both directions and serialization', async f => {
  const data = f.stacked(); data.entities.push({ id: 'upstairs', type: 'actor', c: 4, r: 4, level: 'bridge' });
  const { runtime: r } = await f.spawn(data); const check = (x, message) => { if (!x) throw Error(message); };
  check(r.getEntity('actor').level === undefined && r.getEntity('upstairs').level === 'bridge', 'overlapping actors retain floors');
  const path = r.findPath('actor', { c: 6, r: 4, level: 'bridge' }); check(path?.some(cell => cell.level === 'bridge'), 'stairs path reaches upper floor');
  r.moveTo('actor', { c: 6, r: 4, level: 'bridge' }); r.step(10); check(r.getEntity('actor').level === 'bridge', 'upstairs arrival');
  r.moveTo('actor', { c: 4, r: 4 }); r.step(10); check(r.getEntity('actor').level === undefined, 'downstairs arrival');
  const saved = r.serializeScene(); await r.loadScene(JSON.parse(JSON.stringify(saved))); check(JSON.stringify(saved) === JSON.stringify(r.serializeScene()), 'exact JSON roundtrip');
  const broken = structuredClone(saved); broken.levels[0].map[0][0] = 'missing'; let rejected = false; try { await r.loadScene(broken); } catch { rejected = true; }
  check(rejected && JSON.stringify(saved) === JSON.stringify(r.serializeScene()), 'invalid load preserves active state'); return { path, levels: r.getLevels() };
});
await api('highest visible floor picking and cutaway change rendered pixels', async f => {
  const { runtime: r, host } = await f.spawn(f.stacked()); const point = r.cellToScreen({ c: 4, r: 4, level: 'bridge' });
  const all = r.pick(point); if (all?.level !== 'bridge') throw Error('all-floor picking must choose bridge');
  const capture = () => { r.step(0); const source = host.querySelector('canvas'); const copy = document.createElement('canvas'); copy.width = source.width; copy.height = source.height; const ctx = copy.getContext('2d'); ctx.drawImage(source, 0, 0); return Array.from(ctx.getImageData(0, 0, copy.width, copy.height).data); };
  const before = capture(); r.setViewLevel('ground'); const ground = r.pick(r.cellToScreen({ c: 4, r: 4 })); const after = capture();
  if (ground?.c !== 4 || ground?.r !== 4 || ground.level) throw Error('ground scoped picking');
  const changed = before.reduce((sum, value, i) => sum + Number(value !== after[i]), 0); if (changed < 100) throw Error('cutaway did not affect rendered pixels');
  r.setViewLevel('bridge'); const upper = r.pick(point); if (upper?.level !== 'bridge') throw Error('bridge scoped picking');
  return { all, ground, upper, changedPixelChannels: changed };
});
await api('stair interpolation rises and descends continuously', async f => {
  const { runtime: r } = await f.spawn(f.stacked()); const moves = []; r.on('move', event => moves.push(event));
  r.moveTo('actor', { c: 5, r: 4, level: 'bridge' }); r.step(Math.SQRT2 / 2);
  if (Math.abs(moves.at(-1).elevation - 16) > 1e-7 || r.getEntity('actor').level) throw Error('ascending interpolation or floor occupancy');
  r.step(Math.SQRT2 / 2); if (r.getEntity('actor').level !== 'bridge') throw Error('upper arrival');
  r.moveTo('actor', { c: 4, r: 4 }); r.step(Math.SQRT2 / 2); if (Math.abs(moves.at(-1).elevation - 16) > 1e-7) throw Error('descending interpolation');
  r.step(1); if (r.getEntity('actor').level) throw Error('ground arrival'); return moves;
});
await api('direct neutral completes half-step only and held input continues', async f => {
  const { runtime: r } = await f.spawn(); r.setMoveInput({ x: 1, y: -1 }); r.step(.5);
  if (r.getEntity('actor').c !== 4) throw Error('integer occupancy changed midstep');
  r.setMoveInput(null); r.step(20); if (r.getEntity('actor').c !== 5 || r.getEntity('actor').r !== 4) throw Error('neutral continued past active step');
  r.step(20); if (r.getEntity('actor').c !== 5) throw Error('neutral resumed movement');
  r.setMoveInput({ x: 1, y: -1 }); r.step(2); if (r.getEntity('actor').c !== 7) throw Error('held direction did not continue'); return r.getEntity('actor');
});
for (const obstacle of ['corner', 'hole', 'cliff']) await run(`direct ${obstacle} blocks without detour or falling`, () => fixture.evaluate(async (f, obstacle) => {
  const data = obstacle === 'hole' ? f.stacked() : f.scene();
  if (obstacle === 'corner') data.entities.push({ id: 'wall', type: 'wall', c: 5, r: 4 });
  if (obstacle === 'hole') { data.entities[0].level = 'bridge'; data.levels[0].map[4][5] = null; data.links = []; }
  if (obstacle === 'cliff') data.map[4][5] = 'cliff';
  const { runtime: r } = await f.spawn(data); const initial = r.getEntity('actor');
  r.setMoveInput(obstacle === 'corner' ? { x: 1, y: 0 } : { x: 1, y: -1 }); r.step(20);
  if (JSON.stringify(initial) !== JSON.stringify(r.getEntity('actor'))) throw Error(`${obstacle} changed occupancy`); return initial;
}, obstacle));

// Keep DOM interactions native: page.keyboard, mouse, focus, and CDP touch.
const setup = async ({ second = false, joystick = false, dpad = false } = {}) => fixture.evaluate(async (f, options) => {
  await f.spawn(undefined, { input: true }); if (options.second) await f.spawn(undefined, { input: true });
  if (options.joystick) f.stick(f.owned[0]);
  if (options.dpad) f.pad(f.owned[0]);
}, { second, joystick, dpad });
const step = seconds => fixture.evaluate((f, delta) => { for (const item of f.owned) item.runtime.step(delta); return f.owned.map(item => item.runtime.getEntity('actor')); }, seconds);
const pos = entity => ({ c: entity.c, r: entity.r, ...(entity.level ? { level: entity.level } : {}) });
// Independent ground truth transcribed from Client/engine/move-handler.js:
// triggerPress (lines 81-97) binds W/D/S/A to UP/RIGHT/DOWN/LEFT;
// handlePress (lines 152-171) applies c+1 / r+1 / c-1 / r-1 respectively.
// Keep this literal compatibility fixture independent of Runtime/src/controls.ts.
const originalMovement = [
  { key: 'KeyW', arrow: 'ArrowUp', target: { c: 5, r: 4 }, screen: 'northeast' },
  { key: 'KeyD', arrow: 'ArrowRight', target: { c: 4, r: 5 }, screen: 'southeast' },
  { key: 'KeyS', arrow: 'ArrowDown', target: { c: 3, r: 4 }, screen: 'southwest' },
  { key: 'KeyA', arrow: 'ArrowLeft', target: { c: 4, r: 3 }, screen: 'northwest' },
];
for (const { key, target } of originalMovement) {
  await run(`focused ${key} grid-axis movement, repeat and release`, async () => {
    await setup(); await page.locator('#game-0').focus(); await page.keyboard.down(key); await page.keyboard.down(key); await step(.5); await page.keyboard.up(key);
    const [end] = await step(15); assert.deepEqual(pos(end), target); const [later] = await step(10); assert.deepEqual(pos(later), target); return target;
  });
}
await run('opposite keys cancel and releasing one restores remaining key', async () => {
  await setup(); await page.locator('#game-0').focus(); await page.keyboard.down('KeyW'); await page.keyboard.down('KeyS'); assert.deepEqual(pos((await step(2))[0]), { c: 4, r: 4 });
  await page.keyboard.up('KeyS'); await step(.2); await page.keyboard.up('KeyW'); const result = (await step(10))[0]; assert.deepEqual(pos(result), { c: 5, r: 4 }); return result;
});
await run('two instances follow only their focused keyboard and blur clears hold', async () => {
  await setup({ second: true }); await page.locator('#game-0').focus(); await page.keyboard.down('KeyD'); await step(.3);
  await page.locator('#game-1').focus(); const before = await step(10); assert.deepEqual(before.map(pos), [{ c: 4, r: 5 }, { c: 4, r: 4 }]);
  await page.keyboard.up('KeyD'); await page.keyboard.down('KeyW'); await step(.3); await page.locator('#outside').focus(); const after = await step(10); assert.deepEqual(after.map(pos), [{ c: 4, r: 5 }, { c: 5, r: 4 }]); return after;
});
await run('editable input textarea select and contenteditable do not move', async () => {
  await setup(); await fixture.evaluate(f => { f.owned[0].host.insertAdjacentHTML('beforeend', '<input id="edit-input"><textarea id="edit-area"></textarea><select id="edit-select"><option>A</option><option>B</option></select><div id="edit-content" contenteditable="true">Text</div>'); });
  for (const id of ['edit-input', 'edit-area', 'edit-select', 'edit-content']) { await page.locator(`#${id}`).focus(); await page.keyboard.down('KeyD'); await step(2); await page.keyboard.up('KeyD'); }
  assert.deepEqual(pos((await step(10))[0]), { c: 4, r: 4 });
  await page.locator('#game-0').focus(); await page.keyboard.down('KeyD'); await step(.1); await page.locator('#edit-input').focus(); assert.deepEqual(pos((await step(10))[0]), { c: 4, r: 5 }); return { editableFields: 4, activeHoldCleared: true };
});
for (const action of ['pause', 'load', 'control']) await run(`${action} clears held keyboard without restart`, async () => {
  await setup(); await page.locator('#game-0').focus(); await page.keyboard.down('KeyD'); await step(.2);
  await fixture.evaluate(async (f, action) => { const r = f.owned[0].runtime; if (action === 'pause') { r.pause(); r.resume(); } if (action === 'load') await r.loadScene(f.scene()); if (action === 'control') { r.add({ id: 'other', type: 'actor', c: 1, r: 1 }); r.setControlled('other'); } }, action);
  const after = await step(20); const later = await step(20); assert.deepEqual(after, later); if (action === 'load') assert.deepEqual(pos(after[0]), { c: 4, r: 4 });
  if (action === 'control') assert.deepEqual(await fixture.evaluate(f => ({ c: f.owned[0].runtime.getEntity('other').c, r: f.owned[0].runtime.getEntity('other').r })), { c: 1, r: 1 }); return after;
});

const stickCenter = async () => { const box = await page.locator('.runtime-stick').boundingBox(); assert.ok(box); return { x: box.x + box.width / 2, y: box.y + box.height / 2 }; };
const knob = () => page.locator('.runtime-stick-knob').evaluate(node => node.style.transform);
await run('visible HUD mouse capture outside pad, release recenters without camera drag', async () => {
  await setup({ joystick: true }); const center = await stickCenter(); const camera = await fixture.evaluate(f => f.owned[0].runtime.getCamera());
  await page.mouse.move(center.x + 30, center.y); await page.mouse.down(); await step(.3); assert.notEqual(await knob(), 'translate(0px, 0px)');
  await page.screenshot({ path: resolve(output, 'hud-engaged.png') });
  await page.mouse.move(center.x + 180, center.y); await page.mouse.up(); assert.equal(await knob(), 'translate(0px, 0px)');
  const after = await step(10); assert.deepEqual(pos(after[0]), { c: 5, r: 5 }); assert.deepEqual(await step(10), after); assert.deepEqual(await fixture.evaluate(f => f.owned[0].runtime.getCamera()), camera); return { end: after, camera };
});
for (const ending of ['touchEnd', 'touchCancel', 'lostcapture']) await run(`native touch ${ending} recenters HUD and releases movement`, async () => {
  await setup({ joystick: true }); const center = await stickCenter(); const cdp = await context.newCDPSession(page); const touch = { x: center.x + 30, y: center.y, id: 1 };
  try {
    await cdp.send('Input.dispatchTouchEvent', { type: 'touchStart', touchPoints: [touch] }); await cdp.send('Input.dispatchTouchEvent', { type: 'touchMove', touchPoints: [{ ...touch, x: center.x + 80 }] }); await step(.2);
    if (ending === 'lostcapture') {
      const released = await fixture.evaluate(f => { const item = f.owned[0], node = item.joystick.element; const captured = node.hasPointerCapture(item.lastPointerId); node.releasePointerCapture(item.lastPointerId); return captured; });
      assert.ok(released, 'native pointer capture owned by stick');
      await cdp.send('Input.dispatchTouchEvent', { type: 'touchMove', touchPoints: [{ ...touch, x: center.x + 81 }] });
      await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
      assert.equal(await knob(), 'translate(0px, 0px)', 'lost capture must reset before touch release');
      await cdp.send('Input.dispatchTouchEvent', { type: 'touchEnd', touchPoints: [] });
    } else await cdp.send('Input.dispatchTouchEvent', { type: ending, touchPoints: [] });
    assert.equal(await knob(), 'translate(0px, 0px)'); const after = await step(10); assert.deepEqual(pos(after[0]), { c: 5, r: 5 }); assert.deepEqual(await step(10), after); return after;
  } finally { await cdp.send('Input.dispatchTouchEvent', { type: 'touchCancel', touchPoints: [] }).catch(() => {}); await cdp.detach(); }
});
await run('HUD ignores second touch and retains first pointer ownership', async () => {
  await setup({ joystick: true }); const center = await stickCenter(); const cdp = await context.newCDPSession(page); const a = { x: center.x + 30, y: center.y, id: 1 }, b = { x: center.x - 30, y: center.y, id: 2 };
  try {
    await cdp.send('Input.dispatchTouchEvent', { type: 'touchStart', touchPoints: [a] });
    await cdp.send('Input.dispatchTouchEvent', { type: 'touchStart', touchPoints: [a, b] });
    await cdp.send('Input.dispatchTouchEvent', { type: 'touchMove', touchPoints: [a, { ...b, y: center.y - 30 }] });
    await step(.3); await cdp.send('Input.dispatchTouchEvent', { type: 'touchEnd', touchPoints: [] });
    assert.equal(await knob(), 'translate(0px, 0px)'); const end = (await step(10))[0]; assert.deepEqual(pos(end), { c: 5, r: 5 }); return end;
  } finally { await cdp.send('Input.dispatchTouchEvent', { type: 'touchCancel', touchPoints: [] }).catch(() => {}); await cdp.detach(); }
});
await api('reentrant destroy from inputreset is finite and idempotent', async f => {
  const { runtime: r, host } = await f.spawn(); let resets = 0;
  r.on('inputreset', () => { resets++; if (resets > 3) throw Error('recursive inputreset destruction'); r.destroy(); });
  r.destroy(); r.destroy(); if (resets > 1 || host.querySelector('canvas')) throw Error(`destroy failed: resets=${resets}`); return { resets };
});
await api('nested load from inputreset cancels outer load and preserves newest scene', async f => {
  const { runtime: r } = await f.spawn(); let nested, count = 0; const events = [];
  r.on('scenechange', event => events.push(event.name));
  r.on('inputreset', () => { if (++count === 1) nested = r.loadScene({ ...f.stacked(), name: 'nested newest' }); });
  let rejected; try { await r.loadScene({ ...f.scene(), name: 'outer stale' }); } catch (error) { rejected = error.name; }
  await nested;
  if (rejected !== 'AbortError' || r.serializeScene().name !== 'nested newest' || events.join() !== 'nested newest') throw Error('nested replacement was not atomic');
  return { rejected, events, resets: count };
});
for (const action of ['load', 'moveTo', 'stop', 'pause', 'remove']) await run(`${action} tolerates inputreset listener destroying runtime`, () => fixture.evaluate(async (f, action) => {
  const { runtime: r, host } = await f.spawn(); let callbacks = 0; let errorName;
  r.on('inputreset', () => { callbacks++; r.destroy(); });
  if (action === 'load') { try { await r.loadScene(f.scene()); } catch (error) { errorName = error.name; } if (errorName !== 'AbortError') throw Error('destroyed load did not abort'); }
  if (action === 'moveTo') r.moveTo('actor', { c: 6, r: 4 });
  if (action === 'stop') r.stop('actor');
  if (action === 'pause') r.pause();
  if (action === 'remove') r.remove('actor');
  if (callbacks !== 1 || host.querySelector('canvas')) throw Error(`destroy failed after ${action}`);
  return { callbacks, errorName };
}, action));
await api('direct arrive callback stop prevents held continuation', async f => {
  const { runtime: r } = await f.spawn(); let arrivals = 0; r.on('arrive', () => { arrivals++; r.stop('actor'); });
  r.setMoveInput({ x: 1, y: -1 }); r.step(20);
  if (arrivals !== 1 || r.getEntity('actor').c !== 5) throw Error('arrival callback did not stop direct movement');
  return { arrivals, entity: r.getEntity('actor') };
});
await api('direct move callback pause interrupts remaining frame and clears hold', async f => {
  const { runtime: r } = await f.spawn(); const off = r.on('move', () => r.pause());
  r.setMoveInput({ x: 1, y: -1 }); r.step(20); off(); const paused = r.getEntity('actor');
  r.resume(); r.step(20); if (paused.c !== 5 || r.getEntity('actor').c !== 5) throw Error('pause callback resumed held movement'); return paused;
});
await run('real map clicks select upper and cutaway ground floors', async () => {
  await fixture.evaluate(async f => { const item = await f.spawn(f.stacked(), { input: true }); item.clicks = []; item.runtime.on('tileclick', event => item.clicks.push(event.cell)); });
  for (const cell of [{ c: 6, r: 4, level: 'bridge' }, { c: 4, r: 4 }]) {
    const point = await fixture.evaluate((f, cell) => { const item = f.owned[0]; item.runtime.setViewLevel(cell.level ?? 'ground'); const p = item.runtime.cellToScreen(cell); const box = item.host.querySelector('canvas').getBoundingClientRect(); return { x: box.left + p.x, y: box.top + p.y }; }, cell);
    await page.mouse.click(point.x, point.y); const end = (await step(20))[0]; assert.deepEqual(pos(end), cell);
  }
  const clicks = await fixture.evaluate(f => f.owned[0].clicks); assert.deepEqual(clicks, [{ c: 6, r: 4, level: 'bridge' }, { c: 4, r: 4 }]); return clicks;
});
await api('resume during pause inputreset preserves final state and running ticker', async f => {
  const { runtime: r } = await f.spawn(undefined, { autoStart: true }); const events = []; let frames = 0;
  r.on('pausechange', event => events.push(event.paused)); r.on('frame', () => frames++);
  const off = r.on('inputreset', () => r.resume()); r.pause(); off();
  const before = frames; await new Promise(resolve => setTimeout(resolve, 120));
  if (r.isPaused || events.at(-1) !== false || frames === before) throw Error(`resumed state inconsistent: paused=${r.isPaused}, events=${events}, frames=${before}->${frames}`);
  return { events, before, after: frames };
});
for (const scenario of ['descending-arrival', 'paused-ascent-cutaway']) await run(`${scenario} retains visible ground actor`, () => fixture.evaluate(async (f, scenario) => {
  const data = f.stacked(); if (scenario === 'descending-arrival') Object.assign(data.entities[0], { c: 5, r: 4, level: 'bridge' });
  const { runtime: r, host } = await f.spawn(data);
  if (scenario === 'descending-arrival') { r.moveTo('actor', { c: 4, r: 4 }); r.step(2); }
  else { r.moveTo('actor', { c: 5, r: 4, level: 'bridge' }); r.step(Math.SQRT2 / 2); r.pause(); }
  r.setViewLevel('ground');
  const capture = () => { const source = host.querySelector('canvas'); const copy = document.createElement('canvas'); copy.width = source.width; copy.height = source.height; const ctx = copy.getContext('2d'); ctx.drawImage(source, 0, 0); return Array.from(ctx.getImageData(0, 0, copy.width, copy.height).data); };
  // setViewLevel renders synchronously. Do not step again: that would mask stale parenting.
  const before = capture(); r.remove('actor'); const after = capture(); const changed = before.reduce((n, value, i) => n + Number(value !== after[i]), 0);
  if (changed < 50) throw Error(`ground actor invisible after ${scenario}: ${changed} pixel channels changed on removal`);
  return { changedPixelChannels: changed };
}, scenario));
await api('settled stair descent renders destination floor before any cutaway refresh', async f => {
  const data = f.stacked(); Object.assign(data.entities[0], { c: 5, r: 4, level: 'bridge' });
  const { runtime: r, host } = await f.spawn(data); r.moveTo('actor', { c: 4, r: 4 }); r.step(2);
  const capture = () => { const source = host.querySelector('canvas'); const copy = document.createElement('canvas'); copy.width = source.width; copy.height = source.height; const ctx = copy.getContext('2d'); ctx.drawImage(source, 0, 0); return Array.from(ctx.getImageData(0, 0, copy.width, copy.height).data); };
  const arrived = capture(); r.stop('actor'); const stopped = capture();
  const changed = arrived.reduce((n, value, i) => n + Number(value !== stopped[i]), 0);
  if (changed !== 0) throw Error(`settled actor changed ${changed} pixel channels after stop at same integer position`);
  return { changedPixelChannels: changed };
});

const padButton = (key, game = 0) => page.locator(`#game-${game} .runtime-dpad button[data-key="${key}"]`);
const centerOf = async locator => { const box = await locator.boundingBox(); assert.ok(box); return { x: box.x + box.width / 2, y: box.y + box.height / 2 }; };
const padReleased = () => page.locator('.runtime-dpad [aria-pressed="true"]').count();
for (const { key, target, screen } of originalMovement) await run(`Dpad ${key} native mouse hold and outside release moves ${screen}`, async () => {
  await setup({ dpad: true }); const center = await centerOf(padButton(key)); const camera = await fixture.evaluate(f => f.owned[0].runtime.getCamera());
  assert.equal(await padButton(key).getAttribute('aria-label'), `Move ${screen} (${key.slice(-1)})`);
  await page.mouse.move(center.x, center.y); await page.mouse.down(); assert.equal(await padButton(key).getAttribute('aria-pressed'), 'true'); await step(.3);
  if (key === 'KeyW') await page.screenshot({ path: resolve(output, 'dpad-engaged.png') });
  await page.mouse.move(center.x - 180, center.y - 180); await page.mouse.up(); assert.equal(await padReleased(), 0);
  const after = await step(15); assert.deepEqual(pos(after[0]), target); assert.deepEqual(await step(15), after); assert.deepEqual(await fixture.evaluate(f => f.owned[0].runtime.getCamera()), camera); return target;
});
for (const ending of ['touchEnd', 'touchCancel', 'lostcapture']) await run(`Dpad native ${ending} releases captured touch without stuck input`, async () => {
  await setup({ dpad: true }); const center = await centerOf(padButton('KeyW')); const cdp = await context.newCDPSession(page); const touch = { ...center, id: 1 };
  try {
    await cdp.send('Input.dispatchTouchEvent', { type: 'touchStart', touchPoints: [touch] });
    await cdp.send('Input.dispatchTouchEvent', { type: 'touchMove', touchPoints: [{ ...touch, x: touch.x + 1 }] });
    await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))); await step(.25);
    if (ending === 'lostcapture') {
      const captured = await fixture.evaluate(f => { const { id, button } = f.owned[0].lastDpadPointer; const captured = button.hasPointerCapture(id); button.releasePointerCapture(id); return captured; }); assert.ok(captured);
      await cdp.send('Input.dispatchTouchEvent', { type: 'touchMove', touchPoints: [{ ...touch, x: touch.x - 80 }] });
      await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
      assert.equal(await padReleased(), 0, `lost capture clears pressed state before touch end: ${JSON.stringify(await fixture.evaluate(f => f.owned[0].pointerTrace))}`);
    }
    await cdp.send('Input.dispatchTouchEvent', { type: ending === 'lostcapture' ? 'touchEnd' : ending, touchPoints: [] });
    assert.equal(await padReleased(), 0); const after = await step(15); assert.deepEqual(pos(after[0]), { c: 5, r: 4 }); assert.deepEqual(await step(15), after); return after;
  } finally { await cdp.send('Input.dispatchTouchEvent', { type: 'touchCancel', touchPoints: [] }).catch(() => {}); await cdp.detach(); }
});
for (const kind of ['adjacent', 'opposite-release']) await run(`Dpad simultaneous native touches ${kind} retain independent ownership`, async () => {
  await setup({ dpad: true }); const first = { ...await centerOf(padButton('KeyW')), id: 1 }; const second = { ...await centerOf(padButton(kind === 'adjacent' ? 'KeyD' : 'KeyS')), id: 2 }; const cdp = await context.newCDPSession(page);
  try {
    await cdp.send('Input.dispatchTouchEvent', { type: 'touchStart', touchPoints: [first] }); await cdp.send('Input.dispatchTouchEvent', { type: 'touchStart', touchPoints: [first, second] });
    if (kind === 'opposite-release') {
      assert.deepEqual(pos((await step(4))[0]), { c: 4, r: 4 });
      // CDP touchEnd lists the released contacts, rather than the remaining ones.
      await cdp.send('Input.dispatchTouchEvent', { type: 'touchEnd', touchPoints: [second] });
      assert.equal(await padButton('KeyW').getAttribute('aria-pressed'), 'true', JSON.stringify(await fixture.evaluate(f => f.owned[0].pointerTrace))); assert.equal(await padButton('KeyS').getAttribute('aria-pressed'), 'false');
    }
    await step(.3); await cdp.send('Input.dispatchTouchEvent', { type: 'touchEnd', touchPoints: [] });
    assert.equal(await padReleased(), 0); const end = (await step(15))[0]; assert.deepEqual(pos(end), kind === 'adjacent' ? { c: 5, r: 5 } : { c: 5, r: 4 }); return end;
  } finally { await cdp.send('Input.dispatchTouchEvent', { type: 'touchCancel', touchPoints: [] }).catch(() => {}); await cdp.detach(); }
});
for (const action of ['pause', 'load', 'control', 'blur']) await run(`Dpad ${action} clears active pointer and prevents held continuation`, async () => {
  await setup({ dpad: true }); const center = await centerOf(padButton('KeyD')); await page.mouse.move(center.x, center.y); await page.mouse.down(); await step(.25);
  if (action === 'blur') await page.locator('#outside').focus();
  else await fixture.evaluate(async (f, action) => { const r = f.owned[0].runtime;
    if (action === 'pause') r.pause();
    if (action === 'load') await r.loadScene(f.scene());
    if (action === 'control') { r.add({ id: 'other', type: 'actor', c: 1, r: 1 }); r.setControlled('other'); }
  }, action);
  assert.equal(await padReleased(), 0);
  if (action === 'pause') { assert.equal(await page.locator('.runtime-dpad').getAttribute('aria-disabled'), 'true'); await fixture.evaluate(f => f.owned[0].runtime.resume()); }
  await page.mouse.up(); const after = await step(15); assert.deepEqual(await step(15), after); assert.deepEqual(pos(after[0]), action === 'load' ? { c: 4, r: 4 } : { c: 4, r: 5 });
  if (action === 'control') assert.deepEqual(await fixture.evaluate(f => ({ c: f.owned[0].runtime.getEntity('other').c, r: f.owned[0].runtime.getEntity('other').r })), { c: 1, r: 1 }); return after;
});
await run('Dpad keyboard focus supports WASD and native Enter button activation', async () => {
  await setup({ dpad: true }); await padButton('KeyD').focus(); await page.keyboard.down('KeyW'); await step(.2); await page.keyboard.up('KeyW'); assert.deepEqual(pos((await step(10))[0]), { c: 5, r: 4 });
  await page.keyboard.down('Enter'); await step(.2); await page.keyboard.up('Enter'); assert.deepEqual(pos((await step(10))[0]), { c: 5, r: 5 }); assert.equal(await padReleased(), 0); return { c: 5, r: 5 };
});
await run('Dpad input remains owned by its instance when focus changes', async () => {
  await setup({ dpad: true, second: true }); await fixture.evaluate(f => f.pad(f.owned[1]));
  const center = await centerOf(padButton('KeyD')); await page.mouse.move(center.x, center.y); await page.mouse.down(); await step(.2);
  await padButton('KeyW', 1).focus(); await page.mouse.up(); const first = await step(10); assert.deepEqual(first.map(pos), [{ c: 4, r: 5 }, { c: 4, r: 4 }]);
  await page.keyboard.down('Enter'); await step(.2); await page.keyboard.up('Enter'); const after = await step(10); assert.deepEqual(after.map(pos), [{ c: 4, r: 5 }, { c: 5, r: 4 }]); return after;
});
for (const { key, arrow, target } of originalMovement) await run(`native ${arrow} matches original ${key} axis`, async () => {
  await setup(); await page.locator('#game-0').focus(); await page.keyboard.down(arrow); await step(.2); await page.keyboard.up(arrow);
  const end = (await step(10))[0]; assert.deepEqual(pos(end), target); return end;
});
// Literal sums of adjacent axes from the original fixture: right, down, left, up.
const originalCombinations = [
  { keys: ['KeyW', 'KeyD'], arrows: ['ArrowUp', 'ArrowRight'], target: { c: 5, r: 5 } },
  { keys: ['KeyD', 'KeyS'], arrows: ['ArrowRight', 'ArrowDown'], target: { c: 3, r: 5 } },
  { keys: ['KeyS', 'KeyA'], arrows: ['ArrowDown', 'ArrowLeft'], target: { c: 3, r: 3 } },
  { keys: ['KeyA', 'KeyW'], arrows: ['ArrowLeft', 'ArrowUp'], target: { c: 5, r: 3 } },
];
for (const combination of originalCombinations) for (const keys of [combination.keys, combination.arrows]) await run(`native combined ${keys.join('+')} matches original axes`, async () => {
  await setup(); await page.locator('#game-0').focus(); for (const key of keys) await page.keyboard.down(key); await step(.3); for (const key of keys) await page.keyboard.up(key);
  const end = (await step(10))[0]; assert.deepEqual(pos(end), combination.target); assert.deepEqual((await step(10))[0], end); return end;
});

await page.screenshot({ path: resolve(output, 'completed.png') });
const report = { kind: 'Independent browser runtime API and native input instrumentation; not GUI certification or public VPS end-to-end testing', url: page.url(), timestamp: new Date().toISOString(), results, pageErrors: errors, passed: results.filter(test => test.pass).length, total: results.length };
await writeFile(resolve(output, 'results.json'), JSON.stringify(report, null, 2));
for (const test of results) console.log(`${test.pass ? 'PASS' : 'FAIL'} ${test.name}${test.error ? `\n${test.error}` : ''}`);
console.log(`${report.passed}/${report.total} levels/input browser checks; ${errors.length} page errors. Report: ${output}`);
await browser.close();
process.exitCode = report.passed !== report.total || errors.length ? 1 : 0;
