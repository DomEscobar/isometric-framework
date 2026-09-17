#!/usr/bin/env node
// Declared calibration plus a decoded alpha silhouette: no color fidelity or artistic judgment.
import { open, readFile, stat } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import { inflateSync } from 'node:zlib';
import path from 'node:path';
import { pathToFileURL } from 'node:url';

const MAX_IMAGE_BYTES = 64 * 1024 * 1024;
const MAX_CONTRACT_BYTES = 8 * 1024 * 1024;
const MAX_DIMENSION = 32768;
const MAX_DECODE_PIXELS = 16_000_000;
/** Ignore near-invisible antialiasing when measuring a silhouette. */
const OPAQUE_ALPHA = 8;
const CHANNELS = { 0: 1, 2: 3, 3: 1, 4: 2, 6: 4 };
const PNG_SIGNATURE = Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]);
/** What overhanging artwork may be. Only art clear of the ground may leave the footprint. */
const OVERHANG_CLASSES = {
  canopy: true, eave: true, attachment: true, shadow: true,
  'ground-contact': false, foundation: false, unclear: false,
};

/** Key-sorted serialization so a region hash does not depend on property order. */
function canonical(value) {
  if (Array.isArray(value)) return `[${value.map(canonical).join(',')}]`;
  if (value && typeof value === 'object') {
    return `{${Object.keys(value).sort().map((key) => `${JSON.stringify(key)}:${canonical(value[key])}`).join(',')}}`;
  }
  return typeof value === 'number' ? JSON.stringify(Number(value.toFixed(4))) : JSON.stringify(value);
}
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
    const bitDepth = bytes[24], colorType = bytes[25], interlace = bytes[28];
    const depths = { 0: [1, 2, 4, 8, 16], 2: [8, 16], 3: [1, 2, 4, 8], 4: [8, 16], 6: [8, 16] };
    if (!depths[colorType]?.includes(bitDepth) || bytes[26] !== 0 || bytes[27] !== 0 || interlace > 1) throw new Error('Invalid PNG IHDR encoding fields.');
    // Validate chunk boundaries, then retain image data and color keying for alpha decoding.
    let cursor = 8, ended = false, keyed = null;
    const data = [];
    while (cursor + 12 <= bytes.length) {
      const size = bytes.readUInt32BE(cursor);
      if (size > bytes.length - cursor - 12) throw new Error('Truncated PNG chunk.');
      const type = bytes.toString('ascii', cursor + 4, cursor + 8);
      const body = bytes.subarray(cursor + 8, cursor + 8 + size);
      if (type === 'IDAT' && size > 0) data.push(Buffer.from(body));
      if (type === 'tRNS') keyed = Buffer.from(body);
      cursor += size + 12;
      if (type === 'IEND') { if (size !== 0 || cursor !== bytes.length) throw new Error('Invalid PNG IEND or trailing bytes.'); ended = true; break; }
    }
    if (!data.length || !ended) throw new Error('PNG is missing IDAT image data or IEND.');
    return { imageWidth: width, imageHeight: height, bitDepth, colorType, interlace,
      data: Buffer.concat(data), transparency: colorKey(colorType, keyed),
      hash: createHash('sha256').update(bytes).digest('hex') };
  } finally { await handle.close(); }
}

/** Normalize tRNS into comparable samples; a malformed chunk leaves the image opaque. */
function colorKey(colorType, keyed) {
  if (!keyed) return null;
  if (colorType === 3) return [...keyed];
  if (colorType === 0 && keyed.length === 2) return [keyed.readUInt16BE(0)];
  if (colorType === 2 && keyed.length === 6) return [0, 2, 4].map((offset) => keyed.readUInt16BE(offset));
  return null;
}

function paeth(left, up, corner) {
  const estimate = left + up - corner;
  const toLeft = Math.abs(estimate - left), toUp = Math.abs(estimate - up), toCorner = Math.abs(estimate - corner);
  return toLeft <= toUp && toLeft <= toCorner ? left : toUp <= toCorner ? up : corner;
}

