#!/usr/bin/env node
// Node 22+, built-ins only. Host-scoped I2V submission for the Quellbrunn traveler.
// wavespeed-ai/wan-2.2/image-to-video is not in the shared skill client's MODELS
// allowlist (that client intentionally does not generate video); this script
// checks the model's current documented schema itself (recorded 2026-09-20
// against https://wavespeed.ai/docs/docs-api/wavespeed-ai/wan-2.2-image-to-video)
// and follows the same safety pattern: bounded local PNG, no key logging,
// public-HTTPS-only inputs, one non-retried billable POST, job state persisted
// before and after submission so a resume never resubmits.
import { createHash, randomUUID } from 'node:crypto';
import { readFile, open, rename, unlink } from 'node:fs/promises';
import { isIP } from 'node:net';
import { resolve } from 'node:path';
import { pathToFileURL } from 'node:url';

const API = 'https://api.wavespeed.ai/api/v3';
const MODEL = 'wavespeed-ai/wan-2.2/image-to-video';
const FAILED = new Set(['failed', 'cancelled', 'timeout', 'deleted']);
const ACTIVE = new Set(['created', 'pending', 'queued', 'processing', 'running']);
const HELP = `Usage:
  node i2v-wan22.mjs submit still.png prompt.txt job.json [--timeout-ms N]
  node i2v-wan22.mjs resume job.json [--timeout-ms N]

Requires WAVESPEED_API_KEY. Never logs the key or request body.
Exit codes: 0 completed, 1 remote/persistence error, 2 local input error, 3 polling timeout.
`;

class CliError extends Error { constructor(message, code = 1) { super(message); this.code = code; } }
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

// WaveSpeed's own I2V docs recommend JPG or PNG (and warn away from WEBP), so
// this validator accepts either real signature rather than assuming PNG.
function isBoundedPng(bytes) {
  return bytes.length >= 33 && bytes.subarray(0, 8).equals(Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]))
    && bytes.readUInt32BE(8) === 13 && bytes.subarray(12, 16).toString('ascii') === 'IHDR'
    && bytes.readUInt32BE(16) >= 1 && bytes.readUInt32BE(16) <= 8192
    && bytes.readUInt32BE(20) >= 1 && bytes.readUInt32BE(20) <= 8192;
}
function isBoundedJpeg(bytes) {
  return bytes.length >= 4 && bytes[0] === 0xff && bytes[1] === 0xd8
    && bytes[bytes.length - 2] === 0xff && bytes[bytes.length - 1] === 0xd9;
}
async function localImage(path) {
  let bytes;
  try { bytes = await readFile(path); } catch { fail('Cannot read local image.'); }
  if (bytes.length > 32 * 1024 * 1024 || !(isBoundedPng(bytes) || isBoundedJpeg(bytes))) {
    fail('Local image input must be a bounded PNG or JPEG.');
  }
  return { bytes, contentType: isBoundedPng(bytes) ? 'image/png' : 'image/jpeg', ext: isBoundedPng(bytes) ? 'png' : 'jpg' };
}

