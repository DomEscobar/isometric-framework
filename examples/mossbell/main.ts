import { createRuntime, createDpad, createInteractions, createDebugOverlay, type Cell, type InteractionAction, type Runtime } from '../../src/index';
import { createWorld, key, type Region, type Progress, type Landmark } from './scene';
import { Atmosphere } from './atmosphere';
import { Soundscape } from './audio';
import './style.css';

document.querySelector('#app')!.innerHTML=`
<main class="experience" data-region="town">
  <div id="world" tabindex="0" role="application" aria-label="Explore Mossbell. Click to walk, W A S D to move, E to follow your next discovery."></div>
  <canvas id="atmosphere" aria-hidden="true"></canvas><div class="vignette" aria-hidden="true"></div>
  <header class="masthead"><a class="wordmark" href="../../" aria-label="Isometric Framework examples"><span class="sigil">✧</span> MOSSBELL</a><div class="edition">AN EVENING BETWEEN WORLDS</div></header>
  <section class="place-title"><div class="eyebrow"><span class="live-dot"></span><span id="region-kicker">THE LAST LIGHT OF HOME</span></div><h1 id="region-title">Mossbell<span>.</span></h1><p id="region-description">Warm windows. Wandering thoughts.<br>A little magic just beyond the trees.</p></section>
  <nav class="top-tools" aria-label="World controls"><button id="sound" aria-pressed="false" title="Enable atmospheric sound">♫ <span>Enable sound</span></button><button id="pause" aria-pressed="false" title="Pause world">Ⅱ <span>Pause</span></button><button id="settings-toggle" aria-expanded="false" aria-controls="settings" title="Sound and view settings">☷</button></nav>
  <aside id="settings" class="panel settings" hidden><h2>Make yourself at home</h2><label>Ambience <input id="ambience-volume" type="range" min="0" max="100" value="65"></label><label>Footsteps & effects <input id="effects-volume" type="range" min="0" max="100" value="70"></label><button id="debug-toggle" aria-pressed="false">Show world diagnostics</button><button id="restart">Begin a new evening</button><p>Sound is synthesized locally.<br>No downloads or account needed.</p></aside>
  <div id="markers" aria-label="Nearby places"></div>
  <aside class="journey panel"><div class="chapter"><span id="chapter-number">01</span><span id="chapter-label">A WHISPER IN THE TREES</span><span class="chapter-line"></span><span id="progress-icon">✧</span></div><h2 id="quest-title">The forest is calling.</h2><p id="quest-copy">Across the bridge, something glows between the branches.</p><button id="quest-action" class="primary">Follow the forest lights <span>↗</span></button><button id="places-toggle" class="text-button" aria-expanded="false" aria-controls="places">Or take the long way <span>＋</span></button><div id="places" hidden></div></aside>
  <div class="region-pair" aria-label="Connected worlds"><span id="town-label" class="active">01 · Mossbell</span><i>········</i><span id="forest-label">02 · Bellshade</span></div>
  <div id="toast" role="status" aria-live="polite">Take your time. The evening is yours.</div>
  <div class="view-tools" aria-label="Camera"><button id="zoom-out" aria-label="Zoom out">−</button><button id="fit" aria-label="Show whole world">⌗</button><button id="zoom-in" aria-label="Zoom in">＋</button><button id="follow" aria-pressed="false" aria-label="Follow traveler">◎</button></div>
  <div id="touch-controls" aria-label="Movement controls"></div>
  <footer><span class="controls-hint"><kbd>W</kbd><kbd>A</kbd><kbd>S</kbd><kbd>D</kbd> wander <b>·</b> click a path <b>·</b> drag to look around</span><span class="footer-note">A SMALL WORLD, FULL OF WONDER <span>✦</span></span></footer>
  <div id="transition" class="transition visible"><span>✧</span><p id="transition-text">An evening is taking shape…</p></div>
  <div id="debug-panel" hidden></div>
</main>`;

