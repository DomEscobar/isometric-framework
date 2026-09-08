#!/usr/bin/env node
// Node 22+, built-ins only. Submission is deliberately never retried.
import { createHash, randomUUID } from 'node:crypto';
import { readFile, open, rename, unlink } from 'node:fs/promises';
import { isIP } from 'node:net';
import { resolve } from 'node:path';
import { pathToFileURL } from 'node:url';

const API = 'https://api.wavespeed.ai/api/v3';
const EDIT_MODEL = 'bytedance/seedream-v5.0-pro/edit';
const MODELS = new Set(['bytedance/seedream-v5.0-pro', EDIT_MODEL, 'wavespeed-ai/image-background-remover']);
const FAILED = new Set(['failed', 'cancelled', 'timeout', 'deleted']);
const ACTIVE = new Set(['created', 'pending', 'queued', 'processing', 'running']);
const HELP = `Usage:
  node wavespeed.mjs submit MODEL request.json job.json [--timeout-ms N]
  node wavespeed.mjs resume job.json [--timeout-ms N]

Models: bytedance/seedream-v5.0-pro, bytedance/seedream-v5.0-pro/edit,
wavespeed-ai/image-background-remover
Edit requires prompt and images (1 to 10 public HTTPS URLs, kept in order).
Omitting edit aspect_ratio leaves the provider's reference-based default intact.
Requires WAVESPEED_API_KEY. Reads JSON; never logs the key or request body.
Default polling budget: 300000 ms. Timeout does not cancel a remote job.
Exit codes: 0 completed/help, 1 remote or storage error, 2 invalid local input,
3 polling timeout (resume the same job file). POST is never retried.
`;

class CliError extends Error {
  constructor(message, code = 1) { super(message); this.code = code; }
}
const fail = (message, code = 2) => { throw new CliError(message, code); };
const object = (value) => value !== null && typeof value === 'object' && !Array.isArray(value);
const taskId = (value) => typeof value === 'string' && /^[A-Za-z0-9_-]{1,128}$/.test(value);

function publicHttps(value) {
  if (typeof value !== 'string' || value.length > 16384 || /[\s\x00-\x1f]/.test(value)) return false;
  try {
    const u = new URL(value);
    return u.protocol === 'https:' && !u.username && !u.password && !u.hash
      && !isIP(u.hostname) && !u.hostname.includes(':') && u.hostname.includes('.')
      && !/(^|\.)(localhost|local|internal|invalid|test)$/.test(u.hostname);
  } catch { return false; }
}

function requestFor(model, input) {
  if (!MODELS.has(model)) fail('Unsupported model. Use a model listed by --help.');
  if (!object(input)) fail('Request must be a JSON object.');
  if (model === 'wavespeed-ai/image-background-remover') {
    if (Object.keys(input).some((key) => key !== 'image') || !publicHttps(input.image)) {
      fail('Background removal requires only image: a public HTTPS image URL (no credentials, IP literals, or data URI).');
    }
    return { image: input.image };
  }
  const editing = model === EDIT_MODEL;
  const allowed = new Set(['prompt', 'aspect_ratio', 'resolution', 'output_format', 'prompt_optimization_mode']);
  if (editing) allowed.add('images');
  if (Object.keys(input).some((key) => !allowed.has(key))) fail('Unsupported generation request field.');
  if (typeof input.prompt !== 'string' || !input.prompt.trim() || input.prompt.length > 20000) fail('A nonempty prompt of at most 20000 characters is required.');
  if (editing && (!Array.isArray(input.images) || input.images.length < 1 || input.images.length > 10 || !input.images.every(publicHttps))) {
    fail('Edit requires images: an array of 1 to 10 public HTTPS image URLs (no credentials, IP literals, or data URIs).');
  }
  const result = { ...(editing ? {} : { aspect_ratio: '1:1' }), resolution: '1k', output_format: 'png', prompt_optimization_mode: 'standard', ...input };
  if ((Object.hasOwn(result, 'aspect_ratio') && !['1:1', '1:2', '2:1', '1:3', '3:1', '2:3', '3:2', '3:4', '4:3', '4:5', '5:4', '9:16', '16:9', '9:21', '21:9'].includes(result.aspect_ratio))
      || !['1k', '1.5k', '2k'].includes(result.resolution)
      || result.output_format !== 'png'
      || !['standard', 'fast'].includes(result.prompt_optimization_mode)) {
    fail('Invalid generation options. Use a documented aspect ratio, 1k/1.5k/2k resolution, png output, and standard/fast optimization.');
  }
  return result;
}

