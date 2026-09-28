// Run from a fresh installed consumer: node /path/to/framework/tests/quilt-consumer.mjs
// This is a synthetic offline integration check, not artwork approval.
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { readFile, access } from 'node:fs/promises';
import { resolve } from 'node:path';
import { pathToFileURL } from 'node:url';

const root = process.cwd();
const pkg = resolve(root, 'node_modules/isometric-framework');
const scripts = resolve(pkg, 'skills/consistent-tileset-authoring/scripts');
const python = process.env.PYTHON ?? 'python3';
const run = (command, args) => execFileSync(command, args, { cwd: root, stdio: 'inherit', timeout: 120000 });
for (const file of ['quilt-materials.py', 'quilt_materials.py', 'create-quilting-fixture.py', 'bind-ground.mjs']) await access(resolve(scripts, file));
run(python, ['-B', resolve(scripts, 'create-quilting-fixture.py'), 'diagnostics/quilt']);
for (const out of ['public/art/quilt-diagnostic', 'diagnostics/replay']) {
  run(python, ['-B', resolve(scripts, 'quilt-materials.py'), 'diagnostics/quilt/recipe.json', '--out', out]);
}
assert.deepEqual(await readFile('public/art/quilt-diagnostic/ground.png'), await readFile('diagnostics/replay/ground.png'));
assert.deepEqual(await readFile('public/art/quilt-diagnostic/provenance.json'), await readFile('diagnostics/replay/provenance.json'));
run(process.execPath, [resolve(scripts, 'bind-ground.mjs'), 'diagnostics/quilt/scene.json', 'public/art/quilt-diagnostic/packed-art.json', '--out', 'diagnostics/bound', '--image-url', './art/quilt-diagnostic/ground.png']);
run(python, ['-B', resolve(pkg, 'skills/isometric-visual-loop/scripts/verify-world.py'), 'inspect', 'public/art/quilt-diagnostic/packed-art.json', '--out', 'diagnostics/inspection']);
const { project, validateScene } = await import(pathToFileURL(resolve(pkg, 'dist/core.js')).href);
const original = JSON.parse(await readFile('diagnostics/quilt/scene.json'));
const scene = validateScene(JSON.parse(await readFile('diagnostics/bound/scene.json')));
const binding = JSON.parse(await readFile('diagnostics/bound/binding.json'));
assert.equal(binding.cells.length, 35);
assert.deepEqual(scene.entities, original.entities);
assert.deepEqual(scene.entityTypes, validateScene(original).entityTypes);
assert.equal(binding.image.sourceScale, 2);
for (const item of binding.cells) {
  const p = project(item.cell, scene.tileWidth, scene.tileHeight);
  const { frame } = item;
  assert.equal(frame.x + frame.width / 2, p.x * 2 - binding.image.origin.x);
  assert.equal(frame.y + frame.height / 2, p.y * 2 - binding.image.origin.y);
  assert.equal(scene.tiles[item.newTile].walkable, original.tiles[item.originalTile].walkable);
  assert.equal(scene.tiles[item.newTile].color, 0xffffff);
}
assert.equal(scene.assets.images['ground-binding-image'].sampling, 'nearest');
assert.equal(scene.assets.images['ground-binding-image'].url, './art/quilt-diagnostic/ground.png');
assert.ok(!JSON.stringify(scene).includes(root));
console.log('Packed quilting consumer: deterministic replay, surface inspection, 35 projected frames, collision/entities and local URLs passed.');
