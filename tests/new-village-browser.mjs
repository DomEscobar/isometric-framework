import { chromium } from 'playwright';
import { createHash } from 'node:crypto';
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const layoutPath = join(root, 'examples/new-village/layout.json');
const args = process.argv.slice(2);
const outputFlag = args.indexOf('--out');
const output = resolve(outputFlag >= 0 ? args[outputFlag + 1] : process.env.NEW_VILLAGE_BROWSER_OUT ?? join(root, 'test-results/new-village/browser-review'));
if (outputFlag >= 0 && !args[outputFlag + 1]) throw Error('--out needs a directory');
const url = process.env.RUNTIME_QA_URL ?? 'http://127.0.0.1:4175/examples/new-village/';
const layoutBytes = await readFile(layoutPath);
const layout = JSON.parse(layoutBytes);
const buildings = layout.instances.filter((instance) => instance.kind === 'building');
if (buildings.length !== 4) throw Error('Expected the four declared village buildings');
await mkdir(dirname(output), { recursive: true });
await mkdir(output);

const report = {
  startedUtc: new Date().toISOString(), url,
  layoutSha256: createHash('sha256').update(layoutBytes).digest('hex'),
  status: 'running', errors: [], views: [],
  limits: 'Confirms desktop mouse/mobile touch pointer routes and pause only. Captures await image review and do not establish visual, full motion, performance, or complete acceptance.',
};
const browser = await chromium.launch();
try {
  for (const mobile of [false, true]) {
    const label = mobile ? 'mobile' : 'desktop';
    const context = await browser.newContext({
      viewport: mobile ? { width: 390, height: 844 } : { width: 1240, height: 920 },
      isMobile: mobile, hasTouch: mobile, deviceScaleFactor: 1,
    });
    const page = await context.newPage();
    page.on('pageerror', (error) => report.errors.push({ view: label, message: error.message }));
    page.on('response', (response) => { if (response.status() >= 400) report.errors.push({ view: label, url: response.url(), status: response.status() }); });
    await page.goto(url);
    await page.waitForFunction(() => window.__VILLAGE_QA__?.runtime);
    // Runtime availability precedes the first composited WebGL frame.
    await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(() => resolve()))));
    const missing = await page.evaluate((ids) => {
      const scene = window.__VILLAGE_QA__.scene();
      return ids.filter((id) => {
        const entity = scene.entities.find((candidate) => candidate.id === id);
        return !entity || scene.entityTypes[entity.type]?.visual?.kind !== 'sprite';
      });
    }, buildings.map((building) => building.id));
    if (missing.length) throw Error(`${label}: missing final building sprites: ${missing.join(', ')}`);
    const view = { view: label, input: mobile ? 'touch' : 'mouse', steps: 0, arrivals: [], pause: false };
    report.views.push(view);
    await page.screenshot({ path: join(output, `${label}-overview.png`) });

    async function pointer(point) {
      if (mobile) await page.touchscreen.tap(point.x, point.y); else await page.mouse.click(point.x, point.y);
    }
    async function walkTo(c, r) {
      for (let attempts = 0; attempts < 120; attempts += 1) {
        const next = await page.evaluate(([targetC, targetR]) => {
          const qa = window.__VILLAGE_QA__;
          const traveler = qa.runtime.getEntity('traveler');
          if (traveler.c === targetC && traveler.r === targetR) return { done: true };
          const path = qa.runtime.findPath('traveler', { c: targetC, r: targetR });
          if (!path) return { error: 'No route to declared goal' };
          const cell = path.find((candidate) => candidate.c !== traveler.c || candidate.r !== traveler.r);
          if (!cell) return { error: 'Route has no next step' };
          const point = qa.screen(cell.c, cell.r);
          const bounds = document.querySelector('#game').getBoundingClientRect();
          return { cell, x: point.x + bounds.x, y: point.y + bounds.y,
            bounds: { left: bounds.left, right: bounds.right, top: bounds.top, bottom: bounds.bottom } };
        }, [c, r]);
        if (next.done) return;
        if (next.error) throw Error(`${label}: ${next.error}`);
        if (next.x < next.bounds.left || next.x >= next.bounds.right || next.y < next.bounds.top || next.y >= next.bounds.bottom) throw Error(`${label}: pointer target is outside the game viewport`);
        await pointer(next);
        await page.waitForFunction(({ c: targetC, r: targetR }) => {
          const qa = window.__VILLAGE_QA__;
          const entity = qa.runtime.getEntity('traveler');
          const pose = qa.pose();
          return entity.c === targetC && entity.r === targetR && Math.abs(pose.position.c - targetC) < .01 && Math.abs(pose.position.r - targetR) < .01;
        }, next.cell, { timeout: 4000 });
        view.steps += 1;
      }
      throw Error(`${label}: route exceeded 120 steps`);
    }
    async function capture(id, c, r) {
      await walkTo(c, r);
      await page.screenshot({ path: join(output, `${label}-${id}.png`) });
      view.arrivals.push({ id, cell: [c, r] });
    }
    for (const building of buildings) {
      const approach = building.approaches?.[0];
      if (!approach) throw Error(`No approach declared for ${building.id}`);
      await capture(building.id, approach[0], approach[1]);
    }
    const bridge = layout.bridges.find((candidate) => candidate.id === 'larkspur-bridge');
    if (!bridge || bridge.deck.length !== 3) throw Error('Expected the declared three-cell bridge');
    const first = bridge.deck[0], last = bridge.deck.at(-1);
    const dc = Math.sign(last[0] - first[0]), dr = Math.sign(last[1] - first[1]);
    if (Math.abs(dc) + Math.abs(dr) !== 1) throw Error('Bridge direction is not axis-aligned');
    const crossing = [[first[0] - dc, first[1] - dr], ...bridge.deck, [last[0] + dc, last[1] + dr]];
    for (const [index, cell] of [...crossing, ...crossing.toReversed()].entries()) await capture(`bridge-${index}`, cell[0], cell[1]);
    await page.locator('#pause').click();
    const paused = await page.evaluate(() => window.__VILLAGE_QA__.runtime.isPaused);
    if (!paused) throw Error(`${label}: pause button did not pause the runtime`);
    const pausedA = await page.locator('#game canvas').screenshot({ path: join(output, `${label}-paused-a.png`) });
    await page.waitForTimeout(550);
    const pausedB = await page.locator('#game canvas').screenshot({ path: join(output, `${label}-paused-b.png`) });
    if (!pausedA.equals(pausedB)) throw Error(`${label}: canvas changed while paused`);
    view.pause = true;
    await page.locator('#pause').click();
    if (await page.evaluate(() => window.__VILLAGE_QA__.runtime.isPaused)) throw Error(`${label}: pause button did not resume the runtime`);
    await context.close();
  }
  if (report.errors.length) throw Error('Page or asset loading errors occurred');
  report.status = 'journeys-completed-images-await-review';
} catch (error) {
  report.status = 'failed'; report.failure = String(error); throw error;
} finally {
  report.finishedUtc = new Date().toISOString();
  await writeFile(join(output, 'review.json'), JSON.stringify(report, null, 2));
  await browser.close();
}
console.log(JSON.stringify({ status: report.status, views: report.views.map(({ view, steps, arrivals, pause }) => ({ view, steps, arrivals: arrivals.length, pause })), output }));
