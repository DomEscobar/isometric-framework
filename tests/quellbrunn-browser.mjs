import assert from 'node:assert/strict';
import {chromium} from 'playwright';
import {mkdir,writeFile} from 'node:fs/promises';
const url=process.env.QUELLBRUNN_URL??'http://127.0.0.1:4203/',out='test-results/quellbrunn/browser';
await mkdir(out,{recursive:true});const browser=await chromium.launch();
try{
 for(const [name,viewport]of Object.entries({desktop:{width:1440,height:960},mobile:{width:390,height:844}})){
  const context=await browser.newContext({viewport,hasTouch:name==='mobile',recordVideo:{dir:out+'/video',size:viewport}}),page=await context.newPage(),errors=[],checks=[];
  page.on('pageerror',e=>errors.push(e.message));page.on('response',r=>{if(r.status()>=400)errors.push(`${r.status()} ${r.url()}`)});
  const baseline=await page.evaluate(()=>new Promise(resolve=>{const times=[];let last=performance.now();function f(t){times.push(t-last);last=t;if(times.length<120)requestAnimationFrame(f);else{times.sort((a,b)=>a-b);resolve({median:times[60],p95:times[114]})}}requestAnimationFrame(f)}));
  await page.goto(url);await page.waitForFunction(()=>window.quellbrunn?.ready);await page.waitForTimeout(1000);
  const environment=await page.evaluate(()=>({browser:navigator.userAgent,renderer:'Canvas2D, nearest-neighbour sprite sampling',dpr:devicePixelRatio}));
  await page.screenshot({path:`${out}/${name}.png`});
  const initial=await page.evaluate(()=>window.quellbrunn.state);
  // Hold the real default camera through a full eight-second water cycle.
  for(let i=0;i<=8;i++){await page.screenshot({path:`${out}/${name}-motion-${i}.png`});if(i<8)await page.waitForTimeout(1000);}
  const later=await page.evaluate(()=>window.quellbrunn.state);
  assert(later.time-initial.time>7);assert(later.villagers.every((p,i)=>Math.hypot(p.c-initial.villagers[i].c,p.r-initial.villagers[i].r)>1));
  checks.push({check:'three residents moved on real elapsed time',initial:initial.villagers,final:later.villagers});
  await page.locator('#pause').click();await page.waitForTimeout(100);const pauseState=await page.evaluate(()=>window.quellbrunn.state),before=await page.evaluate(()=>document.querySelector('canvas').toDataURL());await page.waitForTimeout(400);const after=await page.evaluate(()=>document.querySelector('canvas').toDataURL());assert(before===after,'Pause changed rendered pixels');assert.deepEqual(await page.evaluate(()=>window.quellbrunn.state),pauseState);checks.push({check:'pause freezes all pixels and actor states',pass:true});
  async function pose(p,scale=1.1){await page.evaluate(({p,scale})=>window.quellbrunn.inspect(p,scale),{p,scale});await page.waitForTimeout(60);}
  async function click(p,label){const s=await page.evaluate(p=>window.quellbrunn.screen(p),p);assert(s.x>0&&s.x<viewport.width&&s.y>145&&s.y<viewport.height-100,`Target off canvas: ${label} ${JSON.stringify(s)}`);if(name==='mobile')await page.touchscreen.tap(s.x,s.y);else await page.mouse.click(s.x,s.y);await page.waitForFunction(p=>{const s=window.quellbrunn.state;return s.remaining===0&&Math.hypot(s.hero.c-p.c,s.hero.r-p.r)<.23},p,{timeout:15000});checks.push({check:label,target:p,actual:await page.evaluate(()=>window.quellbrunn.state.hero)});}
  // Hand-selected cross-sections of visible dirt, independent of host route helpers.
  for(const [c,rs]of [[10,[13,14.5,16]],[27,[13.75,15,16.5]],[23,[30.75,32.25,33.75]]])for(const r of rs){await pose({c:c-.75,r});await click({c,r},`full path width ${c},${r}`);}
  for(const p of [{c:20,r:12},{c:32,r:11},{c:26,r:35}]){await pose({c:p.c-.75,r:p.r});await click(p,'open grass outside road');}
  for(const c of[14.5,34.5]){const centre=25+1.3*Math.sin(c/8)+.4*Math.sin(c/3),near={c,r:centre-4.8},far={c,r:centre+4.8};await pose(near,.8);await click(far,'bridge entire span forward');await click(near,'bridge entire span back');await page.screenshot({path:`${out}/${name}-bridge-${c}.png`});}
  for(const h of[{c:8,r:6},{c:21,r:6},{c:35,r:9},{c:2,r:34},{c:30,r:32}]){await pose({c:h.c-.75,r:h.r+1.5});await click({c:h.c-.75,r:h.r+2.5},'house entrance');await page.screenshot({path:`${out}/${name}-door-${h.c}-${h.r}.png`});}
  for(const [label,p,start]of[['water',{c:22,r:25.8},{c:22,r:21}],['house',{c:10,r:8},{c:6,r:8}],['tree root',{c:1,r:1.5},{c:3,r:1.5}],['bridge rail',{c:12.9,r:26.5},{c:14.5,r:26.5}]]){await pose(start,1);const before=await page.evaluate(()=>window.quellbrunn.state.hero),s=await page.evaluate(p=>window.quellbrunn.screen(p),p);if(name==='mobile')await page.touchscreen.tap(s.x,s.y);else await page.mouse.click(s.x,s.y);await page.waitForTimeout(150);const after=await page.evaluate(()=>window.quellbrunn.state.hero);assert.deepEqual(after,before,label+' allowed entry');assert.match(await page.locator('#status').textContent(),/Hindernis/);checks.push({check:label+' blocked',pass:true});}
  for(const [key,axis,sign]of[['w','c',1],['s','c',-1],['d','r',1],['a','r',-1]]){await pose({c:22,r:18});await page.locator('#pause').click();await page.keyboard.down(key);await page.waitForTimeout(350);await page.keyboard.up(key);const hero=await page.evaluate(()=>window.quellbrunn.state.hero);assert((hero[axis]-(axis==='c'?22:18))*sign>1);checks.push({check:'keyboard '+key,hero});}
  await pose({c:22,r:18},name==='mobile'?1.3:.95);await page.locator('#pause').click();await page.waitForTimeout(2000);const timing=await page.evaluate(()=>window.quellbrunn.stats());assert(timing.p95<40,`p95 ${timing.p95}ms`);assert.deepEqual(errors,[]);
  await writeFile(`${out}/${name}.json`,JSON.stringify({url,viewport,environment,baseline,timing,errors,checks},null,2));const video=page.video();await context.close();await video.saveAs(`${out}/${name}.webm`);console.log(JSON.stringify({name,checks:checks.length,timing,baseline}));
 }
}finally{await browser.close()}



