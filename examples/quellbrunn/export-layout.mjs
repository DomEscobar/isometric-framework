import {writeFile} from 'node:fs/promises';
import {cells,fromCell,canEnter,nearest,spawn,houses,trees,gardens,bridges,riverCenter,riverHalf,solid,toCell} from './world.ts';
import {findPath} from '../../src/core.ts';
const key=c=>`${c.c},${c.r}`,cell=c=>[c.c,c.r,'ground'],land=[],water=[],planting=[],instances=[],decks=new Map(bridges.map(b=>[b.id,[]]));
const plantKeys=new Set();
for(const h of houses){const fp=[];for(let r=Math.ceil(h.r*4);r<=Math.floor((h.r+5)*4);r++)for(let c=Math.ceil(h.c*4);c<=Math.floor((h.c+5)*4);c++)fp.push([c,r,'ground']);const approach=[Math.ceil(h.c*4)-1,Math.round((h.r+2.5)*4),'ground'];instances.push({id:h.id,kind:'building',footprint:fp,support:'planting',solid:true,approaches:[approach]});fp.forEach(p=>plantKeys.add(p[0]+','+p[1]));}
for(const t of trees){const fp=[];for(let r=Math.floor((t.r-.55)*4);r<=Math.ceil((t.r+.55)*4);r++)for(let c=Math.floor((t.c-.55)*4);c<=Math.ceil((t.c+.55)*4);c++)if(Math.hypot(c/4-t.c,r/4-t.r)<.55&&!plantKeys.has(c+','+r))fp.push([c,r,'ground']);if(fp.length){instances.push({id:t.id,kind:'tree',footprint:fp,support:'planting',solid:true,approaches:[]});fp.forEach(p=>plantKeys.add(p[0]+','+p[1]));}}
for(const g of gardens)for(let r=g.r*4;r<=(g.r+g.h)*4;r++)for(let c=g.c*4;c<=(g.c+g.w)*4;c++)plantKeys.add(c+','+r);
// Region geometry includes supported approach cells; conservative actor radius is a host-level check.
const routeKeys=new Set(cells.map(key));for(const i of instances)for(const p of i.approaches)routeKeys.add(p[0]+','+p[1]);
for(let r=0;r<=160;r++)for(let c=0;c<=192;c++){const p={c:c/4,r:r/4},v=[c,r,'ground'];if(plantKeys.has(c+','+r)){planting.push(v);continue;}if(Math.abs(p.r-riverCenter(p.c))<=riverHalf)water.push(v);else land.push(v);for(const b of bridges)if(p.c>=b.minC+.4&&p.c<=b.maxC-.4&&p.r>=b.minR&&p.r<=b.maxR)decks.get(b.id).push(v);}
const bridgeData=bridges.map(b=>{const deck=decks.get(b.id);const rows=[...new Set(deck.map(p=>p[1]))].sort((a,b)=>a-b),mid=Math.round(b.c*4);return{id:b.id,deck,landings:[[mid,rows[0],'ground'],[mid,rows.at(-1),'ground']],waterOverlayCells:[]}});
const exported={version:1,spawn:cell(toCell(spawn)),regions:[{id:'land',kind:'grass',cells:land},{id:'water',kind:'water',cells:water},{id:'planting',kind:'planting',cells:planting}],instances,routes:[{id:'village-ground',cells:[...routeKeys].map(k=>[...k.split(',').map(Number),'ground']),start:cell(toCell(spawn)),goals:houses.map(h=>cell(nearest(h.door))),clearanceCells:0}],bridges:bridgeData};
await writeFile(new URL('./layout.json',import.meta.url),JSON.stringify(exported));
await writeFile(new URL('./geometry-targets.json',import.meta.url),JSON.stringify({projection:{tileWidth:32,tileHeight:16,heightPixelsPerUnit:20},houseBase:{columns:5,rows:5},doors:houses.map(h=>h.door),bridges},null,2));
for(const h of houses)if(!findPath(toCell(spawn),nearest(h.door),canEnter,()=>true,false))throw Error(h.id+' unreachable');
console.log(JSON.stringify({walkable:cells.length,houses:houses.length,bridges:bridges.length,trees:trees.length}));
