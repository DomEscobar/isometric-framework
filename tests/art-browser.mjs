import { createRequire } from 'node:module';
import { mkdir, writeFile } from 'node:fs/promises';
import { resolve } from 'node:path';

const require = createRequire(resolve(process.env.RUNTIME_QA_PACKAGE ?? 'package.json'));
const { chromium } = require('playwright');
const output = resolve(process.env.RUNTIME_QA_OUTPUT ?? 'test-results/art-api');
await mkdir(output, { recursive: true });
const browser = await chromium.launch({ headless: true });
const context = await browser.newContext({ viewport: { width: 1100, height: 850 }, deviceScaleFactor: 1 });
const page = await context.newPage();
const errors = [], results = [];
page.on('pageerror', error => errors.push(error.message));
await page.route('**/art-qa-host', route => route.fulfill({ contentType: 'text/html', body: '<!doctype html><html><body style="margin:0"></body></html>' }));
await page.route('**/art-missing.png', route => route.fulfill({ status: 404, body: 'missing' }));
await page.goto(`${process.env.RUNTIME_QA_URL ?? 'http://127.0.0.1:4175'}/art-qa-host`);

// These fixtures use the public package API and pixels from its public canvas.
// The deliberately adjacent solid frames make atlas leakage unambiguous.
const fixture = await page.evaluateHandle(async () => {
  const api = await import('/src/index.ts');
  const colors = { red: [255, 0, 0], green: [0, 255, 0], blue: [0, 0, 255], yellow: [255, 255, 0], magenta: [255, 0, 255], cyan: [0, 255, 255], white: [255, 255, 255], orange: [255, 128, 0] };
  const atlas = document.createElement('canvas'); atlas.width = 64; atlas.height = 12;
  const ctx = atlas.getContext('2d');
  Object.values(colors).forEach((rgb, i) => { ctx.fillStyle = `rgb(${rgb})`; ctx.fillRect(i * 8, 0, 8, 12); });
  const url = atlas.toDataURL();
  const owned = [], loads = [];
  const srcDescriptor = Object.getOwnPropertyDescriptor(HTMLImageElement.prototype, 'src');
  Object.defineProperty(HTMLImageElement.prototype, 'src', { ...srcDescriptor, set(value) { if (value) loads.push(String(value)); srcDescriptor.set.call(this, value); } });
  const check = (value, message) => { if (!value) throw Error(message); };
  const manifest = () => ({ images: { atlas: { url, sampling: 'nearest' } },
    textures: Object.fromEntries(Object.keys(colors).map((id, i) => [id, { image: 'atlas', frame: { x: i * 8, y: 0, width: 8, height: 12 } }])),
    animations: { idle: { frames: ['red', 'green'], fps: 4 }, walk: { frames: ['blue'], fps: 4 }, jump: { frames: ['yellow'], fps: 4 }, once: { frames: ['magenta', 'cyan'], fps: 4, loop: false },
      ne: { frames: ['green'] }, se: { frames: ['blue'] }, sw: { frames: ['yellow'] }, nw: { frames: ['magenta'] } } });
  const scene = () => ({ version: 2, levels: [], links: [], name: 'Art fixture', tileWidth: 64, tileHeight: 32, assets: manifest(),
    map: Array.from({ length: 9 }, () => Array(9).fill('floor')), tiles: { floor: { color: 0x343434 } },
    entityTypes: { actor: { visual: { kind: 'sprite', texture: 'red', width: 16 }, bodyHeight: 24, blocking: true } },
    entities: [{ id: 'actor', type: 'actor', c: 4, r: 4 }], controlledId: 'actor', diagonal: true });
  const pixels = item => { item.runtime.step(0); const source = item.host.querySelector('canvas'); const copy = document.createElement('canvas'); copy.width = source.width; copy.height = source.height; const c = copy.getContext('2d'); c.drawImage(source, 0, 0); return { data: c.getImageData(0, 0, copy.width, copy.height).data, width: copy.width, height: copy.height, png: copy.toDataURL() }; };
  const bounds = (item, name) => { const p = pixels(item), rgb = colors[name]; let count = 0, left = Infinity, right = -1, top = Infinity, bottom = -1;
    for (let y = 0; y < p.height; y++) for (let x = 0; x < p.width; x++) { const i = (y * p.width + x) * 4; if (rgb.every((v, k) => p.data[i + k] === v)) { count++; left = Math.min(left, x); right = Math.max(right, x); top = Math.min(top, y); bottom = Math.max(bottom, y); } }
    return { count, left, right, top, bottom, width: count ? right - left + 1 : 0, height: count ? bottom - top + 1 : 0 }; };
  const color = (item, name, count = 384) => { const b = bounds(item, name); check(b.count === count, `${name} silhouette expected ${count} pixels, observed ${JSON.stringify(b)}`); return b; };
  return { api, colors, url, manifest, scene, owned, loads, check, pixels, bounds, color,
    async spawn(data = scene(), options = {}) { const host = document.createElement('div'); host.id = `art-game-${owned.length}`; host.style.cssText = 'position:relative;width:520px;height:390px;display:inline-block;vertical-align:top'; document.body.append(host);
      const runtime = new api.Runtime({ container: host, scene: data, autoStart: false, input: false, speed: 1, background: 0, ...options }); const item = { host, runtime }; owned.push(item); await runtime.ready; runtime.setCamera({ x: 4, y: 220, zoom: 1 }); runtime.step(0); return item; },
    cleanup() { for (const item of owned) { try { item.runtime.destroy(); } catch {} item.host.remove(); } owned.length = 0; loads.length = 0; },
    restore() { Object.defineProperty(HTMLImageElement.prototype, 'src', srcDescriptor); },
  };
});
const run = async (name, test) => {
  try { results.push({ name, pass: true, evidence: await test() }); if ([1, 3, 6, 19].includes(results.length)) await page.screenshot({ path: resolve(output, `passed-${results.length}.png`) }); }
  catch (error) { results.push({ name, pass: false, error: error.stack }); await page.screenshot({ path: resolve(output, `failure-${results.length}.png`) }).catch(() => {}); }
  finally { await fixture.evaluate(f => f.cleanup()); for (const key of ['KeyW', 'KeyA', 'KeyS', 'KeyD']) await page.keyboard.up(key); }
};
const api = (name, test) => run(name, () => fixture.evaluate(test));

