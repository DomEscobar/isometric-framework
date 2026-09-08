import { AnimatedSprite, Sprite } from 'pixi.js';
import { resolveAnimation } from './art.ts';
import type { AssetBank } from './assets.ts';
import type { Cell, SpriteDebugState, SpriteDirection, SpriteState, VisualDefinition } from './types.ts';

/** Facing follows the isometric axes, ignoring vertical lift and art dimensions. */
export function motionDirection(from: Cell, to: Cell): SpriteDirection | undefined {
  const dc = to.c - from.c, dr = to.r - from.r;
  if (Math.abs(dc) + Math.abs(dr) < 1e-8) return undefined;
  const octant = Math.round(Math.atan2(dr - dc, dc + dr) / (Math.PI / 4));
  return (['e', 'se', 's', 'sw', 'w', 'nw', 'n', 'ne'] as const)[(octant + 8) % 8];
}

/** Entity art presentation. Simulation supplies motion; only elapsed seconds advance frames. */
export class EntitySprite {
  readonly sprite: Sprite;
  private state: SpriteState = 'idle';
  private direction: SpriteDirection = 'se';
  private override: string | null = null;
  private selected: string | undefined;
  private readonly named: boolean;

  constructor(private readonly visual: VisualDefinition, private readonly bank: AssetBank) {
    this.named = visual.texture !== undefined || visual.animation !== undefined;
    if (this.named) {
      const clip = resolveAnimation(visual, this.state, this.direction);
      const textures = clip ? bank.animation(clip).frames.map(id => bank.texture(id)) : [bank.texture(visual.texture!)];
      this.sprite = new AnimatedSprite(textures, false);
      this.selected = clip;
      this.configureClip(clip);
    } else if (visual.frames?.length) {
      const animation = new AnimatedSprite(visual.frames.map(url => bank.get(url)), false);
      animation.animationSpeed = (visual.fps ?? 8) / 60;
      animation.play();
      this.sprite = animation;
    } else {
      this.sprite = new Sprite(bank.get(visual.url!));
    }
    if (this.sprite instanceof AnimatedSprite) this.sprite.onFrameChange = () => this.applyFrame();
    this.sprite.tint = visual.tint ?? 0xffffff;
    this.sprite.position.set(visual.offset?.x ?? 0, visual.offset?.y ?? 0);
    this.applyFrame();
  }

  setMotion(state: SpriteState): void {
    if (this.state === state) return;
    this.state = state;
    this.select();
  }

  setDirection(direction: SpriteDirection): void {
    if (this.direction === direction) return;
    this.direction = direction;
    this.select();
  }

  setAnimation(clip: string | null): boolean {
    // Validate before changing the current override, including for legacy sprites.
    if (clip !== null) this.bank.animation(clip);
    if (!this.named) return false;
    this.override = clip;
    this.select(clip !== null);
    return true;
  }

  update(deltaSeconds: number): void {
    if (this.sprite instanceof AnimatedSprite) this.sprite.update(deltaSeconds * 60);
  }

  inspect(): SpriteDebugState {
    const frame = this.sprite instanceof AnimatedSprite ? this.sprite.currentFrame : 0;
    return {
      state: this.state, facing: this.direction, clip: this.selected ?? null,
      override: this.override, frame,
      texture: this.selected ? this.bank.animation(this.selected).frames[frame] ?? null : this.visual.texture ?? null,
      anchor: { x: this.sprite.anchor.x, y: this.sprite.anchor.y },
      offset: { x: this.sprite.position.x, y: this.sprite.position.y },
      width: this.sprite.width, height: this.sprite.height,
    };
  }

  private select(restart = false): void {
    if (!this.named) return;
    const clip = this.override ?? resolveAnimation(this.visual, this.state, this.direction);
    if (clip === this.selected && !restart) return;
    const animation = this.sprite as AnimatedSprite;
    animation.textures = clip
      ? this.bank.animation(clip).frames.map(id => this.bank.texture(id))
      : [this.bank.texture(this.visual.texture!)];
    this.selected = clip;
    this.configureClip(clip);
    this.applyFrame();
  }

  private configureClip(clip: string | undefined): void {
    const animation = this.sprite as AnimatedSprite;
    if (clip === undefined) { animation.gotoAndStop(0); return; }
    const definition = this.bank.animation(clip);
    animation.animationSpeed = (definition.fps ?? 8) / 60;
    animation.loop = definition.loop ?? true;
    animation.gotoAndPlay(0);
  }

  private applyFrame(): void {
    const anchor = this.visual.anchor ?? (this.named ? this.sprite.texture.defaultAnchor : { x: 0.5, y: 1 });
    this.sprite.anchor.set(anchor.x, anchor.y);
    const widthScale = this.visual.width === undefined ? 1 : this.visual.width / this.sprite.texture.orig.width;
    this.sprite.scale.set(widthScale * (this.visual.scale ?? 1));
  }
}
