import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, writeFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { checkAssembly } from '../scripts/check-assembly.mjs';

const script = fileURLToPath(new URL('../scripts/check-assembly.mjs', import.meta.url));
const row = tile => Array.from({ length: 6 }, (_, c) => (c === 4 ? 'water' : tile));

function scene() {
  return {
    version: 2,
    name: 'assembly fixture',
    tileWidth: 64,
    tileHeight: 32,
    assets: {
      images: { atlas: { url: '/art/atlas.png', sampling: 'nearest' } },
      textures: {
        'fountain-0': { image: 'atlas', frame: { x: 0, y: 0, width: 256, height: 128 } },
        'fountain-1': { image: 'atlas', frame: { x: 256, y: 0, width: 256, height: 128 } },
        stray: { image: 'atlas', frame: { x: 0, y: 128, width: 32, height: 32 } },
        frameless: { image: 'atlas' },
      },
      animations: { 'fountain-loop': { frames: ['fountain-0', 'fountain-1'], fps: 8, loop: true } },
    },
    map: Array.from({ length: 6 }, () => row('grass')),
    tiles: {
      grass: { color: 0x6a8f4f },
      water: { color: 0x2f6f9f, walkable: false },
      deck: { color: 0x8a6a4f },
    },
    entityTypes: {
      traveler: { visual: { kind: 'actor' }, bodyHeight: 48 },
      fountain: {
        visual: { kind: 'sprite', animation: 'fountain-loop', anchor: { x: 0.25, y: 0.75 }, width: 256 },
        blocking: true,
        columns: 2,
        rows: 2,
        bodyHeight: 40,
      },
    },
    entities: [
      { id: 'traveler', type: 'traveler', c: 0, r: 0 },
      { id: 'fountain', type: 'fountain', c: 1, r: 1 },
    ],
    controlledId: 'traveler',
    levels: [{
      id: 'bridge',
      name: 'Bridge',
      height: 48,
      map: Array.from({ length: 6 }, (_, r) => Array.from({ length: 6 }, (_, c) => (r === 0 && c === 3 ? 'deck' : null))),
    }],
    links: [],
  };
}

// Anchor 0.25/0.75 on a 256x128 frame puts the entity origin at frame pixel (64,96)
// with scale 1, so each source point below is its projected grid offset plus that origin.
const contacts = [
  { texture: 'fountain-0', source: { x: 32, y: 96 }, grid: { c: -0.5, r: -0.5 } },
  { texture: 'fountain-0', source: { x: 96, y: 64 }, grid: { c: 1.5, r: -0.5 } },
  { texture: 'fountain-1', source: { x: 160, y: 96 }, grid: { c: 1.5, r: 1.5 } },
  { texture: 'fountain-1', source: { x: 96, y: 128 }, grid: { c: -0.5, r: 1.5 } },
];
const cell = (c, r, level) => (level ? { c, r, level } : { c, r });

function plan(overrides = {}) {
  return {
    version: 1,
    actor: 'traveler',
    tolerancePx: 0.01,
    placements: [{ entity: 'fountain', origin: cell(1, 1), contacts }],
    blocked: [cell(1, 1), cell(2, 2), cell(4, 3)],
    open: [cell(0, 1), cell(3, 3)],
    solidHeights: [{ id: 'basin', cell: cell(1, 1), minHeight: 40 }],
    routes: [
      { id: 'around the fountain', from: cell(0, 0), to: cell(3, 3), reachable: true },
      { id: 'across the water', from: cell(0, 0), to: cell(5, 5), reachable: false },
    ],
    paths: [{ id: 'west bank', points: [cell(0, 0), cell(0, 1), cell(0, 2)] }],
    clearances: [{ id: 'deck headroom', cell: cell(3, 0), height: 40 }],
    ...overrides,
  };
}

const failed = result => result.failures.join(' | ');

