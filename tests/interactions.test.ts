import assert from 'node:assert/strict';
import { test } from 'node:test';
import { createInteractions, type InteractionAction, type InteractionRuntime, type InteractionState } from '../src/interactions.ts';
import { WorldModel } from '../src/model.ts';
import type { Cell, EntityPose, MoveResult, Scene, SpriteDirection } from '../src/types.ts';

function scene(): Scene {
  return {
    version: 1, name: 'Interaction test', tileWidth: 64, tileHeight: 32, diagonal: false,
    map: Array.from({ length: 7 }, () => Array<string>(7).fill('grass')),
    tiles: { grass: { color: 0x77aa55 } },
    entityTypes: {
      actor: { visual: { kind: 'actor' }, blocking: true },
      pot: { visual: { kind: 'box' }, blocking: true },
      large: { visual: { kind: 'box' }, blocking: true, columns: 2, rows: 2 },
    },
    entities: [{ id: 'hero', type: 'actor', c: 1, r: 2 }, { id: 'pot', type: 'pot', c: 2, r: 2 }],
  };
}

type EventPayloads = {
  frame: { deltaSeconds: number };
  command: { id: string; kind: 'move' | 'input' | 'jump' | 'stop' };
  blocked: { id: string; target: Cell };
  scenechange: { name: string };
  destroy: Record<string, never>;
};

class FakeRuntime implements InteractionRuntime {
  model: WorldModel;
  isPaused = false;
  dead = false;
  poses = new Map<string, EntityPose>();
  listeners = new Map<keyof EventPayloads, Set<(event: never) => void>>();
  moves: Cell[] = [];
  animations: (string | null)[] = [];
  facings: SpriteDirection[] = [];
  stops = 0;
  animationFailure: 'throw' | 'false' | null = null;
  constructor(data = scene()) { this.model = new WorldModel(data); }
  assertAlive() { assert.equal(this.dead, false, 'controller must not call destroyed runtime'); }
  getEntity(id: string) { this.assertAlive(); return this.model.entity(id); }
  getEntityPose(id: string): EntityPose | undefined {
    this.assertAlive();
    const entity = this.model.entity(id);
    return entity ? structuredClone(this.poses.get(id) ?? { position: entity, elevation: this.getElevation(entity), airborne: false }) : undefined;
  }
  getElevation(cell: Cell) { this.assertAlive(); return this.model.tile(cell)?.elevation ?? 0; }
  serializeScene() { this.assertAlive(); return this.model.serialize(); }
  findPath(id: string, cell: Cell) { this.assertAlive(); return this.model.path(id, cell); }
  moveTo(id: string, cell: Cell): MoveResult {
    this.assertAlive();
    this.emit('command', { id, kind: 'move' });
    const path = this.model.path(id, cell);
    this.moves.push({ ...cell });
    this.poses.delete(id);
    return path === null ? 'blocked' : path.length ? 'started' : 'arrived';
  }
  stop(id: string) { this.assertAlive(); this.stops++; this.emit('command', { id, kind: 'stop' }); this.poses.delete(id); }
  setFacing(_id: string, facing: SpriteDirection) { this.assertAlive(); this.facings.push(facing); return true; }
  setAnimation(_id: string, clip: string | null) {
    this.assertAlive();
    if (clip !== null && this.animationFailure === 'throw') throw new Error('Unknown clip');
    if (clip !== null && this.animationFailure === 'false') return false;
    this.animations.push(clip);
    return true;
  }
  on<K extends keyof EventPayloads>(name: K, listener: (event: EventPayloads[K]) => void) {
    const group = this.listeners.get(name) ?? new Set();
    this.listeners.set(name, group);
    group.add(listener as (event: never) => void);
    return () => { group.delete(listener as (event: never) => void); };
  }
  emit<K extends keyof EventPayloads>(name: K, event: EventPayloads[K]) {
    for (const listener of [...(this.listeners.get(name) ?? [])]) {
      if (this.listeners.get(name)?.has(listener)) listener(event as never);
    }
  }
  frame(deltaSeconds: number) { this.emit('frame', { deltaSeconds }); }
  arrive() { this.model.setPosition('hero', this.moves.at(-1)!); this.poses.delete('hero'); this.frame(0.1); }
  destroy() { this.dead = true; this.emit('destroy', {}); }
}

