import { Application } from 'pixi.js';
import { AssetBank } from './assets.ts';
import { Events } from './events.ts';
import { project, unproject } from './geometry.ts';
import { WorldModel } from './model.ts';
import { SceneView } from './view.ts';
import { attachKeyboard } from './controls.ts';
import { cellOnLevel, levelHeight, levelMaps, levelOf, sameCell } from './levels.ts';
import { bodyHeight, clearFlight, clearPose, flightPose, segmentBox, supported } from './physics.ts';
import type { Flight } from './physics.ts';
import type { Camera, Cell, DebugSnapshot, EntityDefinition, EntityPose, JumpResult, MoveResult, Point, ProjectileOptions, RuntimeEvents, RuntimeOptions, Scene, SpriteDirection } from './types.ts';

interface Motion {
  target: Cell;
  next: Cell | null;
  progress: number;
  direct?: boolean;
}
interface Projectile extends ProjectileOptions { id: string; progress: number; radius: number; color: number }

/** A mountable, independently owned simulation and Pixi display. No application globals. */
export class Runtime {
  readonly ready: Promise<void>;
  private app: Application;
  private model: WorldModel | null = null;
  /** Immutable definitions/geometry; live entities remain owned by WorldModel. */
  private scene: Scene | null = null;
  private view: SceneView | null = null;
  private bank: AssetBank | null = null;
  private events = new Events();
  private motions = new Map<string, Motion>();
  private flights = new Map<string, Flight>();
  private projectiles = new Map<string, Projectile>();
  private projectileSequence = 0;
  private poses = new Map<string, EntityPose>();
  private jumpSettings: { height: number; duration: number; distance: number };
  private camera: Camera = { x: 0, y: 0, zoom: 1 };
  private destroyed = false;
  private destroying = false;
  private resettingInput = false;
  private paused = false;
  private generation = 0;
  private loader: AbortController | null = null;
  private observer: ResizeObserver;
  private detachInput: (() => void) | null = null;
  private detachKeyboard: (() => void) | null = null;
  private moveInput: Cell | null = null;
  private blockedInput = '';
  private viewLevel: string | null = null;
  private speed: number;
  private width = 1;
  private height = 1;

  constructor(private options: RuntimeOptions) {
    if (!(options.container instanceof HTMLElement)) throw new Error('A DOM container is required');
    this.speed = options.speed ?? 3;
    if (!Number.isFinite(this.speed) || this.speed <= 0 || this.speed > 100) throw new Error('speed must be in (0, 100]');
    this.jumpSettings = { height: options.jump?.height ?? 84, duration: options.jump?.duration ?? 0.8, distance: options.jump?.distance ?? 2 };
    const { height, duration, distance } = this.jumpSettings;
    if (!Number.isFinite(height) || height <= 0 || height > 512 || !Number.isFinite(duration) || duration < 0.1 || duration > 5
      || !Number.isInteger(distance) || distance < 1 || distance > 8) throw new Error('Invalid jump settings');
    if (options.assetTimeoutMs !== undefined && (!Number.isFinite(options.assetTimeoutMs) || options.assetTimeoutMs <= 0)) {
      throw new Error('assetTimeoutMs must be positive');
    }
    // Validate before allocating a renderer or installing listeners.
    new WorldModel(options.scene);
    this.app = new Application({
      width: 1, height: 1, resolution: Math.min(window.devicePixelRatio || 1, 2),
      autoDensity: true, antialias: true, backgroundColor: options.background ?? 0xf0f2ea,
      autoStart: false, sharedTicker: false,
    });
    const canvas = this.app.view as HTMLCanvasElement;
    canvas.style.display = 'block';
    canvas.style.touchAction = 'none';
    canvas.setAttribute('aria-label', 'Isometric game map. Click or tap a tile to move; drag to pan.');
    canvas.setAttribute('role', 'img');
    options.container.appendChild(canvas);
    this.app.ticker.remove(this.app.render, this.app);
    this.app.ticker.minFPS = 0;
    this.app.ticker.add(() => this.step(Math.min(this.app.ticker.deltaMS / 1000, 60)));
    this.observer = new ResizeObserver(() => this.resize());
    this.observer.observe(options.container);
    this.resize();
    if (options.input !== false) this.attachInput(canvas);
    if (options.input !== false && options.keyboard !== false) this.detachKeyboard = attachKeyboard(this, options.container);
    this.ready = this.loadScene(options.scene);
    // Observing this internal promise prevents an unhandled rejection when a host
    // destroys during startup; callers still receive the original rejected ready.
    void this.ready.catch(() => {});
  }

  get isPaused(): boolean { return this.paused; }

  on<K extends keyof RuntimeEvents>(name: K, listener: (event: RuntimeEvents[K]) => void): () => void {
    this.assertAlive();
    return this.events.on(name, listener);
  }

