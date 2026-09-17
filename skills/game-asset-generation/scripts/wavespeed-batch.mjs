#!/usr/bin/env node
// Node 22+, built-ins only. Runs independent jobs concurrently; a submission is never retried.
import { createHash } from 'node:crypto';
import { mkdir, readFile, stat, writeFile } from 'node:fs/promises';
import { dirname, join, resolve } from 'node:path';
import { pathToFileURL } from 'node:url';
import { requestFor, runCli } from './wavespeed.mjs';

const MAX_TRACKS = 64;
const MAX_CONCURRENCY = 8;
const DEFAULT_CONCURRENCY = 4;
const FIELDS = ['id', 'model', 'request', 'job'];
const TERMINAL = new Set(['failed', 'cancelled', 'timeout', 'deleted']);
const UNCONFIRMED = new Set(['uploading', 'submitting', 'upload_unknown', 'submission_unknown']);
const COMPLETE = 'complete';
const AMBIGUOUS = 'inspect-provider-history';
const NEXT = {
  [COMPLETE]: 'Download the outputs named in the job file, review them, then set accepted to true in this fragment.',
  [AMBIGUOUS]: 'The submission outcome is unknown and was not retried. Inspect provider history for this request before creating any new job.',
  'task-failed': 'The provider rejected or dropped the task. Decide on a new request; do not resubmit this job file.',
  'resume-required': 'The remote task is still running and was not cancelled. Resume this batch; do not submit again.',
  'local-input-error': 'Nothing was submitted. Fix the local input and use a new job path.',
  'missing-job': 'No job file exists for this track; it was never submitted.',
  'not-started': 'The batch stopped before this track; nothing was submitted for it.',
  unknown: 'Inspect the job file and provider history before any new submission.',
};
const HELP = `Usage:
  node wavespeed-batch.mjs run batch.json results/ --approve N [--timeout-ms N]
  node wavespeed-batch.mjs resume batch.json results/ [--timeout-ms N]

Runs the independent jobs of a batch manifest concurrently, each with its own
request and job file, and writes one result fragment per track. It writes nothing
shared: merge the fragments into a runtime manifest, binding or coverage ledger in
a separate sequential step, so no in-flight production check sees a half-written
input.

--approve N must equal the number of tracks; it authorizes exactly that many
billable submissions. A money ceiling comes from the provider's current estimate,
not from this script. More than one track additionally requires an accepted pilot
fragment of the same model and request shape, because fanning out multiplies
rejected art as fast as accepted art.

Concurrency defaults to ${DEFAULT_CONCURRENCY} and is capped at ${MAX_CONCURRENCY}: a rejected POST cannot be
retried here, so a rate limit becomes a task whose outcome must be inspected by
hand rather than an error that can be repeated away.

Resume queries the saved predictions of an earlier batch without submitting
anything, for tracks whose polling budget ran out. It needs no approval.

Exit codes: 0 every track completed, 1 a task failed or its submission outcome is
unknown, 2 invalid local input, 3 a track needs resuming. Only an unknown outcome
stops further launches; a failed task leaves the other tracks running.
`;

class BatchError extends Error {
  constructor(message, code = 2) { super(message); this.code = code; }
}
const fail = (message, code = 2) => { throw new BatchError(message, code); };
const object = (value) => value !== null && typeof value === 'object' && !Array.isArray(value);
const integer = (value, min, max) => Number.isSafeInteger(value) && value >= min && value <= max;
const exists = (path) => stat(path).then(() => true, () => false);

function relative(base, name, label) {
  if (typeof name !== 'string' || !name || name.length > 1024 || /[\\:]/.test(name)
      || name.startsWith('/') || name.split('/').includes('..')) {
    fail(`${label} must be a relative forward-slash path inside the batch directory.`);
  }
  return resolve(base, name);
}

