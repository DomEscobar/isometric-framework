import assert from 'node:assert/strict';
import { mkdir, writeFile } from 'node:fs/promises';
import { resolve } from 'node:path';
import { chromium } from 'playwright';

// Solid colors are diagnostic fixtures, not replacement artwork for a game.
const output = resolve(process.env.RUNTIME_QA_OUTPUT ?? 'test-results/bridge-occlusion');
await mkdir(output, { recursive: true });
const browser = await chromium.launch({ headless: true });
const page = await browser.newPage({ viewport: { width: 820, height: 650 }, deviceScaleFactor: 1 });
const errors = [];
page.on('pageerror', error => errors.push(error.message));
await page.route('**/bridge-occlusion-host', route => route.fulfill({ contentType: 'text/html', body: '<body style="margin:0"><div id="world" style="width:820px;height:650px"></div>' }));
try {
  await page.goto(`${process.env.RUNTIME_QA_URL ?? 'http://127.0.0.1:4175'}/bridge-occlusion-host`);
  const captures = await page.evaluate(async () => {
    const { createRuntime } = await import('/src/index.ts');
    const image = (width, height, color) => {
      const canvas = document.createElement('canvas'); canvas.width = width; canvas.height = height;
      const context = canvas.getContext('2d'); context.fillStyle = color; context.fillRect(0, 0, width, height);
      return canvas.toDataURL();
    };
    const scene = start => {
      const map = Array.from({ length: 11 }, (_, r) => Array.from({ length: 11 }, (_, c) =>
        c >= 3 && c <= 7 && r >= 3 && r <= 7 ? 'channel' : 'ground'));
      map[5][2] = 'step'; map[8][5] = 'step';
      return {
        version: 2, name: 'Cross-floor occlusion regression', tileWidth: 64, tileHeight: 32, map,
        levels: [{ id: 'bridge', name: 'Bridge', height: 32, map: map.map((row, r) => row.map((_, c) =>
          c >= 3 && c <= 7 && r >= 3 && r <= 7 ? 'deck' : null)) }],
        tiles: { ground: { color: 0x555555 }, channel: { color: 0x114488, elevation: -32 },
          step: { color: 0x888888, elevation: 16 }, deck: { color: 0xccbb99 } },
        maxStepHeight: 16, diagonal: false, links: [],
        assets: {
          images: { actor: { url: image(16, 44, '#ff0000'), sampling: 'nearest' }, lamp: { url: image(8, 80, '#00ff00'), sampling: 'nearest' } },
          textures: { actor: { image: 'actor', anchor: { x: .5, y: 1 } }, lamp: { image: 'lamp', anchor: { x: .5, y: 1 } } },
        },
        entityTypes: {
          actor: { blocking: true, bodyHeight: 44, visual: { kind: 'sprite', texture: 'actor' } },
          lamp: { blocking: true, bodyHeight: 80, visual: { kind: 'sprite', texture: 'lamp' } },
        },
        entities: [{ id: 'actor', type: 'actor', ...start }, { id: 'lamp', type: 'lamp', c: 1, r: 4 }],
        controlledId: 'actor',
      };
    };
    const runtime = await createRuntime({ container: document.querySelector('#world'), scene: scene({ c: 1, r: 5 }), autoStart: false, input: false, speed: 1 });
    const results = [];
    const capture = name => {
      runtime.step(0);
      const source = document.querySelector('canvas'), copy = document.createElement('canvas');
      copy.width = source.width; copy.height = source.height;
      const context = copy.getContext('2d'); context.drawImage(source, 0, 0);
      const pixels = context.getImageData(0, 0, copy.width, copy.height).data;
      let actorPixels = 0, lampPixels = 0;
      for (let i = 0; i < pixels.length; i += 4) {
        if (pixels[i] === 255 && pixels[i + 1] === 0 && pixels[i + 2] === 0) actorPixels++;
        if (pixels[i] === 0 && pixels[i + 1] === 255 && pixels[i + 2] === 0) lampPixels++;
      }
      results.push({ name, actorPixels, lampPixels, pose: runtime.getEntityPose('actor'), png: copy.toDataURL() });
    };
    const load = async start => {
      await runtime.loadScene(scene(start)); runtime.setCamera({ x: 60, y: 320, zoom: 1 });
    };
    try {
      await load({ c: 1, r: 5 }); runtime.moveTo('actor', { c: 2, r: 5 }); runtime.step(1); capture('front-column-step');
      await load({ c: 5, r: 9 }); runtime.moveTo('actor', { c: 5, r: 8 }); runtime.step(1); capture('front-row-step');
      await load({ c: 5, r: 5, level: 'bridge' }); capture('on-deck');
      runtime.setViewLevel('ground'); capture('deck-cutaway');
      await load({ c: 5, r: 5 }); capture('under-deck');
      runtime.setViewLevel('ground'); capture('under-deck-cutaway');
      runtime.setViewLevel(null); capture('under-deck-restored');
      return results;
    } finally { runtime.destroy(); }
  });
  for (const capture of captures) await writeFile(resolve(output, `${capture.name}.png`), Buffer.from(capture.png.split(',')[1], 'base64'));
  await writeFile(resolve(output, 'result.json'), JSON.stringify({ errors, captures: captures.map(({ png, ...rest }) => rest) }, null, 2));
  assert.deepEqual(errors, []);
  for (const capture of captures) {
    const visible = ['front-column-step', 'front-row-step', 'on-deck', 'under-deck-cutaway'].includes(capture.name);
    assert.equal(capture.actorPixels, visible ? 16 * 44 : 0, `${capture.name}: correct actor occlusion`);
    assert.equal(capture.lampPixels, 8 * 80, `${capture.name}: ground foreground lamp stays intact`);
  }
  for (const capture of captures.slice(0, 2)) assert.equal(capture.pose.elevation, 16, `${capture.name}: actor really climbed the step`);
  assert.equal(captures[4].png, captures[6].png, 'Restoring floor visibility restores the exact canvas');
  console.log('PASS: both ground step approaches, foreground lamp, deck actor, underpass occlusion and reversible cutaway.');
} finally { await browser.close(); }