  async loadScene(input: unknown): Promise<void> {
    this.assertAlive();
    const nextModel = new WorldModel(input as Scene);
    const generation = ++this.generation;
    this.resetInput();
    if (this.destroyed || generation !== this.generation) throw new DOMException('Scene load cancelled', 'AbortError');
    const nextBank = new AssetBank();
    this.loader?.abort();
    const controller = new AbortController();
    this.loader = controller;
    let nextView: SceneView | null = null;
    let installed = false;
    try {
      const nextScene = nextModel.serialize();
      await nextBank.load(nextScene, controller.signal, this.options.assetTimeoutMs ?? 15000);
      if (this.destroyed || generation !== this.generation) throw new DOMException('Scene load cancelled', 'AbortError');
      nextView = new SceneView(nextScene, nextBank);
      this.motions.clear();
      this.flights.clear();
      this.projectiles.clear();
      this.poses.clear();
      this.view?.destroy();
      this.bank?.destroy();
      this.model = nextModel;
      this.scene = nextScene;
      this.viewLevel = null;
      this.view = nextView;
      this.bank = nextBank;
      this.app.stage.addChild(nextView.root);
      installed = true;
      this.fit();
      if (this.destroyed || this.destroying || generation !== this.generation) throw new DOMException('Scene load cancelled', 'AbortError');
      if (!this.paused && this.options.autoStart !== false) this.app.start();
      this.events.emit('scenechange', { name: nextScene.name });
    } catch (error) {
      // Once installed, lifecycle replacement/destruction owns these resources.
      // A camera callback can start a newer load while this one is finishing.
      if (!installed) { nextView?.destroy(); nextBank.destroy(); }
      const failure = error instanceof Error ? error : new Error(String(error));
      if (!this.destroyed && generation === this.generation) this.events.emit('error', { error: failure });
      throw failure;
    } finally {
      if (generation === this.generation) this.loader = null;
    }
  }

  serializeScene(): Scene { return this.requireModel().serialize(); }
  getEntity(id: string): EntityDefinition | undefined { return this.requireModel().entity(id); }
  getEntityPose(id: string): EntityPose | undefined {
    const entity = this.requireModel().entity(id);
    if (!entity) return undefined;
    return structuredClone(this.poses.get(id) ?? { position: cellOnLevel(entity.c, entity.r, levelOf(entity)), elevation: this.getElevation(entity), airborne: false });
  }

  /** A locked-direction leap, or a vertical hop when no direction is held. */
  jump(id = this.requireModel().controlledId): JumpResult {
    const model = this.requireModel();
    if (!id || !model.entity(id)) return 'missing';
    if (this.paused || this.destroying) return 'paused';
    if (this.flights.has(id)) return 'airborne';
    const commandGeneration = this.generation;
    this.events.emit('command', { id, kind: 'jump' });
    if (this.destroyed || this.destroying || commandGeneration !== this.generation || this.paused || !model.entity(id)) return 'blocked';
    const entity = model.entity(id)!;
    const takeoff = this.getEntityPose(id)!;
    const from = takeoff.position;
    const fromHeight = takeoff.elevation;
    const direction = id === model.controlledId ? this.moveInput : null;
    let flight: Flight | undefined;
    const candidates: Cell[] = [];
    if (direction) {
      const raised: Cell[] = [], ordinary: Cell[] = [];
      for (let distance = 1; distance <= this.jumpSettings.distance; distance++) {
        const cells = levelMaps(this.scene!).map(level => cellOnLevel(entity.c + direction.c * distance, entity.r + direction.r * distance, level.id))
          .filter(cell => supported(model, id, cell) && this.getElevation(cell) - fromHeight <= this.jumpSettings.height)
          .sort((a, b) => this.getElevation(b) - this.getElevation(a));
        raised.push(...cells.filter(cell => this.getElevation(cell) > fromHeight));
        ordinary.unshift(...cells.filter(cell => this.getElevation(cell) <= fromHeight));
      }
      candidates.push(...raised, ...ordinary);
    }
    candidates.push(cellOnLevel(entity.c, entity.r, levelOf(entity)));
    for (const to of candidates) {
      if (!supported(model, id, to)) continue;
      const toHeight = this.getElevation(to);
      const height = toHeight > fromHeight ? this.jumpSettings.height : Math.min(40, this.jumpSettings.height);
      const candidate: Flight = { from, to, fromHeight, toHeight, ...this.jumpSettings, height, elapsed: 0 };
      if (clearFlight(model, this.scene!, id, candidate)) { flight = candidate; break; }
    }
    if (!flight) { this.events.emit('blocked', { id, target: from }); return 'blocked'; }
    this.motions.delete(id);
    this.flights.set(id, flight);
    this.view!.setMotion(id, 'jump');
    this.poses.set(id, { ...flightPose(flight, 0), airborne: true });
    this.events.emit('jumpstart', { id, from: { ...from }, to: { ...flight.to } });
    return 'started';
  }

