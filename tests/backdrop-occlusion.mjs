import assert from 'node:assert/strict';
import { mkdir, writeFile } from 'node:fs/promises';
import { resolve } from 'node:path';
import { chromium } from 'playwright';

const output = resolve(process.env.RUNTIME_QA_OUTPUT ?? 'test-results/backdrop-occlusion');
await mkdir(output, { recursive: true });
const browser = await chromium.launch({ headless: true });
const page = await browser.newPage({ viewport: { width: 640, height: 480 }, deviceScaleFactor: 1 });
const errors = [];
page.on('pageerror', error => errors.push(error.message));
await page.route('**/backdrop-occlusion-host', route => route.fulfill({ contentType: 'text/html', body: '<body style="margin:0"><div id="world" style="width:640px;height:480px"></div>' }));
try {
  await page.goto(`${process.env.RUNTIME_QA_URL ?? 'http://127.0.0.1:4175'}/backdrop-occlusion-host`);
  const result = await page.evaluate(async () => {
    const { createRuntime } = await import('/src/index.ts');
    const paint = (width, height, fill) => {
      const canvas = document.createElement('canvas'); canvas.width = width; canvas.height = height;
      const ctx = canvas.getContext('2d'); ctx.fillStyle = fill; ctx.fillRect(0, 0, width, height);
      return canvas.toDataURL();
    };
    const scene = actor => ({
      version: 1, name: 'Backdrop occlusion', tileWidth: 48, tileHeight: 24,
      assets: {
        images: { field: { url: paint(80, 40, '#00aa00'), sampling: 'nearest' }, wall: { url: paint(40, 50, '#0000ff'), sampling: 'nearest' }, actor: { url: paint(12, 36, '#ff0000'), sampling: 'nearest' } },
        textures: {
          field: { image: 'field', anchor: { x: 0, y: 0 } },
          wall: { image: 'wall', anchor: { x: 0, y: 0 } },
          actor: { image: 'actor', anchor: { x: 0.5, y: 1 } },
        },
        animations: { idle: { frames: ['actor'] }, walk: { frames: ['actor'] } },
      },
      backdrop: { texture: 'field', x: 200, y: 80 },
      map: [['floor', 'floor', 'hidden'], ['floor', 'floor', 'floor']],
      tiles: { hidden: { color: 0xff00ff, drawn: false, elevation: 24 }, floor: { color: 0x335533, walkable: true } },
      maxStepHeight: 8,
      entityTypes: {
        actor: { bodyHeight: 36, visual: { kind: 'sprite', texture: 'actor', animations: { idle: 'idle', walk: 'walk' } } },
        wall: { bodyHeight: 8, visual: { kind: 'sprite', texture: 'wall', anchor: { x: 0, y: 0 }, offset: { x: 18, y: -50 } } },
      },
      entities: [{ id: 'wall', type: 'wall', c: 1, r: 1 }, { id: 'actor', type: 'actor', ...actor }],
      controlledId: 'actor',
    });
    const runtime = await createRuntime({ container: document.querySelector('#world'), scene: scene({ c: 2, r: 1 }), autoStart: false, input: false, background: 0x111111 });
    const count = (red, blue) => {
      const source = document.querySelector('#world canvas');
      const copy = document.createElement('canvas'); copy.width = source.width; copy.height = source.height;
      const ctx = copy.getContext('2d'); ctx.drawImage(source, 0, 0);
      const pixels = ctx.getImageData(0, 0, copy.width, copy.height).data;
      let reds = 0, blues = 0, magentas = 0;
      for (let i = 0; i < pixels.length; i += 4) {
        if (pixels[i] === 255 && pixels[i + 1] === 0 && pixels[i + 2] === 0) reds++;
        if (pixels[i] === 0 && pixels[i + 1] === 0 && pixels[i + 2] === 255) blues++;
        if (pixels[i] === 255 && pixels[i + 1] === 0 && pixels[i + 2] === 255) magentas++;
      }
      return { reds, blues, magentas, png: copy.toDataURL() };
    };
    try {
      runtime.setCamera({ x: 280, y: 220, zoom: 2 }); runtime.step(0);
      const behind = count();
      await runtime.loadScene(scene({ c: 0, r: 1 }));
      runtime.setCamera({ x: 280, y: 220, zoom: 2 }); runtime.step(0);
      const front = count();
      return { behind, front };
    } finally { runtime.destroy(); }
  });
  for (const name of ['behind', 'front']) await writeFile(resolve(output, `${name}.png`), Buffer.from(result[name].png.split(',')[1], 'base64'));
  await writeFile(resolve(output, 'result.json'), JSON.stringify({ behind: result.behind, front: result.front, errors }, null, 2));
  assert.deepEqual(errors, []);
  assert.equal(result.behind.magentas, 0, 'an undrawn tile must not paint its color');
  assert.equal(result.front.magentas, 0);
  assert.ok(result.behind.blues > 0, 'the wall piece must be visible');
  assert.equal(result.behind.reds, 0, 'the wall piece must cover an actor standing behind it');
  assert.equal(result.front.reds % (12 * 36), 0, 'an actor in front of the wall piece stays fully visible');
  assert.ok(result.front.reds >= 12 * 36);
  console.log('PASS: backdrop hides no actor by itself, and the wall piece covers only the actor behind it.');
} finally { await browser.close(); }