async function readJson(path, label) {
  try {
    const contents = await readFile(path, 'utf8');
    if (contents.length > 1024 * 1024) fail(`${label} exceeds 1 MiB.`);
    return JSON.parse(contents.replace(/^\uFEFF/, ''));
  } catch (error) {
    if (error instanceof CliError) throw error;
    fail(`Cannot read ${label} as JSON.`);
  }
}

async function save(path, job, exclusive = false) {
  const target = exclusive ? path : `${path}.${randomUUID()}.tmp`;
  let handle;
  try {
    handle = await open(target, 'wx', 0o600);
    await handle.writeFile(`${JSON.stringify(job, null, 2)}\n`);
    await handle.sync();
    await handle.close();
    handle = undefined;
    if (!exclusive) await rename(target, path);
  } catch (error) {
    await handle?.close().catch(() => {});
    if (!exclusive) await unlink(target).catch(() => {});
    if (exclusive && error.code === 'EEXIST') fail('Job file already exists; resume it or choose a new path. No submission was made.');
    throw new CliError('Cannot persist job state. Stop and inspect the job file before any new submission.');
  }
}

function readState(value) {
  if (!object(value) || value.version !== 1 || !MODELS.has(value.model)) fail('Invalid job file version or model.');
  if (!taskId(value.id)) fail('Job has no valid task ID. Submission may have been accepted: inspect provider history before creating another job.');
  if (typeof value.createdAt !== 'string' || !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$/.test(value.createdAt)
      || !Number.isFinite(Date.parse(value.createdAt))
      || typeof value.requestHash !== 'string' || !/^[a-f0-9]{64}$/.test(value.requestHash)) fail('Invalid job metadata.');
  // Whitelist fields so edited files cannot inject request bodies or keys into output.
  return { version: 1, model: value.model, createdAt: value.createdAt, requestHash: value.requestHash, id: value.id, status: 'resuming', outputs: [] };
}

function resultState(data, id, key) {
  if (!object(data) || !taskId(data.id) || data.id !== id) throw new CliError('API response has a missing or mismatched task ID. Resume the saved job to check its result.');
  if (!ACTIVE.has(data.status) && !FAILED.has(data.status) && data.status !== 'completed') throw new CliError('API response has an unknown status. Resume the saved job later.');
  let outputs = [];
  if (data.status === 'completed') {
    if (!Array.isArray(data.outputs) || !data.outputs.length || !data.outputs.every((url) => publicHttps(url) && !url.includes(key))) {
      throw new CliError('Completed response has no valid HTTPS output URLs. Inspect the saved task in provider history.');
    }
    outputs = data.outputs;
  }
  return { status: data.status, outputs };
}