function action(perform: InteractionAction['perform'] = () => true): InteractionAction {
  return { id: 'pick', prepareSeconds: 1, recoverSeconds: 0.5, clips: { ne: 'pick-ne' }, recoveryClips: { ne: 'recover-ne' }, perform };
}
const request = (definition: InteractionAction = action()) => ({ actorId: 'hero', targetId: 'pot', action: definition });

test('adjacent action faces target, prepares, atomically removes once and recovers using simulation seconds', () => {
  const runtime = new FakeRuntime();
  let inventory = 0;
  const states: InteractionState[] = [];
  const controller = createInteractions(runtime, { onChange: value => states.push(value) });
  assert.equal(controller.request(request(action(({ target }) => {
    if (!runtime.model.remove(target.id)) return false;
    inventory++;
    return true;
  }))), true);
  assert.equal(controller.getState().phase, 'preparing');
  assert.deepEqual(runtime.facings, ['ne']);
  runtime.frame(0.99);
  assert.equal(inventory, 0);
  runtime.frame(0.01);
  assert.equal(inventory, 1);
  assert.equal(controller.getState().phase, 'recovering');
  runtime.frame(0.5);
  assert.equal(controller.getState().reason, 'completed');
  assert.equal(controller.getState().effectApplied, true);
  assert.deepEqual(runtime.animations, ['pick-ne', 'recover-ne', null]);
  runtime.frame(60);
  assert.equal(inventory, 1);
  assert.ok(states.some(value => value.phase === 'recovering' && value.effectApplied));
});

test('routes to nearest reachable cardinal footprint edge and does not spend movement time on preparation', () => {
  const data = scene();
  data.entities[0] = { id: 'hero', type: 'actor', c: 0, r: 0 };
  data.entities[1] = { id: 'pot', type: 'large', c: 3, r: 3 };
  const runtime = new FakeRuntime(data);
  const controller = createInteractions(runtime);
  assert.equal(controller.request(request()), true);
  assert.equal(controller.getState().phase, 'approaching');
  assert.deepEqual(runtime.moves[0], { c: 2, r: 3, level: 'ground' });
  runtime.arrive();
  assert.equal(controller.getState().phase, 'preparing');
  assert.equal(controller.getState().elapsedSeconds, 0);
});

test('blocked closest neighbor is skipped and a reachable side is selected', () => {
  const data = scene();
  data.entities[0] = { id: 'hero', type: 'actor', c: 0, r: 2 };
  data.entities.push({ id: 'wall', type: 'pot', c: 1, r: 2 });
  const runtime = new FakeRuntime(data);
  const controller = createInteractions(runtime);
  assert.equal(controller.request(request()), true);
  assert.notDeepEqual(runtime.moves[0], { c: 1, r: 2, level: 'ground' });
  assert.ok(runtime.moves[0]!.c === 2 || runtime.moves[0]!.r === 2);
});

test('unreachable target and different disconnected floor do not start an interaction', () => {
  const data = scene();
  for (const [c, r] of [[1, 2], [3, 2], [2, 1], [2, 3]]) {
    if (c === 1 && r === 2) continue;
    data.entities.push({ id: `wall-${c}-${r}`, type: 'pot', c: c!, r: r! });
  }
  data.entities[0] = { id: 'hero', type: 'actor', c: 0, r: 0 };
  data.entities.push({ id: 'wall-left', type: 'pot', c: 1, r: 2 });
  assert.equal(createInteractions(new FakeRuntime(data)).request(request()), false);
  const layered = scene();
  layered.version = 2;
  layered.links = [];
  layered.levels = [{ id: 'bridge', name: 'Bridge', height: 32, map: layered.map }];
  layered.entities[1]!.level = 'bridge';
  assert.equal(createInteractions(new FakeRuntime(layered)).request(request()), false);
});

