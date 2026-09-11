import type { Scene, AssetManifest } from '../../src/index.ts';
import { SIZE, projection, trees, wet, deck, path, spawn } from './layout.ts';

function neutralTree(height: number): string {
  const canvas = document.createElement('canvas'); canvas.width = 36; canvas.height = height + 6;
  const ctx = canvas.getContext('2d')!;
  ctx.fillStyle = '#674728'; ctx.fillRect(15,height-19,6,22);
  ctx.fillStyle = '#315b32'; ctx.beginPath(); ctx.ellipse(18,17,17,16,0,0,Math.PI*2); ctx.fill();
  ctx.fillStyle = '#538640'; ctx.beginPath(); ctx.ellipse(14,13,12,11,0,0,Math.PI*2); ctx.fill();
  ctx.fillStyle = '#776035'; ctx.fillRect(11,height+1,15,3);
  return canvas.toDataURL();
}

export function guideScene(): Scene {
  return {
    version: 1, name: 'Mossbend', ...projection, diagonal: false,
    map: Array.from({length: SIZE}, (_, r) => Array.from({length: SIZE}, (_, c) => deck(c,r) ? 'deck' : wet(c,r) ? 'water' : path(c,r) ? 'path' : 'grass')),
    tiles: {
      grass: {color: 0x548b43}, path: {color: 0xccac70},
      water: {color: 0x368aa0, walkable: false}, deck: {color: 0xa8773e},
    },
    entityTypes: Object.fromEntries(trees.map(t => [t.id, {visual: {kind: 'sprite' as const, url: neutralTree(t.height), anchor: {x:.5,y:(t.height+2)/(t.height+6)}}, blocking: true, bodyHeight: t.height}])),
    entities: trees.map(t => ({id: t.id, type: t.id, c: t.c, r: t.r})),
  };
}

export function playableScene(assets: AssetManifest, groundOnly = false): Scene {
  const scene = guideScene(); scene.assets = assets;
  scene.tiles = {};
  scene.map = Array.from({length:SIZE},(_,r)=>Array.from({length:SIZE},(_,c)=>{
    const id=`ground-${c}-${r}`;
    scene.tiles[id]={color:0x725936,texture:id,walkable:!wet(c,r)||deck(c,r)};
    return id;
  }));
  scene.entityTypes = Object.fromEntries(trees.map(t=>[t.id,{
    visual:{kind:'sprite' as const,texture:groundOnly?'empty':t.id==='oak-front'?'tree-front':t.id},blocking:true,bodyHeight:t.height,
  }]));
  scene.entityTypes.player={visual:{kind:'actor',color:0xe9a757,scale:.30},blocking:true,bodyHeight:16};
  scene.entities.push({id:'traveler',type:'player',...spawn});
  scene.controlledId='traveler';
  for(let r=0;r<SIZE;r++)for(let c=0;c<SIZE;c++){
    if(!wet(c,r)||deck(c,r))continue;
    const id=`water-${c}-${r}`;
    scene.entityTypes[id]={visual:{kind:'sprite',animation:id},blocking:false,bodyHeight:.01};
    scene.entities.push({id,type:id,c,r});
  }
  return scene;
}
