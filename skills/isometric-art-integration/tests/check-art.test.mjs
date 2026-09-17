import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, readFile, writeFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { createHash } from 'node:crypto';
import { deflateSync } from 'node:zlib';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { checkContract, checkFile } from '../scripts/check-art.mjs';

function crc32(bytes) {
  let crc = 0xffffffff;
  for (const byte of bytes) {
    crc ^= byte;
    for (let bit = 0; bit < 8; bit++) crc = (crc >>> 1) ^ ((crc & 1) ? 0xedb88320 : 0);
  }
  return (crc ^ 0xffffffff) >>> 0;
}
function chunk(type, bytes) {
  const buffer = Buffer.alloc(bytes.length + 12);
  buffer.writeUInt32BE(bytes.length, 0);
  buffer.write(type, 4, 'ascii');
  bytes.copy(buffer, 8);
  buffer.writeUInt32BE(crc32(buffer.subarray(4, -4)), buffer.length - 4);
  return buffer;
}
/** Opaque test art: the checker now measures the decoded silhouette, not just metadata. */
function png(width = 128, height = 128, opaqueColumns = width) {
  const header = Buffer.alloc(13);
  header.writeUInt32BE(width, 0); header.writeUInt32BE(height, 4);
  header[8] = 8; header[9] = 6;
  const stride = width * 4;
  const raw = Buffer.alloc(height * (stride + 1));
  for (let row = 0; row < height; row++) {
    for (let column = 0; column < opaqueColumns; column++) {
      raw.fill(255, row * (stride + 1) + 1 + column * 4, row * (stride + 1) + 1 + column * 4 + 4);
    }
  }
  return Buffer.concat([
    Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]), chunk('IHDR', header),
    chunk('IDAT', deflateSync(raw)), chunk('IEND', Buffer.alloc(0)),
  ]);
}
const bytes = png();
const hash = createHash('sha256').update(bytes).digest('hex');
test('starter geometry works after supplying its documented atlas and real hash', async (t) => {
  const directory = await fixture(t);
  const candidate = JSON.parse(await readFile(new URL('../references/starter-contract.json', import.meta.url), 'utf8'));
  const atlas = png(200, 80);
  await writeFile(path.join(directory, 'atlas.png'), atlas);
  for (const asset of candidate.assets) asset.sha256 = createHash('sha256').update(atlas).digest('hex');
  const report = await checkContract(candidate, directory);
  assert.equal(report.passed, true, JSON.stringify(report.errors));
});
const ground = (x, y, c, r) => ({ source: { x, y }, grid: { c, r } });
function contract() {
  const base = {
    image: 'atlas.png', sha256: hash, frame: { x: 0, y: 0, width: 64, height: 32 },
    anchor: { x: 0.5, y: 0.5 }, render: { width: 64 }, footprint: { columns: 1, rows: 1 },
    heights: [], allowedOverhang: '',
  };
  return {
    version: 1, pack: 'Synthetic calibration fixture',
    projection: { tileWidth: 64, tileHeight: 32, heightPixelsPerUnit: 32 },
    tolerances: { groundErrorPx: 0.01, heightErrorPx: 0.01 }, heightReferences: { adult: 2 },
    assets: [
      { ...structuredClone(base), id: 'tile', kind: 'terrain', groundPoints: [ground(0, 16, -0.5, -0.5), ground(32, 32, -0.5, 0.5), ground(32, 0, 0.5, -0.5), ground(64, 16, 0.5, 0.5)] },
      { ...structuredClone(base), id: 'table', kind: 'prop', frame: { x: 64, y: 0, width: 64, height: 64 }, anchor: { x: 0.5, y: 0.75 }, groundPoints: [ground(0, 48, -0.5, -0.5), ground(64, 48, 0.5, 0.5), ground(32, 32, 0.5, -0.5)] },
      { ...structuredClone(base), id: 'person', kind: 'actor', frame: { x: 0, y: 64, width: 32, height: 64 }, anchor: { x: 0.5, y: 1 }, render: { width: 32 }, groundPoints: [ground(16, 64, 0, 0)], heights: [{ reference: 'adult', base: { x: 16, y: 64 }, top: { x: 16, y: 0 } }] },
    ],
  };
}
async function fixture(t) {
  const directory = await mkdtemp(path.join(tmpdir(), 'art-calibration-'));
  t.after(() => rm(directory, { recursive: true, force: true }));
  await writeFile(path.join(directory, 'atlas.png'), bytes);
  return directory;
}
async function rejection(t, mutate, pattern) {
  const directory = await fixture(t);
  const candidate = contract();
  mutate(candidate);
  const report = await checkContract(candidate, directory);
  assert.equal(report.passed, false);
  assert.match(report.errors.map((e) => e.message).join('\n'), pattern);
  return report;
}

