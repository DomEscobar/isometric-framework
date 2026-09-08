import assert from 'node:assert/strict';
import { mkdtemp, readFile, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import test from 'node:test';
import { runCli } from '../scripts/wavespeed.mjs';

const MODEL = 'bytedance/seedream-v5.0-pro';
const EDIT_MODEL = `${MODEL}/edit`;
const KEY = 'fake-test-key-never-use-live';
const OUTPUT = 'https://cdn.example.com/art.png';
const result = (status, extra = {}) => ({ ok: true, status: 200, json: async () => ({ data: { id: 'job_123-ab', status, outputs: status === 'completed' ? [OUTPUT] : [], ...extra } }) });

async function fixture(t, responses = []) {
  const dir = await mkdtemp(join(tmpdir(), 'wavespeed-test-'));
  t.after(() => rm(dir, { recursive: true, force: true }));
  const input = join(dir, 'request.json');
  const jobFile = join(dir, 'job.json');
  await writeFile(input, JSON.stringify({ prompt: 'A tiny pixel tree on a plain background' }));
  let time = 1000;
  const calls = [], sleeps = [], out = [], err = [];
  const deps = {
    env: { WAVESPEED_API_KEY: KEY },
    now: () => time,
    sleep: async (ms) => { assert.ok(ms >= 0); sleeps.push(ms); time += ms; },
    stdout: (text) => out.push(text), stderr: (text) => err.push(text),
    fetch: async (url, options) => {
      calls.push({ url, ...options });
      const next = responses.shift();
      assert.ok(next, 'Unexpected fetch (tests cannot access the network)');
      if (typeof next === 'function') return next(url, options);
      if (next instanceof Error) throw next;
      return next;
    },
  };
  return {
    input, jobFile, calls, sleeps, out, err, deps,
    submit: (...options) => runCli(['submit', MODEL, input, jobFile, ...options], deps),
    resume: (...options) => runCli(['resume', jobFile, ...options], deps),
    state: async () => JSON.parse(await readFile(jobFile, 'utf8')),
  };
}

test('async submission persists ID before polling, uses safe auth, and prints output URLs', async (t) => {
  const f = await fixture(t, [result('created'), async () => {
    assert.equal((await f.state()).id, 'job_123-ab');
    return result('processing');
  }, result('completed')]);
  assert.equal(await f.submit(), 0);
  assert.deepEqual(f.calls.map((c) => c.method), ['POST', 'GET', 'GET']);
  assert.equal(f.calls[0].url, `https://api.wavespeed.ai/api/v3/${MODEL}`);
  assert.equal(f.calls[1].url, 'https://api.wavespeed.ai/api/v3/predictions/job_123-ab/result');
  assert.equal(f.calls[0].headers.Authorization, `Bearer ${KEY}`);
  assert.equal(f.calls[0].redirect, 'error');
  assert.equal(JSON.parse(f.calls[0].body).output_format, 'png');
  assert.equal(JSON.parse(f.calls[0].body).resolution, '1k');
  const state = await f.state();
  assert.equal(state.status, 'completed');
  assert.match(state.requestHash, /^[a-f0-9]{64}$/);
  assert.equal(JSON.stringify(state).includes(KEY), false);
  assert.equal(JSON.stringify(state).includes('tiny pixel tree'), false);
  assert.deepEqual(JSON.parse(f.out.join('')).outputs, [OUTPUT]);
});

for (const status of ['failed', 'cancelled', 'timeout', 'deleted']) {
  test(`terminal ${status} persists, fails, and does not retry`, async (t) => {
    const f = await fixture(t, [result('processing'), result(status, { error: `private ${KEY}` })]);
    assert.equal(await f.submit(), 1);
    assert.equal((await f.state()).status, status);
    assert.equal(f.calls.length, 2);
    assert.equal(f.err.join('').includes(KEY), false);
    assert.match(f.err.join(''), new RegExp(`status ${status}`));
  });
}

test('poll timeout preserves ID and resume uses only GET on the same task', async (t) => {
  const f = await fixture(t, [result('processing')]);
  assert.equal(await f.submit('--timeout-ms', '1'), 3);
  assert.equal(f.calls.length, 1);
  assert.equal((await f.state()).id, 'job_123-ab');
  assert.match(f.err.join(''), /not cancelled.*resume/s);
  f.deps.fetch = async (url, options) => {
    assert.equal(options.method, 'GET');
    assert.match(url, /predictions\/job_123-ab\/result$/);
    return result('completed');
  };
  assert.equal(await f.resume(), 0);
  assert.equal((await f.state()).status, 'completed');
});

test('GET transient HTTP and network failures back off within retry limit', async (t) => {
  const f = await fixture(t, [result('pending'), { ok: false, status: 429 }, new Error(KEY), { ok: false, status: 503 }, result('completed')]);
  assert.equal(await f.submit(), 0);
  assert.deepEqual(f.calls.map((c) => c.method), ['POST', 'GET', 'GET', 'GET', 'GET']);
  assert.ok(f.sleeps.includes(1000) && f.sleeps.includes(4000));
  assert.equal(f.err.join('').includes(KEY), false);
});

test('persistent GET failures are bounded and direct user to resume', async (t) => {
  const f = await fixture(t, [result('pending'), ...Array.from({ length: 5 }, () => ({ ok: false, status: 503 }))]);
  assert.equal(await f.submit(), 1);
  assert.equal(f.calls.length, 6);
  assert.match(f.err.join(''), /Result HTTP 503.*Resume/s);
  assert.equal((await f.state()).id, 'job_123-ab');
});

test('ambiguous POST transport failure is never retried; unusable resume never submits', async (t) => {
  const f = await fixture(t, [new Error(`fetch failed with ${KEY}`)]);
  assert.equal(await f.submit(), 1);
  assert.equal(f.calls.length, 1);
  assert.equal((await f.state()).status, 'submission_unknown');
  assert.equal(await f.resume(), 2);
  assert.equal(f.calls.length, 1);
  assert.match(f.err.join(''), /provider history/);
  assert.equal(f.err.join('').includes(KEY), false);
});

test('POST HTTP failure does not read raw error body or retry', async (t) => {
  const f = await fixture(t, [{ ok: false, status: 500, json: () => { throw Error('Must not read sensitive error body'); } }]);
  assert.equal(await f.submit(), 1);
  assert.equal(f.calls.length, 1);
  assert.match(f.err.join(''), /HTTP 500/);
});

test('existing job is never overwritten or submitted', async (t) => {
  const f = await fixture(t);
  await writeFile(f.jobFile, 'precious existing data');
  assert.equal(await f.submit(), 2);
  assert.equal(f.calls.length, 0);
  assert.equal(await readFile(f.jobFile, 'utf8'), 'precious existing data');
});

test('missing key and invalid local JSON fail before any network request', async (t) => {
  const f = await fixture(t);
  f.deps.env = {};
  assert.equal(await f.submit(), 2);
  assert.match(f.err.join(''), /WAVESPEED_API_KEY/);
  f.deps.env = { WAVESPEED_API_KEY: KEY };
  await writeFile(f.input, '{invalid JSON with secret');
  assert.equal(await f.submit(), 2);
  assert.equal(f.calls.length, 0);
  assert.equal(f.err.join('').includes('with secret'), false);
});

test('model paths, sync controls, base64, and invalid options are rejected locally', async (t) => {
  const f = await fixture(t);
  assert.equal(await runCli(['submit', '../predictions', f.input, f.jobFile], f.deps), 2);
  for (const input of [{ prompt: 'ok', enable_sync_mode: true }, { prompt: 'ok', resolution: '4k' }, { prompt: 'ok', resolution: '99k' }, { prompt: 'ok', output_format: 'jpeg' }]) {
    await writeFile(f.input, JSON.stringify(input));
    assert.equal(await f.submit(), 2);
  }
  for (const image of ['data:image/png;base64,private', 'https://user:password@example.com/a.png', 'https://127.0.0.1/a.png', 'http://cdn.example.com/a.png', 'https://localhost/a.png']) {
    await writeFile(f.input, JSON.stringify({ image }));
    assert.equal(await runCli(['submit', 'wavespeed-ai/image-background-remover', f.input, f.jobFile], f.deps), 2);
  }
  assert.equal(f.calls.length, 0);
  assert.equal(f.err.join('').includes('base64,private'), false);
});

test('background remover accepts HTTPS URL and handles immediate completion', async (t) => {
  const f = await fixture(t, [result('completed')]);
  await writeFile(f.input, JSON.stringify({ image: OUTPUT }));
  assert.equal(await runCli(['submit', 'wavespeed-ai/image-background-remover', f.input, f.jobFile], f.deps), 0);
  assert.equal(f.calls.length, 1);
  assert.deepEqual(JSON.parse(f.calls[0].body), { image: OUTPUT });
});

test('unsafe task IDs never become URLs; valid ID survives malformed status', async (t) => {
  const f = await fixture(t, [result('processing', { id: '../unsafe' })]);
  assert.equal(await f.submit(), 1);
  assert.equal(f.calls.length, 1);
  const g = await fixture(t, [result(`unknown ${KEY}`)]);
  assert.equal(await g.submit(), 1);
  assert.equal((await g.state()).id, 'job_123-ab');
  assert.equal(g.err.join('').includes(KEY), false);
});

test('invalid output and mismatched result IDs are not persisted or printed', async (t) => {
  const f = await fixture(t, [result('processing'), result('completed', { outputs: [`data:image/png;base64,${KEY}`] })]);
  assert.equal(await f.submit(), 1);
  assert.equal(f.out.length, 0);
  assert.equal((await readFile(f.jobFile, 'utf8')).includes(KEY), false);
  const g = await fixture(t, [result('processing'), result('completed', { id: 'different-id' })]);
  assert.equal(await g.submit(), 1);
  assert.match(g.err.join(''), /mismatched task ID/);
});

test('help requires no key and invalid timeout makes no request', async (t) => {
  const f = await fixture(t);
  assert.equal(await runCli(['--help'], { ...f.deps, env: {} }), 0);
  assert.equal(await f.submit('--timeout-ms', '0'), 2);
  assert.equal(await f.submit('--timeout-ms', 'Infinity'), 2);
  assert.equal(f.calls.length, 0);
});

test('POST request timeout aborts transport and never retries', async (t) => {
  let aborted = false;
  const f = await fixture(t, asyncResponses());
  function asyncResponses() {
    return [async (_url, { signal }) => new Promise((_resolve, reject) => {
      signal.addEventListener('abort', () => { aborted = true; reject(new Error(`abort ${KEY}`)); }, { once: true });
    })];
  }
  f.deps.requestTimeoutMs = 10;
  assert.equal(await f.submit(), 1);
  assert.equal(aborted, true);
  assert.equal(f.calls.length, 1);
  assert.equal((await f.state()).status, 'submission_unknown');
  assert.equal(f.err.join('').includes(KEY), false);
});

test('GET unauthorized response stops immediately and does not expose its body', async (t) => {
  const f = await fixture(t, [result('processing'), { ok: false, status: 401, json: () => { throw Error(KEY); } }]);
  assert.equal(await f.submit(), 1);
  assert.equal(f.calls.length, 2);
  assert.match(f.err.join(''), /HTTP 401/);
  assert.equal(f.err.join('').includes(KEY), false);
});

test('unsafe ID in edited resume file fails before fetching', async (t) => {
  const f = await fixture(t);
  await writeFile(f.jobFile, JSON.stringify({ version: 1, model: MODEL, id: '../other-task' }));
  assert.equal(await f.resume(), 2);
  assert.equal(f.calls.length, 0);
});

test('verified nondefault ratio and 1.5k resolution are sent unchanged', async (t) => {
  const f = await fixture(t, [result('completed')]);
  await writeFile(f.input, JSON.stringify({ prompt: 'A sprite', aspect_ratio: '1:3', resolution: '1.5k', prompt_optimization_mode: 'fast' }));
  assert.equal(await f.submit(), 0);
  const body = JSON.parse(f.calls[0].body);
  assert.equal(body.aspect_ratio, '1:3');
  assert.equal(body.resolution, '1.5k');
});

test('UTF-8 BOM request and resume JSON files work with PowerShell output', async (t) => {
  const f = await fixture(t, [result('processing'), result('completed')]);
  await writeFile(f.input, `\uFEFF${JSON.stringify({ prompt: 'A Windows-authored sprite' })}`);
  assert.equal(await f.submit('--timeout-ms', '1'), 3);
  const saved = await readFile(f.jobFile, 'utf8');
  await writeFile(f.jobFile, `\uFEFF${saved}`);
  assert.equal(await f.resume(), 0);
  assert.deepEqual(f.calls.map((call) => call.method), ['POST', 'GET']);
  assert.equal((await f.state()).status, 'completed');
});

test('HTTP 200 processing code 5004 retains the task ID and continues polling', async (t) => {
  const f = await fixture(t, [result('processing', { code: 5004 }), async () => {
    assert.equal((await f.state()).id, 'job_123-ab');
    assert.equal((await f.state()).status, 'processing');
    return result('completed');
  }]);
  assert.equal(await f.submit(), 0);
  assert.deepEqual(f.calls.map((call) => call.method), ['POST', 'GET']);
  assert.equal((await f.state()).status, 'completed');
});

test('edit forwards references in order to its endpoint and preserves provider aspect default', async (t) => {
  const f = await fixture(t, [result('completed')]);
  const images = ['https://cdn.example.com/character.png', 'https://cdn.example.com/pose.png'];
  await writeFile(f.input, JSON.stringify({ prompt: 'Keep the character and match the action pose', images }));
  assert.equal(await runCli(['submit', EDIT_MODEL, f.input, f.jobFile], f.deps), 0);
  assert.equal(f.calls.length, 1);
  assert.equal(f.calls[0].url, 'https://api.wavespeed.ai/api/v3/bytedance/seedream-v5.0-pro/edit');
  const body = JSON.parse(f.calls[0].body);
  assert.deepEqual(body.images, images);
  assert.equal(Object.hasOwn(body, 'aspect_ratio'), false);
  assert.equal(body.output_format, 'png');
  assert.equal(body.resolution, '1k');
  const state = await f.state();
  assert.equal(state.model, EDIT_MODEL);
  assert.equal(JSON.stringify(state).includes(images[0]), false);
});

test('edit accepts ten references and explicit validated aspect ratio', async (t) => {
  const f = await fixture(t, [result('completed')]);
  const images = Array.from({ length: 10 }, (_, i) => `https://cdn.example.com/reference-${i}.png`);
  await writeFile(f.input, JSON.stringify({ prompt: 'A character action', images, aspect_ratio: '3:4', resolution: '1.5k' }));
  assert.equal(await runCli(['submit', EDIT_MODEL, f.input, f.jobFile], f.deps), 0);
  const body = JSON.parse(f.calls[0].body);
  assert.deepEqual(body.images, images);
  assert.equal(body.aspect_ratio, '3:4');
  assert.equal(body.resolution, '1.5k');
});

test('edit rejects invalid reference count, reference URLs, and aspect ratio before any submission', async (t) => {
  const f = await fixture(t);
  const invalidImages = [undefined, [], OUTPUT, Array(11).fill(OUTPUT), [null], ['data:image/png;base64,private'], ['https://user:password@example.com/image.png'], ['https://127.0.0.1/image.png'], ['http://cdn.example.com/image.png'], [OUTPUT, 'invalid']];
  for (const images of invalidImages) {
    await writeFile(f.input, JSON.stringify({ prompt: 'A character action', images }));
    assert.equal(await runCli(['submit', EDIT_MODEL, f.input, f.jobFile], f.deps), 2);
  }
  for (const aspect_ratio of [null, '', '999:1']) {
    await writeFile(f.input, JSON.stringify({ prompt: 'A character action', images: [OUTPUT], aspect_ratio }));
    assert.equal(await runCli(['submit', EDIT_MODEL, f.input, f.jobFile], f.deps), 2);
  }
  assert.equal(f.calls.length, 0);
  assert.equal(f.err.join('').includes('base64,private'), false);
  assert.equal(f.err.join('').includes('user:password'), false);
});

test('text generation rejects images while edit requires a prompt', async (t) => {
  const f = await fixture(t);
  await writeFile(f.input, JSON.stringify({ prompt: 'A character action', images: [OUTPUT] }));
  assert.equal(await f.submit(), 2);
  await writeFile(f.input, JSON.stringify({ images: [OUTPUT] }));
  assert.equal(await runCli(['submit', EDIT_MODEL, f.input, f.jobFile], f.deps), 2);
  assert.equal(f.calls.length, 0);
});

test('edit job resumes through result GET without resubmitting references', async (t) => {
  const f = await fixture(t, [result('processing'), result('completed')]);
  await writeFile(f.input, JSON.stringify({ prompt: 'A character action', images: [OUTPUT] }));
  assert.equal(await runCli(['submit', EDIT_MODEL, f.input, f.jobFile, '--timeout-ms', '1'], f.deps), 3);
  assert.equal((await f.state()).model, EDIT_MODEL);
  assert.equal(await f.resume(), 0);
  assert.deepEqual(f.calls.map((call) => call.method), ['POST', 'GET']);
  assert.match(f.calls[1].url, /predictions\/job_123-ab\/result$/);
  assert.equal(f.calls[1].body, undefined);
  assert.equal((await f.state()).model, EDIT_MODEL);
});