/** Reverse the five PNG line filters; rows are byte aligned including sub-byte depths. */
function unfilter(raw, height, stride, bpp) {
  const out = Buffer.alloc(height * stride);
  for (let row = 0, source = 0; row < height; row++) {
    const filter = raw[source++], line = row * stride, above = line - stride;
    if (filter > 4) return null;
    for (let index = 0; index < stride; index++) {
      const left = index >= bpp ? out[line + index - bpp] : 0;
      const up = row ? out[above + index] : 0;
      const corner = row && index >= bpp ? out[above + index - bpp] : 0;
      const delta = filter === 1 ? left : filter === 2 ? up
        : filter === 3 ? (left + up) >> 1 : filter === 4 ? paeth(left, up, corner) : 0;
      out[line + index] = raw[source + index] + delta;
    }
    source += stride;
  }
  return out;
}

/** Decode alpha coverage only; never color fidelity or artistic quality. */
function decodeAlpha(png) {
  if (png.interlace) return { error: 'interlaced PNGs cannot be measured; save a non-interlaced file' };
  if (png.imageWidth * png.imageHeight > MAX_DECODE_PIXELS) return { error: `image exceeds ${MAX_DECODE_PIXELS} decoded pixels` };
  const channels = CHANNELS[png.colorType];
  const stride = Math.ceil(png.imageWidth * channels * png.bitDepth / 8);
  const bpp = Math.max(1, Math.ceil(channels * png.bitDepth / 8));
  let raw;
  try { raw = inflateSync(png.data); } catch (error) { return { error: `image data could not be inflated (${error.message})` }; }
  if (raw.length !== png.imageHeight * (stride + 1)) return { error: 'image data length disagrees with the declared dimensions' };
  const planes = unfilter(raw, png.imageHeight, stride, bpp);
  if (!planes) return { error: 'image uses an unknown PNG line filter' };
  const sample = (x, y, channel) => {
    const index = x * channels + channel;
    if (png.bitDepth === 8) return planes[y * stride + index];
    if (png.bitDepth === 16) return planes[y * stride + index * 2] * 256 + planes[y * stride + index * 2 + 1];
    const position = index * png.bitDepth;
    return (planes[y * stride + (position >> 3)] >> (8 - png.bitDepth - (position & 7))) & ((1 << png.bitDepth) - 1);
  };
  const keyed = png.transparency;
  const alpha = (x, y, channel) => (png.bitDepth === 16 ? sample(x, y, channel) >> 8 : sample(x, y, channel));
  const opaque = (x, y) => {
    if (png.colorType === 6) return alpha(x, y, 3) >= OPAQUE_ALPHA;
    if (png.colorType === 4) return alpha(x, y, 1) >= OPAQUE_ALPHA;
    if (png.colorType === 3) return (keyed?.[sample(x, y, 0)] ?? 255) >= OPAQUE_ALPHA;
    if (png.colorType === 0) return !keyed || sample(x, y, 0) !== keyed[0];
    return !keyed || [0, 1, 2].some((channel) => sample(x, y, channel) !== keyed[channel]);
  };
  return { opaque };
}

/** Frame-local bounds of the visible silhouette, measured from decoded alpha. */
function measureArt(reader, frame) {
  if (reader.error) return reader;
  let left = Infinity, right = -Infinity, top = Infinity, bottom = -Infinity;
  for (let y = frame.y; y < frame.y + frame.height; y++) {
    for (let x = frame.x; x < frame.x + frame.width; x++) {
      if (!reader.opaque(x, y)) continue;
      if (x < left) left = x;
      if (x > right) right = x;
      if (y < top) top = y;
      if (y > bottom) bottom = y;
    }
  }
  if (right < left) return { error: 'frame decodes to no visible pixels; correct the crop or the artwork' };
  return { left: left - frame.x, right: right - frame.x, top: top - frame.y, bottom: bottom - frame.y };
}

