# Inventory and game checkpoints

Both modules are renderer-independent and exported from the package root and
`isometric-framework/core`. Item definitions, rewards, save timing, storage
location, and UI belong to the host game.

## Item quantities

```ts
import { createInventory } from 'isometric-framework/core';

const bag = createInventory({
  flower: { name: 'Garden flower', maxCount: 20 },
  seed: { name: 'Seed' },
}, { capacity: 30 });

if (bag.canAdd('flower', 2)) bag.add('flower', 2);
bag.remove('flower');
const count = bag.count('flower'); // 1
const data = bag.snapshot();      // { version: 1, items: [{ id, quantity }] }
bag.restore(data);
```

Capacity counts total units, not slots. Capacity and per-item `maxCount` default
to `Number.MAX_SAFE_INTEGER`. `add`/`remove` return false when capacity or quantity
is insufficient, with no partial change. Unknown IDs and invalid quantities throw.
Quantities must be positive safe integers. Empty items are omitted from snapshots.
`restore(unknown)` validates the complete snapshot before replacing contents;
unknown items, duplicate entries, bad versions, and excess capacity are rejected.
Snapshots are detached. Equipment, item instances, crafting, and UI are not supplied.

Claim a world pickup before awarding its item, after checking `canAdd`, as in
`demo/main.ts`. Keep that effect synchronous. Separate inventories do not provide
a shared transaction or multiplayer lock.

## A scene plus host state

```ts
import { createInventory, createSaveSlot } from 'isometric-framework/core';

const bag = createInventory({ flower: { name: 'Garden flower' } });
const slot = createSaveSlot({
  key: 'my-game.progress.v1', gameId: 'my-game',
  storage: localStorage, // Browser host choice; inject an in-memory adapter in Node.
  validateState(input) {
    const checked = createInventory({ flower: { name: 'Garden flower' } });
    checked.restore(input);
    return checked.snapshot();
  },
});

// runtime is an already-created runtime. Catch storage and load errors in the UI.
slot.write(runtime.serializeScene(), bag.snapshot());
const saved = slot.read();
if (saved) {
  actions.cancel('load-save'); // If this host has an interaction controller.
  await runtime.loadScene(saved.scene);
  bag.restore(saved.state);
}
```

`read()` returns null for an empty slot; invalid saves throw. A record contains
`version: 1`, `gameId`, `savedAt`, validated scene data, and validated host `state`.
`validateState` is required and synchronous: it defines your game's state schema.
Save data must contain only finite JSON values, with a 5 MiB encoded-record limit.
Wrong game IDs and unsupported versions are rejected. Migration is host-owned;
the helper does not silently reinterpret an old save.

`SaveStorage` has synchronous `getItem`, `setItem`, and `removeItem` methods.
Validation completes before one `setItem` call. The adapter must replace the full
value atomically or leave the old value intact on failure (as browser localStorage
does). Storage errors propagate to the host. `clear()` removes only this slot.
The module never accesses browser storage or loads a runtime implicitly.

Save **committed** progress: `serializeScene` excludes ongoing jumps, movement,
projectiles, and action timers. Reload resumes at the last committed cell; an
unfinished action must not grant its reward. Store camera, quests, or other host
state explicitly if your game needs them. Await successful scene loading before
applying the already-validated inventory, so asset failures keep current progress.

## Sunflower reference

`demo/garden-progress.ts` supplies the flower definition, save schema and basket /
remaining-flower consistency check. Sunflower saves on completed steps, landings,
and flower effects, and offers **Save garden** / **Continue garden**. Reload
automatically resumes a valid local save. Restart resets the original map and
basket and replaces the checkpoint. Other scene presets keep their existing rules
and do not overwrite the Sunflower slot. Plain scene export remains separate from
a game checkpoint and does not contain inventory.

The storage key is `little-worlds.sunflower.v1`. This is one save per browser
origin, without cloud sync or multiple slots in the demo UI. Save failures are
shown without stopping play. A failed read leaves both the current game and the
stored record intact. Changing games should use a different key and `gameId`.
