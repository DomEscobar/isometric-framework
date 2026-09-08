import type { Cell, EntityDefinition, EntityPose, MoveResult, Scene, SpriteDirection } from './types.ts';

/** Public methods only: this controller can run without a renderer or browser. */
export interface InteractionRuntime {
  readonly isPaused: boolean;
  getEntity(id: string): EntityDefinition | undefined;
  getEntityPose(id: string): EntityPose | undefined;
  getElevation(cell: Cell): number;
  serializeScene(): Scene;
  findPath(id: string, cell: Cell): Cell[] | null;
  moveTo(id: string, cell: Cell): MoveResult;
  stop(id: string): void;
  setFacing(id: string, direction: SpriteDirection): boolean;
  setAnimation(id: string, clip: string | null): boolean;
  on<K extends keyof InteractionEvents>(name: K, listener: (event: InteractionEvents[K]) => void): () => void;
}

interface InteractionEvents {
  frame: { deltaSeconds: number };
  command: { id: string; kind: 'move' | 'input' | 'jump' | 'stop' };
  blocked: { id: string; target: Cell };
  scenechange: { name: string };
  destroy: Record<string, never>;
}

export interface InteractionContext {
  runtime: InteractionRuntime;
  actor: EntityDefinition;
  target: EntityDefinition;
  actionId: string;
}

export interface InteractionAction {
  id: string;
  /** Finite simulation seconds in [0, 3600]. */
  prepareSeconds: number;
  /** Finite simulation seconds in [0, 3600]. */
  recoverSeconds: number;
  clips?: Partial<Record<SpriteDirection, string>>;
  recoveryClips?: Partial<Record<SpriteDirection, string>>;
  /** Synchronous predicate, checked at preparation and immediately before effect. */
  canPerform?: (context: InteractionContext) => boolean;
  /** Synchronous, at most once per accepted action. Return true only after committing
   * the host effect. Hosts must atomically claim/remove shared targets themselves. */
  perform: (context: InteractionContext) => boolean;
}

export interface InteractionState {
  phase: 'idle' | 'approaching' | 'preparing' | 'recovering';
  actorId: string | null;
  targetId: string | null;
  actionId: string | null;
  elapsedSeconds: number;
  effectApplied: boolean;
  reason: string | null;
}

export interface InteractionOptions {
  /** Maximum absolute feet-height difference in pixels. Finite and nonnegative;
   * defaults to 0, allowing only equal-height interaction surfaces. */
  maxHeightDifference?: number;
  /** Synchronous notification. Receives a detached state snapshot. */
  onChange?: (state: InteractionState) => void;
  onError?: (error: Error) => void;
}

export interface InteractionController {
  /** False for rejected requests; repeating an active actor/target/action ID is a no-op. */
  request(request: { actorId: string; targetId: string; action: InteractionAction }): boolean;
  cancel(reason?: string): void;
  getState(): InteractionState;
  destroy(): void;
}

interface Job {
  actorId: string;
  target: EntityDefinition;
  targetElevation: number;
  action: InteractionAction;
  destination: Cell;
  phase: 'approaching' | 'preparing' | 'recovering';
  elapsed: number;
  attempted: boolean;
  applied: boolean;
  clipOwned: boolean;
  facing: SpriteDirection;
  finishedRevision: number | null;
}

const level = (cell: Cell) => cell.level ?? 'ground';
const equal = (a: Cell, b: Cell) => a.c === b.c && a.r === b.r && level(a) === level(b);
const initial = (reason: string | null = null, effectApplied = false): InteractionState => ({
  phase: 'idle', actorId: null, targetId: null, actionId: null, elapsedSeconds: 0, effectApplied, reason,
});

function sync<T>(callback: (...args: never[]) => T, invoke: () => T): T {
  if (callback.constructor.name === 'AsyncFunction') throw new TypeError('Interaction callbacks must be synchronous');
  const result = invoke();
  if (result && (typeof result === 'object' || typeof result === 'function') && 'then' in result
    && typeof result.then === 'function') {
    // Consume rejection without permitting a promise to count as a committed effect.
    void Promise.resolve(result).catch(() => {});
    throw new TypeError('Interaction callbacks must be synchronous');
  }
  return result;
}

