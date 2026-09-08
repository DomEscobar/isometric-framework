import type { Cell, EntityDefinition, EntityType, LevelDefinition, Scene, TileDefinition } from './types.ts';
import { findPath } from './pathfinding.ts';
import { findLevelPath } from './level-pathfinding.ts';
import { cellKey as key, cellOnLevel, levelMaps, levelOf, sameCell } from './levels.ts';
import { validateScene } from './scene.ts';

const copy = <T>(value: T): T => structuredClone(value);
const cardinal = [{ c: -1, r: 0 }, { c: 1, r: 0 }, { c: 0, r: -1 }, { c: 0, r: 1 }];
const directions = [...cardinal, { c: -1, r: -1 }, { c: 1, r: -1 }, { c: -1, r: 1 }, { c: 1, r: 1 }];

/** Authoritative integer grid state, independent of visual interpolation and browser APIs. */
export class WorldModel {
  private state: Scene;
  private byId = new Map<string, EntityDefinition>();
  private occupancy = new Map<string, Set<string>>();
  private floors = new Map<string, LevelDefinition>();
  private connections = new Map<string, Cell[]>();

  constructor(scene: Scene) { this.state = validateScene(scene); this.reindex(); }
  get scene(): Scene { return this.serialize(); }
  get controlledId(): string | undefined { return this.state.controlledId; }
  serialize(): Scene { return copy(this.state); }
  entity(id: string): EntityDefinition | undefined { const entity = this.byId.get(id); return entity && copy(entity); }
  entities(): EntityDefinition[] { return copy(this.state.entities); }
  entityType(id: string): EntityType | undefined { const type = Object.hasOwn(this.state.entityTypes, id) ? this.state.entityTypes[id] : undefined; return type && copy(type); }
  tile(cell: Cell): TileDefinition | null { const tile = this.rawTile(cell); return tile ? copy(tile) : null; }

  private rawTile(cell: Cell): TileDefinition | undefined {
    if (!Number.isInteger(cell.c) || !Number.isInteger(cell.r) || cell.c < 0 || cell.r < 0) return undefined;
    const floor = this.floors.get(levelOf(cell));
    const id = floor?.map[cell.r]?.[cell.c];
    if (id === undefined || id === null) return undefined;
    const tile = this.state.tiles[id]!;
    return { ...tile, elevation: floor!.height + (tile.elevation ?? 0) };
  }

  private footprint(entity: EntityDefinition, origin: Cell = entity): Cell[] {
    const type = this.state.entityTypes[entity.type]!;
    const cells: Cell[] = [];
    for (let r = 0; r < (type.rows ?? 1); r++) {
      for (let c = 0; c < (type.columns ?? 1); c++) cells.push(cellOnLevel(origin.c + c, origin.r + r, levelOf(origin)));
    }
    return cells;
  }

  private reindex(): void {
    this.byId.clear(); this.occupancy.clear();
    this.floors = new Map(levelMaps(this.state).map(level => [level.id, level]));
    this.connections.clear();
    const connect = (from: Cell, to: Cell): void => {
      const destinations = this.connections.get(key(from)) ?? [];
      destinations.push(cellOnLevel(to.c, to.r, levelOf(to)));
      this.connections.set(key(from), destinations);
    };
    for (const link of this.state.links ?? []) {
      connect(link.from, link.to);
      if (link.bidirectional !== false) connect(link.to, link.from);
    }
    for (const entity of this.state.entities) this.index(entity);
  }

  private index(entity: EntityDefinition): void {
    this.byId.set(entity.id, entity);
    for (const cell of this.footprint(entity)) {
      const cellKey = key(cell);
      const occupants = this.occupancy.get(cellKey) ?? new Set<string>();
      occupants.add(entity.id);
      this.occupancy.set(cellKey, occupants);
    }
  }

  private unindex(entity: EntityDefinition): void {
    for (const cell of this.footprint(entity)) {
      const cellKey = key(cell), occupants = this.occupancy.get(cellKey);
      occupants?.delete(entity.id);
      if (!occupants?.size) this.occupancy.delete(cellKey);
    }
  }

  at(cell: Cell): EntityDefinition[] {
    return [...(this.occupancy.get(key(cell)) ?? [])].map(id => copy(this.byId.get(id)!));
  }

  canEnter(cell: Cell, ignoreId?: string): boolean {
    const tile = this.rawTile(cell);
    if (!tile || tile.walkable === false) return false;
    for (const id of this.occupancy.get(key(cell)) ?? []) {
      if (id !== ignoreId && this.state.entityTypes[this.byId.get(id)!.type]!.blocking) return false;
    }
    return true;
  }

  canStep(from: Cell, to: Cell, ignoreId?: string): boolean {
    const source = this.rawTile(from), target = this.rawTile(to);
    if (levelOf(from) !== levelOf(to)) {
      return !!source && !!target && this.canEnter(to, ignoreId)
        && (this.connections.get(key(from)) ?? []).some(cell => sameCell(cell, to));
    }
    return !!source && !!target && this.canEnter(to, ignoreId)
      && Math.abs((source.elevation ?? 0) - (target.elevation ?? 0)) <= (this.state.maxStepHeight ?? 0);
  }