async function readJson(path, label, limit = 1024 * 1024) {
  let contents;
  try { contents = await readFile(path, 'utf8'); } catch { fail(`Cannot read ${label}.`); }
  if (contents.length > limit) fail(`${label} exceeds ${limit} bytes.`);
  try { return JSON.parse(contents.replace(/^\uFEFF/, '')); } catch { fail(`Cannot parse ${label} as JSON.`); }
}

async function digest(path) {
  return createHash('sha256').update(await readFile(path)).digest('hex');
}

/** Validates the whole manifest before the caller spends anything on its first track. */
async function plan(manifestPath, billable) {
  const base = dirname(resolve(manifestPath));
  const manifest = await readJson(manifestPath, 'batch manifest');
  if (!object(manifest) || manifest.version !== 1) fail('Batch manifest needs version 1.');
  if (!Array.isArray(manifest.tracks) || !integer(manifest.tracks.length, 1, MAX_TRACKS)) {
    fail(`Batch manifest needs 1 to ${MAX_TRACKS} tracks.`);
  }
  const concurrency = manifest.concurrency ?? DEFAULT_CONCURRENCY;
  if (!integer(concurrency, 1, MAX_CONCURRENCY)) {
    fail(`concurrency must be 1 to ${MAX_CONCURRENCY}; unbounded fan-out turns a provider rate limit into unknown submissions.`);
  }
  const tracks = [], names = new Set(), jobs = new Set();
  for (const entry of manifest.tracks) {
    if (!object(entry) || Object.keys(entry).length !== FIELDS.length || FIELDS.some((key) => !(key in entry))) {
      fail(`Each track needs only ${FIELDS.join(', ')}.`);
    }
    if (typeof entry.id !== 'string' || !/^[a-z0-9][a-z0-9_-]{0,63}$/i.test(entry.id)) {
      fail('Track ids must be 1 to 64 alphanumeric characters, dashes or underscores.');
    }
    if (names.has(entry.id)) fail(`Duplicate track id: ${entry.id}`);
    names.add(entry.id);
    const request = relative(base, entry.request, `Track ${entry.id} request`);
    const job = relative(base, entry.job, `Track ${entry.id} job`);
    if (jobs.has(job)) fail(`Track ${entry.id} reuses another track's job path; concurrent tracks need their own job files.`);
    jobs.add(job);
    if (billable && await exists(job)) {
      fail(`Track ${entry.id} job file already exists; resume it or choose a new path. No submission was made.`);
    }
    // The client's own validator decides what the provider accepts; a second copy of those
    // rules here would drift. A resume must not be blocked by a local request file, because
    // its remote task is already paid for and running.
    let shape = null;
    try {
      shape = Object.keys(requestFor(entry.model, await readJson(request, `track ${entry.id} request`))).sort();
    } catch (error) {
      if (billable) fail(`Track ${entry.id}: ${error.message}`);
    }
    tracks.push({ id: entry.id, model: entry.model, request, job, jobPath: entry.job, shape });
  }
  return { base, manifest, concurrency, tracks, sha256: await digest(manifestPath) };
}

async function pilot({ base, manifest, tracks }) {
  if (tracks.length === 1) return null;
  if (manifest.pilot === undefined) {
    fail('A batch of more than one track needs pilot: the result fragment of an accepted single-track run. '
      + 'Prove the model and request shape on one track, review the downloaded art, then fan out.');
  }
  const path = relative(base, manifest.pilot, 'Batch pilot');
  const record = await readJson(path, 'pilot fragment');
  if (!object(record) || record.kind !== 'wavespeed-track-result') {
    fail('Pilot must be a track result fragment written by this script.');
  }
  if (record.disposition !== COMPLETE || record.accepted !== true) {
    fail('Pilot fragment is not an accepted completion. Download and review its output, then set accepted to true in that fragment.');
  }
  for (const track of tracks) {
    if (record.model !== track.model) {
      fail(`Pilot proved ${record.model} but track ${track.id} uses ${track.model}. Run one batch per model.`);
    }
    if (!Array.isArray(record.shape) || record.shape.join() !== (track.shape ?? []).join()) {
      fail(`Pilot proved request fields [${record.shape}] but track ${track.id} sends [${track.shape}]. `
        + 'A different request shape is a different provider request; pilot it separately.');
    }
  }
  return { path: manifest.pilot, sha256: await digest(path) };
}