async function readText(path, label, maxBytes) {
  let contents;
  try { contents = await readFile(path, 'utf8'); } catch { fail(`Cannot read ${label}.`); }
  if (contents.length > maxBytes) fail(`${label} exceeds ${maxBytes} bytes.`);
  const trimmed = contents.replace(/^\uFEFF/, '').trim();
  if (!trimmed) fail(`${label} is empty.`);
  return trimmed;
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
  if (!object(value) || value.version !== 1 || value.model !== MODEL) fail('Invalid job file version or model.');
  if (!taskId(value.id)) fail('Job has no valid task ID. Submission may have been accepted: inspect provider history before creating another job.');
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
    const [command, a, b, c] = args;
    if (!((command === 'submit' && args.length === 4) || (command === 'resume' && args.length === 2))) fail(HELP.trim());
    const key = env.WAVESPEED_API_KEY;
    if (typeof key !== 'string' || !key.trim() || /[\r\n]/.test(key)) fail('Set WAVESPEED_API_KEY in the environment before running this command.');
    const jobFile = resolve(command === 'submit' ? c : a);
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
        if (!response.ok) return { http: response.status, retry: response.status === 408 || response.status === 429 || response.status >= 500, text: await response.text().catch(() => '') };
        let envelope;
        try { envelope = await response.json(); } catch { return { invalid: true }; }
        return { data: envelope?.data };
      } catch { return { network: true, retry: true }; }
      finally { clearTimeout(timer); }
    }

    async function uploadWithoutBearer(upload, bytes) {
      if (!object(upload) || upload.method !== 'PUT' || !publicHttps(upload.url) || !object(upload.headers)
          || Object.keys(upload.headers).some((name) => name.toLowerCase() === 'authorization')
          || Object.values(upload.headers).some((value) => typeof value !== 'string' || /[\r\n]/.test(value))) {
        fail('Upload ticket returned an unsafe method, URL, or header set.');
      }
      const remaining = deadline - now();
      if (remaining <= 0) fail('Timed out before upload; no I2V submission was made.');
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), Math.min(requestTimeoutMs, remaining));
      try {
        const response = await fetchImpl(upload.url, { method: upload.method, redirect: 'error', signal: controller.signal, headers: upload.headers, body: bytes });
        if (!response.ok) fail(`Upload HTTP ${response.status}; no I2V submission was made.`);
      } catch (error) {
        if (error instanceof CliError) throw error;
        fail('Upload failed; no I2V submission was made.');
      } finally { clearTimeout(timer); }
    }

    if (command === 'submit') {
      const [stillPath, promptPath] = [a, b];
      const { bytes, contentType, ext } = await localImage(stillPath);
      const prompt = await readText(promptPath, 'prompt file', 20000);
      job = { version: 1, model: MODEL, createdAt: new Date(now()).toISOString(), requestHash: '', stillSha256: createHash('sha256').update(bytes).digest('hex'), id: null, status: 'uploading', outputs: [] };
      await save(jobFile, job, true);
      const ticket = await request('POST', 'media/uploads', JSON.stringify({ filename: `still.${ext}`, size: bytes.length, content_type: contentType }));
      const upload = ticket.data?.upload;
      const fileUrl = ticket.data?.download_url;
      if (!object(upload) || !publicHttps(fileUrl)) {
        job.status = 'upload_unknown'; await save(jobFile, job);
        throw new CliError(`Upload ticket was invalid.${ticket.text ? ` ${ticket.text}` : ''}`);
      }
      await uploadWithoutBearer(upload, bytes);
      const body = JSON.stringify({ image: fileUrl, prompt, resolution: '480p', duration: 5 });
      job.requestHash = createHash('sha256').update(body).digest('hex');
      await save(jobFile, job);
      const response = await request('POST', MODEL, body);
      if (!taskId(response.data?.id)) {
        job.status = 'submission_unknown'; await save(jobFile, job);
        throw new CliError(`${response.http ? `Submission HTTP ${response.http}. ${response.text ?? ''} ` : ''}No valid task ID received. Submission was not retried and may have been accepted. Inspect provider history before submitting again.`);
      }
      job.id = response.data.id; job.status = 'submitted'; await save(jobFile, job);
      Object.assign(job, resultState(response.data, job.id, key));
      await save(jobFile, job);
    } else {
      job = readState(JSON.parse(await readFile(jobFile, 'utf8')));
    }

    let retries = 0;
    while (true) {
      if (job.status === 'completed') { stdout(`${JSON.stringify({ id: job.id, status: job.status, outputs: job.outputs }, null, 2)}\n`); return 0; }
      if (FAILED.has(job.status)) throw new CliError(`Task ${job.id} ended with status ${job.status}. No new job was submitted.`);
      if (now() >= deadline) { stderr(`Polling timed out. Task ${job.id} was not cancelled. Run resume with the same job file.\n`); return 3; }
      if (job.status !== 'resuming') await sleep(Math.min(pollIntervalMs, deadline - now()));
      const response = await request('GET', `predictions/${job.id}/result`);
      if (response.timeout) continue;
      if (response.retry && retries < maxGetRetries) { await sleep(Math.min(1000 * (2 ** retries++), Math.max(0, deadline - now()))); continue; }
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
