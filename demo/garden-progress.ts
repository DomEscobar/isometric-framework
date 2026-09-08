import { createInventory, createSaveSlot, validateScene } from '../src/index';
import type { EntityDefinition, InventorySnapshot, SaveRecord, SaveStorage, Scene } from '../src/index';

export const isCollectible = (entity: EntityDefinition, scene: Scene) => entity.data?.role === 'collectible'
  || (entity.data?.role === undefined && scene.entityTypes[entity.type]?.visual.kind === 'gem');
export const createGardenInventory = () => createInventory({ flower: { name: 'Garden flower' } });
export interface GardenState { baseline: Scene; inventory: InventorySnapshot }
export type GardenSave = SaveRecord<GardenState>;

/** These game-specific rules do not belong in the reusable save or inventory modules. */
export function createGardenSave(storage: SaveStorage) {
  const slot = createSaveSlot<GardenState>({
    key: 'little-worlds.sunflower.v1', gameId: 'little-worlds.sunflower', storage,
    validateState(input): GardenState {
      if (!input || typeof input !== 'object') throw new TypeError('Missing garden progress');
      const state = input as Partial<GardenState>;
      const baseline = validateScene(state.baseline);
      if (baseline.name !== 'Sunflower courtyard') throw new TypeError('This is not a Sunflower save');
      const inventory = createGardenInventory();
      inventory.restore(state.inventory);
      return { baseline, inventory: inventory.snapshot() };
    },
  });
  return {
    write: slot.write,
    read(): GardenSave | null {
      const save = slot.read();
      if (!save) return null;
      const inventory = createGardenInventory(); inventory.restore(save.state.inventory);
      const original = save.state.baseline.entities.filter(entity => isCollectible(entity, save.state.baseline));
      const remaining = save.scene.entities.filter(entity => isCollectible(entity, save.scene));
      if (save.scene.name !== 'Sunflower courtyard'
        || remaining.some(entity => !original.some(initial => initial.id === entity.id && initial.type === entity.type))
        || inventory.count('flower') + remaining.length !== original.length) {
        throw new TypeError('The saved basket and remaining flowers do not match');
      }
      return save;
    },
  };
}