test('valid terrain, prop, and actor use frame-local atlas landmarks', async (t) => {
  const report = await checkContract(contract(), await fixture(t));
  assert.equal(report.passed, true, JSON.stringify(report.errors));
  assert.equal(report.scope, 'metadata-only');
  assert.equal(report.assets.length, 3);
  assert.equal(report.assets[1].imageWidth, 128);
  assert.equal(report.assets[2].scaleY, 1);
  assert.ok(path.isAbsolute(report.assets[0].imagePath));
});

test('terrain allows a nonuniform render height', async (t) => {
  const c = contract(); c.assets = [c.assets[0]];
  c.assets[0].frame.height = 64; c.assets[0].render.height = 32;
  for (const p of c.assets[0].groundPoints) p.source.y *= 2;
  const report = await checkContract(c, await fixture(t));
  assert.equal(report.passed, true, JSON.stringify(report.errors));
  assert.equal(report.assets[0].scaleY, 0.5);
});

test('camera projection is declared and need not be 2:1', async (t) => {
  const c = contract(); c.assets = [c.assets[0]]; c.projection.tileHeight = 40;
  c.assets[0].frame.height = 40;
  for (const p of c.assets[0].groundPoints) p.source.y *= 1.25;
  assert.equal((await checkContract(c, await fixture(t))).passed, true);
});

test('terrain camera mismatch fails and keeps drawable candidates', async (t) => {
  const report = await rejection(t, (c) => { c.assets[0].groundPoints[0].source.x = 6; }, /projection error/);
  assert.equal(report.assets.length, 3);
  assert.equal(report.errors[0].assetId, 'tile');
});

test('understated contacts cannot shrink artwork that overflows its footprint', async (t) => {
  const directory = await mkdtemp(path.join(tmpdir(), 'art-silhouette-'));
  t.after(() => rm(directory, { recursive: true, force: true }));
  const wall = png(152, 128);
  await writeFile(path.join(directory, 'atlas.png'), wall);
  const candidate = contract();
  candidate.projection = { tileWidth: 48, tileHeight: 24, heightPixelsPerUnit: 24 };
  candidate.tolerances = { groundErrorPx: 0.5, heightErrorPx: 1 };
  candidate.assets = [{
    id: 'stadtmauer', kind: 'prop', image: 'atlas.png',
    sha256: createHash('sha256').update(wall).digest('hex'),
    frame: { x: 0, y: 0, width: 152, height: 128 }, anchor: { x: 0.5, y: 1 },
    render: { width: 152 }, footprint: { columns: 1, rows: 1 }, heights: [], allowedOverhang: '',
    // Exact contacts across the middle tile only: every declared-metadata check is satisfied.
    groundPoints: [ground(64, 128, -0.25, -0.25), ground(88, 128, 0.25, 0.25), ground(76, 122, 0.25, -0.25)],
  }];
  const report = await checkContract(candidate, directory);
  assert.equal(report.passed, false);
  const messages = report.errors.map((e) => e.message);
  assert.ok(!messages.some((m) => /projection error|spills outside the rigid footprint/.test(m)), messages.join('\n'));
  assert.deepEqual(messages.map((m) => /past the (\w+) edge/.exec(m)?.[1]), ['left', 'right']);
  assert.ok(messages.every((m) => /spills 52\.0000 rendered px/.test(m)), messages.join('\n'));
  assert.deepEqual(report.assets[0].silhouette, { left: 0, right: 151, top: 0, bottom: 127 });
});

