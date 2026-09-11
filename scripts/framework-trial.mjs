// Optional source-checkout trial recorder. It never launches an agent or generator.
import { createHash } from 'node:crypto';
import { copyFile, lstat, mkdir, readFile, readdir, realpath, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { pathToFileURL } from 'node:url';

const ROOT_FILES = ['package.json', 'package-lock.json', 'AGENTS.md', 'README.md',
  'PROVENANCE.md', 'tsconfig.json', 'tsconfig.build.json', 'vite.config.ts', 'scripts/check-boundaries.mjs'];
const GUIDES = ['RUNTIME_API', 'ARCHITECTURE', 'CREATE_GAME', 'ART_PIPELINE', 'AUTOTILING',
  'DEBUGGING', 'INTERACTIONS', 'INVENTORY_AND_SAVES', 'WORLD_PRODUCTION_FLOW'];
const omit = new Set(['node_modules', '__pycache__', '.git', 'test-results', '.world-build']);
const hash = bytes => createHash('sha256').update(bytes).digest('hex');
const json = file => readFile(file, 'utf8').then(JSON.parse);
const require = (ok, message) => { if (!ok) throw new Error(message); };
const inside = (root, file) => { const r = path.relative(root, file); return r !== '' && !r.startsWith(`..${path.sep}`) && r !== '..' && !path.isAbsolute(r); };
const portable = name => name.split(path.sep).join('/');

async function regular(file) {
  const info = await lstat(file);
  require(info.isFile() && !info.isSymbolicLink(), `Expected regular file: ${file}`);
  require(info.size <= 64 * 1024 * 1024, `File exceeds 64 MiB: ${file}`);
}

async function frameworkFiles(root) {
  const result = [];
  async function visit(name) {
    const file = path.join(root, name), info = await lstat(file);
    require(!info.isSymbolicLink(), `Symlinks are not copied: ${name}`);
    require(inside(root, await realpath(file)), `Source escapes framework: ${name}`);
    if (info.isDirectory()) {
      for (const item of (await readdir(file)).sort()) {
        if (!omit.has(item) && !item.endsWith('.pyc')) await visit(path.join(name, item));
      }
    } else { await regular(file); result.push(portable(name)); }
  }
  for (const name of [...ROOT_FILES, ...GUIDES.map(n => `docs/${n}.md`), 'src', 'skills']) {
    try { await visit(name); } catch (error) { if (error.code !== 'ENOENT') throw error; }
  }
  for (const name of ['package.json', 'AGENTS.md', 'src/index.ts', 'skills/README.md']) {
    require(result.includes(name), `Framework missing ${name}`);
  }
  return result.sort();
}

async function hashes(root, names) {
  const result = {};
  for (const name of names) {
    const file = path.resolve(root, name);
    require(inside(root, file), `Invalid local path: ${name}`);
    await regular(file);
    require(inside(root, await realpath(file)), `Path escapes workspace: ${name}`);
    result[name] = hash(await readFile(file));
  }
  return result;
}

export async function prepareTrial({ framework, contract, references = [], out }) {
  framework = await realpath(path.resolve(framework)); out = path.resolve(out);
  require(out !== framework && !inside(out, framework), 'Output cannot contain the source framework');
  for (const name of ['src', 'skills', 'docs', 'scripts']) {
    const tree = path.join(framework, name);
    require(out !== tree && !inside(tree, out), 'Output must be outside copied framework trees');
  }
  const names = await frameworkFiles(framework), original = await hashes(framework, names);
  const inputs = [contract, ...references];
  for (const file of inputs) await regular(path.resolve(file));
  // Exclusive creation protects previous runs; failures retain partial output for diagnosis.
  await mkdir(path.dirname(out), { recursive: true });
  await mkdir(out);
  const workspace = path.join(out, 'workspace');
  for (const name of names) {
    const dest = path.join(workspace, name);
    await mkdir(path.dirname(dest), { recursive: true });
    await copyFile(path.join(framework, name), dest);
  }
  const inputNames = ['PROJECT_CONTRACT.md'];
  await copyFile(path.resolve(contract), path.join(workspace, inputNames[0]));
  for (const [i, file] of references.entries()) {
    const name = `reference/${i + 1}-${path.basename(file)}`;
    await mkdir(path.join(workspace, 'reference'), { recursive: true });
    await copyFile(path.resolve(file), path.join(workspace, name)); inputNames.push(name);
  }
  require(JSON.stringify(await hashes(workspace, names)) === JSON.stringify(original), 'Framework changed during copy');
  const manifest = { version: 1, preparedAt: new Date().toISOString(), framework: original,
    inputs: await hashes(workspace, inputNames),
    limits: 'Fresh context and actor identity must be established by the agent launcher. This folder is not an OS sandbox.' };
  await writeFile(path.join(out, 'trial.json'), JSON.stringify(manifest, null, 2), { flag: 'wx' });
  await mkdir(path.join(out, 'events'));
  return { workspace, references: inputNames.slice(1), status: 'awaiting-builder-session' };
}

async function events(root) {
  const files = (await readdir(path.join(root, 'events'))).filter(f => /^\d{6}\.json$/.test(f)).sort();
  const result = []; let previous = null;
  for (const [i, name] of files.entries()) {
    require(name === `${String(i + 1).padStart(6, '0')}.json`, 'Event sequence has a gap');
    const bytes = await readFile(path.join(root, 'events', name)), event = JSON.parse(bytes);
    require(event.previousSha256 === previous, 'Event chain changed');
    result.push(event); previous = hash(bytes);
  }
  return { result, previous };
}

export async function recordEvent(root, supplied) {
  root = path.resolve(root);
  const manifest = await json(path.join(root, 'trial.json'));
  const allowed = new Set(['kind', 'actor', 'agentId', 'model', 'note', 'checkpoint', 'verdict', 'cause']);
  require(supplied && !Array.isArray(supplied) && Object.keys(supplied).every(k => allowed.has(k)), 'Unknown event fields');
  require(['session', 'checkpoint', 'intervention', 'framework-update'].includes(supplied.kind), 'Invalid event kind');
  require(['builder', 'reviewer', 'supervisor'].includes(supplied.actor), 'Invalid actor role');
  for (const [key, value] of Object.entries(supplied)) require(typeof value === 'string' && value.trim() && value.length <= 4000, `Invalid ${key}`);
  require(supplied.note, 'Describe the observed event');
  if (supplied.kind === 'session') require(supplied.agentId && supplied.model, 'Session needs actual agent ID and model');
  if (supplied.kind === 'checkpoint') {
    require(supplied.checkpoint && ['pass', 'fail', 'unverified'].includes(supplied.verdict), 'Checkpoint and verdict required');
  }
  if (supplied.cause) require(['framework-gap', 'instruction-conflict', 'execution-error', 'candidate-failure', 'review-error'].includes(supplied.cause), 'Invalid failure cause');
  const history = await events(root);
  const event = { ...supplied, observedAt: new Date().toISOString(), previousSha256: history.previous };
  if (supplied.kind === 'framework-update') {
    require(supplied.actor === 'supervisor', 'Framework updates belong to the supervisor');
    const workspace = path.join(root, 'workspace');
    event.framework = await hashes(workspace, await frameworkFiles(workspace));
  }
  require(manifest.version === 1, 'Unsupported trial version');
  const file = path.join(root, 'events', `${String(history.result.length + 1).padStart(6, '0')}.json`);
  await writeFile(file, JSON.stringify(event, null, 2), { flag: 'wx' });
  return event;
}

export async function trialStatus(root) {
  root = path.resolve(root);
  const manifest = await json(path.join(root, 'trial.json')), history = (await events(root)).result;
  require(manifest.version === 1, 'Unsupported trial version');
  const workspace = path.join(root, 'workspace');
  const latest = history.filter(e => e.kind === 'framework-update').at(-1)?.framework ?? manifest.framework;
  const actual = await hashes(workspace, await frameworkFiles(workspace));
  const changed = (before, after) => [...new Set([...Object.keys(before), ...Object.keys(after)])].filter(k => before[k] !== after[k]);
  const inputChanges = [];
  for (const [name, expected] of Object.entries(manifest.inputs)) {
    try { if ((await hashes(workspace, [name]))[name] !== expected) inputChanges.push(name); }
    catch { inputChanges.push(name); }
  }
  const sessions = history.filter(e => e.kind === 'session' && e.actor === 'builder');
  return { mode: history.some(e => e.kind === 'intervention') ? 'assisted' : sessions.length ? 'no-assistance-recorded' : 'awaiting-builder-session',
    sessions, frameworkVersions: 1 + history.filter(e => e.kind === 'framework-update').length,
    unrecordedFrameworkChanges: changed(latest, actual), inputChanges,
    latestCheckpoint: history.filter(e => e.kind === 'checkpoint').at(-1) ?? null,
    limits: 'Events are reported observations, not authenticated authorship. No-assistance-recorded is not proof of independence or acceptance.' };
}

async function main(args) {
  const [command, ...rest] = args;
  if (command === 'prepare') {
    const options = { references: [] };
    for (let i = 0; i < rest.length; i += 2) {
      const key = rest[i], value = rest[i + 1];
      require(['--framework', '--contract', '--reference', '--out'].includes(key) && value, 'Invalid prepare arguments');
      if (key === '--reference') options.references.push(value); else options[key.slice(2)] = value;
    }
    require(options.framework && options.contract && options.out, 'prepare needs --framework, --contract and --out');
    return prepareTrial(options);
  }
  if (command === 'record' && rest.length === 2) return recordEvent(rest[0], await json(rest[1]));
  if (command === 'status' && rest.length === 1) return trialStatus(rest[0]);
  throw new Error('Usage: framework-trial.mjs prepare --framework DIR --contract FILE [--reference FILE] --out NEW_DIR | record DIR EVENT.json | status DIR');
}

if (process.argv[1] && import.meta.url === pathToFileURL(path.resolve(process.argv[1])).href) {
  main(process.argv.slice(2)).then(value => console.log(JSON.stringify(value, null, 2)))
    .catch(error => { console.error(error.message); process.exitCode = 1; });
}
