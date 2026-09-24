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

test('source checkout exposes only the I2V character-animation production route', async () => {
  for (const retired of [
    'skills/directional-sprite-authoring/references/poses.md',
    'examples/new-village/art/provenance/generation-5-prompt.txt',
    'examples/new-village/art/provenance/generation-9-prompt.txt',
    'examples/pixel-borough/art/originals/explorer.request.json',
    'examples/pixel-borough/art/originals/creatures.request.json',
  ]) await assert.rejects(readFile(join(root, retired)));

  const preparer = await readFile(join(root, 'skills/game-asset-generation/scripts/prepare-request.py'), 'utf8');
  assert.doesNotMatch(preparer, /def load_receipt|identitySelections|spec\["matrix"\]|DIRECTIONS\s*=/);
  const characterSkill = await readFile(join(root, 'skills/directional-sprite-authoring/SKILL.md'), 'utf8');
  assert.match(characterSkill, /one production route:[\s\S]*image-to-video/);
  assert.match(characterSkill, /video-background-remover[\s\S]*image-background-remover[\s\S]*unkeyed source frames/);
  const packer = await readFile(join(root, 'skills/directional-sprite-authoring/scripts/pack-sprites.py'), 'utf8');
  assert.match(packer, /origin\.kind must be video-extraction or static-facing/);
  assert.match(packer, /static-facing origin is only valid for one-frame idle clips/);
});

test('tileset skill names the composed-ground pipeline and does not treat the bed helper as a missing world', async () => {
  const skill = await readFile(join(root, 'skills/consistent-tileset-authoring/SKILL.md'), 'utf8');
  assert.match(skill, /Pick one assembly route/);
  assert.match(skill, /render-layout\.mjs[\s\S]*inspect-registration\.py[\s\S]*prepare-ground\.py[\s\S]*bind-ground\.mjs[\s\S]*inspect-ground-support\.py/);
  assert.match(skill, /A host `tools\/` copy of the four composed-ground scripts is duplication, not a gap/);
  const landscape = await readFile(join(root, 'skills/consistent-tileset-authoring/references/landscape-composition.md'), 'utf8');
  assert.match(landscape, /That limit applies\s+to `prepare-bed-tileset\.mjs` only/);
  const prompts = await readFile(join(root, 'skills/consistent-tileset-authoring/references/modular-terrain-prompts.md'), 'utf8');
  assert.match(prompts, /A composed ground plate\s+does not use this file/);
});

test('composed-ground guidance keeps the measured generator behaviour future agents need', async () => {
  const skill = await readFile(join(root, 'skills/consistent-tileset-authoring/SKILL.md'), 'utf8');
  assert.match(skill, /Registration answers a measurement\s+rather than running by default/);
  const ground = await readFile(join(root, 'skills/consistent-tileset-authoring/references/composed-ground.md'), 'utf8');
  assert.match(ground, /aspect ratio the provider actually offers/);
  assert.match(ground, /Never enlarge a plate\s+to reach delivery size/);
  assert.match(ground, /A declared region came back smaller in\s+every plate and larger in none/);
  assert.match(ground, /gate on the area ratio, not only on boundary position/);
  const provider = await readFile(join(root, 'skills/game-asset-generation/references/wavespeed.md'), 'utf8');
  assert.match(provider, /A local reference such as a layout guide needs a public URL first/);
  assert.match(provider, /one sample per setting/);
});

test('pipeline methods land in packaged skills without lab paths', async () => {
  const scenery = await readFile(join(root, 'skills/game-asset-generation/references/in-situ-scenery.md'), 'utf8');
  assert.match(scenery, /pass` \/ `fail` \/ `uncertain/);
  assert.match(scenery, /Do not decide identity from\s+color, size, filename order or spatial heuristics/);
  assert.match(scenery, /candidate-and-reviewer assignment step remains mandatory/);
  assert.match(scenery, /Do not paste cutouts into the plate for the playable scene/);
  assert.match(scenery, /multi-tile-asset-assembly/);
  assert.match(scenery, /does not reconstruct what they covered/);
  assert.doesNotMatch(scenery, /pipelines\/|huecki|waldlicht/i);

  const service = await readFile(join(root, 'skills/directional-sprite-authoring/references/animation-service.md'), 'utf8');
  assert.match(service, /not motion acceptance/);
  assert.match(service, /mirror` \| Excluded/);
  assert.match(service, /animation-pipeline-atlas-v1[\s\S]*preview only/);
  assert.match(service, /prediction IDs, never the service job ID/);
  assert.match(service, /remove_background` \(paid\) \| Skip for framework hosts/);
  assert.doesNotMatch(service, /pipelines\/|huecki|\/root\/services/i);

  const support = await readFile(join(root, 'skills/consistent-tileset-authoring/references/ground-support.md'), 'utf8');
  assert.match(support, /Optional, unvalidated for terrain/);
  assert.match(support, /never use it as collision or to edit the frozen layout/);

  const generation = await readFile(join(root, 'skills/game-asset-generation/SKILL.md'), 'utf8');
  assert.match(generation, /in-situ-scenery\.md/);
  const character = await readFile(join(root, 'skills/directional-sprite-authoring/SKILL.md'), 'utf8');
  assert.match(character, /animation-service\.md/);
  const tileset = await readFile(join(root, 'skills/consistent-tileset-authoring/SKILL.md'), 'utf8');
  assert.match(tileset, /in-situ-scenery\.md/);
});

test('packed consumer archive contains only consumer docs and skill tooling', () => {
  const listing = spawnSync('tar', ['-tf', archive], { cwd: root, encoding: 'utf8' });
  assert.equal(listing.status, 0, listing.stderr);
  const files = listing.stdout.split(/\r?\n/).filter(Boolean);
  assert.ok(files.includes('package/templates/game/PROJECT_CONTRACT.md'));
  assert.ok(files.includes('package/skills/isometric-visual-loop/SKILL.md'));
  assert.ok(files.includes('package/skills/isometric-visual-loop/scripts/verify-world.py'));
  assert.ok(files.includes('package/skills/isometric-visual-loop/scripts/asset_provenance.py'));
  assert.ok(files.includes('package/skills/isometric-visual-loop/references/asset-policy.md'));
  assert.ok(!files.some(file => /walk-templates|mannequin/i.test(file)));
  assert.ok(files.includes('package/skills/directional-sprite-authoring/scripts/extract-video.py'));
  assert.ok(!files.includes('package/skills/directional-sprite-authoring/scripts/mirror-frames.py'));
  assert.ok(files.includes('package/skills/directional-sprite-authoring/scripts/pack-sprites.py'));
  assert.ok(files.includes('package/skills/directional-sprite-authoring/references/video-to-sprites.md'));
  assert.ok(files.includes('package/skills/directional-sprite-authoring/references/motion-review.md'));
  assert.ok(files.includes('package/skills/directional-sprite-authoring/references/animation-service.md'));
  assert.ok(files.includes('package/skills/game-asset-generation/references/in-situ-scenery.md'));
  assert.ok(!files.includes('package/skills/directional-sprite-authoring/references/poses.md'));
  assert.ok(files.includes('package/skills/directional-sprite-authoring/references/directions.md'));
  assert.ok(!files.some(file => /(^|\/)(tests|__pycache__)(\/|$)/.test(file)));
  assert.ok(!files.some(file => file.includes('examples/') || file.includes('demo/')));
  assert.ok(!files.some(file => file.includes('pipelines/')));
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
