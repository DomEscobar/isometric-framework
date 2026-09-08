import { createRequire } from 'node:module';
import { mkdir, writeFile } from 'node:fs/promises';
import { resolve } from 'node:path';
const require = createRequire(resolve(process.env.RUNTIME_QA_PACKAGE ?? 'package.json'));
const output = resolve(process.env.RUNTIME_QA_OUTPUT ?? 'test-results/browser-api');
await mkdir(output, { recursive: true });
const { chromium } = require('playwright');
const browser = await chromium.launch({headless:true});
const context = await browser.newContext({viewport:{width:1100,height:850}});
const page = await context.newPage();
const pageErrors=[];
page.on('pageerror', error=>pageErrors.push(error.message));
await page.route('**/qa-host', route=>route.fulfill({contentType:'text/html',body:'<!doctype html><html><body style="margin:0"></body></html>'}));
await page.route('**/qa-slow*.png', async route=>{
  await new Promise(resolve=>setTimeout(resolve,700));
  try { await route.fulfill({contentType:'image/png',body:Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+j8ioAAAAASUVORK5CYII=','base64')}); } catch {}
});
await page.goto(`${process.env.RUNTIME_QA_URL ?? 'http://127.0.0.1:4175'}/qa-host`);
const results=await page.evaluate(async()=>{
  const { Runtime } = await import('/src/index.ts');
  const result=[];
  let owned=[];
  const assert=(value,message)=>{if(!value)throw new Error(message)};
  const same=(a,b,message)=>assert(JSON.stringify(a)===JSON.stringify(b),`${message}: ${JSON.stringify(a)} !== ${JSON.stringify(b)}`);
  const scene=(name='base')=>({version:1,name,tileWidth:64,tileHeight:32,map:Array.from({length:5},()=>Array(10).fill('grass')),tiles:{grass:{color:0x86a86b}},entityTypes:{actor:{visual:{kind:'actor',color:0x2255ee},blocking:true},wall:{visual:{kind:'box'},blocking:true},gem:{visual:{kind:'gem'},blocking:false}},entities:[{id:'actor',type:'actor',c:0,r:0}],controlledId:'actor',diagonal:false});
  const spawn=(data=scene(),options={})=>{
    const host=document.createElement('div');host.style.cssText='width:480px;height:340px;display:inline-block';document.body.append(host);
    const runtime=new Runtime({container:host,scene:data,autoStart:false,input:false,...options});owned.push({runtime,host});return runtime;
  };
  const ready=async(data,options)=>{const runtime=spawn(data,options);await runtime.ready;return runtime};
  const png=color=>{const canvas=document.createElement('canvas');canvas.width=16;canvas.height=16;const g=canvas.getContext('2d');g.fillStyle=color;g.fillRect(0,0,16,16);return canvas.toDataURL()};
  const red=png('red'),blue=png('blue');
  const pixels=()=>{const source=owned.at(-1).host.querySelector('canvas'),copy=document.createElement('canvas');copy.width=source.width;copy.height=source.height;const g=copy.getContext('2d');g.drawImage(source,0,0);return{data:Array.from(g.getImageData(0,0,copy.width,copy.height).data),png:copy.toDataURL()}};
  const differences=(a,b)=>a.reduce((sum,value,index)=>sum+(value!==b[index]?1:0),0);
  const captures={};
  const spriteScene=(name,url)=>{const data=scene(name);data.entityTypes.actor.visual={kind:'sprite',url};return data};
  const rejected=async(promise)=>{try{await promise;return null}catch(error){return{name:error.name,message:error.message}}};
  const run=async(name,test)=>{const start=performance.now();try{const evidence=await test();result.push({name,pass:true,evidence,ms:performance.now()-start})}catch(error){result.push({name,pass:false,error:error.stack,ms:performance.now()-start})}finally{for(const {runtime,host}of owned){try{runtime.destroy()}catch{}host.remove()}owned=[]}};
  await run('independent instances and isolated destruction',async()=>{
    const a=await ready(spriteScene('A',red)),b=await ready(spriteScene('B',red));
    const arrivals=[];b.on('arrive',event=>arrivals.push(event));a.moveTo('actor',{c:3,r:0});a.step(1);
    assert(a.getEntity('actor').c===3,'first moved');assert(b.getEntity('actor').c===0,'second was independent');
    a.destroy();assert(document.querySelectorAll('canvas').length===1,'only surviving canvas');
    b.moveTo('actor',{c:2,r:0});b.step(1);assert(b.getEntity('actor').c===2,'surviving instance renders and moves');assert(arrivals.length===1,'surviving events');
    return {survivingScene:b.serializeScene().name,arrivals};
  });
  await run('destroy during initial async assets load',async()=>{
    const a=spawn(spriteScene('slow','/qa-slow-start.png'));let events=0;a.on('scenechange',()=>events++);a.on('error',()=>events++);
    a.destroy();const failure=await rejected(a.ready);await new Promise(resolve=>setTimeout(resolve,800));
    assert(failure?.name==='AbortError','ready rejects cancellation');assert(events===0,'no late callbacks');assert(document.querySelectorAll('canvas').length===0,'no late canvas mount');return{failure,events};
  });
  await run('destroy during movement cancels remaining event listeners',async()=>{
    const a=await ready();let secondary=0,arrive=0,frames=0;
    a.on('move',()=>a.destroy());a.on('move',()=>secondary++);a.on('arrive',()=>arrive++);a.on('frame',()=>frames++);
    a.moveTo('actor',{c:5,r:0});a.step(3);assert(secondary===0&&arrive===0&&frames===0,'all post-destroy callbacks suppressed');assert(!document.querySelector('canvas'),'canvas removed');return{secondary,arrive,frames};
  });
  await run('failed asset load is transactional',async()=>{
    const a=await ready();const snapshot=a.serializeScene();let errors=0;a.on('error',()=>errors++);
    const failure=await rejected(a.loadScene(spriteScene('broken','data:image/png;base64,broken')));
    assert(failure&&errors===1,'one rejected asset error');same(a.serializeScene(),snapshot,'active scene retained');a.moveTo('actor',{c:2,r:0});a.step(1);assert(a.getEntity('actor').c===2,'old scene usable');return{failure,errors};
  });
  await run('malformed scene load preserves active scene',async()=>{
    const a=await ready();const snapshot=a.serializeScene();const failure=await rejected(a.loadScene({...scene(),entities:[{id:'invalid',type:'not-a-type',c:0,r:0}]}));
    assert(failure?.name==='TypeError','malformed scene rejected');same(a.serializeScene(),snapshot,'prior state retained');return failure;
  });
  await run('overlapping loads latest valid request wins',async()=>{
    const a=await ready();const events=[];a.on('scenechange',event=>events.push(event.name));
    const old=rejected(a.loadScene(spriteScene('old','/qa-slow-overlap.png')));await a.loadScene(spriteScene('new',blue));const failure=await old;
    assert(failure?.name==='AbortError','superseded load rejected');assert(a.serializeScene().name==='new','latest scene active');same(events,['new'],'only latest scenechange');return{failure,events};
  });
  await run('invalid load does not cancel pending valid load',async()=>{
    const a=await ready();const loading=a.loadScene(spriteScene('valid','/qa-slow-valid.png'));const failure=await rejected(a.loadScene({version:999}));await loading;
    assert(failure?.name==='TypeError','invalid rejected');assert(a.serializeScene().name==='valid','valid pending scene survived');return{failure,name:a.serializeScene().name};
  });
  await run('equal wall time movement at 30 60 120 Hz',async()=>{
    const positions=[];
    for(const hz of [30,60,120]){const a=await ready(undefined,{speed:3});let latest=null;a.on('move',event=>latest=event.position);a.moveTo('actor',{c:9,r:0});for(let i=0;i<hz*1.5;i++)a.step(1/hz);positions.push({hz,latest,entity:a.getEntity('actor')});a.destroy()}
    for(const value of positions){assert(Math.abs(value.latest.c-4.5)<1e-8,`interpolated position at ${value.hz}`);assert(value.entity.c===4,'integer occupancy remains last completed tile')}
    return positions;
  });
  await run('pause resume preserve simulation progress',async()=>{
    const a=await ready();let frames=0;const changes=[];a.on('frame',()=>frames++);a.on('pausechange',event=>changes.push(event.paused));a.moveTo('actor',{c:6,r:0});a.step(0.5);a.pause();a.step(2);assert(a.getEntity('actor').c===1,'paused motion fixed');assert(a.moveTo('actor',{c:9,r:0})==='paused','paused command rejected');a.resume();a.step(0.5);assert(a.getEntity('actor').c===3,'resume preserves half-tile progress');same(changes,[true,false],'pause events');assert(frames===2,'no paused frames');return{changes,frames,position:a.getEntity('actor')};
  });
  await run('sprites and multiple-image animation advance visibly',async()=>{
    const data=spriteScene('animated',red);data.entityTypes.gem.visual={kind:'sprite',frames:[red,blue],fps:2};data.entities.push({id:'animation',type:'gem',c:3,r:3});const a=await ready(data);
    a.step(0);const canvas=owned.at(-1).host.querySelector('canvas');
    const snap=()=>{a.step(0);const copy=document.createElement('canvas');copy.width=canvas.width;copy.height=canvas.height;const g=copy.getContext('2d');g.drawImage(canvas,0,0);return Array.from(g.getImageData(0,0,copy.width,copy.height).data)};
    const first=snap();a.step(0.5);const second=snap();let changed=0;for(let i=0;i<first.length;i++)if(first[i]!==second[i])changed++;
    assert(changed>50,'animation changes rendered pixels');a.remove('animation');a.step(1);return{changedPixelChannels:changed,remainingEntities:a.getEntities().length};
  });
  await run('camera roundtrip picking at translated zoom and elevations',async()=>{
    const data=scene();data.tiles.raised={color:0xaabbcc,elevation:8};data.map[2][4]='raised';const a=await ready(data);a.setCamera({x:120,y:180,zoom:0.65});
    const probes=[{c:0,r:0},{c:4,r:2},{c:9,r:4}].map(cell=>({cell,point:a.cellToScreen(cell),picked:a.pick(a.cellToScreen(cell))}));for(const probe of probes)same(probe.picked,probe.cell,'screen/cell roundtrip');assert(a.pick({x:Infinity,y:1})===null,'invalid pick');return probes;
  });
  await run('dynamic blocker during a movement segment prevents entry',async()=>{
    const a=await ready();const blocked=[];a.on('blocked',event=>blocked.push(event));a.moveTo('actor',{c:6,r:0});a.step(0.1);a.add({id:'blocker',type:'wall',c:1,r:0});a.step(3);
    assert(a.getEntity('actor').c===0,'did not enter newly blocked tile');assert(blocked.length===1,'one blocked event');a.remove('blocker');a.moveTo('actor',{c:6,r:0});a.step(3);assert(a.getEntity('actor').c===6,'motion recovered after remove');return{blocked,final:a.getEntity('actor')};
  });
  await run('add remove serialization roundtrip and detached outputs',async()=>{
    const a=await ready();a.add({id:'new',type:'gem',c:3,r:3,data:{counter:5}});const snapshot=a.serializeScene();const external=a.getEntity('new');external.data.counter=90;assert(a.getEntity('new').data.counter===5,'getEntity detached');assert(a.remove('new'),'remove existing');assert(!a.remove('new'),'remove missing');await a.loadScene(JSON.parse(JSON.stringify(snapshot)));same(a.serializeScene(),snapshot,'serialized reload exact');return{entity:a.getEntity('new')};
  });
  await run('reentrant move stop prevents further movement and arrival',async()=>{
    const a=await ready();let moves=0,arrivals=0;a.on('move',()=>{moves++;a.stop('actor')});a.on('arrive',()=>arrivals++);a.moveTo('actor',{c:6,r:0});a.step(3);assert(moves===1&&arrivals===0,'stop on callback halts loop');assert(a.getEntity('actor').c===1,'only first segment committed');return{moves,arrivals,entity:a.getEntity('actor')};
  });
  await run('reentrant move loadScene safely replaces active scene',async()=>{
    const a=await ready();let loading,moves=0,arrivals=0;a.on('move',()=>{moves++;loading=a.loadScene(scene('replacement'))});a.on('arrive',()=>arrivals++);a.moveTo('actor',{c:6,r:0});a.step(3);await loading;assert(moves===1&&arrivals===0,'old motion stopped immediately');assert(a.serializeScene().name==='replacement','new scene loaded');assert(a.getEntity('actor').c===0,'new entity intact');return{moves,arrivals,name:a.serializeScene().name};
  });
  await run('reentrant scenechange destroy suppresses later listeners',async()=>{
    const a=await ready();let later=0;a.on('scenechange',()=>a.destroy());a.on('scenechange',()=>later++);await a.loadScene(scene('destroy-me'));assert(later===0,'later scenechange suppressed');assert(!document.querySelector('canvas'),'canvas removed');return{later};
  });
  await run('reentrant frame destroy is safe',async()=>{
    const a=await ready();let later=0;a.on('frame',()=>a.destroy());a.on('frame',()=>later++);a.step(1);assert(later===0,'later frame suppressed');return{later};
  });
  await run('reentrant blocked destroy is safe with multiple movers',async()=>{
    const a=await ready();a.add({id:'second',type:'actor',c:0,r:3});a.moveTo('actor',{c:6,r:0});a.moveTo('second',{c:6,r:3});a.step(0.1);a.add({id:'blocker',type:'wall',c:1,r:0});a.on('blocked',()=>a.destroy());a.step(3);assert(!document.querySelector('canvas'),'destroyed safely before second mover');return{destroyed:true};
  });
  await run('reentrant move remove another mover is safe',async()=>{
    const a=await ready();a.add({id:'second',type:'actor',c:0,r:3});a.moveTo('actor',{c:2,r:0});a.moveTo('second',{c:2,r:3});a.on('move',event=>{if(event.id==='actor')a.remove('second')});a.step(1);assert(!a.getEntity('second'),'other mover removed');assert(a.getEntity('actor').c===2,'first mover arrived');return{entities:a.getEntities()};
  });
  await run('flat and uniformly raised floors never clip actors between cell centers',async()=>{
    const data=spriteScene('flat-silhouette',red);data.entities[0].c=2;data.entities[0].r=2;
    const a=await ready(data,{speed:1});
    const redCount=()=>pixels().data.reduce((count,value,i,rgba)=>count+(i%4===0&&value===255&&rgba[i+1]===0&&rgba[i+2]===0?1:0),0);
    let probes=0;
    for(const elevation of [0,24])for(const [dc,dr]of [[1,0],[-1,0],[0,1],[0,-1]])for(const fraction of [.25,.5,.75]){
      data.tiles.grass.elevation=elevation;await a.loadScene(data);a.setCamera({zoom:1});a.step(0);const expected=redCount();
      assert(expected>100,'baseline sprite must be fully visible');a.moveTo('actor',{c:2+dc,r:2+dr});a.step(fraction);
      const actual=redCount();if(actual!==expected)captures['flat-actor-clipped']=pixels().png;
      assert(actual===expected,`floor clipped sprite at elevation=${elevation},direction=${dc},${dr},fraction=${fraction}: ${actual}/${expected} visible red pixels`);probes++;
    }
    return{silhouetteProbes:probes};
  });
  await run('foreground elevated tile visually occludes lower rear sprite',async()=>{
    const data=spriteScene('occlusion',red);data.entities[0].c=2;data.entities[0].r=1;data.tiles.high={color:0x2288cc,elevation:64};data.map[2][1]='high';
    const a=await ready(data);a.step(0);const withActor=pixels();captures['elevation-with-actor']=withActor.png;a.remove('actor');const withoutActor=pixels();captures['elevation-without-actor']=withoutActor.png;
    const changed=differences(withActor.data,withoutActor.data);assert(changed===0,`fully occluded rear sprite must not alter pixels; changed channels=${changed}`);return{changedPixelChannels:changed};
  });
  await run('stop immediately renders integer position while paused',async()=>{
    const a=await ready();a.step(0);const initial=pixels();captures['stop-initial']=initial.png;a.moveTo('actor',{c:6,r:0});a.step(0.1);const moving=pixels();captures['stop-moving']=moving.png;a.pause();a.stop('actor');const stopped=pixels();captures['stop-stopped']=stopped.png;
    assert(differences(initial.data,moving.data)>50,'movement visibly interpolated');const stale=differences(initial.data,stopped.data);assert(stale===0,`stop must render initial grid position immediately; changed channels=${stale}`);return{changedPixelChannels:stale};
  });
  return {result,captures};
});
for(const [name,data]of Object.entries(results.captures))await writeFile(resolve(output, `${name}.png`),Buffer.from(data.split(',')[1],'base64'));
const cases=results.result;
const report={kind:'Independent browser runtime API instrumentation; not UI end-to-end or live VPS testing',url:page.url(),timestamp:new Date().toISOString(),results:cases,pageErrors,passed:cases.filter(x=>x.pass).length,total:cases.length};
await writeFile(resolve(output, 'results.json'),JSON.stringify(report,null,2));
for (const test of cases) console.log(`${test.pass ? 'PASS' : 'FAIL'} ${test.name}${test.error ? `\n${test.error}` : ''}`);
console.log(`${report.passed}/${report.total} browser API checks passed; ${pageErrors.length} page errors. Report: ${output}`);
await browser.close();
process.exitCode=cases.some(x=>!x.pass)||pageErrors.length?1:0;
