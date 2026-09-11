import assert from 'node:assert/strict';
import {trees,wet,path,deck,spawn,destination,SIZE} from './layout.ts';
for(const t of trees){assert(!wet(t.c,t.r),`${t.id} is planted in water`);assert(!path(t.c,t.r),`${t.id} is planted on a reserved path`)}
const seen=new Set([`${spawn.c},${spawn.r}`]),queue=[spawn];
for(const p of queue)for(const [dc,dr] of [[1,0],[-1,0],[0,1],[0,-1]]){
 const c=p.c+dc,r=p.r+dr,key=`${c},${r}`;
 if(c<0||r<0||c>=SIZE||r>=SIZE||seen.has(key)||(wet(c,r)&&!deck(c,r))||trees.some(t=>t.c===c&&t.r===r))continue;
 seen.add(key);queue.push({c,r});
}
assert(seen.has(`${destination.c},${destination.r}`));
console.log(JSON.stringify({treesOnSupportedPlanting:trees.length,destinationReachable:true,reachableCells:seen.size}));
