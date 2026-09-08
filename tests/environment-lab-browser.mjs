import { chromium } from 'playwright';
import { mkdir, writeFile } from 'node:fs/promises';
import { resolve } from 'node:path';
import assert from 'node:assert/strict';

const output = resolve('test-results/environment-lab');
await mkdir(output, { recursive: true });
const browser = await chromium.launch();
const results = [], errors = [];
const url = `${process.env.RUNTIME_QA_URL ?? 'http://127.0.0.1:4175'}/examples/environment-lab/`;
async function journey(mobile) {
  const context = await browser.newContext(mobile ? { viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true } : { viewport: { width: 1280, height: 1000 } });
  const page = await context.newPage();
  page.on('pageerror', error => errors.push(error.message));
  const click = id => mobile ? page.locator(id).tap() : page.locator(id).click();
  const position = value => page.waitForFunction(value => document.querySelector('#position')?.textContent.startsWith(value), value);
  try {
    await page.goto(url); await position('1.0, 6.0');
    assert.equal(await page.locator('#variant').inputValue(), 'generated-layered');
    if (mobile) {
      assert.equal(await page.locator('#pad').isVisible(), true);
      await page.getByRole('button', {name:'Jump',exact:true}).tap();
      await page.waitForFunction(() => Number.parseFloat(document.querySelector('#position')?.textContent.split('·').at(-1) ?? '0') > 0);
      await page.waitForTimeout(1000); // Let the 0.8-second hop finish before issuing a route.
      assert.equal((await page.locator('#position').textContent()).split('·').at(-1).trim(), '0 px');
    }
    await click('#cross'); await position('12.0, 5.0');
    await click('#under'); await position('4.0, 3.0');
    assert.equal(await page.locator('#floor').inputValue(), 'ground');
    await click('#pause');
    const paused = await page.locator('#world').screenshot();
    await page.waitForTimeout(350);
    assert.ok(paused.equals(await page.locator('#world').screenshot()), 'Paused scene stays visually frozen');
    await click('#pause');
    await click('#debug-toggle'); assert.equal(await page.locator('#debug-toggle').getAttribute('aria-pressed'), 'true');
    await page.screenshot({ path: resolve(output, `${mobile ? 'mobile' : 'desktop'}-underpass.png`), fullPage: true });
    await click('#debug-toggle');
    await click('#restart'); await position('1.0, 6.0');
    assert.equal(await page.locator('#floor').inputValue(), 'all');
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), 'No horizontal page overflow');
    await page.screenshot({ path: resolve(output, `${mobile ? 'mobile' : 'desktop'}-overview.png`), fullPage: true });
    results.push({ journey: mobile ? 'mobile touch' : 'desktop', pass: true });
  } catch (error) {
    await page.screenshot({path:resolve(output,`${mobile?'mobile':'desktop'}-failure.png`),fullPage:true});
    throw new Error(`${error.stack}\nPosition: ${await page.locator('#position').textContent()}\nStatus: ${await page.locator('#status').textContent()}`);
  } finally { await context.close(); }
}
try { await journey(false); await journey(true); }
catch (error) { results.push({ pass: false, error: String(error.stack) }); }
finally { await browser.close(); }
await writeFile(resolve(output, 'results.json'), JSON.stringify({ results, errors }, null, 2));
console.log(JSON.stringify({ results, errors }));
process.exitCode = errors.length || results.some(result => !result.pass) ? 1 : 0;
