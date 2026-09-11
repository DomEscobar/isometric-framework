import assert from 'node:assert/strict';
import { mkdtemp, mkdir, readFile, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { resolve } from 'node:path';
import test from 'node:test';
import { renderLayout, validateLayout, loadProject } from '../scripts/render-layout.mjs';

const layout = () => ({ version: 1, spawn: [0, 0, 'ground'], regions: [{ id: 'ground', kind: 'grass', cells: [[0, 0, 'ground'], [1, 0, 'ground'], [0, 1, 'ground'], [-2, 2, 'ground']] }], instances: [{ id: 'house', kind: 'building', footprint: [[1, 0, 'ground']], approaches: [[0, 0, 'ground']] }, { id: 'oak', kind: 'tree', footprint: [[-2, 2, 'ground']], approaches: [] }], routes: [{ id: 'path', cells: [[0, 0, 'ground'], [1, 0, 'ground']], start: [0, 0, 'ground'], goals: [[1, 0, 'ground']] }], bridges: [{ id: 'crossing', deck: [[0, 1, 'ground']], landings: [[0, 0, 'ground'], [0, 1, 'ground']], waterOverlayCells: [] }] });
async function fixture() { const root = await mkdtemp(resolve(tmpdir(), 'layout-render-')); const input = resolve(root, 'layout.json'); await writeFile(input, JSON.stringify(layout())); return { root, input }; }

test('uses the public projection and keeps negative projected y in bounds', async () => {
  const { root, input } = await fixture(); const result = await renderLayout({ input, out: resolve(root, 'out'), packageRoot: resolve(process.cwd()) });
  const output = JSON.parse(await readFile(resolve(result.outPath, 'projection.json'), 'utf8'));
  assert.deepEqual(output.axisUnitPoints.map(item => item.center), [{ x: 0, y: 0 }, { x: 32, y: -16 }, { x: 32, y: 16 }]);
  assert.equal(output.projectionModule, 'src/core.ts');
  assert.ok(output.output.origin.y <= -32, 'upper-right tile and padding are retained');
  assert.match(await readFile(resolve(result.outPath, 'layout.svg'), 'utf8'), /<polygon/);
});

test('rejects malformed cells, unsupported elevation and an existing output directory', async () => {
  assert.throws(() => validateLayout({ ...layout(), spawn: [0.2, 0, 'ground'] }), /spawn must be/);
  assert.throws(() => validateLayout({ ...layout(), elevation: 12 }), /Top-level elevation/);
  assert.throws(() => validateLayout({ ...layout(), spawn: [0, 0, 'roof'] }), /one floor only/);
  const { root, input } = await fixture(); const out = resolve(root, 'out'); await mkdir(out);
  await assert.rejects(renderLayout({ input, out, packageRoot: process.cwd() }), /already exists/);
  await assert.rejects(renderLayout({ input, out: resolve(root, 'bad-dimensions'), tileWidth: 0, packageRoot: process.cwd() }), /tileWidth/);
});

test('falls back to dist/core.js when source is absent', async () => {
  const root = await mkdtemp(resolve(tmpdir(), 'layout-package-')); await writeFile(resolve(root, 'package.json'), '{"type":"module"}'); await mkdir(resolve(root, 'dist'));
  await writeFile(resolve(root, 'dist/core.js'), 'export function project(cell, w, h) { return { x: (cell.c + cell.r) * w / 2, y: (cell.r - cell.c) * h / 2 }; }');
  const api = await loadProject(root); assert.equal(api.modulePath, resolve(root, 'dist/core.js')); assert.deepEqual(api.project({ c: 1, r: 0 }, 64, 32), { x: 32, y: -16 });
});
