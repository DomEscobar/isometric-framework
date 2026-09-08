import assert from 'node:assert/strict';
import { test } from 'node:test';
import { project, unproject } from '../src/geometry.ts';
import { WorldModel } from '../src/model.ts';
import { findPath } from '../src/pathfinding.ts';
import { validateScene } from '../src/scene.ts';
import type { Cell, Scene } from '../src/types.ts';

function scene(): Scene {
  return {
    version: 1, name: 'Independent test world', tileWidth: 64, tileHeight: 32,
    map: Array.from({ length: 5 }, () => Array(5).fill('ground')),
    tiles: { ground: { color: 0x44aa66 }, water: { color: 0x2266bb, walkable: false }, raised: { color: 0x998844, elevation: 12 } },
    entityTypes: { player: { visual: { kind: 'actor' }, blocking: true }, wall: { visual: { kind: 'box' }, blocking: true }, large: { visual: { kind: 'box' }, blocking: true, columns: 2, rows: 2 } },
    entities: [{ id: 'hero', type: 'player', c: 0, r: 0, data: { stats: { health: 5 } } }], controlledId: 'hero',
  };
}

test('isometric orientation, elevation, and inverse projection retain grid coordinates', () => {
  assert.deepEqual(project({ c: 1, r: 0 }, 64, 32), { x: 32, y: -16 });
  assert.deepEqual(project({ c: 0, r: 1 }, 64, 32), { x: 32, y: 16 });
  assert.deepEqual(project({ c: 1, r: 1 }, 64, 32, 12), { x: 64, y: -12 });
  for (const [width, height] of [[64, 32], [90, 26], [17, 13]]) {
    for (let c = -8; c <= 8; c++) for (let r = -8; r <= 8; r++) {
      assert.deepEqual(unproject(project({ c, r }, width!, height!), width!, height!), { c, r });
    }
  }
});

test('paths exclude the start, include the goal, and take an optimal obstacle detour', () => {
  const model = new WorldModel(scene());
  for (let r = 0; r < 4; r++) model.add({ id: `wall-${r}`, type: 'wall', c: 2, r });
  const path = model.path('hero', { c: 4, r: 0 });
  assert.ok(path);
  assert.equal(path.length, 12);
  assert.deepEqual(path.at(-1), { c: 4, r: 0 });
  let previous = { c: 0, r: 0 };
  for (const cell of path) {
    assert.equal(Math.abs(cell.c - previous.c) + Math.abs(cell.r - previous.r), 1);
    assert.equal(model.canEnter(cell, 'hero'), true);
    previous = cell;
  }
  assert.deepEqual(model.path('hero', { c: 0, r: 0 }), []);
  assert.equal(model.path('unknown', { c: 1, r: 1 }), null);
  model.add({ id: 'close-gap', type: 'wall', c: 2, r: 4 });
  assert.equal(model.path('hero', { c: 4, r: 0 }), null);
  assert.equal(model.path('hero', { c: 2, r: 0 }), null);
});

test('pathfinding rejects invalid coordinates without querying an unbounded grid', () => {
  const enter = (cell: Cell) => cell.c >= 0 && cell.r >= 0 && cell.c < 3 && cell.r < 3;
  for (const bad of [-1, 0.5, NaN, Infinity, Number.MAX_SAFE_INTEGER + 1]) {
    assert.equal(findPath({ c: bad, r: 0 }, { c: 1, r: 1 }, enter, () => true), null);
    assert.equal(findPath({ c: 0, r: 0 }, { c: 1, r: bad }, enter, () => true), null);
  }
});

test('diagonal travel has shortest Euclidean step cost and cannot cut blocked corners', () => {
  const open = scene(); open.diagonal = true;
  const model = new WorldModel(open);
  assert.deepEqual(model.path('hero', { c: 4, r: 4 }), [1, 2, 3, 4].map(n => ({ c: n, r: n })));
  model.add({ id: 'right', type: 'wall', c: 1, r: 0 });
  model.add({ id: 'down', type: 'wall', c: 0, r: 1 });
  assert.equal(model.path('hero', { c: 1, r: 1 }), null);
  model.remove('down');
  const detour = model.path('hero', { c: 1, r: 1 });
  assert.deepEqual(detour, [{ c: 0, r: 1 }, { c: 1, r: 1 }]);
});

