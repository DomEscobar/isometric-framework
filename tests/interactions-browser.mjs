import { createRequire } from 'node:module';
import { mkdir, writeFile } from 'node:fs/promises';
import { resolve } from 'node:path';

const require = createRequire(resolve(process.env.RUNTIME_QA_PACKAGE ?? 'package.json'));
const { chromium } = require('playwright');
const output = resolve(process.env.RUNTIME_QA_OUTPUT ?? 'test-results/interactions-api');
await mkdir(output, { recursive: true });
const browser = await chromium.launch({ headless: true });
const page = await browser.newPage({ viewport: { width: 1000, height: 800 } });
const errors = [], results = [];
page.on('pageerror', error => errors.push(error.message));
await page.route('**/interactions-qa-host', route => route.fulfill({ contentType: 'text/html', body: '<!doctype html><html><body style="margin:0"></body></html>' }));
await page.goto(`${process.env.RUNTIME_QA_URL ?? 'http://127.0.0.1:4175'}/interactions-qa-host`);
const fixture = await page.evaluateHandle(async () => {
  const api = await import('/src/index.ts');
  const atlas = document.createElement('canvas'); atlas.width = 24; atlas.height = 12;
  const ctx = atlas.getContext('2d');
  ['#ff0000', '#00ff00', '#0000ff'].forEach((color, i) => { ctx.fillStyle = color; ctx.fillRect(i * 8, 0, 8, 12); });
  const url = atlas.toDataURL(), owned = [];
  const check = (value, message) => { if (!value) throw Error(message); };
  const scene = () => ({ version: 2, name: 'Interaction fixture', levels: [], links: [], tileWidth: 64, tileHeight: 32,
    map: Array.from({ length: 7 }, () => Array(7).fill('floor')), tiles: { floor: { color: 0xcccccc } }, diagonal: false,
    assets: { images: { atlas: { url, sampling: 'nearest' } }, textures: Object.fromEntries(['red', 'green', 'blue'].map((id, i) => [id, { image: 'atlas', frame: { x: i * 8, y: 0, width: 8, height: 12 } }])),
      animations: { pick: { frames: ['green', 'blue'], fps: 4, loop: false }, recover: { frames: ['blue', 'green'], fps: 4, loop: false } } },
    entityTypes: { actor: { visual: { kind: 'sprite', texture: 'red', width: 16, anchor: { x: .5, y: 1 }, offset: { x: 3, y: -2 } }, bodyHeight: 24, blocking: true },
      flower: { visual: { kind: 'box', color: 0xffff00, height: 10 }, blocking: true } },
    entities: [{ id: 'actor', type: 'actor', c: 1, r: 2 }, { id: 'flower', type: 'flower', c: 4, r: 2 }], controlledId: 'actor' });
  return { api, owned, scene, check,
    async spawn(options = {}, data = scene()) {
      const host = document.createElement('div'); host.id = 'interaction-game'; host.style.cssText = 'position:relative;width:640px;height:480px';
      const panel = document.createElement('aside'); document.body.append(host, panel);
      const runtime = new api.Runtime({ container: host, scene: data, autoStart: false, input: false, speed: 4, ...options });
      const item = { host, panel, runtime, count: 0, phases: [], runtimeErrors: [] }; owned.push(item);
      runtime.on('error', event => item.runtimeErrors.push(String(event.error ?? event)));
      await runtime.ready; runtime.setCamera({ x: 100, y: 240, zoom: 1 }); runtime.step(0);
      item.controller = api.createInteractions(runtime, { onChange: state => item.phases.push(state), onError: error => item.runtimeErrors.push(error.message) });
      item.action = { id: 'pick-flower', prepareSeconds: .6, recoverSeconds: .4,
        clips: { ne: 'pick', se: 'pick', sw: 'pick', nw: 'pick' }, recoveryClips: { ne: 'recover', se: 'recover', sw: 'recover', nw: 'recover' },
        perform: ({ target }) => { if (!runtime.remove(target.id)) return false; item.count++; return true; } };
      item.request = () => item.controller.request({ actorId: 'actor', targetId: 'flower', action: item.action });
      item.until = phase => { for (let i = 0; i < 200 && item.controller.getState().phase !== phase; i++) runtime.step(.05);
        check(item.controller.getState().phase === phase, `Expected ${phase}, got ${JSON.stringify(item.controller.getState())}`); };
      return item;
    },
    cleanup() { for (const item of owned) { item.dpad?.destroy(); item.controller.destroy(); item.overlay?.destroy(); item.runtime.destroy(); item.host.remove(); item.panel.remove(); } owned.length = 0; },
  };
});
const run = async (name, test) => {
  try { results.push({ name, pass: true, evidence: await test() }); }
  catch (error) { results.push({ name, pass: false, error: error.stack }); await page.screenshot({ path: resolve(output, `failure-${results.length}.png`) }).catch(() => {}); }
  finally { await fixture.evaluate(f => { for (const item of f.owned) f.check(item.runtimeErrors.length === 0, `Runtime errors: ${item.runtimeErrors}`); }).catch(error => { results.at(-1).pass = false; results.at(-1).error = `${results.at(-1).error ?? ''}\n${error.stack}`; }); await fixture.evaluate(f => f.cleanup()); }
};
const api = (name, test, argument) => run(name, () => fixture.evaluate(test, argument));

