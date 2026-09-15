import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, writeFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { createHash } from 'node:crypto';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { checkScaleBinding, checkFiles } from '../scripts/check-scale-binding.mjs';

const script = fileURLToPath(new URL('../scripts/check-scale-binding.mjs', import.meta.url));
const atlasBytes = Buffer.from('calibrated atlas fixture');
const atlasHash = createHash('sha256').update(atlasBytes).digest('hex');
const hashes = { atlas: atlasHash };
const clone = value => structuredClone(value);

const asset = (id, kind, frame, anchor, width, heights) => ({
  id,
  kind,
  image: './atlas.png',
  sha256: atlasHash,
  frame,
  anchor,
  render: { width },
  footprint: { columns: 1, rows: 1 },
  groundPoints: [],
  heights,
  allowedOverhang: '',
});

function contract() {
  return {
    version: 1,
    pack: 'binding fixture',
    projection: { tileWidth: 80, tileHeight: 40, heightPixelsPerUnit: 40 },
    tolerances: { groundErrorPx: 1, heightErrorPx: 2 },
    heightReferences: { standing: 1.8, seat: 0.45 },
    assets: [
      asset('terrain', 'terrain', { x: 0, y: 0, width: 80, height: 40 }, { x: 0.5, y: 0.5 }, 80, []),
      asset('actor-idle', 'actor', { x: 80, y: 0, width: 40, height: 80 }, { x: 0.5, y: 0.9 }, 40,
        [{ reference: 'standing', base: { x: 20, y: 72 }, top: { x: 20, y: 0 } }]),
      asset('chair', 'prop', { x: 120, y: 0, width: 80, height: 80 }, { x: 0.5, y: 0.75 }, 80,
        [{ reference: 'seat', base: { x: 40, y: 60 }, top: { x: 40, y: 42 } }]),
    ],
  };
}

function scene() {
  return {
    version: 1,
    name: 'binding fixture',
    tileWidth: 80,
    tileHeight: 40,
    assets: {
      images: { atlas: { url: '/art/atlas.png' } },
      textures: {
        grass: { image: 'atlas', frame: { x: 0, y: 0, width: 80, height: 40 }, anchor: { x: 0.5, y: 0.5 } },
        'actor-0': { image: 'atlas', frame: { x: 80, y: 0, width: 40, height: 80 }, anchor: { x: 0.5, y: 0.9 } },
        'actor-1': { image: 'atlas', frame: { x: 80, y: 0, width: 40, height: 80 }, anchor: { x: 0.5, y: 0.9 } },
        chair: { image: 'atlas', frame: { x: 120, y: 0, width: 80, height: 80 }, anchor: { x: 0.5, y: 0.75 } },
      },
      animations: { idle: { frames: ['actor-0', 'actor-1'], fps: 8, loop: true } },
    },
    map: [['grass']],
    tiles: { grass: { color: 0x6a8f4f, texture: 'grass' } },
    entityTypes: {
      traveler: { visual: { kind: 'sprite', animation: 'idle', width: 40 }, bodyHeight: 72 },
      chair: { visual: { kind: 'sprite', texture: 'chair', width: 80 }, blocking: true, bodyHeight: 18 },
      sparkle: { visual: { kind: 'sprite', texture: 'chair', width: 80 } },
    },
    entities: [],
  };
}

function plan() {
  return {
    version: 1,
    pairings: [
      { asset: 'terrain', tile: 'grass' },
      { asset: 'actor-idle', entityType: 'traveler' },
      { asset: 'chair', entityType: 'chair' },
    ],
    images: { atlas: './atlas.png' },
    exempt: { entityTypes: { sparkle: 'decorative particle without ground contact' }, tiles: {} },
  };
}

const run = (mutate = () => {}) => {
  const parts = { contract: contract(), scene: scene(), plan: plan() };
  mutate(parts);
  return checkScaleBinding(parts.contract, parts.scene, parts.plan, hashes);
};
const failed = result => result.failures.join(' | ');

test('a scene that renders the calibrated values passes without open items', () => {
  const result = run();
  assert.equal(result.pass, true, failed(result));
  assert.deepEqual(result.failures, []);
  assert.deepEqual(result.unverified, []);
  assert.ok(result.results.length > 10);
  assert.ok(result.results.every(entry => entry.pass));
});

test('a body height that contradicts the shared world scale fails', () => {
  const result = run(parts => { parts.scene.entityTypes.traveler.bodyHeight = 96; });
  assert.equal(result.pass, false);
  assert.match(failed(result), /traveler: bodyHeight 96px matches standing \(72px\) within 2px/);

  assert.equal(run(parts => { parts.scene.entityTypes.traveler.bodyHeight = 73.5; }).pass, true);
});

test('an oversized render scale fails even when the crop and anchor are correct', () => {
  const result = run(parts => { parts.scene.entityTypes.traveler.visual.width = 96; });
  assert.equal(result.pass, false);
  assert.equal(result.failures.length, 2);
  assert.match(failed(result), /effective render scale 2\.4000 matches the calibrated 1/);
});

