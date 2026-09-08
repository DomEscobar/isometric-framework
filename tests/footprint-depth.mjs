import assert from 'node:assert/strict';
import { mkdir, writeFile } from 'node:fs/promises';
import { resolve } from 'node:path';
import { chromium } from 'playwright';

const output = resolve(process.env.RUNTIME_QA_OUTPUT ?? 'test-results/footprint-depth');
await mkdir(output, { recursive: true });
const browser = await chromium.launch({ headless: true });
const page = await browser.newPage({ viewport: { width: 560, height: 420 }, deviceScaleFactor: 1 });
const errors = [];
page.on('pageerror', error => errors.push(error.message));
await page.route('**/footprint-depth-host', route => route.fulfill({ contentType: 'text/html', body: '<body style="margin:0"><div id="world" style="width:560px;height:420px"></div>' }));
try {
  await page.goto(`${process.env.RUNTIME_QA_URL ?? 'http://127.0.0.1:4175'}/footprint-depth-host`);
  const result = await page.evaluate(async () => {
    const { createRuntime } = await import('/src/index.ts');
    // Deliberately solid diagnostic art makes occlusion measurable. These are
    // test fixtures, not replacements for the generated game assets.
    const material = (width, height, paint) => {
      const canvas = document.createElement('canvas'); canvas.width = width; canvas.height = height;
      paint(canvas.getContext('2d')); return canvas.toDataURL();
    };
    const actor = material(16, 48, ctx => { ctx.fillStyle = '#ff0000'; ctx.fillRect(0, 0, 16, 48); });
    const house = material(192, 200, ctx => {
      ctx.translate(32, 140); ctx.fillStyle = '#0000ff'; ctx.beginPath();
      for (const [i, [x, y]] of [[-32, -80], [64, -128], [160, -80], [160, 0], [64, 48], [-32, 0]].entries()) {
        if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
      }
      ctx.closePath(); ctx.fill();
    });
    const scene = start => ({
      version: 1, name: 'Footprint depth tie', tileWidth: 64, tileHeight: 32,
      map: Array.from({ length: 9 }, () => Array(9).fill('floor')),
      tiles: { floor: { color: 0x444444 } }, diagonal: false,
      assets: {
        images: { actor: { url: actor, sampling: 'nearest' }, house: { url: house, sampling: 'nearest' } },
        textures: {
          actor: { image: 'actor', anchor: { x: .5, y: 1 } },
          house: { image: 'house', anchor: { x: 32 / 192, y: 140 / 200 } },
        },
        animations: { idle: { frames: ['actor'] }, walk: { frames: ['actor'] } },
      },
      entityTypes: {
        actor: { blocking: true, bodyHeight: 48, visual: { kind: 'sprite', texture: 'actor', animations: { idle: 'idle', walk: 'walk' } } },
        house: { rows: 3, columns: 3, blocking: true, bodyHeight: 80, visual: { kind: 'sprite', texture: 'house' } },
      },
      entities: [{ id: 'house', type: 'house', c: 3, r: 2 }, { id: 'actor', type: 'actor', ...start }], controlledId: 'actor',
    });
    const runtime = await createRuntime({ container: document.querySelector('#world'), scene: scene({ c: 4, r: 6 }), autoStart: false, input: false, speed: 1 });
    const runs = [];
    try {
      for (const start of [{ c: 4, r: 6 }, { c: 5, r: 5 }]) {
        await runtime.loadScene(scene(start)); runtime.setCamera({ x: 20, y: 240, zoom: 1 }); runtime.step(0);
        runtime.moveTo('actor', { c: 4, r: 5 });
        // Render mid-step: Pixi's previous stable order must differ between
        // these approaches before both reach the same final depth plane.
        runtime.step(.5); runtime.step(.5); runtime.setFacing('actor', 'se'); runtime.step(0);
        const source = document.querySelector('#world canvas');
        const copy = document.createElement('canvas'); copy.width = source.width; copy.height = source.height;
        const ctx = copy.getContext('2d'); ctx.drawImage(source, 0, 0);
        const pixels = ctx.getImageData(0, 0, copy.width, copy.height).data;
        let actorPixels = 0;
        for (let i = 0; i < pixels.length; i += 4) if (pixels[i] === 255 && pixels[i + 1] === 0 && pixels[i + 2] === 0) actorPixels++;
        const sprite = runtime.getDebugSnapshot().entities.find(entity => entity.id === 'actor').sprite;
        runs.push({ start, entity: runtime.getEntity('actor'), sprite, actorPixels, png: copy.toDataURL() });
      }
      return runs;
    } finally { runtime.destroy(); }
  });
  for (const [i, run] of result.entries()) await writeFile(resolve(output, `approach-${i + 1}.png`), Buffer.from(run.png.split(',')[1], 'base64'));
  await writeFile(resolve(output, 'result.json'), JSON.stringify({ runs: result.map(({ png, ...run }) => run), identicalPixels: result[0].png === result[1].png, errors }, null, 2));
  assert.deepEqual(errors, []);
  for (const run of result) {
    assert.equal(run.entity.c, 4); assert.equal(run.entity.r, 5);
    assert.equal(run.sprite.facing, 'se'); assert.equal(run.sprite.clip, 'idle'); assert.equal(run.sprite.state, 'idle');
    assert.equal(run.actorPixels, 16 * 48, `Actor must remain fully in front after approach ${JSON.stringify(run.start)}`);
  }
  assert.equal(result[0].png, result[1].png, 'Same final pose must render identically after either approach');
  console.log('PASS: both physical approaches retain all 768 actor pixels and produce identical final canvas images.');
} finally { await browser.close(); }
