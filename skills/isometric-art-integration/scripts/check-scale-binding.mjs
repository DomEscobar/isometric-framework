#!/usr/bin/env node
// Binds a calibration contract to the scene that actually renders it. No pixel inspection.
import { readFile, stat } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import path from 'node:path';
import { pathToFileURL } from 'node:url';

const MAX_FILE_BYTES = 8 * 1024 * 1024;
const MAX_IMAGE_BYTES = 64 * 1024 * 1024;
const object = v => v !== null && typeof v === 'object' && !Array.isArray(v);
const nonempty = v => typeof v === 'string' && v.trim().length > 0;
const finite = n => typeof n === 'number' && Number.isFinite(n);
const near = (a, b, tolerance = 0) => finite(a) && finite(b) && Math.abs(a - b) <= tolerance + 1e-9;
const fixed = n => (Number.isInteger(n) ? String(n) : n.toFixed(4));

const DEFAULT_ANCHOR = { x: 0.5, y: 1 };
const LIMITS = 'Declared contract values against actual scene bindings only. '
  + 'Does not decode pixels, judge silhouettes, or establish that a landmark sits on the artwork it names. '
  + 'It cannot tell whether a calibrated proportion looks right; review the shared-scale board and the rendered scene. '
  + 'Unverified entries are open work and exceptions are stated deviations, neither is acceptance.';

function effectiveScale(visual, frame) {
  return (visual.width ?? frame.width) / frame.width * (visual.scale ?? 1);
}

function spriteTextures(scene, visual) {
  if (nonempty(visual.texture)) return [visual.texture];
  const clip = nonempty(visual.animation) ? scene.assets?.animations?.[visual.animation] : undefined;
  return Array.isArray(clip?.frames) ? clip.frames : [];
}

