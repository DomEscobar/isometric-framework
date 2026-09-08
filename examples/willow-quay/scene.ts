import { resolveAutotiles, type Cell, type Scene, type EntityType, type TextureDefinition } from '../../src/index';
import ground from './art/ground-tiles.json';
import groundUrl from './art/ground-atlas.png?url';
import beds from '../autotile-lab/art/tileset.json';
import bedsUrl from '../autotile-lab/art/bed-atlas.png?url';
import houseUrl from './art/apothecary-source.png?url';
import willowUrl from './art/willow-source.png?url';
import bookUrl from './art/bookbinder-cutout.png?url';
import gardenerUrl from '../../demo/art/pixel-cafe/gardener-atlas.png?url';
import flowersUrl from '../../demo/art/pixel-cafe/flowers-v2.png?url';
import gardenUrl from '../../demo/art/pixel-cafe/garden-atlas.png?url';
import riverUrl from '../environment-lab/art/generated/river-source.png?url';

export const QUAY_SIZE = 14;

/** A complete host-owned district. Generated source pixels and scene geometry stay separate. */
export function createQuayScene(): Scene {
  const textures: Record<string, TextureDefinition> = { ...structuredClone(ground.textures), ...structuredClone(beds.textures) };
  // The ground catalog owns 'grass'; the raised-bed catalog supplies only beds.
  textures.grass = structuredClone(ground.textures.grass);
  const animations: NonNullable<NonNullable<Scene['assets']>['animations']> = {};
  const actorRows = [25, 328, 635, 939], actorColumns = [82, 395, 710, 1025], contacts = [261, 261, 260, 258];
  for (const [row, direction] of ['ne', 'se', 'sw', 'nw'].entries()) {
    for (let i = 0; i < 4; i++) textures[`actor-${direction}-${i}`] = { image: 'actor', frame: { x: actorColumns[i]!, y: actorRows[row]!, width: 160, height: 280 }, anchor: { x: .52, y: contacts[row]! / 280 } };
    animations[`idle-${direction}`] = { frames: [`actor-${direction}-0`], fps: 1, loop: true };
    animations[`walk-${direction}`] = { frames: [1, 0, 2, 0].map(i => `actor-${direction}-${i}`), fps: 8, loop: true };
    animations[`jump-${direction}`] = { frames: [`actor-${direction}-3`], fps: 1, loop: false };
  }
  const facing = (d: string) => ({ idle: `idle-${d}`, walk: `walk-${d}`, jump: `jump-${d}` });
  for (const [i, id] of ['lavender', 'marigold', 'daisy'].entries()) textures[id] = { image: 'flowers', frame: { x: 12 + i * 591, y: 160, width: 576, height: 584 }, anchor: { x: .5, y: 480 / 584 } };
  textures.lantern = { image: 'garden', frame: { x: 742, y: 635, width: 110, height: 337 }, anchor: { x: 44 / 110, y: 313 / 337 } };
  textures.shrub = { image: 'garden', frame: { x: 993, y: 357, width: 223, height: 277 }, anchor: { x: .5, y: .93 } };
  textures.pot = { image: 'garden', frame: { x: 977, y: 59, width: 236, height: 277 }, anchor: { x: .5, y: .92 } };
  textures.apothecary = { image: 'apothecary', frame: { x: 0, y: 0, width: 1254, height: 1254 }, anchor: { x: 626 / 1254, y: 970 / 1254 } };
  textures.willow = { image: 'willow', frame: { x: 0, y: 0, width: 1254, height: 1254 }, anchor: { x: 662 / 1254, y: 1174 / 1254 } };
  textures.bookbinder = { image: 'bookbinder', frame: { x: 0, y: 0, width: 1254, height: 1254 }, anchor: { x: 626 / 1254, y: 970 / 1254 } };
  textures.invisible = { image: 'apothecary', frame: { x: 0, y: 0, width: 1, height: 1 }, anchor: { x: 0, y: 0 } };
  const riverOrigins = [[15, 225], [638, 225], [15, 768], [638, 768]];
  for (let i = 0; i < 4; i++) textures[`water-${i}`] = { image: 'river', frame: { x: riverOrigins[i]![0]!, y: riverOrigins[i]![1]!, width: 600, height: 330 }, anchor: { x: .5, y: .5 } };
  animations.water = { frames: [0, 1, 2, 3].map(i => `water-${i}`), fps: 3, loop: true };
  const prop = (texture: string, width: number, bodyHeight: number, blocking = true): EntityType => ({ blocking, bodyHeight, visual: { kind: 'sprite', texture, width } });
  const scene: Scene = {
    version: 2, name: 'Weidenkai', tileWidth: 64, tileHeight: 32,
    controlledId: 'traveler', diagonal: false, maxStepHeight: 16,
    assets: { images: {
      ground: { url: groundUrl, sampling: 'nearest' }, beds: { url: bedsUrl, sampling: 'nearest' },
      apothecary: { url: houseUrl, sampling: 'nearest' }, actor: { url: gardenerUrl, sampling: 'nearest' },
      willow: { url: willowUrl, sampling: 'nearest' },
      bookbinder: { url: bookUrl, sampling: 'nearest' },
      flowers: { url: flowersUrl, sampling: 'nearest' }, garden: { url: gardenUrl, sampling: 'nearest' }, river: { url: riverUrl, sampling: 'nearest' },
    }, textures, animations },
    map: Array.from({ length: QUAY_SIZE }, (_, r) => Array<string>(QUAY_SIZE).fill(r === 7 || r === 8 ? 'water' : 'grass')),
    tiles: { grass: { color: 0x64794b, texture: 'grass' }, water: { color: 0x287b7d, walkable: false },
      paving: { color: 0xb6a581, texture: 'paved' }, stair: { color: 0xb6a581, texture: 'paved', elevation: 16 }, deck: { color: 0xb6a581, texture: 'paved' },
      abutment: { color: 0xb6a581, texture: 'paved', walkable: false, elevation: 24 } },
    levels: [{ id: 'bridge', name: 'Steinbrücke', height: 32, map: Array.from({ length: QUAY_SIZE }, (_, r) => Array.from({ length: QUAY_SIZE }, (_, c) => c >= 6 && c <= 8 && r >= 6 && r <= 9 ? 'deck' : null)) }],
    links: [{ from: { c: 7, r: 5 }, to: { c: 7, r: 6, level: 'bridge' }, bidirectional: true }, { from: { c: 7, r: 9, level: 'bridge' }, to: { c: 7, r: 10 }, bidirectional: true }],
    entityTypes: {
      traveler: { blocking: true, bodyHeight: 44, visual: { kind: 'sprite', texture: 'actor-se-0', width: 28.4, animations: { ...facing('se'), directions: { ne: facing('ne'), se: facing('se'), sw: facing('sw'), nw: facing('nw'), n: facing('ne'), e: facing('se'), s: facing('sw'), w: facing('nw') } } } },
      apothecary: { blocking: true, columns: 3, rows: 3, bodyHeight: 252, visual: { kind: 'sprite', texture: 'apothecary', width: 1254 * 192 / 878, offset: { x: 64, y: 0 } } },
      bookbinder: { blocking: true, columns: 3, rows: 3, bodyHeight: 252, visual: { kind: 'sprite', texture: 'bookbinder', width: 1254 * 192 / 870, offset: { x: 64, y: 0 } } },
      lantern: prop('lantern', 22, 63), shrub: prop('shrub', 39, 43), pot: prop('pot', 27, 28),
      willow: prop('willow', 230, 211),
      // Flat overlays still need a declared depth volume; sprite defaults are32px tall.
      water: { blocking: false, bodyHeight: 1, visual: { kind: 'sprite', animation: 'water', width: 65.084746, tint: 0x8ba997 } },
      railBlock: { blocking: true, bodyHeight: 24, visual: { kind: 'sprite', texture: 'invisible' } },
      railNear: { blocking: false, bodyHeight: 24, visual: { kind: 'sprite', texture: 'parapet-left' } },
      railFar: { blocking: false, bodyHeight: 24, visual: { kind: 'sprite', texture: 'parapet-right' } },
      bankFar: { blocking: false, bodyHeight: 16, visual: { kind: 'sprite', texture: 'quay-wall' } },
      bankNear: { blocking: false, bodyHeight: 16, visual: { kind: 'sprite', texture: 'quay-wall' } },
    },
    entities: [{ id: 'traveler', type: 'traveler', c: 4, r: 6 }, { id: 'apothecary', type: 'apothecary', c: 3, r: 2 }, { id: 'bookbinder', type: 'bookbinder', c: 9, r: 2 }, { id: 'willow', type: 'willow', c: 0, r: 4 }],
  };
  const add = (id: string, type: string, c: number, r: number, level?: string) => scene.entities.push({ id, type, c, r, ...(level ? { level } : {}) });
  // Connected paving is host data. Borders derive from these same cells.
  const paths: Cell[] = [];
  for (let r = 0; r < QUAY_SIZE; r++) for (let c = 0; c < QUAY_SIZE; c++) {
    if (r === 7 || r === 8) { add(`water-${c}-${r}`, 'water', c, r); continue; }
    if ((r >= 4 && r <= 6 && c >= 1 && c <= 12) || (r >= 9 && r <= 11 && c >= 2 && c <= 12) || (c >= 6 && c <= 8 && r >= 1 && r <= 12)) paths.push({ c, r });
  }
  const paving = resolveAutotiles(paths, { mode: 'blob47', variants: ground.variants });
  if (paving.diagnostics.length) throw new Error('Weidenkai paving catalog is incomplete.');
  for (const { cell, variant } of paving.tiles) {
    if (!variant) throw new Error('Unresolved paving.');
    scene.tiles[variant] = { color: 0x8b9068, texture: variant };
    scene.map[cell.r]![cell.c] = variant;
  }
  scene.map[5]![7] = scene.map[10]![7] = 'stair';
  // Fill the low headroom beneath each shore end. Upper-floor underside is24px;
  // walking must not route a44px actor through that space on the ground floor.
  for (const r of [6, 9]) for (const c of [6, 7, 8]) scene.map[r]![c] = 'abutment';
  const bedCells: Cell[] = [];
  for (const r of [0, 12]) for (const c of [1, 2, 3, 4, 9, 10, 11, 12]) bedCells.push({ c, r });
  for (const c of [1, 12]) for (const r of [1, 2, 3, 10, 11]) bedCells.push({ c, r });
  for (const { cell, variant } of resolveAutotiles(bedCells, { mode: 'blob47', variants: beds.variants }).tiles) {
    if (!variant) throw new Error('Unresolved bed.');
    scene.entityTypes[variant] = { blocking: true, bodyHeight: 12, visual: { kind: 'sprite', texture: variant } };
    add(`bed-${cell.c}-${cell.r}`, variant, cell.c, cell.r);
    const flower = (cell.c + cell.r) % 3 === 0 ? 'daisy' : 'lavender';
    scene.entityTypes[flower] = { blocking: false, visual: { kind: 'sprite', texture: flower, width: 35, offset: { x: 0, y: -12 } } };
    add(`flower-${cell.c}-${cell.r}`, flower, cell.c, cell.r);
  }
  for (const [c, r] of [[2, 5], [10, 5], [5, 10], [10, 10]]) add(`lamp-${c}-${r}`, 'lantern', c!, r!);
  for (const [c, r] of [[2, 2], [3, 11], [11, 11]]) add(`shrub-${c}-${r}`, 'shrub', c!, r!);
  for (const [c, r] of [[5, 0], [12, 4], [9, 10]]) add(`pot-${c}-${r}`, 'pot', c!, r!);
  for (const c of [6, 8]) for (let r = 6; r <= 9; r++) {
    add(`rail-${c}-${r}`, 'railBlock', c, r, 'bridge');
    add(`rail-art-${c}-${r}`, c === 6 ? 'railNear' : 'railFar', c, r, 'bridge');
  }
  for (let c = 0; c < QUAY_SIZE; c++) if (c < 6 || c > 8) {
    add(`bank-far-${c}`, 'bankFar', c, 6);
    // Anchor on the water-side cell: shifting only the image from row9 left
    // its depth footprint across actors walking along that row.
    add(`bank-near-${c}`, 'bankNear', c, 8);
  }
  return scene;
}
