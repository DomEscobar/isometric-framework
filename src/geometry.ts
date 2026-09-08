import type { Cell, Point } from './types.ts';

/** Traviso's positive columns point up/right, positive rows down/right. */
export function project(cell: Cell, tileWidth: number, tileHeight: number, elevation = 0): Point {
  return { x: (cell.c + cell.r) * tileWidth / 2, y: (cell.r - cell.c) * tileHeight / 2 - elevation };
}

/** Inverse projection onto the ground plane, rounded to the nearest tile center. */
export function unproject(point: Point, tileWidth: number, tileHeight: number): Cell {
  return { c: Math.round(point.x / tileWidth - point.y / tileHeight), r: Math.round(point.x / tileWidth + point.y / tileHeight) };
}