test('a correct assembly passes every declared expectation', () => {
  const declared = plan();
  const result = checkAssembly(scene(), declared);
  assert.equal(result.pass, true, failed(result));
  assert.deepEqual(result.failures, []);
  assert.match(result.limits, /Does not inspect pixels/);

  // Every contact yields both a binding and a projection result; nothing may be skipped silently.
  const expected = 1 + declared.placements[0].contacts.length * 2
    + [declared.blocked, declared.open, declared.solidHeights, declared.routes, declared.paths, declared.clearances]
      .reduce((total, group) => total + group.length, 0);
  assert.equal(result.results.length, expected);
  assert.ok(result.results.every(entry => entry.pass));
});

test('contact error is accepted inside the declared tolerance and rejected outside it', () => {
  const drift = offset => ({
    placements: [{
      entity: 'fountain',
      origin: cell(1, 1),
      contacts: contacts.map((contact, index) => (index === 0
        ? { ...contact, source: { x: contact.source.x + offset, y: contact.source.y } }
        : contact)),
    }],
  });
  assert.equal(checkAssembly(scene(), plan({ ...drift(0.5), tolerancePx: 1 })).pass, true);
  const strict = checkAssembly(scene(), plan({ ...drift(2), tolerancePx: 1 }));
  assert.equal(strict.pass, false);
  assert.equal(strict.failures.length, 1);
  assert.match(strict.failures[0], /contact error 2\.000px <= 1px/);
});

test('render offset and scale participate in the contact comparison', () => {
  const shifted = scene();
  shifted.entityTypes.fountain.visual.offset = { x: 7, y: -3 };
  const result = checkAssembly(shifted, plan());
  assert.equal(result.pass, false);
  assert.equal(result.failures.length, contacts.length);

  const halved = scene();
  halved.entityTypes.fountain.visual.width = 128;
  assert.equal(checkAssembly(halved, plan()).pass, false);
});

test('a texture outside the bound clip fails even when its geometry matches', () => {
  const result = checkAssembly(scene(), plan({
    placements: [{
      entity: 'fountain',
      origin: cell(1, 1),
      contacts: [{ texture: 'stray', source: { x: 8, y: 24 }, grid: { c: -0.5, r: -0.5 } }],
    }],
  }));
  assert.equal(result.pass, false);
  assert.match(failed(result), /stray: bound to actual visual/);
});

test('a texture without an explicit source frame cannot be measured', () => {
  const result = checkAssembly(scene(), plan({
    placements: [{
      entity: 'fountain',
      origin: cell(1, 1),
      contacts: [{ texture: 'frameless', source: { x: 0, y: 0 }, grid: { c: 0, r: 0 } }],
    }],
  }));
  assert.equal(result.pass, false);
  assert.deepEqual(result.failures, ['fountain/frameless: explicit source frame required']);
});

test('a wrong declared origin and a missing entity are reported separately', () => {
  const moved = checkAssembly(scene(), plan({
    placements: [{ entity: 'fountain', origin: cell(0, 0), contacts: [] }],
  }));
  assert.deepEqual(moved.failures, ['fountain: declared origin']);

  const absent = checkAssembly(scene(), plan({
    placements: [{ entity: 'ghost', origin: cell(0, 0), contacts: [] }],
  }));
  assert.deepEqual(absent.failures, ['ghost: missing entity']);
});

test('blocked and open expectations follow actual occupancy, not the image rectangle', () => {
  const result = checkAssembly(scene(), plan({
    blocked: [cell(0, 1)],
    open: [cell(2, 1)],
  }));
  assert.equal(result.pass, false);
  assert.equal(result.failures.length, 2);
  assert.match(failed(result), /blocked 0,1@ground/);
  assert.match(failed(result), /open 2,1@ground/);
});

test('a solid height needs an explicit blocking body that covers it', () => {
  assert.equal(checkAssembly(scene(), plan({
    solidHeights: [{ id: 'basin', cell: cell(2, 2), minHeight: 40 }],
  })).pass, true);

  const tall = checkAssembly(scene(), plan({
    solidHeights: [{ id: 'centrepiece', cell: cell(1, 1), minHeight: 48 }],
  }));
  assert.equal(tall.pass, false);
  assert.match(failed(tall), /centrepiece: explicit solid body covers 48px/);

  const decorative = scene();
  decorative.entityTypes.fountain.blocking = false;
  assert.equal(checkAssembly(decorative, plan({
    blocked: [],
    open: [cell(1, 1)],
    solidHeights: [{ id: 'basin', cell: cell(1, 1), minHeight: 40 }],
  })).pass, false);
});

