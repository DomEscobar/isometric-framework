import assert from 'node:assert/strict';
import { mkdir, mkdtemp, readFile, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { basename, join } from 'node:path';
import test from 'node:test';
import { runBatch } from '../scripts/wavespeed-batch.mjs';
import { runCli } from '../scripts/wavespeed.mjs';

const MODEL = 'bytedance/seedream-v5.0-pro';
const KEY = 'fake-test-key-never-use-live';
const SHAPE = ['aspect_ratio', 'output_format', 'prompt', 'prompt_optimization_mode', 'resolution'];

async function workspace(t) {
  const dir = await mkdtemp(join(tmpdir(), 'wavespeed-batch-'));
  t.after(() => rm(dir, { recursive: true, force: true }));
  return dir;
}

async function batch(dir, tracks, extra = {}) {
  for (const track of tracks) {
    await writeFile(join(dir, `${track.id}.request.json`),
      JSON.stringify(track.request ?? { prompt: `One isolated pixel-art ${track.id} on a plain backdrop` }));
  }
  const path = join(dir, 'batch.json');
  await writeFile(path, JSON.stringify({
    version: 1, ...extra,
    tracks: tracks.map((track) => ({
      id: track.id, model: track.model ?? MODEL,
      request: `${track.id}.request.json`, job: track.job ?? `${track.id}.job.json`,
    })),
  }));
  return path;
}

async function pilotFragment(dir, overrides = {}, name = 'pilot.json') {
  await writeFile(join(dir, name), JSON.stringify({
    kind: 'wavespeed-track-result', track: 'pilot', model: MODEL, shape: SHAPE,
    disposition: 'complete', accepted: true, ...overrides,
  }));
  return name;
}

/** Records every client invocation and the highest number that ever overlapped. */
function stub(behaviour) {
  const calls = [], live = { active: 0, peak: 0 };
  return {
    calls, live,
    client: async (argv) => {
      calls.push(argv);
      live.active += 1;
      live.peak = Math.max(live.peak, live.active);
      try { return await behaviour(argv); } finally { live.active -= 1; }
    },
  };
}

const jobPathOf = (argv) => (argv[0] === 'submit' ? argv[3] : argv[1]);

async function persist(argv, job) {
  const path = jobPathOf(argv);
  await writeFile(path, JSON.stringify({
    version: 1, model: argv[0] === 'submit' ? argv[1] : MODEL, createdAt: '2026-01-01T00:00:00.000Z',
    requestHash: 'a'.repeat(64), id: `job_${basename(path, '.json')}`, status: 'completed',
    outputs: ['https://cdn.example.com/art.png'], ...job,
  }));
}

const completes = async (argv) => { await persist(argv, {}); return 0; };

function harness() {
  const out = [], err = [];
  return { out, err, io: { stdout: (t) => out.push(t), stderr: (t) => err.push(t), now: () => 1000 } };
}

const settle = async (predicate) => {
  for (let i = 0; i < 5000 && !predicate(); i += 1) await new Promise((done) => setImmediate(done));
};

test('a batch of accepted pilot, distinct jobs and matching approval runs every track and reports it', async (t) => {
  const dir = await workspace(t);
  const pilot = await pilotFragment(dir);
  const path = await batch(dir, [{ id: 'walk-south' }, { id: 'walk-north' }], { pilot });
  const { client, calls } = stub(completes);
  const { out, io } = harness();
  assert.equal(await runBatch(['run', path, join(dir, 'out'), '--approve', '2'], { client, ...io }), 0);
  assert.deepEqual(calls.map((argv) => argv[0]), ['submit', 'submit']);
  const report = JSON.parse(await readFile(join(dir, 'out', 'batch.json'), 'utf8'));
  assert.equal(report.kind, 'wavespeed-batch-report');
  assert.equal(report.approved, 2);
  assert.equal(report.halted, false);
  assert.match(report.batchSha256, /^[a-f0-9]{64}$/);
  assert.match(report.pilot.sha256, /^[a-f0-9]{64}$/);
  assert.equal(report.scope, 'provider-jobs-only');
  assert.deepEqual(report.tracks.map((entry) => entry.disposition), ['complete', 'complete']);
  assert.equal(JSON.parse(out.join('')).batchSha256, report.batchSha256);
});

test('a fragment carries the prediction ID but neither the signed outputs nor the prompt', async (t) => {
  const dir = await workspace(t);
  const path = await batch(dir, [{ id: 'walk-south' }]);
  const { client } = stub(completes);
  assert.equal(await runBatch(['run', path, join(dir, 'out'), '--approve', '1'], { client, ...harness().io }), 0);
  const raw = await readFile(join(dir, 'out', 'walk-south', 'result.json'), 'utf8');
  const fragment = JSON.parse(raw);
  assert.equal(fragment.kind, 'wavespeed-track-result');
  assert.equal(fragment.predictionId, 'job_walk-south.job');
  assert.equal(fragment.outputCount, 1);
  assert.equal(fragment.accepted, false);
  assert.deepEqual(fragment.shape, SHAPE);
  assert.doesNotMatch(raw, /cdn\.example\.com/);
  assert.doesNotMatch(raw, /isolated pixel-art/);
});

test('nothing is submitted when two tracks share a job path or a job file already exists', async (t) => {
  const dir = await workspace(t);
  const shared = await batch(dir, [{ id: 'a', job: 'same.job.json' }, { id: 'b', job: 'same.job.json' }],
    { pilot: await pilotFragment(dir) });
  const collide = stub(completes);
  const first = harness();
  assert.equal(await runBatch(['run', shared, join(dir, 'out'), '--approve', '2'], { client: collide.client, ...first.io }), 2);
  assert.equal(collide.calls.length, 0);
  assert.match(first.err.join(''), /reuses another track's job path/);

  const again = await batch(dir, [{ id: 'c' }]);
  await writeFile(join(dir, 'c.job.json'), '{}');
  const taken = stub(completes);
  const second = harness();
  assert.equal(await runBatch(['run', again, join(dir, 'out2'), '--approve', '1'], { client: taken.client, ...second.io }), 2);
  assert.equal(taken.calls.length, 0);
  assert.match(second.err.join(''), /already exists.*No submission was made/s);
});

test('an unusable request and a mismatched approval both stop the batch before any submission', async (t) => {
  const dir = await workspace(t);
  const broken = await batch(dir, [{ id: 'bad', request: { prompt: '', nonsense: 1 } }]);
  const rejected = stub(completes);
  const first = harness();
  assert.equal(await runBatch(['run', broken, join(dir, 'out'), '--approve', '1'], { client: rejected.client, ...first.io }), 2);
  assert.equal(rejected.calls.length, 0);
  assert.match(first.err.join(''), /Track bad:/);

  const path = await batch(dir, [{ id: 'x' }, { id: 'y' }], { pilot: await pilotFragment(dir) });
  const unapproved = stub(completes);
  const second = harness();
  assert.equal(await runBatch(['run', path, join(dir, 'out2'), '--approve', '1'], { client: unapproved.client, ...second.io }), 2);
  assert.equal(unapproved.calls.length, 0);
  assert.match(second.err.join(''), /would submit 2 billable jobs.*--approve 2/s);

  const third = harness();
  assert.equal(await runBatch(['run', path, join(dir, 'out3'), '--approve', '2', '--approve', '2'],
    { client: unapproved.client, ...third.io }), 2);
  assert.match(third.err.join(''), /--approve was given more than once/);
  const fourth = harness();
  assert.equal(await runBatch(['run', path, join(dir, 'out4'), '--approve', '02'],
    { client: unapproved.client, ...fourth.io }), 2);
  assert.match(fourth.err.join(''), /without leading zeros/);
  assert.equal(unapproved.calls.length, 0);
});

test('fanning out needs a pilot that was accepted for the same model and request shape', async (t) => {
  const dir = await workspace(t);
  const cases = [
    [null, /needs pilot/],
    [{ accepted: false }, /not an accepted completion/],
    [{ disposition: 'resume-required' }, /not an accepted completion/],
    [{ model: 'wavespeed-ai/image-background-remover' }, /Run one batch per model/],
    [{ shape: ['prompt'] }, /different request shape/],
  ];
  for (const [index, [overrides, expected]] of cases.entries()) {
    const pilot = overrides && await pilotFragment(dir, overrides, `pilot-${index}.json`);
    const path = await batch(dir, [{ id: 'p' }, { id: 'q' }], pilot ? { pilot } : {});
    const { client, calls } = stub(completes);
    const { err, io } = harness();
    assert.equal(await runBatch(['run', path, join(dir, `out-${index}`), '--approve', '2'], { client, ...io }), 2);
    assert.equal(calls.length, 0, 'a refused pilot must cost nothing');
    assert.match(err.join(''), expected);
  }
  const single = await batch(dir, [{ id: 'solo' }]);
  const { client, calls } = stub(completes);
  assert.equal(await runBatch(['run', single, join(dir, 'solo-out'), '--approve', '1'], { client, ...harness().io }), 0);
  assert.equal(calls.length, 1, 'one track is itself the pilot');
});

test('no more tracks run at once than the manifest allows', async (t) => {
  const dir = await workspace(t);
  const pilot = await pilotFragment(dir);
  const ids = ['a', 'b', 'c', 'd', 'e', 'f'];
  const path = await batch(dir, ids.map((id) => ({ id })), { pilot, concurrency: 2 });
  let release;
  const gate = new Promise((done) => { release = done; });
  const { client, calls, live } = stub(async (argv) => { await gate; return completes(argv); });
  const running = runBatch(['run', path, join(dir, 'out'), '--approve', '6'], { client, ...harness().io });
  await settle(() => live.active === 2);
  assert.equal(live.active, 2);
  release();
  assert.equal(await running, 0);
  assert.equal(live.peak, 2);
  assert.equal(calls.length, 6);
});

test('an unknown submission outcome stops further launches, a failed task does not', async (t) => {
  const dir = await workspace(t);
  const pilot = await pilotFragment(dir);
  const ids = ['a', 'b', 'c', 'd'];

  const ambiguous = await batch(dir, ids.map((id) => ({ id })), { pilot, concurrency: 1 });
  const halting = stub(async (argv) => {
    if (basename(jobPathOf(argv)).startsWith('b')) {
      await persist(argv, { id: null, status: 'submission_unknown', outputs: [] });
      return 1;
    }
    return completes(argv);
  });
  assert.equal(await runBatch(['run', ambiguous, join(dir, 'halt'), '--approve', '4'], { client: halting.client, ...harness().io }), 1);
  const halted = JSON.parse(await readFile(join(dir, 'halt', 'batch.json'), 'utf8'));
  assert.equal(halted.halted, true);
  assert.deepEqual(halted.tracks.map((entry) => entry.disposition),
    ['complete', 'inspect-provider-history', 'not-started', 'not-started']);
  assert.equal(halting.calls.length, 2);
  const stopped = JSON.parse(await readFile(join(dir, 'halt', 'c', 'result.json'), 'utf8'));
  assert.match(stopped.nextAction, /nothing was submitted for it/);

  const failing = await batch(dir, ids.map((id) => ({ id, job: `${id}.second.json` })), { pilot, concurrency: 1 });
  const dropped = stub(async (argv) => {
    if (basename(jobPathOf(argv)).startsWith('b')) {
      await persist(argv, { status: 'failed', outputs: [] });
      return 1;
    }
    return completes(argv);
  });
  assert.equal(await runBatch(['run', failing, join(dir, 'failed'), '--approve', '4'], { client: dropped.client, ...harness().io }), 1);
  const report = JSON.parse(await readFile(join(dir, 'failed', 'batch.json'), 'utf8'));
  assert.equal(report.halted, false);
  assert.deepEqual(report.tracks.map((entry) => entry.disposition),
    ['complete', 'task-failed', 'complete', 'complete']);
  assert.equal(dropped.calls.length, 4);
});

test('an exhausted polling budget asks for a resume instead of a second submission', async (t) => {
  const dir = await workspace(t);
  const path = await batch(dir, [{ id: 'slow' }]);
  const timing_out = stub(async (argv) => { await persist(argv, { status: 'processing', outputs: [] }); return 3; });
  assert.equal(await runBatch(['run', path, join(dir, 'out'), '--approve', '1', '--timeout-ms', '120'],
    { client: timing_out.client, ...harness().io }), 3);
  assert.deepEqual(timing_out.calls[0].slice(-2), ['--timeout-ms', '120']);
  const fragment = JSON.parse(await readFile(join(dir, 'out', 'slow', 'result.json'), 'utf8'));
  assert.equal(fragment.disposition, 'resume-required');
  assert.match(fragment.nextAction, /do not submit again/);

  const resumed = stub(completes);
  const { err, io } = harness();
  assert.equal(await runBatch(['resume', path, join(dir, 'out2'), '--approve', '1'], { client: resumed.client, ...io }), 2);
  assert.equal(resumed.calls.length, 0);
  assert.match(err.join(''), /takes no --approve/);
  assert.equal(await runBatch(['resume', path, join(dir, 'out3')], { client: resumed.client, ...harness().io }), 0);
  assert.deepEqual(resumed.calls[0].slice(0, 2), ['resume', join(dir, 'slow.job.json')]);
});

test('resume reports a track that was never submitted instead of submitting it now', async (t) => {
  const dir = await workspace(t);
  const path = await batch(dir, [{ id: 'never' }]);
  const { client, calls } = stub(completes);
  assert.equal(await runBatch(['resume', path, join(dir, 'out')], { client, ...harness().io }), 2);
  assert.equal(calls.length, 0);
  assert.equal(JSON.parse(await readFile(join(dir, 'out', 'never', 'result.json'), 'utf8')).disposition, 'missing-job');
});

test('an existing results directory is refused so earlier evidence survives', async (t) => {
  const dir = await workspace(t);
  const path = await batch(dir, [{ id: 'a' }]);
  await mkdir(join(dir, 'out'), { recursive: true });
  const { client, calls } = stub(completes);
  const { err, io } = harness();
  assert.equal(await runBatch(['run', path, join(dir, 'out'), '--approve', '1'], { client, ...io }), 2);
  assert.equal(calls.length, 0);
  assert.match(err.join(''), /already exists/);
});

test('concurrency beyond the cap is refused, naming the rate-limit reason', async (t) => {
  const dir = await workspace(t);
  const path = await batch(dir, [{ id: 'a' }, { id: 'b' }],
    { pilot: await pilotFragment(dir), concurrency: 32 });
  const { client, calls } = stub(completes);
  const { err, io } = harness();
  assert.equal(await runBatch(['run', path, join(dir, 'out'), '--approve', '2'], { client, ...io }), 2);
  assert.equal(calls.length, 0);
  assert.match(err.join(''), /concurrency must be 1 to 8/);
});

test('the real client is driven concurrently over the network stub, one submission per track', async (t) => {
  const dir = await workspace(t);
  const path = await batch(dir, [{ id: 'east' }, { id: 'west' }],
    { pilot: await pilotFragment(dir), concurrency: 2 });
  const posts = [];
  let issued = 0;
  const deps = {
    env: { WAVESPEED_API_KEY: KEY },
    now: () => 1000,
    sleep: async () => {},
    stdout: () => {}, stderr: () => {},
    fetch: async (url, options) => {
      posts.push({ url, method: options.method });
      issued += 1;
      const id = `job_live-${issued}`;
      return { ok: true, status: 200, json: async () => ({ data: { id, status: 'completed', outputs: ['https://cdn.example.com/art.png'] } }) };
    },
  };
  const client = (argv) => runCli(argv, deps);
  assert.equal(await runBatch(['run', path, join(dir, 'out'), '--approve', '2'], { client, ...harness().io }), 0);
  assert.deepEqual(posts.map((call) => call.method), ['POST', 'POST']);
  assert.deepEqual(new Set(posts.map((call) => call.url)), new Set([`https://api.wavespeed.ai/api/v3/${MODEL}`]));
  for (const id of ['east', 'west']) {
    const job = JSON.parse(await readFile(join(dir, `${id}.job.json`), 'utf8'));
    assert.equal(job.status, 'completed');
    assert.match(JSON.parse(await readFile(join(dir, 'out', id, 'result.json'), 'utf8')).predictionId, /^job_live-[12]$/);
  }
});