test('A* matches an independent exhaustive shortest-distance oracle on small obstructed maps', () => {
  // Fixed masks provide reproducible dead ends, corridors, and competing routes.
  for (const mask of [0, 0x0660, 0x1248, 0x6996, 0x55aa, 0x3330, 0x7ffe]) {
    for (const diagonal of [false, true]) {
      const allowed = (p: Cell) => p.c >= 0 && p.r >= 0 && p.c < 4 && p.r < 4 && ((mask >>> (p.r * 4 + p.c)) & 1) === 0;
      const vertices: Cell[] = [];
      for (let r = 0; r < 4; r++) for (let c = 0; c < 4; c++) if (allowed({ c, r })) vertices.push({ c, r });
      const distances = new Map<string, number>([['0,0', 0]]);
      // Bellman-Ford relaxation is deliberately separate from the A* implementation.
      for (let pass = 0; pass < vertices.length; pass++) {
        for (const a of vertices) for (const b of vertices) {
          const dx = Math.abs(a.c - b.c), dy = Math.abs(a.r - b.r);
          if (dx + dy === 0 || dx > 1 || dy > 1 || (!diagonal && dx + dy !== 1)) continue;
          if (dx && dy && (!allowed({ c: a.c, r: b.r }) || !allowed({ c: b.c, r: a.r }))) continue;
          const candidate = (distances.get(`${a.c},${a.r}`) ?? Infinity) + Math.hypot(dx, dy);
          const key = `${b.c},${b.r}`;
          if (candidate < (distances.get(key) ?? Infinity)) distances.set(key, candidate);
        }
      }
      const path = findPath({ c: 0, r: 0 }, { c: 3, r: 3 }, allowed, () => true, diagonal);
      const expected = distances.get('3,3') ?? Infinity;
      if (!Number.isFinite(expected)) assert.equal(path, null);
      else {
        assert.ok(path);
        let actual = 0, previous = { c: 0, r: 0 };
        for (const cell of path) { actual += Math.hypot(cell.c - previous.c, cell.r - previous.r); previous = cell; }
        assert.ok(Math.abs(actual - expected) < 1e-10, `mask=${mask}, diagonal=${diagonal}: ${actual} != ${expected}`);
      }
    }
  }
});

test('every cell of a moving entity footprint must fit and clear obstacles', () => {
  const input = scene(); input.entities[0]!.type = 'large';
  const model = new WorldModel(input);
  for (const cell of [{ c: 0, r: 0 }, { c: 1, r: 0 }, { c: 0, r: 1 }, { c: 1, r: 1 }]) assert.deepEqual(model.at(cell).map(e => e.id), ['hero']);
  assert.equal(model.path('hero', { c: 4, r: 0 }), null);
  assert.equal(model.path('hero', { c: 0, r: 4 }), null);
  model.add({ id: 'far-corner', type: 'wall', c: 3, r: 3 });
  assert.equal(model.path('hero', { c: 2, r: 2 }), null);
  assert.ok(model.path('hero', { c: 2, r: 0 }));
  assert.throws(() => model.setPosition('hero', { c: 4, r: 4 }), RangeError);
  assert.deepEqual(model.entity('hero') && { c: model.entity('hero')!.c, r: model.entity('hero')!.r }, { c: 0, r: 0 });
});

test('elevation limits apply to every footprint cell and diagonal side crossings', () => {
  const input = scene(); input.entities[0]!.type = 'large';
  input.map[1]![2] = 'raised';
  const strict = new WorldModel(input);
  assert.equal(strict.path('hero', { c: 1, r: 0 }), null);
  input.maxStepHeight = 12;
  assert.deepEqual(new WorldModel(input).path('hero', { c: 1, r: 0 }), [{ c: 1, r: 0 }]);
  const corner = scene(); corner.diagonal = true;
  corner.map[0]![1] = 'raised'; corner.map[1]![0] = 'raised';
  assert.equal(new WorldModel(corner).path('hero', { c: 1, r: 1 }), null);
});

test('removing and moving overlapping blockers preserves the remaining occupancy', () => {
  const model = new WorldModel(scene());
  model.add({ id: 'one', type: 'wall', c: 2, r: 2 });
  model.add({ id: 'two', type: 'wall', c: 2, r: 2 });
  assert.equal(model.remove('one'), true);
  assert.equal(model.remove('one'), false);
  assert.equal(model.canEnter({ c: 2, r: 2 }), false);
  assert.deepEqual(model.at({ c: 2, r: 2 }).map(e => e.id), ['two']);
  model.setPosition('two', { c: 3, r: 2 });
  assert.equal(model.canEnter({ c: 2, r: 2 }), true);
  assert.equal(model.canEnter({ c: 3, r: 2 }), false);
  model.remove('hero');
  assert.equal(model.serialize().controlledId, undefined);
});

test('scene inputs, all public snapshots, and separate models cannot mutate each other', () => {
  const input = scene(), first = new WorldModel(input), second = new WorldModel(input);
  input.map[0]![0] = 'water'; input.entities[0]!.c = 4;
  const snapshot = first.serialize(); snapshot.entities[0]!.c = 3; snapshot.map[0]![0] = 'water';
  const entity = first.entity('hero')!; (entity.data!.stats as { health: number }).health = -99;
  first.entities()[0]!.r = 4;
  first.at({ c: 0, r: 0 })[0]!.type = 'wall';
  first.tile({ c: 0, r: 0 })!.walkable = false;
  first.entityType('player')!.columns = 128;
  first.scene.tiles.ground!.elevation = 900;
  assert.deepEqual(first.serialize(), scene());
  first.setPosition('hero', { c: 2, r: 1 });
  assert.equal(second.entity('hero')!.c, 0);
  assert.equal(second.at({ c: 2, r: 1 }).length, 0);
  assert.equal(first.at({ c: 0, r: 0 }).length, 0);
});

