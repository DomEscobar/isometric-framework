import test from 'node:test';
import assert from 'node:assert/strict';
import { createInventory } from '../src/inventory.ts';
import { createSaveSlot, type SaveStorage } from '../src/saves.ts';
import type { Scene } from '../src/types.ts';

const scene: Scene = {
  version: 1, name: 'Progress checkpoint', tileWidth: 64, tileHeight: 32,
  map: [['grass']], tiles: { grass: { color: 0x449944 } }, entityTypes: {}, entities: [],
};
function storage(): SaveStorage & { values: Map<string, string> } {
  const values = new Map<string, string>();
  return {
    values, getItem: key => values.get(key) ?? null,
    setItem: (key, value) => { values.set(key, value); }, removeItem: key => { values.delete(key); },
  };
}
function validateState(input: unknown): { flowers: number } {
  const state = input as { flowers?: unknown } | null;
  if (!state || !Number.isSafeInteger(state.flowers) || (state.flowers as number) < 0) throw new TypeError('Invalid flower count');
  return { flowers: state.flowers as number };
}

test('inventory respects limits, detaches snapshots and rejects invalid restoration atomically', () => {
  const inventory = createInventory({ flower: { name: 'Flower', maxCount: 3 }, seed: { name: 'Seed' } }, { capacity: 4 });
  assert.equal(inventory.add('flower', 2), true);
  assert.equal(inventory.add('flower', 2), false);
  assert.equal(inventory.add('seed', 2), true);
  assert.equal(inventory.canAdd('flower'), false);
  assert.equal(inventory.remove('flower', 3), false);
  assert.equal(inventory.remove('seed'), true);
  assert.equal(inventory.add('flower'), true);
  const before = inventory.snapshot();
  const detached = inventory.snapshot(); detached.items[0]!.quantity = 100;
  assert.equal(inventory.count('flower'), 3);
  for (const items of [
    [{ id: 'flower', quantity: 1 }, { id: 'flower', quantity: 1 }],
    [{ id: 'seed', quantity: 1 }, { id: 'unknown', quantity: 1 }],
    [{ id: 'flower', quantity: -1 }], [{ id: 'flower', quantity: 1.5 }],
    [{ id: 'flower', quantity: 4 }], [{ id: 'seed', quantity: 5 }],
    [{ id: 'seed', quantity: Number.MAX_SAFE_INTEGER + 1 }],
  ]) {
    assert.throws(() => inventory.restore({ version: 1, items }));
    assert.deepEqual(inventory.snapshot(), before);
  }
  assert.throws(() => inventory.add('unknown'));
  assert.throws(() => inventory.remove('seed', 0));
  inventory.restore({ version: 1, items: [{ id: 'seed', quantity: 2 }] });
  assert.equal(inventory.count('flower'), 0);
  assert.equal(inventory.count('seed'), 2);
});

test('save slots roundtrip detached scene and state, rejecting corrupt and unsupported records', () => {
  const memory = storage();
  const slot = createSaveSlot({ key: 'slot', gameId: 'garden', storage: memory, validateState });
  assert.equal(slot.read(), null);
  slot.write(scene, { flowers: 2 });
  const valid = memory.values.get('slot')!;
  const loaded = slot.read()!;
  assert.deepEqual(loaded.scene, scene);
  assert.deepEqual(loaded.state, { flowers: 2 });
  loaded.scene.name = 'Changed'; loaded.state.flowers = 99;
  assert.equal(slot.read()!.scene.name, scene.name);
  assert.equal(slot.read()!.state.flowers, 2);
  for (const corrupt of [
    '{broken', JSON.stringify({ ...JSON.parse(valid), version: 2 }),
    JSON.stringify({ ...JSON.parse(valid), gameId: 'another-game' }),
    JSON.stringify({ ...JSON.parse(valid), scene: { version: 9 } }),
    JSON.stringify({ ...JSON.parse(valid), state: { flowers: -1 } }),
  ]) {
    memory.values.set('slot', corrupt);
    assert.throws(() => slot.read());
  }
  memory.values.set('slot', valid);
  assert.throws(() => slot.write(scene, { flowers: -1 }));
  const rawSlot = createSaveSlot<unknown>({ key: 'slot', gameId: 'garden', storage: memory, validateState: value => value });
  const cyclic: Record<string, unknown> = {}; cyclic.self = cyclic;
  for (const invalid of [{ fn: () => 1 }, { n: Infinity }, new Date(), cyclic, [undefined], Array(1)]) {
    assert.throws(() => rawSlot.write(scene, invalid));
    assert.equal(memory.values.get('slot'), valid);
  }
  slot.clear(); assert.equal(slot.read(), null);
});

test('storage failures propagate while the previous checkpoint remains intact', () => {
  const memory = storage();
  const slot = createSaveSlot({ key: 'slot', gameId: 'garden', storage: memory, validateState });
  slot.write(scene, { flowers: 1 });
  const before = memory.values.get('slot');
  memory.setItem = () => { throw new Error('Quota exceeded'); };
  assert.throws(() => slot.write(scene, { flowers: 2 }), /Quota exceeded/);
  assert.equal(memory.values.get('slot'), before);
  assert.equal(slot.read()!.state.flowers, 1);
  memory.getItem = () => { throw new Error('Storage unavailable'); };
  assert.throws(() => slot.read(), /Storage unavailable/);
});
