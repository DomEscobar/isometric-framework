import type { RuntimeEvents } from './types.ts';

/** Owned by one runtime. Subscriptions return their own disposal function. */
export class Events {
  private listeners = new Map<keyof RuntimeEvents, Set<(value: never) => void>>();

  on<K extends keyof RuntimeEvents>(name: K, listener: (value: RuntimeEvents[K]) => void): () => void {
    let group = this.listeners.get(name);
    if (!group) this.listeners.set(name, group = new Set());
    group.add(listener as (value: never) => void);
    return () => { group.delete(listener as (value: never) => void); };
  }

  emit<K extends keyof RuntimeEvents>(name: K, value: RuntimeEvents[K]): void {
    for (const listener of [...(this.listeners.get(name) ?? [])]) {
      // A callback may destroy the runtime and clear all subscriptions.
      if (!this.listeners.get(name)?.has(listener)) continue;
      try { listener(value as never); }
      catch (error) {
        if (name !== 'error') this.emit('error', { error: error instanceof Error ? error : new Error(String(error)) });
      }
    }
  }

  clear(): void { this.listeners.clear(); }
}
