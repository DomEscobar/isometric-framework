import {createRuntime,createDpad,type AssetManifest} from '../../src/index.ts';
import {guideScene,playableScene} from './scene.ts';
import {origin,spawn,destination} from './layout.ts';

const params=new URLSearchParams(location.search);
const sources=import.meta.glob('./art/runtime.json',{eager:true,import:'default'});
const packed=sources['./art/runtime.json'] as AssetManifest|undefined;
const guide=params.has('guide')||!packed;
const native=params.has('native')||guide;
document.body.classList.toggle('native',native);
const game=document.querySelector<HTMLElement>('#game')!;
const assets=packed?structuredClone(packed):undefined;
const imageUrls=import.meta.glob(['./art/ground.png','./art/oak-*.png','./art/tree-front.png','./art/water-atlas.png','./art/empty.png'],{eager:true,query:'?url',import:'default'});
if(assets)for(const source of Object.values(assets.images)) source.url=imageUrls['./art/'+source.url] as string;
const runtime=await createRuntime({container:game,scene:guide?guideScene():playableScene(assets!,params.has('ground')),background:0x183c36,autoStart:!guide,input:!guide,speed:3.4});
let overview=false;
function camera(){
 const {width,height}=game.getBoundingClientRect();
 const zoom=native?1:overview?Math.min(3,width/256,height/224):width<500?2:Math.min(3,Math.floor(height/224)||1);
 const p=runtime.getEntityPose('traveler')?.position??spawn;
 const follow=!native&&!overview&&width<500;
 runtime.setCamera({zoom,x:follow?width/2-(p.c+p.r)*10*zoom:(width-256*zoom)/2+origin.x*zoom,y:follow?height*.57-(p.r-p.c)*5*zoom:(height-224*zoom)/2+origin.y*zoom});
}
camera(); runtime.step(1/60);
const observer=new ResizeObserver(camera);observer.observe(game);
const offMove=runtime.on('move',()=>{if(game.clientWidth<500)camera();});
const status=document.querySelector<HTMLElement>('#status')!;
const offArrive=runtime.on('arrive',({id,cell})=>{if(id==='traveler')status.textContent=cell.c===destination.c&&cell.r===destination.r?'Du hast die Lichtung erreicht.':'Folge dem Weg über den Bach.';});
const dpad=!guide?createDpad(runtime,document.querySelector<HTMLElement>('#dpad')!):undefined;
document.querySelector('#cross')!.addEventListener('click',()=>runtime.moveTo('traveler',destination));
document.querySelector('#return')!.addEventListener('click',()=>runtime.moveTo('traveler',spawn));
document.querySelector('#overview')!.addEventListener('click',()=>{overview=!overview;camera();});
document.querySelector('#pause')!.addEventListener('click',e=>{if(runtime.isPaused)runtime.resume();else runtime.pause();(e.currentTarget as HTMLButtonElement).textContent=runtime.isPaused?'Weiter':'Pause';});
document.querySelector('#layers')!.addEventListener('click',()=>{const url=new URL(location.href);if(url.searchParams.has('ground'))url.searchParams.delete('ground');else url.searchParams.set('ground','1');location.href=url.href;});
Object.assign(window,{mossbend:{runtime,ready:true,guide,source:assets,camera,spawn,destination}});
window.addEventListener('pagehide',()=>{offMove();offArrive();observer.disconnect();dpad?.destroy();runtime.destroy();},{once:true});
