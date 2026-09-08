import { chromium } from 'playwright';
import { mkdir, writeFile } from 'node:fs/promises';
import { resolve } from 'node:path';
import assert from 'node:assert/strict';

const output=resolve('test-results/willow-quay/bank-repair'); await mkdir(output,{recursive:true});
const baseline=process.argv.includes('--baseline');
const browser=await chromium.launch(); const results=[],errors=[];
async function journey(mobile=false){
  const name=baseline?'baseline':mobile?'mobile':'desktop';
  const context=await browser.newContext(mobile?{viewport:{width:390,height:844},isMobile:true,hasTouch:true}:{viewport:{width:1440,height:1000}});
  const page=await context.newPage();page.setDefaultTimeout(12000);page.on('pageerror',e=>errors.push(e.message));
  const press=s=>mobile?page.locator(s).tap():page.locator(s).click();
  const records=[];
  async function debug(value){if((await page.locator('#debug-toggle').getAttribute('aria-pressed')==='true')!==value)await press('#debug-toggle');}
  async function tile(c,r){
    await debug(true);const point=await page.locator('[data-runtime-debug]').evaluate((svg,{c,r})=>{
      const p=[...svg.querySelectorAll('polygon')].filter(p=>p.getAttribute('stroke')==='#00bcd4')[r*14+c];
      const points=p.getAttribute('points').split(' ').map(p=>p.split(',').map(Number));const b=svg.getBoundingClientRect();
      return{x:b.x+points.reduce((s,p)=>s+p[0],0)/4,y:b.y+points.reduce((s,p)=>s+p[1],0)/4};
    },{c,r});await debug(false);if(mobile)await page.touchscreen.tap(point.x,point.y);else await page.mouse.click(point.x,point.y);
  }
  async function idle(c,r){
    await debug(true);await page.waitForFunction(({c,r})=>{
      const text=document.querySelector('[data-debug-details]').textContent;
      return text.includes(`Cell: ${c},${r} · ground`)&&text.includes('state: idle')&&text.includes('Route: none');
    },{c,r});return await page.locator('[data-debug-details]').textContent();
  }
  async function capture(c,r,label){
    const details=await idle(c,r);await debug(false);await press('#zoom-in');if(mobile)await press('#zoom-in');
    assert.ok((await page.locator('#position').textContent()).startsWith(`${c}, ${r} ·`));
    await page.screenshot({path:resolve(output,`${name}-${label}.png`),fullPage:true});
    records.push({label,details});await press('#fit');
  }
  try{
    await page.goto(`${process.env.RUNTIME_QA_URL??'http://127.0.0.1:4175'}/examples/willow-quay/`);await page.locator('#world[aria-busy="false"]').waitFor();
    await page.waitForTimeout(400);
    await writeFile(resolve(output,`${name}-scene.json`),JSON.stringify(await page.evaluate(async()=>{const {createQuayScene}=await import('/examples/willow-quay/scene.ts');return createQuayScene();}),null,2));
    await press('[data-destination="bridge"]');await idle(7,11);
    await tile(3,9);await idle(3,9);await tile(4,9);await capture(4,9,'bank4-facing-ne');
    if(!baseline&&!mobile){
      await tile(1,9);records.push({label:'physical west-bank walk',details:await idle(1,9)});
      await tile(5,9);await idle(5,9);await tile(4,9);await capture(4,9,'bank4-facing-sw');
      await tile(9,9);await idle(9,9);await tile(10,9);await capture(10,9,'bank10-facing-ne');
    }
    assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'No horizontal overflow');
    results.push({journey:name,pass:true,records});
  }catch(error){await page.screenshot({path:resolve(output,`${name}-failure.png`),fullPage:true});results.push({journey:name,pass:false,error:String(error.stack),records});}
  finally{await context.close();}
}
try{await journey();if(!baseline&&!process.argv.includes('--desktop-only'))await journey(true);}finally{await browser.close();}
await writeFile(resolve(output,baseline?'baseline-results.json':process.argv.includes('--desktop-only')?'desktop-rerun-results.json':'results.json'),JSON.stringify({results,errors},null,2));
console.log(JSON.stringify({results,errors},null,2));process.exitCode=errors.length||results.some(r=>!r.pass)?1:0;
