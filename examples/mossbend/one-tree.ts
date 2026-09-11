import {createRuntime,attachKeyboard,type Scene} from '../../src/index.ts';
import originalUrl from './art/one-tree/original.png?url';
import groundUrl from './art/one-tree/ground.png?url';
import treeUrl from './art/one-tree/tree.png?url';
import sam3TreeUrl from './art/sam3-tree/tree.png?url';

const sam3=new URLSearchParams(location.search).has('sam3');
const [original,ground,tree]=await Promise.all([originalUrl,sam3?originalUrl:groundUrl,sam3?sam3TreeUrl:treeUrl].map(url=>new Promise<HTMLImageElement>((resolve,reject)=>{const im=new Image();im.onload=()=>resolve(im);im.onerror=()=>reject(new Error('Image failed: '+url));im.src=url})));
if(sam3){
 document.querySelector('h1')!.textContent='Ein Baum, automatisch maskiert';
 document.querySelector('header p')!.textContent='Das vollständige Landschaftsbild bleibt erhalten. Die SAM-3-Maske legt die Originalpixel des linken Baums vor die Figur, wenn sie dahinter steht.';
 document.querySelector('[data-mode=ground]')!.textContent='Verdeckung aus';
 document.querySelector('footer small')!.textContent='Pfeiltasten/WASD oder ins Bild tippen. SAM 3, erster Aufruf, Kandidat 01; keine manuelle Maskenkorrektur. Feste Kamera, ein Baum.';
}
const canvas=document.querySelector<HTMLCanvasElement>('#picture')!,ctx=canvas.getContext('2d')!;
ctx.imageSmoothingEnabled=false;
// Coordinates are derived from the existing picture, not an imposed art layout.
// Local 8x4 grid: measured trunk center is (45,130), at local cell (5,3).
const origin={x:13,y:134};const front={c:2,r:6},behind={c:7,r:1};
const scene:Scene={version:1,name:'One tree traversal test',tileWidth:8,tileHeight:4,diagonal:false,map:Array.from({length:9},(_,r)=>Array.from({length:9},(_,c)=>c+r<5||c+r>12?'edge':'ground')),tiles:{ground:{color:0x58784a},edge:{color:0x183c36,walkable:false}},entityTypes:{traveler:{visual:{kind:'actor',scale:.3},blocking:true,bodyHeight:15},trunk:{visual:{kind:'box',height:20},blocking:true,columns:3,rows:3,bodyHeight:20}},entities:[{id:'traveler',type:'traveler',...front},{id:'trunk',type:'trunk',c:4,r:2}],controlledId:'traveler'};
const runtime=await createRuntime({container:document.querySelector<HTMLElement>('#logical')!,scene,input:false,speed:3.5});
const detachKeyboard=attachKeyboard(runtime,document.querySelector<HTMLElement>('#stage')!);
let mode='assembled',showActor=true,time=0;
let previous={...front},moving=false;
function actor(x:number,y:number){
 const step=moving?Math.floor(time*8)%2:0;
 ctx.fillStyle='#192d25';ctx.fillRect(x-4,y,9,2);
 ctx.fillStyle='#604637';ctx.fillRect(x-3,y-5,3,5-step);ctx.fillRect(x+1,y-5+step,3,5-step);
 ctx.fillStyle='#dc9a52';ctx.fillRect(x-4,y-11,9,7);
 ctx.fillStyle='#f7d79b';ctx.fillRect(x-3,y-17,7,7);
 ctx.fillStyle='#473429';ctx.fillRect(x-4,y-18,8,3);ctx.fillRect(x+2,y-12,1,1);
}
function draw(){
 const p=runtime.getEntityPose('traveler')!.position;
 const x=Math.round(origin.x+(p.c+p.r)*4),y=Math.round(origin.y+(p.r-p.c)*2);
 ctx.clearRect(0,0,256,224);ctx.drawImage(mode==='original'?original:ground,0,0);
 const back=y<130;
 if(showActor&&back)actor(x,y);
 if(mode==='assembled')ctx.drawImage(tree,0,0);
 if(showActor&&!back)actor(x,y);
 // Original mode is an intentionally flat source comparison, not a depth test.
 if(showActor&&back&&mode==='original')actor(x,y);
}
const offFrame=runtime.on('frame',({deltaSeconds})=>{time+=deltaSeconds;const p=runtime.getEntityPose('traveler')!.position;moving=Math.abs(p.c-previous.c)+Math.abs(p.r-previous.r)>.001;previous={...p};draw();});
const status=document.querySelector<HTMLElement>('#status')!;
const offArrive=runtime.on('arrive',({id,cell})=>{if(id==='traveler')status.textContent=cell.c===behind.c&&cell.r===behind.r?'Die Figur steht hinter dem Baum.':'Die Figur steht auf dem begehbaren Boden.';});
document.querySelectorAll<HTMLButtonElement>('[data-mode]').forEach(button=>button.addEventListener('click',()=>{mode=button.dataset.mode!;document.querySelectorAll('[data-mode]').forEach(b=>b.setAttribute('aria-pressed',String(b===button)));draw();}));
document.querySelector<HTMLButtonElement>('#actor')!.onclick=e=>{showActor=!showActor;const b=e.currentTarget as HTMLButtonElement;b.textContent=showActor?'Figur ausblenden':'Figur einblenden';b.setAttribute('aria-pressed',String(showActor));draw();};
document.querySelector<HTMLButtonElement>('#front')!.onclick=()=>{runtime.moveTo('traveler',front);status.textContent='Die Figur läuft vor den Baum.'};
document.querySelector<HTMLButtonElement>('#behind')!.onclick=()=>{runtime.moveTo('traveler',behind);status.textContent='Die Figur läuft hinter den Baum.'};
document.querySelector<HTMLButtonElement>('#pause')!.onclick=e=>{if(runtime.isPaused)runtime.resume();else runtime.pause();(e.currentTarget as HTMLButtonElement).textContent=runtime.isPaused?'Weiter':'Pause';};
canvas.addEventListener('pointerdown',e=>{document.querySelector<HTMLElement>('#stage')!.focus();const b=canvas.getBoundingClientRect(),x=(e.clientX-b.left)*256/b.width-origin.x,y=(e.clientY-b.top)*224/b.height-origin.y;runtime.moveTo('traveler',{c:Math.round(x/8-y/4),r:Math.round(x/8+y/4)});});
draw();Object.assign(window,{oneTree:{runtime,ready:true,front,behind,getState:()=>({mode,showActor,pose:runtime.getEntityPose('traveler'),time})}});
window.addEventListener('pagehide',()=>{offFrame();offArrive();detachKeyboard();runtime.destroy();},{once:true});
