import { readFile } from 'node:fs/promises';
import { existsSync } from 'node:fs';
import { pathToFileURL } from 'node:url';
import { resolve } from 'node:path';

const entry = new URL('../../../src/core.ts', import.meta.url);
const { WorldModel, project, sameCell } = await import(existsSync(entry) ? entry.href : new URL('../../../dist/core.js', import.meta.url).href);
const finite = value => typeof value === 'number' && Number.isFinite(value);
const array = (value, label) => { if (!Array.isArray(value)) throw new TypeError(`${label} must be an array`); return value; };

/** Check a host's declared expectations against its actual scene, not a second scene mock. */
export function checkAssembly(scene, plan) {
  const model = new WorldModel(scene);
  if (plan?.version !== 1 || typeof plan.actor !== 'string' || !model.entity(plan.actor)) throw new TypeError('Plan requires version 1 and an existing actor');
  const tolerance = plan.tolerancePx ?? 1;
  if (!finite(tolerance) || tolerance < 0) throw new TypeError('Invalid contact tolerance');
  const failures = [], results = [];
  const check = (condition, label) => { results.push({ label, pass: !!condition }); if (!condition) failures.push(label); };
  for (const placement of array(plan.placements ?? [], 'placements')) {
    const entity = model.entity(placement.entity);
    if (!entity) { check(false, `${placement.entity}: missing entity`); continue; }
    check(sameCell(entity, placement.origin), `${entity.id}: declared origin`);
    const visual = scene.entityTypes[entity.type].visual;
    for (const sample of array(placement.contacts, 'contacts')) {
      const texture = scene.assets?.textures[sample.texture];
      const frame = texture?.frame;
      if (!frame) { check(false, `${entity.id}/${sample.texture}: explicit source frame required`); continue; }
      const clipId = visual.animation;
      const bound = visual.texture === sample.texture || (clipId && scene.assets.animations?.[clipId]?.frames.includes(sample.texture));
      check(bound, `${entity.id}/${sample.texture}: bound to actual visual`);
      const anchor = visual.anchor ?? texture.anchor ?? { x: .5, y: 1 };
      const scale = (visual.width ?? frame.width) / frame.width * (visual.scale ?? 1);
      const actual = {
        x: (sample.source.x - anchor.x * frame.width) * scale + (visual.offset?.x ?? 0),
        y: (sample.source.y - anchor.y * frame.height) * scale + (visual.offset?.y ?? 0),
      };
      const expected = project(sample.grid, scene.tileWidth, scene.tileHeight, sample.height ?? 0);
      const error = Math.hypot(actual.x - expected.x, actual.y - expected.y);
      check(finite(error) && error <= tolerance, `${entity.id}/${sample.texture}: contact error ${error.toFixed(3)}px <= ${tolerance}px`);
    }
  }
  for (const cell of array(plan.blocked ?? [], 'blocked')) check(!model.canEnter(cell, plan.actor), `blocked ${cell.c},${cell.r}@${cell.level ?? 'ground'}`);
  for (const cell of array(plan.open ?? [], 'open')) check(model.canEnter(cell, plan.actor), `open ${cell.c},${cell.r}@${cell.level ?? 'ground'}`);
  for (const solid of array(plan.solidHeights ?? [], 'solidHeights')) {
    if (!finite(solid.minHeight) || solid.minHeight <= 0) throw new TypeError('Solid height must be positive');
    const heights = model.at(solid.cell).flatMap(entity => {
      const type = scene.entityTypes[entity.type];
      return type.blocking && finite(type.bodyHeight) ? [type.bodyHeight] : [];
    });
    check(heights.length && Math.max(...heights) >= solid.minHeight, `${solid.id}: explicit solid body covers ${solid.minHeight}px`);
  }
  for (const route of array(plan.routes ?? [], 'routes')) {
    const fresh = new WorldModel(scene);
    if (!fresh.canEnter(route.from, plan.actor)) { check(false, `${route.id}: route origin is blocked`); continue; }
    fresh.setPosition(plan.actor, route.from);
    check((fresh.path(plan.actor, route.to) !== null) === route.reachable, `${route.id}: reachable=${route.reachable}`);
  }
  for (const path of array(plan.paths ?? [], 'paths')) {
    const points = array(path.points, 'path points');
    if (points.length < 2) throw new TypeError('Exact paths require at least two cells');
    check(points.slice(1).every((cell, i) => model.canMove(plan.actor, points[i], cell)), `${path.id}: every exact walking segment`);
  }
  for (const clearance of array(plan.clearances ?? [], 'clearances')) {
    const floor = model.tile(clearance.cell);
    if (!floor || !finite(clearance.height) || clearance.height <= 0) throw new TypeError('Clearance requires a supported cell and positive body height');
    const feet = floor.elevation ?? 0;
    const ceiling = (scene.levels ?? []).flatMap(level => {
      const tileId = level.map[clearance.cell.r]?.[clearance.cell.c];
      if (!tileId) return [];
      const elevation = scene.tiles[tileId].elevation ?? 0;
      const top = level.height + elevation;
      return top > feet ? [top - Math.max(1, 8 + elevation)] : [];
    });
    check(!ceiling.length || Math.min(...ceiling) - feet >= clearance.height, `${clearance.id}: floor-slab clearance`);
  }
  return { pass: failures.length === 0, results, failures,
    limits: 'Declared contacts, cell occupancy, walking paths and current slab geometry only. Does not inspect pixels, dynamic motion, freeform colliders or aesthetics.' };
}

if (process.argv[1] && import.meta.url === pathToFileURL(resolve(process.argv[1])).href) {
  if (process.argv.length !== 4) throw new Error('Usage: node --experimental-strip-types check-assembly.mjs scene.json assembly-plan.json');
  const [scene, plan] = await Promise.all(process.argv.slice(2).map(async path => JSON.parse(await readFile(path, 'utf8'))));
  const result = checkAssembly(scene, plan);
  console.log(JSON.stringify(result, null, 2));
  if (!result.pass) process.exitCode = 1;
}
