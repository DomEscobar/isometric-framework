import { Container, Graphics, Matrix } from 'pixi.js';
import { selectTileTexture } from './art.ts';
import { project } from './geometry.ts';
import { levelHeight, levelMaps, levelOf } from './levels.ts';
import { bodyHeight } from './physics.ts';
import { EntitySprite, motionDirection } from './sprites.ts';
import type { AssetBank } from './assets.ts';
import type { Cell, EntityDefinition, EntityType, Scene, SpriteDirection, SpriteState, TileDefinition } from './types.ts';

function shade(color: number, factor: number): number {
  return (Math.round((color >> 16 & 255) * factor) << 16)
    | (Math.round((color >> 8 & 255) * factor) << 8)
    | Math.round((color & 255) * factor);
}

function diamond(g: Graphics, w: number, h: number, y = 0): void {
  g.drawPolygon([-w / 2, y, 0, y - h / 2, w / 2, y, 0, y + h / 2]);
}

interface DepthNode {
  view: Container;
  level: string;
  c0: number; c1: number; r0: number; r1: number; z0: number; z1: number;
  contact: number;
  serial: number;
}

/** Separated world volumes give a partial painter order, not a total 3D order. */
function behind(a: DepthNode, b: DepthNode): boolean {
  const epsilon = 1e-6;
  return a.c0 >= b.c1 - epsilon || a.r1 <= b.r0 + epsilon || a.z1 <= b.z0 + epsilon;
}

/** Scene-owned display tree, independent of DOM input and game rules. */
export class SceneView {
  readonly root = new Container();
  private depths = new Map<Container, DepthNode>();
  private serial = 0;
  private viewLevel: string | null = null;
  private overlay = new Graphics();
  private views = new Map<string, Container>();
  private placements = new Map<string, { cell: Cell; elevation?: number; drawLevel: string }>();
  private types = new Map<string, EntityType>();
  private sprites = new Map<string, EntitySprite>();
  private projectiles = new Map<string, Graphics>();

  constructor(private scene: Scene, private bank: AssetBank) {
    try {
      this.root.sortableChildren = true;
      // Floors share one painter domain. A floor-height container would force
      // every upper tile over even a tall actor standing in front of its edge.
      this.root.sortChildren = () => this.sortDepth();
      this.root.addChild(this.overlay);
      for (const level of levelMaps(scene)) {
        for (let r = 0; r < level.map.length; r++) {
          for (let c = 0; c < level.map[r]!.length; c++) {
            const type = level.map[r]![c];
            if (type === null) continue;
            const tile = scene.tiles[type!]!;
            this.drawTile({ c, r, level: level.id }, tile);
          }
        }
      }
      // Ground and entities share a sort domain so a raised foreground tile can
      // occlude a lower actor. Markers sort with their supporting tile, below actors.
      for (const entity of scene.entities) this.add(entity);
    } catch (error) {
      // A throwing constructor cannot be assigned to Runtime's staged view.
      this.destroy();
      throw error;
    }
  }

  private register(view: Container, cell: Cell, bottom: number, top: number, contact: number,
    columns = 1, rows = 1, drawLevel = levelOf(cell)): void {
    const serial = this.depths.get(view)?.serial ?? this.serial++;
    this.depths.set(view, { view, level: drawLevel, c0: cell.c - 0.5, c1: cell.c + columns - 0.5,
      r0: cell.r - 0.5, r1: cell.r + rows - 0.5, z0: bottom, z1: top, contact, serial });
    view.visible = this.viewLevel === null || levelHeight(this.scene, drawLevel) <= levelHeight(this.scene, this.viewLevel);
    this.root.sortDirty = true;
  }

