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
for (const file of ['quilt-materials.py', 'quilt_materials.py', 'create-quilting-fixture.py', 'bind-ground.mjs', 'compose-landscape-ground.py', 'create-landscape-fixture.py']) await access(resolve(scripts, file));
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

// A separate synthetic recipe exercises contacts and protected object underlays.
// Both commands must resolve from the installed package, never the source checkout.
run(python, ['-B', resolve(scripts, 'create-landscape-fixture.py'), '--out', 'diagnostics/landscape']);
for (const out of ['public/art/landscape-diagnostic', 'diagnostics/landscape-replay']) {
  run(python, ['-B', resolve(scripts, 'compose-landscape-ground.py'), 'diagnostics/landscape/recipe.json', '--project-root', '.', '--out', out]);
}
for (const file of ['ground.png', 'composition-report.json', 'provenance.json']) {
  assert.deepEqual(await readFile(`public/art/landscape-diagnostic/${file}`), await readFile(`diagnostics/landscape-replay/${file}`), `Nondeterministic landscape ${file}`);
}
run(process.execPath, [resolve(scripts, 'bind-ground.mjs'), 'diagnostics/landscape/scene.json', 'public/art/landscape-diagnostic/packed-art.json', '--out', 'diagnostics/landscape-bound', '--image-url', './art/landscape-diagnostic/ground.png']);
run(python, ['-B', resolve(pkg, 'skills/isometric-visual-loop/scripts/verify-world.py'), 'inspect', 'public/art/landscape-diagnostic/packed-art.json', '--out', 'diagnostics/landscape-inspection']);
const landscapeOriginal = validateScene(JSON.parse(await readFile('diagnostics/landscape/scene.json')));
const landscapeScene = validateScene(JSON.parse(await readFile('diagnostics/landscape-bound/scene.json')));
const landscapeBinding = JSON.parse(await readFile('diagnostics/landscape-bound/binding.json'));
const composition = JSON.parse(await readFile('public/art/landscape-diagnostic/composition-report.json'));
assert.deepEqual(landscapeScene.entities, landscapeOriginal.entities);
assert.deepEqual(landscapeScene.entityTypes, landscapeOriginal.entityTypes);
assert.equal(composition.protectedPixelReport.unchangedAfterUnderlays, true);
assert.equal(composition.geometrySource, 'diagnostics/landscape/geometry.json');
assert.ok(composition.contacts.length > 0 && composition.underlays.length > 0);
// Exercise the cross-tool schema with real installed compositor output.
// Independent unit fixtures for each script would miss incompatible path/hash fields.
run(python, ['-B', '-c', `
import importlib.util
from pathlib import Path
root = Path.cwd()
script = root / 'node_modules/isometric-framework/skills/isometric-visual-loop/scripts/production_flow.py'
spec = importlib.util.spec_from_file_location('production_flow', script)
flow = importlib.util.module_from_spec(spec); spec.loader.exec_module(flow)
land = {'geometrySource': 'diagnostics/landscape/geometry.json', 'compositionRecipe': 'diagnostics/landscape/recipe.json', 'compositionReport': 'public/art/landscape-diagnostic/composition-report.json'}
flow._v5_composition(root, land, flow.inputs(root, ['diagnostics/landscape', 'public/art/landscape-diagnostic']))
print('Installed compositor report accepted by installed v5 validator.')
`]);
for (const cell of landscapeBinding.cells) {
  const point = project(cell.cell, landscapeScene.tileWidth, landscapeScene.tileHeight);
  const { sourceScale, origin } = landscapeBinding.image;
  assert.equal(cell.frame.x + cell.frame.width / 2, point.x * sourceScale - origin.x);
  assert.equal(cell.frame.y + cell.frame.height / 2, point.y * sourceScale - origin.y);
  assert.equal(landscapeScene.tiles[cell.newTile].walkable, landscapeOriginal.tiles[cell.originalTile].walkable);
}
console.log(`Packed landscape consumer: deterministic composition, protected pixels, ${landscapeBinding.cells.length} projected frames and unchanged host semantics passed. Not an art verdict.`);
