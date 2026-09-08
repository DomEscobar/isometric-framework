import assert from 'node:assert/strict';
import { test } from 'node:test';
import { analyzeAutotiles, autotileMasks, resolveAutotiles, type AutotileCell } from '../src/core.ts';

test('cardinal16 preserves legacy planter masks on isolated, strip, L and hole layouts', () => {
  const fixtures = [
    [{ c: 0, r: 0 }],
    [{ c: 0, r: 0 }, { c: 1, r: 0 }, { c: 2, r: 0 }],
    [{ c: 0, r: 0 }, { c: 1, r: 0 }, { c: 1, r: 1 }],
    Array.from({ length: 9 }, (_, i) => ({ c: i % 3, r: Math.floor(i / 3) })).filter(p => p.c !== 1 || p.r !== 1),
  ];
  for (const cells of fixtures) {
    const before = structuredClone(cells);
    const occupied = new Set(cells.map(p => `${p.c},${p.r}`));
    const legacy = cells.map(p => [[-1, 0], [1, 0], [0, -1], [0, 1]].reduce((mask, [dc, dr], bit) =>
      mask | (occupied.has(`${p.c + dc!},${p.r + dr!}`) ? 1 << bit : 0), 0));
    assert.deepEqual(analyzeAutotiles(cells, { mode: 'cardinal16' }).map(p => p.mask), legacy);
    assert.deepEqual(cells, before);
  }
  assert.deepEqual(analyzeAutotiles(fixtures[1]!, { mode: 'cardinal16' }).map(p => p.mask), [2, 3, 1]);
  assert.deepEqual(analyzeAutotiles(fixtures[2]!, { mode: 'cardinal16' }).map(p => p.mask), [2, 9, 4]);
  assert.deepEqual(autotileMasks('cardinal16'), Array.from({ length: 16 }, (_, i) => i));
});

test('blob47 gates diagonal contacts, preserves concave corners and yields exactly 47 masks', () => {
  const center = { c: 0, r: 0 };
  const mask = (cells: AutotileCell[]) => analyzeAutotiles([center, ...cells], { mode: 'blob47' })[0]!.mask;
  assert.equal(mask([{ c: 1, r: 1 }]), 0, 'diagonal-only contact never joins');
  assert.equal(mask([{ c: 1, r: 0 }, { c: 1, r: 1 }]), 2, 'one cardinal is insufficient');
  assert.equal(mask([{ c: 1, r: 0 }, { c: 0, r: 1 }]), 10, 'L retains its inside corner');
  assert.equal(mask([{ c: 1, r: 0 }, { c: 0, r: 1 }, { c: 1, r: 1 }]), 138, 'filled corner joins');
  const neighbors = Array.from({ length: 9 }, (_, i) => ({ c: i % 3 - 1, r: Math.floor(i / 3) - 1 }))
    .filter(p => p.c !== 0 || p.r !== 0);
  assert.equal(mask(neighbors), 255);
  assert.equal(mask(neighbors.filter(p => p.c !== 1 || p.r !== 1)), 127, 'diagonal hole is visible');
  const observed = new Set(Array.from({ length: 256 }, (_, bits) => mask(neighbors.filter((_, i) => bits & (1 << i)))));
  assert.equal(observed.size, 47);
  assert.deepEqual([...observed].sort((a, b) => a - b), autotileMasks('blob47'));
});

test('floor identity, family and elevation are independent connection boundaries', () => {
  const cells: AutotileCell[] = [
    { c: 0, r: 0, family: 'soil' },
    { c: -1, r: 0, level: 'ground', family: 'soil', elevation: 0 },
    { c: 1, r: 0, family: 'water' },
    { c: 0, r: -1, family: 'soil', elevation: 8 },
    { c: 0, r: 1, level: 'bridge', family: 'soil' },
    { c: 0, r: 0, level: 'bridge', family: 'soil' },
  ];
  assert.equal(analyzeAutotiles(cells, { mode: 'cardinal16' })[0]!.mask, 1);
  assert.equal(analyzeAutotiles(cells, { mode: 'cardinal16', connectFamilies: true })[0]!.mask, 3);
  assert.equal(analyzeAutotiles(cells, { mode: 'cardinal16', matchElevation: false })[0]!.mask, 5);
  const both = analyzeAutotiles(cells, { mode: 'cardinal16', connectFamilies: true, matchElevation: false });
  assert.equal(both[0]!.mask, 7, 'even equal-height bridge cells never connect to ground');
  assert.equal(both[5]!.mask, 8);
  const square = [{ c: 0, r: 0 }, { c: 1, r: 0 }, { c: 0, r: 1 }, { c: 1, r: 1, family: 'other' }];
  assert.equal(analyzeAutotiles(square, { mode: 'blob47' })[0]!.mask, 10, 'diagonal obeys same family rules');
  assert.equal(analyzeAutotiles(square, { mode: 'blob47', connectFamilies: true })[0]!.mask, 138);
});

test('variant resolution is stable across batch order, reports missing entries and rejects ambiguity', () => {
  const cells = Array.from({ length: 32 }, (_, i) => ({ c: i * 3, r: 0 }));
  const rules = { mode: 'cardinal16' as const, variants: { 0: ['a', 'b', 'c', 'd'] }, seed: 'garden' };
  const first = resolveAutotiles(cells, rules);
  assert.equal(first.diagnostics.length, 0);
  assert.deepEqual(resolveAutotiles(cells, rules), first);
  assert.deepEqual(resolveAutotiles([...cells].reverse(), rules).tiles.reverse(), first.tiles);
  assert.deepEqual(resolveAutotiles(cells.map(p => ({ ...p, level: 'ground', elevation: 0 })), rules).tiles.map(p => p.variant), first.tiles.map(p => p.variant));
  assert.ok(new Set(first.tiles.map(p => p.variant)).size > 1);
  assert.notDeepEqual(resolveAutotiles(cells, { ...rules, seed: 'other' }).tiles.map(p => p.variant), first.tiles.map(p => p.variant));
  const missing = resolveAutotiles([{ c: 0, r: 0 }, { c: 1, r: 0 }], { mode: 'cardinal16', variants: { 0: 'isolated', 1: [] } });
  assert.deepEqual(missing.tiles.map(p => [p.mask, p.variant]), [[2, null], [1, null]]);
  assert.deepEqual(missing.diagnostics.map(p => [p.code, p.mask]), [['missing-variant', 2], ['missing-variant', 1]]);
  missing.diagnostics[0]!.cell.c = 99;
  assert.equal(missing.tiles[0]!.cell.c, 0, 'diagnostics and results do not alias cells');
  assert.throws(() => analyzeAutotiles([{ c: 0, r: 0 }, { c: 0, r: 0, level: 'ground' }], rules), /Duplicate/);
  assert.throws(() => analyzeAutotiles([{ c: 0.5, r: 0 }], rules), /safe integers/);
  assert.throws(() => resolveAutotiles([], { mode: 'blob47', variants: { 16: 'ungated' } }), /Noncanonical/);
  assert.throws(() => resolveAutotiles([], { mode: 'cardinal16', variants: { 0: '' } }), /nonempty IDs/);
});
