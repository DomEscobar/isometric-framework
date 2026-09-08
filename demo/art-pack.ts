import atlasUrl from './art/woodland.svg?url';
import type { Scene } from '../src/types';

/** A replaceable, self-contained theme. Coordinates below refer to the authored SVG atlas. */
export function createWoodlandScene(): Scene {
  const textures: NonNullable<Scene['assets']>['textures'] = {};
  const animations: NonNullable<NonNullable<Scene['assets']>['animations']> = {};
  for (const [index, id] of ['moss-1', 'moss-2', 'moss-3', 'path-1', 'path-2', 'path-3', 'pond'].entries()) {
    textures[id] = { image: 'woodland', frame: { x: index * 128, y: 0, width: 128, height: 64 } };
  }
  for (const [index, id] of ['oak', 'mushrooms', 'rock', 'lantern'].entries()) {
    textures[id] = { image: 'woodland', frame: { x: index * 128, y: 80, width: 128, height: 160 }, anchor: { x: .5, y: .95 } };
  }
  for (const [row, direction] of ['ne', 'se', 'sw', 'nw'].entries()) {
    for (let frame = 0; frame < 7; frame++) {
      textures[`ranger-${direction}-${frame}`] = {
        image: 'woodland', frame: { x: frame * 64, y: 256 + row * 80, width: 64, height: 80 }, anchor: { x: .5, y: .9 },
      };
    }
    animations[`idle-${direction}`] = { frames: [0, 1].map(frame => `ranger-${direction}-${frame}`), fps: 2, loop: true };
    animations[`walk-${direction}`] = { frames: [2, 3, 4, 5].map(frame => `ranger-${direction}-${frame}`), fps: 9, loop: true };
    animations[`jump-${direction}`] = { frames: [`ranger-${direction}-6`], fps: 1, loop: false };
  }
  const facing = (direction: string) => ({ idle: `idle-${direction}`, walk: `walk-${direction}`, jump: `jump-${direction}` });
  return {
    version: 1,
    name: 'Woodland atelier',
    tileWidth: 80,
    tileHeight: 40,
    controlledId: 'traveler',
    diagonal: false,
    maxStepHeight: 0,
    assets: { images: { woodland: { url: atlasUrl, sampling: 'linear' } }, textures, animations },
    map: Array.from({ length: 9 }, (_, r) => Array.from({ length: 9 }, (_, c) => {
      if (r === 0 || c === 0 || r === 8 || c === 8) return 'pond';
      if (r === 4 || c === 4 || (r === 6 && c >= 2 && c <= 6)) return 'path';
      return 'moss';
    })),
    tiles: {
      pond: { color: 0x82aaa0, texture: 'pond', walkable: false, elevation: -5 },
      moss: { color: 0x8fae79, textures: ['moss-1', 'moss-2', 'moss-3'] },
      path: { color: 0xddcca5, textures: ['path-1', 'path-2', 'path-3'] },
    },
    entityTypes: {
      ranger: {
        blocking: true, bodyHeight: 30,
        visual: {
          kind: 'sprite', texture: 'ranger-se-0', width: 62,
          animations: {
            ...facing('se'),
            directions: { ne: facing('ne'), se: facing('se'), sw: facing('sw'), nw: facing('nw'), n: facing('ne'), e: facing('se'), s: facing('sw'), w: facing('nw') },
          },
        },
      },
      oak: { blocking: true, bodyHeight: 82, visual: { kind: 'sprite', texture: 'oak', width: 112 } },
      mushrooms: { blocking: true, bodyHeight: 20, visual: { kind: 'sprite', texture: 'mushrooms', width: 78 } },
      rock: { blocking: true, bodyHeight: 25, visual: { kind: 'sprite', texture: 'rock', width: 85 } },
      lantern: { blocking: false, bodyHeight: 20, visual: { kind: 'sprite', texture: 'lantern', width: 72 } },
    },
    entities: [
      { id: 'traveler', type: 'ranger', c: 4, r: 6 },
      { id: 'oak-west', type: 'oak', c: 1, r: 2 },
      { id: 'oak-north', type: 'oak', c: 6, r: 1 },
      { id: 'oak-east', type: 'oak', c: 7, r: 3 },
      { id: 'oak-south', type: 'oak', c: 1, r: 7 },
      { id: 'mushrooms-west', type: 'mushrooms', c: 2, r: 3 },
      { id: 'mushrooms-east', type: 'mushrooms', c: 6, r: 5 },
      { id: 'mossy-stone', type: 'rock', c: 3, r: 2 },
      { id: 'pond-stone', type: 'rock', c: 7, r: 7 },
      { id: 'firefly-lantern', type: 'lantern', c: 4, r: 2, data: { role: 'collectible' } },
    ],
  };
}
