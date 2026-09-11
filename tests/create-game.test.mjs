import assert from 'node:assert/strict';
import { mkdtemp, readFile, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join, resolve, posix } from 'node:path';
import { spawnSync } from 'node:child_process';
import test from 'node:test';

const root = resolve(import.meta.dirname, '..');
const cli = join(root, 'scripts', 'create-game.mjs');
const framework = JSON.parse(await readFile(join(root, 'package.json'), 'utf8'));
const archiveName = `${framework.name.replace('@', '').replace('/', '-')}-${framework.version}.tgz`;
const archive = join(root, archiveName);
const run = (destination) => spawnSync(process.execPath, [cli, destination], { cwd: root, encoding: 'utf8' });

test('starter tests require a built package archive', async () => {
  try { await readFile(archive); } catch { assert.fail(`Missing ${archiveName}; run npm run build:package before npm run test:starter.`); }
});

test('starter refuses an occupied destination before requiring a package archive', async () => {
  const parent = await mkdtemp(join(tmpdir(), 'isometric-starter-'));
  try {
    const target = join(parent, 'occupied');
    await (await import('node:fs/promises')).mkdir(target);
    await writeFile(join(target, 'keep.txt'), 'keep');
    const result = run(target);
    assert.notEqual(result.status, 0);
    assert.match(result.stderr, /Refusing to overwrite non-empty destination/);
    assert.equal(await readFile(join(target, 'keep.txt'), 'utf8'), 'keep');
  } finally { await rm(parent, { recursive: true, force: true }); }
});

test('starter preserves an approved contract when it is the destination’s only file', async () => {
  const parent = await mkdtemp(join(tmpdir(), 'isometric-starter-'));
  try {
    const target = join(parent, 'approved-game');
    const approved = '# Project contract\n\nApproved scope: a small garden.\n';
    await (await import('node:fs/promises')).mkdir(target);
    await writeFile(join(target, 'PROJECT_CONTRACT.md'), approved);
    const result = run(target);
    assert.equal(result.status, 0, result.stderr);
    assert.equal(await readFile(join(target, 'PROJECT_CONTRACT.md'), 'utf8'), approved);
    await readFile(join(target, 'src', 'main.ts'));
  } finally { await rm(parent, { recursive: true, force: true }); }
});

test('starter creates a neutral self-contained host from the built package', async () => {
  const parent = await mkdtemp(join(tmpdir(), 'isometric-starter-'));
  try {
    const target = join(parent, 'my-game');
    const result = run(target);
    assert.equal(result.status, 0, result.stderr);
    const manifest = JSON.parse(await readFile(join(target, 'package.json'), 'utf8'));
    assert.equal(manifest.dependencies['isometric-framework'], `file:vendor/${archiveName}`);
    for (const file of ['index.html', 'src/main.ts', 'src/style.css', 'AGENTS.md', 'PROJECT_CONTRACT.md', '.gitignore', `vendor/${archiveName}`]) {
      await readFile(join(target, file));
    }
    assert.match(await readFile(join(target, '.gitignore'), 'utf8'), /node_modules\/\n.*dist\/\n.*test-results\/\n.*\.world-build\//s);
    assert.match(await readFile(join(target, 'PROJECT_CONTRACT.md'), 'utf8'), /single source of truth|Human requirements/);
  } finally { await rm(parent, { recursive: true, force: true }); }
});

test('packed consumer archive contains only consumer docs and skill tooling', () => {
  const listing = spawnSync('tar', ['-tf', archive], { cwd: root, encoding: 'utf8' });
  assert.equal(listing.status, 0, listing.stderr);
  const files = listing.stdout.split(/\r?\n/).filter(Boolean);
  assert.ok(files.includes('package/templates/game/PROJECT_CONTRACT.md'));
  assert.ok(files.includes('package/skills/isometric-visual-loop/SKILL.md'));
  assert.ok(files.includes('package/skills/isometric-visual-loop/scripts/verify-world.py'));
  assert.ok(!files.some(file => /(^|\/)(tests|__pycache__)(\/|$)/.test(file)));
  assert.ok(!files.some(file => file.includes('examples/') || file.includes('demo/')));
  assert.ok(!files.includes('package/AGENTS.md'));
  assert.ok(!files.some(file => /docs\/(AUTUMN_CROSSING|GENERATED_ENVIRONMENT_TRIAL|WILLOW_QUAY)\.md$/.test(file)));
  assert.ok(!files.some(file => /docs\/(history|evidence)\//.test(file)));
  assert.ok(!files.includes('package/APP_GUIDE.md'));
  assert.ok(!files.includes('package/VERIFICATION.md'));
  assert.equal(files.filter(file => /^package\/skills\/[^/]+\/SKILL\.md$/.test(file)).length, 7);
  for (const file of files.filter(file => file.endsWith('.md') && !file.startsWith('package/templates/'))) {
    const content = spawnSync('tar', ['-xOf', archive, file], { encoding: 'utf8' });
    assert.equal(content.status, 0, content.stderr);
    for (const [, target] of content.stdout.matchAll(/\]\(([^)\s]+)\)/g)) {
      if (/^(?:https?:|#|mailto:)/.test(target)) continue;
      const path = decodeURIComponent(target.split('#')[0]);
      if (!path) continue;
      const resolved = posix.normalize(posix.join(posix.dirname(file), path));
      assert.ok(files.includes(resolved) || files.some(entry => entry.startsWith(`${resolved}/`)), `${file}: missing packed link ${target}`);
    }
  }
});
