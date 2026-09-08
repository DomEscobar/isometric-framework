import type { Cell } from './types.ts';

interface Node extends Cell { g: number; f: number; order: number; parent?: Node }

/** Binary min heap adapted from Traviso's A* open set; stable ties keep paths deterministic. */
class MinHeap {
  private items: Node[] = [];
  private less(a: Node, b: Node): boolean { return a.f < b.f || (a.f === b.f && a.order < b.order); }
  push(node: Node): void {
    let index = this.items.length;
    this.items.push(node);
    while (index > 0) {
      const parent = (index - 1) >> 1;
      if (!this.less(node, this.items[parent]!)) break;
      this.items[index] = this.items[parent]!;
      index = parent;
    }
    this.items[index] = node;
  }
  pop(): Node | undefined {
    const first = this.items[0];
    const last = this.items.pop();
    if (!this.items.length || !last) return first;
    let index = 0;
    while (index * 2 + 1 < this.items.length) {
      let child = index * 2 + 1;
      if (child + 1 < this.items.length && this.less(this.items[child + 1]!, this.items[child]!)) child++;
      if (!this.less(this.items[child]!, last)) break;
      this.items[index] = this.items[child]!;
      index = child;
    }
    this.items[index] = last;
    return first;
  }
}

const cardinal = [{ c: -1, r: 0 }, { c: 1, r: 0 }, { c: 0, r: -1 }, { c: 0, r: 1 }];
const directions = [...cardinal, { c: -1, r: -1 }, { c: 1, r: -1 }, { c: -1, r: 1 }, { c: 1, r: 1 }];
const key = (cell: Cell): string => `${cell.c},${cell.r}`;
const valid = (cell: Cell): boolean => Number.isSafeInteger(cell.c) && Number.isSafeInteger(cell.r) && cell.c >= 0 && cell.r >= 0;

/** Complete A* route excluding the start. The caller supplies finite map bounds through canEnter. */
export function findPath(from: Cell, to: Cell, canEnter: (cell: Cell) => boolean, canStep: (from: Cell, to: Cell) => boolean, diagonal = false): Cell[] | null {
  if (!valid(from) || !valid(to) || !canEnter(from) || !canEnter(to)) return null;
  if (from.c === to.c && from.r === to.r) return [];
  const heuristic = (cell: Cell): number => {
    const dc = Math.abs(to.c - cell.c), dr = Math.abs(to.r - cell.r);
    return diagonal ? dc + dr + (Math.SQRT2 - 2) * Math.min(dc, dr) : dc + dr;
  };
  let order = 0;
  const open = new MinHeap();
  const start: Node = { c: from.c, r: from.r, g: 0, f: heuristic(from), order: order++ };
  open.push(start);
  const best = new Map<string, number>([[key(from), 0]]);
  let current: Node | undefined;
  while ((current = open.pop())) {
    if (current.g !== best.get(key(current))) continue;
    if (current.c === to.c && current.r === to.r) {
      const path: Cell[] = [];
      let node = current;
      while (node.parent) { path.push({ c: node.c, r: node.r }); node = node.parent; }
      return path.reverse();
    }
    for (const offset of diagonal ? directions : cardinal) {
      const next = { c: current.c + offset.c, r: current.r + offset.r };
      if (!valid(next) || !canEnter(next) || !canStep(current, next)) continue;
      const isDiagonal = offset.c !== 0 && offset.r !== 0;
      if (isDiagonal) {
        const sideC = { c: next.c, r: current.r }, sideR = { c: current.c, r: next.r };
        if (!canEnter(sideC) || !canEnter(sideR) || !canStep(current, sideC) || !canStep(current, sideR) || !canStep(sideC, next) || !canStep(sideR, next)) continue;
      }
      const g = current.g + (isDiagonal ? Math.SQRT2 : 1);
      const nextKey = key(next);
      if (g >= (best.get(nextKey) ?? Infinity)) continue;
      best.set(nextKey, g);
      open.push({ ...next, g, f: g + heuristic(next), order: order++, parent: current });
    }
  }
  return null;
}