test('deliberate overhang needs a declared budget and a stated reason', async (t) => {
  const directory = await mkdtemp(path.join(tmpdir(), 'art-overhang-'));
  t.after(() => rm(directory, { recursive: true, force: true }));
  const canopy = png(96, 96);
  await writeFile(path.join(directory, 'atlas.png'), canopy);
  const candidate = contract();
  candidate.assets = [{
    id: 'tree', kind: 'prop', image: 'atlas.png',
    sha256: createHash('sha256').update(canopy).digest('hex'),
    frame: { x: 0, y: 0, width: 96, height: 96 }, anchor: { x: 0.5, y: 1 },
    render: { width: 96 }, footprint: { columns: 1, rows: 1 }, heights: [], allowedOverhang: '',
    groundPoints: [ground(32, 96, -0.25, -0.25), ground(64, 96, 0.25, 0.25), ground(48, 88, 0.25, -0.25)],
  }];
  const undeclared = await checkContract(structuredClone(candidate), directory);
  assert.equal(undeclared.errors.length, 2);
  assert.ok(undeclared.errors.every((e) => /spills 16\.0000 rendered px/.test(e.message)), JSON.stringify(undeclared.errors));
  const unexplained = structuredClone(candidate);
  unexplained.assets[0].overhangPx = 16;
  assert.match((await checkContract(unexplained, directory)).errors.map((e) => e.message).join('\n'), /requires allowedOverhang to state/);
  const justified = structuredClone(candidate);
  justified.assets[0].overhangPx = 16;
  justified.assets[0].allowedOverhang = 'Canopy crosses tile edges; trunk base stays inside the footprint';
  const report = await checkContract(structuredClone(justified), directory);
  assert.equal(report.passed, false, 'a budget and prose alone must not pass');
  assert.match(report.errors.map((e) => e.message).join('\n'), /needs a classified ruling/);
  const negative = structuredClone(justified);
  negative.assets[0].overhangPx = -1;
  assert.match((await checkContract(negative, directory)).errors.map((e) => e.message).join('\n'), /nonnegative silhouette budget/);
});

test('ground tolerance cannot be widened until the measurements stop biting', async (t) => {
  const directory = await mkdtemp(path.join(tmpdir(), 'art-tolerance-'));
  t.after(() => rm(directory, { recursive: true, force: true }));
  const wide = png(96, 96);
  await writeFile(path.join(directory, 'atlas.png'), wide);
  const candidate = contract();
  candidate.assets = [{
    id: 'tree', kind: 'prop', image: 'atlas.png', sha256: createHash('sha256').update(wide).digest('hex'),
    frame: { x: 0, y: 0, width: 96, height: 96 }, anchor: { x: 0.5, y: 1 },
    render: { width: 96 }, footprint: { columns: 1, rows: 1 }, heights: [], allowedOverhang: '',
    groundPoints: [ground(32, 96, -0.25, -0.25), ground(64, 96, 0.25, 0.25), ground(48, 88, 0.25, -0.25)],
  }];
  const half = candidate.projection.tileWidth / 2;
  const waived = structuredClone(candidate);
  waived.tolerances.groundErrorPx = half;
  const report = await checkContract(waived, directory);
  assert.equal(report.passed, false, 'a tolerance as wide as half a tile must not waive the gate');
  assert.match(report.errors.map((e) => e.message).join('\n'), /must stay below half a tile width/);
  const workable = structuredClone(candidate);
  workable.tolerances.groundErrorPx = half - 1e-9;
  assert.ok(!(await checkContract(workable, directory)).errors.some((e) => /half a tile width/.test(e.message)));
});

test('a budget only holds with a ruling pinned to the measured region', async (t) => {
  const directory = await mkdtemp(path.join(tmpdir(), 'art-ruling-'));
  t.after(() => rm(directory, { recursive: true, force: true }));
  const canopy = png(96, 96);
  await writeFile(path.join(directory, 'atlas.png'), canopy);
  const candidate = contract();
  candidate.overhangRulings = 'rulings.json';
  candidate.assets = [{
    id: 'tree', kind: 'prop', image: 'atlas.png',
    sha256: createHash('sha256').update(canopy).digest('hex'),
    frame: { x: 0, y: 0, width: 96, height: 96 }, anchor: { x: 0.5, y: 1 },
    render: { width: 96 }, footprint: { columns: 1, rows: 1 }, heights: [],
    overhangPx: 16, allowedOverhang: 'Canopy crosses tile edges',
    groundPoints: [ground(32, 96, -0.25, -0.25), ground(64, 96, 0.25, 0.25), ground(48, 88, 0.25, -0.25)],
  }];
  const rule = async (ruling) => {
    await writeFile(path.join(directory, 'rulings.json'), JSON.stringify({ version: 1, rulings: [ruling] }));
    return checkContract(structuredClone(candidate), directory);
  };
  await writeFile(path.join(directory, 'rulings.json'), JSON.stringify({ version: 1, rulings: [] }));
  const measured = await checkContract(structuredClone(candidate), directory);
  const region = measured.assets[0].overhang;
  assert.deepEqual(Object.keys(region.columns).filter((side) => region.columns[side]), ['left', 'right']);
  assert.match(region.regionSha256, /^[0-9a-f]{64}$/);

  const verdict = {
    asset: 'tree', imageSha256: candidate.assets[0].sha256, regionSha256: region.regionSha256,
    classification: { left: 'canopy', right: 'canopy' }, basis: 'Fronds held clear of the ground',
    classifier: { model: 'test-classifier', promptSha256: 'b'.repeat(64), decidedAt: '2026-09-17' },
  };
  assert.equal((await rule(verdict)).passed, true, 'a pinned, permitted ruling passes');

  const base = await rule({ ...verdict, classification: { left: 'ground-contact', right: 'canopy' } });
  assert.equal(base.passed, false);
  assert.match(base.errors[0].message, /left overhang is classified as ground-contact/);

  const stale = await rule({ ...verdict, regionSha256: 'a'.repeat(64) });
  assert.match(stale.errors[0].message, /decided for a different region/);

  const partial = await rule({ ...verdict, classification: { left: 'canopy' } });
  assert.match(partial.errors[0].message, /leaves the right spill unjudged/);

  const invented = await rule({ ...verdict, classification: { ...verdict.classification, middle: 'canopy' } });
  assert.match(invented.errors.map((e) => e.message).join('\n'), /unknown side middle/);

  const guessed = await rule({ ...verdict, classification: { left: 'unclear', right: 'canopy' } });
  assert.match(guessed.errors[0].message, /classified as unclear/);
});

