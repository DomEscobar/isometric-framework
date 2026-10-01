// Run from an installed, served consumer after quilt-consumer.mjs.
// Synthetic rendering evidence only: never a generated-art or game acceptance.
import assert from 'node:assert/strict';
import { mkdir, writeFile, readFile, unlink } from 'node:fs/promises';
import { resolve } from 'node:path';
import { chromium } from 'playwright';

const url = process.env.RUNTIME_QA_URL;
assert.ok(url, 'Set RUNTIME_QA_URL to the served consumer');
const output = resolve(process.argv[2] ?? 'test-results/landscape-browser');
const pagePath = resolve('landscape-diagnostic.html');
await assert.rejects(readFile(pagePath), 'Refusing to overwrite an existing diagnostic page');
await readFile('diagnostics/landscape-bound/scene.json');
await mkdir(output, { recursive: true });
await writeFile(pagePath, `<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Landscape compositor diagnostic</title>
<style>body{margin:0;background:#f5f0e5;font:16px system-ui}header{padding:12px}#game{height:calc(100dvh - 100px)}button{padding:8px;margin-right:8px}</style>
<header>Synthetic diagnostic — not game art. <span id="status">Loading</span><br>
<button id="ground">Ground only</button><button id="dressed">Dressed</button><button id="detail">Detail</button></header><div id="game"></div>
<script type="module">
import {createRuntime} from 'isometric-framework';
const original = await (await fetch('/diagnostics/landscape-bound/scene.json')).json();
const runtime = await createRuntime({container:document.querySelector('#game'),scene:original,background:0xf5f0e5,input:false});
let camera=runtime.getCamera();
async function show(mode){const scene=structuredClone(original);if(mode==='ground'){scene.entities=[];delete scene.controlledId;}
await runtime.loadScene(scene);runtime.setCamera(camera);document.querySelector('#status').textContent=mode;}
document.querySelector('#ground').onclick=()=>show('ground');
document.querySelector('#dressed').onclick=()=>show('dressed');
document.querySelector('#detail').onclick=()=>{camera={...runtime.getCamera(),zoom:Math.min(4,runtime.getCamera().zoom*1.5)};runtime.setCamera(camera);document.querySelector('#status').textContent='detail';};
document.querySelector('#status').textContent='dressed';
</script></html>`);
let browser;
const report = { kind: 'synthetic-landscape-rendering', errors: [], captures: [], productionArt: 'unverified' };
try {
  browser = await chromium.launch();
  for (const viewport of [{ width: 1200, height: 900 }, { width: 390, height: 844 }]) {
    const mobile = viewport.width < 500;
    const context = await browser.newContext({ viewport, isMobile: mobile, hasTouch: mobile });
    const page = await context.newPage();
    page.on('pageerror', error => report.errors.push(error.message));
    page.on('response', response => { if (response.status() >= 400) report.errors.push(`${response.status()} ${response.url()}`); });
    await page.goto(new URL('/landscape-diagnostic.html', url).href);
    await page.locator('#status').filter({ hasText: 'dressed' }).waitFor();
    for (const mode of ['ground', 'dressed', 'detail']) {
      await page.locator(`#${mode}`).click();
      await page.locator('#status').filter({ hasText: mode }).waitFor();
      await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
      const name = `${mobile ? 'mobile' : 'desktop'}-${mode}.png`;
      await page.screenshot({ path: resolve(output, name), fullPage: true });
      assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), 'Horizontal overflow');
      report.captures.push({ name, viewport, mode });
    }
    await context.close();
  }
  assert.deepEqual(report.errors, []);
  report.status = 'rendered-awaiting-independent-image-review';
} finally {
  await writeFile(resolve(output, 'report.json'), JSON.stringify(report, null, 2) + '\n');
  await browser?.close();
  await unlink(pagePath);
}
console.log(JSON.stringify(report, null, 2));
