import assert from 'node:assert/strict';
import { test } from 'node:test';
import { resolveAnimation, selectTileTexture, validateAssetManifest } from '../src/art.ts';
import { validateScene } from '../src/scene.ts';
import { WorldModel } from '../src/model.ts';
import { bodyHeight } from '../src/physics.ts';
import type { AssetManifest, Scene, VisualDefinition } from '../src/types.ts';

function manifest(): AssetManifest {
  return {
    images: { sheet: { url: '/art/sheet.png', sampling: 'nearest' } },
    textures: {
      first: { image: 'sheet', frame: { x: 0, y: 0, width: 32, height: 48 }, anchor: { x: 0.5, y: 1 } },
      second: { image: 'sheet', frame: { x: 32, y: 0, width: 32, height: 48 } },
    },
    animations: { idle: { frames: ['first'], fps: 8 }, walk: { frames: ['first', 'second'], fps: 10, loop: true }, jump: { frames: ['second'], loop: false } },
  };
}
function scene(): Scene {
  return {
    version: 1, name: 'Art contracts', tileWidth: 64, tileHeight: 32,
    assets: manifest(), map: [['floor', 'floor'], ['floor', 'floor']],
    tiles: { floor: { color: 0x557733, textures: ['first', 'second'] } },
    entityTypes: { hero: { blocking: true, bodyHeight: 24, visual: {
      kind: 'sprite', animation: 'idle', width: 36, scale: 2, tint: 0xffffff,
      anchor: { x: 0.5, y: 1 }, offset: { x: 0, y: -2 },
      animations: { idle: 'idle', walk: 'walk', directions: { ne: { jump: 'jump' } } },
    } } },
    entities: [{ id: 'hero', type: 'hero', c: 0, r: 0 }], controlledId: 'hero',
  };
}

test('manifest validation detaches nested frames, textures and animation data', () => {
  const input = manifest(), validated = validateAssetManifest(input);
  assert.deepEqual(validated, input);
  input.textures.first!.frame!.x = 5;
  input.animations!.walk!.frames.push('first');
  assert.equal(validated.textures.first!.frame!.x, 0);
  assert.equal(validated.animations!.walk!.frames.length, 2);
  assert.deepEqual(validateAssetManifest(JSON.parse(JSON.stringify(validated))), validated);
});

test('manifest references never resolve inherited Object properties', () => {
  for (const id of ['missing', 'toString', '__proto__', 'constructor']) {
    const image = manifest(); image.textures.first!.image = id;
    assert.throws(() => validateAssetManifest(image), /unknown image/);
    const frame = manifest(); frame.animations!.idle!.frames = [id];
    assert.throws(() => validateAssetManifest(frame), /unknown texture/);
  }
  const unusual = JSON.parse('{"images":{"__proto__":{"url":"/sheet.png"}},"textures":{"constructor":{"image":"__proto__"}},"animations":{"toString":{"frames":["constructor"]}}}');
  assert.deepEqual(validateAssetManifest(unusual), unusual);
  assert.equal(Object.getPrototypeOf(validateAssetManifest(unusual).images), Object.prototype);
});

test('manifest rejects corrupt source frames, clips, sampling and unsafe JSON', () => {
  const mutations: ((data: AssetManifest) => void)[] = [
    data => { data.images.sheet!.url = ''; },
    data => { data.images.sheet!.sampling = 'cubic' as 'nearest'; },
    data => { data.textures.first!.frame!.width = 0; },
    data => { data.textures.first!.frame!.x = -1; },
    data => { data.textures.first!.frame!.height = 1.5; },
    data => { data.textures.first!.frame!.y = NaN; },
    data => { data.textures.first!.anchor!.x = 1.1; },
    data => { data.animations!.idle!.fps = Infinity; },
    data => { data.animations!.idle!.fps = 0; },
    data => { data.animations!.idle!.frames = []; },
    data => { data.animations!.idle!.loop = 1 as unknown as boolean; },
    data => { data.animations!.idle!.frames = Array(1025).fill('first'); },
  ];
  for (const mutate of mutations) { const input = manifest(); mutate(input); assert.throws(() => validateAssetManifest(input), TypeError); }
  for (const bad of [undefined, () => 1, new Date(), Symbol('bad'), NaN]) assert.throws(() => validateAssetManifest({ ...manifest(), bad }), TypeError);
  const cyclic = { ...manifest(), cycle: {} }; cyclic.cycle = cyclic;
  assert.throws(() => validateAssetManifest(cyclic), /cycle/);
  assert.throws(() => validateAssetManifest({ ...manifest(), oversized: Array(200_001) }), /data size/);
  let invoked = false;
  const accessor = Object.defineProperty(manifest(), 'bad', { enumerable: true, get: () => { invoked = true; return 1; } });
  assert.throws(() => validateAssetManifest(accessor), /accessors/);
  assert.equal(invoked, false);
});

test('tile variants are stable across traversal order, JSON copies and explicit ground', () => {
  const tile = { color: 0, textures: ['a', 'b', 'c', 'd', 'e'] };
  const cells = Array.from({ length: 64 }, (_, i) => ({ c: i % 8, r: Math.floor(i / 8) }));
  const initial = cells.map(cell => selectTileTexture(tile, cell));
  const reversed = [...cells].reverse().map(cell => selectTileTexture(JSON.parse(JSON.stringify(tile)), cell)).reverse();
  assert.deepEqual(reversed, initial);
  assert.ok(new Set(initial).size > 1);
  assert.deepEqual(cells.map(cell => selectTileTexture(tile, { ...cell, level: 'ground' })), initial);
  assert.notDeepEqual(cells.map(cell => selectTileTexture(tile, { ...cell, level: 'bridge' })), initial);
  assert.equal(selectTileTexture({ color: 0, texture: 'single' }, cells[0]!), 'single');
  assert.equal(selectTileTexture({ color: 0 }, cells[0]!), undefined);
});

