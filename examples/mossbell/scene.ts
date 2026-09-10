import { resolveAutotiles, type Cell, type Scene } from '../../src/index';
import { makeArt, pathCatalog, bedCatalog } from './assets';

export type Region = 'town' | 'forest';
export type Progress = 'seeking' | 'seed' | 'planted';
export interface Landmark { id: string; name: string; cell: Cell; description: string; kind: 'visit' | 'portal' | 'spring' | 'plant' }
export interface World { scene: Scene; region: Region; landmarks: Landmark[]; water: Cell[]; lamps: Cell[]; smoke: { cell: Cell; x: number; y: number }[]; bells: { cell: Cell; x: number; y: number }[]; spring?: Cell; spawn: Cell }

export const TOWN_EXIT: Cell = { c: 19, r: 19 };
export const FOREST_EXIT: Cell = { c: 3, r: 21 };
export const SPRING: Cell = { c: 17, r: 9 };
export const SEEDBED: Cell = { c: 8, r: 6 };
export const key = (c: Cell) => `${c.c},${c.r},${c.level ?? 'ground'}`;

export function createWorld(region: Region, progress: Progress, returning = false, calibration = false): World {
  const { assets, types } = makeArt();
  const forest = region === 'forest', size = forest ? 24 : 22;
  const spawn: Cell = forest ? { c: 7, r: 20 } : returning ? { c: 18, r: 19 } : { c: 9, r: 8 };
  const scene: Scene = { version: 2, name: forest ? 'Bellshade Forest' : 'Mossbell', tileWidth: 64, tileHeight: 32, diagonal: false, controlledId: 'traveler', maxStepHeight: 16,
    assets, entityTypes: types, map: Array.from({ length: size }, () => Array<string>(size).fill('grass')),
    tiles: { grass: { color: 0x405e55, texture: forest?'forest-grass':'grass' }, water: { color: 0x234d59, texture:'water-base', walkable: false }, paving: { color: 0x949080, texture: 'paved' },
      stair: { color: 0x777976, texture: 'paved', elevation: 16 }, deck: { color: 0x777976, texture: 'paved' },
      abutment: { color: 0x626c67, texture: 'paved', elevation: 24, walkable: false }, log: { color: 0x77625b, texture: 'log-top', elevation: 8 } },
    entities: [{ id: 'traveler', type: 'traveler', ...spawn }], levels: [], links: [] };
  const world: World = { scene, region, landmarks: [], water: [], lamps: [], smoke: [], bells: [], spawn };
  const path = new Map<string, Cell>(), reserved = new Set<string>();
  const add = (id: string, type: string, c: number, r: number, level?: string) => {
    scene.entities.push({ id, type, c, r, ...(level ? { level } : {}) });
    if (types[type]!.blocking && !level) for (let y = r; y < r + (types[type]!.rows ?? 1); y++) for (let x = c; x < c + (types[type]!.columns ?? 1); x++) reserved.add(`${x},${y}`);
  };
  const rect = (c: number, r: number, w: number, h: number) => { for (let y = r; y < r+h; y++) for (let x = c; x < c+w; x++) path.set(`${x},${y}`, { c:x, r:y }); };
  const lamp = (c: number, r: number) => { add(`lamp-${c}-${r}`, 'lantern', c, r); world.lamps.push({ c, r }); };
  const landmark = (id: string, name: string, cell: Cell, description: string, kind: Landmark['kind'] = 'visit') => world.landmarks.push({ id, name, cell, description, kind });
  const channel = forest ? [15, 16] : [14, 15];
  for (const r of channel) for (let c = 0; c < size; c++) { scene.map[r]![c] = 'water'; world.water.push({ c, r }); }
  if (!forest) {
    rect(3, 5, 16, 7); rect(10, 10, 3, 10); rect(10, 18, 10, 3); rect(2, 16, 10, 3); rect(17, 10, 3, 4);
    const houses = [['apothecary', 'cottage', 5, 2], ['bakery', 'bakery', 11, 2], ['bookbinder', 'bookshop', 17, 3], ['glasshouse', 'greenhouse', 2, 17], ['home', 'cottage', 16, 10]] as const;
    for (const [id, type, c, r] of houses) { add(id, type, c, r); if (type !== 'greenhouse') world.smoke.push({ cell: { c:c+1, r:r+1 }, x: type === 'cottage' ? 48 : 30, y: type === 'cottage' ? -186 : -184 }); }
    add('bell-tree', 'tree', 3, 8); world.bells.push({ cell:{c:3,r:8}, x:-68, y:-115 }, {cell:{c:3,r:8},x:79,y:-122});
    add('seedbed', 'seedbed', SEEDBED.c, SEEDBED.r);
    if (progress === 'planted') add('final-bloom', 'bloom', SEEDBED.c, SEEDBED.r);
    add('bakery-cat', 'cat', 13, 6); add('herbalist', 'villager', 7, 7); add('reader', 'villager', 18, 7); add('gardener', 'villager', 5, 16);
    for (const [c,r] of [[4,6],[10,6],[15,7],[9,12],[13,17],[19,18]]) lamp(c!,r!);
    for (let c=1;c<20;c+=2) { add(`garden-top-${c}`,'lavender',c,0); if (c<9 || c>13) add(`garden-low-${c}`,'marigold',c,20); }
    for (const [c,r] of [[2,4],[9,3],[15,3],[20,6],[20,11],[1,12],[6,12],[14,12],[7,17],[17,17]]) add(`shrub-${c}-${r}`,'shrub',c!,r!);
    const bedCells:Cell[]=[];
    for(const [bc,br,bw,bh] of [[5,10,4,2],[13,9,2,3],[1,1,2,4],[14,18,3,1]])for(let r=br!;r<br!+bh!;r++)for(let c=bc!;c<bc!+bw!;c++)bedCells.push({c,r});
    for(const {cell,variant} of resolveAutotiles(bedCells,{mode:'blob47',variants:bedCatalog}).tiles){if(!variant)throw new Error('Missing garden border');add(`bed-${cell.c}-${cell.r}`,variant,cell.c,cell.r);add(`bed-flower-${cell.c}-${cell.r}`,(cell.c+cell.r)%2?'lavender':'daisy',cell.c,cell.r);}
    for(const [c,r] of [[9,10],[15,9],[6,15]])if(!channel.includes(r!))add(`bench-${c}-${r}`,'bench',c!,r!);
    for(const [c,r] of [[0,6],[1,10],[0,18],[20,1],[21,8],[21,21]])add(`village-tree-${c}-${r}`,'smallSpruce',c!,r!);
    // A 3-cell-wide supported bridge, with a single clear lane and explicit rail cells.
    const deck = Array.from({length:size},(_,r)=>Array.from({length:size},(_,c)=>c>=10&&c<=12&&r>=13&&r<=16?'deck':null));
    scene.levels = [{id:'bridge',name:'Bellwater bridge',height:32,map:deck}];
    scene.links = [{from:{c:11,r:12},to:{c:11,r:13,level:'bridge'},bidirectional:true},{from:{c:11,r:16,level:'bridge'},to:{c:11,r:17},bidirectional:true}];
    for (const r of [13,16]) for(const c of [10,11,12]) scene.map[r]![c]='abutment';
    for (const c of [10,12]) for(let r=13;r<=16;r++) { add(`rail-${c}-${r}`,'railBlock',c,r,'bridge'); add(`rail-art-${c}-${r}`,c===10?'railNear':'railFar',c,r,'bridge'); }
    scene.map[12]![11]=scene.map[17]![11]='stair';
    landmark('apothecary','The apothecary',{c:8,r:7},'Mira: “The spring has been singing again. Follow the lights beyond the bridge.”');
    landmark('bell-tree','The bell tree',{c:4,r:9},'The bells turn in a breeze you can barely feel.');
    landmark('bridge','Bellwater bridge',{c:11,r:14,level:'bridge'},'Below the stone, the stream carries the last light toward Bellshade.');
    landmark('seedbed','A place for a seed',SEEDBED,'A little empty bed, waiting for something unusual.','plant');
    landmark('forest-gate','Bellshade Forest',TOWN_EXIT,'Follow the blue lights into Bellshade.','portal');
    add('gate-sign','sign',20,19);
  } else {
    rect(2,19,8,3); rect(7,12,3,10); rect(7,10,12,3); rect(15,7,5,5);
    // Two readable exploration loops, each rejoining the main trail.
    rect(3,5,3,9); rect(3,5,10,3); rect(11,5,3,8); rect(3,12,7,2);
    rect(13,17,8,3); rect(18,10,3,9); rect(8,19,13,2);
    add('ancient-tree','tree',18,6); world.spring={...SPRING};
    add('spring-heart','invisible',SPRING.c,SPRING.r);
    add('herbalist-shelter','greenhouse',3,2);
    add('leafling','wisp',14,11); add('leafling-friend','wisp',18,18); add('forest-cat','cat',5,9);
    for (const r of channel) for (const c of [7,8,9]) scene.map[r]![c]='log';
    add('home-sign','sign',2,21);
    for (const [c,r] of [[6,18],[10,13],[14,10]]) lamp(c!,r!);
    for (let c=1;c<size;c+=3) for (const r of [0,23]) if (!path.has(`${c},${r}`)&&!(r===23&&c===4)) add(`edge-${c}-${r}`, c%2?'spruce':'smallSpruce',c,r);
    for (let r=3;r<22;r+=4) for(const c of [0,22]) add(`edge-${c}-${r}`,'spruce',c,r);
    for (const [c,r] of [[2,7],[6,3],[9,2],[13,2],[16,2],[21,5],[1,15],[5,11],[11,8],[14,6],[16,13],[21,13],[12,18],[16,22]]) if(!path.has(`${c},${r}`)) add(`grove-${c}-${r}`,'spruce',c!,r!);
    for (const [c,r] of [[6,8],[10,9],[14,14],[16,5],[20,8],[12,21],[4,17]]) add(`rock-${c}-${r}`,'rock',c!,r!);
    world.bells.push({cell:{c:18,r:6},x:-68,y:-115},{cell:{c:18,r:6},x:79,y:-122});
    landmark('spring-heart','The luminous spring',SPRING,'A small light stirs beneath the surface.','spring');
    landmark('shelter','The old glasshouse',{c:5,r:5},'Someone still tends these plants. The watering can is warm.');
    landmark('log','The fallen crossing',{c:8,r:15},'The moss is soft. The water is much deeper than it looks.');
    landmark('southern-grove','The listening grove',{c:18,r:19},'A leafling pauses in the ferns, listening to the distant bells.');
    landmark('town-gate','Return to Mossbell',FOREST_EXIT,'Warm windows wait beyond the trees.','portal');
  }
  const paving=resolveAutotiles([...path.values()].filter(({c,r})=>!channel.includes(r)&&scene.map[r]?.[c]==='grass'),{mode:'blob47',variants:pathCatalog});
  if(paving.diagnostics.length) throw new Error('Incomplete path family');
  for(const {cell,variant} of paving.tiles) { if(!variant) throw new Error('Missing path');const id=forest?`${variant}-${cell.c%4}-${cell.r%4}`:variant; scene.tiles[id]={color:forest?0x62685b:0x8b8b78,texture:forest?`forest-${id}`:variant}; scene.map[cell.r]![cell.c]=id; }
  if(!forest) scene.map[12]![11]=scene.map[17]![11]='stair';
  // Shared exact channel boundaries; bank strips are grounded on the water side.
  if(!forest)for(let c=0;c<size;c++) if(c<10||c>12) for(const r of [channel[0]!-1,channel[1]!]) add(`bank-${c}-${r}`,'bank',c,r);
  for(const cell of world.water)if(scene.map[cell.r]![cell.c]==='water')add(`flow-${cell.c}-${cell.r}`,'flow',cell.c,cell.r);
  if(forest)for(let c=1;c<size-1;c+=2)if(c<7||c>9)for(const r of [14,17])add(`bank-fern-${c}-${r}`,'fern',c,r);
  // Deterministic dressing; keep the complete route network clear of solid bodies.
  for(let r=1;r<size-1;r++) for(let c=1;c<size-1;c++) {
    if(scene.map[r]![c]!=='grass'||reserved.has(`${c},${r}`)) continue;
    const n=(c*37+r*71+c*r*13)%101;
    if(forest && n<42) add(`fern-${c}-${r}`,n<9?'mushrooms':n%2?'fern':'fernB',c,r);
    else if(!forest && n<15) add(`flowers-${c}-${r}`,n%2?'lavender':'daisy',c,r);
  }
  if(calibration) {
    // Same live bindings; this view isolates the bridge, motion and player scale.
    scene.entities=scene.entities.filter(e=>e.id==='traveler'||e.id==='bell-tree'||e.id==='apothecary'||e.id.startsWith('rail')||e.id.startsWith('bank')||e.id.startsWith('lamp')||e.id.startsWith('flow'));
    world.smoke=world.smoke.slice(0,1);
    scene.entities[0]={id:'traveler',type:'traveler',c:11,r:11};
  }
  if(forest)for(let r=0;r<size;r++)for(let c=0;c<size;c++)if(scene.map[r]![c]==='grass'){const id=`forest-grass-${c%4}-${r%4}`;scene.tiles[id]={color:0x354f49,texture:id};scene.map[r]![c]=id;}
  return world;
}