/** Read classifier verdicts. The checker never classifies; it only verifies pinned rulings. */
async function loadRulings(file, into, fail) {
  let document;
  try {
    const info = await stat(file);
    if (!info.isFile() || info.size > MAX_CONTRACT_BYTES) throw new Error('Rulings must be a regular JSON file no larger than 8 MiB.');
    document = JSON.parse((await readFile(file, 'utf8')).replace(/^\uFEFF/, ''));
  } catch (error) { fail(`Cannot read overhangRulings ${file}: ${error.message}`); return; }
  if (!shape(document, ['version', 'rulings'], [], 'overhangRulings', fail)) return;
  if (document.version !== 1) fail('overhangRulings.version must be 1.');
  if (!Array.isArray(document.rulings)) { fail('overhangRulings.rulings must be an array.'); return; }
  document.rulings.forEach((ruling, i) => {
    const at = `rulings[${i}]`;
    if (!shape(ruling, ['asset', 'imageSha256', 'regionSha256', 'classification', 'basis', 'classifier'], [], at, fail)) return;
    for (const key of ['asset', 'basis']) if (!nonempty(ruling[key])) fail(`${at}.${key} must be a nonempty string.`);
    for (const key of ['imageSha256', 'regionSha256']) if (!/^[0-9a-f]{64}$/i.test(ruling[key] ?? '')) fail(`${at}.${key} must be 64 hexadecimal characters.`);
    // Sides are judged separately: a legitimate eave on one side cannot excuse a wall base on the other.
    if (!object(ruling.classification) || !Object.keys(ruling.classification).length) fail(`${at}.classification must name a class per spilling side.`);
    else {
      for (const [side, name] of Object.entries(ruling.classification)) {
        if (!['left', 'right'].includes(side)) fail(`${at}.classification has unknown side ${side}; expected left or right.`);
        else if (!Object.hasOwn(OVERHANG_CLASSES, name)) fail(`${at}.classification.${side} must be one of ${Object.keys(OVERHANG_CLASSES).join(', ')}.`);
      }
    }
    if (shape(ruling.classifier, ['model', 'promptSha256', 'decidedAt'], [], `${at}.classifier`, fail)) {
      for (const key of ['model', 'decidedAt']) if (!nonempty(ruling.classifier[key])) fail(`${at}.classifier.${key} must be a nonempty string.`);
      if (!/^[0-9a-f]{64}$/i.test(ruling.classifier.promptSha256 ?? '')) fail(`${at}.classifier.promptSha256 must be 64 hexadecimal characters.`);
    }
    if (nonempty(ruling.asset)) {
      if (into.has(ruling.asset)) fail(`${at} duplicates a ruling for asset ${ruling.asset}.`);
      else into.set(ruling.asset, ruling);
    }
  });
}