  spawnProjectile(options: ProjectileOptions): string {
    const model = this.requireModel();
    const { from, to, speed, elevation } = options;
    const radius = options.radius ?? 6, color = options.color ?? 0xf26638;
    if (!from || !to || ![from.c, from.r, to.c, to.r, speed, elevation, radius, color].every(Number.isFinite)
      || speed <= 0 || speed > 1000 || radius <= 0 || radius > 128 || Math.hypot(to.c - from.c, to.r - from.r) === 0
      || !Number.isFinite(Math.hypot(to.c - from.c, to.r - from.r))
      || !Number.isInteger(color) || color < 0 || color > 0xffffff) throw new TypeError('Invalid projectile');
    for (const cell of [from, to]) levelHeight(this.scene!, levelOf(cell));
    const targetId = options.targetId ?? model.controlledId;
    if (targetId !== undefined && !model.entity(targetId)) throw new Error(`Unknown projectile target: ${targetId}`);
    const id = `projectile-${++this.projectileSequence}`;
    const projectile: Projectile = { ...options, from: { ...from }, to: { ...to }, targetId, radius, color, id, progress: 0 };
    this.projectiles.set(id, projectile);
    this.view!.projectile(id, from, elevation, radius, color);
    this.app.render();
    return id;
  }

  removeProjectile(id: string): boolean {
    this.assertAlive();
    const removed = this.projectiles.delete(id);
    if (removed) { this.view?.removeProjectile(id); this.app.render(); }
    return removed;
  }
  getEntities(): EntityDefinition[] { return this.requireModel().entities(); }
  /** Override the current sprite clip; null resumes automatic idle/walk/jump selection. */
  setAnimation(id: string, clip: string | null): boolean {
    this.requireModel();
    const changed = this.view!.setAnimation(id, clip);
    if (changed) this.app.render();
    return changed;
  }
  /** Set a stationary actor's visible facing; subsequent movement can change it. */
  setFacing(id: string, direction: SpriteDirection): boolean {
    this.requireModel();
    if (!['n', 'ne', 'e', 'se', 's', 'sw', 'w', 'nw'].includes(direction)) throw new TypeError('Invalid sprite facing');
    const changed = this.view!.setFacing(id, direction);
    if (changed) this.app.render();
    return changed;
  }

  getDebugSnapshot(): DebugSnapshot {
    const model = this.requireModel(), scene = this.scene!;
    const maxHeight = this.viewLevel === null ? Infinity : levelHeight(scene, this.viewLevel);
    const tiles: DebugSnapshot['tiles'] = [];
    let tilesTruncated = false;
    for (const level of levelMaps(scene)) {
      if (level.height > maxHeight) continue;
      for (let r = 0; r < level.map.length; r++) for (let c = 0; c < level.map[r]!.length; c++) {
        const tile = level.map[r]![c];
        if (tile === null) continue;
        if (tiles.length >= 2000) { tilesTruncated = true; continue; }
        tiles.push({ cell: { c, r, level: level.id }, elevation: level.height + (scene.tiles[tile!]!.elevation ?? 0) });
      }
    }
    return {
      sceneName: scene.name, tileWidth: scene.tileWidth, tileHeight: scene.tileHeight,
      camera: this.getCamera(), viewLevel: this.viewLevel, controlledId: model.controlledId ?? null,
      tiles, tilesTruncated,
      entities: model.entities().map(entity => {
        const type = scene.entityTypes[entity.type]!;
        const motion = this.motions.get(entity.id);
        return {
          id: entity.id, type: entity.type, cell: { c: entity.c, r: entity.r, level: levelOf(entity) },
          pose: this.getEntityPose(entity.id)!, elevation: this.getElevation(entity),
          columns: type.columns ?? 1, rows: type.rows ?? 1, bodyHeight: bodyHeight(type),
          blocking: type.blocking ?? false, visible: levelHeight(scene, levelOf(entity)) <= maxHeight,
          route: motion ? motion.direct ? [{ ...motion.target }] : model.path(entity.id, motion.target) ?? [] : [],
          sprite: this.view!.inspectSprite(entity.id),
        };
      }),
    };
  }
  findPath(id: string, target: Cell): Cell[] | null { return this.requireModel().path(id, target); }
  getElevation(cell: Cell): number {
    const tile = this.requireModel().tile(cell);
    if (!tile) throw new RangeError('There is no floor at this cell');
    return tile.elevation ?? 0;
  }
  getLevels(): { id: string; name: string; height: number }[] {
    this.requireModel();
    return levelMaps(this.scene!).map(({ id, name, height }) => ({ id, name, height }));
  }
  getViewLevel(): string | null { this.assertAlive(); return this.viewLevel; }
  /** Null shows all floors; a floor ID cuts away floors above it and scopes picking. */
  setViewLevel(id: string | null): void {
    this.requireModel();
    if (id !== null) levelHeight(this.scene!, id);
    this.viewLevel = id;
    this.view!.setViewLevel(id);
    this.app.render();
    this.events.emit('viewchange', { level: id });
  }

