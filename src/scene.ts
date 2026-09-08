import type { Scene } from './types.ts';
import { validateAssetManifest } from './art.ts';

function fail(path: string, message: string): never {
  throw new TypeError(`Invalid scene: ${path} ${message}`);
}

function record(value: unknown, path: string): Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) fail(path, 'must be an object');
  return value as Record<string, unknown>;
}

function number(value: unknown, path: string, min: number, max: number, integer = false): number {
  if (typeof value !== 'number' || !Number.isFinite(value) || value < min || value > max || (integer && !Number.isInteger(value))) {
    fail(path, `must be ${integer ? 'an integer' : 'a number'} between ${min} and ${max}`);
  }
  return value;
}

function string(value: unknown, path: string, max = 256): string {
  if (typeof value !== 'string' || !value.length || value.length > max) fail(path, `must be a nonempty string of at most ${max} characters`);
  return value;
}

function optionalBoolean(value: unknown, path: string): void {
  if (value !== undefined && typeof value !== 'boolean') fail(path, 'must be a boolean');
}

/** Validate JSON data before cloning: JSON.stringify alone silently loses invalid values. */
function cloneJSON(input: unknown): unknown {
  const ancestors = new Set<object>();
  let count = 0;
  function copy(value: unknown, path: string, depth: number): unknown {
    if (++count > 200_000 || depth > 64) fail(path, 'exceeds the data size or nesting limit');
    if (value === null || typeof value === 'boolean' || typeof value === 'string') return value;
    if (typeof value === 'number') {
      if (!Number.isFinite(value)) fail(path, 'must be finite');
      return value;
    }
    if (!value || typeof value !== 'object') fail(path, 'must contain only JSON values');
    if (ancestors.has(value)) fail(path, 'contains a cycle');
    const prototype = Object.getPrototypeOf(value);
    if (!Array.isArray(value) && prototype !== Object.prototype && prototype !== null) fail(path, 'must be a plain object');
    if (Object.getOwnPropertySymbols(value).length) fail(path, 'must not have symbol keys');
    if (Array.isArray(value) && value.length > 200_000) fail(path, 'exceeds the data size limit');
    for (const [key, descriptor] of Object.entries(Object.getOwnPropertyDescriptors(value))) {
      if (descriptor.get || descriptor.set) fail(`${path}.${key}`, 'must not contain accessors');
    }
    ancestors.add(value);
    let result: unknown;
    if (Array.isArray(value)) {
      result = Array.from(value, (entry, index) => copy(entry, `${path}[${index}]`, depth + 1));
    } else {
      result = Object.fromEntries(Object.entries(value).map(([key, entry]) => [key, copy(entry, `${path}.${key}`, depth + 1)]));
    }
    ancestors.delete(value);
    return result;
  }
  return copy(input, 'scene', 0);
}