/** Dependency injection keeps tests offline; only env.WAVESPEED_API_KEY supplies auth. */
export async function runCli(argv, dependencies = {}) {
  const {
    env = process.env, fetch: fetchImpl = globalThis.fetch,
    sleep = (ms) => new Promise((done) => setTimeout(done, ms)), now = Date.now,
    stdout = (text) => process.stdout.write(text), stderr = (text) => process.stderr.write(text),
    pollIntervalMs = 2000, requestTimeoutMs = 30000, maxGetRetries = 4,
  } = dependencies;
  try {
    if (argv.length === 1 && ['--help', '-h'].includes(argv[0])) { stdout(HELP); return 0; }
    const args = [...argv];
    let timeoutMs = 300000;
    const option = args.indexOf('--timeout-ms');
    if (option !== -1) {
      if (option !== args.length - 2 || !/^\d+$/.test(args[option + 1])) fail('Place --timeout-ms N at the end (1 to 3600000 ms).');
      timeoutMs = Number(args[option + 1]);
      args.splice(option);
      if (!Number.isSafeInteger(timeoutMs) || timeoutMs < 1 || timeoutMs > 3600000) fail('Timeout must be 1 to 3600000 ms.');
    }
    const [command, modelOrFile, inputFile, outputFile] = args;
    if (!((command === 'submit' && args.length === 4) || (command === 'resume' && args.length === 2))) fail(HELP.trim());
    const key = env.WAVESPEED_API_KEY;
    if (typeof key !== 'string' || !key.trim() || /[\r\n]/.test(key)) fail('Set WAVESPEED_API_KEY in the environment before running this command.');
    const jobFile = resolve(command === 'submit' ? outputFile : modelOrFile);
    const deadline = now() + timeoutMs;
    let job;

    async function request(method, path, body) {
      const remaining = deadline - now();
      if (remaining <= 0) return { timeout: true };
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), Math.min(requestTimeoutMs, remaining));
      try {
        const response = await fetchImpl(`${API}/${path}`, {
          method, redirect: 'error', signal: controller.signal,
          headers: { Authorization: `Bearer ${key}`, ...(body ? { 'Content-Type': 'application/json' } : {}) },
          ...(body ? { body } : {}),
        });
        if (!response.ok) return { http: response.status, retry: response.status === 408 || response.status === 429 || response.status >= 500 };
        let envelope;
        try { envelope = await response.json(); } catch { return { invalid: true }; }
        return { data: envelope?.data };
      } catch { return { network: true, retry: true }; }
      finally { clearTimeout(timer); }
    }

    if (command === 'submit') {
      const body = JSON.stringify(requestFor(modelOrFile, await readJson(inputFile, 'request file')));
      job = { version: 1, model: modelOrFile, createdAt: new Date(now()).toISOString(), requestHash: createHash('sha256').update(body).digest('hex'), id: null, status: 'submitting', outputs: [] };
      await save(jobFile, job, true); // Reserve the path before any paid operation.
      const response = await request('POST', modelOrFile, body);
      if (!taskId(response.data?.id)) {
        job.status = 'submission_unknown';
        await save(jobFile, job);
        throw new CliError(`${response.http ? `Submission HTTP ${response.http}. ` : ''}No valid task ID received. Submission was not retried and may have been accepted. Inspect provider history before submitting again.`);
      }
      job.id = response.data.id;
      job.status = 'submitted';
      await save(jobFile, job); // Persist ID before parsing status or polling.
      Object.assign(job, resultState(response.data, job.id, key));
      await save(jobFile, job);
    } else {
      job = readState(await readJson(jobFile, 'job file'));
    }

    let retries = 0;
    while (true) {
      if (job.status === 'completed') { stdout(`${JSON.stringify({ id: job.id, status: job.status, outputs: job.outputs }, null, 2)}\n`); return 0; }
      if (FAILED.has(job.status)) throw new CliError(`Task ${job.id} ended with status ${job.status}. No new job was submitted.`);
      if (now() >= deadline) {
        stderr(`Polling timed out. Task ${job.id} was not cancelled. Run resume with the same job file; do not submit again.\n`);
        return 3;
      }
      if (job.status !== 'resuming') await sleep(Math.min(pollIntervalMs, deadline - now()));
      const response = await request('GET', `predictions/${job.id}/result`);
      if (response.timeout) continue;
      if (response.retry && retries < maxGetRetries) {
        await sleep(Math.min(1000 * (2 ** retries++), Math.max(0, deadline - now())));
        continue;
      }
      if (!response.data) throw new CliError(`${response.http ? `Result HTTP ${response.http}. ` : 'Could not read result. '}Resume the same job file; no new job was submitted.`);
      retries = 0;
      Object.assign(job, resultState(response.data, job.id, key));
      await save(jobFile, job);
    }
  } catch (error) {
    stderr(`${error instanceof CliError ? error.message : 'Operation failed. Inspect the saved job before submitting again.'}\n`);
    return error instanceof CliError ? error.code : 1;
  }
}

if (process.argv[1] && import.meta.url === pathToFileURL(resolve(process.argv[1])).href) {
  process.exitCode = await runCli(process.argv.slice(2));
}