  /** Held screen-relative direction. Neutral finishes only the current tile step. */
  setMoveInput(direction: Point | null): void {
    this.assertAlive();
    if (this.destroying) return;
    if (direction && (!Number.isFinite(direction.x) || !Number.isFinite(direction.y))) throw new TypeError('Movement input must be finite');
    if (!direction || Math.hypot(direction.x, direction.y) < 0.001 || this.paused || !this.model) {
      this.moveInput = null;
      this.blockedInput = '';
      return;
    }
    // Eight screen sectors map to the isometric grid. Movement speed stays in
    // tile units; the stick is directional, with its dead zone handled by the HUD.
    const directions = [{ c: 1, r: 1 }, { c: 0, r: 1 }, { c: -1, r: 1 }, { c: -1, r: 0 },
      { c: -1, r: -1 }, { c: 0, r: -1 }, { c: 1, r: -1 }, { c: 1, r: 0 }];
    const sector = (Math.round(Math.atan2(direction.y, direction.x) / (Math.PI / 4)) + 8) % 8;
    const next = directions[sector]!;
    const commandId = this.model.controlledId;
    const commandGeneration = this.generation;
    if (commandId) this.events.emit('command', { id: commandId, kind: 'input' });
    if (this.destroyed || this.destroying || commandGeneration !== this.generation || this.paused) return;
    if (this.moveInput?.c !== next.c || this.moveInput?.r !== next.r) this.blockedInput = '';
    this.moveInput = next;
    const id = this.model.controlledId;
    if (id && this.motions.has(id) && !this.motions.get(id)!.direct) this.cancelMotion(id);
  }

  private resetInput(): void {
    this.moveInput = null;
    this.blockedInput = '';
    if (this.resettingInput) return;
    this.resettingInput = true;
    try { this.events.emit('inputreset', {}); }
    finally { this.resettingInput = false; }
  }

  private startDirect(id: string): Motion | null {
    if (!this.moveInput || !this.model || id !== this.model.controlledId || this.flights.has(id)) return null;
    const next = this.model.nextStep(id, this.moveInput);
    if (!next) {
      const entity = this.model.entity(id);
      const key = JSON.stringify([id, entity, this.moveInput]);
      if (entity && this.blockedInput !== key) {
        this.blockedInput = key;
        this.events.emit('blocked', { id, target: cellOnLevel(entity.c + this.moveInput.c, entity.r + this.moveInput.r, levelOf(entity)) });
      }
      return null;
    }
    this.blockedInput = '';
    const motion: Motion = { target: next, next, progress: 0, direct: true };
    this.motions.set(id, motion);
    return motion;
  }

  add(entity: EntityDefinition): void {
    const model = this.requireModel();
    const incomingType = model.entityType(entity.type);
    if (incomingType?.blocking) {
      for (const id of this.flights.keys()) {
        const airborne = model.entity(id)!;
        const type = model.entityType(airborne.type)!;
        if (levelOf(entity) === levelOf(airborne) && entity.c < airborne.c + (type.columns ?? 1)
          && entity.c + (incomingType.columns ?? 1) > airborne.c && entity.r < airborne.r + (type.rows ?? 1)
          && entity.r + (incomingType.rows ?? 1) > airborne.r) throw new Error('A jumping entity reserves its takeoff footprint');
      }
    }
    model.add(entity);
    try { this.view!.add(model.entity(entity.id)!); }
    catch (error) { model.remove(entity.id); throw error; }
    this.app.render();
  }

  remove(id: string): boolean {
    const generation = this.generation;
    if (id === this.requireModel().controlledId) this.resetInput();
    if (this.destroyed || generation !== this.generation) return false;
    const removed = this.requireModel().remove(id);
    this.motions.delete(id);
    this.flights.delete(id);
    this.poses.delete(id);
    if (removed) { this.view!.remove(id); this.app.render(); }
    return removed;
  }

  setControlled(id: string | null): void { this.requireModel().setControlled(id); this.resetInput(); }

  moveTo(id: string, target: Cell): MoveResult {
    const model = this.requireModel();
    const generation = this.generation;
    if (!model.entity(id)) return 'missing';
    if (this.paused) return 'paused';
    if (this.flights.has(id)) return 'blocked';
    this.events.emit('command', { id, kind: 'move' });
    if (this.destroyed || this.destroying || generation !== this.generation || this.paused || !model.entity(id)) return 'blocked';
    if (id === model.controlledId) this.resetInput();
    if (this.destroyed || generation !== this.generation) return 'blocked';
    const path = model.path(id, target);
    if (!path) { this.events.emit('blocked', { id, target: { ...target } }); return 'blocked'; }
    this.cancelMotion(id);
    if (path.length === 0) {
      this.events.emit('arrive', { id, cell: { ...target } });
      return 'arrived';
    }
    this.motions.set(id, { target: { ...target }, next: null, progress: 0 });
    return 'started';
  }

