import gardenUrl from './art/pixel-cafe/garden-atlas.png?url';
import gardenerUrl from './art/pixel-cafe/gardener-atlas.png?url';
import flowersUrl from './art/pixel-cafe/flowers-v2.png?url';
import planterUrl from './art/pixel-cafe/planter-bases.png?url';
import type { EntityDefinition, EntityType, Scene, TextureDefinition } from '../src/types';
import { analyzeAutotiles } from '../src/core.ts';

/** Hand-inspected regions in the original 1254px generated atlas; it is not an equal grid. */
const gardenFrames: Record<string, [number, number, number, number, number, number]> = {
  parasol: [42, 6, 275, 342, 138 / 275, 304 / 342],
  'chair-se': [406, 88, 168, 252, .49, .89],
  'chair-sw': [678, 88, 169, 253, .50, .89],
  'orange-pot': [977, 59, 236, 277, .50, .92],
  'purple-bed': [15, 366, 300, 278, .50, .79],
  'orange-bed': [330, 370, 301, 274, .50, .79],
  'white-bed': [641, 369, 301, 275, .50, .79],
  shrub: [993, 357, 223, 277, .50, .93],
  'fence-ne': [28, 668, 283, 302, .50, .72],
  'fence-se': [343, 668, 284, 302, .50, .72],
  lantern: [742, 635, 110, 337, 44 / 110, 313 / 337],
  palm: [945, 642, 292, 325, 153 / 292, 300 / 325],
  terracotta: [10, 992, 299, 197, .50, .50],
  grass: [318, 991, 306, 198, .50, .50],
  decking: [633, 991, 303, 198, .50, .50],
  sandstone: [947, 991, 301, 198, .50, .50],
};