/** Bounded lanes, and no new launches once an outcome is unknown. */
async function pool(tracks, limit, work) {
  const outcomes = new Array(tracks.length);
  let next = 0, halted = false;
  const lane = async () => {
    while (!halted) {
      const index = next++;
      if (index >= tracks.length) return;
      outcomes[index] = await work(tracks[index]);
      if (outcomes[index].halt) halted = true;
    }
  };
  await Promise.all(Array.from({ length: Math.min(limit, tracks.length) }, lane));
  return { outcomes, halted };
}

/**
 * The client reports one exit code for two unlike outcomes: a submission whose fate is unknown,
 * and a task that demonstrably failed. Only the first justifies stopping a batch, and the job
 * file it persisted is what tells them apart.
 */
function disposition(code, job) {
  if (code === 0) return COMPLETE;
  if (code === 2) return 'local-input-error';
  if (code === 3) return 'resume-required';
  if (code !== 1) return 'unknown';
  const status = object(job) && typeof job.status === 'string' ? job.status : null;
  if (!object(job) || typeof job.id !== 'string' || UNCONFIRMED.has(status)) return AMBIGUOUS;
  if (TERMINAL.has(status)) return 'task-failed';
  return 'resume-required';
}

function fragmentFor(track, mode, code, job, startedAt, completedAt) {
  const verdict = disposition(code, job);
  // No output URLs and no request body: the URLs are signed and expiring, and provenance is
  // meant to carry the prediction ID plus local hashes of what was actually downloaded.
  return {
    kind: 'wavespeed-track-result',
    track: track.id,
    model: track.model,
    shape: track.shape,
    mode,
    job: track.jobPath,
    exitCode: code,
    disposition: verdict,
    nextAction: NEXT[verdict],
    status: object(job) && typeof job.status === 'string' ? job.status : null,
    predictionId: object(job) && typeof job.id === 'string' ? job.id : null,
    requestHash: object(job) && typeof job.requestHash === 'string' ? job.requestHash : null,
    outputCount: object(job) && Array.isArray(job.outputs) ? job.outputs.length : 0,
    startedAt,
    completedAt,
    accepted: false,
  };
}