  stop(id: string): void {
    const generation = this.generation;
    this.requireModel();
    this.events.emit('command', { id, kind: 'stop' });
    if (this.destroyed || this.destroying || generation !== this.generation) return;
    if (id === this.requireModel().controlledId) this.resetInput();
    if (this.destroyed || generation !== this.generation) return;
    this.cancelMotion(id);
  }

  private cancelMotion(id: string): void {
    const entity = this.requireModel().entity(id);
    this.motions.delete(id);
    this.flights.delete(id);
    this.poses.delete(id);
    if (entity) {
      // Returning to reserved occupancy cancels travel; it is not a reverse step.
      this.view!.position(id, entity, undefined, levelOf(entity), false);
      this.view!.setMotion(id, 'idle');
    }
    this.app.render();
  }

  /** Advance by elapsed seconds. With autoStart:false the host owns the game loop. */
  step(deltaSeconds: number): void {
    this.assertAlive();
    if (!Number.isFinite(deltaSeconds) || deltaSeconds < 0 || deltaSeconds > 60) throw new Error('step requires 0–60 seconds');
    if (!this.model || !this.view || this.paused) return;
    const generation = this.generation;
    let remaining = deltaSeconds;
    do {
      const dt = this.flights.size || this.projectiles.size ? Math.min(remaining, 1 / 120) : remaining;
      const before = new Map<string, EntityPose>();
      for (const projectile of this.projectiles.values()) {
        if (projectile.targetId) {
          const pose = this.getEntityPose(projectile.targetId);
          if (pose) before.set(projectile.targetId, pose);
        }
      }
      this.advanceMovement(dt);
      if (this.destroyed || generation !== this.generation || this.paused) return;
      this.advanceFlights(dt);
      if (this.destroyed || generation !== this.generation || this.paused) return;
      this.advanceProjectiles(dt, before);
      if (this.destroyed || generation !== this.generation || this.paused) return;
      remaining -= dt;
    } while (remaining > 1e-10);
    for (const entity of this.model.entities()) {
      this.view.setMotion(entity.id, this.flights.has(entity.id) ? 'jump' : this.motions.has(entity.id) ? 'walk' : 'idle');
    }
    this.view.update(deltaSeconds);
    this.events.emit('frame', { deltaSeconds });
    if (!this.destroyed) this.app.render();
  }

  private advanceMovement(deltaSeconds: number): void {
    const generation = this.generation;
    const model = this.model!;
    const controlled = model.controlledId;
    if (controlled && !this.motions.has(controlled)) this.startDirect(controlled);
    if (this.destroyed || generation !== this.generation || this.paused) return;
    for (const [id, initialMotion] of [...this.motions]) {
      let motion = initialMotion;
      let remaining = deltaSeconds * this.speed;
      while (remaining > 0 && this.motions.get(id) === motion) {
        const entity = model.entity(id);
        if (!entity) { this.motions.delete(id); break; }
        if (!motion.next) {
          const path = model.path(id, motion.target);
          if (!path || path.length === 0) {
            this.cancelMotion(id);
            this.events.emit(path ? 'arrive' : 'blocked', path
              ? { id, cell: cellOnLevel(entity.c, entity.r, levelOf(entity)) } : { id, target: motion.target });
            break;
          }
          motion.next = path[0]!;
        }
        // Recheck the immediate segment: blockers can change while walking.
        if (!model.canMove(id, entity, motion.next, motion.direct)) {
          this.cancelMotion(id);
          this.events.emit('blocked', { id, target: motion.target });
          break;
        }
        const fromHeight = model.tile(entity)?.elevation ?? 0;
        const toHeight = model.tile(motion.next)?.elevation ?? 0;
        const crossing = levelOf(entity) !== levelOf(motion.next);
        const distance = Math.hypot(motion.next.c - entity.c, motion.next.r - entity.r, crossing ? (toHeight - fromHeight) / this.scene!.tileHeight : 0);
        const used = Math.min(remaining, distance * (1 - motion.progress));
        remaining -= used;
        motion.progress = Math.min(1, motion.progress + used / distance);
        const position = cellOnLevel(entity.c + (motion.next.c - entity.c) * motion.progress,
          entity.r + (motion.next.r - entity.r) * motion.progress, levelOf(motion.progress >= 1 - 1e-9 ? motion.next : entity));
        const elevation = fromHeight + (toHeight - fromHeight) * motion.progress;
        const drawLevel = motion.progress >= 1 - 1e-9 ? levelOf(motion.next)
          : levelHeight(this.scene!, levelOf(entity)) > levelHeight(this.scene!, levelOf(motion.next)) ? levelOf(entity) : levelOf(motion.next);
        this.view!.position(id, position, elevation, drawLevel);
        this.poses.set(id, { position: { ...position }, elevation, airborne: false });
        if (motion.progress >= 1 - 1e-9) {
          model.setPosition(id, motion.next);
          motion.next = null;
          motion.progress = 0;
        }
        this.events.emit('move', { id, position, elevation });
        if (this.destroyed || generation !== this.generation || this.paused) return;
        if (this.motions.get(id) !== motion) break;
        const current = model.entity(id);
        if (current && sameCell(current, motion.target) && !motion.next) {
          this.motions.delete(id);
          this.events.emit('arrive', { id, cell: cellOnLevel(current.c, current.r, levelOf(current)) });
          if (this.destroyed || generation !== this.generation || this.paused) return;
          if (motion.direct && !this.motions.has(id)) {
            const next = this.startDirect(id);
            if (this.destroyed || generation !== this.generation || this.paused) return;
            if (next) motion = next;
          }
        }
      }
      if (this.destroyed || generation !== this.generation || this.paused) return;
    }
  }