test('routes are compared against the declared reachability in both directions', () => {
  const wrong = checkAssembly(scene(), plan({
    routes: [{ id: 'across the water', from: cell(0, 0), to: cell(5, 5), reachable: true }],
  }));
  assert.equal(wrong.pass, false);
  assert.match(failed(wrong), /across the water: reachable=true/);

  const blockedOrigin = checkAssembly(scene(), plan({
    routes: [{ id: 'from the water', from: cell(4, 0), to: cell(0, 0), reachable: true }],
  }));
  assert.match(failed(blockedOrigin), /from the water: route origin is blocked/);
});

test('an exact path rejects a skipped segment that mere reachability would allow', () => {
  const detour = checkAssembly(scene(), plan({
    paths: [{ id: 'skips a cell', points: [cell(0, 0), cell(0, 2)] }],
  }));
  assert.equal(detour.pass, false);
  assert.match(failed(detour), /skips a cell: every exact walking segment/);

  assert.equal(checkAssembly(scene(), plan({
    paths: [{ id: 'through the fountain', points: [cell(1, 0), cell(1, 1), cell(1, 2)] }],
  })).pass, false);
});

test('clearance uses the actual slab geometry above the cell', () => {
  const tight = checkAssembly(scene(), plan({
    clearances: [{ id: 'deck headroom', cell: cell(3, 0), height: 41 }],
  }));
  assert.equal(tight.pass, false);
  assert.match(failed(tight), /deck headroom: floor-slab clearance/);

  assert.equal(checkAssembly(scene(), plan({
    clearances: [{ id: 'open sky', cell: cell(0, 5), height: 4096 }],
  })).pass, true);
});

test('an unusable plan is rejected before any expectation is checked', () => {
  const cases = [
    [{ version: 2 }, /version 1 and an existing actor/],
    [{ actor: 'ghost' }, /version 1 and an existing actor/],
    [{ tolerancePx: -1 }, /Invalid contact tolerance/],
    [{ placements: 'all' }, /placements must be an array/],
    [{ solidHeights: [{ id: 'basin', cell: cell(1, 1), minHeight: 0 }] }, /Solid height must be positive/],
    [{ paths: [{ id: 'single', points: [cell(0, 0)] }] }, /at least two cells/],
    [{ clearances: [{ id: 'void', cell: cell(99, 99), height: 40 }] }, /supported cell and positive body height/],
    [{ clearances: [{ id: 'flat', cell: cell(3, 0), height: 0 }] }, /supported cell and positive body height/],
  ];
  for (const [overrides, message] of cases) {
    assert.throws(() => checkAssembly(scene(), plan(overrides)), message);
  }
});

test('the CLI prints a JSON report and signals failure through its exit code', async t => {
  const directory = await mkdtemp(path.join(tmpdir(), 'assembly-'));
  t.after(() => rm(directory, { recursive: true, force: true }));
  const scenePath = path.join(directory, 'scene.json');
  const planPath = path.join(directory, 'assembly-plan.json');
  await writeFile(scenePath, JSON.stringify(scene()));

  const run = async plans => {
    await writeFile(planPath, JSON.stringify(plans));
    return spawnSync(process.execPath, ['--experimental-strip-types', script, scenePath, planPath], { encoding: 'utf8' });
  };

  const accepted = await run(plan());
  assert.equal(accepted.status, 0, accepted.stderr);
  assert.equal(JSON.parse(accepted.stdout).pass, true);

  const rejected = await run(plan({ open: [cell(1, 1)] }));
  assert.equal(rejected.status, 1);
  assert.deepEqual(JSON.parse(rejected.stdout).failures, ['open 1,1@ground']);

  const usage = spawnSync(process.execPath, ['--experimental-strip-types', script, scenePath], { encoding: 'utf8' });
  assert.notEqual(usage.status, 0);
  assert.match(usage.stderr, /Usage: node/);
});
