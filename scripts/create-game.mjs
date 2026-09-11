import { cp, lstat, mkdir, readFile, readdir, rename, stat, writeFile } from 'node:fs/promises';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const frameworkRoot = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const usage = 'Usage: node scripts/create-game.mjs <destination>\nRun npm ci and npm run build:package in the framework checkout first.';
const [destination] = process.argv.slice(2);

if (!destination || process.argv.slice(2).length !== 1) {
  console.error(usage);
  process.exitCode = 1;
} else {
  const target = resolve(process.cwd(), destination);
  let targetEntries = [];
  try { targetEntries = await readdir(target); } catch (error) {
    if (error?.code !== 'ENOENT') throw error;
  }
  const existingContract = targetEntries.length === 1 && targetEntries[0] === 'PROJECT_CONTRACT.md';
  if (targetEntries.length && !existingContract) throw new Error(`Refusing to overwrite non-empty destination: ${target}`);
  if (existingContract && !(await lstat(resolve(target, 'PROJECT_CONTRACT.md'))).isFile()) {
    throw new Error(`PROJECT_CONTRACT.md must be an ordinary file: ${target}`);
  }

  const framework = JSON.parse(await readFile(resolve(frameworkRoot, 'package.json'), 'utf8'));
  const archiveName = `${framework.name.replace('@', '').replace('/', '-')}-${framework.version}.tgz`;
  const archive = resolve(frameworkRoot, archiveName);
  try { await stat(archive); } catch { throw new Error(`Missing ${archiveName}. Run npm run build:package in ${frameworkRoot} first.`); }

  await mkdir(target, { recursive: true });
  const templateRoot = resolve(frameworkRoot, 'templates', 'game');
  for (const entry of await readdir(templateRoot)) {
    if (existingContract && entry === 'PROJECT_CONTRACT.md') continue;
    await cp(resolve(templateRoot, entry), resolve(target, entry), { recursive: true, errorOnExist: true });
  }
  await rename(resolve(target, 'gitignore'), resolve(target, '.gitignore'));
  await mkdir(resolve(target, 'vendor'));
  await cp(archive, resolve(target, 'vendor', archiveName));
  const manifestPath = resolve(target, 'package.json');
  const manifest = JSON.parse(await readFile(manifestPath, 'utf8'));
  manifest.dependencies['isometric-framework'] = `file:vendor/${archiveName}`;
  await writeFile(manifestPath, `${JSON.stringify(manifest, null, 2)}\n`);
  console.log(`Created ${target}`);
  console.log('Next: cd into the game, run npm install, then npm run dev. The scaffold does not install dependencies for you.');
}