const el=<T extends HTMLElement=HTMLElement>(id:string)=>document.getElementById(id) as T;
const ui=document.querySelector<HTMLElement>('.experience')!;
const lifecycle=new AbortController(),sound=new Soundscape();
let disposed=false,transitioning=false,region:Region='town',runtime:Runtime|undefined,cleanup:(()=>void)|undefined;
let progress:Progress='seeking',follow=innerWidth<700,time=0,lastNpc=0,manualPause=false;
const calibration=new URLSearchParams(location.search).has('calibration');
try{const saved=localStorage.getItem('mossbell-progress-v1');if(saved==='seed'||saved==='planted')progress=saved;}catch{ /* Storage is optional. */ }
let world=createWorld(region,progress,false,calibration);
const message=(text:string)=>{el('toast').textContent=text;};
const on=(id:string,fn:(event:MouseEvent)=>void)=>el(id).addEventListener('click',fn,{signal:lifecycle.signal});
const save=()=>{try{localStorage.setItem('mossbell-progress-v1',progress);}catch{message('Your discovery stays with you for this visit; storage is unavailable.');}};
const delay=(ms:number)=>new Promise<void>(resolve=>setTimeout(resolve,ms));

async function start(){
  const rt=runtime=await createRuntime({container:el('world'),scene:world.scene,background:0x101c28,speed:3.3,clickToMove:false,jump:{height:25,distance:1,duration:.6}});
  if(disposed){rt.destroy();return;}
  const atmosphere=new Atmosphere(el<HTMLCanvasElement>('atmosphere'),rt,world,progress);
  const dpad=createDpad(rt,el('touch-controls'));
  const debug=createDebugOverlay(rt,{container:el('world'),panel:el('debug-panel')});
  sound.setWorld(world);
  const actions=createInteractions(rt,{onError:error=>message(error.message),onChange:state=>{ui.dataset.action=state.phase;}});
  const springAction:InteractionAction={id:'listen',prepareSeconds:1.5,recoverSeconds:.7,canPerform:()=>progress==='seeking',perform:()=>{progress='seed';save();atmosphere.setProgress(progress);sound.chime();updateUi();message('The spring opens like a flower. A luminous seed settles into your hands.');return true;}};
  const plantAction:InteractionAction={id:'plant',prepareSeconds:1.2,recoverSeconds:.6,canPerform:()=>progress==='seed',perform:()=>{if(rt.getEntity('final-bloom'))return false;rt.add({id:'final-bloom',type:'bloom',c:8,r:6});progress='planted';save();atmosphere.setProgress(progress);sound.chime();updateUi();message('A little of the forest now grows at home. Both worlds are yours to wander.');return true;}};
  const focus=()=>el('world').focus({preventScroll:true});
  const centerPlayer=()=>{const pose=rt.getEntityPose('traveler');if(!pose)return;const cam=rt.getCamera(),p={x:(pose.position.c+pose.position.r)*32*cam.zoom+cam.x,y:(pose.position.r-pose.position.c)*16*cam.zoom+cam.y-pose.elevation*cam.zoom},rect=el('world').getBoundingClientRect();rt.setCamera({x:cam.x+rect.width*.53-p.x,y:cam.y+rect.height*(innerWidth<700?.48:.53)-p.y});};
  const fit=()=>{
    const rect=el('world').getBoundingClientRect(),size=world.scene.map.length;
    if(follow){rt.setCamera({zoom:innerWidth<700?1.05:1.1});centerPlayer();}
    else {const zoom=Math.min((rect.width-(innerWidth<700?8:80))/(size*64+8),(rect.height-150)/(size*32+230),1.15);rt.setCamera({zoom,x:rect.width/2-(size-1)*32*zoom,y:rect.height/2+90*zoom});}
    atmosphere.draw();updateMarkers();
  };
  async function transition(next:Region){
    if(transitioning||disposed||rt.isPaused)return;
    transitioning=true;actions.cancel();rt.stop('traveler');rt.setMoveInput(null);rt.pause();
    el('transition-text').textContent=next==='forest'?'Beyond the last lantern…':'The warm windows of home…';el('transition').classList.add('visible');
    const candidate=createWorld(next,progress,next==='town');
    try{
      await delay(450);if(disposed)return;
      await rt.loadScene(candidate.scene);if(disposed)return;
      region=next;world=candidate;time=0;lastNpc=0;sound.setWorld(world);atmosphere.setWorld(world,progress);updateUi();fit();
      message(next==='forest'?'The air turns cool. Somewhere ahead, the spring is singing.':'The village welcomes you back.');
      await delay(350);
    }catch(error){message(`The path could not open: ${error instanceof Error?error.message:String(error)}`);}
    finally{if(!disposed){transitioning=false;el('transition').classList.remove('visible');if(!manualPause&&!document.hidden)rt.resume();focus();}}
  }
  function navigate(place:Landmark){
    if(transitioning||rt.isPaused)return;
    if(innerWidth<700&&!follow){follow=true;el('follow').setAttribute('aria-pressed','true');fit();}
    actions.cancel();focus();
    if(place.kind==='spring'&&progress==='seeking'){if(actions.request({actorId:'traveler',targetId:'spring-heart',action:springAction}))message('Follow the stream. Listen closely at the spring.');else message('Move closer to the spring along the open trail.');return;}
    if(place.kind==='plant'){
      if(progress==='seed'){actions.request({actorId:'traveler',targetId:'seedbed',action:plantAction});message('A small seed. A place to begin.');}
      else message(progress==='planted'?'Your moonflower is home.':'This bed is waiting for a seed from Bellshade.');return;
    }
    const result=rt.moveTo('traveler',place.cell);
    if(result==='blocked'){message('That approach is blocked. Try the neighboring path.');return;}
    message(place.description);
    if(result==='arrived'&&place.kind==='portal')void transition(region==='town'?'forest':'town');
  }
  function quest(){
    const id=region==='forest'?(progress==='seeking'?'spring-heart':'town-gate'):(progress==='seed'?'seedbed':'forest-gate');
    const place=world.landmarks.find(p=>p.id===id);if(place)navigate(place);
  }
  function updateMarkers(){
    for(const place of world.landmarks){const marker=document.querySelector<HTMLElement>(`[data-marker="${place.id}"]`);if(!marker)continue;const p=rt.cellToScreen(place.cell);marker.style.transform=`translate(${p.x}px,${p.y-24*rt.getCamera().zoom}px) translate(-50%,-100%)`;marker.hidden=p.x<30||p.x>innerWidth-30||p.y<65||p.y>innerHeight-60;}
  }
  function updateUi(){
    ui.dataset.region=region;ui.dataset.progress=progress;el('region-title').innerHTML=region==='town'?'Mossbell<span>.</span>':'Bellshade<span>.</span>';
    el('region-kicker').textContent=region==='town'?'THE LAST LIGHT OF HOME':'WHERE THE FOREST REMEMBERS';
    el('region-description').innerHTML=region==='town'?'Warm windows. Wandering thoughts.<br>A little magic just beyond the trees.':'Follow the water. Trust the glow.<br>Some places have been waiting for you.';
    el('town-label').classList.toggle('active',region==='town');el('forest-label').classList.toggle('active',region==='forest');
    el('chapter-number').textContent=progress==='planted'?'03':region==='forest'||progress==='seed'?'02':'01';
    el('chapter-label').textContent=progress==='planted'?'A LITTLE MAGIC, BROUGHT HOME':progress==='seed'?'SOMETHING WORTH CARRYING':region==='forest'?'THE SONG BENEATH THE ROOTS':'A WHISPER IN THE TREES';
    el('quest-title').textContent=progress==='planted'?'You made a little wonder.':progress==='seed'?'Carry the light home.':region==='forest'?'Something stirs below.':'The forest is calling.';
    el('quest-copy').textContent=progress==='planted'?'A moonflower blooms by the apothecary. There is still an evening to explore.':progress==='seed'?'A luminous seed rests in your hands. The little bed by the apothecary is waiting.':region==='forest'?'Past the fallen crossing, a spring glows beneath the ancient bell tree.':'Across the bridge, something glows between the branches.';
    el('quest-action').innerHTML=`${region==='forest'?(progress==='seeking'?'Listen to the spring':'Return to Mossbell'):(progress==='seed'?'Plant the luminous seed':progress==='planted'?'Wander into Bellshade':'Follow the forest lights')} <span>↗</span>`;
    el('progress-icon').textContent=progress==='seeking'?'✧':progress==='seed'?'❧':'✿';
    el('places').replaceChildren();el('markers').replaceChildren();
    for(const place of world.landmarks){
      const button=document.createElement('button');button.textContent=place.name;button.addEventListener('click',()=>navigate(place));el('places').append(button);
      if(place.kind==='portal'||place.kind==='spring'||place.kind==='plant'&&progress==='seed'){
        const marker=document.createElement('button');marker.className='map-marker';marker.dataset.marker=place.id;marker.innerHTML=`<span>${place.kind==='portal'?'↗':'✧'}</span> ${place.name}`;marker.addEventListener('click',()=>navigate(place));el('markers').append(marker);
      }
    }
    updateMarkers();
  }
  const subscriptions=[
    rt.on('tileclick',({cell,entityIds})=>{if(transitioning||rt.isPaused)return;const place=world.landmarks.find(p=>key(p.cell)===key(cell)||entityIds.includes(p.id));if(place){navigate(place);return;}actions.cancel();const result=rt.moveTo('traveler',cell);if(result==='blocked')message('The path winds around that. Try the open ground.');}),
    rt.on('arrive',({id,cell})=>{if(id!=='traveler')return;const place=world.landmarks.find(p=>key(p.cell)===key(cell));if(place?.kind==='portal')queueMicrotask(()=>{if(!disposed)void transition(region==='town'?'forest':'town');});}),
    rt.on('move',({id,position})=>{if(id!=='traveler')return;sound.footstep(position,world.scene.map[Math.round(position.r)]?.[Math.round(position.c)]??'grass');if(follow)centerPlayer();}),
    rt.on('frame',({deltaSeconds})=>{
      time+=deltaSeconds;atmosphere.step(deltaSeconds);const player=rt.getEntityPose('traveler');if(player)sound.step(deltaSeconds,player.position);
      if(time-lastNpc>8&&!transitioning){lastNpc=time;const phase=Math.floor(time/8)%2;
        if(region==='forest'){rt.moveTo('leafling',{c:phase?15:13,r:11});rt.moveTo('leafling-friend',{c:phase?19:17,r:19});}
        else{rt.moveTo('herbalist',{c:phase?7:9,r:7});rt.moveTo('reader',{c:18,r:phase?8:7});}
      }
    }),
    rt.on('camerachange',()=>{atmosphere.draw();updateMarkers();}),
    rt.on('pausechange',({paused})=>{sound.setPaused(paused&&!transitioning);el('pause').setAttribute('aria-pressed',String(paused));el('pause').innerHTML=paused?'▷ <span>Resume</span>':'Ⅱ <span>Pause</span>';ui.dataset.paused=String(paused);}),
    rt.on('error',({error})=>message(error.message)),
  ];
  on('quest-action',quest);
  on('pause',()=>{if(transitioning)return;manualPause=!manualPause;if(manualPause)rt.pause();else if(!document.hidden)rt.resume();focus();});
  on('sound',()=>{void sound.toggle().then(enabled=>{el('sound').setAttribute('aria-pressed',String(enabled));el('sound').innerHTML=enabled?'♫ <span>Sound on</span>':'♫ <span>Sound off</span>';}).catch(()=>message('Sound could not start in this browser.'));});
  on('settings-toggle',()=>{const hidden=!el('settings').hidden;el('settings').hidden=hidden;el('settings-toggle').setAttribute('aria-expanded',String(!hidden));});
  for(const id of ['ambience-volume','effects-volume'])el(id).addEventListener('input',()=>sound.levels(Number(el<HTMLInputElement>('ambience-volume').value)/100,Number(el<HTMLInputElement>('effects-volume').value)/100),{signal:lifecycle.signal});
  on('places-toggle',()=>{el('places').hidden=!el('places').hidden;el('places-toggle').setAttribute('aria-expanded',String(!el('places').hidden));});
  on('fit',()=>{follow=false;el('follow').setAttribute('aria-pressed','false');fit();});
  on('follow',()=>{follow=!follow;el('follow').setAttribute('aria-pressed',String(follow));if(follow)fit();});
  for(const [id,factor] of [['zoom-in',1.2],['zoom-out',1/1.2]] as const)on(id,()=>{const cam=rt.getCamera(),rect=el('world').getBoundingClientRect(),zoom=Math.min(2,Math.max(.35,cam.zoom*factor)),ratio=zoom/cam.zoom;rt.setCamera({zoom,x:rect.width/2-(rect.width/2-cam.x)*ratio,y:rect.height/2-(rect.height/2-cam.y)*ratio});});
  on('debug-toggle',()=>{const enabled=el('debug-toggle').getAttribute('aria-pressed')!=='true';el('debug-toggle').setAttribute('aria-pressed',String(enabled));debug.setEnabled(enabled);el('debug-panel').hidden=!enabled;});
  on('restart',()=>{try{localStorage.removeItem('mossbell-progress-v1');}catch{ /* optional */ }location.reload();});
  el('world').addEventListener('keydown',event=>{if(event.key.toLowerCase()==='e'){event.preventDefault();quest();}if(event.key==='Escape'){actions.cancel();el('settings').hidden=true;}},{signal:lifecycle.signal});
  document.addEventListener('visibilitychange',()=>{sound.setHidden(document.hidden);if(document.hidden)rt.pause();else if(!manualPause&&!transitioning)rt.resume();},{signal:lifecycle.signal});
  window.addEventListener('resize',()=>{if(follow)centerPlayer();atmosphere.draw();updateMarkers();},{signal:lifecycle.signal});
  cleanup=()=>{subscriptions.forEach(fn=>fn());actions.destroy();dpad.destroy();debug.destroy();sound.destroy();rt.destroy();};
  // Explicit authoring surface: public runtime APIs only; no private renderer access.
  Object.assign(window,{__MOSSBELL__:{runtime:rt,getWorld:()=>structuredClone(world),snapshot:()=>({region,progress,transitioning,time,atmosphereTime:atmosphere.time,action:actions.getState(),audio:sound.snapshot(),debug:rt.getDebugSnapshot()}),captureAudio:(seconds:number)=>sound.capture(seconds)}});
  updateUi();fit();el('follow').setAttribute('aria-pressed',String(follow));el('transition').classList.remove('visible');focus();
}
const dispose=()=>{if(disposed)return;disposed=true;lifecycle.abort();cleanup?.();};
window.addEventListener('pagehide',event=>{if(!event.persisted)dispose();else{sound.setHidden(true);runtime?.pause();}});
window.addEventListener('pageshow',event=>{if(event.persisted){sound.setHidden(document.hidden);if(!manualPause&&!document.hidden)runtime?.resume();}});
if(import.meta.hot)import.meta.hot.dispose(dispose);
start().catch(error=>{el('transition-text').textContent=`The evening could not load: ${error instanceof Error?error.message:String(error)}`;});

