import type { AssetManifest, EntityType } from '../../../src/index';
import propsUrl from './props-atlas.png?url';
import archUrl from './bridge-arch.png?url';
import nearUrl from './bridge-near-rail.png?url';
import farUrl from './bridge-far-rail.png?url';
import wallUrl from './wall-material.png?url';
import cliffUrl from './cliff-material.png?url';
import cliffAtlasUrl from './cliff-atlas.png?url';
import props from './props-frames.json';
import { terrainAssets, terrainTiles } from './terrain';

const bridgeTexture = (image: string) => ({ image, frame: { x: 0, y: 0, width: 352, height: 288 }, anchor: { x: 64 / 352, y: 112 / 288 } });
export const autumnAssets: AssetManifest = {
  images: { ...terrainAssets.images, 'autumn-cliff-phases': { url: cliffAtlasUrl, sampling: 'nearest' }, 'autumn-cliff': { url: cliffUrl, sampling: 'nearest' }, 'autumn-wall': { url: wallUrl, sampling: 'nearest' }, 'autumn-props': { url: propsUrl, sampling: 'nearest' },
    'bridge-arch': { url: archUrl, sampling: 'nearest' }, 'bridge-near-rail': { url: nearUrl, sampling: 'nearest' }, 'bridge-far-rail': { url: farUrl, sampling: 'nearest' } },
  textures: { ...terrainAssets.textures, ...props, 'autumn-cliff': { image: 'autumn-cliff' }, 'autumn-wall': { image: 'autumn-wall' }, 'bridge-arch': bridgeTexture('bridge-arch'),
    ...Object.fromEntries(Array.from({ length: 4 }, (_, phase) => [`autumn-cliff-${phase}`, { image: 'autumn-cliff-phases', frame: { x: phase * 32, y: 0, width: 32, height: 64 } }])),
    'bridge-near-rail': bridgeTexture('bridge-near-rail'), 'bridge-far-rail': bridgeTexture('bridge-far-rail') },
};
const prop = (texture: string, height: number): EntityType => ({ blocking: true, bodyHeight: height, visual: { kind: 'sprite', texture } });
const bridge = (texture: string, bodyHeight: number): EntityType => ({ blocking: false, rows: 6, bodyHeight, visual: { kind: 'sprite', texture } });
export const autumnArtTypes: Record<string, EntityType> = {
  'tree-gold': prop('tree-gold', 190), 'tree-rust': prop('tree-rust', 198), 'tree-olive': prop('tree-olive', 184),
  rock: prop('rock', 38), shrub: prop('shrub', 40), bench: prop('bench', 34),
  'bridge-arch': bridge('bridge-arch', 64), 'bridge-near-rail': bridge('bridge-near-rail', 24), 'bridge-far-rail': bridge('bridge-far-rail', 24),
};
export const autumnTiles = {
  ...terrainTiles,
  grass: { ...terrainTiles.grass, sideTexture: 'autumn-cliff' },
  dirt: { ...terrainTiles.dirt, sideTexture: 'autumn-cliff' },
  paving: { ...terrainTiles.paving, sideTexture: 'autumn-wall' },
};
