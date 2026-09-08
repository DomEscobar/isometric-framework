import type { WorldModel } from './model.ts';
import { cellOnLevel, levelMaps, levelOf } from './levels.ts';
import type { Cell, EntityPose, EntityType, Scene } from './types.ts';

export interface Flight {
  from: Cell; to: Cell; fromHeight: number; toHeight: number;
  height: number; duration: number; elapsed: number;
}

export function bodyHeight(type: EntityType): number {
  if (type.bodyHeight !== undefined) return type.bodyHeight;
  const visual = type.visual;
  return (visual.kind === 'actor' ? 55 : visual.kind === 'box' ? visual.height ?? 32 : 32) * (visual.scale ?? 1);
}

export function flightPose(flight: Flight, progress: number): EntityPose {
  const t = Math.max(0, Math.min(1, progress));
  const rise = flight.toHeight - flight.fromHeight;
  // Solve one constant-gravity arc with an exact apex, rather than adding an
  // extra hump above the ascending start/end chord. Higher landings shorten descent.
  const curvature = (Math.sqrt(flight.height) + Math.sqrt(Math.max(0, flight.height - rise))) ** 2;
  const velocity = 2 * Math.sqrt(flight.height * curvature);
  return {
    position: cellOnLevel(flight.from.c + (flight.to.c - flight.from.c) * t,
      flight.from.r + (flight.to.r - flight.from.r) * t, levelOf(t === 1 ? flight.to : flight.from)),
    elevation: t === 1 ? flight.toHeight : flight.fromHeight + velocity * t - curvature * t * t,
    airborne: t < 1,
  };
}

export function supported(model: WorldModel, id: string, cell: Cell): boolean {
  const entity = model.entity(id);
  if (!entity) return false;
  const type = model.entityType(entity.type)!;
  const height = model.tile(cell)?.elevation;
  if (height === undefined) return false;
  for (let r = 0; r < (type.rows ?? 1); r++) for (let c = 0; c < (type.columns ?? 1); c++) {
    const part = cellOnLevel(cell.c + c, cell.r + r, levelOf(cell));
    if (!model.canEnter(part, id) || model.tile(part)?.elevation !== height) return false;
  }
  return true;
}

/** Conservative volume checks include the whole footprint and overhead slabs. */
export function clearPose(model: WorldModel, scene: Scene, id: string, pose: EntityPose): boolean {
  const entity = model.entity(id);
  if (!entity) return false;
  const type = model.entityType(entity.type)!;
  const bottom = pose.elevation + 0.001, top = bottom + bodyHeight(type);
  for (let r = 0; r < (type.rows ?? 1); r++) for (let c = 0; c < (type.columns ?? 1); c++) {
    const column = Math.round(pose.position.c) + c, row = Math.round(pose.position.r) + r;
    for (const level of levelMaps(scene)) {
      const cell = cellOnLevel(column, row, level.id);
      const tile = model.tile(cell);
      if (!tile) continue;
      const floorTop = tile.elevation ?? 0;
      const floorBottom = level.id === 'ground' ? -Infinity : floorTop - Math.max(1, 8 + floorTop - level.height);
      if (bottom < floorTop && top > floorBottom) return false;
      for (const other of model.at(cell)) {
        if (other.id === id) continue;
        const otherType = model.entityType(other.type)!;
        if (otherType.blocking && bottom < floorTop + bodyHeight(otherType) && top > floorTop) return false;
      }
    }
  }
  return true;
}

export function clearFlight(model: WorldModel, scene: Scene, id: string, flight: Flight): boolean {
  // Dense preflight prevents entering a platform from its underside or side.
  const samples = Math.max(96, Math.ceil(Math.hypot(flight.to.c - flight.from.c, flight.to.r - flight.from.r) * 48));
  for (let index = 0; index <= samples; index++) {
    if (!clearPose(model, scene, id, flightPose(flight, index / samples))) return false;
  }
  return true;
}

/** Segment against a box, used on relative bullet/actor motion to prevent tunneling. */
export function segmentBox(from: number[], to: number[], minimum: number[], maximum: number[]): number | null {
  let entry = 0, exit = 1;
  for (let axis = 0; axis < from.length; axis++) {
    const delta = to[axis]! - from[axis]!;
    if (Math.abs(delta) < 1e-12) {
      if (from[axis]! < minimum[axis]! || from[axis]! > maximum[axis]!) return null;
      continue;
    }
    let near = (minimum[axis]! - from[axis]!) / delta;
    let far = (maximum[axis]! - from[axis]!) / delta;
    if (near > far) [near, far] = [far, near];
    entry = Math.max(entry, near); exit = Math.min(exit, far);
    if (entry > exit) return null;
  }
  return entry;
}