  /** Check an exact segment; every part of a wide entity needs support and its own stair link. */
  canMove(id: string, from: Cell, to: Cell, direct = false): boolean {
    const entity = this.byId.get(id);
    if (!entity || !Number.isInteger(from.c) || !Number.isInteger(from.r) || !Number.isInteger(to.c) || !Number.isInteger(to.r)) return false;
    const dc = Math.abs(to.c - from.c), dr = Math.abs(to.r - from.r);
    if (dc > 1 || dr > 1 || dc + dr === 0) return false;
    const crossing = levelOf(from) !== levelOf(to);
    if (crossing && dc + dr !== 1) return false;
    const diagonal = dc !== 0 && dr !== 0;
    if (diagonal && !this.state.diagonal && !direct) return false;
    const step = (source: Cell, destination: Cell): boolean => {
      const sourceParts = this.footprint(entity, source);
      return this.footprint(entity, destination).every((part, index) => this.canStep(sourceParts[index]!, part, id));
    };
    if (!step(from, to)) return false;
    if (diagonal) {
      const sideC = cellOnLevel(to.c, from.r, levelOf(from));
      const sideR = cellOnLevel(from.c, to.r, levelOf(from));
      if (!step(from, sideC) || !step(from, sideR) || !step(sideC, to) || !step(sideR, to)) return false;
    }
    return true;
  }

  /** Direct input never detours. An available staircase in the input direction takes priority. */
  nextStep(id: string, direction: { c: number; r: number }): Cell | null {
    const entity = this.byId.get(id);
    if (!entity || !Number.isFinite(direction.c) || !Number.isFinite(direction.r)) return null;
    const dc = Math.sign(direction.c), dr = Math.sign(direction.r);
    if (dc === 0 && dr === 0) return null;
    const stair = (this.connections.get(key(entity)) ?? []).find(cell => cell.c - entity.c === dc && cell.r - entity.r === dr && this.canMove(id, entity, cell, true));
    if (stair) return copy(stair);
    const next = cellOnLevel(entity.c + dc, entity.r + dr, levelOf(entity));
    return this.canMove(id, entity, next, true) ? next : null;
  }

  path(id: string, target: Cell): Cell[] | null {
    const entity = this.byId.get(id);
    if (!entity || !this.rawTile(target)) return null;
    const enter = (cell: Cell): boolean => this.footprint(entity, cell).every(part => this.canEnter(part, id));
    // Existing scenery can start on blocked terrain; only the starting node gets an exception.
    if (sameCell(entity, target)) return [];
    if (!enter(target)) return null;
    if (this.state.version === 1) {
      return findPath(entity, target, cell => sameCell(cell, entity) || enter(cell), (from, to) => this.canMove(id, from, to), this.state.diagonal);
    }
    const neighbors = (from: Cell): Cell[] => {
      const candidates = (this.state.diagonal ? directions : cardinal).map(offset => cellOnLevel(from.c + offset.c, from.r + offset.r, levelOf(from)));
      candidates.push(...(this.connections.get(key(from)) ?? []));
      return candidates.filter(to => this.canMove(id, from, to));
    };
    const cost = (from: Cell, to: Cell): number => {
      const vertical = levelOf(from) === levelOf(to) ? 0 : (this.rawTile(to)!.elevation! - this.rawTile(from)!.elevation!) / this.state.tileHeight;
      return Math.hypot(to.c - from.c, to.r - from.r, vertical);
    };
    return findLevelPath(cellOnLevel(entity.c, entity.r, levelOf(entity)), cellOnLevel(target.c, target.r, levelOf(target)), neighbors, cost);
  }

  add(entity: EntityDefinition): void {
    const candidate = this.serialize();
    candidate.entities.push(entity);
    this.state = validateScene(candidate);
    this.reindex();
  }

  remove(id: string): boolean {
    const entity = this.byId.get(id);
    if (!entity) return false;
    this.unindex(entity);
    this.byId.delete(id);
    this.state.entities = this.state.entities.filter(entity => entity.id !== id);
    if (this.state.controlledId === id) delete this.state.controlledId;
    return true;
  }

  /** Explicit placement/teleport, including scenery overlap; movement uses path/canStep first. */
  setPosition(id: string, cell: Cell): void {
    const entity = this.byId.get(id);
    if (!entity) throw new Error(`Unknown entity: ${id}`);
    if (!Number.isInteger(cell.c) || !Number.isInteger(cell.r) || !this.footprint(entity, cell).every(part => this.rawTile(part))) throw new RangeError('Entity footprint must fit inside the map at integer coordinates');
    this.unindex(entity);
    entity.c = cell.c; entity.r = cell.r;
    if (levelOf(cell) === 'ground') delete entity.level;
    else entity.level = cell.level;
    this.index(entity);
  }

  setControlled(id: string | null): void {
    if (id === null) delete this.state.controlledId;
    else {
      if (!this.byId.has(id)) throw new Error(`Unknown entity: ${id}`);
      this.state.controlledId = id;
    }
  }
}