  private advanceFlights(deltaSeconds: number): void {
    const generation = this.generation;
    for (const [id, flight] of [...this.flights]) {
      if (this.flights.get(id) !== flight) continue;
      flight.elapsed = Math.min(flight.duration, flight.elapsed + deltaSeconds);
      const progress = Math.min(1, flight.elapsed / flight.duration);
      let pose = flightPose(flight, progress);
      if (!clearPose(this.model!, this.scene!, id, pose) || (progress >= 1 && !supported(this.model!, id, flight.to))) {
        // Integer occupancy remains reserved at takeoff until touchdown.
        this.cancelMotion(id);
        this.events.emit('blocked', { id, target: { ...flight.to } });
        if (this.destroyed || generation !== this.generation || this.paused) return;
        continue;
      }
      if (progress >= 1 - 1e-9) {
        this.model!.setPosition(id, flight.to);
        this.flights.delete(id);
        pose = flightPose(flight, 1);
      }
      this.poses.set(id, pose);
      // A jumping entity sorts on the highest floor its feet have cleared.
      const drawLevel = pose.airborne
        ? levelMaps(this.scene!).filter(level => level.height <= pose.elevation + 0.001)
          .sort((a, b) => b.height - a.height)[0]?.id ?? levelOf(pose.position)
        : levelOf(pose.position);
      this.view!.position(id, pose.position, pose.elevation, drawLevel);
      this.events.emit('move', { id, position: { ...pose.position }, elevation: pose.elevation });
      if (this.destroyed || generation !== this.generation || this.paused) return;
      if (this.poses.get(id) !== pose) continue;
      if (!pose.airborne && !this.flights.has(id) && this.model!.entity(id)) {
        this.events.emit('land', { id, cell: { ...flight.to } });
        if (this.destroyed || generation !== this.generation || this.paused) return;
        if (this.model!.entity(id) && !this.flights.has(id)) this.events.emit('arrive', { id, cell: { ...flight.to } });
        if (this.destroyed || generation !== this.generation || this.paused) return;
      }
    }
  }

  private advanceProjectiles(deltaSeconds: number, before: Map<string, EntityPose>): void {
    const generation = this.generation;
    for (const [id, projectile] of [...this.projectiles]) {
      if (this.projectiles.get(id) !== projectile) continue;
      const length = Math.hypot(projectile.to.c - projectile.from.c, projectile.to.r - projectile.from.r);
      const oldProgress = projectile.progress;
      projectile.progress = Math.min(1, oldProgress + deltaSeconds * projectile.speed / length);
      const positionAt = (progress: number): Cell => cellOnLevel(projectile.from.c + (projectile.to.c - projectile.from.c) * progress,
        projectile.from.r + (projectile.to.r - projectile.from.r) * progress, levelOf(projectile.from));
      const from = positionAt(oldProgress), to = positionAt(projectile.progress);
      const target = projectile.targetId && this.model!.entity(projectile.targetId);
      const after = target ? this.getEntityPose(target.id) : undefined;
      const previous = target ? before.get(target.id) ?? after : undefined;
      if (target && after && previous) {
        const type = this.model!.entityType(target.type)!;
        const radius = projectile.radius / (this.scene!.tileWidth / Math.SQRT2);
        const relative = (cell: Cell, pose: EntityPose): number[] => [cell.c - pose.position.c, cell.r - pose.position.r, projectile.elevation - pose.elevation];
        const hit = segmentBox(relative(from, previous), relative(to, after),
          [-0.22 - radius, -0.22 - radius, -projectile.radius],
          [(type.columns ?? 1) - 0.78 + radius, (type.rows ?? 1) - 0.78 + radius, bodyHeight(type) + projectile.radius]);
        if (hit !== null) {
          this.removeProjectile(id);
          this.events.emit('projectilehit', { projectileId: id, entityId: target.id,
            position: positionAt(oldProgress + (projectile.progress - oldProgress) * hit), elevation: projectile.elevation });
          if (this.destroyed || generation !== this.generation || this.paused) return;
          continue;
        }
      }
      if (projectile.progress >= 1) this.removeProjectile(id);
      else this.view!.projectile(id, to, projectile.elevation, projectile.radius, projectile.color);
    }
  }