/** Compare one calibrated asset with the scene definition that renders it. */
export function checkScaleBinding(contract, scene, plan, imageHashes = {}) {
  const results = [], failures = [], unverified = [], exceptions = [];
  const check = (condition, label) => { results.push({ label, pass: !!condition }); if (!condition) failures.push(label); };
  const report = () => ({ pass: failures.length === 0, results, failures, unverified, exceptions, limits: LIMITS });

  if (plan?.version !== 1 || !Array.isArray(plan.pairings)) throw new TypeError('Plan requires version 1 and a pairings array');
  if (!object(contract?.projection) || !object(contract.heightReferences) || !Array.isArray(contract.assets)) {
    throw new TypeError('Contract requires projection, heightReferences and assets');
  }
  if (!object(scene?.entityTypes) || !object(scene.tiles)) throw new TypeError('Scene requires entityTypes and tiles');
  const heightTolerance = contract.tolerances?.heightErrorPx ?? 0;
  if (!finite(heightTolerance) || heightTolerance < 0) throw new TypeError('Invalid height tolerance');

  check(near(scene.tileWidth, contract.projection.tileWidth), `projection: tileWidth ${scene.tileWidth} matches contract ${contract.projection.tileWidth}`);
  check(near(scene.tileHeight, contract.projection.tileHeight), `projection: tileHeight ${scene.tileHeight} matches contract ${contract.projection.tileHeight}`);

  const assets = new Map(contract.assets.filter(asset => nonempty(asset?.id)).map(asset => [asset.id, asset]));
  const exemptTypes = exemptGroup('entityTypes');
  const exemptTiles = exemptGroup('tiles');
  const pairedTypes = new Set(), pairedTiles = new Set();

  for (const [index, pairing] of plan.pairings.entries()) {
    const label = pairing?.entityType ?? pairing?.tile ?? `pairings[${index}]`;
    const asset = assets.get(pairing?.asset);
    if (!asset) { check(false, `${label}: contract has no asset "${pairing?.asset}"`); continue; }
    if (!!pairing.entityType === !!pairing.tile) { check(false, `${label}: pair an asset with exactly one entityType or tile`); continue; }

    if (pairing.tile) {
      pairedTiles.add(pairing.tile);
      bindTile(pairing, asset, label);
      continue;
    }
    pairedTypes.add(pairing.entityType);
    bindEntityType(pairing, asset, label);
  }

  for (const [id, type] of Object.entries(scene.entityTypes)) {
    if (type?.visual?.kind !== 'sprite' || exemptTypes.has(id)) continue;
    check(pairedTypes.has(id), `coverage: sprite entity type "${id}" is calibrated or explicitly exempt`);
  }
  for (const [id, tile] of Object.entries(scene.tiles)) {
    if ((!nonempty(tile?.texture) && !Array.isArray(tile?.textures)) || exemptTiles.has(id)) continue;
    check(pairedTiles.has(id), `coverage: textured tile "${id}" is calibrated or explicitly exempt`);
  }
  return report();

  function exemptGroup(kind) {
    const group = plan.exempt?.[kind];
    if (group === undefined) return new Set();
    if (!object(group)) { check(false, `plan.exempt.${kind} must map each name to a stated reason`); return new Set(); }
    const names = new Set();
    for (const [name, reason] of Object.entries(group)) {
      if (!nonempty(reason)) { check(false, `plan.exempt.${kind}.${name} must state why it stays uncalibrated`); continue; }
      names.add(name);
      exceptions.push(`exempt ${kind.replace(/s$/, '')} "${name}": ${reason.trim()}`);
    }
    return names;
  }

  function bindImage(asset, texture, label) {
    const image = texture.image;
    if (!Object.hasOwn(plan.images ?? {}, image)) {
      check(false, `${label}: declare the host file for scene image "${image}" in plan.images`);
      return;
    }
    if (plan.images[image] === null) { unverified.push(`${label}: scene image "${image}" declared unresolvable; its bytes are unchecked`); return; }
    const actual = imageHashes[image];
    if (!nonempty(actual)) { unverified.push(`${label}: scene image "${image}" could not be hashed`); return; }
    check(actual.toLowerCase() === String(asset.sha256).toLowerCase(),
      `${label}: scene image "${image}" is the calibrated file`);
  }

  function bindFrame(asset, texture, textureId, label) {
    const frame = texture.frame ?? { x: 0, y: 0, width: asset.frame?.width, height: asset.frame?.height };
    const same = ['x', 'y', 'width', 'height'].every(key => near(frame[key], asset.frame?.[key]));
    check(same, `${label}/${textureId}: scene crop matches the calibrated frame`);
    return frame;
  }

  function bindEntityType(pairing, asset, label) {
    const type = scene.entityTypes[pairing.entityType];
    if (!type) { check(false, `${label}: scene has no entity type`); return; }
    const visual = type.visual ?? {};
    if (visual.kind !== 'sprite') { check(false, `${label}: calibrated art requires a sprite visual, found "${visual.kind}"`); return; }

    const textureIds = spriteTextures(scene, visual);
    if (!textureIds.length) { check(false, `${label}: visual selects no named texture or animation frames`); return; }

    const scaleY = asset.render?.height === undefined
      ? asset.render?.width / asset.frame?.width
      : asset.render.height / asset.frame.height;
    check(near(asset.render?.width / asset.frame?.width, scaleY),
      `${label}: calibrated scaling is uniform and representable by the runtime`);

    for (const textureId of textureIds) {
      const texture = scene.assets?.textures?.[textureId];
      if (!object(texture)) { check(false, `${label}/${textureId}: scene manifest has no such texture`); continue; }
      const frame = bindFrame(asset, texture, textureId, label);
      const anchor = visual.anchor ?? texture.anchor ?? DEFAULT_ANCHOR;
      check(near(anchor.x, asset.anchor?.x) && near(anchor.y, asset.anchor?.y),
        `${label}/${textureId}: effective anchor matches the calibrated anchor`);
      const scale = effectiveScale(visual, frame);
      check(near(scale, asset.render?.width / asset.frame?.width),
        `${label}/${textureId}: effective render scale ${fixed(scale)} matches the calibrated ${fixed(asset.render?.width / asset.frame?.width)}`);
      bindImage(asset, texture, `${label}/${textureId}`);
    }

    const offset = visual.offset ?? { x: 0, y: 0 };
    const calibrated = asset.render?.offset ?? { x: 0, y: 0 };
    check(near(offset.x, calibrated.x) && near(offset.y, calibrated.y), `${label}: render offset matches the calibrated offset`);
    check(near(type.columns ?? 1, asset.footprint?.columns) && near(type.rows ?? 1, asset.footprint?.rows),
      `${label}: grid footprint matches the calibrated footprint`);

    bindBodyHeight(pairing, asset, type, label);
  }

  function bindBodyHeight(pairing, asset, type, label) {
    const heights = Array.isArray(asset.heights) ? asset.heights : [];
    const reference = nonempty(pairing.bodyHeightReference)
      ? pairing.bodyHeightReference
      : (heights.length === 1 ? heights[0].reference : undefined);
    if (!nonempty(reference)) {
      if (!heights.length) { unverified.push(`${label}: asset declares no height reference; its physical size is unchecked`); return; }
      check(false, `${label}: declare bodyHeightReference; the asset names ${heights.length} height references`);
      return;
    }
    const units = contract.heightReferences[reference];
    if (!finite(units)) { check(false, `${label}: heightReferences has no entry "${reference}"`); return; }
    const expected = units * contract.projection.heightPixelsPerUnit;
    if (!finite(type.bodyHeight)) {
      if (type.blocking) check(false, `${label}: blocking entity requires an explicit bodyHeight of ${fixed(expected)}px`);
      else unverified.push(`${label}: nonblocking entity declares no bodyHeight; ${fixed(expected)}px stays unchecked`);
      return;
    }
    if (Object.hasOwn(pairing, 'deliberateBodyHeight')) {
      if (!nonempty(pairing.deliberateBodyHeight)) {
        check(false, `${label}: deliberateBodyHeight must state why the collider deviates from ${reference}`);
        return;
      }
      exceptions.push(`${label}: bodyHeight ${fixed(type.bodyHeight)}px deliberately deviates from ${reference} `
        + `(${fixed(expected)}px) — ${pairing.deliberateBodyHeight.trim()}`);
      return;
    }
    check(near(type.bodyHeight, expected, heightTolerance),
      `${label}: bodyHeight ${fixed(type.bodyHeight)}px matches ${reference} (${fixed(expected)}px) within ${heightTolerance}px`);
  }

  function bindTile(pairing, asset, label) {
    const tile = scene.tiles[pairing.tile];
    if (!object(tile)) { check(false, `${label}: scene has no such tile`); return; }
    const textureIds = nonempty(tile.texture) ? [tile.texture] : (Array.isArray(tile.textures) ? tile.textures : []);
    if (!textureIds.length) { check(false, `${label}: tile selects no named texture`); return; }
    check(near(asset.render?.width, scene.tileWidth), `${label}: calibrated render width matches the scene tile width`);
    if (asset.render?.height !== undefined) {
      check(near(asset.render.height, scene.tileHeight), `${label}: calibrated render height matches the scene tile height`);
    }
    for (const textureId of textureIds) {
      const texture = scene.assets?.textures?.[textureId];
      if (!object(texture)) { check(false, `${label}/${textureId}: scene manifest has no such texture`); continue; }
      bindFrame(asset, texture, textureId, label);
      bindImage(asset, texture, `${label}/${textureId}`);
    }
  }
}