  private sortDepth(): void {
    const nodes = [...this.depths.values()].filter(node => node.view.visible)
      .sort((a, b) => a.contact - b.contact || a.serial - b.serial);
    const bounds = nodes.map(({ view }) => {
      const local = view.getLocalBounds();
      return { x0: view.x + local.x * view.scale.x, x1: view.x + (local.x + local.width) * view.scale.x,
        y0: view.y + local.y * view.scale.y, y1: view.y + (local.y + local.height) * view.scale.y };
    });
    const edges = nodes.map(() => [] as number[]), incoming = nodes.map(() => 0);
    for (let a = 0; a < nodes.length; a++) for (let b = a + 1; b < nodes.length; b++) {
      const x = bounds[a]!, y = bounds[b]!;
      if (x.x1 <= y.x0 || y.x1 <= x.x0 || x.y1 <= y.y0 || y.y1 <= x.y0) continue;
      const ab = behind(nodes[a]!, nodes[b]!), ba = behind(nodes[b]!, nodes[a]!);
      // Conflicting separating axes indicate ambiguous sprite overhang, not a
      // reason to invent another physical volume. Keep the contact tie-break.
      if (ab === ba) continue;
      const from = ab ? a : b, to = ab ? b : a;
      edges[from]!.push(to); incoming[to]!++;
    }
    const remaining = new Set(nodes.map((_, index) => index));
    let rank = 0;
    while (remaining.size) {
      // Nodes start in legacy contact order, including the footprint tie bias.
      // Cycles can occur with unsplit intersecting art: break deterministically.
      let next: number | undefined;
      for (const index of remaining) if (incoming[index] === 0) { next = index; break; }
      next ??= remaining.values().next().value!;
      remaining.delete(next);
      nodes[next]!.view.zIndex = rank++;
      for (const target of edges[next]!) incoming[target]!--;
    }
    this.root.children.sort((a, b) => a.zIndex - b.zIndex);
    this.root.sortDirty = false;
  }

  private drawTile(cell: Cell, tile: TileDefinition): void {
    const { tileWidth: w, tileHeight: h } = this.scene;
    const container = new Container();
    this.root.addChild(container);
    const g = new Graphics();
    container.addChild(g);
    const baseHeight = levelHeight(this.scene, levelOf(cell));
    const lift = baseHeight + (tile.elevation ?? 0);
    // Additional floors are slabs, leaving an actual open passage underneath.
    const depth = Math.max(1, 8 + (tile.elevation ?? 0));
    const side = tile.sideTexture === undefined ? undefined : this.bank.texture(tile.sideTexture);
    for (const [left, factor] of [[true, 0.68], [false, 0.82]] as const) {
      const x = left ? -w / 2 : 0, y = left ? 0 : h / 2, slope = left ? h / 2 : -h / 2;
      // Vertical material pixels remain world pixels. Repeat framed textures in
      // separate strips so a tall side cannot sample the next atlas region.
      const repeat = side?.height ?? depth;
      for (let offset = 0; offset < depth; offset += repeat) {
        const bottom = Math.min(offset + repeat, depth);
        if (side) g.beginTextureFill({ texture: side, color: shade(0xffffff, factor),
          matrix: new Matrix(w / (2 * side.width), slope / side.width, 0, 1, x, y + offset) });
        else g.beginFill(shade(tile.color, factor));
        g.drawPolygon([x, y + offset, x + w / 2, y + slope + offset,
          x + w / 2, y + slope + bottom, x, y + bottom]);
        g.endFill();
      }
    }
    const texture = selectTileTexture(tile, cell);
    // Textured terrain owns its edge colors. A base stroke would expose a
    // procedural grid between otherwise continuous grass or water materials.
    g.lineStyle(texture === undefined ? 1 : 0, shade(tile.color, 0.9), 0.75);
    g.beginFill(tile.color);
    diamond(g, w, h);
    g.endFill();
    if (texture !== undefined) {
      const frame = this.bank.texture(texture);
      // Draw the cropped diamond directly instead of a rectangular sprite with
      // a stencil mask. Hundreds of masks force GPU state changes per frame.
      // AssetBank frames are unrotated/untrimmed; Graphics maps their atlas UVs.
      g.lineStyle(0);
      g.beginTextureFill({ texture: frame,
        matrix: new Matrix(w / frame.width, 0, 0, h / frame.height, -w / 2, -h / 2) });
      diamond(g, w, h);
      g.endFill();
    }
    const p = project(cell, w, h, lift);
    container.position.set(p.x, p.y);
    // Sort terrain at its back edge, not its center. Otherwise a flat tile
    // ahead of an interpolating actor paints over that actor's lower body.
    this.register(container, cell, lift - depth, lift, (cell.r - cell.c - 1) * h / 2 + 0.2);
  }

  add(entity: EntityDefinition): void {
    const type = this.scene.entityTypes[entity.type]!;
    const view = this.createVisual(entity.id, type);
    this.views.set(entity.id, view);
    this.types.set(entity.id, type);
    this.root.addChild(view);
    this.position(entity.id, entity);
  }