test('spam while approaching, preparing or recovering does not restart or duplicate the effect', () => {
  const runtime = new FakeRuntime();
  runtime.model.setPosition('hero', { c: 0, r: 0 });
  let count = 0;
  const definition = action(() => { count++; return true; });
  const controller = createInteractions(runtime);
  controller.request(request(definition));
  for (let i = 0; i < 20; i++) controller.request(request(definition));
  assert.equal(runtime.moves.length, 1);
  runtime.arrive();
  runtime.frame(0.5);
  controller.request(request({ ...definition, prepareSeconds: 20 }));
  assert.equal(controller.getState().elapsedSeconds, 0.5);
  runtime.frame(0.5);
  controller.request(request(definition));
  runtime.frame(0.5);
  assert.equal(count, 1);
  assert.equal(runtime.animations.filter(clip => clip === 'pick-ne').length, 1);
});

test('paused runtime freezes both phases and rejects new requests', () => {
  const runtime = new FakeRuntime();
  const controller = createInteractions(runtime);
  runtime.isPaused = true;
  assert.equal(controller.request(request()), false);
  runtime.isPaused = false;
  controller.request(request());
  runtime.frame(0.4);
  runtime.isPaused = true;
  runtime.frame(40);
  assert.equal(controller.getState().elapsedSeconds, 0.4);
  runtime.isPaused = false;
  runtime.frame(0.6);
  assert.equal(controller.getState().phase, 'recovering');
  runtime.isPaused = true;
  runtime.frame(40);
  assert.equal(controller.getState().elapsedSeconds, 0);
});

test('cancelling before effect does nothing; cancellation after effect never undoes host state', () => {
  const runtime = new FakeRuntime();
  let count = 0;
  const controller = createInteractions(runtime);
  const definition = action(() => { count++; return true; });
  controller.request(request(definition));
  runtime.frame(0.9);
  controller.cancel();
  runtime.frame(5);
  assert.equal(count, 0);
  controller.request(request(definition));
  runtime.frame(1);
  controller.cancel('walk-away');
  assert.equal(count, 1);
  assert.equal(controller.getState().effectApplied, true);
  assert.equal(controller.getState().reason, 'walk-away');
  assert.equal(runtime.animations.at(-1), null);
});

for (const kind of ['move', 'input', 'jump', 'stop'] as const) {
  test(`foreign actor ${kind} command immediately cancels; another actor's command does not`, () => {
    const runtime = new FakeRuntime();
    const controller = createInteractions(runtime);
    controller.request(request());
    runtime.emit('command', { id: 'other', kind });
    assert.equal(controller.getState().phase, 'preparing');
    const previousStops = runtime.stops;
    runtime.emit('command', { id: 'hero', kind });
    assert.equal(controller.getState().reason, `actor-${kind}`);
    assert.equal(runtime.animations.at(-1), null);
    if (kind === 'input' || kind === 'jump') assert.equal(runtime.stops, previousStops, 'preserve incoming held controls and jump direction');
  });
}

test('target removal, teleport or airborne pose before effect invalidates the pending job', () => {
  for (const mutate of [
    (runtime: FakeRuntime) => runtime.model.remove('pot'),
    (runtime: FakeRuntime) => runtime.model.setPosition('pot', { c: 3, r: 2 }),
    (runtime: FakeRuntime) => runtime.poses.set('pot', { position: { c: 2, r: 2 }, airborne: true, elevation: 4 }),
  ]) {
    const runtime = new FakeRuntime();
    let effects = 0;
    const controller = createInteractions(runtime);
    controller.request(request(action(() => { effects++; return true; })));
    mutate(runtime);
    runtime.frame(1);
    assert.equal(effects, 0);
    assert.equal(controller.getState().phase, 'idle');
  }
});

