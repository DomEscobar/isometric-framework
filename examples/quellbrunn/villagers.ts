import {route,fromCell,type Point} from './world.ts';
import type {Person} from './render.ts';
// Each resident follows the same supported ground as the player, at their own pace.
export function createVillagers(people:Person[]){
 const schedules:Point[][]=[[{c:12,r:16},{c:7.25,r:8.5},{c:19,r:17},{c:20.25,r:8.5}], [{c:30,r:18},{c:34.5,r:20},{c:34.5,r:30.5},{c:29.25,r:34.5}], [{c:23,r:33},{c:14.5,r:33},{c:14.5,r:18},{c:25,r:18}]];
 const residents=people.map((person,i)=>({person,stops:schedules[i]!,index:0,path:[] as Point[],wait:i*.6}));
 return{update(dt:number){for(const r of residents){const p=r.person;p.moving=false;if(r.wait>0){r.wait-=dt;continue;}if(!r.path.length){r.index=(r.index+1)%r.stops.length;r.path=(route(p,r.stops[r.index]!)??[]).map(fromCell);if(!r.path.length){r.wait=1;continue;}}
 let remaining=dt*(2.1+p.color*.2);while(remaining>0&&r.path.length){const next=r.path[0]!,dc=next.c-p.c,dr=next.r-p.r,d=Math.hypot(dc,dr);if(d>.001){p.facing=Math.abs(dc)>Math.abs(dr)?(dc>0?0:3):(dr>0?2:1);p.moving=true;}if(d<=remaining){Object.assign(p,next);r.path.shift();remaining-=d;}else{p.c+=dc/d*remaining;p.r+=dr/d*remaining;remaining=0;}}if(p.moving)p.walk=(p.walk+dt*2)%1;if(!r.path.length)r.wait=1.8+p.color*.4;
 }},get states(){return residents.map(r=>({...r.person,remaining:r.path.length,stop:r.index,wait:r.wait}))}};
}