test('side materials preserve their named texture through scene validation and reject missing references', () => {
  const input = scene();
  input.tiles.floor!.sideTexture = 'second';
  const parsed = validateScene(JSON.parse(JSON.stringify(input)));
  assert.equal(parsed.tiles.floor!.sideTexture, 'second');
  input.tiles.floor!.sideTexture = 'missing';
  assert.throws(() => validateScene(input), /unknown texture/);
});

test('animation resolution follows directional state, general state, directional idle, general idle, base', () => {
  const visual: VisualDefinition = { kind: 'sprite', animation: 'base', animations: {
    idle: 'general-idle', walk: 'general-walk', directions: { ne: { walk: 'ne-walk', idle: 'ne-idle' } },
  } };
  assert.equal(resolveAnimation(visual, 'walk', 'ne'), 'ne-walk');
  assert.equal(resolveAnimation(visual, 'walk', 'sw'), 'general-walk');
  assert.equal(resolveAnimation(visual, 'jump', 'ne'), 'ne-idle');
  assert.equal(resolveAnimation(visual, 'jump', 'sw'), 'general-idle');
  delete visual.animations!.directions!.ne!.walk;
  assert.equal(resolveAnimation(visual, 'walk', 'ne'), 'general-walk');
  assert.equal(resolveAnimation({ kind: 'sprite', animation: 'base' }, 'jump', 'n'), 'base');
  assert.equal(resolveAnimation({ kind: 'sprite', texture: 'first' }, 'idle', 'n'), undefined);
});

test('art scenes roundtrip through model snapshots while preserving independent footprint and body size', () => {
  const input = scene(), model = new WorldModel(input);
  const snapshot = model.serialize();
  assert.deepEqual(validateScene(JSON.parse(JSON.stringify(snapshot))), snapshot);
  assert.equal(snapshot.entityTypes.hero!.bodyHeight, 24);
  assert.equal(snapshot.entityTypes.hero!.visual.width, 36);
  input.entityTypes.hero!.visual.width = 4096;
  input.entityTypes.hero!.visual.scale = 100;
  const largerArt = new WorldModel(input);
  assert.deepEqual(largerArt.at({ c: 1, r: 0 }), []);
  assert.deepEqual(largerArt.path('hero', { c: 1, r: 1 }), model.path('hero', { c: 1, r: 1 }));
  assert.equal(largerArt.scene.entityTypes.hero!.bodyHeight, 24);
  assert.equal(bodyHeight(largerArt.scene.entityTypes.hero!), 24);
  assert.equal(bodyHeight({ visual: { kind: 'sprite', width: 4096, scale: 2 } }), 64);
});

test('legacy URL and individual frame sprites remain supported without a manifest', () => {
  for (const visual of [{ kind: 'sprite' as const, url: '/hero.png' }, { kind: 'sprite' as const, frames: ['/1.png', '/2.png'], fps: 6 }]) {
    const input = scene(); delete input.assets;
    input.tiles.floor = { color: 0 };
    input.entityTypes.hero!.visual = visual;
    assert.deepEqual(validateScene(input), input);
  }
});

test('scene rejects ambiguous or missing sprite sources and unknown art references', () => {
  const mutations: ((data: Scene) => void)[] = [
    data => { data.entityTypes.hero!.visual.url = '/hero.png'; },
    data => { data.entityTypes.hero!.visual = { kind: 'sprite' }; },
    data => { data.entityTypes.hero!.visual = { kind: 'sprite', url: '/1.png', frames: ['/2.png'] }; },
    data => { data.tiles.floor!.texture = 'first'; },
    data => { data.tiles.floor!.textures = []; },
    data => { data.tiles.floor!.textures = ['toString']; },
    data => { data.entityTypes.hero!.visual.animation = 'toString'; },
    data => { data.entityTypes.hero!.visual.animations!.walk = 'missing'; },
    data => { data.entityTypes.hero!.visual.animations!.directions!.ne!.jump = 'missing'; },
    data => { data.entityTypes.hero!.visual.animations!.directions = { bad: { idle: 'idle' } } as never; },
    data => { data.entityTypes.hero!.visual = { kind: 'sprite', url: '/1.png', animations: { idle: 'idle' } }; },
    data => { delete data.assets; },
  ];
  for (const mutate of mutations) { const input = scene(); mutate(input); assert.throws(() => validateScene(input), TypeError); }
});

test('scene bounds presentation fields and requires a positive finite physical body height', () => {
  for (const bodyHeight of [0, -1, NaN, Infinity, 4097]) {
    const input = scene(); input.entityTypes.hero!.bodyHeight = bodyHeight;
    assert.throws(() => validateScene(input), /bodyHeight/);
  }
  for (const field of [{ width: 0 }, { width: 4097 }, { tint: 0x1000000 }, { anchor: { x: -0.1, y: 1 } }, { offset: { x: 4097, y: 0 } }]) {
    const input = scene(); Object.assign(input.entityTypes.hero!.visual, field);
    assert.throws(() => validateScene(input), TypeError);
  }
});
