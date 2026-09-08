import { createRequire } from 'node:module';
import { mkdir, writeFile } from 'node:fs/promises';
import { resolve } from 'node:path';
import assert from 'node:assert/strict';

const require = createRequire(resolve(process.env.RUNTIME_QA_PACKAGE ?? 'package.json'));
const { chromium } = require('playwright');
const output = resolve(process.env.RUNTIME_QA_OUTPUT ?? 'test-results/jump-api');
await mkdir(output, { recursive: true });
const browser = await chromium.launch({ headless: true });
const context = await browser.newContext({ viewport: { width: 1100, height: 850 }, hasTouch: true });
const page = await context.newPage();
const errors = [], results = [];
page.on('pageerror', error => errors.push(error.message));
await page.route('**/jump-qa-host', route => route.fulfill({ contentType: 'text/html', body: '<!doctype html><html><body style="margin:0"><button id="outside">Outside game</button></body></html>' }));
await page.goto(`${process.env.RUNTIME_QA_URL ?? 'http://127.0.0.1:4175'}/jump-qa-host`);
const fixture = await page.evaluateHandle(async () => {
  const { Runtime, createDpad, createJumpButton } = await import('/src/index.ts');
  const { createScene } = await import('/demo/scenes.ts');
  const owned = [];
  const scene = () => ({ version: 2, levels: [], links: [], name: 'Jump fixture', tileWidth: 64, tileHeight: 32,
    map: Array.from({ length: 9 }, () => Array(9).fill('grass')),
    tiles: { grass: { color: 0x719654 }, upper: { color: 0xf0bd67 } },
    entityTypes: { actor: { visual: { kind: 'actor', color: 0xdf3355 }, blocking: true }, wall: { visual: { kind: 'box', height: 160 }, blocking: true } },
    entities: [{ id: 'actor', type: 'actor', c: 2, r: 4 }], controlledId: 'actor', diagonal: true });
  const stacked = () => { const data = scene(); const map = Array.from({ length: 9 }, () => Array(9).fill(null)); map[4][4] = 'upper'; data.levels = [{ id: 'bridge', name: 'Bridge', height: 72, map }]; return data; };
  const userRepro = (removeAdjacentSteps = false) => { const data = createScene('jump'); const actor = data.entities.find(entity => entity.id === 'traveler'); actor.c = 3; actor.r = 6; if (removeAdjacentSteps) { data.map[5][1] = 'path'; data.map[5][2] = 'path'; } return data; };
  return { scene, stacked, userRepro, owned,
    async spawn(data = scene(), options = {}) {
      const host = document.createElement('div'); host.id = `jump-game-${owned.length}`; host.style.cssText = 'position:relative;width:520px;height:390px;display:inline-block;vertical-align:top'; document.body.append(host);
      const runtime = new Runtime({ container: host, scene: data, autoStart: false, input: false, speed: 1, ...options });
      const item = { host, runtime, starts: [], lands: [], hits: [] }; owned.push(item); await runtime.ready;
      runtime.on('jumpstart', event => item.starts.push(event)); runtime.on('land', event => item.lands.push(event)); runtime.on('projectilehit', event => item.hits.push(event)); return item;
    },
    controls(item) { item.pad = createDpad(item.runtime, item.host); item.jump = createJumpButton(item.runtime, item.host); },
    cleanup() { for (const item of owned) { try { item.pad?.destroy(); item.jump?.destroy(); item.runtime.destroy(); } catch {} item.host.remove(); } owned.length = 0; },
  };
});
const run = async (name, test) => {
  try { const evidence = await test(); results.push({ name, pass: true, evidence }); }
  catch (error) { results.push({ name, pass: false, error: error.stack }); await page.screenshot({ path: resolve(output, `failure-${results.length}.png`) }).catch(() => {}); }
  finally { await fixture.evaluate(f => f.cleanup()); for (const key of ['KeyW', 'KeyA', 'KeyS', 'KeyD', 'Space', 'Enter']) await page.keyboard.up(key); }
};
const api = (name, test) => run(name, () => fixture.evaluate(test));

