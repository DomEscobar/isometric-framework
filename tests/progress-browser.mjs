import { chromium } from 'playwright';
import { mkdir, writeFile } from 'node:fs/promises';
import { resolve } from 'node:path';
import assert from 'node:assert/strict';

const output = resolve(process.env.RUNTIME_QA_OUTPUT ?? 'test-results/progress-demo');
const url = process.env.RUNTIME_QA_URL ?? 'http://127.0.0.1:4175';
await mkdir(output, { recursive: true });
const browser = await chromium.launch();
const results = [], errors = [];
const key = 'little-worlds.sunflower.v1';
const until = (page, id, text) => page.waitForFunction(({ id, text }) => document.getElementById(id)?.textContent.includes(text), { id, text });
async function open(mobile = false) {
  const context = await browser.newContext(mobile ? { viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true } : { viewport: { width: 1280, height: 900 } });
  const page = await context.newPage(); page.on('pageerror', error => errors.push(error.message));
  await page.goto(url); await until(page, 'run-state', 'Running');
  return { page, context };
}
async function pick(page, touch = false) {
  await page.locator('#debug-toggle').click();
  await page.locator('canvas').scrollIntoViewIfNeeded();
  const point = await page.locator('[data-runtime-debug]').evaluate(svg => {
    const polygon = [...svg.querySelectorAll('polygon')].filter(node => node.getAttribute('stroke') === '#00bcd4')[2 * 9 + 2];
    const points = polygon.getAttribute('points').split(' ').map(p => p.split(',').map(Number));
    const box = svg.getBoundingClientRect();
    return { x: box.x + points.reduce((sum, p) => sum + p[0], 0) / 4, y: box.y + points.reduce((sum, p) => sum + p[1], 0) / 4 };
  });
  if (touch) await page.touchscreen.tap(point.x, point.y); else await page.mouse.click(point.x, point.y);
  await until(page, 'collection-count', '1 / 3'); await until(page, 'action-status', 'Flower picked');
}
async function run(name, fn) {
  try { await fn(); results.push({ name, pass: true }); console.log('PASS', name); }
  catch (error) { results.push({ name, pass: false, error: String(error.stack) }); console.error('FAIL', name, error); }
}
try {
  await run('desktop collection, reload, cross-scene continue and restart preserve coherent progress', async () => {
    const { page, context } = await open();
    try {
      await pick(page);
      const saved = await page.evaluate(key => JSON.parse(localStorage.getItem(key)), key);
      assert.equal(saved.state.inventory.items[0].quantity, 1);
      assert.equal(saved.scene.entities.filter(e => e.data?.role === 'collectible').length, 2);
      await page.reload(); await until(page, 'save-status', 'restored');
      assert.equal(await page.locator('#collection-count').innerText(), '1 / 3');
      assert.equal(await page.locator('#actor-cell').innerText(), '2, 3');
      assert.match(await page.locator('#inventory-items').innerText(), /Garden flowers × 1/);
      await page.locator('#preset').selectOption('jump'); await until(page, 'scene-name', 'Jump');
      await page.locator('#load-game').click(); await until(page, 'scene-name', 'Sunflower'); await until(page, 'save-status', 'restored');
      assert.equal(await page.locator('#trap-controls').isVisible(), false);
      assert.equal(await page.locator('#collection-count').innerText(), '1 / 3');
      await page.screenshot({ path: resolve(output, 'desktop-restored.png'), fullPage: true });
      await page.locator('#restart').click(); await until(page, 'collection-count', '0 / 3'); await until(page, 'save-status', 'saved');
      await page.reload(); await until(page, 'save-status', 'restored');
      assert.equal(await page.locator('#collection-count').innerText(), '0 / 3');
      assert.equal(await page.locator('#actor-cell').innerText(), '2, 6');
    } finally { await context.close(); }
  });
  await run('corrupt saves and refused storage preserve the playable current garden', async () => {
    const { page, context } = await open();
    try {
      await pick(page);
      await page.evaluate(key => localStorage.setItem(key, JSON.stringify({ version: 999 })), key);
      await page.locator('#load-game').click(); await until(page, 'save-status', 'Could not restore');
      assert.equal(await page.locator('#collection-count').innerText(), '1 / 3');
      assert.equal(await page.locator('#actor-cell').innerText(), '2, 3');
      assert.equal(await page.evaluate(key => JSON.parse(localStorage.getItem(key)).version, key), 999);
      await page.evaluate(() => { Storage.prototype.setItem = () => { throw new DOMException('Storage full', 'QuotaExceededError'); }; });
      await page.locator('#save-game').click(); await until(page, 'save-status', 'Could not save');
      assert.equal(await page.locator('#collection-count').innerText(), '1 / 3');
      assert.equal(await page.locator('#run-state').innerText(), 'Running');
      await page.screenshot({ path: resolve(output, 'storage-error.png'), fullPage: true });
    } finally { await context.close(); }
  });
  await run('mobile touch collection restores after reload without horizontal overflow', async () => {
    const { page, context } = await open(true);
    try {
      await pick(page, true); await page.reload(); await until(page, 'save-status', 'restored');
      assert.equal(await page.locator('#collection-count').innerText(), '1 / 3');
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
      await page.screenshot({ path: resolve(output, 'mobile-restored.png'), fullPage: true });
    } finally { await context.close(); }
  });
} finally { await browser.close(); }
await writeFile(resolve(output, 'report.json'), JSON.stringify({ url, results, errors }, null, 2));
console.log(`${results.filter(result => result.pass).length}/${results.length} progress journeys; ${errors.length} browser errors.`);
process.exitCode = results.some(result => !result.pass) || errors.length ? 1 : 0;
