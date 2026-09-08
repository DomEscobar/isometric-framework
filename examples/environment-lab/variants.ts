import a from './variants/a.json';
import b from './variants/b.json';
import c from './variants/c.json';
import accepted from './variants/accepted.json';
import atlasUrl from '../../skills/animated-environments/assets/challenge-atlas.svg?url';
import type { Scene } from '../../src/index';
import fountainUrl from './art/generated/fountain-source.png?url';
import riverUrl from './art/generated/river-source.png?url';
import bridgeUrl from './art/generated/bridge-source.png?url';
import railUrl from './art/generated/rail-source.png?url';
import splashUrl from './art/generated/splash-source.png?url';
import { createGeneratedScene, type GeneratedMode } from './generated-scene';

export const variants = { accepted, a, b, c };
export type Variant = keyof typeof variants | `generated-${GeneratedMode}`;
export function createEnvironmentScene(variant: Variant): Scene {
  if (variant.startsWith('generated-')) return createGeneratedScene(accepted as Scene, variant.slice(10) as GeneratedMode, {fountain:fountainUrl,river:riverUrl,bridge:bridgeUrl,rail:railUrl,splash:splashUrl});
  const scene = structuredClone(variants[variant as keyof typeof variants]) as Scene;
  scene.assets!.images.challenge!.url = atlasUrl;
  return scene;
}
