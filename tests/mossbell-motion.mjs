import { chromium } from 'playwright';
import assert from 'node:assert/strict';
import { mkdir, writeFile } from 'node:fs/promises';
import { resolve } from 'node:path';

const output = resolve('test-results/mossbell/motion');
await mkdir(output, { recursive: true });
const browser = await chromium.launch({ channel: 'chrome' });
const page = await browser.newPage({ viewport: { width: 900, height: 700 } });
const errors = [];
page.on('pageerror', error => errors.push(error.message));

try {
  await page.goto(`${process.env.RUNTIME_QA_URL ?? 'http://127.0.0.1:4175'}/examples/mossbell/`);
  await page.waitForFunction(() => window.__MOSSBELL__);
  const fixture = await page.evaluateHandle(async () => {
    const api = await import('/src/index.ts');
    const { createWorld } = await import('/examples/mossbell/scene.ts');
    const container = document.createElement('div');
    Object.assign(container.style, { position: 'fixed', inset: '0', background: '#17232c' });
    document.body.replaceChildren(container);
    const runtime = await api.createRuntime({ container, scene: createWorld('forest', 'seeking').scene, autoStart: false, input: false });
    runtime.step(0);
    return { runtime };
  });
  const frames = () => fixture.evaluate(({ runtime }) => runtime.getDebugSnapshot().entities
    .filter(entity => entity.type === 'flow' || entity.type === 'fern' || entity.type === 'fernB')
    .map(entity => ({ id: entity.id, frame: entity.sprite?.frame })));
  const start = await frames();
  const frame0 = await page.screenshot({ path: resolve(output, 'frame0.png') });
  await fixture.evaluate(({ runtime }) => runtime.step(.2));
  const advanced = await frames();
  const frame1 = await page.screenshot({ path: resolve(output, 'frame1.png') });
  assert.notDeepEqual(advanced, start);
  assert.ok(!frame0.equals(frame1));
  await fixture.evaluate(({ runtime }) => { runtime.pause(); runtime.step(.8); });
  assert.deepEqual(await frames(), advanced);
  await fixture.evaluate(({ runtime }) => { runtime.resume(); runtime.step(2.2); });
  const looped = await frames();
  const flow = list => list.filter(entity => entity.id.startsWith('flow-'));
  assert.deepEqual(flow(looped), flow(start));
  assert.deepEqual(errors, []);
  await writeFile(resolve(output, 'report.json'), JSON.stringify({ pass: true, animatedEntities: start.length, waterLoopSeconds: 2.4, pauseFreezes: true, pixelsAdvance: true, errors }, null, 2));
  await fixture.evaluate(({ runtime }) => runtime.destroy());
  console.log(JSON.stringify({ pass: true, animatedEntities: start.length, waterLoopSeconds: 2.4, pauseFreezes: true, pixelsAdvance: true }));
} finally {
  await browser.close();
}
