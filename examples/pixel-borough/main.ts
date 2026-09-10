import { createRuntime, createInteractions, createDpad, type InteractionAction } from '../../src/index.ts';
import { makeScene, creatureNames, bridgeRoute } from './scene.ts';
const game=document.querySelector<HTMLElement>('#game')!;
const status=document.querySelector<HTMLElement>('#status')!;
const groundOnly=new URLSearchParams(location.search).has('ground');
async function start(){
const runtime=await createRuntime({container:game,scene:makeScene(groundOnly),speed:4,background:0x467184,clickToMove:false,keyboard:false});
const greeted=new Set<string>();const responseTimers=new Map<string,number>();let disposed=false;let follow=innerWidth<600;
function message(){status.textContent=greeted.size===3?'Three new friends! The borough is yours to explore.':`Meet the locals · ${greeted.size}/3 friends · Click a creature to say hello.`;}
const actions=createInteractions(runtime,{onError:error=>{status.textContent=error.message;}});
const greeting:InteractionAction={id:'hello',prepareSeconds:.35,recoverSeconds:1,canPerform:({target})=>target.data?.creature===true,perform:({target})=>{greeted.add(target.id);runtime.setAnimation(target.id,target.id+'.greet');responseTimers.set(target.id,1.2);status.textContent=`${creatureNames[target.id]} ${target.id==='nib'?'rustles its leaf ears':target.id==='bramble'?'wiggles its fern frill':'flutters a happy hello'}! · ${greeted.size}/3 friends`;document.querySelector(`[data-friend="${target.id}"]`)?.classList.add('met');return true;}};
function greet(id:string){follow=true;runtime.setCamera({zoom:innerWidth<600?1.6:1.5});if(!actions.request({actorId:'explorer',targetId:id,action:greeting}))status.textContent='Find a clear path closer to this little friend.';game.focus();}
runtime.on('tileclick',({cell,entityIds})=>{const creature=entityIds.find(id=>id in creatureNames);if(creature){greet(creature);return;}actions.cancel('cancelled');runtime.moveTo('explorer',cell);});
runtime.on('frame',({deltaSeconds})=>{for(const [id,t]of responseTimers){if(t<=deltaSeconds){runtime.setAnimation(id,null);responseTimers.delete(id);}else responseTimers.set(id,t-deltaSeconds);}if(follow){const p=runtime.getEntityPose('explorer');if(p){const camera=runtime.getCamera();runtime.setCamera({x:game.clientWidth/2-(p.position.c+p.position.r)*24*camera.zoom,y:game.clientHeight*.48-(p.position.r-p.position.c)*12*camera.zoom});}}});
runtime.on('error',({error})=>{status.textContent=error.message;});runtime.on('pausechange',({paused})=>{document.querySelector('#pause')!.textContent=paused?'Resume':'Pause';});
function overview(){follow=false;const zoom=Math.min((game.clientWidth-36)/1152,(game.clientHeight-14)/640);runtime.setCamera({zoom,x:game.clientWidth/2-552*zoom,y:game.clientHeight/2+32*zoom});}
document.querySelector('#fit')!.addEventListener('click',()=>{overview();game.focus();});
document.querySelector('#follow')!.addEventListener('click',()=>{follow=true;runtime.setCamera({zoom:innerWidth<600?1.7:1.5});game.focus();});
document.querySelector('#pause')!.addEventListener('click',()=>{runtime.isPaused?runtime.resume():runtime.pause();game.focus();});
document.querySelector('#restart')!.addEventListener('click',async()=>{const camera=runtime.getCamera();const wasFollowing=follow;actions.cancel('cancelled');responseTimers.clear();greeted.clear();document.querySelectorAll('.met').forEach(el=>el.classList.remove('met'));try{await runtime.loadScene(makeScene(groundOnly));if(!disposed){follow=wasFollowing;runtime.setCamera(camera);runtime.resume();message();game.focus();}}catch(e){status.textContent='Could not restart: '+String(e);}});
document.querySelectorAll<HTMLButtonElement>('[data-friend]').forEach(el=>el.addEventListener('click',()=>greet(el.dataset.friend!)));
// Four-axis keyboard: last pressed direction wins. This preserves the published
// axes and avoids pretending that this four-view pack contains eight facings.
const vectors:Record<string,{x:number,y:number}>={w:{x:1,y:-.5},ArrowUp:{x:1,y:-.5},d:{x:1,y:.5},ArrowRight:{x:1,y:.5},s:{x:-1,y:.5},ArrowDown:{x:-1,y:.5},a:{x:-1,y:-.5},ArrowLeft:{x:-1,y:-.5}};
const held:string[]=[];
function release(){held.length=0;runtime.setMoveInput(null);}
function keydown(e:KeyboardEvent){if(!game.contains(document.activeElement))return;const key=e.key.length===1?e.key.toLowerCase():e.key;if(vectors[key]){e.preventDefault();if(!held.includes(key))held.push(key);runtime.setMoveInput(vectors[held.at(-1)!]!);}else if(e.key==='Escape'){actions.cancel('cancelled');release();}else if(key==='e'){const p=runtime.getEntity('explorer')!;const nearest=runtime.getEntities().filter(x=>x.data?.creature).sort((a,b)=>(Math.abs(a.c-p.c)+Math.abs(a.r-p.r))-(Math.abs(b.c-p.c)+Math.abs(b.r-p.r)))[0];if(nearest)greet(nearest.id);}}
function keyup(e:KeyboardEvent){const key=e.key.length===1?e.key.toLowerCase():e.key;const i=held.indexOf(key);if(i>=0){held.splice(i,1);runtime.setMoveInput(held.length?vectors[held.at(-1)!]!:null);}}
window.addEventListener('keydown',keydown);window.addEventListener('keyup',keyup);window.addEventListener('blur',release);game.addEventListener('blur',release);
const dpad=createDpad(runtime,document.querySelector<HTMLElement>('#dpad')!);
if(follow)runtime.setCamera({zoom:1.6});else overview();runtime.setFacing('resident-1','sw');runtime.setFacing('resident-2','ne');message();game.focus();
Object.assign(window,{borough:{runtime,actions,makeScene,greeted,greet,bridgeRoute,setFollow:(value:boolean)=>{follow=value;}}});
function dispose(){if(disposed)return;disposed=true;dpad.destroy();actions.destroy();runtime.destroy();window.removeEventListener('keydown',keydown);window.removeEventListener('keyup',keyup);window.removeEventListener('blur',release);game.removeEventListener('blur',release);}
window.addEventListener('pagehide',e=>{if(!e.persisted)dispose();});if(import.meta.hot)import.meta.hot.dispose(dispose);
}
void start().catch(error=>{status.textContent='Pixel Borough could not load. '+(error instanceof Error?error.message:String(error))+' Reload to retry.';status.setAttribute('role','alert');document.querySelectorAll<HTMLButtonElement>('button').forEach(button=>button.disabled=true);console.error('Pixel Borough startup failed',error);});
