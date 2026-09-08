import { BaseTexture, Rectangle, SCALE_MODES, Texture } from 'pixi.js';
import type { AnimationClip, Scene } from './types.ts';

/** Scene-owned images and frames. Never registers resources in Pixi's global cache. */
export class AssetBank {
  private urls = new Map<string, Texture>();
  private frames = new Map<string, Texture>();
  private bases = new Set<BaseTexture>();
  private owned = new Set<Texture>();
  private animations = new Map<string, AnimationClip>();
  private generation = 0;

  async load(scene: Scene, signal: AbortSignal, timeoutMs: number): Promise<void> {
    const generation = ++this.generation;
    const urls = new Map<string, Texture>();
    const frames = new Map<string, Texture>();
    const bases = new Map<string, BaseTexture>();
    const owned = new Set<Texture>();
    const sources = new Map<string, { url: string; sampling: 'nearest' | 'linear' }>();
    const legacy = new Set<string>();
    const key = (url: string, sampling = 'nearest') => JSON.stringify([url, sampling]);
    for (const type of Object.values(scene.entityTypes)) {
      if (type.visual.url) legacy.add(type.visual.url);
      for (const url of type.visual.frames ?? []) legacy.add(url);
    }
    for (const url of legacy) sources.set(key(url), { url, sampling: 'nearest' });
    for (const source of Object.values(scene.assets?.images ?? {})) {
      const sampling = source.sampling ?? 'nearest';
      sources.set(key(source.url, sampling), { url: source.url, sampling });
    }
    const release = () => {
      for (const texture of owned) texture.destroy(false);
      for (const base of bases.values()) base.destroy();
    };
    try {
      const results = await Promise.allSettled([...sources].map(async ([id, source]) => {
        const image = await this.image(source.url, signal, timeoutMs);
        if (signal.aborted || generation !== this.generation) throw new DOMException('Scene load cancelled', 'AbortError');
        bases.set(id, new BaseTexture(image, {
          scaleMode: source.sampling === 'linear' ? SCALE_MODES.LINEAR : SCALE_MODES.NEAREST,
        }));
      }));
      const failed = results.find((result): result is PromiseRejectedResult => result.status === 'rejected');
      if (failed) throw failed.reason;
      if (signal.aborted || generation !== this.generation) throw new DOMException('Scene load cancelled', 'AbortError');
      for (const url of legacy) {
        const texture = new Texture(bases.get(key(url))!);
        owned.add(texture);
        urls.set(url, texture);
      }
      for (const [id, definition] of Object.entries(scene.assets?.textures ?? {})) {
        const source = scene.assets!.images[definition.image]!;
        const base = bases.get(key(source.url, source.sampling))!;
        const frame = definition.frame;
        if (frame && (frame.x + frame.width > base.width || frame.y + frame.height > base.height)) {
          throw new Error(`Texture "${id}" frame exceeds image "${definition.image}" bounds (${base.width}x${base.height})`);
        }
        const texture = new Texture(base, frame ? new Rectangle(frame.x, frame.y, frame.width, frame.height) : undefined);
        texture.defaultAnchor.set(definition.anchor?.x ?? 0.5, definition.anchor?.y ?? 1);
        owned.add(texture);
        frames.set(id, texture);
      }
    } catch (error) {
      release();
      throw error;
    }
    this.release();
    this.urls = urls;
    this.frames = frames;
    this.bases = new Set(bases.values());
    this.owned = owned;
    this.animations = new Map(Object.entries(scene.assets?.animations ?? {}));
  }

  get(url: string): Texture {
    const texture = this.urls.get(url);
    if (!texture) throw new Error(`Texture not loaded: ${url}`);
    return texture;
  }

  texture(id: string): Texture {
    const texture = this.frames.get(id);
    if (!texture) throw new Error(`Unknown texture: ${id}`);
    return texture;
  }

  animation(id: string): AnimationClip {
    const animation = this.animations.get(id);
    if (!animation) throw new Error(`Unknown animation: ${id}`);
    return animation;
  }

  destroy(): void {
    this.generation++;
    this.release();
  }

  private release(): void {
    // Frames can share a base; destroying a frame must not destroy its siblings.
    for (const texture of this.owned) texture.destroy(false);
    for (const base of this.bases) base.destroy();
    this.owned.clear();
    this.bases.clear();
    this.urls.clear();
    this.frames.clear();
    this.animations.clear();
  }

  private image(url: string, signal: AbortSignal, timeoutMs: number): Promise<HTMLImageElement> {
    return new Promise((resolve, reject) => {
      if (signal.aborted) { reject(new DOMException('Scene load cancelled', 'AbortError')); return; }
      const image = new Image();
      image.crossOrigin = 'anonymous';
      const cleanup = () => {
        clearTimeout(timer);
        image.onload = null;
        image.onerror = null;
        signal.removeEventListener('abort', abort);
      };
      const fail = (error: Error) => { cleanup(); image.src = ''; reject(error); };
      const abort = () => fail(new DOMException('Scene load cancelled', 'AbortError'));
      const timer = setTimeout(() => fail(new Error(`Asset timed out: ${url}`)), timeoutMs);
      image.onload = () => { cleanup(); resolve(image); };
      image.onerror = () => fail(new Error(`Could not load asset: ${url}`));
      signal.addEventListener('abort', abort, { once: true });
      image.src = url;
    });
  }
}
