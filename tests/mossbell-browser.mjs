import { chromium } from 'playwright';
import { mkdir, writeFile } from 'node:fs/promises';
import { resolve } from 'node:path';
import assert from 'node:assert/strict';

const output=resolve(process.env.MOSSBELL_OUTPUT??'test-results/mossbell/playtest');
await mkdir(output,{recursive:true});
const browser=await chromium.launch({channel:'chrome'}),report={checks:[],errors:[],routes:[],performance:[]};
const base=process.env.RUNTIME_QA_URL??'http://127.0.0.1:4175';
const check=(name,data=true)=>report.checks.push({name,passed:true,data});
const samples=async page=>page.evaluate(()=>new Promise(resolve=>{const values=[];let last=performance.now();const next=now=>{values.push(now-last);last=now;if(values.length<180)requestAnimationFrame(next);else{values.shift();values.sort((a,b)=>a-b);resolve({median:values[Math.floor(values.length*.5)],p95:values[Math.floor(values.length*.95)]});}};requestAnimationFrame(next);}));
try{
  for(const mobile of [false,true]){
    const label=mobile?'mobile':'desktop';
    const context=await browser.newContext({viewport:mobile?{width:390,height:844}:{width:1440,height:960},...(mobile?{isMobile:true,hasTouch:true}:{}),recordVideo:{dir:resolve(output,'video'),size:mobile?{width:390,height:844}:{width:1440,height:960}}});
    const page=await context.newPage();page.setDefaultTimeout(18000);
    page.on('pageerror',error=>report.errors.push({label,message:error.message}));
    page.on('response',response=>{if(response.status()>=400)report.errors.push({label,status:response.status(),url:response.url()});});
    await page.goto('about:blank');const blank=await samples(page);
    await page.goto(`${base}/examples/mossbell/`);
    await page.waitForFunction(()=>window.__MOSSBELL__&&!window.__MOSSBELL__.snapshot().transitioning);
    await page.waitForFunction(()=>!document.querySelector('#transition').classList.contains('visible'));
    if(!mobile)await writeFile(resolve(output,'scene-town.json'),JSON.stringify(await page.evaluate(()=>window.__MOSSBELL__.getWorld().scene)));
    const state=()=>page.evaluate(()=>{const s=window.__MOSSBELL__.snapshot();return{...s,debug:undefined,hero:window.__MOSSBELL__.runtime.getEntity('traveler')};});
    const capture=async name=>{await page.waitForFunction(()=>getComputedStyle(document.querySelector('#transition')).opacity==='0');await page.screenshot({path:resolve(output,`${label}-${name}.png`)});};
    const press=async selector=>mobile?await page.locator(selector).tap():await page.locator(selector).click();
    await page.evaluate(()=>{window.__route=[];window.__runtimeErrors=[];window.__MOSSBELL__.runtime.on('error',({error})=>window.__runtimeErrors.push(error.message));window.__MOSSBELL__.runtime.on('move',({id})=>{if(id!=='traveler')return;const actor=window.__MOSSBELL__.runtime.getEntity(id);const s={c:actor.c,r:actor.r,level:actor.level??'ground',region:window.__MOSSBELL__.snapshot().region};if(JSON.stringify(window.__route.at(-1))!==JSON.stringify(s))window.__route.push(s);});});
    assert.equal((await state()).audio.enabled,false);check(`${label}: sound requires gesture`);
    await press('#sound');await page.waitForFunction(()=>window.__MOSSBELL__.snapshot().audio.rms>.0001);
    check(`${label}: sound enabled and non-silent`,(await state()).audio);
    if(!mobile){
      await page.evaluate(()=>{window.__audioRecording=window.__MOSSBELL__.captureAudio(8).then(async blob=>Array.from(new Uint8Array(await blob.arrayBuffer())));});
      await page.locator('#world').focus();await page.keyboard.down('w');await page.waitForTimeout(380);await page.keyboard.up('w');await page.waitForTimeout(500);
      assert.ok((await state()).hero.c>9);check('desktop: held W moves c+ and release settles');
    }else{
      const before=(await state()).hero,box=await page.locator('[data-key="KeyD"]').boundingBox();assert.ok(box&&box.x>=0&&box.y+box.height<=844);
      const cdp=await context.newCDPSession(page);await cdp.send('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:[{x:box.x+box.width/2,y:box.y+box.height/2}]});await page.waitForTimeout(420);await cdp.send('Input.dispatchTouchEvent',{type:'touchEnd',touchPoints:[]});await page.waitForTimeout(450);assert.ok((await state()).hero.r>before.r);check('mobile: real held touch D-pad movement and release');
    }
    await capture('town');
    const native=await page.evaluate(()=>{const canvas=document.querySelector('#world canvas');const gl=canvas.getContext('webgl2')??canvas.getContext('webgl');const debug=gl?.getExtension('WEBGL_debug_renderer_info');return{renderer:debug?gl.getParameter(debug.UNMASKED_RENDERER_WEBGL):gl?.getParameter(gl.RENDERER),userAgent:navigator.userAgent};});
    report.performance.push({label,scene:'town',viewport:page.viewportSize(),blank,...native,...await samples(page)});
    await press('#pause');const paused=await state();const pausedImage=await page.locator('#atmosphere').evaluate(canvas=>canvas.toDataURL());await page.waitForTimeout(750);
    assert.equal((await state()).time,paused.time);assert.equal((await state()).audio.state,'suspended');assert.equal(pausedImage,await page.locator('#atmosphere').evaluate(canvas=>canvas.toDataURL()));check(`${label}: pause freezes simulation, rendered effects and audio`);
    await press('#pause');await press('#settings-toggle');
    await page.locator('#ambience-volume').fill('20');await page.locator('#effects-volume').fill('35');
    assert.equal((await state()).audio.ambience,.2);assert.equal((await state()).audio.effects,.35);check(`${label}: independent ambience and effect levels`);
    await press('#settings-toggle');
    const blocked=await page.evaluate(()=>window.__MOSSBELL__.runtime.findPath('traveler',{c:5,r:14}));assert.equal(blocked,null);check(`${label}: water is blocked`);
    await press('#quest-action');await page.waitForFunction(()=>window.__MOSSBELL__.snapshot().region==='forest'&&!window.__MOSSBELL__.snapshot().transitioning,{},{timeout:26000});
    const route=await page.evaluate(()=>window.__route.splice(0));assert.ok(route.some(c=>c.level==='bridge'));report.routes.push({label,journey:'town-to-forest',route});check(`${label}: town to forest physically crosses supported bridge`);
    if(!mobile)await writeFile(resolve(output,'scene-forest.json'),JSON.stringify(await page.evaluate(()=>window.__MOSSBELL__.getWorld().scene)));
    if(mobile){await capture('forest-follow');await press('#fit');}
    await capture('forest');report.performance.push({label,scene:'forest',viewport:page.viewportSize(),blank,...native,...await samples(page)});
    const beforeMotion=await page.locator('#world canvas').screenshot();await page.waitForTimeout(800);assert.ok(!beforeMotion.equals(await page.locator('#world canvas').screenshot()));check(`${label}: runtime scenery pixels animate`);
    const clips=await page.evaluate(()=>window.__MOSSBELL__.snapshot().debug.entities.filter(e=>e.type==='flow'||e.type==='fern').slice(0,8).map(e=>({id:e.id,clip:e.sprite.clip,frame:e.sprite.frame})));
    check(`${label}: named environmental clips`,clips);
    if(!mobile){
      const bytes=await page.evaluate(()=>window.__audioRecording);await writeFile(resolve(output,'town-audio.webm'),Buffer.from(bytes));
      await page.evaluate(()=>{window.__audioRecording=window.__MOSSBELL__.captureAudio(10).then(async blob=>Array.from(new Uint8Array(await blob.arrayBuffer())));});
    }
    await press('#quest-action');await page.waitForFunction(()=>window.__MOSSBELL__.snapshot().progress==='seed'&&window.__MOSSBELL__.snapshot().action.phase==='idle',{},{timeout:26000});
    assert.equal((await state()).action.effectApplied,true);check(`${label}: spring interaction grants one seed`);await capture('spring-awakened');
    const forestRoute=await page.evaluate(()=>window.__route.splice(0));assert.ok(forestRoute.some(c=>c.c>=7&&c.c<=9&&[15,16].includes(c.r)));report.routes.push({label,journey:'forest-to-spring',route:forestRoute});
    await press('#quest-action');await page.waitForFunction(()=>window.__MOSSBELL__.snapshot().region==='town'&&!window.__MOSSBELL__.snapshot().transitioning,{},{timeout:28000});assert.equal((await state()).progress,'seed');check(`${label}: return transition preserves seed`);
    await press('#quest-action');await page.waitForFunction(()=>window.__MOSSBELL__.snapshot().progress==='planted'&&window.__MOSSBELL__.snapshot().action.phase==='idle',{},{timeout:22000});
    assert.equal(await page.evaluate(()=>window.__MOSSBELL__.runtime.getEntities().filter(e=>e.id==='final-bloom').length),1);check(`${label}: planting produces exactly one visible moonflower`);await capture('home-bloom');
    if(!mobile){const bytes=await page.evaluate(()=>window.__audioRecording);await writeFile(resolve(output,'forest-audio.webm'),Buffer.from(bytes));}
    await press('#sound');await page.waitForTimeout(600);assert.equal((await state()).audio.muted,true);assert.ok((await state()).audio.rms<.0005);check(`${label}: mute silences mix`);
    assert.deepEqual(await page.evaluate(()=>window.__runtimeErrors),[]);check(`${label}: no host runtime errors during journey`);
    await page.reload();await page.waitForFunction(()=>window.__MOSSBELL__);assert.equal((await state()).progress,'planted');assert.ok(await page.evaluate(()=>!!window.__MOSSBELL__.runtime.getEntity('final-bloom')));check(`${label}: discovery resumes after reload`);
    const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth);assert.equal(overflow,false);check(`${label}: no horizontal document overflow`);
    await context.close();
  }
  assert.deepEqual(report.errors,[]);check('No page or asset errors');
}catch(error){report.failure=error.stack;throw error;}
finally{await writeFile(resolve(output,'report.json'),JSON.stringify(report,null,2));await browser.close();}
console.log(JSON.stringify({passed:report.checks.length,errors:report.errors,performance:report.performance},null,2));
