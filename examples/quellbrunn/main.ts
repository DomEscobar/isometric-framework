import {createView,type Person} from './render.ts';
import {createEnvironment} from './environment.ts';
import {createVillagers} from './villagers.ts';
import {createGeneratedGround} from './generated-ground.ts';
import {spawn,route,fromCell,canStand,landmarks,bridges,type Point} from './world.ts';
const canvas=document.querySelector<HTMLCanvasElement>('canvas')!,view=await createView(canvas),environment=createEnvironment();
const generated=await createGeneratedGround(view.terrain);let generatedEnabled=new URLSearchParams(location.search).get('terrain')!=='original';
const hero:Person={...spawn,facing:2,walk:0,moving:false,color:0};
const people:Person[]=[hero,...[{c:12,r:16},{c:30,r:18},{c:23,r:33}].map((p,i)=>({...p,facing:2,walk:0,moving:false,color:i+1}))];let path:Point[]=[],target:Point|undefined,paused=false,debug=false,follow=innerWidth<650,time=0,last=performance.now(),key:string|undefined,tour:Point[]=[];
const villagers=createVillagers(people.slice(1));
let effects:((ctx:CanvasRenderingContext2D,time:number)=>void)|undefined;const intervals:number[]=[],history:Point[]=[];
const terrainButton=document.createElement('button');terrainButton.id='terrain';document.querySelector('footer>div')!.append(terrainButton);
function setGeneratedGround(value:boolean){generatedEnabled=value;view.setTerrain(value?generated.land:undefined);effects=value?generated.water:environment.water;terrainButton.textContent=value?'Boden: generiert':'Boden: vorher';terrainButton.setAttribute('aria-pressed',String(value));}
terrainButton.onclick=()=>setGeneratedGround(!generatedEnabled);setGeneratedGround(generatedEnabled);
const status=document.querySelector('#status')!,pauseButton=document.querySelector<HTMLButtonElement>('#pause')!;
if(innerWidth<650)view.focus(hero,1.3);else view.overview();
function go(point:Point,retain=false){const next=route(hero,point);if(!next){status.textContent='Hier ist Wasser oder ein Hindernis.';return false;}path=next.map(fromCell);target=point;if(!retain)tour=[];key=undefined;follow=true;paused=false;pauseButton.textContent='Pause';status.textContent='Unterwegs durch Quellbrunn.';return true;}
function visit(id:string){const p=landmarks.find(p=>p.id===id);return p?go(p):false;}
function nextStop(){while(tour.length){const p=tour.shift()!;if(go(p,true)&&path.length)return;}target=undefined;status.textContent='Wieder am Dorfplatz.';}
function startTour(){tour=[{c:14.5,r:18},{c:14.5,r:33},{c:30,r:30.5},{c:34.5,r:18},{c:22,r:18}];nextStop()}
function pause(){paused=!paused;pauseButton.textContent=paused?'Weiter':'Pause'}
document.querySelectorAll<HTMLButtonElement>('[data-place]').forEach(b=>b.onclick=()=>visit(b.dataset.place!));
document.querySelector<HTMLButtonElement>('#tour')!.onclick=startTour;pauseButton.onclick=pause;
document.querySelector<HTMLButtonElement>('#overview')!.onclick=()=>{follow=false;view.overview()};
document.querySelector<HTMLButtonElement>('#plus')!.onclick=()=>view.zoom(1.25);document.querySelector<HTMLButtonElement>('#minus')!.onclick=()=>view.zoom(.8);
document.querySelector<HTMLButtonElement>('#debug')!.onclick=()=>debug=!debug;
let pointer:{id:number;x:number;y:number;sx:number;sy:number;drag:boolean}|undefined;
canvas.addEventListener('pointerdown',e=>{pointer={id:e.pointerId,x:e.clientX,y:e.clientY,sx:e.clientX,sy:e.clientY,drag:false};canvas.setPointerCapture(e.pointerId)});
canvas.addEventListener('pointermove',e=>{if(!pointer||pointer.id!==e.pointerId)return;if(Math.hypot(e.clientX-pointer.sx,e.clientY-pointer.sy)>5)pointer.drag=true;if(pointer.drag){follow=false;view.pan(e.clientX-pointer.x,e.clientY-pointer.y)}pointer.x=e.clientX;pointer.y=e.clientY});
canvas.addEventListener('pointerup',e=>{if(pointer?.id===e.pointerId&&!pointer.drag)go(view.world({x:e.clientX,y:e.clientY}));pointer=undefined});canvas.addEventListener('pointercancel',()=>pointer=undefined);
canvas.addEventListener('wheel',e=>{e.preventDefault();view.zoom(e.deltaY<0?1.1:1/1.1)},{passive:false});
const axes:Record<string,[number,number,number]>={w:[1,0,0],arrowup:[1,0,0],d:[0,1,2],arrowright:[0,1,2],s:[-1,0,3],arrowdown:[-1,0,3],a:[0,-1,1],arrowleft:[0,-1,1]};
window.addEventListener('keydown',e=>{const k=e.key.toLowerCase();if(axes[k]){e.preventDefault();key=k;path=[];tour=[];target=undefined;follow=true;}else if(e.code==='Space'&&!e.repeat){e.preventDefault();pause()}});
window.addEventListener('keyup',e=>{if(key===e.key.toLowerCase())key=undefined});window.addEventListener('blur',()=>key=undefined);
window.addEventListener('resize',()=>{view.resize();if(follow)view.focus(hero);else view.overview()});document.addEventListener('visibilitychange',()=>last=performance.now());
function frame(now:number){const elapsed=(now-last)/1000;last=now;const dt=Math.min(.05,elapsed);if(elapsed>0&&elapsed<.2){intervals.push(elapsed*1000);if(intervals.length>1800)intervals.shift();}
if(!paused){time+=dt;hero.moving=false;if(key){const [dc,dr,face]=axes[key]!;hero.facing=face;const p={c:hero.c+dc*dt*5,r:hero.r+dr*dt*5};if(canStand(p)){Object.assign(hero,p);hero.moving=true;}}
else if(path.length){hero.moving=true;const ahead=path[Math.min(6,path.length-1)]!,dc=ahead.c-hero.c,dr=ahead.r-hero.r;hero.facing=Math.abs(dc)>Math.abs(dr)?(dc>0?0:3):(dr>0?2:1);let distance=dt*5;while(path.length&&distance>0){const p=path[0]!,dc=p.c-hero.c,dr=p.r-hero.r,d=Math.hypot(dc,dr);if(d<=distance){Object.assign(hero,p);path.shift();distance-=d;history.push({...p});}else{hero.c+=dc/d*distance;hero.r+=dr/d*distance;distance=0;}}if(!path.length){hero.moving=false;if(tour.length)nextStop();else{target=undefined;status.textContent='Hier kannst du weitergehen.';}}}
if(hero.moving)hero.walk=(hero.walk+dt*2.6)%1;villagers.update(dt);if(history.length>2000)history.splice(0,history.length-2000);if(follow)view.focus(hero);
}
view.draw(time,people,debug,effects?ctx=>effects!(ctx,time):undefined,target,{under:ctx=>environment.wheel(ctx,time),over:ctx=>environment.smoke(ctx,time)});requestAnimationFrame(frame)}
document.querySelector('#loading')!.remove();requestAnimationFrame(frame);
Object.assign(window,{quellbrunn:{ready:true,get state(){return{hero:{...hero},villagers:villagers.states,time,paused,remaining:path.length,tour:tour.length,history:history.length,scale:view.scale}},go,visit,startTour,screen:view.screen,world:view.world,canStand,
stats(){const a=[...intervals].sort((a,b)=>a-b);return{samples:a.length,median:a[Math.floor(a.length*.5)],p95:a[Math.floor(a.length*.95)]}},
inspect(p:Point,scale=1.5){if(!canStand(p))throw Error('Unsupported pose');Object.assign(hero,p,{moving:false});path=[];tour=[];target=undefined;paused=true;pauseButton.textContent='Weiter';follow=false;view.focus(p,scale)},
setEffects(fn:typeof effects){effects=fn},setGroundOnly:view.setGroundOnly,setGeneratedGround,generated,inspectTime(value:number){if(!paused)throw Error('Pause first');time=value},people}});