test('an effective anchor that differs from the calibrated anchor fails', () => {
  const result = run(parts => { parts.scene.entityTypes.chair.visual.anchor = { x: 0.5, y: 1 }; });
  assert.equal(result.pass, false);
  assert.match(failed(result), /chair\/chair: effective anchor/);
});

test('every frame of a clip is compared, not only the first', () => {
  const result = run(parts => {
    parts.scene.assets.textures['actor-1'].frame = { x: 80, y: 0, width: 32, height: 80 };
  });
  assert.equal(result.pass, false);
  assert.match(failed(result), /traveler\/actor-1: scene crop matches the calibrated frame/);
  assert.ok(!failed(result).includes('actor-0'));
});

test('uncalibrated sprites and tiles are reported unless they are named as exempt', () => {
  const sprite = run(parts => { parts.plan.exempt.entityTypes = {}; });
  assert.equal(sprite.pass, false);
  assert.match(failed(sprite), /coverage: sprite entity type "sparkle"/);

  const tile = run(parts => {
    parts.scene.tiles.stone = { color: 0x888888, texture: 'chair' };
  });
  assert.equal(tile.pass, false);
  assert.match(failed(tile), /coverage: textured tile "stone"/);

  assert.equal(run(parts => {
    parts.scene.tiles.stone = { color: 0x888888, texture: 'chair' };
    parts.plan.exempt.tiles = { stone: 'debug overlay, never rendered in play' };
  }).pass, true);
});

test('leaving art uncalibrated requires a stated reason that stays visible', () => {
  const base = run();
  assert.deepEqual(base.exceptions, ['exempt entityType "sparkle": decorative particle without ground contact']);

  const bare = run(parts => { parts.plan.exempt.entityTypes = ['sparkle']; });
  assert.equal(bare.pass, false);
  assert.match(failed(bare), /plan\.exempt\.entityTypes must map each name to a stated reason/);

  const silent = run(parts => { parts.plan.exempt.entityTypes = { sparkle: '  ' }; });
  assert.equal(silent.pass, false);
  assert.match(failed(silent), /plan\.exempt\.entityTypes\.sparkle must state why it stays uncalibrated/);
  assert.match(failed(silent), /coverage: sprite entity type "sparkle"/);
});

test('a deliberate collider deviation is recorded as a stated exception, not a failure', () => {
  const conservative = run(parts => {
    parts.scene.entityTypes.chair.bodyHeight = 64;
    parts.plan.pairings[2].deliberateBodyHeight = 'full-height blocker so the player cannot jump through the back rest';
  });
  assert.equal(conservative.pass, true, failed(conservative));
  assert.match(conservative.exceptions.join(' '),
    /chair: bodyHeight 64px deliberately deviates from seat \(18px\) — full-height blocker/);

  const unexplained = run(parts => {
    parts.scene.entityTypes.chair.bodyHeight = 64;
    parts.plan.pairings[2].deliberateBodyHeight = '';
  });
  assert.equal(unexplained.pass, false);
  assert.match(failed(unexplained), /deliberateBodyHeight must state why the collider deviates from seat/);

  const missing = run(parts => {
    delete parts.scene.entityTypes.chair.bodyHeight;
    parts.plan.pairings[2].deliberateBodyHeight = 'conservative blocker';
  });
  assert.equal(missing.pass, false);
  assert.match(failed(missing), /blocking entity requires an explicit bodyHeight/);
});

test('the scene image must be the file the contract measured', () => {
  const other = checkScaleBinding(contract(), scene(), plan(), { atlas: 'a'.repeat(64) });
  assert.equal(other.pass, false);
  assert.match(failed(other), /is the calibrated file/);

  const undeclared = run(parts => { parts.plan.images = {}; });
  assert.equal(undeclared.pass, false);
  assert.match(failed(undeclared), /declare the host file for scene image "atlas"/);

  const waived = run(parts => { parts.plan.images = { atlas: null }; });
  assert.equal(waived.pass, true);
  assert.equal(waived.unverified.length, 4);
  assert.match(waived.unverified[0], /declared unresolvable/);
});

test('projection and footprint disagreements are reported separately', () => {
  const projection = run(parts => { parts.scene.tileWidth = 64; });
  assert.match(failed(projection), /projection: tileWidth 64 matches contract 80/);

  const elevation = run(parts => { parts.scene.tileHeight = 48; });
  assert.match(failed(elevation), /projection: tileHeight 48 matches contract 40/);

  const footprint = run(parts => { parts.scene.entityTypes.chair.columns = 2; });
  assert.match(failed(footprint), /chair: grid footprint/);

  const offset = run(parts => { parts.scene.entityTypes.chair.visual.offset = { x: 4, y: 0 }; });
  assert.match(failed(offset), /chair: render offset/);
});

