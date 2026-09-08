import type { AssetManifest, SpriteAnimationSet } from './art.ts';
export type { AssetManifest, ImageSource, TextureDefinition, AnimationClip, SpriteDirection, SpriteState, SpriteAnimationSet } from './art.ts';

/** Grid coordinates preserve Traviso's original orientation. */
export interface Cell { c: number; r: number; /** Omitted means the base ground floor. */ level?: string }
export interface Point { x: number; y: number }
export interface TileDefinition {
  color: number;
  walkable?: boolean;
  /** Elevation in screen pixels. */
  elevation?: number;
  /** Named top-face texture; mutually exclusive with textures. */
  texture?: string;
  /** Deterministic top-face variants selected by cell and floor. */
  textures?: string[];
  /** Named material repeated on vertical terrain faces; omitted keeps solid shading. */
  sideTexture?: string;
}
export interface VisualDefinition {
  kind: 'box' | 'actor' | 'gem' | 'sprite';
  color?: number;
  /** Height of the built-in box visual, in screen pixels. */
  height?: number;
  /** URLs resolve against the document; use absolute URLs when embedding elsewhere. */
  url?: string;
  /** A sequence of image URLs, not a sprite-sheet descriptor. */
  frames?: string[];
  /** Named manifest texture or animation; use exactly one sprite source. */
  texture?: string;
  animation?: string;
  animations?: SpriteAnimationSet;
  /** Normalized origin, overriding the texture anchor. Default bottom center. */
  anchor?: Point;
  /** Display width in pixels before scale, preserving the image aspect ratio. */
  width?: number;
  tint?: number;
  /** Presentation offset in pixels; does not move the physical body. */
  offset?: Point;
  /** Frames per second. */
  fps?: number;
  scale?: number;
}
export interface EntityType {
  visual: VisualDefinition;
  blocking?: boolean;
  /** Rectangular footprint extending in positive column/row directions. */
  columns?: number;
  rows?: number;
  /** Absolute physical height in pixels, independent of art width and scale. */
  bodyHeight?: number;
}
export interface EntityDefinition extends Cell {
  id: string;
  type: string;
  data?: Record<string, unknown>;
}
export interface LevelDefinition {
  id: string;
  name: string;
  /** Floor height in pixels, added to tile elevation. */
  height: number;
  /** Same dimensions as the ground map; null denotes an absent floor. */
  map: (string | null)[][];
}
export interface LevelLink {
  /** Stair endpoints must be cardinally adjacent cells on different floors. */
  from: Cell;
  to: Cell;
  bidirectional?: boolean;
}
export interface Scene {
  version: 1 | 2;
  name: string;
  tileWidth: number;
  tileHeight: number;
  assets?: AssetManifest;
  /** Row-major tile type IDs. */
  map: string[][];
  tiles: Record<string, TileDefinition>;
  entityTypes: Record<string, EntityType>;
  entities: EntityDefinition[];
  controlledId?: string;
  diagonal?: boolean;
  /** Largest traversable difference between tile elevations, in pixels. Default 0. */
  maxStepHeight?: number;
  /** Version 2 stacked floors. The base map always has ID 'ground', height 0. */
  levels?: LevelDefinition[];
  /** The only traversable connections between separate floors. */
  links?: LevelLink[];
}
export type MoveResult = 'started' | 'arrived' | 'blocked' | 'missing' | 'paused';
export type JumpResult = 'started' | 'airborne' | 'blocked' | 'missing' | 'paused';
export interface EntityPose { position: Cell; elevation: number; airborne: boolean }
export interface SpriteDebugState {
  state: import('./art.ts').SpriteState;
  facing: import('./art.ts').SpriteDirection;
  clip: string | null;
  override: string | null;
  frame: number;
  texture: string | null;
  anchor: Point;
  offset: Point;
  width: number;
  height: number;
}
/** Detached authoring diagnostics; changes to this data never mutate the scene. */
export interface DebugSnapshot {
  sceneName: string;
  tileWidth: number;
  tileHeight: number;
  camera: Camera;
  viewLevel: string | null;
  controlledId: string | null;
  tiles: { cell: Cell; elevation: number }[];
  tilesTruncated: boolean;
  entities: {
    id: string; type: string; cell: Cell; pose: EntityPose;
    elevation: number; columns: number; rows: number; bodyHeight: number;
    blocking: boolean; visible: boolean; route: Cell[];
    sprite: SpriteDebugState | null;
  }[];
}
export interface JumpOptions {
  /** Maximum feet rise above takeoff. Default84px; same/lower-floor hops are capped at40px. */
  height?: number;
  duration?: number;
  distance?: number;
}
export interface ProjectileOptions {
  from: Cell;
  to: Cell;
  /** Grid tiles per second. */
  speed: number;
  /** Absolute height above the ground plane, in pixels. */
  elevation: number;
  radius?: number;
  color?: number;
  /** Defaults to the controlled entity at spawn time. */
  targetId?: string;
}
export interface RuntimeEvents {
  tileclick: { cell: Cell; entityIds: string[] };
  hover: { cell: Cell | null };
  move: { id: string; position: Cell; elevation: number };
  arrive: { id: string; cell: Cell };
  blocked: { id: string; target: Cell };
  jumpstart: { id: string; from: Cell; to: Cell };
  land: { id: string; cell: Cell };
  projectilehit: { projectileId: string; entityId: string; position: Cell; elevation: number };
  frame: { deltaSeconds: number };
  scenechange: { name: string };
  pausechange: { paused: boolean };
  inputreset: Record<string, never>;
  /** Explicit motion intent; host controllers may cancel their current action. */
  command: { id: string; kind: 'move' | 'input' | 'jump' | 'stop' };
  camerachange: { camera: Camera };
  viewchange: { level: string | null };
  /** Emitted before disposal; listeners should release owned subscriptions/resources. */
  destroy: Record<string, never>;
  error: { error: Error };
}
export interface Camera { x: number; y: number; zoom: number }
export interface RuntimeOptions {
  container: HTMLElement;
  scene: Scene;
  /** Tile units per second. Default 3. */
  speed?: number;
  /** Maximum feet rise in pixels (84), flight seconds (0.8), and maximum grid steps (2). */
  jump?: JumpOptions;
  /** Enable click movement, dragging and wheel zoom. Default true. */
  input?: boolean;
  /** Keep picking/panning but let the host handle tileclick routing. Default true. */
  clickToMove?: boolean;
  /** WASD/arrow controls, scoped to focus inside the game container. Default true with input. */
  keyboard?: boolean;
  background?: number;
  /** Stop unresponsive asset requests after this many milliseconds. Default 15000. */
  assetTimeoutMs?: number;
  /** False lets the host drive simulation and rendering with step(seconds). */
  autoStart?: boolean;
}
