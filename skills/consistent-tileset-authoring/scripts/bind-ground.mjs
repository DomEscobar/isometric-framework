#!/usr/bin/env node
/** Bind a prepared continuous ground plate into one public runtime texture per map cell. */
import { createHash } from 'node:crypto';
import { access, mkdir, readFile, writeFile } from 'node:fs/promises';
import { constants } from 'node:fs';
import { dirname, extname, isAbsolute, relative, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const PREFIX = 'ground-binding-';
const MAX_PNG_BYTES = 64 * 1024 * 1024;
const MAX_PNG_AXIS = 8192;
const MAX_PNG_PIXELS = 16_000_000;

function fail(message) { throw new Error(message); }
function hash(value) { return createHash('sha256').update(value).digest('hex'); }
function object(value, label) { if (!value || typeof value !== 'object' || Array.isArray(value)) fail(`${label} must be an object`); return value; }
function integer(value, label, min, max) { if (!Number.isInteger(value) || value < min || value > max) fail(`${label} must be an integer between ${min} and ${max}`); return value; }
async function exists(path) { try { await access(path, constants.F_OK); return true; } catch { return false; } }

function localPath(root, value, label) {
  if (typeof value !== 'string' || !value || isAbsolute(value) || value.includes('://') || value.startsWith('file:')) fail(`${label} must be a local relative path`);
  const path = resolve(root, value);
  if (path !== root && !path.startsWith(`${root}${String.fromCharCode(92)}`) && !path.startsWith(`${root}/`)) fail(`${label} must stay inside ${root}`);
  return path;
}

/** Read only the PNG signature and IHDR. It establishes dimensions, not pixel decoding. */
function pngHeader(bytes, label) {
  if (bytes.length > MAX_PNG_BYTES) fail(`${label} exceeds the ${MAX_PNG_BYTES} byte cap`);
  if (bytes.length < 24 || !bytes.subarray(0, 8).equals(Buffer.from([137, 80, 78, 71, 13, 10, 26, 10])) || bytes.readUInt32BE(8) !== 13 || bytes.subarray(12, 16).toString('ascii') !== 'IHDR') fail(`${label} is not a PNG with an IHDR header`);
  const width = bytes.readUInt32BE(16), height = bytes.readUInt32BE(20);
  if (!width || !height || width > MAX_PNG_AXIS || height > MAX_PNG_AXIS || width * height > MAX_PNG_PIXELS) fail(`${label} dimensions exceed authoring bounds`);
  return { width, height };
}

export async function findPackageRoot(start = dirname(fileURLToPath(import.meta.url))) {
  let directory = resolve(start);
  while (true) {
    if (await exists(resolve(directory, 'package.json'))) return directory;
    const parent = dirname(directory);
    if (parent === directory) fail('Could not find package.json above bind-ground.mjs');
    directory = parent;
  }
}

/** Load the public core surface from a source checkout or an installed package. */
export async function loadProject(packageRoot) {
  packageRoot ??= await findPackageRoot();
  const source = resolve(packageRoot, 'src/core.ts');
  const fallback = resolve(packageRoot, 'dist/core.js');
  const modulePath = await exists(source) ? source : await exists(fallback) ? fallback : null;
  if (!modulePath) fail(`No public core module found in ${packageRoot} (expected src/core.ts or dist/core.js)`);
  const api = await import(pathToFileURL(modulePath).href);
  if (typeof api.project !== 'function' || typeof api.validateScene !== 'function') fail(`Public core module lacks project() or validateScene(): ${modulePath}`);
  return { project: api.project, validateScene: api.validateScene, modulePath };
}

function parseArgs(argv) {
  const values = {};
  for (let index = 0; index < argv.length; index += 1) {
    const value = argv[index];
    if (!value.startsWith('--') && !values.scene) values.scene = value;
    else if (!value.startsWith('--') && !values.packed) values.packed = value;
    else if (value === '--out') values.out = argv[++index];
    else if (value === '--image-url') values.imageUrl = argv[++index];
    else fail(`Unknown or misplaced argument: ${value}`);
  }
  if (!values.scene || !values.packed || !values.out || typeof values.imageUrl !== 'string' || !values.imageUrl) fail('Usage: bind-ground.mjs scene.json prepared/packed-art.json --out NEW_DIR --image-url ./art/prepared/ground.png');
  return values;
}

function parseJson(bytes, label) { try { return JSON.parse(bytes.toString('utf8')); } catch (error) { fail(`${label} is invalid JSON: ${error.message}`); } }

function packedSurface(packed) {
  const root = object(packed, 'packed art');
  if (root.version !== 1 || !Array.isArray(root.groups)) fail('packed art must be version 1 with groups');
  const surfaces = root.groups.filter(group => group && typeof group === 'object' && !Array.isArray(group) && group.kind === 'surface');
  if (surfaces.length !== 1) fail('packed art must contain exactly one surface group');
  const group = object(surfaces[0], 'packed art surface group');
  if (group.kind !== 'surface') fail('packed art group must be a surface');
  const composition = object(group.composition, 'packed art surface composition');
  if (typeof composition.reference !== 'string' || !composition.reference) fail('packed art surface composition.reference is required');
  if (!Array.isArray(composition.origin) || composition.origin.length !== 2) fail('packed art surface composition.origin must be [x,y]');
  return { reference: composition.reference, origin: { x: integer(composition.origin[0], 'composition.origin[0]', -1_000_000, 1_000_000), y: integer(composition.origin[1], 'composition.origin[1]', -1_000_000, 1_000_000) } };
}

function assertFlatGround(scene) {
  if (scene.version === 2 && ((scene.levels?.length ?? 0) !== 0 || (scene.links?.length ?? 0) !== 0)) fail('bind-ground supports one flat ground plane only; bind elevated or multi-floor art in the host with its explicit level placement');
  for (const [r, row] of scene.map.entries()) for (const [c, tileId] of row.entries()) {
    const elevation = scene.tiles[tileId].elevation ?? 0;
    if (elevation !== 0) fail(`bind-ground supports one flat ground plane only; map[${r}][${c}] has elevation ${elevation}`);
  }
}

function assertFreeIds(scene) {
  const existing = [Object.keys(scene.tiles), Object.keys(scene.assets?.images ?? {}), Object.keys(scene.assets?.textures ?? {})].flat();
  const collision = existing.find(id => id.startsWith(PREFIX));
  if (collision) fail(`Scene already contains reserved ground binding ID: ${collision}`);
}

async function preparerMetadata(directory, reference, imageHash) {
  const path = resolve(directory, 'provenance.json');
  if (!await exists(path)) return undefined;
  const bytes = await readFile(path); const data = parseJson(bytes, 'preparer provenance');
  const declared = data?.outputs?.[reference];
  if (declared !== undefined && declared !== imageHash) fail(`preparer provenance hash for ${reference} does not match the local image`);
  return { file: 'provenance.json', sha256: hash(bytes), imageSha256: typeof declared === 'string' ? declared : undefined };
}

export async function bindGround({ scene: sceneInput, packed: packedInput, out, imageUrl, packageRoot }) {
  const outPath = resolve(out);
  if (await exists(outPath)) fail(`Output directory already exists: ${outPath}`);
  if (typeof imageUrl !== 'string' || !imageUrl) fail('--image-url must be explicit and nonempty; it is the host runtime URL for the local PNG');
  const scenePath = resolve(sceneInput), packedPath = resolve(packedInput);
  const [sceneBytes, packedBytes] = await Promise.all([readFile(scenePath), readFile(packedPath)]);
  const root = packageRoot ?? await findPackageRoot(); const api = await loadProject(root);
  const scene = api.validateScene(parseJson(sceneBytes, 'scene input'));
  assertFlatGround(scene); assertFreeIds(scene);
  const surface = packedSurface(parseJson(packedBytes, 'packed art'));
  const preparedDir = dirname(packedPath);
  const imagePath = localPath(preparedDir, surface.reference, 'composition.reference');
  if (extname(imagePath).toLowerCase() !== '.png') fail('composition.reference must name a local PNG');
  const imageBytes = await readFile(imagePath); const image = pngHeader(imageBytes, 'composition reference');
  const imageHash = hash(imageBytes); const preparer = await preparerMetadata(preparedDir, surface.reference, imageHash);
  const cloned = JSON.parse(JSON.stringify(scene));
  cloned.assets ??= { images: {}, textures: {} };
  cloned.assets.images ??= {}; cloned.assets.textures ??= {};
  cloned.assets.images[`${PREFIX}image`] = { url: imageUrl, sampling: 'nearest' };
  const cells = [];
  for (let r = 0; r < cloned.map.length; r += 1) for (let c = 0; c < cloned.map[r].length; c += 1) {
    const originalTile = cloned.map[r][c]; const point = api.project({ c, r }, cloned.tileWidth, cloned.tileHeight);
    const frame = { x: point.x - cloned.tileWidth / 2 - surface.origin.x, y: point.y - cloned.tileHeight / 2 - surface.origin.y, width: cloned.tileWidth, height: cloned.tileHeight };
    for (const [key, value] of Object.entries(frame)) integer(value, `frame ${key} at (${c},${r})`, 0, 65536);
    if (frame.x + frame.width > image.width || frame.y + frame.height > image.height) fail(`frame for map[${r}][${c}] exceeds composition reference ${image.width}x${image.height}`);
    const suffix = `${c}-${r}`, texture = `${PREFIX}texture-${suffix}`, tile = `${PREFIX}tile-${suffix}`;
    cloned.assets.textures[texture] = { image: `${PREFIX}image`, frame };
    const definition = { ...cloned.tiles[originalTile] }; delete definition.texture; delete definition.textures; definition.texture = texture;
    cloned.tiles[tile] = definition; cloned.map[r][c] = tile;
    cells.push({ cell: { c, r, level: 'ground' }, world: point, frame, originalTile, newTile: tile, texture });
  }
  const outputScene = api.validateScene(cloned);
  const toolBytes = await readFile(fileURLToPath(import.meta.url));
  const binding = { version: 1, projectionModule: relative(root, api.modulePath).replaceAll('\\', '/'), inputs: { scene: { file: scenePath, sha256: hash(sceneBytes) }, packedArt: { file: packedPath, sha256: hash(packedBytes) }, image: { file: imagePath, sha256: imageHash }, tool: { file: 'bind-ground.mjs', sha256: hash(toolBytes) }, ...(preparer ? { preparer } : {}) }, image: { url: imageUrl, reference: surface.reference, dimensions: image, origin: surface.origin }, cells };
  await mkdir(outPath, { recursive: false });
  await Promise.all([writeFile(resolve(outPath, 'scene.json'), `${JSON.stringify(outputScene, null, 2)}\n`), writeFile(resolve(outPath, 'binding.json'), `${JSON.stringify(binding, null, 2)}\n`)]);
  return { outPath, scene: outputScene, binding };
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  try { const result = await bindGround(parseArgs(process.argv.slice(2))); process.stdout.write(`Bound ground to ${result.outPath}\n`); } catch (error) { process.stderr.write(`bind-ground: ${error.message}\n`); process.exitCode = 1; }
}