test('preparation cannot apply while the actor is airborne, between cells, moved or removed', () => {
  for (const mutate of [
    (runtime: FakeRuntime) => runtime.poses.set('hero', { position: { c: 1, r: 2 }, airborne: true, elevation: 4 }),
    (runtime: FakeRuntime) => runtime.poses.set('hero', { position: { c: 1.25, r: 2 }, airborne: false, elevation: 0 }),
    (runtime: FakeRuntime) => runtime.model.setPosition('hero', { c: 1, r: 1 }),
    (runtime: FakeRuntime) => runtime.model.remove('hero'),
  ]) {
    const runtime = new FakeRuntime();
    let effects = 0;
    const controller = createInteractions(runtime);
    controller.request(request(action(() => { effects++; return true; })));
    mutate(runtime);
    runtime.frame(1);
    assert.equal(effects, 0);
    assert.equal(controller.getState().phase, 'idle');
  }
});

test('airborne requests are rejected before moveTo could cancel flight', () => {
  const runtime = new FakeRuntime();
  runtime.poses.set('hero', { position: { c: 1, r: 2 }, elevation: 15, airborne: true });
  const controller = createInteractions(runtime);
  assert.equal(controller.request(request()), false);
  assert.equal(runtime.moves.length, 0);
  assert.equal(runtime.stops, 0);
});

test('continuous arrival pose must match committed cell before preparation begins', () => {
  const runtime = new FakeRuntime();
  runtime.model.setPosition('hero', { c: 0, r: 0 });
  const controller = createInteractions(runtime);
  controller.request(request());
  runtime.model.setPosition('hero', runtime.moves[0]!);
  runtime.poses.set('hero', { position: { c: 0.9, r: 2 }, elevation: 0, airborne: false });
  runtime.frame(1);
  assert.equal(controller.getState().phase, 'approaching');
  runtime.poses.delete('hero');
  runtime.frame(0.1);
  assert.equal(controller.getState().phase, 'preparing');
  assert.equal(controller.getState().elapsedSeconds, 0);
});

test('scene replacement drops job without changing a new scene actor with the same ID', () => {
  const runtime = new FakeRuntime();
  const controller = createInteractions(runtime);
  controller.request(request());
  const beforeStops = runtime.stops;
  const beforeClips = runtime.animations.length;
  runtime.model = new WorldModel(scene());
  runtime.emit('scenechange', { name: 'Replacement' });
  assert.equal(controller.getState().reason, 'scenechange');
  assert.equal(runtime.stops, beforeStops);
  assert.equal(runtime.animations.length, beforeClips);
});

test('runtime destruction disconnects without touching the dead runtime and is repeatable', () => {
  const runtime = new FakeRuntime();
  const controller = createInteractions(runtime);
  controller.request(request());
  runtime.destroy();
  assert.equal(controller.getState().reason, 'destroyed');
  assert.equal([...runtime.listeners.values()].reduce((n, group) => n + group.size, 0), 0);
  controller.destroy();
  controller.cancel();
  assert.equal(controller.request(request()), false);
});

test('large delta consumes preparation and recovery once, including zero-duration phases', () => {
  for (const seconds of [0, 1]) {
    const runtime = new FakeRuntime();
    let effects = 0;
    const controller = createInteractions(runtime);
    controller.request(request({ ...action(() => { effects++; return true; }), prepareSeconds: seconds, recoverSeconds: seconds }));
    runtime.frame(60);
    assert.equal(effects, 1);
    assert.equal(controller.getState().reason, 'completed');
  }
});

test('perform reentrancy cannot duplicate effects or clear a replacement animation', () => {
  const runtime = new FakeRuntime();
  const controller = createInteractions(runtime);
  let effects = 0;
  controller.request(request(action(() => {
    effects++;
    runtime.frame(60);
    controller.request(request({ ...action(), id: 'new-action', clips: { ne: 'new-clip' } }));
    return true;
  })));
  runtime.frame(1);
  assert.equal(effects, 1);
  assert.equal(controller.getState().actionId, 'new-action');
  assert.equal(controller.getState().phase, 'preparing');
  assert.equal(runtime.animations.at(-1), 'new-clip');
});

test('perform may destroy runtime; no continuation calls the destroyed object', () => {
  const runtime = new FakeRuntime();
  const controller = createInteractions(runtime);
  controller.request(request(action(() => { runtime.destroy(); return true; })));
  runtime.frame(1);
  assert.equal(controller.getState().phase, 'idle');
  assert.equal(controller.getState().reason, 'destroyed');
});

