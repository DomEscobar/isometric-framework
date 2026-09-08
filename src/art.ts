import type { Cell, Point, TileDefinition, VisualDefinition } from './types.ts';

export interface ImageSource {
  /** Resolved against the host document, like legacy sprite URLs. */
  url: string;
  /** Pixel art defaults to nearest-neighbor sampling. */
  sampling?: 'nearest' | 'linear';
}
export interface TextureDefinition {
  image: string;
  /** Integral source-image pixels. Omit to use the entire image. */
  frame?: { x: number; y: number; width: number; height: number };
  /** Normalized origin; sprites default to bottom center. */
  anchor?: Point;
}
export interface AnimationClip {
  /** Ordered named textures, including repeated frames when desired. */
  frames: string[];
  fps?: number;
  loop?: boolean;
}
export interface AssetManifest {
  images: Record<string, ImageSource>;
  textures: Record<string, TextureDefinition>;
  animations?: Record<string, AnimationClip>;
}
/** Screen-space facing, independent of the isometric grid axes. */
export type SpriteDirection = 'n' | 'ne' | 'e' | 'se' | 's' | 'sw' | 'w' | 'nw';
export type SpriteState = 'idle' | 'walk' | 'jump';
export interface SpriteAnimationSet {
  idle?: string;
  walk?: string;
  jump?: string;
  directions?: Partial<Record<SpriteDirection, { idle?: string; walk?: string; jump?: string }>>;
}

function fail(path: string, message: string): never {
  throw new TypeError(`Invalid assets: ${path} ${message}`);
}
function record(value: unknown, path: string): Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) fail(path, 'must be an object');
  return value as Record<string, unknown>;
}
function string(value: unknown, path: string, max = 256): string {
  if (typeof value !== 'string' || !value.length || value.length > max) fail(path, `must be a nonempty string of at most ${max} characters`);
  return value;
}
function number(value: unknown, path: string, min: number, max: number, integer = false): void {
  if (typeof value !== 'number' || !Number.isFinite(value) || value < min || value > max || (integer && !Number.isInteger(value))) {
    fail(path, `must be ${integer ? 'an integer' : 'a number'} between ${min} and ${max}`);
  }
}

/** Clone only JSON values without invoking accessors or serialization hooks. */
function cloneJSON(input: unknown): unknown {
  const ancestors = new Set<object>();
  let count = 0;
  function copy(value: unknown, path: string, depth: number): unknown {
    if (++count > 200_000 || depth > 64) fail(path, 'exceeds the data size or nesting limit');
    if (value === null || typeof value === 'boolean' || typeof value === 'string') return value;
    if (typeof value === 'number') {
      if (!Number.isFinite(value)) fail(path, 'must be finite');
      return value;
    }
    if (!value || typeof value !== 'object') fail(path, 'must contain only JSON values');
    if (ancestors.has(value)) fail(path, 'contains a cycle');
    const prototype = Object.getPrototypeOf(value);
    if (!Array.isArray(value) && prototype !== Object.prototype && prototype !== null) fail(path, 'must be a plain object');
    if (Object.getOwnPropertySymbols(value).length) fail(path, 'must not have symbol keys');
    if (Array.isArray(value) && value.length > 200_000) fail(path, 'exceeds the data size limit');
    const entries = Object.entries(Object.getOwnPropertyDescriptors(value));
    for (const [key, descriptor] of entries) {
      if (descriptor.get || descriptor.set) fail(`${path}.${key}`, 'must not contain accessors');
    }
    ancestors.add(value);
    const result = Array.isArray(value)
      ? Array.from({ length: value.length }, (_, i) => copy(Object.getOwnPropertyDescriptor(value, String(i))?.value, `${path}[${i}]`, depth + 1))
      : Object.fromEntries(entries.filter(([, descriptor]) => descriptor.enumerable).map(([key, descriptor]) => [key, copy(descriptor.value, `${path}.${key}`, depth + 1)]));
    ancestors.delete(value);
    return result;
  }
  return copy(input, 'assets', 0);
}