  pause(): void {
    this.assertAlive();
    if (this.paused) return;
    this.paused = true;
    this.resetInput();
    if (this.destroyed || !this.paused) return;
    this.app.stop();
    this.events.emit('pausechange', { paused: true });
  }

  resume(): void {
    this.assertAlive();
    if (!this.paused) return;
    this.paused = false;
    if (this.model && this.options.autoStart !== false) this.app.start();
    this.events.emit('pausechange', { paused: false });
  }

  getCamera(): Camera { this.assertAlive(); return { ...this.camera }; }

  setCamera(camera: Partial<Camera>): void {
    this.assertAlive();
    const next = { ...this.camera, ...camera };
    if (![next.x, next.y, next.zoom].every(Number.isFinite) || next.zoom <= 0) throw new Error('Invalid camera');
    this.camera = { ...next, zoom: Math.max(0.05, Math.min(4, next.zoom)) };
    if (this.view) {
      this.view.root.position.set(this.camera.x, this.camera.y);
      this.view.root.scale.set(this.camera.zoom);
    }
    this.app.render();
    this.events.emit('camerachange', { camera: this.getCamera() });
  }

  fit(): void {
    this.assertAlive();
    if (!this.model) return;
    const scene = this.scene!;
    const rows = scene.map.length;
    const columns = scene.map[0]!.length;
    const top = -(columns - 1) * scene.tileHeight / 2 - scene.tileHeight / 2;
    const bottom = (rows - 1) * scene.tileHeight / 2 + scene.tileHeight / 2 + 8;
    const left = -scene.tileWidth / 2;
    const right = (columns + rows - 2) * scene.tileWidth / 2 + scene.tileWidth / 2;
    const headroom = Math.max(64, ...Object.values(scene.tiles).map(tile => (tile.elevation ?? 0) + 64)) + Math.max(0, ...this.getLevels().map(level => level.height));
    const zoom = Math.max(0.05, Math.min(1.5, (this.width - 40) / (right - left), (this.height - 48) / (bottom - top + headroom)));
    this.setCamera({ zoom, x: this.width / 2 - (left + right) / 2 * zoom, y: this.height / 2 - (top - headroom + bottom) / 2 * zoom });
  }

  resize(): void {
    if (this.destroyed) return;
    const rect = this.options.container.getBoundingClientRect();
    const width = Math.max(1, rect.width);
    const height = Math.max(1, rect.height);
    const previous = { width: this.width, height: this.height };
    this.width = width;
    this.height = height;
    this.app.renderer.resize(width, height);
    this.setCamera({ x: this.camera.x + (width - previous.width) / 2, y: this.camera.y + (height - previous.height) / 2 });
  }

  /** Coordinates are CSS pixels relative to this runtime's canvas. */
  cellToScreen(cell: Cell): Point {
    const model = this.requireModel();
    const scene = this.scene!;
    const p = project(cell, scene.tileWidth, scene.tileHeight, model.tile(cell)?.elevation ?? 0);
    return { x: p.x * this.camera.zoom + this.camera.x, y: p.y * this.camera.zoom + this.camera.y };
  }

  pick(point: Point): Cell | null {
    if (!this.model || this.destroyed || !Number.isFinite(point.x) || !Number.isFinite(point.y)) return null;
    const scene = this.scene!;
    const p = { x: (point.x - this.camera.x) / this.camera.zoom, y: (point.y - this.camera.y) / this.camera.zoom };
    // Inverse projection per distinct elevation, then choose the front-most face.
    // This avoids the inherited full-map scan and supports raised diamond tops.
    let picked: Cell | null = null;
    for (const level of levelMaps(scene)) {
      if (this.viewLevel !== null && level.id !== this.viewLevel) continue;
      for (const elevation of new Set(Object.values(scene.tiles).map(tile => level.height + (tile.elevation ?? 0)))) {
        const planar = unproject({ x: p.x, y: p.y + elevation }, scene.tileWidth, scene.tileHeight);
        const cell = cellOnLevel(planar.c, planar.r, level.id);
        const tile = this.model.tile(cell);
        if (!tile || (tile.elevation ?? 0) !== elevation) continue;
        if (!picked || level.height > levelHeight(scene, levelOf(picked)) || (level.id === levelOf(picked) && cell.r - cell.c > picked.r - picked.c)) picked = cell;
      }
    }
    return picked;
  }

