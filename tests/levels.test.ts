import assert from 'node:assert/strict';
import { test } from 'node:test';
import { WorldModel } from '../src/model.ts';
import { cellKey, levelHeight, sameCell } from '../src/levels.ts';
import { validateScene } from '../src/scene.ts';
import type { Cell, Scene } from '../src/types.ts';

function scene(): Scene {
  return {
    version: 2, name: 'Stacked floors', tileWidth: 64, tileHeight: 32,
    map: Array.from({ length: 5 }, () => Array<string>(5).fill('floor')),
    tiles: { floor: { color: 0x44aa66 }, raised: { color: 0x997744, elevation: 8 }, water: { color: 0x3366bb, walkable: false } },
    entityTypes: {
      actor: { visual: { kind: 'actor' }, blocking: true },
      wall: { visual: { kind: 'box' }, blocking: true },
      wide: { visual: { kind: 'actor' }, blocking: true, columns: 2 },
    },
    entities: [{ id: 'hero', type: 'actor', c: 1, r: 1, data: { stats: { health: 5 } } }],
    controlledId: 'hero', diagonal: false,
    levels: [{ id: 'upper', name: 'Upper', height: 64, map: Array.from({ length: 5 }, () => Array<string | null>(5).fill('floor')) }],
    links: [{ from: { c: 1, r: 1 }, to: { c: 2, r: 1, level: 'upper' } }],
  };
}

function assertRoute(model: WorldModel, target: Cell): Cell[] {
  const path = model.path('hero', target);
  assert.ok(path, 'expected a complete reachable route');
  assert.ok(path.length > 0, 'different floors must not collapse into a zero-length route');
  assert.equal(sameCell(path.at(-1)!, target), true);
  let previous: Cell = model.entity('hero')!;
  for (const cell of path) {
    assert.equal(model.canMove('hero', previous, cell), true, `invalid segment ${cellKey(previous)} -> ${cellKey(cell)}`);
    previous = cell;
  }
  return path;
}

test('stacked cells have independent identity, occupancy, and blocking', () => {
  const model = new WorldModel(scene());
  model.add({ id: 'upper-wall', type: 'wall', c: 1, r: 1, level: 'upper' });
  assert.deepEqual(model.at({ c: 1, r: 1 }).map(entity => entity.id), ['hero']);
  assert.deepEqual(model.at({ c: 1, r: 1, level: 'upper' }).map(entity => entity.id), ['upper-wall']);
  assert.equal(model.canEnter({ c: 1, r: 1 }, 'hero'), true);
  assert.equal(model.canEnter({ c: 1, r: 1, level: 'upper' }, 'hero'), false);
  assert.equal(sameCell({ c: 1, r: 1 }, { c: 1, r: 1, level: 'ground' }), true);
  assert.equal(sameCell({ c: 1, r: 1 }, { c: 1, r: 1, level: 'upper' }), false);
  assert.notEqual(cellKey({ c: 1, r: 1 }), cellKey({ c: 1, r: 1, level: 'upper' }));
  model.remove('upper-wall');
  assert.equal(model.canEnter({ c: 1, r: 1, level: 'upper' }), true);
  assert.equal(model.canEnter({ c: 1, r: 1 }), false);
});

test('cross-floor routes include stairs even when the destination shares start coordinates', () => {
  const model = new WorldModel(scene());
  const path = assertRoute(model, { c: 1, r: 1, level: 'upper' });
  assert.deepEqual(path, [{ c: 2, r: 1, level: 'upper' }, { c: 1, r: 1, level: 'upper' }]);
  model.setPosition('hero', path.at(-1)!);
  assertRoute(model, { c: 1, r: 1 });
  assert.equal(model.at({ c: 1, r: 1 }).length, 0);
  assert.equal(model.at({ c: 1, r: 1, level: 'upper' })[0]!.id, 'hero');
});

test('separate floors cannot be reached without explicit links regardless of step height', () => {
  const source = scene(); source.links = []; source.maxStepHeight = 1000;
  const model = new WorldModel(source);
  assert.equal(model.path('hero', { c: 1, r: 1, level: 'upper' }), null);
  assert.equal(model.path('hero', { c: 2, r: 1, level: 'upper' }), null);
  assert.equal(model.canMove('hero', { c: 1, r: 1 }, { c: 2, r: 1, level: 'upper' }), false);
});