await api('named atlas crop has exact silhouette and no neighboring-frame bleed', async f => {
  const item = await f.spawn(); const b = f.color(item, 'red');
  f.check(b.width === 16 && b.height === 24, 'crop aspect ratio was not preserved');
  for (const name of Object.keys(f.colors).filter(x => x !== 'red')) f.check(f.bounds(item, name).count === 0, `adjacent ${name} frame leaked`);
  return b;
});
await api('nearest sampling retains exact colors at fractional display scale', async f => {
  const data = f.scene(); data.entityTypes.actor.visual.width = 17;
  const item = await f.spawn(data), p = f.pixels(item), center = item.runtime.cellToScreen({ c: 4, r: 4 });
  // Interior pixels are well clear of antialiased geometry edges.
  for (let y = center.y - 23; y < center.y - 2; y++) for (let x = center.x - 6; x < center.x + 6; x++) {
    const i = (y * p.width + x) * 4; f.check(p.data[i] === 255 && p.data[i + 1] === 0 && p.data[i + 2] === 0, 'sampling blended adjacent atlas frames');
  }
  return f.bounds(item, 'red');
});
await api('texture anchor, explicit width, scale and offset align with feet', async f => {
  // Keep all art above feet so foreground terrain cannot occlude this alignment probe.
  const data = f.scene(); data.assets.textures.red.anchor = { x: 0, y: 0 }; Object.assign(data.entityTypes.actor.visual, { width: 16, scale: 2, offset: { x: 7, y: -60 } });
  const item = await f.spawn(data), b = f.color(item, 'red', 1536), feet = item.runtime.cellToScreen({ c: 4, r: 4 });
  f.check(b.left === feet.x + 7 && b.top === feet.y - 60 && b.width === 32 && b.height === 48, `anchor alignment ${JSON.stringify({ b, feet })}`); return { b, feet };
});
await api('visual anchor overrides manifest anchor and tint multiplies source color', async f => {
  const data = f.scene(); data.assets.textures.white.anchor = { x: 0, y: 0 }; Object.assign(data.entityTypes.actor.visual, { texture: 'white', anchor: { x: .5, y: 1 }, tint: 0x00ffff });
  const item = await f.spawn(data), b = f.color(item, 'cyan'), feet = item.runtime.cellToScreen({ c: 4, r: 4 });
  f.check(b.left === feet.x - 8 && b.bottom === feet.y - 1, 'visual anchor did not override texture anchor'); return { b, feet };
});
await api('idle clip advances deterministically and pause freezes every art pixel', async f => {
  const data = f.scene(); data.entityTypes.actor.visual = { kind: 'sprite', animation: 'idle', width: 16 };
  const item = await f.spawn(data), r = item.runtime; f.color(item, 'red'); r.step(.26); f.color(item, 'green'); r.pause(); const before = f.pixels(item).png; r.step(4);
  f.check(f.pixels(item).png === before, 'paused animation advanced'); r.resume(); r.step(.25); return f.color(item, 'red');
});
await api('automatic idle walk jump and landing choose observable clips', async f => {
  const data = f.scene(); data.entityTypes.actor.visual.animations = { idle: 'idle', walk: 'walk', jump: 'jump' };
  const item = await f.spawn(data), r = item.runtime; f.color(item, 'red'); r.moveTo('actor', { c: 5, r: 4 }); r.step(.25); f.color(item, 'blue');
  r.stop('actor'); f.color(item, 'red'); f.check(r.jump() === 'started', 'hop blocked'); r.step(.2); f.color(item, 'yellow'); r.step(.6); f.check(!r.getEntityPose('actor').airborne, 'did not land');
  f.check(f.bounds(item, 'yellow').count === 0, 'landing retained jump clip'); return r.getEntityPose('actor');
});
await api('manual nonloop override clamps last frame and null restores automatic state', async f => {
  const data = f.scene(); data.entityTypes.actor.visual.animations = { idle: 'idle', walk: 'walk' };
  const item = await f.spawn(data), r = item.runtime; f.check(r.setAnimation('actor', 'once') === true, 'override rejected'); f.color(item, 'magenta'); r.step(.26); f.color(item, 'cyan'); r.step(2); f.color(item, 'cyan');
  r.moveTo('actor', { c: 5, r: 4 }); r.step(.25); f.color(item, 'cyan'); f.check(r.setAnimation('actor', null), 'automatic reset rejected'); return f.color(item, 'blue');
});
await api('unknown clip throws atomically; missing entity returns false', async f => {
  const item = await f.spawn(), r = item.runtime; r.setAnimation('actor', 'once'); const before = f.pixels(item).png; let rejected = false;
  try { r.setAnimation('actor', 'missing'); } catch { rejected = true; }
  f.check(rejected && f.pixels(item).png === before, 'unknown clip changed active visual'); f.check(r.setAnimation('missing-entity', 'once') === false, 'missing entity did not return false'); return f.color(item, 'magenta');
});
await api('requesting the same completed nonloop clip replays from its first frame', async f => {
  const item = await f.spawn(), r = item.runtime;
  f.check(r.setAnimation('actor', 'once'), 'initial override rejected'); f.color(item, 'magenta'); r.step(2); f.color(item, 'cyan');
  f.check(r.setAnimation('actor', 'once'), 'repeated override rejected'); const replayStart = f.color(item, 'magenta');
  r.step(.26); f.color(item, 'cyan'); r.step(2); return { replayStart, replayEnd: f.color(item, 'cyan') };
});
await run('native northeast midwalk stop returns to integer feet and keeps northeast idle facing', async () => {
  await fixture.evaluate(async f => { const data = f.scene(); data.entityTypes.actor.visual.animations = { idle: 'idle', walk: 'walk', directions: { ne: { idle: 'ne' }, sw: { idle: 'sw' } } }; await f.spawn(data, { input: true }); });
  await page.locator('#art-game-0').focus(); await page.keyboard.down('KeyW');
  await fixture.evaluate(f => { const item = f.owned[0]; item.runtime.step(.25); f.check(item.runtime.getEntityPose('actor').position.c === 4.25, 'fixture did not reach fractional NE pose'); f.color(item, 'blue'); });
  await page.keyboard.up('KeyW');
  return fixture.evaluate(f => { const item = f.owned[0], r = item.runtime; r.stop('actor'); const pose = r.getEntityPose('actor');
    f.check(pose.position.c === 4 && pose.position.r === 4 && !pose.airborne, 'stop did not restore original integer feet');
    const immediate = f.color(item, 'green'); r.step(.5); return { pose, immediate, settled: f.color(item, 'green') }; });
});
await api('late blocked flight rollback preserves northeast facing at original feet', async f => {
  const data = f.scene(); data.entityTypes.actor.visual.animations = { idle: 'idle', jump: 'jump', directions: { ne: { idle: 'ne' }, sw: { idle: 'sw' } } };
  data.entityTypes.wall = { visual: { kind: 'box', color: 0x454545, height: 160 }, bodyHeight: 160, blocking: true };
  const upper = Array.from({ length: 9 }, () => Array(9).fill(null)); upper[4][6] = 'floor'; data.levels = [{ id: 'bridge', name: 'Bridge', height: 72, map: upper }];
  const item = await f.spawn(data), r = item.runtime; r.setMoveInput({ x: 1, y: -1 }); f.check(r.jump() === 'started', 'flight did not start'); r.setMoveInput(null); r.step(.4);
  const airborne = r.getEntityPose('actor'); f.check(airborne.airborne && airborne.position.c > 4, 'flight did not establish northeast facing');
  r.add({ id: 'late-block', type: 'wall', c: 6, r: 4, level: 'bridge' }); r.step(1); const pose = r.getEntityPose('actor');
  f.check(!pose.airborne && pose.position.c === 4 && pose.position.r === 4 && pose.position.level !== 'bridge', `unsafe rollback ${JSON.stringify(pose)}`);
  return { pose, idleFacing: f.color(item, 'green') };
});