function validateAction(action: InteractionAction): void {
  if (!action || typeof action.id !== 'string' || !action.id.length || action.id.length > 256
    || typeof action.perform !== 'function' || (action.canPerform !== undefined && typeof action.canPerform !== 'function')) {
    throw new TypeError('An interaction requires an ID and synchronous perform callback');
  }
  for (const value of [action.prepareSeconds, action.recoverSeconds]) {
    if (!Number.isFinite(value) || value < 0 || value > 3600) throw new RangeError('Interaction durations must be in [0, 3600] seconds');
  }
  if (action.perform.constructor.name === 'AsyncFunction' || action.canPerform?.constructor.name === 'AsyncFunction') {
    throw new TypeError('Interaction callbacks must be synchronous');
  }
}

/** Approach, prepare, apply one host effect, and recover on simulation frames. */
export function createInteractions(runtime: InteractionRuntime, options: InteractionOptions = {}): InteractionController {
  const maxHeightDifference = options.maxHeightDifference ?? 0;
  if (!Number.isFinite(maxHeightDifference) || maxHeightDifference < 0) {
    throw new RangeError('Interaction maxHeightDifference must be finite and nonnegative');
  }
  const heightsMatch = (a: number, b: number, tolerance = maxHeightDifference) =>
    Number.isFinite(a) && Number.isFinite(b) && Math.abs(a - b) <= tolerance + 1e-6;
  let active: Job | null = null;
  let idle = initial();
  let disposed = false;
  let revision = 0;
  let callbackDepth = 0;
  let expectedCommand: { id: string; kind: 'move' | 'stop'; pending: boolean } | null = null;
  const disposers: (() => void)[] = [];
  const current = (job: Job) => !disposed && active === job;
  function invoke<T>(callback: (...args: never[]) => T, execute: () => T): T {
    callbackDepth++;
    try { return sync(callback, execute); } finally { callbackDepth--; }
  }

  function state(): InteractionState {
    return active ? {
      phase: active.phase, actorId: active.actorId, targetId: active.target.id, actionId: active.action.id,
      elapsedSeconds: active.elapsed, effectApplied: active.applied, reason: null,
    } : { ...idle };
  }
  function report(error: unknown): void {
    try {
      if (options.onError) invoke(options.onError, () => options.onError!(error instanceof Error ? error : new Error(String(error))));
    } catch { /* Reporting must not interrupt cleanup or escape runtime event delivery. */ }
  }
  function ownCommand<T>(id: string, kind: 'move' | 'stop', execute: () => T): T {
    const previous = expectedCommand;
    expectedCommand = { id, kind, pending: true };
    try { return execute(); } finally { expectedCommand = previous; }
  }
  function finish(job: Job, reason: string, touchRuntime = true, notify = true, stopMotion = true): void {
    if (active !== job) return;
    active = null;
    const finishedRevision = ++revision;
    job.finishedRevision = finishedRevision;
    idle = initial(reason, job.applied);
    // Clear before stop: stop emits user callbacks which may start a newer action.
    if (touchRuntime) {
      try { if (job.clipOwned) runtime.setAnimation(job.actorId, null); } catch (error) { report(error); }
      if (stopMotion && !disposed && revision === finishedRevision) {
        try { ownCommand(job.actorId, 'stop', () => runtime.stop(job.actorId)); } catch (error) { report(error); }
      }
    }
    if (notify && revision === finishedRevision) changed();
  }
  function changed(): void {
    if (!options.onChange || disposed) return;
    const observed = active;
    try { invoke(options.onChange, () => options.onChange!(state())); }
    catch (error) {
      if (observed && current(observed)) finish(observed, 'callback-error', true, false);
      report(error);
    }
  }
  function fail(job: Job, error: unknown): void {
    if (current(job)) finish(job, 'error');
    report(error);
  }
  function context(job: Job): InteractionContext | null {
    const actor = runtime.getEntity(job.actorId);
    const target = runtime.getEntity(job.target.id);
    return actor && target ? { runtime, actor, target, actionId: job.action.id } : null;
  }
  function targetValid(job: Job): boolean {
    const target = runtime.getEntity(job.target.id);
    if (!target) return job.applied; // Collecting may intentionally remove the target.
    const pose = runtime.getEntityPose(target.id);
    return target.type === job.target.type && equal(target, job.target) && !!pose && !pose.airborne && equal(pose.position, target)
      && heightsMatch(pose.elevation, job.targetElevation, 0);
  }
  function actorValid(job: Job, atDestination: boolean): boolean {
    const actor = runtime.getEntity(job.actorId);
    const pose = runtime.getEntityPose(job.actorId);
    return !!actor && !!pose && !pose.airborne
      && (!atDestination || (equal(actor, job.destination) && equal(pose.position, actor)));
  }
  function withinReach(job: Job): boolean {
    const pose = runtime.getEntityPose(job.actorId);
    return !!pose && heightsMatch(pose.elevation, job.targetElevation);
  }
  function permitted(job: Job): boolean {
    const ctx = context(job);
    if (!ctx) return false;
    const callback = job.action.canPerform;
    return !callback || invoke(callback, () => callback(ctx)) === true;
  }
  function useClip(job: Job, clips: InteractionAction['clips']): boolean {
    const clip = clips?.[job.facing];
    if (clip === undefined) return true;
    // Mark ownership before the call so a partially failing adapter is cleaned up.
    job.clipOwned = true;
    return runtime.setAnimation(job.actorId, clip);
  }
  function begin(job: Job): void {
    if (!current(job) || !actorValid(job, true) || !targetValid(job)) return;
    if (!withinReach(job)) { finish(job, 'invalid-target'); return; }
    ownCommand(job.actorId, 'stop', () => runtime.stop(job.actorId));
    if (!current(job) || runtime.isPaused) return;
    if (!actorValid(job, true) || !targetValid(job) || !withinReach(job) || !permitted(job)) {
      if (current(job)) finish(job, 'invalid-target');
      return;
    }
    if (!current(job) || runtime.isPaused) return;
    // The side selected during routing establishes the visible isometric facing.
    runtime.setFacing(job.actorId, job.facing);
    if (!current(job)) return;
    if (!useClip(job, job.action.clips)) { finish(job, 'invalid-clip'); return; }
    if (!current(job)) return;
    job.phase = 'preparing';
    job.elapsed = 0;
    changed();
  }
  function advance(deltaSeconds: number): void {
    const job = active;
    if (!job || disposed || callbackDepth || runtime.isPaused) return;
    try {
      if (!Number.isFinite(deltaSeconds) || deltaSeconds < 0 || deltaSeconds > 60) throw new RangeError('Interaction frame delta must be in [0, 60]');
      if (!actorValid(job, job.phase !== 'approaching') || !targetValid(job)
        || (job.phase !== 'approaching' && !withinReach(job))) { finish(job, 'invalid-target'); return; }
      if (job.phase === 'approaching') {
        if (actorValid(job, true)) begin(job);
        // A movement frame is not also counted as preparation time.
        return;
      }
      let remaining = deltaSeconds;
      if (job.phase === 'preparing') {
        if (job.attempted) return; // A reentrant frame during perform cannot apply twice.
        const used = Math.min(remaining, Math.max(0, job.action.prepareSeconds - job.elapsed));
        job.elapsed += used;
        remaining -= used;
        changed();
        if (!current(job) || runtime.isPaused || job.elapsed < job.action.prepareSeconds) return;
        if (!actorValid(job, true) || !targetValid(job) || !withinReach(job) || !permitted(job)) {
          if (current(job)) finish(job, 'invalid-target');
          return;
        }
        if (!current(job) || runtime.isPaused) return;
        // Predicates are host callbacks too: recheck their mutations before effect.
        const ctx = context(job);
        if (!ctx || !actorValid(job, true) || !targetValid(job) || !withinReach(job)) { finish(job, 'invalid-target'); return; }
        job.attempted = true;
        const committed = invoke(job.action.perform, () => job.action.perform(ctx));
        job.applied = committed === true;
        if (!current(job)) {
          // Cancellation inside perform happens before its return value is known.
          // Reconcile only that job's still-current idle result, never a newer job.
          if (job.applied && !active && job.finishedRevision === revision && !idle.effectApplied) {
            idle = { ...idle, effectApplied: true };
            changed();
          }
          return;
        }
        if (!job.applied) { finish(job, 'effect-rejected'); return; }
        job.phase = 'recovering';
        job.elapsed = 0;
        if (!actorValid(job, true) || !targetValid(job) || !withinReach(job)) { finish(job, 'invalid-target'); return; }
        if (!useClip(job, job.action.recoveryClips)) { finish(job, 'invalid-clip'); return; }
        changed();
      }
      if (!current(job) || runtime.isPaused || job.phase !== 'recovering') return;
      job.elapsed = Math.min(job.action.recoverSeconds, job.elapsed + remaining);
      if (job.elapsed >= job.action.recoverSeconds) finish(job, 'completed');
      else changed();
    } catch (error) { fail(job, error); }
  }
  function dispose(touchRuntime: boolean): void {
    if (disposed) return;
    // Prevent requests in cleanup callbacks from resurrecting a disposed controller.
    disposed = true;
    const job = active;
    disposers.splice(0).forEach(off => off());
    if (job) {
      active = null;
      job.finishedRevision = ++revision;
      idle = initial('destroyed', job.applied);
      if (touchRuntime) {
        try { if (job.clipOwned) runtime.setAnimation(job.actorId, null); } catch (error) { report(error); }
        try { runtime.stop(job.actorId); } catch (error) { report(error); }
      }
    }
  }

  disposers.push(
    runtime.on('frame', event => advance(event.deltaSeconds)),
    runtime.on('command', event => {
      if (expectedCommand?.pending && expectedCommand.id === event.id && expectedCommand.kind === event.kind) {
        expectedCommand.pending = false;
        return;
      }
      if (active?.actorId === event.id) {
        // Input and jump take over motion themselves. Calling stop here would reset
        // the held controls before the incoming command can consume/release them.
        finish(active, `actor-${event.kind}`, true, true, event.kind !== 'input' && event.kind !== 'jump');
      }
    }),
    runtime.on('blocked', event => { if (active?.actorId === event.id) finish(active, 'blocked'); }),
    runtime.on('scenechange', () => { if (active) finish(active, 'scenechange', false); }),
    runtime.on('destroy', () => dispose(false)),
  );

  return {
    getState: state,
    cancel(reason = 'cancelled') { if (active) finish(active, reason); },
    destroy() { dispose(true); },
    request({ actorId, targetId, action }) {
      if (disposed) return false;
      if (active?.actorId === actorId && active.target.id === targetId && active.action.id === action.id) return true;
      if (runtime.isPaused) return false;
      validateAction(action);
      if (active) finish(active, 'replaced');
      // A cancellation callback may already have supplied the replacement.
      if (disposed || active || runtime.isPaused) return false;
      const requestRevision = revision;
      const actor = runtime.getEntity(actorId);
      const target = runtime.getEntity(targetId);
      const pose = runtime.getEntityPose(actorId);
      if (!actor || !target || actorId === targetId || !pose || pose.airborne) return false;
      const targetElevation = runtime.getElevation(target);
      const scene = runtime.serializeScene();
      const actorType = scene.entityTypes[actor.type];
      const targetType = scene.entityTypes[target.type];
      if (!actorType || !targetType) return false;
      const ac = actorType.columns ?? 1, ar = actorType.rows ?? 1;
      const tc = targetType.columns ?? 1, tr = targetType.rows ?? 1;
      const candidates: { cell: Cell; facing: SpriteDirection; distance: number }[] = [];
      const add = (c: number, r: number, facing: SpriteDirection) => {
        const cell: Cell = { c, r, level: level(target) };
        const path = runtime.findPath(actorId, cell);
        if (!path || !heightsMatch(runtime.getElevation(cell), targetElevation)) return;
        let previous: Cell = actor;
        let distance = 0;
        for (const step of path) {
          distance += Math.hypot(step.c - previous.c, step.r - previous.r);
          previous = step;
        }
        candidates.push({ cell, facing, distance });
      };
      // Rectangles touch along one edge; corners and overlapping footprints are excluded.
      for (let r = target.r - ar + 1; r < target.r + tr; r++) {
        add(target.c - ac, r, 'ne');
        add(target.c + tc, r, 'sw');
      }
      for (let c = target.c - ac + 1; c < target.c + tc; c++) {
        add(c, target.r - ar, 'se');
        add(c, target.r + tr, 'nw');
      }
      candidates.sort((a, b) => a.distance - b.distance);
      const selected = candidates[0];
      if (!selected || revision !== requestRevision || disposed) return false;
      const job: Job = {
        actorId, target: { ...target }, targetElevation,
        action: { ...action, clips: { ...action.clips }, recoveryClips: { ...action.recoveryClips } },
        destination: selected.cell, facing: selected.facing,
        phase: 'approaching', elapsed: 0, attempted: false, applied: false, clipOwned: false,
        finishedRevision: null,
      };
      active = job;
      ++revision;
      try {
        if (!targetValid(job)) { finish(job, 'invalid-target'); return false; }
        // Even a zero-length route must pass through moveTo/stop to cancel held input
        // and snap any prior ground motion back to the committed cell.
        const result = ownCommand(actorId, 'move', () => runtime.moveTo(actorId, selected.cell));
        if (!current(job)) return false;
        if (result !== 'started' && result !== 'arrived') { finish(job, result); return false; }
        if (actorValid(job, true)) begin(job);
        else changed();
        return current(job);
      } catch (error) { fail(job, error); return false; }
    },
  };
}