  private createVisual(id: string, type: EntityType): Container {
    const { visual } = type;
    const container = new Container();
    const w = this.scene.tileWidth;
    if (visual.kind === 'sprite') {
      const presentation = new EntitySprite(visual, this.bank);
      this.sprites.set(id, presentation);
      container.addChild(presentation.sprite);
      return container;
    }
    const g = new Graphics();
    const color = visual.color ?? 0x687950;
    g.beginFill(0x17282a, 0.14).drawEllipse(0, 1, w * 0.24, w * 0.1).endFill();
    if (visual.kind === 'actor') {
      g.beginFill(shade(color, 0.68)).drawRoundedRect(-10, -16, 8, 15, 3).drawRoundedRect(2, -16, 8, 15, 3).endFill();
      g.beginFill(color).drawRoundedRect(-13, -35, 26, 24, 7).endFill();
      g.beginFill(0xffdeb8).drawRoundedRect(-10, -53, 20, 22, 7).endFill();
      g.beginFill(0x3c302d).drawRoundedRect(-11, -55, 22, 9, 3).endFill();
      g.beginFill(0x33312e).drawRect(3, -43, 3, 3).endFill();
      g.beginFill(0xffffff, 0.3).drawRoundedRect(-9, -31, 5, 13, 2).endFill();
    } else if (visual.kind === 'gem') {
      g.beginFill(color).drawPolygon([0, -33, 12, -19, 0, -6, -12, -19]).endFill();
      g.beginFill(0xffffff, 0.48).drawPolygon([0, -33, 0, -6, -12, -19]).endFill();
    } else {
      const height = visual.height ?? 32;
      const halfW = w * 0.32;
      const halfH = this.scene.tileHeight * 0.32;
      g.beginFill(shade(color, 0.75)).drawPolygon([-halfW, -height, 0, -height + halfH, 0, halfH, -halfW, 0]).endFill();
      g.beginFill(shade(color, 0.9)).drawPolygon([0, -height + halfH, halfW, -height, halfW, 0, 0, halfH]).endFill();
      g.beginFill(color);
      diamond(g, halfW * 2, halfH * 2, -height);
      g.endFill();
    }
    container.addChild(g);
    container.scale.set(visual.scale ?? 1);
    return container;
  }

  position(id: string, cell: Cell, elevation?: number, drawLevel = levelOf(cell), updateFacing = true): void {
    const view = this.views.get(id);
    if (!view) return;
    const previous = this.placements.get(id);
    if (previous && updateFacing) {
      const direction = motionDirection(previous.cell, cell);
      if (direction) this.sprites.get(id)?.setDirection(direction);
    }
    // Preserve interpolation and its preferred visibility floor so paused
    // cutaway changes do not move the actor or advance simulation.
    this.placements.set(id, { cell: { ...cell }, elevation, drawLevel });
    const type = this.types.get(id);
    const level = levelMaps(this.scene).find(level => level.id === levelOf(cell))!;
    const floor = this.scene.tiles[level.map[Math.round(cell.r)]?.[Math.round(cell.c)] ?? ''];
    const feet = elevation ?? level.height + (floor?.elevation ?? 0);
    const p = project(cell, this.scene.tileWidth, this.scene.tileHeight, feet);
    if (this.viewLevel !== null && levelHeight(this.scene, drawLevel) > levelHeight(this.scene, this.viewLevel)) drawLevel = levelOf(cell);
    view.position.set(p.x, p.y);
    // Front-most ground contact provides a stable fallback to volume ordering.
    // At equal contact depth, compact footprints draw in front of larger ones.
    // Otherwise Pixi's stable ties retain the actor's previous approach order.
    // The bias stays below .01, inside the terrain/entity/projectile offsets.
    // This remains the stable fallback for ambiguous intersecting artwork.
    const span = (type?.rows ?? 1) + (type?.columns ?? 1) - 1;
    const footprintBias = 0.01 * (1 - 1 / span);
    this.register(view, cell, feet, feet + bodyHeight(type!),
      (cell.r - cell.c + (type?.rows ?? 1) - 1) * this.scene.tileHeight / 2 + 0.1 - footprintBias,
      type?.columns ?? 1, type?.rows ?? 1, drawLevel);
  }