/** A small host-owned garden. Decorative width never substitutes for blocking footprints. */
export function createPixelCafeScene(calibration = false): Scene {
  const textures: Record<string, TextureDefinition> = {};
  const animations: NonNullable<NonNullable<Scene['assets']>['animations']> = {};
  for (const [id, [x, y, width, height, ax, ay]] of Object.entries(gardenFrames)) {
    textures[id] = { image: 'garden', frame: { x, y, width, height }, anchor: { x: ax, y: ay } };
  }
  for (const [i, id] of ['purple-bed', 'orange-bed', 'white-bed'].entries()) {
    textures[id] = { image: 'flowers', frame: { x: 12 + i * 591, y: 160, width: 576, height: 584 }, anchor: { x: .5, y: 480 / 584 } };
  }
  const planterTypes: Record<string, EntityType> = {};
  for (let mask = 0; mask < 16; mask++) {
    const id = `planter-base-${mask}`;
    textures[id] = { image: 'planters', frame: { x: (mask % 4) * 160, y: Math.floor(mask / 4) * 128, width: 160, height: 128 }, anchor: { x: .5, y: 88 / 128 } };
    planterTypes[id] = { blocking: false, bodyHeight: 10, visual: { kind: 'sprite', texture: id, width: 80 } };
  }
  // Padded source windows keep a common display scale. Ground contacts are
  // measured for idle facings; walk/jump contact drift needs rendered validation.
  const actorRows = [25, 328, 635, 939];
  const actorColumns = [82, 395, 710, 1025];
  const contacts = [261, 261, 260, 258];
  for (const [row, direction] of ['ne', 'se', 'sw', 'nw'].entries()) {
    for (let frame = 0; frame < 4; frame++) {
      textures[`gardener-${direction}-${frame}`] = {
        image: 'gardener', frame: { x: actorColumns[frame]!, y: actorRows[row]!, width: 160, height: 280 },
        anchor: { x: .52, y: contacts[row]! / 280 },
      };
    }
    animations[`idle-${direction}`] = { frames: [`gardener-${direction}-0`], fps: 1, loop: true };
    animations[`walk-${direction}`] = { frames: [1, 0, 2, 0].map(frame => `gardener-${direction}-${frame}`), fps: 8, loop: true };
    animations[`jump-${direction}`] = { frames: [`gardener-${direction}-3`], fps: 1, loop: false };
    // Reuse the existing grounded arm/stride poses for a small action gesture.
    // These are not dedicated flower-plucking drawings; column 3 stays jump-only.
    animations[`pick-${direction}`] = { frames: [0, 1, 2].map(frame => `gardener-${direction}-${frame}`), fps: 3.33, loop: false };
    animations[`pick-recover-${direction}`] = { frames: [2, 1, 0].map(frame => `gardener-${direction}-${frame}`), fps: 6.67, loop: false };
  }
  const facing = (direction: string) => ({ idle: `idle-${direction}`, walk: `walk-${direction}`, jump: `jump-${direction}` });
  const prop = (texture: string, width: number, bodyHeight: number, blocking = true): EntityType => ({
    blocking, bodyHeight, visual: { kind: 'sprite', texture, width },
  });
  const entities: EntityDefinition[] = [{ id: 'traveler', type: 'gardener', c: 2, r: 6 }];
  const add = (type: string, c: number, r: number) => entities.push({ id: `${type}-${c}-${r}`, type, c, r });
  // Rear railings follow native +c northeast and +r southeast axes.
  for (const c of [0, 2, 4, 6]) add('fence-ne', c, 0);
  for (const r of [0, 2, 4, 6]) add('fence-se', 8, r);
  const flowers = ['purple-bed', 'orange-bed', 'white-bed'];
  for (let c = 2; c <= 7; c++) add(c === 4 ? 'orange-pot' : flowers[c % 3]!, c, 1);
  for (let r = 2; r <= 7; r++) add(flowers[(r + 1) % 3]!, 7, r);
  for (const c of [1, 2, 3, 5, 6, 7, 8]) add(flowers[c % 3]!, c, 8);
  for (const r of [1, 2, 3, 5, 6, 7, 8]) add(flowers[(r + 2) % 3]!, 0, r);
  add('palm', 1, 1);
  add('parasol', 5, 2);
  add('shrub', 6, 7);
  add('lantern', 1, 7);
  for (const [index, [c, r]] of [[2, 2], [6, 5], [4, 7]].entries()) {
    entities.push({ id: `seed-pot-${index + 1}`, type: 'seed-pot', c: c!, r: r!, data: { role: 'collectible', name: 'Path flower' } });
  }
  if (calibration) {
    entities.splice(0, entities.length, { id: 'traveler', type: 'gardener', c: 2, r: 6 });
    for (const [i, [c, r]] of [[2, 2], [3, 2], [4, 2], [4, 3], [4, 4]].entries()) add(flowers[i % 3]!, c!, r!);
    add('parasol', 6, 2);
    add('lantern', 1, 4);
    add('orange-pot', 7, 6);
    add('palm', 1, 1);
    add('calibration-base', 2, 4);
  }
  // Soil/stone geometry is separate from foliage. Neighbor masks remove interior
  // retaining walls; every rigid base uses the exact same ground projection.
  const beds = entities.filter(entity => flowers.includes(entity.type));
  const topology = analyzeAutotiles(beds, { mode: 'cardinal16' });
  for (const [index, bed] of beds.entries()) {
    const mask = topology[index]!.mask;
    entities.unshift({ id: `base-${bed.id}`, type: `planter-base-${mask}`, c: bed.c, r: bed.r });
    entities.push({ id: `crown-${bed.id}`, type: `${bed.type}-crown`, c: bed.c, r: bed.r });
  }
  const flowerTypes: Record<string, EntityType> = {};
  for (const id of flowers) {
    flowerTypes[id] = { blocking: true, bodyHeight: 50, visual: { kind: 'sprite', texture: id, width: 50, offset: { x: -10, y: -15 } } };
    flowerTypes[`${id}-crown`] = { blocking: false, bodyHeight: 50, visual: { kind: 'sprite', texture: id, width: 50, offset: { x: 10, y: -5 } } };
  }
  return {
    version: 1, name: calibration ? 'Sunflower art calibration' : 'Sunflower courtyard', tileWidth: 80, tileHeight: 40,
    controlledId: 'traveler', diagonal: false, maxStepHeight: 0,
    assets: {
      images: { garden: { url: gardenUrl, sampling: 'nearest' }, gardener: { url: gardenerUrl, sampling: 'nearest' }, flowers: { url: flowersUrl, sampling: 'nearest' }, planters: { url: planterUrl, sampling: 'nearest' } },
      textures, animations,
    },
    map: Array.from({ length: 9 }, (_, r) => Array.from({ length: 9 }, (_, c) => {
      if (calibration) return 'terracotta';
      if ((c === 0 && r === 4) || (r === 8 && c === 4)) return 'sandstone';
      if (r === 0 || c === 0 || r === 8 || c === 8 || r === 1 || c === 7) return 'grass';
      return 'terracotta';
    })),
    tiles: {
      grass: { color: 0x6d8b35, texture: 'grass' },
      terracotta: { color: 0xc77b51, texture: 'terracotta' },
      sandstone: { color: 0xdcb984, texture: 'sandstone' },
    },
    entityTypes: {
      ...planterTypes, ...flowerTypes,
      ...(calibration ? { 'calibration-base': { ...planterTypes['planter-base-0']!, blocking: true } } : {}),
      gardener: {
        blocking: true, bodyHeight: 64,
        visual: {
          kind: 'sprite', texture: 'gardener-se-0', width: 48,
          animations: {
            ...facing('se'),
            directions: { ne: facing('ne'), se: facing('se'), sw: facing('sw'), nw: facing('nw'), n: facing('ne'), e: facing('se'), s: facing('sw'), w: facing('nw') },
          },
        },
      },
      // The source group is centered over its four occupied cells: +.5c,+.5r projects to +40px x.
      parasol: { ...prop('parasol', 120, 132), columns: 2, rows: 2, visual: { kind: 'sprite', texture: 'parasol', width: 120, offset: { x: 40, y: 0 } } },
      'orange-pot': prop('orange-pot', 54, 54),
      shrub: prop('shrub', 58, 52),
      palm: prop('palm', 104, 96),
      lantern: prop('lantern', 27, 76),
      'seed-pot': prop('orange-pot', 22, 18, false),
      'fence-ne': { ...prop('fence-ne', 82, 42), columns: 2, visual: { kind: 'sprite', texture: 'fence-ne', width: 82, offset: { x: 20, y: -10 } } },
      'fence-se': { ...prop('fence-se', 82, 42), rows: 2, visual: { kind: 'sprite', texture: 'fence-se', width: 82, offset: { x: 20, y: 10 } } },
    },
    entities,
  };
}
