import type { Scene, TextureDefinition } from '../../src/index';

export type GeneratedMode = 'raw' | 'registered' | 'layered';
export const generatedSources = ['fountain', 'river', 'bridge', 'rail', 'splash'] as const;

/** Host-owned bindings measured from the generated PNGs; never infer cells from a prompt. */
export function createGeneratedScene(base: Scene, mode: GeneratedMode, urls: Record<string, string>): Scene {
  const scene = structuredClone(base);
  scene.name = `Generated water & stone · ${mode}`;
  const textures: Record<string, TextureDefinition> = {};
  const frame = (id: string, image: string, x: number, y: number, width: number, height: number, ax: number, ay: number) => {
    textures[id] = { image, frame: { x, y, width, height }, anchor: { x: ax, y: ay } };
  };
  for (let i = 0; i < 4; i++) {
    frame(`fountain-${i}`, 'fountain', i % 2 * 627, Math.floor(i / 2) * 627, 627, 627, .20600744285, .70653907496);
    const riverOrigins = [[15,225],[638,225],[15,768],[638,768]];
    if (mode === 'raw') frame(`river-${i}`, 'river', i % 2 * 627, Math.floor(i / 2) * 627, 627, 627, .5, .5);
    else frame(`river-${i}`, 'river', riverOrigins[i]![0]!, riverOrigins[i]![1]!, 600, 330, .5, .5);
  }
  const splashOrigins = [[168,300],[680,300],[168,730],[690,730]];
  const splashAnchors = [[.5025,167/240],[.5025,166/240],[.5025,139/240],[.5,142/240]];
  for (let i = 0; i < 4; i++) frame(`splash-${i}`, 'splash', splashOrigins[i]![0]!, splashOrigins[i]![1]!, 400, 240, splashAnchors[i]![0]!, splashAnchors[i]![1]!);
  // Terrain always fills a 64x32 diamond; this tight crop matches the measured paving corners.
  frame('deck', 'bridge', 188,143,568,286,.5,.5);
  frame('pier', 'bridge', 1189,20,280,427,138/280,352/427);
  frame('rail', 'rail',0,0,1536,1024,336/1536,912/1024);
  frame('proxy', 'fountain',0,0,1,1,0,0);
  scene.assets = {
    images: Object.fromEntries(generatedSources.map(id => [id, {url:urls[id]!,sampling:'nearest' as const}])),
    textures,
    animations: {
      'fountain-loop': {frames:[0,1,2,3].map(i=>`fountain-${i}`),fps:4,loop:true},
      'river-loop': {frames:[0,1,2,3].map(i=>`river-${i}`),fps:4,loop:true},
      'splash-loop': {frames:[0,1,2,3].map(i=>`splash-${i}`),fps:4,loop:true},
    },
  };
  scene.tiles.grass!.color = 0x98ab79;
  scene.tiles.river!.color = 0x227f8a;
  for (const [id,tile] of Object.entries(scene.tiles)) if (id === 'towpath' || id === 'deck' || id.startsWith('step')) {tile.texture='deck';tile.color=0xbca074;}
  scene.entityTypes.fountain = {columns:3,rows:3,blocking:true,bodyHeight:46,visual:{kind:'sprite',width:217.6925858951,...(mode==='layered'?{texture:'fountain-0'}:{animation:'fountain-loop'})}};
  scene.entityTypes.fountainStone!.bodyHeight = 114;
  scene.entityTypes.water = {blocking:false,visual:{kind:'sprite',animation:'river-loop',width:mode==='raw'?68.01:65.084746}};
  scene.entityTypes.pier = {blocking:true,bodyHeight:67.1,visual:{kind:'sprite',texture:'pier',width:66.865672}};
  // Six single-cell collider reservations per edge remain independent of three render spans.
  for (const id of ['railFar','railNear']) scene.entityTypes[id] = {blocking:true,bodyHeight:32,visual:{kind:'sprite',texture:'proxy'}};
  // Split the measured ~3.2px slope residual across both ends instead of fixing only one end.
  scene.entityTypes.railArt = {blocking:false,visual:{kind:'sprite',texture:'rail',width:1536*64/913,offset:{x:-16,y:6.4}}};
  for (const r of [4,6]) for (const c of [3,5,7]) scene.entities.push({id:`rail-art-${c}-${r}`,type:'railArt',c,r,level:'bridge'});
  if (mode === 'layered') {
    // Fixed generated base + small independently generated splash sprites: no stone frame changes.
    // Keep the same sorting origin, use presentation offsets within this fully blocked basin.
    for (const [i,x,y] of [[0,5,-16],[1,121,-16],[2,64,1]]) {
      const id=`splash-${i}`;
      scene.entityTypes[id]={blocking:false,visual:{kind:'sprite',animation:'splash-loop',width:22.9226361,offset:{x:x!,y:y!}}};
      scene.entities.push({id,type:id,c:1,r:8});
    }
  }
  return scene;
}
