// Authoring regression: supply valid and deliberately damaged surface previews.
// node .../surface-preview-browser.mjs VALID_HTML INVALID_HTML EVIDENCE_DIR
import assert from 'node:assert/strict';
import { chromium } from 'playwright';
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import { resolve } from 'node:path';
import { pathToFileURL } from 'node:url';

const [valid, invalid, evidence] = process.argv.slice(2);
assert(valid && invalid && evidence, 'Supply two generated preview files and evidence directory');
await mkdir(evidence, { recursive: true });
const browser = await chromium.launch();
const errors = [];
try {
  const page = await browser.newPage({ viewport: { width: 1440, height: 960 } });
  page.on('pageerror', error => errors.push(error.message));
  const zoom = value => page.locator('#zoom').evaluate((input, value) => {
    input.value = String(value);
    input.dispatchEvent(new Event('input', { bubbles: true }));
  }, value);
  for (const [name, file] of [['valid', valid], ['invalid', invalid]]) {
    await page.goto(pathToFileURL(resolve(file)).href);
    await page.waitForSelector('body[data-decoded="true"]');
    const article = page.locator('article[data-surface]').first();
    const canvas = article.locator('canvas');
    await page.waitForFunction(() => document.querySelector('article[data-surface] canvas')?.width > 0);
    assert.match(await article.innerText(), /COMPOSED.*origin/);
    await zoom(1);
    await page.waitForTimeout(80);
    const initial = await canvas.evaluate(c => ({ pixels: c.toDataURL(), width: c.width, css: c.style.width }));
    await zoom(2);
    await page.waitForTimeout(80);
    assert.equal(await canvas.evaluate(c => parseFloat(c.style.width)), initial.width * 2);
    await page.locator('#surface-mask').click();
    await page.waitForTimeout(80);
    assert.notEqual(await canvas.evaluate(c => c.toDataURL()), initial.pixels, 'Mask overlay had no effect');
    await page.locator('#surface-mask').click();
    await page.locator('#surface-reference').click();
    await page.waitForTimeout(80);
    const reference = await canvas.evaluate(c => c.toDataURL());
    if (name === 'invalid') {
      assert.match(await page.locator('#status').innerText(), /FAIL/);
      assert.match(await article.locator('p.bad').innerText(), /differ|overlap|holes|outside/);
      assert.notEqual(reference, initial.pixels, 'Damaged assembly displayed reference as actual');
    } else {
      assert.match(await page.locator('#status').innerText(), /PASS/);
    }
    await page.locator('#surface-reference').click();
    await zoom(1);
    await page.waitForTimeout(80);
    await page.screenshot({ path: resolve(evidence, `${name}-desktop.png`) });
    await page.setViewportSize({ width: 390, height: 844 });
    assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), 'Mobile page overflow');
    await page.screenshot({ path: resolve(evidence, `${name}-mobile.png`) });
    await page.setViewportSize({ width: 1440, height: 960 });
  }
  const broken = (await readFile(valid, 'utf8')).replace(/data:image\/png;base64,[A-Za-z0-9+/=]+/, 'data:image/png;base64,broken');
  await page.goto('about:blank');
  await page.setContent(broken);
  await page.waitForSelector('body[data-decoded="false"]');
  assert.match(await page.locator('#status').innerText(), /IMAGE DECODE FAILED/);
  assert.deepEqual(errors, []);
  const report = { passed: true, checks: ['decoded images', 'actual composition', 'source origin', 'shared zoom',
    'mask toggle', 'reference comparison', 'damaged surface visibly distinct', 'failure labels', 'mobile layout', 'image decode failure'], errors };
  await writeFile(resolve(evidence, 'browser.json'), JSON.stringify(report, null, 2));
  console.log(JSON.stringify(report));
} finally {
  await browser.close();
}
