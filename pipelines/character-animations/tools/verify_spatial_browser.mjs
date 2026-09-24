import { chromium } from '/root/games/waldlicht/node_modules/playwright/index.mjs';
import fs from 'node:fs/promises';
import assert from 'node:assert/strict';

const output = new URL('../review/fast-clean-pipeline/', import.meta.url).pathname;
const browser = await chromium.launch({
  headless: true,
  executablePath: '/root/.cache/ms-playwright/chromium_headless_shell-1234/chrome-linux/headless_shell',
  args: ['--no-sandbox'],
});
try {
  const page = await browser.newPage({ viewport: { width: 640, height: 480 } });
  const consoleErrors = [];
  const pageErrors = [];
  page.on('console', message => { if (message.type() === 'error') consoleErrors.push(message.text()); });
  page.on('pageerror', error => pageErrors.push(error.message));
  await page.goto('http://127.0.0.1:4391/preview.html', { waitUntil: 'networkidle' });
  await page.waitForFunction(() => window.__animationVerification?.loaded === true);
  const before = await page.evaluate(() => window.__animationVerification.frameAdvanceCount);
  await page.waitForTimeout(1000);
  const state = await page.evaluate(() => window.__animationVerification);
  const canvas = await page.locator('canvas').evaluate(element => ({ width: element.width, height: element.height }));
  assert.equal(state.textureDecoded, true);
  assert.equal(state.rectanglesInBounds, true);
  assert.ok(state.frameAdvanceCount > before);
  assert.deepEqual(state.errors, []);
  assert.deepEqual(consoleErrors, []);
  assert.deepEqual(pageErrors, []);
  assert.deepEqual(canvas, { width: 160, height: 160 });
  await page.screenshot({ path: `${output}browser-manifest-player.png` });
  const result = { state, canvas, consoleErrors, pageErrors, screenshot: 'browser-manifest-player.png' };
  await fs.writeFile(`${output}browser-verification.json`, `${JSON.stringify(result, null, 2)}\n`);
  console.log(JSON.stringify(result));
} finally {
  await browser.close();
}
