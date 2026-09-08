import { type Scene, type TextureDefinition, type EntityType } from '../../src/index';
import { autumnAssets, autumnArtTypes, autumnTiles } from './art/manifest';
import { applyTerrain } from './art/terrain';
import gardenerUrl from '../../demo/art/pixel-cafe/gardener-atlas.png?url';

export const AUTUMN_SIZE = 24;
export const AUTUMN_CONTENT_OFFSET = 3;
const CONTENT_SIZE = 18;

/** Host-owned geometry; artwork never determines walkability or floor identity. */
export function createAutumnScene(): Scene {
  const textures: Record<string, TextureDefinition> = { ...structuredClone(autumnAssets.textures) };
  const animations = { ...structuredClone(autumnAssets.animations) };
  const rows = [25, 328, 635, 939], columns = [82, 395, 710, 1025], contacts = [261, 261, 260, 258];
  for (const [row, direction] of ['ne', 'se', 'sw', 'nw'].entries()) {
    for (let frame = 0; frame < 4; frame++) textures[`actor-${direction}-${frame}`] = { image: 'actor', frame: { x: columns[frame]!, y: rows[row]!, width: 160, height: 280 }, anchor: { x: .52, y: contacts[row]! / 280 } };
    animations[`idle-${direction}`] = { frames: [`actor-${direction}-0`], fps: 1, loop: true };
    animations[`walk-${direction}`] = { frames: [1, 0, 2, 0].map(frame => `actor-${direction}-${frame}`), fps: 8, loop: true };
    animations[`jump-${direction}`] = { frames: [`actor-${direction}-3`], fps: 1, loop: false };
  }
  textures.invisible = { image: 'actor', frame: { x: 0, y: 0, width: 1, height: 1 }, anchor: { x: 0, y: 0 } };
  const facing = (direction: string) => ({ idle: `idle-${direction}`, walk: `walk-${direction}`, jump: `jump-${direction}` });
  const traveler: EntityType = { blocking: true, bodyHeight: 44, visual: { kind: 'sprite', texture: 'actor-se-0', width: 28.4, animations: { ...facing('se'), directions: { ne: facing('ne'), se: facing('se'), sw: facing('sw'), nw: facing('nw'), n: facing('ne'), e: facing('se'), s: facing('sw'), w: facing('nw') } } } };
  const scene: Scene = {
    version: 2, name: 'Goldlaub', tileWidth: 64, tileHeight: 32,
    controlledId: 'traveler', diagonal: false, maxStepHeight: 16,
    assets: { ...structuredClone(autumnAssets), images: { ...autumnAssets.images, actor: { url: gardenerUrl, sampling: 'nearest' } }, textures, animations },
    map: Array.from({ length: CONTENT_SIZE }, () => Array<string>(CONTENT_SIZE).fill('grass')),
    tiles: {
      ...structuredClone(autumnTiles),
      grass: { ...autumnTiles.grass!, elevation: 32 },
      dirt: { ...autumnTiles.dirt!, elevation: 32 },
      water: { ...autumnTiles.water!, walkable: false },
      abutmentBase: { ...autumnTiles.dirt!, elevation: 0 },
      stairSupport: { ...autumnTiles.paving!, walkable: false },
      stair48: { ...autumnTiles.paving!, elevation: 48 },
    },
    levels: [
      // These solid end beams fill48..56px between stairs and the deck underside.
      // The center keeps its56px underside, preserving the arched water opening.
      { id: 'bridge-supports', name: 'Brückenauflager', height: 56, map: Array.from({ length: CONTENT_SIZE }, (_, r) => Array.from({ length: CONTENT_SIZE }, (_, c) => c >= 6 && c <= 8 && (r === 6 || r === 11) ? 'stairSupport' : null)) },
      { id: 'bridge', name: 'Alte Steinbrücke', height: 64, map: Array.from({ length: CONTENT_SIZE }, (_, r) => Array.from({ length: CONTENT_SIZE }, (_, c) => c >= 6 && c <= 8 && r >= 6 && r <= 11 ? 'paving' : null)) },
    ],
    links: [{ from: { c: 7, r: 5 }, to: { c: 7, r: 6, level: 'bridge' }, bidirectional: true }, { from: { c: 7, r: 11, level: 'bridge' }, to: { c: 7, r: 12 }, bidirectional: true }],
    entityTypes: { ...structuredClone(autumnArtTypes), traveler, railBlock: { blocking: true, bodyHeight: 28, visual: { kind: 'sprite', texture: 'invisible' } }, abutmentBlock: { blocking: true, bodyHeight: 56, visual: { kind: 'sprite', texture: 'invisible' } } },
    entities: [{ id: 'traveler', type: 'traveler', c: 7, r: 8, level: 'bridge' }],
  };
  const add = (id: string, type: string, c: number, r: number, level?: string) => scene.entities.push({ id, type, c, r, ...(level ? { level } : {}) });
  // A gently changing shore avoids an endless ruler-straight channel.
  const riverBounds = (c: number) => ({ first: c < 4 ? 6 : c > 13 ? 8 : 7, last: c < 3 ? 9 : c > 12 ? 11 : 10 });
  for (let c = 0; c < CONTENT_SIZE; c++) {
    const { first, last } = riverBounds(c);
    for (let r = first; r <= last; r++) scene.map[r]![c] = 'water';
  }
  // Broad dirt approaches, with enough standing room beside the stairs.
  for (let r = 1; r <= 5; r++) for (let c = 3; c <= 9; c++) if ((r >= 2 && r <= 4) || c >= 5) scene.map[r]![c] = 'dirt';
  for (let r = 12; r <= 16; r++) for (let c = 6; c <= 13; c++) if ((r >= 13 && r <= 15) || c <= 9) scene.map[r]![c] = 'dirt';
  for (const r of [5, 12]) for (const c of [6, 7, 8]) scene.map[r]![c] = 'stair48';
  // Only the shore supports are solid. The center opening remains water, not a ground wall.
  for (const r of [6, 11]) for (const c of [6, 7, 8]) {
    scene.map[r]![c] = 'abutmentBase';
    add(`abutment-${c}-${r}`, 'abutmentBlock', c, r);
  }
  for (const c of [6, 8]) for (let r = 6; r <= 11; r++) add(`rail-${c}-${r}`, 'railBlock', c, r, 'bridge');
  add('bridge-arch', 'bridge-arch', 6, 6);
  add('bridge-near-rail', 'bridge-near-rail', 6, 6, 'bridge');
  add('bridge-far-rail', 'bridge-far-rail', 8, 6, 'bridge');

  // Trees share a scale and trunk contact; canopy overlap is deliberate.
  const trees: [number, number, string][] = [
    [0, 0, 'tree-gold'], [2, 0, 'tree-rust'], [4, 0, 'tree-olive'], [7, 0, 'tree-gold'], [10, 0, 'tree-rust'], [13, 0, 'tree-olive'], [16, 0, 'tree-gold'],
    [0, 2, 'tree-rust'], [1, 4, 'tree-gold'], [3, 4, 'tree-gold'], [11, 3, 'tree-rust'], [14, 3, 'tree-gold'], [17, 3, 'tree-olive'],
    [12, 12, 'tree-rust'], [15, 13, 'tree-gold'], [17, 15, 'tree-rust'], [14, 16, 'tree-olive'], [12, 17, 'tree-gold'],
    [17, 0, 'tree-rust'], [17, 17, 'tree-gold'],
  ];
  for (const [c, r, type] of trees) if (scene.map[r]![c] !== 'water') add(`tree-${c}-${r}`, type, c, r);
  for (const [c, r] of [[0, 5], [2, 5], [4, 6], [10, 6], [12, 6], [16, 7], [1, 10], [4, 11], [10, 11], [13, 12], [17, 12]]) {
    if (scene.map[r!]![c!] !== 'water') add(`bank-rock-${c}-${r}`, 'rock', c!, r!);
  }
  for (const [c, r] of [[1, 1], [3, 1], [9, 0], [12, 2], [15, 4], [17, 6], [0, 12], [2, 14], [4, 16], [6, 17], [11, 16], [14, 14], [16, 16], [11, 5], [3, 5], [4, 12], [10, 12]]) add(`shrub-${c}-${r}`, 'shrub', c!, r!);
  // Extend real terrain around the composed crossing; the edge of a board is not
  // a forest boundary. The original assembly moves as one rigid +3,+3 unit.
  const offset = AUTUMN_CONTENT_OFFSET;
  const ground = Array.from({ length: AUTUMN_SIZE }, () => Array<string>(AUTUMN_SIZE).fill('grass'));
  for (let c = 0; c < AUTUMN_SIZE; c++) {
    const { first, last } = riverBounds(c - offset);
    for (let r = first + offset; r <= last + offset; r++) ground[r]![c] = 'water';
  }
  for (let r = 0; r < CONTENT_SIZE; r++) for (let c = 0; c < CONTENT_SIZE; c++) ground[r + offset]![c + offset] = scene.map[r]![c]!;
  scene.map = ground;
  for (const level of scene.levels ?? []) {
    const padded = Array.from({ length: AUTUMN_SIZE }, () => Array<string | null>(AUTUMN_SIZE).fill(null));
    for (let r = 0; r < CONTENT_SIZE; r++) for (let c = 0; c < CONTENT_SIZE; c++) padded[r + offset]![c + offset] = level.map[r]![c]!;
    level.map = padded;
  }
  for (const entity of scene.entities) { entity.c += offset; entity.r += offset; }
  for (const link of scene.links ?? []) for (const cell of [link.from, link.to]) { cell.c += offset; cell.r += offset; }
  const forestMargin: [number, number, string][] = [
    [0, 1, 'tree-olive'], [3, 1, 'tree-gold'], [7, 1, 'tree-rust'], [11, 1, 'tree-olive'], [15, 1, 'tree-gold'], [19, 1, 'tree-rust'], [23, 1, 'tree-olive'],
    [1, 5, 'tree-gold'], [1, 8, 'tree-rust'], [22, 5, 'tree-gold'], [23, 8, 'tree-rust'],
    [4, 23, 'tree-rust'], [12, 23, 'tree-olive'], [17, 23, 'tree-rust'], [22, 22, 'tree-gold'], [23, 18, 'tree-rust'],
  ];
  for (const [c, r, type] of forestMargin) if (ground[r]![c] !== 'water') add(`forest-edge-${c}-${r}`, type, c, r);
  add('riverside-bench', 'bench', 0, 14);
  applyTerrain(scene);
  return scene;
}