export async function checkContract(contract, directory = process.cwd()) {
  const report = result(contract);
  const fail = (message) => report.errors.push({ message });
  // Atlases are shared between assets; inspect and decode each file once per run.
  const inspected = new Map(), alpha = new Map();
  if (!shape(contract, ['version', 'pack', 'projection', 'tolerances', 'heightReferences', 'assets'], ['overhangRulings'], 'contract', fail)) return report;
  if (contract.version !== 1) fail('contract.version must be 1.');
  if (!nonempty(contract.pack)) fail('contract.pack must be a nonempty string.');
  if (shape(contract.projection, ['tileWidth', 'tileHeight', 'heightPixelsPerUnit'], [], 'projection', fail)) {
    for (const [key, value] of Object.entries(contract.projection)) if (!positive(value)) fail(`projection.${key} must be finite and positive.`);
  }
  if (shape(contract.tolerances, ['groundErrorPx', 'heightErrorPx'], [], 'tolerances', fail)) {
    for (const [key, value] of Object.entries(contract.tolerances)) if (!finite(value) || value < 0) fail(`tolerances.${key} must be finite and nonnegative.`);
    // Every ground check is measured against this slack, so an unbounded value waives all of them.
    // Half a tile is where the tolerance stops being smaller than the cell it is measuring.
    const half = positive(contract.projection?.tileWidth) ? contract.projection.tileWidth / 2 : undefined;
    if (half !== undefined && finite(contract.tolerances.groundErrorPx) && contract.tolerances.groundErrorPx >= half) {
      fail(`tolerances.groundErrorPx ${contract.tolerances.groundErrorPx} must stay below half a tile width (${half}); a slack that wide waives contact, footprint and overhang measurement instead of absorbing measurement error.`);
    }
  }
  if (!object(contract.heightReferences)) fail('heightReferences must be an object of named positive world-unit values.');
  else for (const [key, value] of Object.entries(contract.heightReferences)) if (!nonempty(key) || !positive(value)) fail(`heightReferences.${key} must name a finite positive world-unit value.`);
  if (!Array.isArray(contract.assets) || contract.assets.length === 0 || contract.assets.length > 2048) fail('assets must contain between 1 and 2048 assets.');
  const rulings = new Map();
  if (Object.hasOwn(contract, 'overhangRulings')) {
    if (!nonempty(contract.overhangRulings)) fail('overhangRulings must be a local path to the classified overhang rulings.');
    else await loadRulings(path.resolve(directory, contract.overhangRulings), rulings, fail);
  }
  if (report.errors.length) return report;
  const ids = new Set();
  for (const asset of contract.assets) {
    const assetId = nonempty(asset?.id) ? asset.id : undefined;
    const add = (message) => report.errors.push({ ...(assetId ? { assetId } : {}), message });
    const start = report.errors.length;
    if (!shape(asset, ['id', 'kind', 'image', 'sha256', 'frame', 'anchor', 'render', 'footprint', 'groundPoints', 'heights', 'allowedOverhang'], ['overhangPx'], 'asset', add)) continue;
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
    if (Object.hasOwn(asset, 'overhangPx')) {
      if (!finite(asset.overhangPx) || asset.overhangPx < 0) add('overhangPx must be a finite nonnegative silhouette budget in rendered pixels.');
      else if (asset.overhangPx > 0 && !nonempty(asset.allowedOverhang)) add('A positive overhangPx requires allowedOverhang to state which artwork deliberately leaves the footprint.');
    }
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
    let info = inspected.get(imagePath);
    if (!info) {
      try { info = await inspectPNG(imagePath); }
      catch (error) { add(`Cannot inspect PNG ${asset.image}: ${error.message}`); continue; }
      inspected.set(imagePath, info);
    }
    if (asset.frame.x + asset.frame.width > info.imageWidth || asset.frame.y + asset.frame.height > info.imageHeight) { add(`frame exceeds PNG bounds ${info.imageWidth}x${info.imageHeight}.`); continue; }
    if (!alpha.has(imagePath)) alpha.set(imagePath, decodeAlpha(info));
    const art = measureArt(alpha.get(imagePath), asset.frame);
    const silhouette = art.error ? undefined : { left: art.left, right: art.right, top: art.top, bottom: art.bottom };
    report.assets.push({ ...asset, imagePath, imageWidth: info.imageWidth, imageHeight: info.imageHeight, scaleX, scaleY, silhouette });
    if (info.hash !== asset.sha256.toLowerCase()) add(`sha256 mismatch for ${asset.image}; expected ${asset.sha256.toLowerCase()}, actual ${info.hash}. Recalibrate changed artwork before updating its hash.`);
    if (asset.kind !== 'terrain' && Math.abs(scaleX - scaleY) > 1e-9 * Math.max(scaleX, scaleY)) add('Props and actors require uniform render scaling; remove render.height or preserve the source aspect ratio.');
    const offset = asset.render.offset ?? { x: 0, y: 0 };
    const overhang = asset.overhangPx ?? 0;
    if (art.error) add(`Cannot measure the silhouette of ${asset.image}: ${art.error}`);
    else if (asset.kind !== 'actor') {
      // No pixel outside the footprint's ground diamond can belong to this asset at any height,
      // so compare the decoded silhouette against that band instead of the declared contacts.
      const { tileWidth } = contract.projection;
      const tolerance = contract.tolerances.groundErrorPx;
      const slack = overhang + tolerance + 1e-9;
      const edge = (column) => (column - asset.anchor.x * asset.frame.width) * scaleX + offset.x;
      const far = (asset.footprint.columns + asset.footprint.rows - 1) * tileWidth / 2;
      const spill = { left: -tileWidth / 2 - edge(art.left), right: edge(art.right + 1) - far };
      const exceeded = Object.entries(spill).filter(([, over]) => over > slack);
      for (const [side, over] of exceeded) {
        add(`Decoded silhouette spills ${over.toFixed(4)} rendered px past the ${side} edge of the ground diamond that footprint ${asset.footprint.columns}x${asset.footprint.rows} reserves (overhangPx ${overhang}, groundErrorPx ${contract.tolerances.groundErrorPx}). Widen the footprint, rescale or recenter the artwork, or declare a justified overhangPx; declared contact points cannot shrink measured artwork.`);
      }
      // Reported whenever art leaves the diamond, so the band can be viewed and classified before a
      // budget exists. The hash deliberately excludes overhangPx, so a ruling made now still holds.
      if (Math.max(spill.left, spill.right) > tolerance) {
        const columns = { left: [], right: [] };
        for (let column = art.left; column <= art.right; column++) {
          if (edge(column) < -tileWidth / 2 - tolerance) columns.left.push(column);
          if (edge(column + 1) > far + tolerance) columns.right.push(column);
        }
        // How far the spilling material stays above the nearest declared ground contact. Screen y
        // conflates height and depth, so this cannot decide the class on its own; it is the evidence
        // a classifier is asked to judge, pinned here so the verdict can be audited against it.
        const reader = alpha.get(imagePath);
        const groundY = Math.max(...asset.groundPoints.map(({ source }) => source.y));
        const clearance = (list) => {
          let lowest = -Infinity;
          for (const column of list) {
            for (let row = asset.frame.height - 1; row > lowest; row--) {
              if (reader.opaque(asset.frame.x + column, asset.frame.y + row)) { lowest = row; break; }
            }
          }
          return finite(lowest) ? (groundY - lowest) * scaleY : null;
        };
        const region = {
          asset: asset.id, image: asset.image, frame: asset.frame, anchor: asset.anchor,
          render: asset.render, footprint: asset.footprint, projection: contract.projection,
          silhouette, spill,
          columns: Object.fromEntries(Object.entries(columns).map(([side, list]) =>
            [side, list.length ? { from: list[0], to: list[list.length - 1], groundClearancePx: clearance(list) } : null])),
        };
        const regionSha256 = createHash('sha256').update(canonical(region)).digest('hex');
        report.assets[report.assets.length - 1].overhang = { ...region, regionSha256 };
        const ruling = rulings.get(asset.id);
        if (exceeded.length) {
          // Already reported as beyond budget; a verdict cannot rescue art that does not fit.
        } else if (!ruling) {
          add(`Overhang of ${Math.max(spill.left, spill.right).toFixed(4)} px is permitted only by overhangPx ${overhang} and needs a classified ruling. Classify the spilling columns and record a ruling with regionSha256 ${regionSha256}; prose in allowedOverhang is not a verdict.`);
        } else if (ruling.regionSha256.toLowerCase() !== regionSha256) {
          add(`Overhang ruling was decided for a different region (ruling ${ruling.regionSha256.toLowerCase()}, measured ${regionSha256}). Reclassify after any change to the artwork, frame, anchor, scale, footprint or projection.`);
        } else if (ruling.imageSha256.toLowerCase() !== info.hash) {
          add(`Overhang ruling judged different artwork (ruling ${ruling.imageSha256.toLowerCase()}, actual ${info.hash}).`);
        } else {
          report.assets[report.assets.length - 1].overhang.classification = ruling.classification;
          const spilling = Object.entries(region.columns).filter(([, span]) => span).map(([side]) => side);
          const judged = Object.keys(ruling.classification);
          for (const side of spilling) {
            if (!judged.includes(side)) add(`Overhang ruling leaves the ${side} spill unjudged; classify every side the silhouette leaves.`);
            else if (!OVERHANG_CLASSES[ruling.classification[side]]) add(`The ${side} overhang is classified as ${ruling.classification[side]}, which may not leave the footprint: ${ruling.basis}. Artwork meeting the ground belongs inside reserved cells.`);
          }
          for (const side of judged) if (!spilling.includes(side)) add(`Overhang ruling classifies a ${side} spill that is not measured; reclassify the current region.`);
        }
      }
    }
    if (!art.error && asset.kind === 'prop') {
      // The renderer sorts depth and blocks movement with a host-declared body height, so the
      // artwork's own top has to bound it. A pixel at cell (c,r) and height h draws at screen
      // y = (r-c)*tileHeight/2 - h; which cell owns the highest pixel is not decidable from the
      // silhouette, so this is the band the footprint allows rather than a single figure.
      const { tileHeight } = contract.projection;
      const top = (art.top - asset.anchor.y * asset.frame.height) * scaleY + offset.y;
      report.assets[report.assets.length - 1].bodyHeightPx = {
        low: -(asset.footprint.columns - 1) * tileHeight / 2 - top,
        high: (asset.footprint.rows - 1) * tileHeight / 2 - top,
      };
    }
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
