/* Read-only live follow-up verification. No provider submissions. */
import fs from 'node:fs';import path from 'node:path';import assert from 'node:assert/strict';import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),links='/root/.cache/ms-playwright/.links';const roots=fs.readdirSync(links).map(f=>fs.readFileSync(path.join(links,f),'utf8')).filter(p=>fs.existsSync(p+'/package.json'));const {chromium}=require(roots[0]);
const base=process.env.BASE_URL||'http://127.0.0.1:47847',out='evidence/repair-followup';fs.mkdirSync(out,{recursive:true});
const rid='8e96cc6e6289256aead3f64d8ea86bfc132d7c47dee27898749bf43428cc1577';
const browser=await chromium.launch({executablePath:'/root/.cache/ms-playwright/chromium_headless_shell-1234/chrome-linux/headless_shell',headless:true,args:['--no-sandbox']});
try{
 const page=await browser.newPage({viewport:{width:1440,height:1000}});const errors=[];page.on('pageerror',e=>errors.push(e.message));
 const get=async url=>{const r=await page.request.get(base+url);assert.equal(r.status(),200);return r.json();};
 const before=await get('/api/generation/status'),runBefore=await get('/api/auto-repair/'+rid);
 await page.goto(base);await page.locator('#autoRepairId').fill(rid);await page.locator('#autoRepairStatus').click();await page.waitForFunction(id=>window.autoRun?.id===id,rid);
 await page.locator('#autoRepairReadiness').click();await page.waitForFunction(()=>document.getElementById('autoRepairReadinessStatus').textContent.includes('missing final'));
 assert.match(await page.locator('#autoRepairProgress').innerText(),/1\/15/);assert.match(await page.locator('#autoRepairReadinessStatus').innerText(),/GESPERRT/);
 const proof=await get('/api/auto-repair/'+rid+'/continuation-readiness');assert.equal(proof.eligible,false);assert.equal(proof.read_only,true);assert.equal(proof.lifetime_iterations,1);
 await page.locator('#autoRepairPanel').screenshot({path:out+'/urban-continuation-blockers.png'});
 await page.reload();await page.waitForFunction(id=>window.autoRun?.id===id,rid);assert.equal(await page.locator('#autoRepairMax').inputValue(),'15');
 await page.setViewportSize({width:390,height:844});await page.locator('#autoRepairReadiness').click();await page.waitForFunction(()=>document.getElementById('autoRepairReadinessStatus').textContent.includes('missing final'));
 assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
 const after=await get('/api/generation/status');assert.deepEqual(after,before);assert.deepEqual(await get('/api/auto-repair/'+rid),runBefore);assert.deepEqual(errors,[]);
 const result={result:'PASS: genuine read-only blocked run; not successful repair',run_id:rid,readiness:proof,budget:after,run_unchanged:true,desktop_mobile:true,pageerrors:errors};fs.writeFileSync(out+'/live-verification.json',JSON.stringify(result,null,2));console.log(JSON.stringify(result));
}finally{await browser.close();}