test('invalid additions are atomic and control selection validates entity IDs', () => {
  const model = new WorldModel(scene()), before = model.serialize();
  assert.throws(() => model.add({ id: 'hero', type: 'wall', c: 1, r: 1 }), TypeError);
  assert.throws(() => model.add({ id: 'outside', type: 'large', c: 4, r: 4 }), TypeError);
  assert.deepEqual(model.serialize(), before);
  assert.throws(() => model.setControlled('missing'));
  assert.equal(model.serialize().controlledId, 'hero');
  model.setControlled(null);
  assert.equal(model.serialize().controlledId, undefined);
});

test('scene validation rejects malformed shape, references, numeric fields and visual definitions', () => {
  const changes: Array<(s: any) => void> = [
    s => s.version = 2, s => s.name = '', s => s.tileWidth = NaN, s => s.tileHeight = Infinity,
    s => s.tileWidth = 0, s => s.map = [], s => s.map[1] = ['ground'], s => s.map[0][0] = 'missing',
    s => s.tiles = [], s => s.tiles.ground.color = -1, s => s.tiles.ground.color = 1.5,
    s => s.tiles.ground.walkable = 'yes', s => s.tiles.ground.elevation = Infinity,
    s => s.entityTypes.player.rows = 0, s => s.entityTypes.player.columns = 1.5,
    s => s.entityTypes.player.visual.kind = 'unsupported', s => s.entityTypes.player.visual.kind = 'sprite',
    s => s.entityTypes.player.visual.frames = [], s => s.entityTypes.player.visual.frames = [42],
    s => s.entityTypes.player.visual.fps = 0, s => s.entityTypes.player.visual.scale = -1,
    s => s.entities.push({ ...s.entities[0] }), s => s.entities[0].id = '',
    s => s.entities[0].type = 'missing', s => s.entities[0].c = -1, s => s.entities[0].r = 0.2,
    s => { s.entities[0].type = 'large'; s.entities[0].c = 4; },
    s => s.controlledId = 'missing', s => s.diagonal = 1, s => s.maxStepHeight = -1,
    s => s.entities[0].data = [], s => s.entities[0].data = null,
  ];
  for (const mutate of changes) {
    const input = scene(); mutate(input);
    assert.throws(() => validateScene(input), TypeError, String(mutate));
  }
  for (const invalid of [null, undefined, [], 'scene', 1]) assert.throws(() => validateScene(invalid), TypeError);
});

test('scene data must round-trip losslessly as JSON and cannot contain cycles or special objects', () => {
  const circular: Record<string, unknown> = {}; circular.self = circular;
  for (const value of [undefined, NaN, Infinity, 1n, () => 1, Symbol('x'), new Date(), new Map(), circular]) {
    const input = scene(); input.entities[0]!.data = { value };
    assert.throws(() => validateScene(input), TypeError);
  }
  const input = scene(); input.entities[0]!.data = { nested: [{ truth: true, absent: null, value: -1.25 }], text: 'hello' };
  assert.deepEqual(validateScene(JSON.parse(JSON.stringify(input))), input);
  input.entities[0]!.data = { [Symbol('hidden')]: 1 };
  assert.throws(() => validateScene(input), TypeError);
});

test('prototype property names work only as explicit definitions and do not pollute objects', () => {
  for (const id of ['__proto__', 'constructor', 'toString']) {
    const input = scene(); input.map[0]![0] = id;
    assert.throws(() => validateScene(input), TypeError);
    input.tiles = Object.fromEntries([...Object.entries(input.tiles), [id, { color: 1 }]]);
    input.entityTypes = Object.fromEntries([...Object.entries(input.entityTypes), [id, { visual: { kind: 'box' }, blocking: true }]]);
    input.entities.push({ id, type: id, c: 2, r: 2 });
    const model = new WorldModel(JSON.parse(JSON.stringify(input)));
    assert.equal(model.tile({ c: 0, r: 0 })!.color, 1);
    assert.equal(model.canEnter({ c: 2, r: 2 }), false);
    assert.equal(model.remove(id), true);
    assert.equal(model.canEnter({ c: 2, r: 2 }), true);
  }
  const withPrototypeKey = scene();
  withPrototypeKey.entities[0]!.data = JSON.parse('{"__proto__":{"polluted":true},"constructor":{"retained":true}}');
  const preserved = validateScene(withPrototypeKey).entities[0]!.data!;
  assert.equal(Object.hasOwn(preserved, '__proto__'), true);
  assert.deepEqual(preserved.__proto__, { polluted: true });
  assert.equal(({} as Record<string, unknown>).polluted, undefined);
  const input = scene(); input.entities[0]!.type = 'constructor';
  assert.throws(() => validateScene(input), TypeError);
});