for (const hz of [30, 60, 120]) await run(`jump reaches second floor without stairs at ${hz} Hz`, () => fixture.evaluate(async (f, hz) => {
  const item = await f.spawn(f.stacked()), r = item.runtime;
  if (r.findPath('actor', { c: 4, r: 4, level: 'bridge' }) !== null) throw Error('fixture must have no stair route');
  r.setMoveInput({ x: 1, y: -1 }); if (r.jump() !== 'started') throw Error('jump did not start'); r.setMoveInput(null);
  if (r.jump() !== 'airborne') throw Error('double jump accepted');
  const poses = []; for (let frame = 0; frame < hz; frame++) { r.step(1 / hz); poses.push(r.getEntityPose('actor')); }
  const end = r.getEntityPose('actor');
  if (end.airborne || end.position.c !== 4 || end.position.r !== 4 || end.position.level !== 'bridge' || end.elevation !== 72) throw Error(`invalid landing ${JSON.stringify(end)}`);
  const peak = Math.max(...poses.map(pose => pose.elevation));
  if (peak < 80 || peak > 84.001 || item.starts.length !== 1 || item.lands.length !== 1) throw Error(`invalid peak ${peak} or duplicate events`);
  return { end, apex: Math.max(...poses.map(pose => pose.elevation)), starts: item.starts, lands: item.lands };
}, hz));
await api('neutral jump rises, lands at launch and protects pose snapshots', async f => {
  const item = await f.spawn(), r = item.runtime; r.jump(); r.step(.4); const apex = r.getEntityPose('actor');
  if (!apex.airborne || Math.abs(apex.elevation - 40) > .001 || apex.position.c !== 2 || apex.position.r !== 4) throw Error('invalid neutral apex');
  apex.position.c = 999; if (r.getEntityPose('actor').position.c === 999) throw Error('pose leaked mutable state');
  r.step(.4); const end = r.getEntityPose('actor'); if (end.airborne || end.elevation !== 0 || end.position.c !== 2 || item.lands.length !== 1) throw Error('neutral landing');
  if (r.jump('missing') !== 'missing' || r.getEntityPose('missing') !== undefined) throw Error('missing actor behavior'); return end;
});
await api('negative-elevation ground jump renders safely below every floor base', async f => {
  const data = f.scene(); data.tiles.grass.elevation = -20; const item = await f.spawn(data), r = item.runtime;
  if (r.jump() !== 'started') throw Error('negative-elevation hop did not start'); r.step(1 / 120); const early = r.getEntityPose('actor');
  if (!early.airborne || early.elevation >= 0) throw Error('fixture did not exercise feet below floor base');
  r.step(1); const end = r.getEntityPose('actor'); if (end.airborne || end.elevation !== -20 || end.position.c !== 2) throw Error('negative-elevation landing failed'); return { early, end };
});
await api('settled raised terrain actor returns to ground depth layer and survives cutaway', async f => {
  const data = f.scene(); data.tiles.grass.elevation = 104; data.tiles.foreground = { color: 0x447766, elevation: 136 }; data.map[5][2] = 'foreground';
  const upperMap = Array.from({ length: 9 }, () => Array(9).fill(null)); upperMap[0][0] = 'upper'; data.levels = [{ id: 'bridge', name: 'Bridge', height: 72, map: upperMap }];
  const item = await f.spawn(data), r = item.runtime;
  const capture = () => { const source = item.host.querySelector('canvas'); const copy = document.createElement('canvas'); copy.width = source.width; copy.height = source.height; const ctx = copy.getContext('2d'); ctx.drawImage(source, 0, 0); return Array.from(ctx.getImageData(0, 0, copy.width, copy.height).data); };
  if (r.jump() !== 'started') throw Error('raised terrain hop blocked'); r.step(1); const landed = capture(); r.stop('actor'); const stopped = capture();
  const changed = landed.reduce((sum, value, index) => sum + Number(value !== stopped[index]), 0); if (changed) throw Error(`settled actor retained airborne floor layer: ${changed} changed channels after stop`);
  r.setViewLevel('ground'); const visible = capture(); r.remove('actor'); const absent = capture(); const actorChannels = visible.reduce((sum, value, index) => sum + Number(value !== absent[index]), 0);
  if (actorChannels < 100) throw Error('ground cutaway hid settled ground actor'); return { changedAfterStop: changed, actorPixelChannels: actorChannels };
});
for (const elevation of [0, 18]) await run(`mid-walk jump preserves fractional takeoff position and height ${elevation}`, () => fixture.evaluate(async (f, elevation) => {
  const data = f.scene(); data.tiles.grass.elevation = elevation; const item = await f.spawn(data), r = item.runtime;
  r.setMoveInput({ x: 1, y: -1 }); r.step(.3); const before = r.getEntityPose('actor');
  if (Math.abs(before.position.c - 2.3) > 1e-8 || before.elevation !== elevation) throw Error('fixture did not reach fractional walking pose');
  if (r.jump() !== 'started') throw Error('mid-walk jump blocked'); const takeoff = r.getEntityPose('actor');
  if (!takeoff.airborne || JSON.stringify(before.position) !== JSON.stringify(takeoff.position) || before.elevation !== takeoff.elevation) throw Error(`takeoff snapped ${JSON.stringify({ before, takeoff })}`);
  r.setMoveInput(null); r.step(.8); const end = r.getEntityPose('actor');
  if (end.airborne || end.position.c !== 4 || end.position.r !== 4 || end.elevation !== elevation) throw Error('fractional takeoff did not land on integer tile'); return { before, takeoff, end };
}, elevation));
await api('mid-walk jump rollback uses reserved integer cell rather than fractional takeoff', async f => {
  const item = await f.spawn(f.stacked()), r = item.runtime; r.setMoveInput({ x: 1, y: -1 }); r.step(.3); if (r.jump() !== 'started') throw Error('mid-walk jump blocked'); r.setMoveInput(null); r.step(.2);
  let rejected = false; try { r.add({ id: 'launch-block', type: 'wall', c: 2, r: 4 }); } catch { rejected = true; }
  if (!rejected) throw Error('integer launch reservation lost after fractional takeoff');
  r.add({ id: 'late-block', type: 'wall', c: 4, r: 4, level: 'bridge' }); r.step(1); const end = r.getEntityPose('actor');
  if (end.airborne || end.position.c !== 2 || end.position.r !== 4 || end.position.level || end.elevation !== 0) throw Error(`rollback to invalid fractional cell ${JSON.stringify(end)}`); return end;
});
await api('upper-floor actor can jump down to supported ground', async f => {
  const data = f.stacked(); data.entities[0] = { ...data.entities[0], c: 4, level: 'bridge' }; const item = await f.spawn(data), r = item.runtime;
  r.setMoveInput({ x: 1, y: -1 }); if (r.jump() !== 'started') throw Error('descent blocked'); r.setMoveInput(null); r.step(1);
  const end = r.getEntityPose('actor'); if (end.airborne || end.position.c !== 6 || end.position.level || end.elevation !== 0) throw Error(`descent landing ${JSON.stringify(end)}`); return end;
});
await api('jump lands on first raised platform instead of skipping over it', async f => {
  const data = f.stacked(); data.levels[0].map[4][3] = 'upper'; data.levels[0].map[4][4] = null;
  const item = await f.spawn(data), r = item.runtime; r.setMoveInput({ x: 1, y: -1 });
  if (r.jump() !== 'started') throw Error('adjacent platform jump did not start'); r.setMoveInput(null); r.step(1);
  const end = r.getEntityPose('actor'); if (end.airborne || end.position.c !== 3 || end.position.level !== 'bridge' || end.elevation !== 72) throw Error(`skipped narrow platform ${JSON.stringify(end)}`); return end;
});
await api('platform above maximum jump rise cannot be landed upon', async f => {
  const data = f.stacked(); data.levels[0].height = 144; const item = await f.spawn(data), r = item.runtime;
  r.setMoveInput({ x: 1, y: -1 }); r.jump(); r.setMoveInput(null); let peak = 0;
  for (let frame = 0; frame < 120; frame++) { r.step(1 / 120); peak = Math.max(peak, r.getEntityPose('actor').elevation); }
  const end = r.getEntityPose('actor'); if (end.position.level === 'bridge' || end.airborne || peak > 84.001) throw Error('jump exceeded maximum rise'); return { end, peak };
});
for (const lower of ['absent', 'beside-route', 'along-route']) await run(`same ground takeoff cannot reach 144-high platform with low neighbor ${lower}`, () => fixture.evaluate(async (f, lower) => {
  const data = f.scene(); const high = Array.from({ length: 9 }, () => Array(9).fill(null)); high[4][4] = 'upper'; data.levels = [{ id: 'high', name: 'High', height: 144, map: high }];
  if (lower !== 'absent') { const low = Array.from({ length: 9 }, () => Array(9).fill(null)); low[lower === 'along-route' ? 4 : 5][3] = 'upper'; data.levels.push({ id: 'low', name: 'Low', height: 72, map: low }); }
  const item = await f.spawn(data), r = item.runtime; const takeoff = r.getEntityPose('actor'); r.setMoveInput({ x: 1, y: -1 }); const result = r.jump(); r.setMoveInput(null); let peak = takeoff.elevation;
  for (let frame = 0; frame < 120; frame++) { r.step(1 / 120); const pose = r.getEntityPose('actor'); peak = Math.max(peak, pose.elevation); if (pose.position.level === 'high') throw Error('single ground jump entered high floor'); }
  const end = r.getEntityPose('actor'), entity = r.getEntity('actor');
  if (peak > 84.001 || end.airborne || entity.level === 'high' || end.elevation === 144) throw Error(`neighbor raised jump reach ${JSON.stringify({ peak, end, entity })}`);
  if (lower === 'along-route' && (entity.level !== 'low' || entity.c !== 3 || end.elevation !== 72)) throw Error('first reachable low platform was not landed upon');
  return { lower, result, takeoff, peak, end, entity, starts: item.starts };
}, lower));
await api('separate second jump from 72-high platform can reach 144-high platform', async f => {
  const data = f.scene(); const high = Array.from({ length: 9 }, () => Array(9).fill(null)), low = Array.from({ length: 9 }, () => Array(9).fill(null)); high[4][4] = 'upper'; low[4][3] = 'upper';
  data.levels = [{ id: 'high', name: 'High', height: 144, map: high }, { id: 'low', name: 'Low', height: 72, map: low }];
  const item = await f.spawn(data), r = item.runtime; r.setMoveInput({ x: 1, y: -1 }); r.jump(); r.setMoveInput(null); r.step(1); const first = r.getEntityPose('actor');
  if (first.airborne || first.position.level !== 'low' || first.elevation !== 72) throw Error('first landing not low platform');
  r.setMoveInput({ x: 1, y: -1 }); if (r.jump() !== 'started') throw Error('second 72-pixel rise blocked'); r.setMoveInput(null); r.step(1); const second = r.getEntityPose('actor');
  if (second.airborne || second.position.level !== 'high' || second.elevation !== 144 || item.starts.length !== 2 || item.lands.length !== 2) throw Error('separate second jump did not land high'); return { first, second, starts: item.starts, lands: item.lands };
});
await api('upper tile local elevation contributes slab thickness to ceiling collision', async f => {
  const data = f.stacked(); data.tiles.thick = { color: 0x998855, elevation: 32 }; data.levels[0].map[4][2] = 'thick';
  const item = await f.spawn(data), r = item.runtime; const result = r.jump(); r.step(1);
  if (result !== 'blocked' || item.starts.length || r.getEntityPose('actor').elevation !== 0) throw Error('hop entered thick elevated platform underside'); return { result, pose: r.getEntityPose('actor') };
});
await api('solid ceiling blocks hop without moving or emitting jumpstart', async f => {
  const data = f.stacked(); data.levels[0].map[4][2] = 'upper'; const item = await f.spawn(data), r = item.runtime;
  if (r.jump() !== 'blocked') throw Error('jump passed through ceiling'); r.step(1);
  if (r.getEntityPose('actor').airborne || item.starts.length || r.getEntity('actor').c !== 2) throw Error('blocked ceiling mutated actor'); return r.getEntityPose('actor');
});
await api('blocked landing and tall intervening wall never permit unsafe flight', async f => {
  const data = f.scene(); data.entities.push({ id: 'wall', type: 'wall', c: 3, r: 4 }); const item = await f.spawn(data), r = item.runtime;
  r.setMoveInput({ x: 1, y: -1 }); r.jump(); r.setMoveInput(null); r.step(1);
  if (r.getEntity('actor').c !== 2 || r.getEntityPose('actor').airborne) throw Error('jump tunneled through tall wall'); return { starts: item.starts, end: r.getEntityPose('actor') };
});
await api('wide actor cannot land on a platform supporting only half its footprint', async f => {
  const data = f.stacked(); data.entityTypes.actor.columns = 2; const item = await f.spawn(data), r = item.runtime;
  r.setMoveInput({ x: 1, y: -1 }); r.jump(); r.setMoveInput(null); r.step(1);
  const end = r.getEntityPose('actor'); if (end.position.level === 'bridge' || end.airborne) throw Error('unsupported wide landing'); return end;
});
await api('late landing obstacle rolls back safely and reserves launch occupancy', async f => {
  const item = await f.spawn(f.stacked()), r = item.runtime; r.setMoveInput({ x: 1, y: -1 }); r.jump(); r.setMoveInput(null); r.step(.3);
  let reserved = false; try { r.add({ id: 'launch-block', type: 'wall', c: 2, r: 4 }); } catch { reserved = true; }
  if (!reserved) throw Error('airborne actor lost launch reservation'); r.add({ id: 'landing-block', type: 'wall', c: 4, r: 4, level: 'bridge' }); r.step(1);
  const end = r.getEntityPose('actor'); if (end.airborne || end.position.c !== 2 || end.position.level || end.elevation !== 0) throw Error(`unsafe rollback ${JSON.stringify(end)}`); return end;
});
await api('pause freezes flight and resume completes it', async f => {
  const item = await f.spawn(), r = item.runtime; r.jump(); r.step(.2); r.pause(); const before = r.getEntityPose('actor'); r.step(5);
  if (JSON.stringify(before) !== JSON.stringify(r.getEntityPose('actor')) || r.jump() !== 'paused') throw Error('pause did not freeze');
  r.resume(); r.step(1); if (r.getEntityPose('actor').airborne || item.lands.length !== 1) throw Error('resume failed'); return { before, end: r.getEntityPose('actor') };
});
await api('load cancels flights and projectiles without stale events', async f => {
  const item = await f.spawn(), r = item.runtime; r.jump(); const id = r.spawnProjectile({ from: { c: 0, r: 4 }, to: { c: 8, r: 4 }, speed: 8, elevation: 20 }); r.step(.05);
  await r.loadScene(f.scene()); r.step(2); if (r.getEntityPose('actor').airborne || item.hits.length || item.lands.length || r.removeProjectile(id)) throw Error('old scene simulation survived load'); return r.getEntityPose('actor');
});
await api('stop during flight restores launch pose and prevents later landing', async f => {
  const item = await f.spawn(f.stacked()), r = item.runtime; r.setMoveInput({ x: 1, y: -1 }); r.jump(); r.step(.3); r.stop('actor');
  const end = r.getEntityPose('actor'); r.step(2);
  if (end.airborne || end.position.c !== 2 || end.elevation !== 0 || item.lands.length || JSON.stringify(end) !== JSON.stringify(r.getEntityPose('actor'))) throw Error('stop left airborne state'); return end;
});
await api('removing an airborne target cancels its landing and future trap hits', async f => {
  const item = await f.spawn(), r = item.runtime; r.jump(); r.spawnProjectile({ from: { c: 0, r: 4 }, to: { c: 8, r: 4 }, speed: 8, elevation: 20 }); r.step(.1); r.remove('actor'); r.step(2);
  if (r.getEntityPose('actor') || item.lands.length || item.hits.length) throw Error('removed target survived in simulation'); return { lands: item.lands.length, hits: item.hits.length };
});
await api('pause freezes projectiles before collision', async f => {
  const item = await f.spawn(), r = item.runtime; r.spawnProjectile({ from: { c: 0, r: 4 }, to: { c: 8, r: 4 }, speed: 8, elevation: 20 }); r.pause(); r.step(2);
  if (item.hits.length) throw Error('paused projectile advanced'); r.resume(); r.step(1); if (item.hits.length !== 1) throw Error('projectile did not resume'); return item.hits;
});
for (const hz of [30, 60, 120]) await run(`fast projectile sweeps through grounded target at ${hz} Hz`, () => fixture.evaluate(async (f, hz) => {
  const item = await f.spawn(), r = item.runtime; const id = r.spawnProjectile({ from: { c: 0, r: 4 }, to: { c: 8, r: 4 }, speed: 1000, elevation: 20 }); r.step(1 / hz);
  if (item.hits.length !== 1 || item.hits[0].entityId !== 'actor' || item.hits[0].projectileId !== id) throw Error('fast bullet tunneled through actor');
  r.step(2); if (item.hits.length !== 1 || r.removeProjectile(id)) throw Error('hit projectile persisted'); return item.hits;
}, hz));
await api('ground-level projectile passes beneath airborne actor at jump apex', async f => {
  const item = await f.spawn(), r = item.runtime; r.jump(); r.step(.4); const pose = r.getEntityPose('actor');
  const id = r.spawnProjectile({ from: { c: 0, r: 4 }, to: { c: 8, r: 4 }, speed: 1000, elevation: 20 }); r.step(.02);
  if (item.hits.length || r.removeProjectile(id)) throw Error('jump did not evade ground-height projectile'); return { pose, hits: item.hits.length };
});
await api('projectiles distinguish absolute target height on stacked floors', async f => {
  const data = f.stacked(); data.entities[0] = { ...data.entities[0], c: 4, level: 'bridge' }; const item = await f.spawn(data), r = item.runtime;
  r.spawnProjectile({ from: { c: 0, r: 4 }, to: { c: 8, r: 4 }, speed: 1000, elevation: 20 }); r.step(.02);
  if (item.hits.length) throw Error('ground projectile hit upstairs actor');
  r.spawnProjectile({ from: { c: 0, r: 4 }, to: { c: 8, r: 4 }, speed: 1000, elevation: 92 }); r.step(.02);
  if (item.hits.length !== 1) throw Error('upper-height projectile missed upstairs actor'); return item.hits;
});
await api('removeProjectile cancels only that projectile and invalid options are atomic', async f => {
  const item = await f.spawn(), r = item.runtime; const base = { from: { c: 0, r: 4 }, to: { c: 8, r: 4 }, speed: 20, elevation: 20 };
  const id = r.spawnProjectile(base); if (!r.removeProjectile(id) || r.removeProjectile(id)) throw Error('projectile removal result');
  let rejected = 0; for (const change of [{ speed: 0 }, { speed: NaN }, { elevation: Infinity }, { radius: -1 }, { targetId: 'absent' }]) { try { r.spawnProjectile({ ...base, ...change }); } catch { rejected++; } }
  r.step(2); if (rejected !== 5 || item.hits.length) throw Error('invalid projectile mutated simulation'); return { rejected };
});
await api('instances isolate airborne state and trap hits', async f => {
  const a = await f.spawn(), b = await f.spawn(); a.runtime.jump(); a.runtime.step(.4);
  b.runtime.spawnProjectile({ from: { c: 0, r: 4 }, to: { c: 8, r: 4 }, speed: 1000, elevation: 20 }); b.runtime.step(.02);
  if (!a.runtime.getEntityPose('actor').airborne || b.runtime.getEntityPose('actor').airborne || a.hits.length || b.hits.length !== 1) throw Error('instances leaked state'); return { a: a.runtime.getEntityPose('actor'), b: b.hits };
});
for (const event of ['jumpstart', 'land', 'projectilehit']) await run(`${event} callback may destroy runtime safely`, () => fixture.evaluate(async (f, event) => {
  const item = await f.spawn(), r = item.runtime; r.on(event, () => r.destroy());
  if (event === 'projectilehit') r.spawnProjectile({ from: { c: 0, r: 4 }, to: { c: 8, r: 4 }, speed: 1000, elevation: 20 }); else r.jump();
  if (event !== 'jumpstart') r.step(1); return { destroyedIn: event };
}, event));
for (const event of ['jumpstart', 'land', 'projectilehit']) await run(`${event} callback scene load prevents stale simulation`, () => fixture.evaluate(async (f, event) => {
  const item = await f.spawn(), r = item.runtime; let loading; r.on(event, () => { loading = r.loadScene(f.scene()); });
  if (event === 'projectilehit') r.spawnProjectile({ from: { c: 0, r: 4 }, to: { c: 8, r: 4 }, speed: 1000, elevation: 20 }); else r.jump();
  if (event !== 'jumpstart') r.step(1); await loading; const before = r.getEntityPose('actor'); r.step(2);
  if (before.airborne || before.elevation !== 0 || JSON.stringify(before) !== JSON.stringify(r.getEntityPose('actor'))) throw Error('callback load left stale simulation'); return { event, before };
}, event));
await api('projectile hit callback pause stops further bullets in the same step', async f => {
  const item = await f.spawn(), r = item.runtime; r.on('projectilehit', () => r.pause()); const bullet = { from: { c: 0, r: 4 }, to: { c: 8, r: 4 }, speed: 1000, elevation: 20 };
  r.spawnProjectile(bullet); r.spawnProjectile(bullet); r.step(1); if (item.hits.length !== 1 || !r.isPaused) throw Error('pause callback did not stop batch');
  r.resume(); r.step(1); if (item.hits.length !== 2) throw Error('remaining projectile did not resume'); return item.hits;
});