await api('approach follows axis edges, faces target, applies one effect and restores automatic art', async f => {
  const item = await f.spawn(), r = item.runtime; f.check(item.request(), 'request rejected');
  f.check(item.controller.getState().phase === 'approaching', 'did not approach');
  const route = r.getDebugSnapshot().entities.find(x => x.id === 'actor').route;
  let previous = r.getEntity('actor'); for (const cell of route) { f.check(Math.abs(cell.c - previous.c) + Math.abs(cell.r - previous.r) === 1, 'diagonal approach'); previous = cell; }
  item.until('preparing'); const preparing = r.getDebugSnapshot().entities.find(x => x.id === 'actor');
  f.check(preparing.cell.c === 3 && preparing.cell.r === 2 && preparing.sprite.facing === 'ne' && preparing.sprite.override === 'pick', 'wrong interaction edge/facing/clip');
  f.check(item.count === 0, 'effect fired before preparation'); item.until('recovering');
  f.check(item.count === 1 && !r.getEntity('flower'), 'effect not committed exactly once');
  f.check(r.getDebugSnapshot().entities[0].sprite.override === 'recover', 'missing recovery clip'); item.until('idle'); r.step(2);
  f.check(item.count === 1 && r.getDebugSnapshot().entities[0].sprite.override === null, 'duplicate effect or lingering override');
  return { route, preparing, result: item.controller.getState(), count: item.count };
});
await api('repeated requests preserve preparation clock and cannot duplicate a consumed target', async f => {
  const item = await f.spawn(); item.request(); item.until('preparing'); item.runtime.step(.2);
  const before = item.controller.getState(); for (let i = 0; i < 30; i++) f.check(item.request(), 'same active request rejected');
  f.check(item.controller.getState().elapsedSeconds === before.elapsedSeconds, 'spam reset clock'); item.until('recovering');
  for (let i = 0; i < 30; i++) item.request(); item.until('idle');
  f.check(!item.request() && item.count === 1, 'consumed target accepted or duplicated'); return { before, count: item.count };
});
await api('pause freezes preparation, sprite frame and recovery; resume finishes once', async f => {
  const item = await f.spawn(), r = item.runtime; item.request(); item.until('preparing'); r.step(.2); r.pause();
  const state = JSON.stringify(item.controller.getState()), art = JSON.stringify(r.getDebugSnapshot().entities[0].sprite);
  r.step(5); f.check(JSON.stringify(item.controller.getState()) === state && JSON.stringify(r.getDebugSnapshot().entities[0].sprite) === art && item.count === 0, 'paused preparation advanced');
  r.resume(); item.until('recovering'); r.pause(); const recovery = JSON.stringify(item.controller.getState()); r.step(5);
  f.check(JSON.stringify(item.controller.getState()) === recovery && item.count === 1, 'paused recovery advanced'); r.resume(); item.until('idle'); return { count: item.count };
});
for (const phase of ['approaching', 'preparing', 'recovering']) await api(`cancellation during ${phase} stops movement and preserves only committed effects`, async (f, phase) => {
  const item = await f.spawn(), r = item.runtime; item.request(); item.until(phase); item.controller.cancel('user-cancel');
  const pose = JSON.stringify(r.getEntityPose('actor')); r.step(3);
  f.check(item.controller.getState().phase === 'idle' && JSON.stringify(r.getEntityPose('actor')) === pose, 'cancel left active movement');
  f.check(item.count === (phase === 'recovering' ? 1 : 0), 'cancel changed committed effect count');
  f.check(r.getDebugSnapshot().entities[0].sprite.override === null, 'cancel left override'); return { state: item.controller.getState(), count: item.count };
}, phase);
for (const kind of ['move', 'input', 'jump', 'stop']) await api(`external ${kind} command cancels preparation without later effect`, async (f, kind) => {
  const item = await f.spawn(), r = item.runtime; item.request(); item.until('preparing');
  if (kind === 'move') r.moveTo('actor', { c: 2, r: 3 });
  else if (kind === 'input') r.setMoveInput({ x: -1, y: 1 });
  else if (kind === 'jump') r.jump();
  else r.stop('actor');
  f.check(item.controller.getState().phase === 'idle', `${kind} did not cancel`); r.step(2); r.setMoveInput(null);
  f.check(item.count === 0 && !!r.getEntity('flower') && r.getDebugSnapshot().entities[0].sprite.override === null, 'effect or stale art after command'); return item.controller.getState();
}, kind);
for (const input of ['keyboard', 'dpad']) await run(`native ${input} release after interrupting preparation cannot leave movement held`, async () => {
  await fixture.evaluate(async (f, input) => {
    const data = f.scene(); data.entities.find(x => x.id === 'flower').c = 2;
    const item = await f.spawn({ input: true }, data); if (input === 'dpad') item.dpad = f.api.createDpad(item.runtime, item.host);
    f.check(item.request() && item.controller.getState().phase === 'preparing', 'fixture is not preparing adjacent to target');
  }, input);
  try {
    if (input === 'keyboard') { await page.locator('#interaction-game').focus(); await page.keyboard.down('KeyD'); }
    else { const box = await page.locator('.runtime-dpad [data-key="KeyD"]').boundingBox(); await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2); await page.mouse.down(); }
    await fixture.evaluate(f => { const item = f.owned[0]; item.runtime.step(.1); f.check(item.controller.getState().phase === 'idle', 'native input did not interrupt action'); });
    if (input === 'keyboard') await page.keyboard.up('KeyD'); else await page.mouse.up();
    return await fixture.evaluate(f => {
      const item = f.owned[0]; item.runtime.step(1); const first = item.runtime.getEntityPose('actor');
      f.check(first.position.c === 1 && first.position.r === 3 && !first.airborne, `released input passed first tile: ${JSON.stringify(first)}`);
      item.runtime.step(2); const settled = item.runtime.getEntityPose('actor');
      f.check(JSON.stringify(settled) === JSON.stringify(first) && item.count === 0, 'released input continued movement or effect');
      f.check(!item.dpad?.element.querySelector('[aria-pressed="true"]'), 'Dpad stayed pressed'); return { first, settled };
    });
  } finally { await page.keyboard.up('KeyD'); await page.mouse.up(); }
});

