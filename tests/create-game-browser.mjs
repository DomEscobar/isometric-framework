// Run against a separately built/served generated project, never the framework demo.
import assert from 'node:assert/strict';
import { mkdir, writeFile } from 'node:fs/promises';
import { resolve } from 'node:path';
import { chromium } from 'playwright';

const url = process.env.RUNTIME_QA_URL;
if (!url) throw new Error('Set RUNTIME_QA_URL to the generated project dev or preview URL');
const output = resolve(process.argv[2] ?? 'test-results/starter-browser');
await mkdir(output, { recursive: true });
const browser = await chromium.launch();
const report = { url, views: [], errors: [], limits: 'Neutral starter startup and input only; screenshots require inspection. This does not certify a finished world.' };
try {
  for (const mobile of [false, true]) {
    const name = mobile ? 'mobile' : 'desktop';
    const context = await browser.newContext({ viewport: mobile ? { width: 390, height: 844 } : { width: 1200, height: 900 }, isMobile: mobile, hasTouch: mobile });
    const page = await context.newPage();
    page.on('pageerror', e => report.errors.push(e.message));
    page.on('console', message => { if (message.type() === 'error') report.errors.push(message.text()); });
    page.on('response', r => { if (r.status() >= 400) report.errors.push(`${r.status()} ${r.url()}`); });
    await page.goto(url);
    await page.locator('canvas').waitFor();
    await page.locator('.runtime-dpad-w').waitFor();
    await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
    // The first GPU presentation may lag DOM readiness in headless Chromium.
    // This settle period is not visual proof: inspect both saved start/arrival views.
    await page.waitForTimeout(500);
    const before = await page.locator('canvas').screenshot();
    await page.screenshot({ path: `${output}/${name}-start.png`, fullPage: true });
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), 'Horizontal overflow');
    if (mobile) {
      const cdp = await context.newCDPSession(page);
      for (const direction of ['w', 'd']) {
        const button = page.locator(`.runtime-dpad-${direction}`);
        await button.scrollIntoViewIfNeeded();
        const box = await button.boundingBox();
        assert.ok(box);
        await cdp.send('Input.dispatchTouchEvent', { type: 'touchStart', touchPoints: [{ x: box.x + box.width / 2, y: box.y + box.height / 2 }] });
        await page.waitForTimeout(2000);
        await cdp.send('Input.dispatchTouchEvent', { type: 'touchEnd', touchPoints: [] });
      }
    } else {
      await page.locator('#game').focus();
      for (const key of ['KeyW', 'KeyD']) {
        await page.keyboard.down(key);
        await page.waitForTimeout(2000);
        await page.keyboard.up(key);
      }
    }
    await page.waitForFunction(() => document.querySelector('#status')?.textContent?.includes('Calibration complete'));
    assert.ok(!before.equals(await page.locator('canvas').screenshot()), 'Input did not change the rendered canvas');
    await page.screenshot({ path: `${output}/${name}-arrived.png`, fullPage: true });
    report.views.push({ name, input: mobile ? 'real CDP touch holds' : 'keyboard holds', arrived: true });
    await context.close();
  }
  assert.deepEqual(report.errors, []);
  report.status = 'startup-and-journeys-passed-images-await-inspection';
} finally {
  await writeFile(`${output}/report.json`, JSON.stringify(report, null, 2) + '\n');
  await browser.close();
}
console.log(JSON.stringify(report, null, 2));
