/** Host-defined item identity and a per-item unit limit. */
export interface ItemDefinition { name: string; maxCount?: number }
export interface InventoryOptions { /** Maximum total units, not slots. */ capacity?: number }
export interface InventorySnapshot { version: 1; items: { id: string; quantity: number }[] }
export interface Inventory {
  count(id: string): number;
  canAdd(id: string, quantity?: number): boolean;
  add(id: string, quantity?: number): boolean;
  remove(id: string, quantity?: number): boolean;
  snapshot(): InventorySnapshot;
  /** Validate completely before replacing the current contents. */
  restore(input: unknown): void;
}

function integer(value: unknown, minimum: number, label: string): number {
  if (typeof value !== 'number' || !Number.isSafeInteger(value) || value < minimum) {
    throw new TypeError(`${label} must be a safe integer of at least ${minimum}`);
  }
  return value;
}

/** A renderer-independent counter inventory. Game effects, UI and persistence stay with the host. */
export function createInventory(definitions: Record<string, ItemDefinition>, options: InventoryOptions = {}): Inventory {
  if (!definitions || typeof definitions !== 'object' || Array.isArray(definitions)) {
    throw new TypeError('Item definitions must be an object');
  }
  const capacity = integer(options.capacity ?? Number.MAX_SAFE_INTEGER, 0, 'Inventory capacity');
  const limits = new Map<string, number>();
  for (const [id, definition] of Object.entries(definitions)) {
    if (!id.trim() || !definition || typeof definition.name !== 'string' || !definition.name.trim()) {
      throw new TypeError('Items require a nonempty id and name');
    }
    limits.set(id, integer(definition.maxCount ?? Number.MAX_SAFE_INTEGER, 0, `Item ${id} maxCount`));
  }
  let contents = new Map<string, number>();
  let total = 0;
  const limit = (id: string): number => {
    const value = limits.get(id);
    if (value === undefined) throw new TypeError(`Unknown item: ${id}`);
    return value;
  };
  const canAdd = (id: string, quantity = 1): boolean => {
    const maximum = limit(id);
    integer(quantity, 1, 'Item quantity');
    return quantity <= capacity - total && quantity <= maximum - (contents.get(id) ?? 0);
  };
  return {
    count(id) { limit(id); return contents.get(id) ?? 0; },
    canAdd,
    add(id, quantity = 1) {
      if (!canAdd(id, quantity)) return false;
      contents.set(id, (contents.get(id) ?? 0) + quantity);
      total += quantity;
      return true;
    },
    remove(id, quantity = 1) {
      limit(id); integer(quantity, 1, 'Item quantity');
      const count = contents.get(id) ?? 0;
      if (quantity > count) return false;
      if (quantity === count) contents.delete(id);
      else contents.set(id, count - quantity);
      total -= quantity;
      return true;
    },
    snapshot: () => ({ version: 1, items: Array.from(contents, ([id, quantity]) => ({ id, quantity })) }),
    restore(input) {
      if (!input || typeof input !== 'object' || Array.isArray(input)) throw new TypeError('Invalid inventory snapshot');
      const snapshot = input as Record<string, unknown>;
      if (snapshot.version !== 1 || !Array.isArray(snapshot.items)) throw new TypeError('Invalid inventory snapshot version or items');
      const next = new Map<string, number>();
      let nextTotal = 0;
      for (const entry of snapshot.items) {
        if (!entry || typeof entry !== 'object' || Array.isArray(entry) || typeof entry.id !== 'string') {
          throw new TypeError('Invalid inventory item');
        }
        const maximum = limit(entry.id);
        const quantity = integer(entry.quantity, 1, 'Item quantity');
        if (next.has(entry.id)) throw new TypeError(`Duplicate inventory item: ${entry.id}`);
        if (quantity > maximum || quantity > capacity - nextTotal) throw new RangeError('Inventory snapshot exceeds capacity');
        next.set(entry.id, quantity);
        nextTotal += quantity;
      }
      contents = next;
      total = nextTotal;
    },
  };
}
