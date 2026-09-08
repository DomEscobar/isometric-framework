import { autotileMasks, resolveAutotiles, type AutotileResult } from '../../src/core.ts';
import type { Cell, Point, Scene, TextureDefinition } from '../../src/types.ts';

export const MAP_SIZE = 9;
export const ACTOR_ID = 'traveler';
export const PRESETS = ['straight', 'l', 'rectangle', 'ring', 'diagonal'] as const;
export type Preset = typeof PRESETS[number];
export interface LabState { beds: Cell[]; actor: Cell }
export interface Tileset {
  version: number;
  mode: string;
  tileWidth: number;
  tileHeight: number;
  bodyHeight: number;
  variants: Readonly<Partial<Record<number, string | readonly string[]>>>;
  textures: Record<string, TextureDefinition>;
  anchor: Point;
}

export function createLabState(preset: Preset = 'ring'): LabState {
  const beds: Cell[] = [];
  for (let r = 0; r < MAP_SIZE; r++) for (let c = 0; c < MAP_SIZE; c++) {
    const square = c >= 2 && c <= 6 && r >= 2 && r <= 6;
    const include = preset === 'straight' ? r === 4 && c >= 2 && c <= 6
      : preset === 'l' ? (c === 2 && r >= 2 && r <= 6) || (r === 6 && c >= 2 && c <= 6)
      : preset === 'rectangle' ? square
      : preset === 'ring' ? square && (c === 2 || c === 6 || r === 2 || r === 6)
      : (c === 3 && r === 3) || (c === 4 && r === 4);
    if (include) beds.push({ c, r });
  }
  return { beds, actor: { c: 1, r: 7 } };
}

function inMap(cell: Cell): boolean {
  return Number.isInteger(cell.c) && Number.isInteger(cell.r)
    && cell.c >= 0 && cell.r >= 0 && cell.c < MAP_SIZE && cell.r < MAP_SIZE
    && (cell.level === undefined || cell.level === 'ground');
}

/** Immutable host edit; topology is recomputed by createAutotileScene. */
export function toggleBed(state: LabState, cell: Cell): LabState {
  if (!inMap(cell)) throw new Error('Choose a tile inside the map.');
  if (cell.c === state.actor.c && cell.r === state.actor.r) throw new Error('Move the traveler before planting this tile.');
  const exists = state.beds.some(bed => bed.c === cell.c && bed.r === cell.r);
  return {
    actor: { ...state.actor },
    beds: exists ? state.beds.filter(bed => bed.c !== cell.c || bed.r !== cell.r).map(bed => ({ ...bed }))
      : [...state.beds.map(bed => ({ ...bed })), { c: cell.c, r: cell.r }],
  };
}

/** Headless scene builder: pass host-owned atlas metadata and its resolved image URL. */
export function createAutotileScene(state: LabState, tileset: Tileset, atlasUrl: string): { scene: Scene; resolution: AutotileResult } {
  if (tileset.version !== 1 || tileset.mode !== 'blob47') throw new Error('This lab requires a version 1 blob47 tileset.');
  const missing = autotileMasks('blob47').filter(mask => {
    const variant = tileset.variants[mask];
    return !variant || (Array.isArray(variant) && !variant.length);
  });
  if (missing.length) throw new Error(`Incomplete tileset: missing blob47 masks ${missing.join(', ')}.`);
  if (!inMap(state.actor) || state.beds.some(cell => !inMap(cell))) throw new Error('Lab cells must be inside the 9 × 9 ground map.');
  if (state.beds.some(cell => cell.c === state.actor.c && cell.r === state.actor.r)) throw new Error('A flowerbed cannot occupy the traveler’s tile.');
  const resolution = resolveAutotiles(state.beds, { mode: 'blob47', variants: tileset.variants });
  if (resolution.diagnostics.length) throw new Error(resolution.diagnostics.map(item => item.message).join('\n'));
  if (!tileset.textures.grass) throw new Error('Missing grass texture.');
  for (const variant of Object.values(tileset.variants)) for (const id of typeof variant === 'string' ? [variant] : variant ?? []) {
    if (!tileset.textures[id]) throw new Error(`Missing texture for variant ${id}.`);
  }
  const scene: Scene = {
    version: 1, name: 'Autotile garden', tileWidth: tileset.tileWidth, tileHeight: tileset.tileHeight,
    assets: { images: { beds: { url: atlasUrl, sampling: 'nearest' } }, textures: structuredClone(tileset.textures) },
    map: Array.from({ length: MAP_SIZE }, () => Array<string>(MAP_SIZE).fill('grass')),
    tiles: { grass: { color: 0x8da563, texture: 'grass', walkable: true } },
    entityTypes: { traveler: { visual: { kind: 'actor', color: 0xc96d4c, scale: 48 / 55 }, blocking: true, bodyHeight: 48 } },
    entities: [{ id: ACTOR_ID, type: 'traveler', ...state.actor }],
    controlledId: ACTOR_ID, diagonal: false,
  };
  for (const { cell, variant } of resolution.tiles) {
    if (!variant) throw new Error('Unresolved autotile.');
    const type = `tile-${variant}`;
    scene.entityTypes[type] = { visual: { kind: 'sprite', texture: variant, anchor: { ...tileset.anchor } }, blocking: true, bodyHeight: tileset.bodyHeight };
    scene.entities.push({ id: `bed-${cell.c}-${cell.r}`, type, c: cell.c, r: cell.r });
  }
  return { scene, resolution };
}
