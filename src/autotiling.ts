import type { Cell } from './types.ts';
import { cellKey, levelOf } from './levels.ts';

export type AutotileMode = 'cardinal16' | 'blob47';
/** Host-supplied topology, independent of scene schema and rendering. */
export interface AutotileCell extends Cell {
  /** Omitted families connect to each other, but not to named families. */
  family?: string;
  /** Local surface height on this floor; omitted means zero. */
  elevation?: number;
}
export interface AutotileOptions {
  /** c-=1, c+=2, r-=4, r+=8 (the existing planter atlas convention).
   * blob47 also uses (c-,r-)=16, (c+,r-)=32, (c-,r+)=64, (c+,r+)=128.
   * A corner bit survives only if its diagonal AND both adjacent cardinals connect.
   * These are grid deltas, not screen-space compass directions or atlas indices. */
  mode: AutotileMode;
  /** Default false: families must be equal. True connects across families. */
  connectFamilies?: boolean;
  /** Default true: elevations must be equal. Floors NEVER connect across identities. */
  matchElevation?: boolean;
}
export interface AutotileRules extends AutotileOptions {
  /** Keys are actual masks, not sequential atlas indices. Only canonical masks are valid.
   * Lists are equally weighted deterministic alternatives; empty entries report missing. */
  variants: Readonly<Partial<Record<number, string | readonly string[]>>>;
  /** Defaults to zero. Selection depends on this seed and normalized cell identity,
   * family, elevation and mask, never input ordering or global random state. */
  seed?: string | number;
}
export interface AutotileTopology { cell: AutotileCell; mask: number }
export interface AutotileResolution extends AutotileTopology {
  /** Null means an explicit missing-variant diagnostic; there is no fallback. */
  variant: string | null;
}
export interface AutotileDiagnostic extends AutotileTopology {
  code: 'missing-variant';
  message: string;
}
export interface AutotileResult {
  tiles: AutotileResolution[];
  diagnostics: AutotileDiagnostic[];
}

const cardinals = [[-1, 0, 1], [1, 0, 2], [0, -1, 4], [0, 1, 8]] as const;
const corners = [[-1, -1, 16, 5], [1, -1, 32, 6], [-1, 1, 64, 9], [1, 1, 128, 10]] as const;
function canonical(mask: number): number {
  for (const [, , bit, sides] of corners) if ((mask & sides) !== sides) mask &= ~bit;
  return mask;
}
const cardinalMasks = Object.freeze(Array.from({ length: 16 }, (_, i) => i));
const blobMasks = Object.freeze(Array.from({ length: 256 }, (_, i) => i).filter(mask => canonical(mask) === mask));

/** Sorted canonical masks: 16 cardinal combinations or 47 corner-aware combinations. */
export function autotileMasks(mode: AutotileMode): readonly number[] {
  if (mode === 'cardinal16') return cardinalMasks;
  if (mode === 'blob47') return blobMasks;
  throw new TypeError(`Unknown autotile mode: ${mode}`);
}

/** Resolve topology in input order in O(cells) work. Inputs are not mutated.
 * Duplicate normalized (c,r,level) cells and invalid values throw, since they make
 * connectivity ambiguous. Missing cells are empty; ground is the omitted floor. */
export function analyzeAutotiles(cells: readonly AutotileCell[], options: AutotileOptions): AutotileTopology[] {
  autotileMasks(options.mode);
  for (const name of ['connectFamilies', 'matchElevation'] as const) {
    if (options[name] !== undefined && typeof options[name] !== 'boolean') throw new TypeError(`${name} must be boolean`);
  }
  const index = new Map<string, AutotileCell>();
  for (const cell of cells) {
    if (!Number.isSafeInteger(cell.c) || !Number.isSafeInteger(cell.r)) throw new TypeError('Autotile coordinates must be safe integers');
    if ((cell.level !== undefined && (typeof cell.level !== 'string' || !cell.level.length))
      || (cell.family !== undefined && (typeof cell.family !== 'string' || !cell.family.length))
      || (cell.elevation !== undefined && (typeof cell.elevation !== 'number' || !Number.isFinite(cell.elevation)))) {
      throw new TypeError('Autotile level/family must be nonempty strings and elevation must be finite');
    }
    const key = cellKey(cell);
    if (index.has(key)) throw new TypeError(`Duplicate autotile cell: ${key}`);
    index.set(key, cell);
  }
  return cells.map(cell => {
    const connects = (dc: number, dr: number): boolean => {
      const neighbor = index.get(cellKey({ c: cell.c + dc, r: cell.r + dr, level: cell.level }));
      return !!neighbor && (options.connectFamilies === true || cell.family === neighbor.family)
        && (options.matchElevation === false || (cell.elevation ?? 0) === (neighbor.elevation ?? 0));
    };
    let mask = 0;
    for (const [dc, dr, bit] of cardinals) if (connects(dc, dr)) mask |= bit;
    if (options.mode === 'blob47') {
      for (const [dc, dr, bit, sides] of corners) if ((mask & sides) === sides && connects(dc, dr)) mask |= bit;
    }
    return { cell: { ...cell }, mask };
  });
}

/** Select host-owned variant IDs; does not load textures or modify a scene.
 * Incomplete tables produce per-cell diagnostics; malformed tables throw. */
export function resolveAutotiles(cells: readonly AutotileCell[], rules: AutotileRules): AutotileResult {
  const validMasks = new Set(autotileMasks(rules.mode));
  if (!rules.variants || typeof rules.variants !== 'object' || Array.isArray(rules.variants)) {
    throw new TypeError('Autotile variants must be a mask-keyed object');
  }
  if (rules.seed !== undefined && typeof rules.seed !== 'string'
    && (typeof rules.seed !== 'number' || !Number.isFinite(rules.seed))) throw new TypeError('Autotile seed must be a string or finite number');
  for (const [key, value] of Object.entries(rules.variants)) {
    if (String(Number(key)) !== key || !validMasks.has(Number(key))) throw new TypeError(`Noncanonical ${rules.mode} variant mask: ${key}`);
    if (value === undefined) continue;
    const variants = typeof value === 'string' ? [value] : value;
    if (!Array.isArray(variants) || Array.from(variants).some(id => typeof id !== 'string' || !id.length)) {
      throw new TypeError(`Autotile variants for mask ${key} must be nonempty IDs`);
    }
  }
  const diagnostics: AutotileDiagnostic[] = [];
  const tiles = analyzeAutotiles(cells, rules).map(({ cell, mask }): AutotileResolution => {
    const entry = Object.hasOwn(rules.variants, mask) ? rules.variants[mask] : undefined;
    const variants = typeof entry === 'string' ? [entry] : entry;
    if (!variants?.length) {
      diagnostics.push({ code: 'missing-variant', cell: { ...cell }, mask, message: `No ${rules.mode} variant for mask ${mask} at ${cellKey(cell)}` });
      return { cell, mask, variant: null };
    }
    const key = JSON.stringify([rules.seed ?? 0, levelOf(cell), cell.c, cell.r, cell.family ?? null, cell.elevation ?? 0, mask]);
    let hash = 2166136261;
    for (let i = 0; i < key.length; i++) hash = Math.imul(hash ^ key.charCodeAt(i), 16777619) >>> 0;
    return { cell, mask, variant: variants[hash % variants.length]! };
  });
  return { tiles, diagnostics };
}