// Literal compatibility expectations from original isometric WASD axes, independent of implementation helpers.
for (const [key, clip, name, dc, dr] of [['KeyW', 'ne', 'green', 1, 0], ['KeyD', 'se', 'blue', 0, 1], ['KeyS', 'sw', 'yellow', -1, 0], ['KeyA', 'nw', 'magenta', 0, -1]]) {
  await run(`${key} selects ${clip.toUpperCase()} walk art and preserves native grid movement`, async () => {
    await fixture.evaluate(async f => { const data = f.scene(); data.entityTypes.actor.visual.animations = { directions: { ne: { idle: 'ne', walk: 'ne' }, se: { idle: 'se', walk: 'se' }, sw: { idle: 'sw', walk: 'sw' }, nw: { idle: 'nw', walk: 'nw' } } }; await f.spawn(data, { input: true }); });
    await page.locator('#art-game-0').focus(); await page.keyboard.down(key);
    const evidence = await fixture.evaluate((f, args) => { const [name, dc, dr] = args, item = f.owned[0], r = item.runtime; r.step(.25); const pose = r.getEntityPose('actor');
      f.check(pose.position.c === 4 + dc * .25 && pose.position.r === 4 + dr * .25, `wrong native axes ${JSON.stringify(pose)}`); return { pose, pixels: f.color(item, name) }; }, [name, dc, dr]);
    await page.keyboard.up(key); await fixture.evaluate((f, name) => { const item = f.owned[0]; item.runtime.step(1); f.color(item, name); }, name); return evidence;
  });
}