test('predicate mutation immediately before effect is revalidated; callback frame recursion is ignored', () => {
  const runtime = new FakeRuntime();
  let checks = 0;
  let effects = 0;
  const controller = createInteractions(runtime);
  controller.request(request({ ...action(() => { effects++; return true; }), canPerform: () => {
    runtime.frame(60);
    if (++checks === 2) runtime.model.remove('pot');
    return true;
  } }));
  assert.equal(checks, 1);
  runtime.frame(1);
  assert.equal(checks, 2);
  assert.equal(effects, 0);
  assert.equal(controller.getState().phase, 'idle');
});

test('throwing predicates/effects and invalid clips clean up; rejected effects never recover', () => {
  for (const failure of ['predicate', 'effect', 'clip', 'unsupported-clip', 'rejected'] as const) {
    const runtime = new FakeRuntime();
    const errors: Error[] = [];
    const controller = createInteractions(runtime, { onError: error => errors.push(error) });
    if (failure === 'clip') runtime.animationFailure = 'throw';
    if (failure === 'unsupported-clip') runtime.animationFailure = 'false';
    const definition = action(() => { if (failure === 'effect') throw new Error('effect'); return failure !== 'rejected'; });
    if (failure === 'predicate') definition.canPerform = () => { throw new Error('predicate'); };
    controller.request(request(definition));
    runtime.frame(1);
    assert.equal(controller.getState().phase, 'idle', failure);
    assert.equal(controller.getState().effectApplied, false, failure);
    if (failure !== 'predicate') assert.equal(runtime.animations.at(-1), null, failure);
    if (['predicate', 'effect', 'clip'].includes(failure)) assert.equal(errors.length, 1, failure);
  }
});

test('onChange exception cancels safely and onError exception does not escape', () => {
  const runtime = new FakeRuntime();
  const controller = createInteractions(runtime, {
    onChange: () => { throw new Error('HUD failed'); },
    onError: () => { throw new Error('report failed'); },
  });
  assert.doesNotThrow(() => controller.request(request()));
  assert.equal(controller.getState().reason, 'callback-error');
  assert.equal(runtime.animations.at(-1), null);
});

test('durations and callbacks are validated; a promise never counts as a committed effect', async () => {
  const runtime = new FakeRuntime();
  const controller = createInteractions(runtime);
  for (const invalid of [NaN, Infinity, -1, 3601]) {
    assert.throws(() => controller.request(request({ ...action(), prepareSeconds: invalid })), RangeError);
    assert.throws(() => controller.request(request({ ...action(), recoverSeconds: invalid })), RangeError);
  }
  let invoked = false;
  const asyncAction = { ...action(), perform: async () => { invoked = true; return true; } } as unknown as InteractionAction;
  assert.throws(() => controller.request(request(asyncAction)), /synchronous/);
  assert.equal(invoked, false);
  controller.request(request({ ...action(), perform: (() => Promise.reject(new Error('async failed'))) as unknown as InteractionAction['perform'] }));
  runtime.frame(1);
  await new Promise(resolve => setTimeout(resolve, 0));
  assert.equal(controller.getState().effectApplied, false);
  assert.equal(controller.getState().reason, 'error');
});

test('state snapshots and action clip maps are detached from callers', () => {
  const runtime = new FakeRuntime();
  const controller = createInteractions(runtime);
  const definition = action();
  controller.request(request(definition));
  controller.getState().elapsedSeconds = 999;
  definition.recoveryClips!.ne = 'mutated';
  runtime.frame(1);
  assert.equal(runtime.animations.at(-1), 'recover-ne');
  assert.equal(controller.getState().elapsedSeconds, 0);
});

test('same-floor adjacency cannot reach a target on a higher surface by default', () => {
  const data = scene();
  data.tiles.raised = { color: 0x998844, elevation: 128 };
  data.map[2]![2] = 'raised';
  const runtime = new FakeRuntime(data);
  let effects = 0;
  const controller = createInteractions(runtime);
  assert.equal(controller.request(request(action(() => { effects++; return true; }))), false);
  runtime.frame(60);
  assert.equal(effects, 0);
  assert.equal(runtime.moves.length, 0);
});