  destroy(): void {
    if (this.destroyed || this.destroying) return;
    this.destroying = true;
    this.events.emit('destroy', {});
    this.resetInput();
    this.detachKeyboard?.();
    this.destroyed = true;
    ++this.generation;
    this.loader?.abort();
    this.loader = null;
    this.detachInput?.();
    this.observer.disconnect();
    this.events.clear();
    this.motions.clear();
    this.flights.clear();
    this.projectiles.clear();
    this.poses.clear();
    this.app.stop();
    this.view?.destroy();
    this.bank?.destroy();
    this.view = null;
    this.bank = null;
    this.model = null;
    this.scene = null;
    this.app.destroy(true, { children: true, texture: false, baseTexture: false });
  }

  private assertAlive(): void { if (this.destroyed) throw new Error('Runtime has been destroyed'); }
  private requireModel(): WorldModel {
    this.assertAlive();
    if (!this.model) throw new Error('Await runtime.ready before using the scene');
    return this.model;
  }

  private attachInput(canvas: HTMLCanvasElement): void {
    let pointer: { id: number; start: Point; last: Point; dragged: boolean } | null = null;
    const local = (event: PointerEvent | WheelEvent): Point => {
      const rect = canvas.getBoundingClientRect();
      return { x: event.clientX - rect.left, y: event.clientY - rect.top };
    };
    const down = (event: PointerEvent) => {
      if (pointer || event.button !== 0) return;
      this.options.container.focus({ preventScroll: true });
      const p = local(event);
      pointer = { id: event.pointerId, start: p, last: p, dragged: false };
      canvas.setPointerCapture(event.pointerId);
    };
    const move = (event: PointerEvent) => {
      const p = local(event);
      if (pointer && pointer.id === event.pointerId) {
        pointer.dragged ||= Math.hypot(p.x - pointer.start.x, p.y - pointer.start.y) > 5;
        if (pointer.dragged) this.setCamera({ x: this.camera.x + p.x - pointer.last.x, y: this.camera.y + p.y - pointer.last.y });
        pointer.last = p;
      }
      const cell = this.pick(p);
      const controlled = this.model?.controlledId;
      this.view?.highlight(cell, !!cell && !this.model?.canEnter(cell, controlled));
      this.events.emit('hover', { cell });
      if (!this.destroyed) this.app.render();
    };
    const up = (event: PointerEvent) => {
      if (!pointer || pointer.id !== event.pointerId) return;
      const dragged = pointer.dragged;
      pointer = null;
      if (canvas.hasPointerCapture(event.pointerId)) canvas.releasePointerCapture(event.pointerId);
      if (dragged || !this.model) return;
      const cell = this.pick(local(event));
      if (!cell) return;
      const generation = this.generation;
      this.events.emit('tileclick', { cell, entityIds: this.model.at(cell).map(entity => entity.id) });
      if (this.destroyed || generation !== this.generation) return;
      const controlledId = this.model.controlledId;
      if (controlledId && this.options.clickToMove !== false) this.moveTo(controlledId, cell);
    };
    const cancel = () => { pointer = null; };
    const leave = () => {
      if (!pointer) { this.view?.highlight(null); this.events.emit('hover', { cell: null }); }
    };
    const wheel = (event: WheelEvent) => {
      event.preventDefault();
      const p = local(event);
      const nextZoom = Math.max(0.05, Math.min(4, this.camera.zoom * Math.exp(-event.deltaY * 0.001)));
      const ratio = nextZoom / this.camera.zoom;
      this.setCamera({ zoom: nextZoom, x: p.x - (p.x - this.camera.x) * ratio, y: p.y - (p.y - this.camera.y) * ratio });
    };
    canvas.addEventListener('pointerdown', down);
    canvas.addEventListener('pointermove', move);
    canvas.addEventListener('pointerup', up);
    canvas.addEventListener('pointercancel', cancel);
    canvas.addEventListener('lostpointercapture', cancel);
    canvas.addEventListener('pointerleave', leave);
    canvas.addEventListener('wheel', wheel, { passive: false });
    this.detachInput = () => {
      canvas.removeEventListener('pointerdown', down);
      canvas.removeEventListener('pointermove', move);
      canvas.removeEventListener('pointerup', up);
      canvas.removeEventListener('pointercancel', cancel);
      canvas.removeEventListener('lostpointercapture', cancel);
      canvas.removeEventListener('pointerleave', leave);
      canvas.removeEventListener('wheel', wheel);
      if (pointer && canvas.hasPointerCapture(pointer.id)) canvas.releasePointerCapture(pointer.id);
      pointer = null;
    };
  }
}

export async function createRuntime(options: RuntimeOptions): Promise<Runtime> {
  const runtime = new Runtime(options);
  try { await runtime.ready; return runtime; }
  catch (error) { runtime.destroy(); throw error; }
}
