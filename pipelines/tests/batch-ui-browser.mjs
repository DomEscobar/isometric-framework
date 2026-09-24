/* MOCK HTTP browser proof: no app import, ledger, provider or paid calls. */
import fs from 'node:fs';import path from 'node:path';import http from 'node:http';import assert from 'node:assert/strict';import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),links='/root/.cache/ms-playwright/.links';
const roots=fs.readdirSync(links).map(f=>fs.readFileSync(path.join(links,f),'utf8')).filter(p=>fs.existsSync(p+'/package.json'));const {chromium}=require(roots[0]);
const server=http.createServer((req,res)=>{res.setHeader('Content-Type',req.url==='/workflows.js'?'application/javascript':'text/html');res.end(fs.readFileSync(req.url==='/workflows.js'?'static/workflows.js':'static/index.html'));});
await new Promise(r=>server.listen(0,'127.0.0.1',r));
const browser=await chromium.launch({executablePath:'/root/.cache/ms-playwright/chromium_headless_shell-1234/chrome-linux/headless_shell',args:['--no-sandbox']});
try{
 const page=await browser.newPage();page.setDefaultTimeout(4000);const errors=[],posts=[];page.on('pageerror',e=>errors.push(e.message));
 let batch={id:'a'.repeat(64),status:'needs_attention',display_status:'needs_attention',terminal:false,can_resume:true,can_cancel:true,frozen:{revision:'b'.repeat(64),density:1},limits:{initial_per_style:1,repair_per_style:0},styles:[{style_spec_id:'c'.repeat(64),phase:'submitting',display_status:'running',stop_reason:'unknown_submission; receipt required',source_candidate_id:null,candidate_id:null,evaluation_id:null}]};
 await page.route('**/api/**',async route=>{const req=route.request(),url=new URL(req.url());let value={};
 if(req.method()==='POST'){posts.push(url.pathname);if(url.pathname.endsWith('/cancel'))batch={...batch,status:'cancelled',display_status:'cancelled',terminal:true,can_cancel:false,can_resume:false};}
 if(url.pathname==='/api/overnight-batch')value=[batch];else if(url.pathname.startsWith('/api/overnight-batch/'))value=batch;
 else if(url.pathname==='/api/style-presets')value=[];else if(url.pathname==='/api/generation/status')value={enabled:false,authenticated:false,total_budget_usd:'10',reserved_usd:'1',reasons:['MOCK closed']};else if(url.pathname==='/api/reviewer/config')value={enabled:false};
 await route.fulfill({json:value});});
 await page.goto(`http://127.0.0.1:${server.address().port}`);
 await page.waitForFunction(()=>document.querySelector('#batchId')?.value==='a'.repeat(64));
 assert.match(await page.locator('#batchProgress').innerText(),/unknown_submission/);
 await page.locator('#batchResume').click();await page.waitForFunction(()=>document.querySelector('#batchResume').disabled===false);
 assert(posts.includes('/api/overnight-batch/'+batch.id+'/resume'));
 await page.locator('#batchCancel').click();await page.waitForFunction(()=>document.querySelector('#batchProgress').textContent.includes('cancelled'));
 assert(await page.locator('#batchResume').isDisabled());assert(await page.locator('#batchCancel').isDisabled());
 await page.reload();await page.waitForFunction(()=>document.querySelector('#batchProgress')?.textContent.includes('cancelled'));
 await page.setViewportSize({width:390,height:844});assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth),390);
 assert.deepEqual(errors,[]);assert.equal(posts.length,2);console.log('PASS saved discovery, resume/readback, durable cancelled reload, mobile width; MOCK HTTP only');
}finally{await browser.close();await new Promise(r=>server.close(r));}
