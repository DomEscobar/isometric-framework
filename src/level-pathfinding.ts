import type { Cell } from './types.ts';
import { cellKey, sameCell } from './levels.ts';

interface Node { cell: Cell; cost: number; priority: number; order: number; parent?: Node }
class MinHeap {
  private items: Node[] = [];
  private less(a: Node, b: Node): boolean {
    return a.priority < b.priority || (a.priority === b.priority && a.order < b.order);
  }
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
    const first = this.items[0], last = this.items.pop();
    if (!last || !this.items.length) return first;
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

/** A* over a finite graph. Planar distance is admissible even when stairs add vertical cost. */
export function findLevelPath(from: Cell, to: Cell, neighbors: (cell: Cell) => Cell[], cost: (from: Cell, to: Cell) => number): Cell[] | null {
  const heuristic = (cell: Cell): number => Math.hypot(to.c - cell.c, to.r - cell.r);
  const open = new MinHeap();
  let order = 0;
  open.push({ cell: from, cost: 0, priority: heuristic(from), order: order++ });
  const best = new Map<string, number>([[cellKey(from), 0]]);
  let current: Node | undefined;
  while ((current = open.pop())) {
    if (current.cost !== best.get(cellKey(current.cell))) continue;
    if (sameCell(current.cell, to)) {
      const result: Cell[] = [];
      for (let node = current; node.parent; node = node.parent) result.push(node.cell);
      return result.reverse();
    }
    for (const next of neighbors(current.cell)) {
      const nextCost = current.cost + cost(current.cell, next), key = cellKey(next);
      if (nextCost >= (best.get(key) ?? Infinity)) continue;
      best.set(key, nextCost);
      open.push({ cell: next, cost: nextCost, priority: nextCost + heuristic(next), order: order++, parent: current });
    }
  }
  return null;
}