await api('scene replacement cancels action and leaves replacement actor art intact', async f => {
  const item = await f.spawn(), r = item.runtime; item.request(); item.until('preparing');
  const next = f.scene(); next.name = 'Replacement'; next.entityTypes.actor.visual.texture = 'blue'; await r.loadScene(next); r.step(3);
  f.check(item.controller.getState().phase === 'idle' && item.count === 0, 'old action survived scenechange');
  const snapshot = r.getDebugSnapshot(); f.check(snapshot.sceneName === 'Replacement' && snapshot.entities[0].sprite.texture === 'blue', 'old cleanup altered replacement art'); return snapshot.entities[0].sprite;
});
await api('camera listener destroying runtime during scene fit aborts load cleanly', async f => {
  const item = await f.spawn({ autoStart: true }), r = item.runtime;
  r.on('camerachange', () => r.destroy()); let failure;
  try { await r.loadScene(f.scene()); } catch (error) { failure = { name: error.name, message: error.message }; }
  f.check(failure?.name === 'AbortError', `destroying camera callback did not produce AbortError: ${JSON.stringify(failure)}`);
  return failure;
});
await api('camera listener superseding scene load preserves newest scene and reports old load aborted', async f => {
  const item = await f.spawn(), r = item.runtime; let pending;
  const off = r.on('camerachange', () => { off(); const newest = f.scene(); newest.name = 'Newest'; newest.entityTypes.actor.visual.texture = 'blue'; pending = r.loadScene(newest); });
  const older = f.scene(); older.name = 'Superseded'; let failure;
  try { await r.loadScene(older); } catch (error) { failure = { name: error.name, message: error.message }; }
  await pending; r.step(0); const snapshot = r.getDebugSnapshot();
  f.check(failure?.name === 'AbortError', `superseded scene did not reject AbortError: ${JSON.stringify(failure)}`);
  f.check(snapshot.sceneName === 'Newest' && snapshot.entities[0].sprite.texture === 'blue', 'superseded cleanup damaged latest scene');
  return { failure, sceneName: snapshot.sceneName, sprite: snapshot.entities[0].sprite };
});
await api('removing the target during preparation cancels without awarding an item', async f => {
  const item = await f.spawn(); item.request(); item.until('preparing'); item.runtime.remove('flower'); item.runtime.step(2);
  f.check(item.count === 0 && item.controller.getState().phase === 'idle' && item.runtime.getDebugSnapshot().entities[0].sprite.override === null, 'missing target still produced effect');
  return item.controller.getState();
});
await api('destroying only the controller clears its motion and art while runtime remains usable', async f => {
  const item = await f.spawn(); item.request(); item.until('preparing'); item.controller.destroy(); item.runtime.step(2);
  f.check(!item.request() && item.count === 0 && item.runtime.getDebugSnapshot().entities[0].sprite.override === null, 'disposed controller remained active');
  f.check(item.runtime.moveTo('actor', { c: 2, r: 3 }) === 'started', 'controller disposal damaged runtime'); item.runtime.step(2);
  const actor = item.runtime.getEntity('actor'); f.check(actor.c === 2 && actor.r === 3, 'runtime cannot move after controller disposal'); return actor;
});
await api('runtime destruction disposes active interaction and debug overlay exactly once', async f => {
  const item = await f.spawn(); item.request(); item.until('preparing');
  item.overlay = f.api.createDebugOverlay(item.runtime, { container: item.host, panel: item.panel }); item.overlay.setEnabled(true);
  let destroys = 0; item.runtime.on('destroy', () => destroys++); item.runtime.destroy(); item.runtime.destroy();
  f.check(destroys === 1 && item.controller.getState().phase === 'idle' && !item.request() && item.count === 0, 'destroy lifecycle broken');
  f.check(!item.host.querySelector('[data-runtime-debug]') && !item.panel.childElementCount, 'debug DOM leaked'); return { destroys, state: item.controller.getState() };
});
await api('facing and detached debug snapshots expose current art without permitting world mutation', async f => {
  const item = await f.spawn(), r = item.runtime; f.check(r.setFacing('actor', 'nw'), 'facing rejected'); r.setAnimation('actor', 'pick'); r.step(.3);
  const snapshot = r.getDebugSnapshot(), actor = snapshot.entities.find(x => x.id === 'actor');
  f.check(actor.sprite.facing === 'nw' && actor.sprite.frame === 1 && actor.sprite.texture === 'blue' && actor.sprite.anchor.x === .5 && actor.sprite.offset.x === 3, 'inaccurate sprite diagnostic');
  actor.cell.c = 99; actor.pose.position.c = 99; actor.sprite.anchor.x = 99; snapshot.camera.x = 99; snapshot.tiles[0].cell.c = 99;
  const current = r.getDebugSnapshot(); f.check(current.entities[0].cell.c === 1 && current.entities[0].pose.position.c === 1 && current.entities[0].sprite.anchor.x === .5 && current.camera.x === 100 && current.tiles[0].cell.c === 0, 'debug snapshot aliases runtime');
  f.check(!r.setFacing('missing', 'ne'), 'missing actor accepted'); return current.entities[0];
});
await api('debug overlay defaults off and follows paused camera and manual resize refresh', async f => {
  const item = await f.spawn(), r = item.runtime; item.overlay = f.api.createDebugOverlay(r, { container: item.host, panel: item.panel });
  const svg = item.host.querySelector('[data-runtime-debug]'); f.check(item.panel.hidden && svg.style.display === 'none', 'debug enabled by default');
  item.overlay.setEnabled(true); f.check(!item.panel.hidden && svg.querySelectorAll('polygon').length > 40, 'debug grid absent');
  const before = svg.querySelector('rect').getAttribute('x'); r.pause(); r.setCamera({ x: 140, y: 240, zoom: 1 });
  f.check(Number(svg.querySelector('rect').getAttribute('x')) - Number(before) === 40, 'paused camera drift');
  item.host.style.width = '500px'; r.resize(); item.overlay.refresh(); f.check(svg.getAttribute('viewBox') === '0 0 500 480', 'resize viewBox stale');
  f.check(item.panel.textContent.includes('Facing:') && item.panel.textContent.includes('Footprint:'), 'debug readout absent');
  item.overlay.setEnabled(false); f.check(item.panel.hidden && svg.style.display === 'none', 'toggle off failed'); return { viewBox: svg.getAttribute('viewBox') };
});
await run('debug readout follows approach route and current interaction clip', async () => {
  const evidence = await fixture.evaluate(async f => {
    const item = await f.spawn(); item.overlay = f.api.createDebugOverlay(item.runtime, { container: item.host, panel: item.panel }); item.overlay.setEnabled(true); item.request(); item.runtime.step(.1);
    const svg = item.host.querySelector('[data-runtime-debug]'); f.check(!!svg.querySelector('polyline') && !item.panel.textContent.includes('Route: none'), 'approach route missing from overlay');
    item.until('preparing'); item.runtime.step(.1); item.overlay.refresh();
    const readout = item.panel.querySelector('[data-debug-details]').textContent;
    f.check(readout.includes('Facing: ne') && readout.includes('Clip: pick') && readout.includes('override: pick') && !svg.querySelector('polyline'), 'debug details do not match preparation');
    return { readout };
  });
  await page.screenshot({ path: resolve(output, 'interaction-debug-preparing.png') }); return evidence;
});
for (const automatic of [false, true]) await run(`native tile click passes through overlay with clickToMove ${automatic}`, async () => {
  const point = await fixture.evaluate(async (f, automatic) => {
    const item = await f.spawn({ input: true, clickToMove: automatic }); item.clicks = [];
    item.runtime.on('tileclick', event => item.clicks.push(event)); item.overlay = f.api.createDebugOverlay(item.runtime, { container: item.host, panel: item.panel }); item.overlay.setEnabled(true);
    const point = item.runtime.cellToScreen({ c: 2, r: 4 }); return { x: point.x, y: point.y };
  }, automatic);
  await page.mouse.click(point.x, point.y);
  return fixture.evaluate((f, automatic) => { const item = f.owned[0]; item.runtime.step(2); const actor = item.runtime.getEntity('actor');
    f.check(item.clicks.length === 1 && item.clicks[0].cell.c === 2 && item.clicks[0].cell.r === 4, 'overlay intercepted native click');
    f.check(actor.c === (automatic ? 2 : 1) && actor.r === (automatic ? 4 : 2), 'clickToMove mode incorrect'); return { actor, clicks: item.clicks };
  }, automatic);
});

const report = { kind: 'Chromium public runtime API integration and native pointer checks; not VPS end-to-end certification', url: page.url(), timestamp: new Date().toISOString(), results, pageErrors: errors, passed: results.filter(x => x.pass).length, total: results.length };
await writeFile(resolve(output, 'results.json'), JSON.stringify(report, null, 2));
for (const result of results) console.log(`${result.pass ? 'PASS' : 'FAIL'} ${result.name}${result.error ? `\n${result.error}` : ''}`);
console.log(`${report.passed}/${report.total} interaction browser checks passed; ${errors.length} page errors. Report: ${output}`);
await browser.close();
process.exitCode = report.passed !== report.total || errors.length ? 1 : 0;
