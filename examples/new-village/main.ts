import { createRuntime, createDpad, type Scene } from '../../src/index.ts';
import boundScene from './art/bound-ground-v5/scene.json';
import cottage from './art/cottage/measurement.json';
import workshop from './art/workshop/measurement.json';
import traveler from './art/traveler-final/runtime.json';
import layout from './layout.json';

const scene = structuredClone(boundScene) as Scene;
scene.name = 'Larkspur Crossing';
// The flush wooden surface is terrain; actors draw above it through native depth.
// No invented raised rails: the generated crossing has none.
scene.entities = scene.entities.filter(entity => !entity.id.startsWith('bridge-rail'));
const assets=scene.assets!;
assets.images['ground-binding-image']!.url=new URL('./art/registered-ground-v5/ground.png',import.meta.url).href;
assets.images.waterFlow={url:new URL('./art/water-flow-v3.png',import.meta.url).href,sampling:'nearest'};
for(let i=0;i<16;i++)assets.textures[`flow-${i}`]={image:'waterFlow',frame:{x:(i%4)*928,y:Math.floor(i/4)*464,width:928,height:464},anchor:{x:0,y:0}};
assets.animations={...assets.animations,streamFlow:{frames:Array.from({length:16},(_,i)=>`flow-${i}`),fps:6,loop:true}};
scene.entityTypes.streamFlow={blocking:false,visual:{kind:'sprite',animation:'streamFlow',width:928,anchor:{x:0,y:0},offset:{x:-32,y:-256}}};
scene.entities.push({id:'stream-flow',type:'streamFlow',c:0,r:0});
assets.images.cottage={url:new URL('./art/cottage/cottage.png',import.meta.url).href,sampling:'nearest'};
assets.textures.cottage={image:'cottage',anchor:cottage.anchor};
scene.entityTypes.cottage={blocking:true,columns:2,rows:2,bodyHeight:100,visual:{kind:'sprite',texture:'cottage',width:cottage.renderWidth}};
scene.entities.find(entity=>entity.id==='clay-hall')!.type='cottage';
assets.images.loomCottage={url:new URL('./art/cottage/loom-cottage.png',import.meta.url).href,sampling:'nearest'};
assets.textures.loomCottage={image:'loomCottage',anchor:cottage.anchor};
scene.entityTypes.loomCottage={...scene.entityTypes.cottage,visual:{kind:'sprite',texture:'loomCottage',width:cottage.renderWidth}};
scene.entities.find(entity=>entity.id==='loom-house')!.type='loomCottage';
for(const [id,image,url] of [['ferry-kitchen','workshop',new URL('./art/workshop/workshop.png',import.meta.url).href],['orchard-house','orchardWorkshop',new URL('./art/workshop/orchard-workshop.png',import.meta.url).href]]){
 assets.images[image!]={url:url!,sampling:'nearest'};assets.textures[image!]={image:image!,anchor:workshop.anchor};
 scene.entityTypes[image!]={blocking:true,columns:2,rows:2,bodyHeight:95,visual:{kind:'sprite',texture:image!,width:workshop.renderWidth}};
 scene.entities.find(entity=>entity.id===id)!.type=image!;
}
assets.images.elm={url:new URL('./art/elm/elm-wind.png',import.meta.url).href,sampling:'nearest'};
for(let i=0;i<4;i++)assets.textures[`elm-${i}`]={image:'elm',frame:{x:i*128,y:0,width:128,height:144},anchor:{x:.5,y:128/144}};
assets.animations!['tree.leaves.wind']={frames:['elm-0','elm-1','elm-2','elm-3'],fps:2,loop:true};
scene.entityTypes.elm={blocking:true,bodyHeight:100,visual:{kind:'sprite',animation:'tree.leaves.wind',width:128}};
for(const instance of layout.instances.filter(instance=>instance.kind==='tree'))scene.entities.push({id:instance.id,type:'elm',c:instance.footprint[0]![0] as number,r:instance.footprint[0]![1] as number});
Object.assign(assets.images,{traveler:{url:new URL('./art/traveler-final/traveler.png',import.meta.url).href,sampling:'nearest'}});
Object.assign(assets.textures,traveler.assets.textures);
Object.assign(assets.animations!,traveler.assets.animations);
// Four actual body facings; the nearest-view aliases remain explicit in the pack.
scene.entityTypes.traveler={blocking:true,bodyHeight:38,visual:{kind:'sprite',animation:'traveler.idle.se',width:48,animations:traveler.visualAnimations}};
async function bootstrap(){
const container=document.querySelector<HTMLDivElement>('#game')!;
const status=document.querySelector<HTMLElement>('#status')!;
const pause=document.querySelector<HTMLButtonElement>('#pause')!;
const runtime=await createRuntime({container,scene,speed:1.1,background:0x697984});
const mobile=matchMedia('(max-width:600px)').matches;
function follow(){
 if(!mobile)return;
 const pose=runtime.getEntityPose('traveler')!;
 const point=runtime.cellToScreen(pose.position);
 const camera=runtime.getCamera();
 runtime.setCamera({x:camera.x+container.clientWidth/2-point.x,y:camera.y+container.clientHeight*.52-point.y});
}
if(mobile){runtime.setCamera({zoom:.85});follow();}
const stopFollowing=runtime.on('move',({id})=>{if(id==='traveler')follow();});
const dpad=createDpad(runtime,document.querySelector<HTMLElement>('#dpad')!);
const names:Record<string,string>={'clay-hall':'Clay Hall','ferry-kitchen':'Ferry Kitchen','loom-house':'Loom House','orchard-house':'Orchard House'};
const unsubscribe=runtime.on('arrive',({id,cell})=>{if(id==='traveler'){const place=layout.instances.find(instance=>instance.approaches.some(([c,r])=>c===cell.c&&r===cell.r));status.textContent=place?names[place.id]??'By the village trees':'Along the brook';}});
pause.addEventListener('click',()=>{runtime.isPaused?runtime.resume():runtime.pause();pause.textContent=runtime.isPaused?'Continue':'Pause';});
status.textContent='Welcome to Larkspur';
container.focus();
// Read-only diagnostics plus public runtime methods for repeatable acceptance captures.
Object.assign(window,{__VILLAGE_QA__:{runtime,scene:()=>runtime.serializeScene(),screen:(c:number,r:number)=>runtime.cellToScreen({c,r}),pose:()=>runtime.getEntityPose('traveler')}});
if(import.meta.hot)import.meta.hot.dispose(()=>{stopFollowing();unsubscribe();dpad.destroy();runtime.destroy();});
}

void bootstrap();