test('routing skips an adjacent low cell and selects a reachable equal-height side', () => {
  const data = scene();
  data.tiles.raised = { color: 0x998844, elevation: 128 };
  data.map[2]![2] = 'raised';
  data.map[1]![2] = 'raised';
  data.maxStepHeight = 128;
  const runtime = new FakeRuntime(data);
  const controller = createInteractions(runtime);
  assert.equal(controller.request(request()), true);
  assert.deepEqual(runtime.moves[0], { c: 2, r: 1, level: 'ground' });
  assert.equal(controller.getState().phase, 'approaching');
  runtime.arrive();
  assert.equal(controller.getState().phase, 'preparing');
  runtime.frame(1.5);
  assert.equal(controller.getState().reason, 'completed');
});

test('explicit vertical reach is bounded and invalid values fail before subscriptions', () => {
  const data = scene();
  data.tiles.raised = { color: 0x998844, elevation: 128 };
  data.map[2]![2] = 'raised';
  assert.equal(createInteractions(new FakeRuntime(data), { maxHeightDifference: 127 }).request(request()), false);
  const runtime = new FakeRuntime(data);
  const controller = createInteractions(runtime, { maxHeightDifference: 128 });
  assert.equal(controller.request(request()), true);
  runtime.frame(1.5);
  assert.equal(controller.getState().effectApplied, true);
  for (const invalid of [-1, Infinity, NaN]) {
    const invalidRuntime = new FakeRuntime();
    assert.throws(() => createInteractions(invalidRuntime, { maxHeightDifference: invalid }), /finite and nonnegative/);
    assert.equal(invalidRuntime.listeners.size, 0);
  }
});

test('absolute feet heights are revalidated after the final predicate immediately before effect', () => {
  for (const changedId of ['hero', 'pot']) {
    const runtime = new FakeRuntime();
    let predicates = 0;
    let effects = 0;
    const controller = createInteractions(runtime);
    controller.request(request({ ...action(() => { effects++; return true; }), canPerform: () => {
      if (++predicates === 2) {
        runtime.poses.set(changedId, { position: runtime.getEntity(changedId)!, elevation: 128, airborne: false });
      }
      return true;
    } }));
    runtime.frame(1);
    assert.equal(effects, 0, changedId);
    assert.equal(controller.getState().reason, 'invalid-target', changedId);
  }
});

test('committed perform cancelling itself reconciles the final idle state and notification', () => {
  const runtime = new FakeRuntime();
  const notifications: InteractionState[] = [];
  const controller = createInteractions(runtime, { onChange: state => notifications.push(state) });
  let inventory = 0;
  controller.request(request(action(() => {
    inventory++;
    controller.cancel('committed-cancel');
    return true;
  })));
  runtime.frame(1);
  assert.equal(inventory, 1);
  assert.equal(controller.getState().phase, 'idle');
  assert.equal(controller.getState().reason, 'committed-cancel');
  assert.equal(controller.getState().effectApplied, true);
  assert.equal(notifications.at(-1)?.effectApplied, true);
});

test('committed old perform cannot overwrite a newer action or its cancellation result', () => {
  for (const cancelReplacement of [false, true]) {
    const runtime = new FakeRuntime();
    const controller = createInteractions(runtime);
    controller.request(request(action(() => {
      controller.cancel('old-cancel');
      controller.request(request({ ...action(), id: 'replacement', clips: { ne: 'replacement-clip' } }));
      if (cancelReplacement) controller.cancel('replacement-cancel');
      return true;
    })));
    runtime.frame(1);
    assert.equal(controller.getState().effectApplied, false);
    if (cancelReplacement) assert.equal(controller.getState().reason, 'replacement-cancel');
    else {
      assert.equal(controller.getState().actionId, 'replacement');
      assert.equal(runtime.animations.at(-1), 'replacement-clip');
    }
  }
});
