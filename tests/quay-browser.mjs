import { chromium } from 'playwright';
import { mkdir, writeFile } from 'node:fs/promises';
import { resolve } from 'node:path';
import assert from 'node:assert/strict';

const output = resolve(process.env.QUAY_QA_OUTPUT ?? 'test-results/willow-quay/playtest');
await mkdir(output, { recursive: true });
const browser = await chromium.launch();
const results = [], errors = [];
const url = `${process.env.RUNTIME_QA_URL ?? 'http://127.0.0.1:4175'}/examples/willow-quay/`;
async function journey(mobile) {
  const name = mobile ? 'mobile' : 'desktop';
  const context = await browser.newContext(mobile ? { viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true } : { viewport: { width: 1440, height: 1000 } });
  const page = await context.newPage();
  page.setDefaultTimeout(12000);
  page.on('pageerror', e => errors.push({ journey: name, error: e.message }));
  const checks = [], routes = [], idleStates = [];
  let trace;
  const press = selector => mobile ? page.locator(selector).tap() : page.locator(selector).click();
  const pos = () => page.locator('#position').textContent();
  const screenshot = label => page.screenshot({ path: resolve(output, `${name}-${label}.png`), fullPage: true });
  async function debug(enabled) {
    if ((await page.locator('#debug-toggle').getAttribute('aria-pressed') === 'true') !== enabled) await press('#debug-toggle');
  }
  async function tilePoint(c, r) {
    await debug(true);
    await page.locator('#world').scrollIntoViewIfNeeded();
    return page.locator('[data-runtime-debug]').evaluate((svg, { c, r }) => {
      const polygon = [...svg.querySelectorAll('polygon')].filter(p => p.getAttribute('stroke') === '#00bcd4')[r * 14 + c];
      const points = polygon.getAttribute('points').split(' ').map(p => p.split(',').map(Number));
      const box = svg.getBoundingClientRect();
      return { x: box.x + points.reduce((s,p) => s+p[0],0)/4, y: box.y + points.reduce((s,p) => s+p[1],0)/4, width:Math.max(...points.map(p=>p[0]))-Math.min(...points.map(p=>p[0])) };
    }, { c, r });
  }
  async function tile(c,r,xFraction=0) {
    const point = await tilePoint(c,r);
    point.x+=point.width*xFraction;
    await debug(false);
    if (mobile) await page.touchscreen.tap(point.x,point.y); else await page.mouse.click(point.x,point.y);
  }
  async function arrival(c,r,label,bridge=false) {
    await page.waitForFunction(({c,r})=>document.querySelector('#position').textContent.startsWith(`${c}, ${r} ·`),{c,r},{timeout:17000});
    const samples = await trace.evaluate(state=>state.records.splice(0));
    routes.push({ label, samples });
    assert.ok((await pos()).startsWith(`${c}, ${r} ·`),`${label}: arrival ${c},${r}; got ${await pos()}`);
    for(const sample of samples) {
      const [,sc,sr]=sample.match(/^(\d+), (\d+)/)??[];
      assert.ok(!(sample.endsWith('Ufer') && +sc>=6 && +sc<=8 && [6,9].includes(+sr)),`${label}: cannot walk beneath abutment/deck at ${sample}`);
    }
    if(bridge) assert.ok(samples.some(p=>p.endsWith('Brücke')),`${label}: physically crossed bridge level`);
    for(let i=1;i<samples.length;i++) {
      const a=samples[i-1].match(/^(\d+), (\d+)/).slice(1).map(Number), b=samples[i].match(/^(\d+), (\d+)/).slice(1).map(Number);
      assert.equal(Math.abs(a[0]-b[0])+Math.abs(a[1]-b[1]),1,`${label}: cardinal adjacent movement`);
    }
  }
  async function idleStair(c,r,label) {
    // The north stair center touches the upper deck polygon: click its exposed left interior.
    await tile(c,r,label==='north-stair'?-.2:0); await arrival(c,r,label);
    await debug(true);
    await page.waitForFunction(()=>{
      const text=document.querySelector('[data-debug-details]').textContent;
      return text.includes('state: idle') && text.includes('Route: none') && !text.includes('airborne');
    });
    const details=await page.locator('[data-debug-details]').textContent();
    assert.ok(details.includes(`Cell: ${c},${r} · ground · 16px`),`${label}: final idle must be the requested ground stair, not a passing route cell`);
    idleStates.push({label,position:await pos(),details});
    await debug(false); await press('#zoom-in');
    if(mobile) await press('#zoom-in');
    assert.ok((await pos()).startsWith(`${c}, ${r} ·`) && await page.locator('#position').getAttribute('data-level')==='ground',`${label}: zoom preserves exact ground stair position`);
    await screenshot(`${label}-idle-close`); await press('#fit');
  }
  try {
    await page.goto(url);
    await page.locator('#world[aria-busy="false"]').waitFor();
    trace=await page.evaluateHandle(()=>{
      const element=document.querySelector('#position');
      const state={records:[element.textContent],observer:null};
      state.observer=new MutationObserver(()=>{ const value=element.textContent; if(state.records.at(-1)!==value) state.records.push(value); });
      state.observer.observe(element,{childList:true,characterData:true,subtree:true});
      return state;
    });
    await page.waitForTimeout(400);
    if(process.argv.includes('--north-only')) {
      await tile(7,4); await arrival(7,4,'north approach');
      await idleStair(7,5,'north-stair');
      results.push({journey:'desktop north stair correction',pass:true,checks:['Exact requested settled ground stair before and after zoom'],routes,idleStates});
      return;
    }
    await screenshot('overview');
    assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'No horizontal overflow');
    await press('[data-destination="apothecary"]'); await arrival(4,5,'apothecary');
    await screenshot('building-front');
    if(!mobile) {
      await press('#zoom-in'); await screenshot('building-close-from-4-6'); await press('#fit');
    }
    checks.push('Destination button reaches apothecary');
    await tile(4,3);
    await page.waitForFunction(()=>document.querySelector('#status').textContent.includes('kein begehbarer'));
    assert.ok((await pos()).startsWith('4, 5 ·'),'House collision preserves position');
    await tile(3,7);
    await page.waitForFunction(()=>document.querySelector('#status').textContent.includes('kein begehbarer'));
    assert.ok((await pos()).startsWith('4, 5 ·'),'Water collision preserves position');
    checks.push('House and water clicks blocked');
    await press('[data-destination="bridge"]');
    await page.waitForTimeout(140); await press('#pause'); await debug(true);
    const frozen = await page.locator('[data-debug-details]').textContent();
    await page.waitForTimeout(550);
    assert.equal(await page.locator('[data-debug-details]').textContent(),frozen,'Pause freezes pose and clip');
    await debug(false); await press('#pause');
    if(!mobile) {
      await page.waitForFunction(()=>/^7, [78] · Brücke$/.test(document.querySelector('#position').textContent));
      await press('#pause'); await press('#zoom-in'); await screenshot('bridge-close');
      await press('#zoom-out'); await press('#pause');
    }
    await arrival(7,11,'outward bridge crossing',true);
    await screenshot('far-bank');
    checks.push('Pause/resume and real outward bridge traversal');
    await idleStair(7,10,'south-stair');
    await press('[data-destination="canal"]'); await arrival(11,6,'return bridge crossing',true);
    await screenshot('canal');
    checks.push('Return bridge traversal');
    await idleStair(7,5,'north-stair');
    checks.push('Physical arrival and settled idle on south and north stairs');
    if(!mobile) {
      await tile(4,1); await arrival(4,1,'behind building');
      await screenshot('building-behind');
      await tile(5,5); await arrival(5,5,'side approach to building');
      await tile(4,5); await arrival(4,5,'return in front of building from 5,5');
      await press('#zoom-in'); await screenshot('building-close'); await screenshot('building-close-from-5-5'); await press('#fit');
      checks.push('Actor walks behind and in front of building');
    } else {
      await tile(11,5); await arrival(11,5,'mobile clear control tile');
      const pad=page.locator('#touch-controls button').filter({hasText:'W'}); await pad.scrollIntoViewIfNeeded();
      const bounds=await pad.boundingBox(); assert.ok(bounds && bounds.width>=40);
      const touch=await context.newCDPSession(page);
      await touch.send('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:[{x:bounds.x+bounds.width/2,y:bounds.y+bounds.height/2}]});
      await page.waitForTimeout(360);
      await touch.send('Input.dispatchTouchEvent',{type:'touchEnd',touchPoints:[]});
      const controlPosition=await pos();
      assert.match(controlPosition,/^1[23], 5 · Ufer$/,'Held W advances along c+ only');
      routes.push({label:'held W moves c+',samples:await trace.evaluate(state=>state.records.splice(0))});
      await debug(true); await press('[aria-label="Springen"]');
      await page.waitForFunction(()=>document.querySelector('[data-debug-details]').textContent.includes('airborne'));
      await page.waitForFunction(()=>!document.querySelector('[data-debug-details]').textContent.includes('airborne'));
      await debug(false);
      await debug(true); const before=await page.locator('[data-runtime-debug] polygon').first().getAttribute('points');
      await debug(false); await press('#zoom-in'); await debug(true);
      const after=await page.locator('[data-runtime-debug] polygon').first().getAttribute('points');
      assert.notEqual(before,after,'Zoom in changes visible geometry');
      await debug(false); await press('#zoom-out');
      await screenshot('touch-controls');
      checks.push('Held touch W, airborne jump, zoom controls');
    }
    results.push({journey:name,pass:true,checks,routes,idleStates});
  } catch(error) {
    await screenshot('failure');
    results.push({journey:name,pass:false,checks,routes,idleStates,error:String(error.stack),position:await pos(),status:await page.locator('#status').textContent()});
  } finally { await context.close(); }
}
try { if(!process.argv.includes('--mobile-only')) await journey(false); if(!process.argv.includes('--desktop-only')&&!process.argv.includes('--north-only')) await journey(true); } finally { await browser.close(); }
await writeFile(resolve(output,process.argv.includes('--north-only')?'north-rerun-results.json':process.argv.includes('--mobile-only')?'mobile-rerun-results.json':process.argv.includes('--desktop-only')?'desktop-rerun-results.json':'results.json'),JSON.stringify({results,errors},null,2));
console.log(JSON.stringify({results,errors},null,2));
process.exitCode=errors.length || results.some(r=>!r.pass) ? 1 : 0;