/** Returns detached scene data. No renderer, application state, or backend is required. */
export function validateScene(input: unknown): Scene {
  const scene = record(cloneJSON(input), 'scene');
  if (scene.version !== 1 && scene.version !== 2) fail('version', 'must be 1 or 2');
  if (scene.version === 1 && (scene.levels !== undefined || scene.links !== undefined)) fail('version', 'requires version 2 for levels and links');
  string(scene.name, 'name');
  number(scene.tileWidth, 'tileWidth', 1, 4096);
  number(scene.tileHeight, 'tileHeight', 1, 4096);
  optionalBoolean(scene.diagonal, 'diagonal');
  if (scene.maxStepHeight !== undefined) number(scene.maxStepHeight, 'maxStepHeight', 0, 131072);
  const assets = scene.assets === undefined ? undefined : validateAssetManifest(scene.assets);
  if (assets) scene.assets = assets;
  const reference = (value: unknown, path: string, kind: 'textures' | 'animations'): void => {
    const id = string(value, path);
    const definitions = assets?.[kind];
    if (!definitions || !Object.hasOwn(definitions, id)) fail(path, `references an unknown ${kind === 'textures' ? 'texture' : 'animation'}`);
  };
  const tiles = record(scene.tiles, 'tiles');
  if (!Object.keys(tiles).length || Object.keys(tiles).length > 16384) fail('tiles', 'must contain 1 to 16384 definitions');
  for (const [id, value] of Object.entries(tiles)) {
    string(id, 'tile ID');
    const tile = record(value, `tiles.${id}`);
    number(tile.color, `tiles.${id}.color`, 0, 0xffffff, true);
    optionalBoolean(tile.walkable, `tiles.${id}.walkable`);
    if (tile.elevation !== undefined) number(tile.elevation, `tiles.${id}.elevation`, -65536, 65536);
    if (tile.texture !== undefined && tile.textures !== undefined) fail(`tiles.${id}`, 'must use texture or textures, not both');
    if (tile.texture !== undefined) reference(tile.texture, `tiles.${id}.texture`, 'textures');
    if (tile.sideTexture !== undefined) reference(tile.sideTexture, `tiles.${id}.sideTexture`, 'textures');
    if (tile.textures !== undefined) {
      if (!Array.isArray(tile.textures) || !tile.textures.length || tile.textures.length > 1024) fail(`tiles.${id}.textures`, 'must contain 1 to 1024 texture IDs');
      tile.textures.forEach((texture, i) => reference(texture, `tiles.${id}.textures[${i}]`, 'textures'));
    }
  }
  if (!Array.isArray(scene.map) || !scene.map.length || scene.map.length > 128) fail('map', 'must have 1 to 128 rows');
  const firstRow = scene.map[0];
  if (!Array.isArray(firstRow) || !firstRow.length || firstRow.length > 128) fail('map', 'must have 1 to 128 columns');
  const columns = firstRow.length;
  for (const [r, row] of scene.map.entries()) {
    if (!Array.isArray(row) || row.length !== columns) fail(`map[${r}]`, 'must match the first row width');
    for (const [c, id] of row.entries()) {
      if (typeof id !== 'string' || !Object.hasOwn(tiles, id)) fail(`map[${r}][${c}]`, 'references an unknown tile');
    }
  }
  const maps = new Map<string, (string | null)[][]>([['ground', scene.map as string[][]]]);
  if (scene.version === 2) {
    if (!Array.isArray(scene.levels) || scene.levels.length > 8) fail('levels', 'must be an array of at most 8 additional floors');
    if (!Array.isArray(scene.links) || scene.links.length > 4096) fail('links', 'must be an array of at most 4096 connections');
    const heights = new Set<number>([0]);
    for (const [index, value] of scene.levels.entries()) {
      const path = `levels[${index}]`, level = record(value, path);
      const id = string(level.id, `${path}.id`);
      if (maps.has(id)) fail(`${path}.id`, 'must be unique and cannot be ground');
      string(level.name, `${path}.name`);
      const height = number(level.height, `${path}.height`, -4096, 4096);
      if (heights.has(height)) fail(`${path}.height`, 'must be unique and nonzero');
      heights.add(height);
      if (!Array.isArray(level.map) || level.map.length !== scene.map.length) fail(`${path}.map`, 'must match ground map dimensions');
      for (const [r, row] of level.map.entries()) {
        if (!Array.isArray(row) || row.length !== columns) fail(`${path}.map[${r}]`, 'must match ground map dimensions');
        for (const [c, tile] of row.entries()) {
          if (tile !== null && (typeof tile !== 'string' || !Object.hasOwn(tiles, tile))) fail(`${path}.map[${r}][${c}]`, 'must be a known tile or null');
        }
      }
      maps.set(id, level.map as (string | null)[][]);
    }
    const edges = new Set<string>();
    for (const [index, value] of scene.links.entries()) {
      const path = `links[${index}]`, link = record(value, path);
      optionalBoolean(link.bidirectional, `${path}.bidirectional`);
      const endpoint = (value: unknown, path: string): { c: number; r: number; level: string } => {
        const cell = record(value, path);
        const c = number(cell.c, `${path}.c`, 0, columns - 1, true);
        const r = number(cell.r, `${path}.r`, 0, (scene.map as unknown[]).length - 1, true);
        const level = cell.level === undefined ? 'ground' : string(cell.level, `${path}.level`);
        const map = maps.get(level);
        if (!map) fail(`${path}.level`, 'references an unknown level');
        const tileId = map[r]![c];
        if (tileId === null || tileId === undefined || record(tiles[tileId], path).walkable === false) fail(path, 'must reference a walkable floor');
        return { c, r, level };
      };
      const from = endpoint(link.from, `${path}.from`), to = endpoint(link.to, `${path}.to`);
      if (from.level === to.level || Math.abs(from.c - to.c) + Math.abs(from.r - to.r) !== 1) fail(path, 'must connect cardinally adjacent cells on distinct floors');
      const key = JSON.stringify([from, to]), reverse = JSON.stringify([to, from]);
      if (edges.has(key) || edges.has(reverse)) fail(path, 'duplicates an existing connection');
      edges.add(key);
    }
  }
  const entityTypes = record(scene.entityTypes, 'entityTypes');
  if (Object.keys(entityTypes).length > 16384) fail('entityTypes', 'exceeds 16384 definitions');
  for (const [id, value] of Object.entries(entityTypes)) {
    string(id, 'entity type ID');
    const type = record(value, `entityTypes.${id}`);
    optionalBoolean(type.blocking, `${id}.blocking`);
    if (type.columns !== undefined) number(type.columns, `${id}.columns`, 1, 128, true);
    if (type.rows !== undefined) number(type.rows, `${id}.rows`, 1, 128, true);
    if (type.bodyHeight !== undefined) number(type.bodyHeight, `${id}.bodyHeight`, Number.MIN_VALUE, 4096);
    const visual = record(type.visual, `${id}.visual`);
    if (!['box', 'actor', 'gem', 'sprite'].includes(visual.kind as string)) fail(`${id}.visual.kind`, 'is unsupported');
    if (visual.color !== undefined) number(visual.color, `${id}.visual.color`, 0, 0xffffff, true);
    if (visual.height !== undefined) number(visual.height, `${id}.visual.height`, 0, 4096);
    if (visual.scale !== undefined) number(visual.scale, `${id}.visual.scale`, 0.01, 100);
    if (visual.fps !== undefined) number(visual.fps, `${id}.visual.fps`, 0.1, 120);
    if (visual.width !== undefined) number(visual.width, `${id}.visual.width`, Number.MIN_VALUE, 4096);
    if (visual.tint !== undefined) number(visual.tint, `${id}.visual.tint`, 0, 0xffffff, true);
    for (const key of ['anchor', 'offset']) {
      if (visual[key] !== undefined) {
        const point = record(visual[key], `${id}.visual.${key}`);
        for (const axis of ['x', 'y']) number(point[axis], `${id}.visual.${key}.${axis}`, key === 'anchor' ? 0 : -4096, key === 'anchor' ? 1 : 4096);
      }
    }
    if (visual.url !== undefined) string(visual.url, `${id}.visual.url`, 8192);
    if (visual.frames !== undefined) {
      if (!Array.isArray(visual.frames) || !visual.frames.length || visual.frames.length > 1024) fail(`${id}.visual.frames`, 'must contain 1 to 1024 URLs');
      visual.frames.forEach((url, i) => string(url, `${id}.visual.frames[${i}]`, 8192));
    }
    if (visual.texture !== undefined) reference(visual.texture, `${id}.visual.texture`, 'textures');
    if (visual.animation !== undefined) reference(visual.animation, `${id}.visual.animation`, 'animations');
    if (visual.kind === 'sprite' && ['url', 'frames', 'texture', 'animation'].filter(key => visual[key] !== undefined).length !== 1) {
      fail(`${id}.visual`, 'requires exactly one source: URL, frames, texture, or animation');
    }
    if (visual.animations !== undefined) {
      if (visual.kind !== 'sprite' || (visual.texture === undefined && visual.animation === undefined)) fail(`${id}.visual.animations`, 'requires a sprite with a named texture or animation base');
      const path = `${id}.visual.animations`, set = record(visual.animations, path);
      const states = (value: unknown, path: string, allowDirections: boolean): Record<string, unknown> => {
        const state = record(value, path);
        for (const [key, entry] of Object.entries(state)) {
          if (allowDirections && key === 'directions') continue;
          if (!['idle', 'walk', 'jump'].includes(key)) fail(`${path}.${key}`, 'is an unsupported animation state');
          reference(entry, `${path}.${key}`, 'animations');
        }
        return state;
      };
      states(set, path, true);
      if (set.directions !== undefined) {
        const directions = record(set.directions, `${path}.directions`);
        for (const [direction, value] of Object.entries(directions)) {
          if (!['n', 'ne', 'e', 'se', 's', 'sw', 'w', 'nw'].includes(direction)) fail(`${path}.directions.${direction}`, 'is an unsupported direction');
          states(value, `${path}.directions.${direction}`, false);
        }
      }
    }
  }
  if (!Array.isArray(scene.entities) || scene.entities.length > 16384) fail('entities', 'must be an array of at most 16384 entities');
  const ids = new Set<string>();
  for (const [index, value] of scene.entities.entries()) {
    const entity = record(value, `entities[${index}]`);
    const id = string(entity.id, `entities[${index}].id`);
    if (ids.has(id)) fail(`entities[${index}].id`, 'must be unique');
    ids.add(id);
    const typeId = string(entity.type, `${id}.type`);
    if (!Object.hasOwn(entityTypes, typeId)) fail(`${id}.type`, 'references an unknown entity type');
    const type = record(entityTypes[typeId], `${id}.type`);
    const c = number(entity.c, `${id}.c`, 0, columns - 1, true);
    const r = number(entity.r, `${id}.r`, 0, scene.map.length - 1, true);
    if (c + (type.columns as number ?? 1) > columns || r + (type.rows as number ?? 1) > scene.map.length) fail(id, 'footprint extends outside the map');
    const level = entity.level === undefined ? 'ground' : string(entity.level, `${id}.level`);
    const map = maps.get(level);
    if (!map) fail(`${id}.level`, 'references an unknown level');
    for (let dr = 0; dr < (type.rows as number ?? 1); dr++) {
      for (let dc = 0; dc < (type.columns as number ?? 1); dc++) {
        if (map[r + dr]![c + dc] === null) fail(id, 'footprint must be supported by a floor');
      }
    }
    if (entity.data !== undefined) record(entity.data, `${id}.data`);
  }
  if (scene.controlledId !== undefined && !ids.has(string(scene.controlledId, 'controlledId'))) fail('controlledId', 'references an unknown entity');
  return scene as unknown as Scene;
}
