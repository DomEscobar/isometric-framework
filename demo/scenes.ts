import type { Scene } from '../src/types';
import { createWoodlandScene } from './art-pack';
import { createPixelCafeScene } from './pixel-cafe';

export type Preset = 'jump' | 'levels' | 'courtyard' | 'collection' | 'art' | 'cafe' | 'cafe-calibration';

/** Game content belongs to the application, not the engine. Return fresh scene data. */
export function createScene(preset: Preset): Scene {
  if (preset === 'cafe') return createPixelCafeScene();
  if (preset === 'cafe-calibration') return createPixelCafeScene(true);
  if (preset === 'art') return createWoodlandScene();
  if (preset === 'jump') return createJumpScene();
  if (preset === 'levels') return createBridgeScene();
  const map = Array.from({ length: 9 }, (_, r) =>
    Array.from({ length: 9 }, (_, c) => {
      if (r === 0 || r === 8 || c === 0 || c === 8) return 'water';
      if (r === 4 || c === 4) return 'path';
      return (r + c) % 3 === 0 ? 'grassLight' : 'grass';
    }),
  );
  return {
    version: 1,
    name: preset === 'courtyard' ? 'The quiet courtyard' : 'A pocketful of light',
    tileWidth: 72,
    tileHeight: 36,
    diagonal: false,
    maxStepHeight: 0,
    controlledId: 'traveler',
    map,
    tiles: {
      water: { color: 0xbcd9d6, walkable: false, elevation: -7 },
      grass: { color: 0xadc59b },
      grassLight: { color: 0xb9cfa7 },
      path: { color: 0xe0d8bc },
    },
    entityTypes: {
      traveler: { visual: { kind: 'actor', color: 0xd96e52, height: 34 }, blocking: true },
      hedge: { visual: { kind: 'box', color: 0x628b68, height: 38 }, blocking: true },
      stone: { visual: { kind: 'box', color: 0xaba99c, height: 23 }, blocking: true },
      gem: { visual: { kind: 'gem', color: 0xedb845, height: 22 }, blocking: false },
    },
    entities: [
      { id: 'traveler', type: 'traveler', c: 4, r: 7 },
      { id: 'hedge-north', type: 'hedge', c: 2, r: 2 },
      { id: 'hedge-east', type: 'hedge', c: 6, r: 2 },
      { id: 'hedge-west', type: 'hedge', c: 2, r: 6 },
      { id: 'hedge-south', type: 'hedge', c: 6, r: 6 },
      { id: 'center-stone', type: 'stone', c: 4, r: 4 },
      ...(preset === 'collection' ? [
        { id: 'light-1', type: 'gem', c: 2, r: 4 },
        { id: 'light-2', type: 'gem', c: 4, r: 2 },
        { id: 'light-3', type: 'gem', c: 6, r: 4 },
      ] : []),
    ],
  };
}

/** The trap cadence is a host game rule; this scene supplies only its visible lane and launcher. */
function createJumpScene(): Scene {
  const scene = createBridgeScene();
  scene.name = 'Jump & dodge';
  scene.tiles.trapLane = { color: 0xd8b1a0 };
  scene.tiles.launchPad = { color: 0x956b5b };
  for (let c = 1; c <= 9; c++) scene.map[6]![c] = 'trapLane';
  scene.map[6]![0] = 'launchPad';
  scene.entityTypes.launcher = { visual: { kind: 'box', color: 0x80544a, height: 26 }, blocking: true };
  scene.entities = scene.entities.map(entity => entity.id === 'traveler' ? { ...entity, c: 2, r: 6 } : entity);
  scene.entities.push({ id: 'trap-launcher', type: 'launcher', c: 0, r: 6 });
  return scene;
}

/** Two walkable surfaces at the same coordinates, joined only by two stair flights. */
function createBridgeScene(): Scene {
  const scene = createScene('collection');
  const map: string[][] = Array.from({ length: 11 }, (_, r) =>
    Array.from({ length: 11 }, (_, c) => {
      if (r === 0 || r === 10 || c === 0 || c === 10) return 'water';
      if (r === 5 || c === 5 || r === 6) return 'path';
      return (r + c) % 3 === 0 ? 'grassLight' : 'grass';
    }),
  );
  for (const [c, tile] of [[1, 'step1'], [2, 'step2'], [3, 'step3'], [7, 'step3'], [8, 'step2'], [9, 'step1']] as const) {
    map[5]![c] = tile;
  }
  return {
    ...scene,
    version: 2,
    name: 'Above & below',
    maxStepHeight: 18,
    map,
    tiles: {
      ...scene.tiles,
      step1: { color: 0xdbbd8f, elevation: 18 },
      step2: { color: 0xd1aa77, elevation: 36 },
      step3: { color: 0xc39862, elevation: 54 },
      bridge: { color: 0xc48e64 },
    },
    levels: [{
      id: 'bridge', name: 'Bridge', height: 72,
      map: Array.from({ length: 11 }, (_, r) =>
        Array.from({ length: 11 }, (_, c) => r >= 4 && r <= 6 && c >= 4 && c <= 6 ? 'bridge' : null),
      ),
    }],
    links: [
      { from: { c: 3, r: 5 }, to: { c: 4, r: 5, level: 'bridge' }, bidirectional: true },
      { from: { c: 6, r: 5, level: 'bridge' }, to: { c: 7, r: 5 }, bidirectional: true },
    ],
    entities: [
      { id: 'traveler', type: 'traveler', c: 1, r: 6 },
      { id: 'ground-stone', type: 'stone', c: 5, r: 4 },
      { id: 'bridge-hedge', type: 'hedge', c: 5, r: 6, level: 'bridge' },
      { id: 'garden-hedge', type: 'hedge', c: 8, r: 8 },
      { id: 'ground-light', type: 'gem', c: 5, r: 5 },
      { id: 'bridge-light', type: 'gem', c: 5, r: 5, level: 'bridge' },
      { id: 'bridge-light-east', type: 'gem', c: 6, r: 4, level: 'bridge' },
    ],
  };
}
