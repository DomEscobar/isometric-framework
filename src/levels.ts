import type { Cell, LevelDefinition, Scene } from './types.ts';

export function levelOf(cell: Cell): string { return cell.level ?? 'ground'; }
export function sameCell(a: Cell, b: Cell): boolean {
  return a.c === b.c && a.r === b.r && levelOf(a) === levelOf(b);
}
export function levelMaps(scene: Scene): LevelDefinition[] {
  return [{ id: 'ground', name: 'Ground', height: 0, map: scene.map }, ...(scene.levels ?? [])];
}
export function levelHeight(scene: Scene, id: string): number {
  if (id === 'ground') return 0;
  const level = scene.levels?.find(level => level.id === id);
  if (!level) throw new RangeError(`Unknown level: ${id}`);
  return level.height;
}

/** Canonical grid cells omit the ground label for version 1 compatibility. */
export function cellOnLevel(c: number, r: number, level: string): Cell {
  return level === 'ground' ? { c, r } : { c, r, level };
}
export function cellKey(cell: Cell): string { return JSON.stringify([levelOf(cell), cell.c, cell.r]); }