await api('one atlas image serves named frames and legacy URLs without duplicate loads', async f => {
  const data = f.scene(); data.assets.images.alias = { url: f.url }; data.assets.textures.alias = { image: 'alias', frame: { x: 8, y: 0, width: 8, height: 12 } };
  data.entityTypes.other = { visual: { kind: 'sprite', texture: 'alias', width: 16 } }; data.entityTypes.legacy = { visual: { kind: 'sprite', url: f.url } }; data.entities.push({ id: 'other', type: 'other', c: 3, r: 3 });
  const item = await f.spawn(data); f.check(f.loads.filter(url => url === f.url).length === 1, 'same source decoded more than once'); f.color(item, 'red'); f.color(item, 'green'); item.runtime.remove('actor'); return f.color(item, 'green');
});
await api('destroying or replacing one runtime leaves another shared-URL atlas intact', async f => {
  const first = await f.spawn(), second = await f.spawn(); const before = f.pixels(second).png;
  const other = f.scene(); other.entityTypes.actor.visual.texture = 'green'; await first.runtime.loadScene(other);
  f.check(f.pixels(second).png === before, 'replacing scene freed another instance resources');
  first.runtime.destroy(); f.check(f.pixels(second).png === before, 'destroy freed another instance resources');
  const replacement = f.scene(); replacement.entityTypes.actor.visual.texture = 'blue'; await second.runtime.loadScene(replacement); second.runtime.setCamera({ x: 4, y: 220, zoom: 1 });
  return f.color(second, 'blue');
});
await api('decoded out-of-bounds atlas frame rejects transaction and preserves live scene', async f => {
  const item = await f.spawn(), r = item.runtime, before = f.pixels(item).png, snapshot = JSON.stringify(r.serializeScene()); const broken = f.scene(); broken.name = 'invalid frame'; broken.assets.textures.red.frame.x = 63;
  let message = ''; try { await r.loadScene(broken); } catch (error) { message = error.message; }
  f.check(message.length > 0, 'out-of-image frame accepted'); f.check(JSON.stringify(r.serializeScene()) === snapshot && f.pixels(item).png === before, 'failed frame replaced active scene'); return { message, pixels: f.color(item, 'red') };
});
await api('missing atlas rejects without damaging old visuals or public state', async f => {
  const item = await f.spawn(), r = item.runtime, before = f.pixels(item).png, snapshot = JSON.stringify(r.serializeScene()); const broken = f.scene(); broken.assets.images.atlas.url = '/art-missing.png';
  let rejected = false; try { await r.loadScene(broken); } catch { rejected = true; }
  f.check(rejected && JSON.stringify(r.serializeScene()) === snapshot && f.pixels(item).png === before, 'missing image was not transactional'); return f.color(item, 'red');
});
await run('superseding a pending atlas load aborts it while old scene remains usable', async () => {
  let release, requested;
  const gate = new Promise(resolve => { release = resolve; }); const requestSeen = new Promise(resolve => { requested = resolve; });
  await page.route('**/art-delayed.png', async route => { requested(); await gate; await route.fulfill({ status: 404, body: 'cancelled fixture' }).catch(() => {}); });
  try {
    await fixture.evaluate(async f => { const item = await f.spawn(); item.before = f.pixels(item).png; const next = f.scene(); next.assets.images.atlas.url = '/art-delayed.png'; item.pending = item.runtime.loadScene(next).then(() => 'resolved', error => error.name); });
    await Promise.race([requestSeen, new Promise((_, reject) => setTimeout(() => reject(Error('delayed request not observed')), 5000))]);
    return await fixture.evaluate(async f => { const item = f.owned[0]; f.check(f.pixels(item).png === item.before, 'pending load blanked active view'); const next = f.scene(); next.name = 'newest'; next.entityTypes.actor.visual.texture = 'blue'; await item.runtime.loadScene(next); item.runtime.setCamera({ x: 4, y: 220, zoom: 1 });
      f.check(await item.pending === 'AbortError', 'superseded load did not abort'); f.check(item.runtime.serializeScene().name === 'newest', 'older scene won load race'); return f.color(item, 'blue'); });
  } finally { release(); await page.unroute('**/art-delayed.png'); }
});
await api('tile texture is clipped to top diamond with unchanged sides and background', async f => {
  const data = f.scene(); data.map = [['floor']]; data.entities = []; delete data.controlledId; data.tiles.floor.texture = 'red'; const item = await f.spawn(data); item.runtime.setCamera({ x: 100, y: 100, zoom: 1 }); const p = f.pixels(item);
  const rgb = (x, y) => Array.from(p.data.slice((y * p.width + x) * 4, (y * p.width + x) * 4 + 3));
  f.check(JSON.stringify(rgb(100, 100)) === '[255,0,0]', 'tile center did not use texture');
  for (const [x, y] of [[72, 87], [128, 87], [75, 112], [125, 112]]) f.check(JSON.stringify(rgb(x, y)) === '[0,0,0]', 'rectangular texture escaped diamond mask');
  f.check(JSON.stringify(rgb(100, 119)) !== '[255,0,0]', 'top texture spilled onto sidewall'); return { center: rgb(100, 100), side: rgb(100, 119) };
});
await api('tile variants render public deterministic selection and survive JSON reload', async f => {
  const data = f.scene(); data.entities = []; delete data.controlledId; data.tiles.floor.textures = ['red', 'green', 'blue'];
  const item = await f.spawn(data); const selections = [];
  for (let r = 2; r <= 5; r++) for (let c = 2; c <= 5; c++) { const cell = { c, r }, name = f.api.selectTileTexture(data.tiles.floor, cell), point = item.runtime.cellToScreen(cell), p = f.pixels(item), i = (point.y * p.width + point.x) * 4;
    f.check(f.colors[name].every((v, k) => p.data[i + k] === v), `tile ${c},${r} did not render selected ${name}`); selections.push(name); }
  f.check(new Set(selections).size > 1, 'variants all collapsed to one texture'); const before = f.pixels(item).png, saved = JSON.parse(JSON.stringify(item.runtime.serializeScene()));
  await item.runtime.loadScene(saved); item.runtime.setCamera({ x: 4, y: 220, zoom: 1 }); f.check(f.pixels(item).png === before, 'variants changed after scene serialization'); return { selections };
});
await api('tile side material repeats vertically with face shading and no atlas bleed', async f => {
  const atlas = document.createElement('canvas'); atlas.width = 64; atlas.height = 24;
  const context = atlas.getContext('2d'); context.fillStyle = '#00ff00'; context.fillRect(0, 0, 64, 24);
  context.fillStyle = '#ff0000'; context.fillRect(32, 8, 16, 4);
  context.fillStyle = '#0000ff'; context.fillRect(32, 12, 16, 4);
  const data = f.scene(); data.map = [['floor']]; data.entities = []; delete data.controlledId;
  data.assets.images.sides = { url: atlas.toDataURL(), sampling: 'nearest' };
  data.assets.textures.sides = { image: 'sides', frame: { x: 32, y: 8, width: 16, height: 8 } };
  data.tiles.floor = { color: 0x343434, elevation: 32, sideTexture: 'sides' };
  const item = await f.spawn(data); item.runtime.setCamera({ x: 100, y: 100, zoom: 1 });
  const p = f.pixels(item), samples = [];
  for (const [x, intensity] of [[84, 173], [116, 209]]) for (const offset of [2, 6, 10, 14, 34, 38]) {
    const index = ((76 + offset) * p.width + x) * 4, actual = Array.from(p.data.slice(index, index + 3));
    const expected = offset % 8 < 4 ? [intensity, 0, 0] : [0, 0, intensity];
    f.check(JSON.stringify(actual) === JSON.stringify(expected), `side material at ${x},${offset}: ${actual} instead of ${expected}`);
    samples.push(actual);
  }
  f.check(f.bounds(item, 'green').count === 0, 'side repeat sampled a neighboring atlas region');
  return { samples, elevation: item.runtime.getElevation({ c: 0, r: 0 }) };
});
await api('art width and scale do not alter explicit body height, footprint or routing', async f => {
  const data = f.scene(); data.entityTypes.wall = { visual: { kind: 'sprite', texture: 'white', width: 8 }, bodyHeight: 160, blocking: true }; data.entities.push({ id: 'wall', type: 'wall', c: 5, r: 4 });
  const first = await f.spawn(data), path = first.runtime.findPath('actor', { c: 6, r: 4 }); first.runtime.setMoveInput({ x: 1, y: -1 }); const jump = first.runtime.jump(); first.runtime.setMoveInput(null); first.runtime.step(1); const end = first.runtime.getEntity('actor');
  const bigger = structuredClone(data); bigger.entityTypes.wall.visual.width = 256; bigger.entityTypes.wall.visual.scale = 2; const second = await f.spawn(bigger);
  f.check(JSON.stringify(second.runtime.findPath('actor', { c: 6, r: 4 })) === JSON.stringify(path), 'presentation changed routing'); second.runtime.setMoveInput({ x: 1, y: -1 }); const secondJump = second.runtime.jump(); second.runtime.setMoveInput(null); second.runtime.step(1);
  f.check(secondJump === jump && JSON.stringify(second.runtime.getEntity('actor')) === JSON.stringify(end) && end.c === 4, 'presentation changed physical jump blocking'); return { path, jump, end };
});

await fixture.evaluate(f => f.restore());
const report = { kind: 'Independent Chromium public runtime API and canvas pixel instrumentation; not GUI certification or VPS end-to-end testing', url: page.url(), timestamp: new Date().toISOString(), results, pageErrors: errors, passed: results.filter(x => x.pass).length, total: results.length };
await writeFile(resolve(output, 'results.json'), JSON.stringify(report, null, 2));
for (const result of results) console.log(`${result.pass ? 'PASS' : 'FAIL'} ${result.name}${result.error ? `\n${result.error}` : ''}`);
console.log(`${report.passed}/${report.total} art browser checks passed; ${errors.length} page errors. Report: ${output}`);
await browser.close();
process.exitCode = report.passed !== report.total || errors.length ? 1 : 0;
