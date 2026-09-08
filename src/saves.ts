import { validateScene } from './scene.ts';
import type { Scene } from './types.ts';

/** Synchronous storage; setItem must either replace the whole value or leave it unchanged. */
export interface SaveStorage {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
  removeItem(key: string): void;
}
export interface SaveRecord<T> { version: 1; gameId: string; savedAt: string; scene: Scene; state: T }
export interface SaveSlotOptions<T> {
  key: string;
  gameId: string;
  storage: SaveStorage;
  /** Synchronously validate host state, throwing on invalid data. Returned state must be JSON-only. */
  validateState(input: unknown): T;
}
export interface SaveSlot<T> {
  read(): SaveRecord<T> | null;
  write(scene: Scene, state: T): void;
  clear(): void;
}

const MAX_BYTES = 5 * 1024 * 1024;
function checkSize(text: string): void {
  if (text.length > MAX_BYTES || new TextEncoder().encode(text).length > MAX_BYTES) {
    throw new RangeError('Save exceeds the 5 MiB limit');
  }
}

/** Do not silently lose functions, sparse array entries, accessors, or special objects in JSON. */
function cloneJSON(input: unknown): unknown {
  const ancestors = new Set<object>();
  let nodes = 0;
  function clone(value: unknown, depth: number): unknown {
    if (++nodes > 200_000 || depth > 64) throw new RangeError('Save exceeds the data nesting or node limit');
    if (value === null || typeof value === 'string' || typeof value === 'boolean') return value;
    if (typeof value === 'number' && Number.isFinite(value)) return value;
    if (!value || typeof value !== 'object') throw new TypeError('Save data must contain only finite JSON values');
    if (ancestors.has(value)) throw new TypeError('Save data contains a cycle');
    const array = Array.isArray(value);
    const prototype = Object.getPrototypeOf(value);
    if (!array && prototype !== Object.prototype && prototype !== null) throw new TypeError('Save data must use plain objects');
    if (Object.getOwnPropertySymbols(value).length) throw new TypeError('Save data must not have symbol keys');
    const descriptors = Object.getOwnPropertyDescriptors(value);
    for (const [key, descriptor] of Object.entries(descriptors)) {
      if (array && key === 'length') continue;
      if (descriptor.get || descriptor.set || !descriptor.enumerable) throw new TypeError('Save data must use enumerable data properties');
      if (array && (!/^(0|[1-9]\d*)$/.test(key) || Number(key) >= value.length)) throw new TypeError('Save arrays cannot have named properties');
    }
    ancestors.add(value);
    let result: unknown;
    if (array) {
      if (value.length > 200_000) throw new RangeError('Save array exceeds the data size limit');
      result = Array.from({ length: value.length }, (_, index) => {
        const descriptor = descriptors[String(index)];
        if (!descriptor) throw new TypeError('Save arrays cannot contain holes');
        return clone(descriptor.value, depth + 1);
      });
    } else {
      result = Object.fromEntries(Object.entries(descriptors).map(([key, descriptor]) => [key, clone(descriptor.value, depth + 1)]));
    }
    ancestors.delete(value);
    return result;
  }
  return clone(input, 0);
}

/** Explicit scene + host-state checkpoint. Never loads a runtime or accesses browser storage implicitly. */
export function createSaveSlot<T>(options: SaveSlotOptions<T>): SaveSlot<T> {
  const { key, gameId, storage, validateState } = options;
  if (typeof key !== 'string' || !key.trim() || typeof gameId !== 'string' || !gameId.trim()) {
    throw new TypeError('Save key and gameId must be nonempty strings');
  }
  if (!storage || typeof storage.getItem !== 'function' || typeof storage.setItem !== 'function' || typeof storage.removeItem !== 'function') {
    throw new TypeError('Save storage must implement getItem, setItem and removeItem');
  }
  if (typeof validateState !== 'function' || validateState.constructor.name === 'AsyncFunction') {
    throw new TypeError('Save state validator must be a synchronous function');
  }
  const stateCopy = (input: unknown): T => {
    const validated = validateState(cloneJSON(input));
    if (validated && typeof validated === 'object' && typeof (validated as { then?: unknown }).then === 'function') {
      void Promise.resolve(validated).catch(() => {});
      throw new TypeError('Save state validator must return synchronous JSON data');
    }
    return cloneJSON(validated) as T;
  };
  return {
    read() {
      const text = storage.getItem(key);
      if (text === null) return null;
      checkSize(text);
      const record: unknown = JSON.parse(text);
      if (!record || typeof record !== 'object' || Array.isArray(record)) throw new TypeError('Invalid save record');
      const data = record as Record<string, unknown>;
      if (data.version !== 1 || data.gameId !== gameId) throw new TypeError('Save version or gameId does not match');
      if (typeof data.savedAt !== 'string' || !Number.isFinite(Date.parse(data.savedAt))) throw new TypeError('Invalid save timestamp');
      return { version: 1, gameId, savedAt: data.savedAt, scene: validateScene(data.scene), state: stateCopy(data.state) };
    },
    write(scene, state) {
      const record: SaveRecord<T> = {
        version: 1, gameId, savedAt: new Date().toISOString(),
        scene: validateScene(cloneJSON(scene)), state: stateCopy(state),
      };
      const text = JSON.stringify(record);
      checkSize(text);
      storage.setItem(key, text);
    },
    clear: () => storage.removeItem(key),
  };
}
