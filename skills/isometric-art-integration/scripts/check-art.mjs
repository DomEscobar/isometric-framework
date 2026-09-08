#!/usr/bin/env node
// Calibration metadata only: this does not identify pixels, silhouettes, or artistic quality.
import { open, readFile, stat } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import path from 'node:path';
import { pathToFileURL } from 'node:url';

const MAX_IMAGE_BYTES = 64 * 1024 * 1024;
const MAX_CONTRACT_BYTES = 8 * 1024 * 1024;
const MAX_DIMENSION = 32768;
const PNG_SIGNATURE = Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]);
const finite = (n) => typeof n === 'number' && Number.isFinite(n);
const positive = (n) => finite(n) && n > 0;
const integer = (n) => Number.isSafeInteger(n) && n >= 0;
const object = (v) => v !== null && typeof v === 'object' && !Array.isArray(v);
const nonempty = (v) => typeof v === 'string' && v.trim().length > 0;
const near = (a, b) => Math.abs(a - b) <= 1e-9 * Math.max(1, Math.abs(a), Math.abs(b));
const result = (contract) => ({ passed: false, scope: 'metadata-only', errors: [], assets: [], contract });

function shape(value, required, optional, label, fail) {
  if (!object(value)) { fail(`${label} must be an object.`); return false; }
  let valid = true;
  for (const key of required) if (!Object.hasOwn(value, key)) { fail(`${label}.${key} is required.`); valid = false; }
  for (const key of Object.keys(value)) if (!required.includes(key) && !optional.includes(key)) {
    fail(`${label}.${key} is not a supported field.`); valid = false;
  }
  return valid;
}

function point(value, label, fail, keys = ['x', 'y']) {
  if (!shape(value, keys, [], label, fail)) return false;
  if (!keys.every((key) => finite(value[key]))) { fail(`${label} coordinates must be finite numbers.`); return false; }
  return true;
}

function noncollinear(points) {
  const first = points[0];
  const second = points.find((p) => !near(p.x, first.x) || !near(p.y, first.y));
  if (!second) return false;
  return points.some((p) => {
    const a = (second.x - first.x) * (p.y - first.y);
    const b = (second.y - first.y) * (p.x - first.x);
    return finite(a) && finite(b) && !near(a, b);
  });
}

async function inspectPNG(imagePath) {
  // Read at most the declared limit, even if a file grows during inspection.
  const handle = await open(imagePath, 'r');
  try {
    const info = await handle.stat();
    if (!info.isFile() || info.size > MAX_IMAGE_BYTES) throw new Error('PNG must be a regular file no larger than 64 MiB.');
    const bytes = Buffer.alloc(info.size);
    let offset = 0;
    while (offset < bytes.length) {
      const { bytesRead } = await handle.read(bytes, offset, bytes.length - offset, offset);
      if (!bytesRead) throw new Error('PNG changed or ended during inspection.');
      offset += bytesRead;
    }
    if (bytes.length < 33 || !bytes.subarray(0, 8).equals(PNG_SIGNATURE)) throw new Error('Invalid PNG signature or truncated IHDR.');
    if (bytes.readUInt32BE(8) !== 13 || bytes.toString('ascii', 12, 16) !== 'IHDR') throw new Error('PNG must begin with a 13-byte IHDR chunk.');
    const width = bytes.readUInt32BE(16), height = bytes.readUInt32BE(20);
    if (!width || !height || width > MAX_DIMENSION || height > MAX_DIMENSION) throw new Error('PNG IHDR dimensions must be between 1 and 32768 pixels.');
    const bitDepth = bytes[24], colorType = bytes[25];
    const depths = { 0: [1, 2, 4, 8, 16], 2: [8, 16], 3: [1, 2, 4, 8], 4: [8, 16], 6: [8, 16] };
    if (!depths[colorType]?.includes(bitDepth) || bytes[26] !== 0 || bytes[27] !== 0 || bytes[28] > 1) throw new Error('Invalid PNG IHDR encoding fields.');
    // Validate chunk boundaries and require image data and an end marker. No pixel decoding.
    let cursor = 8, dataSeen = false, ended = false;
    while (cursor + 12 <= bytes.length) {
      const size = bytes.readUInt32BE(cursor);
      if (size > bytes.length - cursor - 12) throw new Error('Truncated PNG chunk.');
      const type = bytes.toString('ascii', cursor + 4, cursor + 8);
      if (type === 'IDAT' && size > 0) dataSeen = true;
      cursor += size + 12;
      if (type === 'IEND') { if (size !== 0 || cursor !== bytes.length) throw new Error('Invalid PNG IEND or trailing bytes.'); ended = true; break; }
    }
    if (!dataSeen || !ended) throw new Error('PNG is missing IDAT image data or IEND.');
    return { imageWidth: width, imageHeight: height, hash: createHash('sha256').update(bytes).digest('hex') };
  } finally { await handle.close(); }
}

