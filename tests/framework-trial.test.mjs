import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, mkdir, writeFile, readFile, access, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { prepareTrial, recordEvent, trialStatus } from '../scripts/framework-trial.mjs';

async function fixture(t) {
  const root = await mkdtemp(path.join(tmpdir(), 'framework-trial-'));
  t.after(() => rm(root, { recursive: true, force: true }));
  const framework = path.join(root, 'framework');
  for (const [name, text] of Object.entries({ 'package.json': '{}', 'AGENTS.md': 'rules',
    'src/index.ts': 'export {};', 'skills/README.md': 'catalog',
    'examples/old/art.png': 'EXCLUDED', 'docs/OLD_TRIAL.md': 'EXCLUDED',
    'docs/evidence/old.png': 'EXCLUDED', 'skills/demo/__pycache__/old.pyc': 'EXCLUDED' })) {
    const file = path.join(framework, name); await mkdir(path.dirname(file), { recursive: true }); await writeFile(file, text);
  }
  const contract = path.join(root, 'contract.md'), reference = path.join(root, 'style.png');
  await writeFile(contract, 'Original scope'); await writeFile(reference, 'reference bytes');
  return { framework, contract, references: [reference], out: path.join(root, 'trial') };
}

test('snapshot excludes hosts/history/cache, preserves inputs and refuses overwrite', async t => {
  const options = await fixture(t), result = await prepareTrial(options);
  assert.equal(await readFile(path.join(result.workspace, 'PROJECT_CONTRACT.md'), 'utf8'), 'Original scope');
  assert.equal(await readFile(path.join(result.workspace, result.references[0]), 'utf8'), 'reference bytes');
  for (const name of ['examples', 'docs/OLD_TRIAL.md', 'docs/evidence', 'skills/demo/__pycache__']) await assert.rejects(access(path.join(result.workspace, name)));
  assert.equal((await trialStatus(options.out)).mode, 'awaiting-builder-session');
  await assert.rejects(prepareTrial(options), /EEXIST/);
});

test('session, assistance and observed timestamps are explicit', async t => {
  const options = await fixture(t); await prepareTrial(options);
  const before = Date.now();
  const event = await recordEvent(options.out, { kind: 'session', actor: 'builder', agentId: 'session-1', model: 'selected-model', note: 'Fresh agent launched separately' });
  assert.ok(Date.parse(event.observedAt) >= before);
  assert.equal((await trialStatus(options.out)).mode, 'no-assistance-recorded');
  await assert.rejects(recordEvent(options.out, { kind: 'session', actor: 'builder', note: 'missing identity' }), /agent ID/);
  await assert.rejects(recordEvent(options.out, { kind: 'intervention', actor: 'supervisor', note: 'help', observedAt: 'yesterday' }), /Unknown/);
  await recordEvent(options.out, { kind: 'intervention', actor: 'supervisor', note: 'Provided host implementation recipe' });
  assert.equal((await trialStatus(options.out)).mode, 'assisted');
});

test('framework changes require a recorded version; contract changes remain visible', async t => {
  const options = await fixture(t); const { workspace } = await prepareTrial(options);
  await writeFile(path.join(workspace, 'src/index.ts'), 'export const fixed = true;');
  await writeFile(path.join(workspace, 'src/helper.ts'), 'export {};');
  await writeFile(path.join(workspace, 'PROJECT_CONTRACT.md'), 'Reduced scope');
  let status = await trialStatus(options.out);
  assert.deepEqual(status.unrecordedFrameworkChanges.sort(), ['src/helper.ts', 'src/index.ts']);
  assert.deepEqual(status.inputChanges, ['PROJECT_CONTRACT.md']);
  await recordEvent(options.out, { kind: 'framework-update', actor: 'supervisor', cause: 'framework-gap', note: 'General adapter repaired and tested' });
  status = await trialStatus(options.out);
  assert.equal(status.frameworkVersions, 2); assert.deepEqual(status.unrecordedFrameworkChanges, []);
  assert.deepEqual(status.inputChanges, ['PROJECT_CONTRACT.md']);
});

test('event edits invalidate subsequent hash links', async t => {
  const options = await fixture(t); await prepareTrial(options);
  for (let i = 0; i < 2; i++) await recordEvent(options.out, { kind: 'checkpoint', actor: 'reviewer', checkpoint: 'layout', verdict: 'fail', note: 'Disconnected stream' });
  const file = path.join(options.out, 'events/000001.json');
  await writeFile(file, (await readFile(file, 'utf8')).replace('Disconnected stream', 'Accepted stream'));
  await assert.rejects(trialStatus(options.out), /chain changed/);
});

test('ignored trial output inside checkout is allowed, copied source trees are not', async t => {
  const options = await fixture(t);
  for (const tree of ['src', 'skills', 'docs', 'scripts']) {
    await assert.rejects(prepareTrial({ ...options, out: path.join(options.framework, tree, 'trial') }), /outside copied/);
  }
  const out = path.join(options.framework, 'test-results', 'trial');
  await prepareTrial({ ...options, out });
  assert.equal((await trialStatus(out)).mode, 'awaiting-builder-session');
});