test('a blocking entity needs an explicit body height and a decorative one stays open', () => {
  const blocking = run(parts => { delete parts.scene.entityTypes.chair.bodyHeight; });
  assert.equal(blocking.pass, false);
  assert.match(failed(blocking), /chair: blocking entity requires an explicit bodyHeight of 18px/);

  const decorative = run(parts => {
    delete parts.scene.entityTypes.chair.bodyHeight;
    delete parts.scene.entityTypes.chair.blocking;
  });
  assert.equal(decorative.pass, true);
  assert.match(decorative.unverified.join(' '), /nonblocking entity declares no bodyHeight; 18px stays unchecked/);
});

test('an ambiguous or missing height reference is not silently skipped', () => {
  const ambiguous = run(parts => {
    parts.contract.assets[1].heights.push({ reference: 'seat', base: { x: 20, y: 72 }, top: { x: 20, y: 54 } });
  });
  assert.equal(ambiguous.pass, false);
  assert.match(failed(ambiguous), /declare bodyHeightReference; the asset names 2 height references/);

  assert.equal(run(parts => {
    parts.contract.assets[1].heights.push({ reference: 'seat', base: { x: 20, y: 72 }, top: { x: 20, y: 54 } });
    parts.plan.pairings[1].bodyHeightReference = 'standing';
  }).pass, true);

  const unnamed = run(parts => {
    parts.contract.assets[2].heights = [];
    delete parts.scene.entityTypes.chair.bodyHeight;
  });
  assert.match(unnamed.unverified.join(' '), /asset declares no height reference/);

  const unknown = run(parts => { parts.plan.pairings[1].bodyHeightReference = 'crouching'; });
  assert.match(failed(unknown), /heightReferences has no entry "crouching"/);
});

test('calibrated art that the runtime cannot reproduce uniformly fails', () => {
  const result = run(parts => { parts.contract.assets[2].render.height = 40; });
  assert.equal(result.pass, false);
  assert.match(failed(result), /calibrated scaling is uniform and representable by the runtime/);
});

test('terrain is bound to the actual tile size', () => {
  const result = run(parts => { parts.contract.assets[0].render.width = 64; });
  assert.equal(result.pass, false);
  assert.match(failed(result), /grass: calibrated render width matches the scene tile width/);
});

test('an unusable pairing or plan is rejected instead of silently passing', () => {
  assert.throws(() => run(parts => { parts.plan.version = 2; }), /version 1 and a pairings array/);
  assert.throws(() => run(parts => { delete parts.plan.pairings; }), /version 1 and a pairings array/);
  assert.throws(() => run(parts => { delete parts.contract.projection; }), /projection, heightReferences and assets/);
  assert.throws(() => run(parts => { delete parts.scene.entityTypes; }), /entityTypes and tiles/);

  assert.match(failed(run(parts => { parts.plan.pairings[1].asset = 'ghost'; })), /contract has no asset "ghost"/);
  assert.match(failed(run(parts => { parts.plan.pairings[1].tile = 'grass'; })), /exactly one entityType or tile/);
  assert.match(failed(run(parts => { parts.plan.pairings[1].entityType = 'ghost'; })), /scene has no entity type/);
  assert.match(failed(run(parts => { parts.scene.entityTypes.traveler.visual = { kind: 'box' }; })), /requires a sprite visual, found "box"/);
});

test('the file entry point hashes declared images and the CLI signals failure', async t => {
  const directory = await mkdtemp(path.join(tmpdir(), 'scale-binding-'));
  t.after(() => rm(directory, { recursive: true, force: true }));
  const files = {
    contract: path.join(directory, 'art-contract.json'),
    scene: path.join(directory, 'scene.json'),
    plan: path.join(directory, 'binding-plan.json'),
  };
  await writeFile(path.join(directory, 'atlas.png'), atlasBytes);
  await writeFile(files.contract, JSON.stringify(contract()));
  await writeFile(files.scene, JSON.stringify(scene()));
  await writeFile(files.plan, JSON.stringify(plan()));

  const accepted = await checkFiles(files.contract, files.scene, files.plan);
  assert.equal(accepted.pass, true, failed(accepted));

  const passing = spawnSync(process.execPath, [script, files.contract, files.scene, files.plan], { encoding: 'utf8' });
  assert.equal(passing.status, 0, passing.stderr);
  assert.equal(JSON.parse(passing.stdout).pass, true);

  await writeFile(path.join(directory, 'atlas.png'), Buffer.from('a different atlas'));
  const rejected = spawnSync(process.execPath, [script, files.contract, files.scene, files.plan], { encoding: 'utf8' });
  assert.equal(rejected.status, 1);
  assert.match(JSON.parse(rejected.stdout).failures.join(' '), /is the calibrated file/);

  const usage = spawnSync(process.execPath, [script, files.contract], { encoding: 'utf8' });
  assert.notEqual(usage.status, 0);
  assert.match(usage.stderr, /Usage: node/);
});