export async function checkContract(contract, directory = process.cwd()) {
  const report = result(contract);
  const fail = (message) => report.errors.push({ message });
  if (!shape(contract, ['version', 'pack', 'projection', 'tolerances', 'heightReferences', 'assets'], [], 'contract', fail)) return report;
  if (contract.version !== 1) fail('contract.version must be 1.');
  if (!nonempty(contract.pack)) fail('contract.pack must be a nonempty string.');
  if (shape(contract.projection, ['tileWidth', 'tileHeight', 'heightPixelsPerUnit'], [], 'projection', fail)) {
    for (const [key, value] of Object.entries(contract.projection)) if (!positive(value)) fail(`projection.${key} must be finite and positive.`);
  }
  if (shape(contract.tolerances, ['groundErrorPx', 'heightErrorPx'], [], 'tolerances', fail)) {
    for (const [key, value] of Object.entries(contract.tolerances)) if (!finite(value) || value < 0) fail(`tolerances.${key} must be finite and nonnegative.`);
  }
  if (!object(contract.heightReferences)) fail('heightReferences must be an object of named positive world-unit values.');
  else for (const [key, value] of Object.entries(contract.heightReferences)) if (!nonempty(key) || !positive(value)) fail(`heightReferences.${key} must name a finite positive world-unit value.`);
  if (!Array.isArray(contract.assets) || contract.assets.length === 0 || contract.assets.length > 2048) fail('assets must contain between 1 and 2048 assets.');
  if (report.errors.length) return report;
  const ids = new Set();
  for (const asset of contract.assets) {
    const assetId = nonempty(asset?.id) ? asset.id : undefined;
    const add = (message) => report.errors.push({ ...(assetId ? { assetId } : {}), message });
    const start = report.errors.length;
    if (!shape(asset, ['id', 'kind', 'image', 'sha256', 'frame', 'anchor', 'render', 'footprint', 'groundPoints', 'heights', 'allowedOverhang'], [], 'asset', add)) continue;
    if (!assetId) add('id must be a nonempty string.');
    else if (ids.has(assetId)) add(`Duplicate asset id: ${assetId}.`);
    else ids.add(assetId);
    if (!['terrain', 'prop', 'actor'].includes(asset.kind)) add('kind must be terrain, prop, or actor.');
    if (!nonempty(asset.image) || asset.image.includes('\0') || /^(?![a-z]:[\\/])[a-z][a-z\d+.-]*:/i.test(asset.image) || /^[/\\]{2}/.test(asset.image)) add('image must be a local filesystem path, not a URL or network path.');
    else if (path.extname(asset.image).toLowerCase() !== '.png') add('Only PNG image files are supported.');
    if (typeof asset.sha256 !== 'string' || !/^[a-f\d]{64}$/i.test(asset.sha256)) add('sha256 must contain exactly 64 hexadecimal characters.');
    if (shape(asset.frame, ['x', 'y', 'width', 'height'], [], 'frame', add)) {
      if (!integer(asset.frame.x) || !integer(asset.frame.y) || !integer(asset.frame.width) || !integer(asset.frame.height) || !asset.frame.width || !asset.frame.height) add('frame requires nonnegative integer x/y and positive integer width/height.');
    }
    if (point(asset.anchor, 'anchor', add) && (asset.anchor.x < 0 || asset.anchor.x > 1 || asset.anchor.y < 0 || asset.anchor.y > 1)) add('anchor must be normalized to [0, 1].');
    if (shape(asset.render, ['width'], ['height', 'offset'], 'render', add)) {
      if (!positive(asset.render.width) || (Object.hasOwn(asset.render, 'height') && !positive(asset.render.height))) add('render.width and optional render.height must be finite and positive.');
      if (Object.hasOwn(asset.render, 'offset')) point(asset.render.offset, 'render.offset', add);
    }
    if (shape(asset.footprint, ['columns', 'rows'], [], 'footprint', add) && (!integer(asset.footprint.columns) || !asset.footprint.columns || !integer(asset.footprint.rows) || !asset.footprint.rows)) add('footprint columns and rows must be positive integers.');
    if (typeof asset.allowedOverhang !== 'string') add('allowedOverhang must be an explanatory string (empty is allowed).');
    for (const field of ['groundPoints', 'heights']) if (!Array.isArray(asset[field]) || asset[field].length > 4096) add(`${field} must be an array with at most 4096 entries.`);
    if (report.errors.length !== start) continue;
    const inside = (p, label) => {
      if (p.x < 0 || p.y < 0 || p.x > asset.frame.width || p.y > asset.frame.height) add(`${label} must be frame-local and inside [0, frame.width] / [0, frame.height].`);
    };
    for (const [i, p] of asset.groundPoints.entries()) {
      if (!shape(p, ['source', 'grid'], [], `groundPoints[${i}]`, add)) continue;
      if (point(p.source, `groundPoints[${i}].source`, add)) inside(p.source, `groundPoints[${i}].source`);
      point(p.grid, `groundPoints[${i}].grid`, add, ['c', 'r']);
    }
    for (const [i, h] of asset.heights.entries()) {
      if (!shape(h, ['reference', 'base', 'top'], [], `heights[${i}]`, add)) continue;
      if (!nonempty(h.reference) || !Object.hasOwn(contract.heightReferences, h.reference)) add(`heights[${i}].reference must name an entry in heightReferences.`);
      if (point(h.base, `heights[${i}].base`, add)) inside(h.base, `heights[${i}].base`);
      if (point(h.top, `heights[${i}].top`, add)) inside(h.top, `heights[${i}].top`);
    }
    if (report.errors.length !== start) continue;
    const scaleX = asset.render.width / asset.frame.width;
    const scaleY = asset.render.height === undefined ? scaleX : asset.render.height / asset.frame.height;
    if (!positive(scaleX) || !positive(scaleY)) { add('Render scale is nonfinite or underflows; use practical pixel dimensions.'); continue; }
    const imagePath = path.resolve(directory, asset.image);
    let info;
    try { info = await inspectPNG(imagePath); }
    catch (error) { add(`Cannot inspect PNG ${asset.image}: ${error.message}`); continue; }
    if (asset.frame.x + asset.frame.width > info.imageWidth || asset.frame.y + asset.frame.height > info.imageHeight) { add(`frame exceeds PNG bounds ${info.imageWidth}x${info.imageHeight}.`); continue; }
    report.assets.push({ ...asset, imagePath, imageWidth: info.imageWidth, imageHeight: info.imageHeight, scaleX, scaleY });
    if (info.hash !== asset.sha256.toLowerCase()) add(`sha256 mismatch for ${asset.image}; expected ${asset.sha256.toLowerCase()}, actual ${info.hash}. Recalibrate changed artwork before updating its hash.`);
    if (asset.kind !== 'terrain' && Math.abs(scaleX - scaleY) > 1e-9 * Math.max(scaleX, scaleY)) add('Props and actors require uniform render scaling; remove render.height or preserve the source aspect ratio.');
    const offset = asset.render.offset ?? { x: 0, y: 0 };
    const actual = asset.groundPoints.map(({ source }) => ({ x: (source.x - asset.anchor.x * asset.frame.width) * scaleX + offset.x, y: (source.y - asset.anchor.y * asset.frame.height) * scaleY + offset.y }));
    const coordinateTolerance = contract.tolerances.groundErrorPx * Math.hypot(1 / contract.projection.tileWidth, 1 / contract.projection.tileHeight);
    asset.groundPoints.forEach(({ grid }, i) => {
      if (grid.c < -0.5 || grid.c > asset.footprint.columns - 0.5 || grid.r < -0.5 || grid.r > asset.footprint.rows - 0.5) add(`groundPoints[${i}].grid exceeds the declared rigid footprint. allowedOverhang cannot exempt ground contacts.`);
      const measuredC = actual[i].x / contract.projection.tileWidth - actual[i].y / contract.projection.tileHeight;
      const measuredR = actual[i].x / contract.projection.tileWidth + actual[i].y / contract.projection.tileHeight;
      if (!finite(measuredC) || !finite(measuredR) || measuredC < -0.5 - coordinateTolerance || measuredC > asset.footprint.columns - 0.5 + coordinateTolerance || measuredR < -0.5 - coordinateTolerance || measuredR > asset.footprint.rows - 0.5 + coordinateTolerance) {
        add(`groundPoints[${i}] actual rendered contact spills outside the rigid footprint: measured grid (${measuredC.toFixed(4)}, ${measuredR.toFixed(4)}), permitted c [-0.5, ${asset.footprint.columns - 0.5}] / r [-0.5, ${asset.footprint.rows - 0.5}] with coordinate tolerance ${coordinateTolerance.toFixed(6)}. Correct the artwork, anchor, scale, or footprint; declared grid correspondences cannot exempt measured ground spill.`);
      }
      const expected = { x: (grid.c + grid.r) * contract.projection.tileWidth / 2, y: (grid.r - grid.c) * contract.projection.tileHeight / 2 };
      const error = Math.hypot(actual[i].x - expected.x, actual[i].y - expected.y);
      if (!finite(error) || error > contract.tolerances.groundErrorPx + 1e-9) add(`groundPoints[${i}] projection error ${error.toFixed(4)} px exceeds groundErrorPx ${contract.tolerances.groundErrorPx}; check camera, anchor, render scale, offset, and contact landmark.`);
    });
    if (asset.kind === 'terrain') {
      if (asset.footprint.columns !== 1 || asset.footprint.rows !== 1) add('Terrain calibration requires a 1x1 footprint.');
      const corners = new Set(asset.groundPoints.map(({ grid }) => `${grid.c},${grid.r}`));
      if (asset.groundPoints.length !== 4 || !['-0.5,-0.5', '-0.5,0.5', '0.5,-0.5', '0.5,0.5'].every((p) => corners.has(p))) add('Terrain requires exactly four groundPoints at the four 1x1 cell corners (c/r = +/-0.5).');
    } else if (asset.kind === 'prop' && (actual.length < 3 || !noncollinear(actual) || !noncollinear(asset.groundPoints.map(({ grid }) => ({ x: grid.c, y: grid.r }))))) add('Props require at least three noncollinear source contacts and noncollinear grid contacts.');
    else if (asset.kind === 'actor' && !actual.length) add('Actors require at least one ground contact point.');
    if (asset.kind === 'actor' && !asset.heights.length) add('Actors require at least one named height measurement.');
    asset.heights.forEach((h, i) => {
      const horizontal = Math.abs(h.base.x - h.top.x) * scaleX;
      const measured = (h.base.y - h.top.y) * scaleY;
      const expected = contract.heightReferences[h.reference] * contract.projection.heightPixelsPerUnit;
      if (!finite(horizontal) || horizontal > contract.tolerances.heightErrorPx + 1e-9) add(`heights[${i}] base/top must describe the same world x; horizontal error ${horizontal.toFixed(4)} px exceeds heightErrorPx.`);
      if (!finite(measured) || !finite(expected) || Math.abs(measured - expected) > contract.tolerances.heightErrorPx + 1e-9) add(`heights[${i}] measures ${measured.toFixed(4)} px; reference ${h.reference} requires ${expected.toFixed(4)} px within heightErrorPx ${contract.tolerances.heightErrorPx}.`);
    });
  }
  report.passed = report.errors.length === 0;
  return report;
}

export async function checkFile(file) {
  let contract;
  try {
    const info = await stat(file);
    if (!info.isFile() || info.size > MAX_CONTRACT_BYTES) throw new Error('Contract must be a regular JSON file no larger than 8 MiB.');
    contract = JSON.parse((await readFile(file, 'utf8')).replace(/^\uFEFF/, ''));
  } catch (error) {
    const report = result(null);
    report.errors.push({ message: `Cannot read contract ${file}: ${error.message}` });
    return report;
  }
  return checkContract(contract, path.dirname(path.resolve(file)));
}

if (process.argv[1] && import.meta.url === pathToFileURL(path.resolve(process.argv[1])).href) {
  const report = process.argv.length === 3 ? await checkFile(process.argv[2]) : { ...result(null), errors: [{ message: 'Usage: node check-art.mjs <contract.json>' }] };
  process.stdout.write(`${JSON.stringify(report, null, 2)}\n`);
  process.exitCode = report.passed ? 0 : 1;
}
