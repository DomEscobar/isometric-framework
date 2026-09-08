import type { AssetManifest, Scene, TileDefinition } from '../../../src/index';
import terrainUrl from './terrain-atlas.png?url';
import frames from './terrain-frames.json';

/** One source family, fixed geometry, world-space phase; never random per-cell textures. */
export const terrainAssets: AssetManifest = {
  images: { 'autumn-terrain': { url: terrainUrl, sampling: 'nearest' } },
  textures: frames,
};
export const terrainTiles: Record<'grass' | 'dirt' | 'paving' | 'water', TileDefinition> = {
  grass: { color: 0x777138, texture: 'terrain-grass-dirt-15-0-0' },
  dirt: { color: 0x9e6944, texture: 'terrain-dirt-grass-15-0-0' },
  paving: { color: 0xaa9061, texture: 'terrain-paving-15-0-0' },
  water: { color: 0x3b514a, walkable: false, texture: 'terrain-water-grass-15-0-0' },
};

/** Change only presentation IDs; collision/elevation/links/entities stay untouched. */
export function applyTerrain(scene: Scene): Scene {
  scene.assets ??= { images: {}, textures: {} };
  Object.assign(scene.assets.images, terrainAssets.images);
  Object.assign(scene.assets.textures, terrainAssets.textures);
  const material = (id: string | null | undefined): string => {
    if (id === 'grass' || id === 'dirt' || id === 'water') return id;
    if (id === 'abutmentBase') return 'dirt';
    if (id === 'paving' || id?.startsWith('stair') || id === 'abutment' || id?.startsWith('bridge-support') || id?.startsWith('bridgeSupport')) return 'paving';
    return '';
  };
  for (const map of [scene.map, ...(scene.levels ?? []).map(level => level.map)]) {
    const original = map.map(row => [...row]);
    for (let r = 0; r < original.length; r++) for (let c = 0; c < original[r]!.length; c++) {
      const id = original[r]![c];
      if (id == null) continue;
      const base = material(id);
      if (!base) continue;
      const neighbors = [[c - 1, r], [c + 1, r], [c, r - 1], [c, r + 1]] as const;
      const nearby = neighbors.map(([nc, nr]) => material(original[nr]?.[nc]));
      const alternative = base === 'grass' ? (nearby.includes('water') ? 'water' : 'dirt')
        : base === 'dirt' ? (nearby.includes('water') ? 'water' : 'grass')
        : nearby.includes('grass') ? 'grass' : nearby.includes('dirt') ? 'dirt' : 'grass';
      const family = base === 'paving' ? 'paving' : `${base}-${alternative}`;
      // Missing map cells continue the edge material, avoiding a synthetic map border.
      const mask = base === 'paving' ? 15 : neighbors.reduce((bits, [nc, nr], index) => {
        const other = material(original[nr]?.[nc]);
        return bits | (other !== alternative ? 1 << index : 0);
      }, 0);
      // Water on either side of a shore uses the same expanded world phase.
      const period = family.includes('water') ? 8 : 4;
      const texture = `terrain-${family}-${mask}-${c % period}-${r % period}`;
      const tileId = `${id}:${texture}`;
      const tile = { ...scene.tiles[id]!, texture };
      if (tile.sideTexture === 'autumn-cliff') tile.sideTexture = `autumn-cliff-${(c + r) % 4}`;
      delete tile.textures;
      scene.tiles[tileId] = tile;
      map[r]![c] = tileId;
    }
  }
  return scene;
}
