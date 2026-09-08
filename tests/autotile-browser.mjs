import { chromium } from 'playwright';
import { mkdir, writeFile } from 'node:fs/promises';
import { resolve } from 'node:path';
import assert from 'node:assert/strict';

const output=resolve('test-results/autotile-lab');await mkdir(output,{recursive:true});
const browser=await chromium.launch(),errors=[],results=[];
const url=(process.env.RUNTIME_QA_URL??'http://127.0.0.1:4175')+'/examples/autotile-lab/';
async function journey(mobile){
  const context=await browser.newContext(mobile?{viewport:{width:390,height:844},isMobile:true,hasTouch:true}:{viewport:{width:1280,height:1000}});
  const page=await context.newPage();page.on('pageerror',e=>errors.push(e.message));
  const button=selector=>mobile?page.locator(selector).tap():page.locator(selector).click();
  const count=n=>page.waitForFunction(n=>document.querySelector('#count')?.textContent.startsWith(`${n} bed tiles`),n);
  const cell=async(c,r)=>{
    const point=await page.locator('[data-runtime-debug]').evaluate((svg,{c,r})=>{
      const polygon=[...svg.querySelectorAll('polygon')].filter(p=>p.getAttribute('stroke')==='#00bcd4')[r*9+c];
      const points=polygon.getAttribute('points').split(' ').map(p=>p.split(',').map(Number)),box=svg.getBoundingClientRect();
      return{x:box.x+points.reduce((s,p)=>s+p[0],0)/4,y:box.y+points.reduce((s,p)=>s+p[1],0)/4};
    },{c,r});
    if(mobile)await page.touchscreen.tap(point.x,point.y);else await page.mouse.click(point.x,point.y);
  };
  try{
    await page.goto(url);await count(16);await button('#debug-toggle');
    await page.locator('#world').scrollIntoViewIfNeeded();
    await cell(4,4);await page.waitForFunction(()=>document.querySelector('#status').textContent.includes('No walking route'));
    await button('#edit');await page.locator('#world').scrollIntoViewIfNeeded();await cell(2,4);await count(15);
    await button('#edit');await page.locator('#world').scrollIntoViewIfNeeded();await cell(4,4);
    await page.waitForFunction(()=>document.querySelector('#position').textContent==='Traveler 4, 4');
    await button('#edit');await page.locator('#world').scrollIntoViewIfNeeded();await cell(4,4);
    assert.match(await page.locator('#status').textContent(),/Move the traveler/);await count(15);
    await page.screenshot({path:resolve(output,`${mobile?'mobile':'desktop'}-opened-ring.png`),fullPage:true});
    await button('#debug-toggle');
    for(const [shape,n]of(mobile?[['ring',16]]:[['straight',5],['l',9],['rectangle',25],['diagonal',2],['ring',16]])){
      await page.locator('#preset').selectOption(shape);await count(n);
      await page.screenshot({path:resolve(output,`${mobile?'mobile':'desktop'}-${shape}.png`),fullPage:true});
    }
    assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'No horizontal overflow');
    if(mobile){
      await button('#edit');
      // Find the public D-pad by its actual visible button text if the aria label differs.
      const pad=page.locator('#pad button').filter({hasText:'W'});await pad.scrollIntoViewIfNeeded();
      const box=await pad.boundingBox();assert.ok(box&&box.width>=40);
      const touch=await context.newCDPSession(page);
      await touch.send('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:[{x:box.x+box.width/2,y:box.y+box.height/2}]});
      await page.waitForTimeout(220);
      await touch.send('Input.dispatchTouchEvent',{type:'touchEnd',touchPoints:[]});
      await page.waitForFunction(()=>document.querySelector('#position').textContent!=='Traveler 1, 7');
      await page.screenshot({path:resolve(output,'mobile-play.png'),fullPage:true});
    }
    results.push({journey:mobile?'mobile touch edit and play':'desktop topology and traversal',pass:true});
  }catch(error){await page.screenshot({path:resolve(output,`${mobile?'mobile':'desktop'}-failure.png`),fullPage:true});throw error;}
  finally{await context.close();}
}
try{await journey(false);await journey(true);}catch(error){results.push({pass:false,error:String(error.stack)});}finally{await browser.close();}
console.log(JSON.stringify({results,errors}));await writeFile(resolve(output,'results.json'),JSON.stringify({results,errors},null,2));
process.exitCode=errors.length||results.some(r=>!r.pass)?1:0;