test('one-way stairs permit only the declared direction', () => {
  const source = scene(); source.links![0]!.bidirectional = false;
  const model = new WorldModel(source);
  assertRoute(model, { c: 3, r: 1, level: 'upper' });
  model.setPosition('hero', { c: 2, r: 1, level: 'upper' });
  assert.equal(model.path('hero', { c: 1, r: 1 }), null);
  assert.equal(model.canMove('hero', model.entity('hero')!, { c: 1, r: 1 }), false);
});

test('holes, floor edges, and blocked landings are impassable', () => {
  const source = scene(); source.levels![0]!.map[2]![2] = null;
  const model = new WorldModel(source);
  for (const target of [{ c: 2, r: 2, level: 'upper' }, { c: -1, r: 1, level: 'upper' }, { c: 5, r: 1, level: 'upper' }, { c: 2, r: 1, level: 'missing' }]) {
    assert.equal(model.tile(target), null);
    assert.equal(model.canEnter(target), false);
    assert.equal(model.path('hero', target), null);
  }
  model.add({ id: 'landing-wall', type: 'wall', c: 2, r: 1, level: 'upper' });
  assert.equal(model.path('hero', { c: 4, r: 4, level: 'upper' }), null);
  model.remove('landing-wall');
  assertRoute(model, { c: 4, r: 4, level: 'upper' });
});

test('wide entities need parallel stairs and complete support for every footprint cell', () => {
  const source = scene(); source.entities[0]!.type = 'wide';
  source.links = [{ from: { c: 1, r: 1 }, to: { c: 1, r: 2, level: 'upper' } }];
  assert.equal(new WorldModel(source).path('hero', { c: 1, r: 2, level: 'upper' }), null);
  source.links.push({ from: { c: 2, r: 1 }, to: { c: 2, r: 2, level: 'upper' } });
  const model = new WorldModel(source);
  assert.deepEqual(assertRoute(model, { c: 1, r: 2, level: 'upper' }), [{ c: 1, r: 2, level: 'upper' }]);
  model.setPosition('hero', { c: 1, r: 2, level: 'upper' });
  assert.equal(model.at({ c: 2, r: 2, level: 'upper' })[0]!.id, 'hero');
  assert.equal(model.at({ c: 2, r: 1 }).length, 0);
  assertRoute(model, { c: 1, r: 1 });
  model.add({ id: 'block-half', type: 'wall', c: 3, r: 2, level: 'upper' });
  assert.equal(model.nextStep('hero', { c: 1, r: 0 }), null);
  assert.equal(model.path('hero', { c: 4, r: 2, level: 'upper' }), null);
  source.levels![0]!.map[3]![2] = null;
  const holes = new WorldModel(source);
  holes.setPosition('hero', { c: 1, r: 2, level: 'upper' });
  assert.equal(holes.nextStep('hero', { c: 0, r: 1 }), null);
  assert.throws(() => holes.setPosition('hero', { c: 1, r: 3, level: 'upper' }), RangeError);
});

test('absolute tile heights add floor elevation without modifying serialized tile definitions', () => {
  const source = scene(); source.map[0]![0] = 'raised'; source.levels![0]!.map[0]![0] = 'raised';
  source.levels!.push({ id: 'basement', name: 'Basement', height: -48, map: structuredClone(source.levels![0]!.map) });
  const before = structuredClone(source), model = new WorldModel(source);
  assert.equal(model.tile({ c: 0, r: 0 })!.elevation, 8);
  assert.equal(model.tile({ c: 0, r: 0, level: 'upper' })!.elevation, 72);
  assert.equal(model.tile({ c: 0, r: 0, level: 'basement' })!.elevation, -40);
  assert.equal(levelHeight(source, 'ground'), 0);
  assert.equal(levelHeight(source, 'upper'), 64);
  assert.throws(() => levelHeight(source, 'missing'), RangeError);
  assert.deepEqual(model.serialize(), before);
  assert.deepEqual(source, before);
});