test('a ruling cannot be carried over to repainted artwork', async (t) => {
  const directory = await mkdtemp(path.join(tmpdir(), 'art-ruling-stale-'));
  t.after(() => rm(directory, { recursive: true, force: true }));
  const canopy = png(96, 96);
  await writeFile(path.join(directory, 'atlas.png'), canopy);
  const candidate = contract();
  candidate.overhangRulings = 'rulings.json';
  candidate.assets = [{
    id: 'tree', kind: 'prop', image: 'atlas.png', sha256: createHash('sha256').update(canopy).digest('hex'),
    frame: { x: 0, y: 0, width: 96, height: 96 }, anchor: { x: 0.5, y: 1 },
    render: { width: 96 }, footprint: { columns: 1, rows: 1 }, heights: [],
    overhangPx: 16, allowedOverhang: 'Canopy crosses tile edges',
    groundPoints: [ground(32, 96, -0.25, -0.25), ground(64, 96, 0.25, 0.25), ground(48, 88, 0.25, -0.25)],
  }];
  await writeFile(path.join(directory, 'rulings.json'), JSON.stringify({ version: 1, rulings: [] }));
  const first = await checkContract(structuredClone(candidate), directory);
  await writeFile(path.join(directory, 'rulings.json'), JSON.stringify({
    version: 1,
    rulings: [{ asset: 'tree', imageSha256: candidate.assets[0].sha256,
      regionSha256: first.assets[0].overhang.regionSha256, classification: { left: 'canopy', right: 'canopy' },
      basis: 'Fronds held clear of the ground',
      classifier: { model: 'test-classifier', promptSha256: 'b'.repeat(64), decidedAt: '2026-09-17' } }],
  }));
  assert.equal((await checkContract(structuredClone(candidate), directory)).passed, true);
  // Widening the footprint moves the judged region, so the old verdict must stop applying.
  const widened = structuredClone(candidate);
  widened.assets[0].footprint = { columns: 2, rows: 1 };
  widened.assets[0].groundPoints = [ground(32, 96, -0.25, -0.25), ground(64, 96, 0.25, 0.25), ground(48, 88, 0.25, -0.25)];
  const moved = await checkContract(widened, directory);
  assert.match(moved.errors.map((e) => e.message).join('\n'), /different region|spills/);
});

test('a prop reports the body height its own artwork demands', async (t) => {
  const directory = await fixture(t);
  const candidate = contract();
  const report = await checkContract(candidate, directory);
  assert.equal(report.passed, true, JSON.stringify(report.errors));
  const of = (id) => report.assets.find((asset) => asset.id === id);
  // The table's opaque frame reaches 48px above its anchor row, and a 1x1 footprint leaves no
  // doubt which cell owns that row, so the band collapses onto the single measured figure.
  assert.deepEqual(of('table').bodyHeightPx, { low: 48, high: 48 });
  // Terrain lies in the ground plane and an actor's body is not its drawn silhouette.
  for (const id of ['tile', 'person']) assert.equal(of(id).bodyHeightPx, undefined);

  candidate.assets[1].footprint = { columns: 2, rows: 3 };
  const wider = await checkContract(candidate, directory);
  assert.equal(wider.passed, true, JSON.stringify(wider.errors));
  // Reading the highest pixel as the farthest cell lowers the floor by one column of depth;
  // reading it as the nearest raises the ceiling by two rows. Only the floor is enforced.
  assert.deepEqual(wider.assets.find((asset) => asset.id === 'table').bodyHeightPx,
    { low: 48 - 16, high: 48 + 32 });
});

