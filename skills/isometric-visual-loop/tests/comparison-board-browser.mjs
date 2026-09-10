// Authoring-only probe. Start a local server exposing a generated comparison bundle.
// node skills/isometric-visual-loop/tests/comparison-board-browser.mjs BOARD_URL [SCREENSHOT]
import assert from 'node:assert/strict';
import { chromium } from 'playwright';

const url = process.argv[2];
assert(url, 'Supply the URL of a generated board.html');
const browser = await chromium.launch({ headless: true });
try {
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.goto(url);
  await page.waitForSelector('body[data-decoded="true"]');
  const canvas = page.locator('canvas[data-kind="current"]').first();
  assert(await page.locator('canvas[data-kind="reference"]').count() > 0);
  assert(await page.locator('article li').count() > 0, 'Protected criteria must be visible beside the images');
  assert.match(await page.locator('#status').innerText(), /visual review required/);
  const changedBaseline = await page.evaluate(() => Boolean(packet.baselineChange));
  assert.equal(await page.locator('#baseline-change').isVisible(), changedBaseline);
  if (changedBaseline) assert.match(await page.locator('#baseline-change').innerText(), /Prior findings remain open/);
  for (const zoom of ['0.5', '1', '2']) {
    await page.locator('#zoom').selectOption(zoom);
    assert(await page.locator('canvas').evaluateAll((nodes, z) => nodes.every(c =>
      c.getBoundingClientRect().width === c.width * Number(z) &&
      c.getBoundingClientRect().height === c.height * Number(z)), zoom));
  }
  await page.locator('#zoom').selectOption('1');
  const bounds = await canvas.boundingBox();
  await page.mouse.move(bounds.x + 20, bounds.y + 20);
  await page.mouse.down();
  await page.mouse.move(bounds.x + 60, bounds.y + 45);
  await page.mouse.up();
  assert.deepEqual(JSON.parse(await page.locator('#coordinates').inputValue()).region, [20, 20, 41, 26]);
  const marked = await canvas.evaluate(c => c.toDataURL());
  await page.locator('#clear').click();
  assert.equal(await page.locator('#coordinates').inputValue(), '');
  assert.notEqual(await canvas.evaluate(c => c.toDataURL()), marked);
  await page.locator('#zoom').selectOption('0.5');
  if (process.argv[3]) await page.screenshot({ path: process.argv[3], fullPage: true });
  const hasPrevious = await page.locator('canvas[data-kind="previous"]').count() > 0;
  if (hasPrevious) assert.doesNotMatch(await page.locator('#prior').innerText(), /No previous/);
  else assert.match(await page.locator('#comparisons').innerText(), /First round/);
  await page.setViewportSize({ width: 390, height: 844 });
  assert(await page.locator('.panels').evaluateAll(nodes => nodes.every(n =>
    getComputedStyle(n).gridTemplateColumns.split(' ').length === 1)));
  assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
  await page.route(url, async route => {
    const response = await route.fetch();
    const html = (await response.text()).replace(/data:image\/[^;]+;base64,[A-Za-z0-9+/=]+/, 'data:image/png;base64,broken');
    await route.fulfill({ response, body: html });
  });
  await page.reload();
  await page.waitForSelector('body[data-decoded="false"]');
  assert.match(await page.locator('#status').innerText(), /IMAGE DECODE FAILED/);
  assert.deepEqual(errors, []);
  console.log(JSON.stringify({ passed: true, hasPrevious, changedBaseline, checks: ['decoded images', 'protected criteria', 'baseline correction notice', 'shared zoom', 'source-pixel selection', 'clear overlay', 'previous state', 'mobile stacking', 'no page overflow', 'decode failure label', 'no page errors'] }));
} finally {
  await browser.close();
}