const setup = async (controls = false) => fixture.evaluate(async (f, controls) => { const item = await f.spawn(f.stacked(), { input: true }); if (controls) f.controls(item); }, controls);
const step = seconds => fixture.evaluate((f, delta) => { f.owned[0].runtime.step(delta); return f.owned[0].runtime.getEntityPose('actor'); }, seconds);
for (const removeAdjacentSteps of [false, true]) for (const native of [false, true]) await run(`exact demo (3,6) A jump toward (3,5), adjacent stairs ${removeAdjacentSteps ? 'removed' : 'present'}, ${native ? 'native keys' : 'API input'}`, async () => {
  await fixture.evaluate(async (f, options) => { await f.spawn(f.userRepro(options.removeAdjacentSteps), { input: options.native }); }, { removeAdjacentSteps, native });
  const takeoff = await fixture.evaluate(f => f.owned[0].runtime.getEntityPose('traveler'));
  if (native) { await page.locator('#jump-game-0').focus(); await page.keyboard.down('KeyA'); await page.keyboard.down('Space'); await page.keyboard.up('KeyA'); await page.keyboard.up('Space'); }
  else await fixture.evaluate(f => { const r = f.owned[0].runtime; r.setMoveInput({ x: -1, y: -1 }); r.jump(); r.setMoveInput(null); });
  const result = await fixture.evaluate(f => { const item = f.owned[0], r = item.runtime; const poses = []; for (let frame = 0; frame < 120; frame++) { r.step(1 / 120); poses.push(r.getEntityPose('traveler')); } return { starts: item.starts, lands: item.lands, end: r.getEntityPose('traveler'), entity: r.getEntity('traveler'), peak: Math.max(...poses.map(pose => pose.elevation)) }; });
  await page.screenshot({ path: resolve(output, `user-repro-${removeAdjacentSteps ? 'without-steps' : 'full-scene'}-${native ? 'keys' : 'api'}.png`) });
  assert.deepEqual(result.end.position, { c: 3, r: 5 }); assert.equal(result.end.elevation, 54); assert.equal(result.end.airborne, false); assert.equal(result.starts.length, 1); assert.equal(result.lands.length, 1); assert.ok(result.peak <= 84.001);
  return { removeAdjacentSteps, native, takeoff, ...result };
});
await run('native W plus Space jumps northeast onto second floor and Space repeat does not autojump', async () => {
  await setup(); await page.locator('#jump-game-0').focus(); await page.keyboard.down('KeyW'); await page.keyboard.down('Space'); await page.keyboard.up('KeyW'); await step(.4);
  await page.keyboard.down('Space'); await step(.8); await page.keyboard.down('Space'); await step(1); await page.keyboard.up('Space');
  const state = await fixture.evaluate(f => ({ pose: f.owned[0].runtime.getEntityPose('actor'), starts: f.owned[0].starts }));
  assert.equal(state.starts.length, 1); assert.deepEqual(state.pose.position, { c: 4, r: 4, level: 'bridge' }); assert.equal(state.pose.airborne, false); return state;
});
await run('native Space inside editable fields or outside game does not jump', async () => {
  await setup(); await fixture.evaluate(f => f.owned[0].host.insertAdjacentHTML('beforeend', '<input id="jump-edit"><textarea id="jump-area"></textarea><div id="jump-content" contenteditable="true">Text</div>'));
  for (const id of ['jump-edit', 'jump-area', 'jump-content', 'outside']) { await page.locator(`#${id}`).focus(); await page.keyboard.press('Space'); await step(1); }
  assert.equal(await fixture.evaluate(f => f.owned[0].starts.length), 0); return { protectedFields: 4 };
});
await run('two-finger mobile Dpad plus Jump preserves direction and does not pan map', async () => {
  await setup(true); const pad = await page.locator('.runtime-dpad [data-key="KeyW"]').boundingBox(), jump = await page.getByRole('button', { name: 'Jump', exact: true }).boundingBox(); assert.ok(pad && jump);
  const camera = await fixture.evaluate(f => f.owned[0].runtime.getCamera()); const cdp = await context.newCDPSession(page);
  const a = { x: pad.x + pad.width / 2, y: pad.y + pad.height / 2, id: 1 }, b = { x: jump.x + jump.width / 2, y: jump.y + jump.height / 2, id: 2 };
  try {
    await cdp.send('Input.dispatchTouchEvent', { type: 'touchStart', touchPoints: [a] });
    await cdp.send('Input.dispatchTouchEvent', { type: 'touchStart', touchPoints: [a, b] }); await step(.2);
    await page.screenshot({ path: resolve(output, 'two-finger-jump.png') });
    await cdp.send('Input.dispatchTouchEvent', { type: 'touchEnd', touchPoints: [] }); const end = await step(1);
    assert.deepEqual(end.position, { c: 4, r: 4, level: 'bridge' }); assert.equal(end.airborne, false); assert.deepEqual(await fixture.evaluate(f => f.owned[0].runtime.getCamera()), camera);
    assert.equal(await fixture.evaluate(f => f.owned[0].starts.length), 1); return end;
  } finally { await cdp.send('Input.dispatchTouchEvent', { type: 'touchCancel', touchPoints: [] }).catch(() => {}); await cdp.detach(); }
});
await run('native Jump button keyboard activation fires once and paused action is disabled', async () => {
  await setup(true); const button = page.getByRole('button', { name: 'Jump', exact: true }); await button.focus(); await page.keyboard.down('Space'); await step(1); await page.keyboard.down('Space'); await page.keyboard.up('Space'); await step(1);
  assert.equal(await fixture.evaluate(f => f.owned[0].starts.length), 1); await fixture.evaluate(f => f.owned[0].runtime.pause()); const box = await button.boundingBox(); assert.ok(box); await page.mouse.click(box.x + box.width / 2, box.y + box.height / 2); await page.keyboard.press('Enter'); assert.equal(await button.getAttribute('aria-disabled'), 'true'); assert.equal(await fixture.evaluate(f => f.owned[0].starts.length), 1); return { starts: 1, disabled: true };
});

const report = { kind: 'Independent browser runtime API and native input instrumentation; not GUI certification or public VPS end-to-end testing', url: page.url(), timestamp: new Date().toISOString(), results, pageErrors: errors, passed: results.filter(test => test.pass).length, total: results.length };
await writeFile(resolve(output, 'results.json'), JSON.stringify(report, null, 2));
for (const test of results) console.log(`${test.pass ? 'PASS' : 'FAIL'} ${test.name}${test.error ? `\n${test.error}` : ''}`);
console.log(`${report.passed}/${report.total} jump/projectile browser checks; ${errors.length} page errors. Report: ${output}`);
await browser.close();
process.exitCode = report.passed !== report.total || errors.length ? 1 : 0;
