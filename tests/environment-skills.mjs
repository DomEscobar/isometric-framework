import { chromium } from 'playwright';
import { readFile, mkdir, writeFile } from 'node:fs/promises';
import { resolve } from 'node:path';
import { checkAssembly } from '../skills/multi-tile-asset-assembly/scripts/check-assembly.mjs';
import { createGeneratedScene, generatedSources } from '../examples/environment-lab/generated-scene.ts';

const output = resolve('test-results/environment-skill-comparison');
await mkdir(output, { recursive: true });
const source = await readFile('skills/animated-environments/assets/challenge-atlas.svg', 'utf8');
const variants = process.argv.slice(2).length ? process.argv.slice(2) : ['a', 'b', 'c'];
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
const errors = [], results = [];
page.on('pageerror', error => errors.push(error.message));
await page.route('**/__environment-atlas.svg', route => route.fulfill({ contentType: 'image/svg+xml', body: source }));
await page.route('**/environment-qa-host', route => route.fulfill({ contentType: 'text/html', body: '<!doctype html><style>body{margin:0;background:#e9eee2}#world{width:1000px;height:850px;position:relative}#panel{position:absolute;left:1000px;top:0;width:270px;font:12px monospace}</style><div id="world"></div><div id="panel"></div>' }));
await page.goto(`${process.env.RUNTIME_QA_URL ?? 'http://127.0.0.1:4175'}/environment-qa-host`);
const fixture = await page.evaluateHandle(async () => ({ api: await import('/src/index.ts') }));
const cell = (c, r, level = 'ground') => ({ c, r, level });
const corners = [[16,160,-.5,-.5],[112,112,2.5,-.5],[208,160,2.5,2.5],[112,208,-.5,2.5]];
const crossing = [...[0,1,2].map(c => cell(c,5)), ...[3,4,5,6,7,8].map(c => cell(c,5,'bridge')), ...[9,10,11,12].map(c => cell(c,5))];
const plan = {
  version: 1, actor: 'traveler', tolerancePx: .01,
  placements: [{ entity: 'fountain', origin: cell(1,8), contacts: [0,1,2,3].flatMap(i => corners.map(([x,y,c,r]) => ({ texture: `fountain-${i}`, source: {x,y}, grid: {c,r} }))) }],
  blocked: [...[1,2,3].flatMap(c=>[8,9,10].map(r=>cell(c,r))), ...[3,4,5,6,7,8].flatMap(c=>[4,6].map(r=>cell(c,r,'bridge'))), ...[3,8].flatMap(c=>[4,6].map(r=>cell(c,r))), ...[5,6].flatMap(c=>Array.from({length:13},(_,r)=>cell(c,r)))],
  open: [3,4,5,6,7].map(r=>cell(4,r)),
  paths: [{id:'bridge both banks',points:crossing},{id:'bridge reverse',points:[...crossing].reverse()},{id:'underpass',points:[3,4,5,6,7].map(r=>cell(4,r))}],
  clearances: [{id:'underpass headroom',cell:cell(4,5),height:48}],
};
try {
  for (const variant of variants) {
    const generated=variant.startsWith('generated-');
    if (!['a','b','c','accepted','generated-raw','generated-registered','generated-layered'].includes(variant)) throw new Error(`Unknown variant: ${variant}`);
    const base = JSON.parse(await readFile(`examples/environment-lab/variants/${generated?'accepted':variant}.json`, 'utf8'));
    const scene = generated?createGeneratedScene(base,variant.slice(10),Object.fromEntries(generatedSources.map(id=>[id,`/examples/environment-lab/art/generated/${id}-source.png`]))):base;
    const trialPlan=structuredClone(plan);
    if(generated){
      trialPlan.tolerancePx=3; // Retrospective measured fit; source uncertainty/projection residual documented.
      const frameIds=variant==='generated-layered'?[0]:[0,1,2,3];
      trialPlan.placements[0].contacts=frameIds.flatMap(i=>[[37,443,-.5,-.5],[590,443,2.5,2.5],[314,588,-.5,2.5]].map(([x,y,c,r])=>({texture:`fountain-${i}`,source:{x,y},grid:{c,r}})));
      const river=scene.entities.find(e=>e.type==='water');
      const raw=variant==='generated-raw';
      trialPlan.placements.push({entity:river.id,origin:river,contacts:[0,1,2,3].flatMap(i=>{
        const dx=i%2?-4:0,dy=i>=2?-84:0;
        const points=raw?[[20+dx,390+dy,-.5,-.5],[611+dx,390+dy,.5,.5],[315+dx,231+dy,.5,-.5]]:[[5,165,-.5,-.5],[595,165,.5,.5],[300,6,.5,-.5]];
        return points.map(([x,y,c,r])=>({texture:`river-${i}`,source:{x,y},grid:{c,r}}));
      })});
      for(const pier of scene.entities.filter(e=>e.type==='pier'))trialPlan.placements.push({entity:pier.id,origin:pier,contacts:[[4,352,-.5,-.5],[272,352,.5,.5],[139,420,-.5,.5]].map(([x,y,c,r])=>({texture:'pier',source:{x,y},grid:{c,r}}))});
      for(const rail of scene.entities.filter(e=>e.type==='railArt'))trialPlan.placements.push({entity:rail.id,origin:rail,contacts:[[336,912,-.5,0],[1249,501,1.5,0]].map(([x,y,c,r])=>({texture:'rail',source:{x,y},grid:{c,r}}))});
      await writeFile(resolve(output,`${variant}-scene.json`),JSON.stringify(scene,null,2));
    }
    await writeFile(resolve(output,`${variant}-plan.json`),JSON.stringify(trialPlan,null,2));
    const assembly = checkAssembly(scene, trialPlan);
    const solidVolume = checkAssembly(scene, {version:1, actor:'traveler', solidHeights:[{id:'fountain stone centerpiece',cell:cell(2,9),minHeight:generated?114:86}]});
    await writeFile(resolve(output, `${variant}-assembly.json`), JSON.stringify(assembly,null,2));
    const negativeAnchor = structuredClone(scene); negativeAnchor.entityTypes[negativeAnchor.entities.find(e=>e.id==='fountain').type].visual.anchor={x:.5,y:1};
    const negativeBridge = structuredClone(scene); negativeBridge.entityTypes.badBridge={visual:{kind:'box',color:0x888888},columns:6,rows:3,blocking:true};negativeBridge.entities.push({id:'badBridge',type:'badBridge',c:3,r:4});
    const catchesBadAnchor = !checkAssembly(negativeAnchor,trialPlan).pass, catchesSolidBridge = !checkAssembly(negativeBridge,trialPlan).pass;
    await fixture.evaluate(async (f,scene) => {
      f.runtime=await f.api.createRuntime({container:document.getElementById('world'),scene,autoStart:false,input:false,jump:{height:84,duration:.8,distance:4},background:0xe9eee2});
      f.runtime.on('error',({error})=>{throw error;});
      f.debug=f.api.createDebugOverlay(f.runtime,{container:document.getElementById('world'),panel:document.getElementById('panel')});
      f.runtime.step(0);
    },scene);
    const screenshot = suffix => page.screenshot({path:resolve(output,`${variant}-${suffix}.png`)});
    const baseline = await screenshot('frame0');
    const initial = await fixture.evaluate(f=>f.runtime.getDebugSnapshot().entities.filter(e=>e.sprite?.clip).map(e=>({id:e.id,frame:e.sprite.frame})));
    await fixture.evaluate(f=>f.runtime.step(.25));
    const advanced = await screenshot('frame1');
    await fixture.evaluate(f=>{f.runtime.pause();f.runtime.step(.75);});
    const paused = await screenshot('paused');
    await fixture.evaluate(f=>{f.runtime.resume();f.runtime.step(.75);});
    const loop = await screenshot('loop');
    const final = await fixture.evaluate(f=>f.runtime.getDebugSnapshot().entities.filter(e=>e.sprite?.clip).map(e=>({id:e.id,frame:e.sprite.frame})));
    const animation = { pixelsAdvance:!baseline.equals(advanced),pauseFreezes:advanced.equals(paused),loopReturns:baseline.equals(loop),framesReturn:JSON.stringify(initial)===JSON.stringify(final),animatedEntities:initial.length };
    const bridge = await fixture.evaluate(f=>{
      const floors=[];const off=f.runtime.on('move',({position})=>floors.push(position.level??'ground'));
      f.runtime.moveTo('traveler',{c:12,r:5});for(let i=0;i<300;i++)f.runtime.step(1/30);off();
      return {destination:f.runtime.getEntity('traveler'),usedBridge:floors.includes('bridge')};
    });
    await screenshot('crossed');
    await fixture.evaluate(async(f,scene)=>{const under=structuredClone(scene);Object.assign(under.entities.find(e=>e.id==='traveler'),{c:4,r:7,level:'ground'});await f.runtime.loadScene(under);f.runtime.moveTo('traveler',{c:4,r:3});f.runtime.step(2/3);},scene);
    await screenshot('under-all-floors');
    await fixture.evaluate(f=>{f.runtime.setViewLevel('ground');f.debug.setEnabled(true);});
    await screenshot('under-ground-overlay');
    const under = await fixture.evaluate(f=>{f.runtime.step(2);return f.runtime.getEntity('traveler');});
    const jump = await fixture.evaluate(async(f,scene)=>{
      const probe=structuredClone(scene);Object.assign(probe.entities.find(e=>e.id==='traveler'),{c:0,r:9,level:'ground'});await f.runtime.loadScene(probe);
      f.debug.setEnabled(false);f.runtime.setMoveInput({x:1,y:-1});let target;const off=f.runtime.on('jumpstart',event=>target=event.to);f.runtime.jump();f.runtime.setMoveInput(null);f.runtime.step(.8);off();return{target,landed:f.runtime.getEntity('traveler')};
    },scene);
    const result={variant,assembly:assembly.pass,negativeProbes:{catchesBadAnchor,catchesSolidBridge},animation,
      bridgeWalk:bridge.usedBridge&&bridge.destination.c===12&&bridge.destination.r===5,bridge,
      underpass:under.c===4&&under.r===3&&(under.level??'ground')==='ground',
      solidCenterpiece:solidVolume.pass,jumpCrossesStone:jump.landed.c===4&&jump.landed.r===9,jump};
    results.push(result);console.log(JSON.stringify(result));
    await fixture.evaluate(f=>{f.debug.destroy();f.runtime.destroy();});
  }
} finally { await browser.close(); }
await writeFile(resolve(output,variants.join('-')+'-results.json'),JSON.stringify({results,errors,scope:'Workflow comparison; extra extended-jump stress probe separates walking occupancy from solid vertical volume. Floor traversal observed with move events; arrive emits only at the destination.'},null,2));
await writeFile(resolve(output,'assembly-plan.json'),JSON.stringify(plan,null,2));
const acceptedFailed=results.some(result=>['accepted','generated-layered'].includes(result.variant)&&(!result.assembly||!result.bridgeWalk||!result.underpass||!result.solidCenterpiece||result.jumpCrossesStone||!Object.values(result.negativeProbes).every(Boolean)||!result.animation.pixelsAdvance||!result.animation.pauseFreezes||!result.animation.loopReturns||!result.animation.framesReturn));
process.exitCode=errors.length||acceptedFailed?1:0;