test('art narrower than its footprint passes, but a blank frame is rejected', async (t) => {
  const directory = await mkdtemp(path.join(tmpdir(), 'art-padding-'));
  t.after(() => rm(directory, { recursive: true, force: true }));
  const padded = png(64, 32, 32);
  await writeFile(path.join(directory, 'atlas.png'), padded);
  const candidate = contract();
  candidate.assets = [candidate.assets[0]];
  candidate.assets[0].sha256 = createHash('sha256').update(padded).digest('hex');
  const report = await checkContract(candidate, directory);
  assert.equal(report.passed, true, JSON.stringify(report.errors));
  assert.equal(report.assets[0].silhouette.right, 31);
  const blankBytes = png(64, 32, 0);
  await writeFile(path.join(directory, 'atlas.png'), blankBytes);
  const blank = contract();
  blank.assets = [blank.assets[0]];
  blank.assets[0].sha256 = createHash('sha256').update(blankBytes).digest('hex');
  assert.match((await checkContract(blank, directory)).errors.map((e) => e.message).join('\n'), /no visible pixels/);
});

test('rigid contact cannot escape footprint using allowedOverhang', async (t) => {
  await rejection(t, (c) => { c.assets[1].groundPoints[0].grid.c = -1; c.assets[1].allowedOverhang = 'Decorative tree canopy'; }, /exceeds the declared rigid footprint/);
});

test('actual rendered ground spill fails even when declared grid contacts stay inside', async (t) => {
  const report = await rejection(t, (c) => {
    c.assets[1].render.offset = { x: 8, y: 0 };
    c.assets[1].allowedOverhang = 'Decorative canopy only';
  }, /actual rendered contact spills outside the rigid footprint/);
  assert.ok(report.errors.some((error) => error.assetId === 'table' && /measured grid \(0\.6250, 0\.6250\)/.test(error.message)));
  assert.ok(!report.errors.some((error) => /\.grid exceeds/.test(error.message)));
});

test('actual ground containment permits the declared pixel measurement tolerance', async (t) => {
  const c = contract(); c.assets = [c.assets[1]];
  c.tolerances.groundErrorPx = 1;
  c.assets[0].render.offset = { x: 0.5, y: 0 };
  const report = await checkContract(c, await fixture(t));
  assert.equal(report.passed, true, JSON.stringify(report.errors));
});

test('actor world-height mismatch is detected separately from ground fit', async (t) => {
  await rejection(t, (c) => { c.assets[2].heights[0].top.y = 12; }, /reference adult requires 64/);
});

test('height landmark horizontal displacement is rejected', async (t) => {
  await rejection(t, (c) => { c.assets[2].heights[0].top.x = 18; }, /same world x/);
});

test('nonuniform props are rejected', async (t) => {
  await rejection(t, (c) => { c.assets[1].render.height = 48; }, /require uniform render scaling/);
});

test('render offset participates in ground validation', async (t) => {
  await rejection(t, (c) => { c.assets[2].render.offset = { x: 0, y: 10 }; }, /projection error 10/);
});

test('frame overflow, fractional frames, and frame-local bounds are rejected', async (t) => {
  const a = await rejection(t, (c) => { c.assets[1].frame.x = 100; }, /frame exceeds PNG bounds/);
  assert.equal(a.assets.some((asset) => asset.id === 'table'), false);
  await rejection(t, (c) => { c.assets[0].frame.width = 63.5; }, /positive integer width/);
  await rejection(t, (c) => { c.assets[1].groundPoints[0].source.x = 100; }, /must be frame-local/);
});

test('checksum mismatch fails but remains previewable', async (t) => {
  const report = await rejection(t, (c) => { c.assets[0].sha256 = 'a'.repeat(64); }, /sha256 mismatch/);
  assert.equal(report.assets.length, 3);
});