  remove(id: string): void {
    const view = this.views.get(id);
    if (!view) return;
    this.sprites.delete(id);
    this.depths.delete(view);
    view.destroy({ children: true, texture: false, baseTexture: false });
    this.views.delete(id);
    this.placements.delete(id);
    this.types.delete(id);
  }

  setMotion(id: string, state: SpriteState): void {
    this.sprites.get(id)?.setMotion(state);
    this.root.sortDirty = true;
  }

  setAnimation(id: string, clip: string | null): boolean {
    if (!this.views.has(id)) return false;
    if (clip !== null) this.bank.animation(clip);
    this.root.sortDirty = true;
    return this.sprites.get(id)?.setAnimation(clip) ?? false;
  }

  setFacing(id: string, direction: SpriteDirection): boolean {
    const sprite = this.sprites.get(id);
    if (!sprite) return false;
    sprite.setDirection(direction);
    this.root.sortDirty = true;
    return true;
  }

  inspectSprite(id: string) { return this.sprites.get(id)?.inspect() ?? null; }

  projectile(id: string, cell: Cell, elevation: number, radius: number, color: number): void {
    let graphic = this.projectiles.get(id);
    if (!graphic) {
      graphic = new Graphics();
      graphic.beginFill(color, 0.18).drawCircle(0, 0, radius * 1.8).endFill();
      graphic.beginFill(color).drawCircle(0, 0, radius).endFill();
      graphic.beginFill(0xffffff, 0.8).drawCircle(-radius * 0.25, -radius * 0.25, radius * 0.3).endFill();
      this.projectiles.set(id, graphic);
    }
    const floor = levelMaps(this.scene).filter(level => level.height <= elevation).sort((a, b) => b.height - a.height)[0] ?? levelMaps(this.scene)[0]!;
    if (graphic.parent !== this.root) this.root.addChild(graphic);
    const point = project(cell, this.scene.tileWidth, this.scene.tileHeight, elevation);
    graphic.position.set(point.x, point.y);
    this.register(graphic, cell, elevation - radius, elevation + radius,
      (cell.r - cell.c) * this.scene.tileHeight / 2 + 0.15, 1, 1, floor.id);
  }

  removeProjectile(id: string): void {
    const graphic = this.projectiles.get(id);
    if (graphic) { this.depths.delete(graphic); graphic.destroy(); }
    this.projectiles.delete(id);
  }

  highlight(cell: Cell | null, blocked = false): void {
    this.overlay.clear();
    this.depths.delete(this.overlay);
    if (!cell) return;
    const level = levelMaps(this.scene).find(level => level.id === levelOf(cell))!;
    const tile = this.scene.tiles[level.map[cell.r]?.[cell.c] ?? ''];
    const p = project(cell, this.scene.tileWidth, this.scene.tileHeight, level.height + (tile?.elevation ?? 0));
    this.overlay.position.set(p.x, p.y);
    const feet = level.height + (tile?.elevation ?? 0);
    this.register(this.overlay, cell, feet, feet, (cell.r - cell.c - 1) * this.scene.tileHeight / 2 + 0.3);
    this.overlay.lineStyle(2, blocked ? 0xc15344 : 0xffffff, 0.95);
    this.overlay.beginFill(blocked ? 0xc15344 : 0xffffff, 0.2);
    diamond(this.overlay, this.scene.tileWidth - 4, this.scene.tileHeight - 3);
    this.overlay.endFill();
  }

  setViewLevel(id: string | null): void {
    this.viewLevel = id;
    const limit = id === null ? Infinity : levelHeight(this.scene, id);
    for (const node of this.depths.values()) node.view.visible = levelHeight(this.scene, node.level) <= limit;
    for (const [entityId, placement] of this.placements) {
      this.position(entityId, placement.cell, placement.elevation, placement.drawLevel);
    }
    this.overlay.clear();
    this.depths.delete(this.overlay);
    this.root.sortDirty = true;
  }

  update(deltaSeconds: number): void {
    for (const sprite of this.sprites.values()) sprite.update(deltaSeconds);
    if (this.sprites.size) this.root.sortDirty = true;
  }

  destroy(): void {
    this.sprites.clear();
    this.views.clear();
    this.placements.clear();
    this.types.clear();
    this.depths.clear();
    this.projectiles.clear();
    this.root.destroy({ children: true, texture: false, baseTexture: false });
  }
}
