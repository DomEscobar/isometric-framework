import assert from 'node:assert/strict';
import { mkdtemp, mkdir, readFile, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { resolve } from 'node:path';
import test from 'node:test';
import { bindGround } from '../scripts/bind-ground.mjs';
import { validateScene } from '../../../src/core.ts';

const png = (width, height) => { const header = Buffer.alloc(24); Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]).copy(header); header.writeUInt32BE(13, 8); header.write('IHDR', 12); header.writeUInt32BE(width, 16); header.writeUInt32BE(height, 20); return header; };
const baseScene = () => ({ version: 1, name: 'Ground binding', tileWidth: 64, tileHeight: 32, diagonal: false, maxStepHeight: 0, map: [['grass', 'water'], ['rock', 'grass']], tiles: { grass: { color: 0x338844, walkable: true }, water: { color: 0x2244aa, walkable: false, sideTexture: 'side' }, rock: { color: 0x777777, walkable: true } }, assets: { images: { sideImage: { url: './side.png' } }, textures: { side: { image: 'sideImage' } } }, entityTypes: { actor: { visual: { kind: 'box', color: 0xffffff } } }, entities: [{ id: 'hero', type: 'actor', c: 0, r: 0 }], controlledId: 'hero' });
async function fixture(scene = baseScene(), options = {}) { const root = await mkdtemp(resolve(tmpdir(), 'bind-ground-')); const prepared = resolve(root, 'prepared'); await mkdir(prepared); await writeFile(resolve(root, 'scene.json'), JSON.stringify(scene)); await writeFile(resolve(prepared, 'ground.png'), png(options.width ?? 192, options.height ?? 96)); await writeFile(resolve(prepared, 'packed-art.json'), JSON.stringify({ version: 1, groups: [{ id: 'ground', kind: 'surface', composition: { reference: 'ground.png', origin: options.origin ?? [-32, -32] } }] })); return { root, scene: resolve(root, 'scene.json'), packed: resolve(prepared, 'packed-art.json'), out: resolve(root, 'bound') }; }

test('binds each flat map cell to a continuous prepared PNG using public projection', async () => {
  const f = await fixture(); const result = await bindGround({ scene: f.scene, packed: f.packed, out: f.out, imageUrl: './art/prepared/ground.png' });
  const saved = JSON.parse(await readFile(resolve(f.out, 'scene.json'), 'utf8')); assert.deepEqual(validateScene(saved), saved);
  assert.equal(saved.map[0][0], 'ground-binding-tile-0-0'); assert.equal(saved.map[0][1], 'ground-binding-tile-1-0'); assert.equal(saved.map[1][0], 'ground-binding-tile-0-1');
  const first = saved.assets.textures['ground-binding-texture-0-0'].frame; const cPlus = saved.assets.textures['ground-binding-texture-1-0'].frame; const rPlus = saved.assets.textures['ground-binding-texture-0-1'].frame;
  assert.deepEqual(first, { x: 0, y: 16, width: 64, height: 32 }); assert.deepEqual(cPlus, { x: 32, y: 0, width: 64, height: 32 }); assert.deepEqual(rPlus, { x: 32, y: 32, width: 64, height: 32 });
  assert.equal(saved.tiles['ground-binding-tile-1-0'].walkable, false); assert.equal(saved.tiles['ground-binding-tile-1-0'].sideTexture, 'side'); assert.equal(saved.tiles['ground-binding-tile-1-0'].texture, 'ground-binding-texture-1-0');
  assert.deepEqual(saved.entities, baseScene().entities); assert.equal(result.binding.cells.length, 4);
});

test('rejects out-of-bounds or nonintegral source frames and does not create output', async () => {
  const small = await fixture(baseScene(), { width: 64, height: 32 }); await assert.rejects(bindGround({ scene: small.scene, packed: small.packed, out: small.out, imageUrl: './ground.png' }), /exceeds composition/);
  const odd = baseScene(); odd.tileWidth = 63; const misaligned = await fixture(odd); await assert.rejects(bindGround({ scene: misaligned.scene, packed: misaligned.packed, out: misaligned.out, imageUrl: './ground.png' }), /frame x|frame y/);
});

test('rejects elevated or multi-floor input and an existing output directory', async () => {
  const elevated = baseScene(); elevated.tiles.grass.elevation = 4; const f = await fixture(elevated); await assert.rejects(bindGround({ scene: f.scene, packed: f.packed, out: f.out, imageUrl: './ground.png' }), /flat ground/);
  const multi = baseScene(); multi.version = 2; multi.levels = [{ id: 'roof', name: 'Roof', height: 32, map: [[null, null], [null, null]] }]; multi.links = []; const g = await fixture(multi); await assert.rejects(bindGround({ scene: g.scene, packed: g.packed, out: g.out, imageUrl: './ground.png' }), /flat ground/);
  const h = await fixture(); await mkdir(h.out); await assert.rejects(bindGround({ scene: h.scene, packed: h.packed, out: h.out, imageUrl: './ground.png' }), /already exists/);
});