test('unknown fields, nonfinite values, duplicate ids, and invalid hashes fail schema checks', async (t) => {
  await rejection(t, (c) => { c.projection.tileWidth = Infinity; }, /finite and positive/);
  await rejection(t, (c) => { c.assets[0].anchor.x = NaN; }, /finite numbers/);
  await rejection(t, (c) => { c.assets[1].id = 'tile'; }, /Duplicate asset id/);
  await rejection(t, (c) => { c.assets[0].sha256 = 'bad'; }, /64 hexadecimal/);
  await rejection(t, (c) => { c.assets[0].render.scale = 2; }, /not a supported field/);
  await rejection(t, (c) => { delete c.assets[0].allowedOverhang; }, /allowedOverhang is required/);
});

test('required ground and height measurements cannot be omitted', async (t) => {
  await rejection(t, (c) => { c.assets[0].groundPoints.pop(); }, /exactly four groundPoints/);
  await rejection(t, (c) => { c.assets[1].groundPoints.pop(); }, /at least three noncollinear/);
  await rejection(t, (c) => { c.assets[2].groundPoints = []; }, /at least one ground contact/);
  await rejection(t, (c) => { c.assets[2].heights = []; }, /at least one named height/);
  await rejection(t, (c) => { c.assets[2].heights[0].reference = 'unknown'; }, /must name an entry/);
});

test('collinear source or grid prop contacts cannot certify a footprint', async (t) => {
  await rejection(t, (c) => { c.assets[1].groundPoints[2].source = { x: 32, y: 48 }; }, /noncollinear/);
  await rejection(t, (c) => { c.assets[1].groundPoints[2].grid = { c: 0, r: 0 }; }, /noncollinear/);
});

test('missing, remote, and non-PNG sources fail without fetching', async (t) => {
  await rejection(t, (c) => { c.assets[0].image = 'missing.png'; }, /Cannot inspect PNG/);
  await rejection(t, (c) => { c.assets[0].image = 'https://example.test/a.png'; }, /local filesystem path/);
  await rejection(t, (c) => { c.assets[0].image = 'atlas.jpg'; }, /Only PNG/);
});

test('invalid PNG signature, dimensions, and truncated chunks fail inspection', async (t) => {
  const directory = await fixture(t);
  for (const [mutate, pattern] of [
    [(b) => { b[0] = 0; }, /Invalid PNG signature/],
    [(b) => { b.writeUInt32BE(0, 16); }, /IHDR dimensions/],
    [(b) => { b.writeUInt32BE(32769, 20); }, /IHDR dimensions/],
    [(b) => { b.writeUInt32BE(0xffffffff, 33); }, /Truncated PNG chunk/],
  ]) {
    const invalid = Buffer.from(bytes); mutate(invalid);
    await writeFile(path.join(directory, 'atlas.png'), invalid);
    const report = await checkContract(contract(), directory);
    assert.equal(report.passed, false);
    assert.match(report.errors[0].message, pattern);
    assert.equal(report.assets.length, 0);
  }
});

test('contract asset limit is bounded', async (t) => {
  await rejection(t, (c) => { c.assets = Array(2049).fill(c.assets[0]); }, /between 1 and 2048/);
});

test('checkFile resolves images relative to contract and reports malformed JSON', async (t) => {
  const directory = await fixture(t), file = path.join(directory, 'contract.json');
  await writeFile(file, JSON.stringify(contract()));
  assert.equal((await checkFile(file)).passed, true);
  await writeFile(file, '{');
  assert.equal((await checkFile(file)).passed, false);
  assert.equal((await checkFile(path.join(directory, 'missing.json'))).passed, false);
});

test('checkFile accepts UTF-8 BOM JSON produced by PowerShell', async (t) => {
  const directory = await fixture(t), file = path.join(directory, 'contract.json');
  await writeFile(file, '\uFEFF' + JSON.stringify(contract()), 'utf8');
  const report = await checkFile(file);
  assert.equal(report.passed, true, JSON.stringify(report.errors));
  assert.equal(report.assets.length, 3);
});

test('CLI emits a JSON report and status 0/1', async (t) => {
  const directory = await fixture(t), file = path.join(directory, 'contract.json');
  const script = fileURLToPath(new URL('../scripts/check-art.mjs', import.meta.url));
  await writeFile(file, JSON.stringify(contract()));
  const passed = spawnSync(process.execPath, [script, file], { encoding: 'utf8' });
  assert.equal(passed.status, 0, passed.stderr);
  assert.equal(JSON.parse(passed.stdout).passed, true);
  const failed = spawnSync(process.execPath, [script, path.join(directory, 'absent.json')], { encoding: 'utf8' });
  assert.equal(failed.status, 1);
  assert.equal(JSON.parse(failed.stdout).scope, 'metadata-only');
});
