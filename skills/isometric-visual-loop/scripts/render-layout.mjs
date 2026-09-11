#!/usr/bin/env node
/** Render a semantic spatial-layout v1 file with the package's public projection. */
import { createHash } from 'node:crypto';
import { access, mkdir, readFile, writeFile } from 'node:fs/promises';
import { constants } from 'node:fs';
import { dirname, isAbsolute, relative, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const MAX_CELLS = 20_000;
const MAX_COORDINATE = 100_000;
const MAX_DIMENSION = 32_768;
const MAX_PNG_PIXELS = 16_000_000;
const PAD = 32;
const COLORS = Object.freeze({ planting: '#9aaa69', paving: '#c9b99a', grass: '#82a96b', soil: '#a87855', water: '#72a9bd', deck: '#b18a61', building: '#77645b', tree: '#617a52', prop: '#9a8069', bridge: '#a87952' });

function fail(message) { throw new Error(message); }
function hash(value) { return createHash('sha256').update(value).digest('hex'); }
function esc(value) { return String(value).replace(/[&<>"']/g, character => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&apos;' })[character]); }
function isObject(value) { return value !== null && typeof value === 'object' && !Array.isArray(value); }
function id(value, label) { if (typeof value !== 'string' || !value) fail(`${label} needs a nonempty id`); return value; }
function cell(value, label) {
  if (!Array.isArray(value) || value.length !== 3 || !Number.isInteger(value[0]) || !Number.isInteger(value[1]) || typeof value[2] !== 'string' || !value[2]) fail(`${label} must be [column,row,floor]`);
  if (Math.abs(value[0]) > MAX_COORDINATE || Math.abs(value[1]) > MAX_COORDINATE) fail(`${label} coordinate exceeds ${MAX_COORDINATE}`);
  return { c: value[0], r: value[1], level: value[2] };
}
function cellList(value, label, { required = true } = {}) {
  if (!Array.isArray(value) || (required && value.length === 0)) fail(`${label} needs ${required ? 'a nonempty' : 'an'} cell list`);
  if (value.length > MAX_CELLS) fail(`${label} exceeds ${MAX_CELLS} cells`);
  return value.map((entry, index) => cell(entry, `${label}[${index}]`));
}
function objects(value, label) { if (!Array.isArray(value)) fail(`${label} must be an array`); return value; }

export function validateLayout(layout) {
  if (!isObject(layout) || layout.version !== 1) fail('Spatial layout version must be 1');
  if ('elevation' in layout) fail('Top-level elevation is not part of spatial-layout v1; provide a host level mapping before rendering elevated layouts');
  const unique = (entries, label) => {
    const known = new Set();
    return entries.map((entry, index) => {
      if (!isObject(entry)) fail(`${label}[${index}] must be an object`);
      const entryId = id(entry.id, `${label}[${index}]`);
      if (known.has(entryId)) fail(`${label} ids must be unique`);
      known.add(entryId);
      return entry;
    });
  };
  const regions = unique(objects(layout.regions, 'regions'), 'regions').map(region => ({ ...region, id: id(region.id, 'region'), kind: id(region.kind, `region ${region.id}`), cells: cellList(region.cells, `region ${region.id}.cells`), underBridgeCells: region.underBridgeCells === undefined ? [] : cellList(region.underBridgeCells, `region ${region.id}.underBridgeCells`, { required: false }) }));
  const instances = unique(objects(layout.instances, 'instances'), 'instances').map(instance => ({ ...instance, id: id(instance.id, 'instance'), kind: id(instance.kind, `instance ${instance.id}`), footprint: cellList(instance.footprint, `instance ${instance.id}.footprint`), approaches: instance.approaches === undefined ? [] : cellList(instance.approaches, `instance ${instance.id}.approaches`, { required: false }) }));
  const routes = unique(objects(layout.routes, 'routes'), 'routes').map(route => ({ ...route, id: id(route.id, 'route'), cells: cellList(route.cells, `route ${route.id}.cells`), start: cell(route.start, `route ${route.id}.start`), goals: cellList(route.goals, `route ${route.id}.goals`) }));
  const bridges = unique(objects(layout.bridges, 'bridges'), 'bridges').map(bridge => {
    const landings = cellList(bridge.landings, `bridge ${bridge.id}.landings`);
    if (landings.length !== 2) fail(`bridge ${bridge.id}.landings needs exactly two cells`);
    return { ...bridge, id: id(bridge.id, 'bridge'), deck: cellList(bridge.deck, `bridge ${bridge.id}.deck`), landings, waterOverlayCells: bridge.waterOverlayCells === undefined ? [] : cellList(bridge.waterOverlayCells, `bridge ${bridge.id}.waterOverlayCells`, { required: false }) };
  });
  const spawn = cell(layout.spawn, 'spawn');
  const total = regions.reduce((count, item) => count + item.cells.length + item.underBridgeCells.length, 0) + instances.reduce((count, item) => count + item.footprint.length + item.approaches.length, 0) + routes.reduce((count, item) => count + item.cells.length + item.goals.length + 1, 0) + bridges.reduce((count, item) => count + item.deck.length + item.landings.length + item.waterOverlayCells.length, 0) + 1;
  if (total > MAX_CELLS) fail(`Layout exceeds ${MAX_CELLS} total cells`);
  const floors = new Set(allCells({ regions, instances, routes, bridges, spawn }).map(entry => entry.level));
  if (floors.size !== 1) fail('render-layout supports one floor only: spatial-layout v1 has no host height mapping for multi-floor projection');
  return { regions, instances, routes, bridges, spawn };
}

async function exists(path) { try { await access(path, constants.F_OK); return true; } catch { return false; } }
export async function findPackageRoot(start = dirname(fileURLToPath(import.meta.url))) {
  let directory = resolve(start);
  while (true) {
    if (await exists(resolve(directory, 'package.json'))) return directory;
    const parent = dirname(directory); if (parent === directory) fail('Could not find package.json above render-layout.mjs'); directory = parent;
  }
}
export async function loadProject(packageRoot) {
  packageRoot ??= await findPackageRoot();
  const source = resolve(packageRoot, 'src/core.ts');
  const fallback = resolve(packageRoot, 'dist/core.js');
  const modulePath = await exists(source) ? source : await exists(fallback) ? fallback : null;
  if (!modulePath) fail(`No public core module found in ${packageRoot} (expected src/core.ts or dist/core.js)`);
  const api = await import(pathToFileURL(modulePath).href);
  if (typeof api.project !== 'function') fail(`Public core module does not export project: ${modulePath}`);
  return { project: api.project, modulePath };
}
function point(project, entry, tileWidth, tileHeight) { return project({ c: entry.c, r: entry.r, level: entry.level }, tileWidth, tileHeight); }
function diamond(center, tileWidth, tileHeight, origin) { return `${center.x - tileWidth / 2 - origin.x},${center.y - origin.y} ${center.x - origin.x},${center.y - tileHeight / 2 - origin.y} ${center.x + tileWidth / 2 - origin.x},${center.y - origin.y} ${center.x - origin.x},${center.y + tileHeight / 2 - origin.y}`; }
function allCells(layout) { return [...layout.regions.flatMap(item => [...item.cells, ...item.underBridgeCells]), ...layout.instances.flatMap(item => [...item.footprint, ...item.approaches]), ...layout.routes.flatMap(item => [...item.cells, item.start, ...item.goals]), ...layout.bridges.flatMap(item => [...item.deck, ...item.landings, ...item.waterOverlayCells]), layout.spawn]; }
function bounds(project, layout, tileWidth, tileHeight) {
  const points = allCells(layout).map(entry => point(project, entry, tileWidth, tileHeight));
  const minX = Math.min(...points.map(entry => entry.x - tileWidth / 2)) - PAD;
  const maxX = Math.max(...points.map(entry => entry.x + tileWidth / 2)) + PAD;
  const minY = Math.min(...points.map(entry => entry.y - tileHeight / 2)) - PAD;
  const maxY = Math.max(...points.map(entry => entry.y + tileHeight / 2)) + PAD;
  const width = Math.ceil(maxX - minX); const height = Math.ceil(maxY - minY);
  if (!Number.isFinite(width) || !Number.isFinite(height) || width > MAX_DIMENSION || height > MAX_DIMENSION) fail(`Projected output exceeds ${MAX_DIMENSION}px per side`);
  return { origin: { x: minX, y: minY }, width, height };
}
function svgRoot(dimensions, contents) { return `<svg xmlns="http://www.w3.org/2000/svg" width="${dimensions.width}" height="${dimensions.height}" viewBox="0 0 ${dimensions.width} ${dimensions.height}" shape-rendering="crispEdges">${contents}</svg>\n`; }
function flatSvg(project, layout, dimensions, tileWidth, tileHeight) {
  const regions = layout.regions.flatMap(region => [...region.cells, ...region.underBridgeCells].map(entry => `<polygon points="${diamond(point(project, entry, tileWidth, tileHeight), tileWidth, tileHeight, dimensions.origin)}" fill="${COLORS[region.kind] ?? '#b4aa9d'}"/>`));
  const instances = layout.instances.flatMap(instance => instance.footprint.map(entry => `<polygon points="${diamond(point(project, entry, tileWidth, tileHeight), tileWidth, tileHeight, dimensions.origin)}" fill="${COLORS[instance.kind] ?? COLORS.prop}"/>`));
  const bridges = layout.bridges.flatMap(bridge => bridge.deck.map(entry => `<polygon points="${diamond(point(project, entry, tileWidth, tileHeight), tileWidth, tileHeight, dimensions.origin)}" fill="${COLORS.bridge}"/>`));
  return svgRoot(dimensions, `${regions.join('')}${instances.join('')}${bridges.join('')}`);
}
function landmarks(project, layout, tileWidth, tileHeight) {
  const make = (label, entry) => ({ label, cell: [entry.c, entry.r, entry.level], center: point(project, entry, tileWidth, tileHeight) });
  return [make('spawn', layout.spawn), ...layout.instances.flatMap(instance => instance.approaches.map((entry, index) => make(`entrance:${instance.id}:${index + 1}`, entry))), ...layout.bridges.flatMap(bridge => [make(`bridge:${bridge.id}:start`, bridge.landings[0]), make(`bridge:${bridge.id}:end`, bridge.landings[1])])];
}
function debugText(value) { return value.length > 42 ? `${value.slice(0, 39)}…` : value; }
function debugSvg(project, layout, dimensions, tileWidth, tileHeight, marks) {
  const base = flatSvg(project, layout, dimensions, tileWidth, tileHeight).replace(/<\/svg>\n$/, '');
  const label = mark => `<text data-full-label="${esc(mark.label)}" x="${Math.min(dimensions.width - 4, Math.max(4, mark.center.x - dimensions.origin.x + 6))}" y="${Math.min(dimensions.height - 4, Math.max(12, mark.center.y - dimensions.origin.y - 6))}" font-family="sans-serif" font-size="12" fill="#24201d">${esc(debugText(mark.label))}<title>${esc(mark.label)}</title></text>`;
  const labels = marks.map(mark => `<g><circle cx="${mark.center.x - dimensions.origin.x}" cy="${mark.center.y - dimensions.origin.y}" r="4" fill="#24201d"/>${label(mark)}</g>`).join('');
  const spawn = point(project, layout.spawn, tileWidth, tileHeight); const cAxis = point(project, { c: layout.spawn.c + 1, r: layout.spawn.r, level: layout.spawn.level }, tileWidth, tileHeight); const rAxis = point(project, { c: layout.spawn.c, r: layout.spawn.r + 1, level: layout.spawn.level }, tileWidth, tileHeight);
  const axisLines = [[cAxis, 'c+1'], [rAxis, 'r+1']].map(([end, label]) => `<g><line x1="${spawn.x - dimensions.origin.x}" y1="${spawn.y - dimensions.origin.y}" x2="${end.x - dimensions.origin.x}" y2="${end.y - dimensions.origin.y}" stroke="#24201d" stroke-width="2"/><text x="${end.x - dimensions.origin.x + 4}" y="${end.y - dimensions.origin.y - 4}" font-family="sans-serif" font-size="11" fill="#24201d">${label}</text></g>`).join('');
  const ids = [...layout.regions.map(item => ({ label: `region:${item.id}`, cell: item.cells[0] })), ...layout.instances.map(item => ({ label: `instance:${item.id}`, cell: item.footprint[0] })), ...layout.bridges.map(item => ({ label: `bridge:${item.id}`, cell: item.deck[0] }))].map(mark => { const center = point(project, mark.cell, tileWidth, tileHeight); return label({ ...mark, center: { x: center.x, y: center.y + 20 } }); }).join('');
  return `${base}<desc>Diagnostic labels longer than 42 characters are visibly truncated; data-full-label and title preserve the complete label.</desc>${axisLines}${labels}${ids}</svg>\n`;
}
function numberOption(value, name) { const parsed = Number(value); if (!Number.isFinite(parsed) || parsed <= 0 || parsed > 1024) fail(`${name} must be a finite number in 0..1024`); return parsed; }
export function parseArgs(argv) {
  const values = { tileWidth: 64, tileHeight: 32, png: false };
  for (let index = 0; index < argv.length; index += 1) {
    const value = argv[index];
    if (!value.startsWith('--') && !values.input) values.input = value;
    else if (value === '--out') values.out = argv[++index];
    else if (value === '--tile-width') values.tileWidth = numberOption(argv[++index], '--tile-width');
    else if (value === '--tile-height') values.tileHeight = numberOption(argv[++index], '--tile-height');
    else if (value === '--png') values.png = true;
    else fail(`Unknown or misplaced argument: ${value}`);
  }
  if (!values.input || !values.out) fail('Usage: render-layout.mjs layout.json --out NEW_DIR [--tile-width 64] [--tile-height 32] [--png]');
  return values;
}
export async function renderLayout({ input, out, tileWidth = 64, tileHeight = 32, png = false, packageRoot }) {
  tileWidth = numberOption(tileWidth, 'tileWidth'); tileHeight = numberOption(tileHeight, 'tileHeight');
  const inputPath = resolve(input); const outPath = resolve(out);
  if (await exists(outPath)) fail(`Output directory already exists: ${outPath}`);
  const inputText = await readFile(inputPath, 'utf8'); let inputJson;
  try { inputJson = JSON.parse(inputText); } catch (error) { fail(`Invalid JSON: ${error.message}`); }
  const layout = validateLayout(inputJson); const root = packageRoot ?? await findPackageRoot(); const api = await loadProject(root);
  const dimensions = bounds(api.project, layout, tileWidth, tileHeight); const marks = landmarks(api.project, layout, tileWidth, tileHeight);
  if (png && dimensions.width * dimensions.height > MAX_PNG_PIXELS) fail(`PNG output exceeds ${MAX_PNG_PIXELS} pixels`);
  const axis = ['origin', 'c+1', 'r+1'].map((label, index) => { const entry = index === 0 ? { c: 0, r: 0, level: layout.spawn.level } : index === 1 ? { c: 1, r: 0, level: layout.spawn.level } : { c: 0, r: 1, level: layout.spawn.level }; return { label, cell: [entry.c, entry.r, entry.level], center: point(api.project, entry, tileWidth, tileHeight) }; });
  const toolText = await readFile(fileURLToPath(import.meta.url), 'utf8');
  const projection = { version: 1, projectionModule: relative(root, api.modulePath).replaceAll('\\', '/'), inputHash: hash(inputText), toolHash: hash(toolText), tileWidth, tileHeight, output: { origin: dimensions.origin, width: dimensions.width, height: dimensions.height, padding: PAD }, landmarks: marks, axisUnitPoints: axis };
  await mkdir(outPath, { recursive: false });
  const svg = flatSvg(api.project, layout, dimensions, tileWidth, tileHeight);
  await Promise.all([writeFile(resolve(outPath, 'layout.svg'), svg), writeFile(resolve(outPath, 'layout-debug.svg'), debugSvg(api.project, layout, dimensions, tileWidth, tileHeight, marks)), writeFile(resolve(outPath, 'projection.json'), `${JSON.stringify(projection, null, 2)}\n`)]);
  if (png) {
    let playwright; try { playwright = await import('playwright'); } catch { fail('PNG rendering requires the optional authoring dependency playwright. Install it in the authoring environment, then rerun with --png.'); }
    const browser = await playwright.chromium.launch({ headless: true });
    try { const page = await browser.newPage({ viewport: { width: dimensions.width, height: dimensions.height } }); await page.setContent(`<!doctype html><style>html,body{margin:0;padding:0;overflow:hidden}svg{display:block}</style>${svg}`); await page.screenshot({ path: resolve(outPath, 'layout.png'), clip: { x: 0, y: 0, width: dimensions.width, height: dimensions.height } }); } finally { await browser.close(); }
  }
  return { outPath, projection };
}
if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  try { const result = await renderLayout(parseArgs(process.argv.slice(2))); process.stdout.write(`Rendered layout to ${result.outPath}\n`); } catch (error) { process.stderr.write(`render-layout: ${error.message}\n`); process.exitCode = 1; }
}