test('multilevel snapshots are detached and serialize through JSON without losing floors or stairs', () => {
  const source = scene(), model = new WorldModel(source);
  const expected = model.serialize();
  source.levels![0]!.map[0]![0] = null;
  source.links![0]!.to.c = 4;
  for (const snapshot of [model.serialize(), model.scene]) {
    snapshot.levels![0]!.map[0]![0] = null;
    snapshot.links![0]!.to.level = 'missing';
    (snapshot.entities[0]!.data!.stats as { health: number }).health = -1;
  }
  const tile = model.tile({ c: 1, r: 1, level: 'upper' })!; tile.elevation = 900;
  assert.deepEqual(model.serialize(), expected);
  const restored = new WorldModel(JSON.parse(JSON.stringify(model.serialize())));
  assert.deepEqual(restored.serialize(), expected);
  assertRoute(restored, { c: 1, r: 1, level: 'upper' });
  restored.setPosition('hero', { c: 2, r: 1, level: 'upper' });
  const moved = new WorldModel(JSON.parse(JSON.stringify(restored.serialize())));
  assert.equal(moved.entity('hero')!.level, 'upper');
  assertRoute(moved, { c: 1, r: 1 });
});

test('multilevel validation rejects malformed versions, floors, heights, and dimensions', () => {
  const invalid: [string, (source: Scene) => void][] = [
    ['version one with floors', source => { source.version = 1; }],
    ['unknown version', source => { (source as unknown as { version: number }).version = 3; }],
    ['missing levels', source => { delete source.levels; }],
    ['missing links', source => { delete source.links; }],
    ['reserved ground ID', source => { source.levels![0]!.id = 'ground'; }],
    ['duplicate floor ID', source => { source.levels!.push({ ...structuredClone(source.levels![0]!), height: 128 }); }],
    ['duplicate height', source => { source.levels!.push({ ...structuredClone(source.levels![0]!), id: 'third' }); }],
    ['zero height', source => { source.levels![0]!.height = 0; }],
    ['nonfinite height', source => { source.levels![0]!.height = NaN; }],
    ['empty ID', source => { source.levels![0]!.id = ''; }],
    ['missing row', source => { source.levels![0]!.map.pop(); }],
    ['ragged row', source => { source.levels![0]!.map[0]!.pop(); }],
    ['unknown floor tile', source => { source.levels![0]!.map[0]![0] = 'missing'; }],
    ['hole on ground map', source => { (source.map as (string | null)[][])[0]![0] = null; }],
    ['too many floors', source => { source.levels = Array.from({ length: 9 }, (_, i) => ({ ...structuredClone(source.levels![0]!), id: `floor-${i}`, height: i + 1 })); }],
  ];
  for (const [name, mutate] of invalid) {
    const source = scene(); mutate(source);
    assert.throws(() => validateScene(source), TypeError, name);
  }
});

test('multilevel validation rejects invalid entity floors and unsupported footprints', () => {
  const invalid: [string, (source: Scene) => void][] = [
    ['unknown entity floor', source => { source.entities[0]!.level = 'missing'; }],
    ['empty entity floor', source => { source.entities[0]!.level = ''; }],
    ['entity in hole', source => { source.entities[0]!.level = 'upper'; source.levels![0]!.map[1]![1] = null; }],
    ['wide entity partially unsupported', source => { source.entities[0]!.type = 'wide'; source.entities[0]!.level = 'upper'; source.entities[0]!.r = 3; source.levels![0]!.map[3]![2] = null; }],
    ['wide entity beyond edge', source => { source.entities[0]!.type = 'wide'; source.entities[0]!.c = 4; }],
    ['fractional position', source => { source.entities[0]!.r = 0.5; }],
  ];
  for (const [name, mutate] of invalid) {
    const source = scene(); mutate(source);
    assert.throws(() => validateScene(source), TypeError, name);
  }
});