/** Validate and detach manifest JSON. Decoded image bounds are checked by the renderer. */
export function validateAssetManifest(input: unknown): AssetManifest {
  const manifest = record(cloneJSON(input), 'assets');
  const images = record(manifest.images, 'images');
  const textures = record(manifest.textures, 'textures');
  const animations = manifest.animations === undefined ? {} : record(manifest.animations, 'animations');
  if (Object.keys(images).length > 1024) fail('images', 'exceeds 1024 definitions');
  if (Object.keys(textures).length > 16384) fail('textures', 'exceeds 16384 definitions');
  if (Object.keys(animations).length > 4096) fail('animations', 'exceeds 4096 definitions');
  for (const [id, value] of Object.entries(images)) {
    string(id, 'image ID');
    const image = record(value, `images.${id}`);
    string(image.url, `images.${id}.url`, 8192);
    if (image.sampling !== undefined && image.sampling !== 'nearest' && image.sampling !== 'linear') fail(`images.${id}.sampling`, 'must be nearest or linear');
  }
  for (const [id, value] of Object.entries(textures)) {
    string(id, 'texture ID');
    const path = `textures.${id}`, texture = record(value, path);
    const image = string(texture.image, `${path}.image`);
    if (!Object.hasOwn(images, image)) fail(`${path}.image`, 'references an unknown image');
    if (texture.frame !== undefined) {
      const frame = record(texture.frame, `${path}.frame`);
      for (const key of ['x', 'y']) number(frame[key], `${path}.frame.${key}`, 0, 65536, true);
      for (const key of ['width', 'height']) number(frame[key], `${path}.frame.${key}`, 1, 16384, true);
    }
    if (texture.anchor !== undefined) {
      const anchor = record(texture.anchor, `${path}.anchor`);
      for (const key of ['x', 'y']) number(anchor[key], `${path}.anchor.${key}`, 0, 1);
    }
  }
  for (const [id, value] of Object.entries(animations)) {
    string(id, 'animation ID');
    const path = `animations.${id}`, animation = record(value, path);
    if (!Array.isArray(animation.frames) || !animation.frames.length || animation.frames.length > 1024) fail(`${path}.frames`, 'must contain 1 to 1024 texture IDs');
    animation.frames.forEach((value, i) => {
      const texture = string(value, `${path}.frames[${i}]`);
      if (!Object.hasOwn(textures, texture)) fail(`${path}.frames[${i}]`, 'references an unknown texture');
    });
    if (animation.fps !== undefined) number(animation.fps, `${path}.fps`, 0.1, 120);
    if (animation.loop !== undefined && typeof animation.loop !== 'boolean') fail(`${path}.loop`, 'must be a boolean');
  }
  return manifest as unknown as AssetManifest;
}

/** Stable variant selection by integer cell and floor identity; consumes no random state. */
export function selectTileTexture(tile: TileDefinition, cell: Cell): string | undefined {
  if (tile.texture !== undefined) return tile.texture;
  if (!tile.textures?.length) return undefined;
  const key = JSON.stringify([cell.c, cell.r, cell.level ?? 'ground']);
  let hash = 2166136261;
  for (let i = 0; i < key.length; i++) hash = Math.imul(hash ^ key.charCodeAt(i), 16777619) >>> 0;
  return tile.textures[hash % tile.textures.length];
}

/** Specific state, general state, specific idle, general idle, then the base clip. */
export function resolveAnimation(visual: VisualDefinition, state: SpriteState, direction: SpriteDirection): string | undefined {
  const set = visual.animations;
  const directional = set?.directions && Object.hasOwn(set.directions, direction) ? set.directions[direction] : undefined;
  return directional?.[state] ?? set?.[state] ?? directional?.idle ?? set?.idle ?? visual.animation;
}
