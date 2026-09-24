/* Explicit HTTP fixtures: UI accounting/readiness only, not live repair proof. */
import fs from 'node:fs';
import path from 'node:path';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),links='/root/.cache/ms-playwright/.links';
const roots=fs.readdirSync(links).map(f=>fs.readFileSync(path.join(links,f),'utf8')).filter(p=>fs.existsSync(p+'/package.json'));
const {chromium}=require(roots[0]);
const browser=await chromium.launch({executablePath:'/root/.cache/ms-playwright/chromium_headless_shell-1234/chrome-linux/headless_shell',headless:true,args:['--no-sandbox']});
try {
 const page=await browser.newPage({viewport:{width:1280,height:900}});page.setDefaultTimeout(3000);
 const id='a'.repeat(64);let proofCalls=0;
 await page.route('**/api/auto-repair/'+id,route=>route.fulfill({json:{id,status:'needs_attention',phase:'plan',max_iterations:15,inherited_iterations:2,iterations:[],best_candidate_id:'b'.repeat(64),latest_candidate_id:'c'.repeat(64),stop_reason:'MOCK readiness test'}}));
 await page.route('**/api/auto-repair/'+id+'/continuation-readiness',route=>{proofCalls++;return route.fulfill({json:{eligible:false,blockers:['materials: missing final evidence citation'],lifetime_iterations:2}});});
 await page.goto(process.env.BASE_URL||'http://127.0.0.1:47847');
 await page.locator('#autoRepairId').fill(id);await page.locator('#autoRepairStatus').click();
 await page.waitForFunction(()=>window.autoRun?.id==='a'.repeat(64));
 assert.match(await page.locator('#autoRepairProgress').innerText(),/2\/15/,'lifetime count must include ancestor attempts');
 await page.locator('#autoRepairReadiness').click();
 await page.waitForFunction(()=>document.getElementById('autoRepairReadinessStatus').textContent.includes('missing final'));
 assert.match(await page.locator('#autoRepairReadinessStatus').innerText(),/GESPERRT/);
 assert.equal(proofCalls,1);
 console.log(JSON.stringify({result:'PASS',scope:'mock HTTP UI only',inherited_accounting:true,readiness_blocker:true}));
} finally {await browser.close();}