export async function runBatch(argv, dependencies = {}) {
  const {
    stdout = (text) => process.stdout.write(text),
    stderr = (text) => process.stderr.write(text),
    now = Date.now, client = (args) => runCli(args),
  } = dependencies;
  try {
    if (argv.length === 1 && ['--help', '-h'].includes(argv[0])) { stdout(HELP); return 0; }
    const args = [...argv];
    const rest = [];
    let timeoutMs = 300000, approve = null;
    const given = new Set();
    while (args.length) {
      const token = args.shift();
      if (token === '--timeout-ms' || token === '--approve') {
        // An authorization that appears twice has no single meaning; refuse rather than pick one.
        if (given.has(token)) fail(`${token} was given more than once.`);
        given.add(token);
        const raw = args.shift();
        if (!/^(0|[1-9]\d{0,8})$/.test(raw ?? '')) fail(`${token} needs a whole number without leading zeros.`);
        if (token === '--timeout-ms') timeoutMs = Number(raw); else approve = Number(raw);
      } else rest.push(token);
    }
    if (!integer(timeoutMs, 1, 3600000)) fail('Timeout must be 1 to 3600000 ms.');
    const [mode, manifestPath, output] = rest;
    if (rest.length !== 3 || !['run', 'resume'].includes(mode)) fail(HELP.trim());

    const prepared = await plan(manifestPath, mode === 'run');
    if (mode === 'run') {
      if (approve !== prepared.tracks.length) {
        fail(`This batch would submit ${prepared.tracks.length} billable jobs. Pass --approve ${prepared.tracks.length} to authorize exactly that many.`);
      }
    } else if (approve !== null) {
      fail('Resume submits nothing, so it takes no --approve.');
    }
    const proven = mode === 'run' ? await pilot(prepared) : null;

    const directory = resolve(output);
    if (await exists(directory)) fail('Results directory already exists; every attempt needs its own, so earlier evidence is never overwritten.');
    await mkdir(directory, { recursive: true });

    const startedAt = new Date(now()).toISOString();
    const { outcomes, halted } = await pool(prepared.tracks, prepared.concurrency, async (track) => {
      const began = new Date(now()).toISOString();
      if (mode === 'resume' && !await exists(track.job)) {
        return { fragment: { ...fragmentFor(track, mode, null, null, began, began), disposition: 'missing-job', nextAction: NEXT['missing-job'] } };
      }
      const code = await client(mode === 'run'
        ? ['submit', track.model, track.request, track.job, '--timeout-ms', String(timeoutMs)]
        : ['resume', track.job, '--timeout-ms', String(timeoutMs)]);
      let job = null;
      try { job = JSON.parse(await readFile(track.job, 'utf8')); } catch { /* the client reported why; the fragment records the absence */ }
      const fragment = fragmentFor(track, mode, code, job, began, new Date(now()).toISOString());
      // Only an unknown submission outcome stops the batch. A rate limit arrives as exactly this,
      // and each further launch would add another task whose fate has to be inspected by hand.
      return { fragment, halt: mode === 'run' && fragment.disposition === AMBIGUOUS };
    });

    const entries = [];
    for (const [index, track] of prepared.tracks.entries()) {
      const fragment = outcomes[index]?.fragment ?? {
        ...fragmentFor(track, mode, null, null, startedAt, startedAt),
        disposition: 'not-started', nextAction: NEXT['not-started'],
      };
      await mkdir(join(directory, track.id), { recursive: true });
      const path = join(directory, track.id, 'result.json');
      await writeFile(path, `${JSON.stringify(fragment, null, 2)}\n`, { encoding: 'utf8', flag: 'wx' });
      entries.push({ track: track.id, disposition: fragment.disposition, fragment: `${track.id}/result.json` });
    }

    const report = {
      kind: 'wavespeed-batch-report',
      mode,
      batchSha256: prepared.sha256,
      pilot: proven,
      approved: approve,
      concurrency: prepared.concurrency,
      timeoutMs,
      halted,
      startedAt,
      completedAt: new Date(now()).toISOString(),
      tracks: entries,
      scope: 'provider-jobs-only',
      merge: 'Fragments are per-track. Update the runtime manifest, binding and coverage ledger in one sequential step.',
    };
    await writeFile(join(directory, 'batch.json'), `${JSON.stringify(report, null, 2)}\n`, { encoding: 'utf8', flag: 'wx' });
    stdout(`${JSON.stringify(report, null, 2)}\n`);

    const seen = new Set(entries.map((entry) => entry.disposition));
    if (seen.has(AMBIGUOUS) || seen.has('task-failed')) return 1;
    if (['local-input-error', 'missing-job', 'not-started', 'unknown'].some((name) => seen.has(name))) return 2;
    if (seen.has('resume-required')) return 3;
    return 0;
  } catch (error) {
    stderr(`${error instanceof BatchError ? error.message : 'Batch failed. Inspect the saved job files before any new submission.'}\n`);
    return error instanceof BatchError ? error.code : 1;
  }
}

if (process.argv[1] && import.meta.url === pathToFileURL(resolve(process.argv[1])).href) {
  process.exitCode = await runBatch(process.argv.slice(2));
}