async function readJSON(file) {
  const info = await stat(file);
  if (!info.isFile() || info.size > MAX_FILE_BYTES) throw new Error(`${file} must be a regular JSON file no larger than 8 MiB`);
  return JSON.parse((await readFile(file, 'utf8')).replace(/^\uFEFF/, ''));
}

export async function checkFiles(contractPath, scenePath, planPath) {
  const [contract, scene, plan] = await Promise.all([contractPath, scenePath, planPath].map(readJSON));
  const directory = path.dirname(path.resolve(planPath));
  const hashes = {};
  for (const [id, relative] of Object.entries(plan?.images ?? {})) {
    if (relative === null) continue;
    if (!nonempty(relative)) throw new TypeError(`plan.images.${id} must be a local path or null`);
    const file = path.resolve(directory, relative);
    const info = await stat(file);
    if (!info.isFile() || info.size > MAX_IMAGE_BYTES) throw new Error(`${relative} must be a regular file no larger than 64 MiB`);
    hashes[id] = createHash('sha256').update(await readFile(file)).digest('hex');
  }
  return checkScaleBinding(contract, scene, plan, hashes);
}

if (process.argv[1] && import.meta.url === pathToFileURL(path.resolve(process.argv[1])).href) {
  if (process.argv.length !== 5) throw new Error('Usage: node check-scale-binding.mjs art-contract.json scene.json binding-plan.json');
  const result = await checkFiles(process.argv[2], process.argv[3], process.argv[4]);
  process.stdout.write(`${JSON.stringify(result, null, 2)}\n`);
  if (!result.pass) process.exitCode = 1;
}