test('multilevel validation rejects stairs with invalid endpoints or duplicate edges', () => {
  const invalid: [string, (source: Scene) => void][] = [
    ['same floor', source => { delete source.links![0]!.to.level; }],
    ['same coordinates', source => { source.links![0]!.to.c = 1; }],
    ['diagonal stair', source => { source.links![0]!.to.r = 2; }],
    ['distant stair', source => { source.links![0]!.to.c = 4; }],
    ['outside map', source => { source.links![0]!.from.c = -1; }],
    ['fractional coordinate', source => { source.links![0]!.from.c = 1.5; }],
    ['unknown floor', source => { source.links![0]!.to.level = 'missing'; }],
    ['hole endpoint', source => { source.levels![0]!.map[1]![2] = null; }],
    ['blocked endpoint', source => { source.levels![0]!.map[1]![2] = 'water'; }],
    ['duplicate edge', source => { source.links!.push(structuredClone(source.links![0]!)); }],
    ['reverse duplicate edge', source => { const link = source.links![0]!; source.links!.push({ from: structuredClone(link.to), to: structuredClone(link.from) }); }],
    ['nonboolean direction flag', source => { (source.links![0] as unknown as { bidirectional: string }).bidirectional = 'yes'; }],
  ];
  for (const [name, mutate] of invalid) {
    const source = scene(); mutate(source);
    assert.throws(() => validateScene(source), TypeError, name);
  }
});

test('direct input supports all eight grid directions without changing click-path diagonal policy', () => {
  const source = scene(); source.links = []; source.entities[0]!.c = 2; source.entities[0]!.r = 2;
  const model = new WorldModel(source);
  for (let c = -1; c <= 1; c++) for (let r = -1; r <= 1; r++) {
    if (c === 0 && r === 0) continue;
    assert.deepEqual(model.nextStep('hero', { c: c * 3, r: r * 3 }), { c: 2 + c, r: 2 + r });
  }
  assert.equal(model.canMove('hero', { c: 2, r: 2 }, { c: 3, r: 3 }), false);
  assert.equal(model.canMove('hero', { c: 2, r: 2 }, { c: 3, r: 3 }, true), true);
  const path = assertRoute(model, { c: 3, r: 3 });
  assert.equal(path.length, 2);
  assert.equal(model.serialize().diagonal, false);
  assert.deepEqual(model.entity('hero'), source.entities[0]);
});

test('direct input stops at obstacles without pathfinding detours or corner cutting', () => {
  const source = scene(); source.links = [];
  const model = new WorldModel(source);
  model.add({ id: 'wall', type: 'wall', c: 2, r: 1 });
  assert.equal(model.nextStep('hero', { c: 1, r: 0 }), null);
  assert.equal(model.nextStep('hero', { c: 1, r: 1 }), null);
  assertRoute(model, { c: 3, r: 1 });
  model.remove('wall');
  model.add({ id: 'other-side', type: 'wall', c: 1, r: 2 });
  assert.equal(model.nextStep('hero', { c: 1, r: 1 }), null);
  model.remove('other-side');
  assert.deepEqual(model.nextStep('hero', { c: 1, r: 1 }), { c: 2, r: 2 });
  model.setPosition('hero', { c: 0, r: 0 });
  assert.equal(model.nextStep('hero', { c: -1, r: 0 }), null);
  assert.equal(model.nextStep('hero', { c: 0, r: -1 }), null);
});

test('direct input prioritizes an available stair and respects blocked landings', () => {
  const model = new WorldModel(scene());
  assert.deepEqual(model.nextStep('hero', { c: 1, r: 0 }), { c: 2, r: 1, level: 'upper' });
  model.add({ id: 'landing-wall', type: 'wall', c: 2, r: 1, level: 'upper' });
  assert.deepEqual(model.nextStep('hero', { c: 1, r: 0 }), { c: 2, r: 1 });
  model.remove('landing-wall');
  model.setPosition('hero', { c: 2, r: 1, level: 'upper' });
  assert.deepEqual(model.nextStep('hero', { c: -1, r: 0 }), { c: 1, r: 1 });
});

test('direct input rejects invalid vectors and elevation barriers including diagonal side cells', () => {
  const source = scene(); source.links = []; source.map[1]![2] = 'raised';
  const model = new WorldModel(source);
  assert.equal(model.nextStep('hero', { c: 1, r: 0 }), null);
  assert.equal(model.nextStep('hero', { c: 1, r: 1 }), null);
  for (const vector of [{ c: 0, r: 0 }, { c: NaN, r: 0 }, { c: 1, r: Infinity }]) assert.equal(model.nextStep('hero', vector), null);
  assert.equal(model.nextStep('missing', { c: 1, r: 0 }), null);
  source.maxStepHeight = 8;
  assert.deepEqual(new WorldModel(source).nextStep('hero', { c: 1, r: 1 }), { c: 2, r: 2 });
});
