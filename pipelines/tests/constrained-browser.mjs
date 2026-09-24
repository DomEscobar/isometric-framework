/* Retained evidence only: no start, upload, quote or paid request. */
import fs from 'node:fs';import path from 'node:path';import assert from 'node:assert/strict';import crypto from 'node:crypto';import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),links='/root/.cache/ms-playwright/.links';
const roots=fs.readdirSync(links).map(f=>fs.readFileSync(path.join(links,f),'utf8')).filter(p=>fs.existsSync(p+'/package.json'));const {chromium}=require(roots[0]);
const base=process.env.BASE_URL||'http://127.0.0.1:45567',out='evidence/constrained-recovery';const w=JSON.parse(fs.readFileSync(out+'/run.json'));
const browser=await chromium.launch({executablePath:'/root/.cache/ms-playwright/chromium_headless_shell-1234/chrome-linux/headless_shell',headless:true,args:['--no-sandbox']});
try{
 const page=await browser.newPage({viewport:{width:1560,height:960},deviceScaleFactor:1});const errors=[];page.on('pageerror',e=>errors.push(e.message));
 const before=await (await page.request.get(base+'/api/generation/status')).json();
 const endpoint=base+'/api/generation/jobs/'+w.iterations[0].job_id+'/constrained-original';
 const download=await page.request.get(endpoint);assert.equal(download.status(),200);const raw=await download.body();fs.writeFileSync(out+'/browser-downloaded-original.jpg',raw);
 assert(raw.equals(fs.readFileSync(out+'/provider-original.jpg')));
 await page.goto(endpoint);await page.waitForFunction(()=>document.images[0]?.complete);
 const sizes=await page.evaluate(()=>({natural:[document.images[0].naturalWidth,document.images[0].naturalHeight],display:[document.images[0].clientWidth,document.images[0].clientHeight]}));
 assert.deepEqual(sizes,{natural:[768,512],display:[768,512]});await page.locator('img').screenshot({path:out+'/browser-original-native.png'});
 await page.goto(base);await page.locator('#autoRepairId').fill(w.id);await page.locator('#autoRepairStatus').click();await page.waitForFunction(id=>window.autoRun?.id===id,w.id);
 assert.match(await page.locator('#autoRepairProgress').innerText(),/lokal verworfen/);
 assert.doesNotMatch(await page.locator('#autoRepairProgress').innerText(),/undefined/);
 assert.equal(await page.locator('#constrainedOriginalLink').getAttribute('href'),'/api/generation/jobs/'+w.iterations[0].job_id+'/constrained-original');
 await page.locator('#autoRepairPanel').screenshot({path:out+'/browser-run-status.png'});
 assert.equal(Number(await page.locator('#autoRepairMax').inputValue()),15);
 const seed=w.continuation.seed_proof;
 const prod=await page.request.get(base+`/api/terrain/${seed.candidate_id}/download?revision=${w.frozen.revision}&density=1&mode=production&evaluation_id=${seed.evaluation_id}`);
 assert.equal(prod.status(),409);
 const after=await (await page.request.get(base+'/api/generation/status')).json();assert.deepEqual(before,after);assert.deepEqual(errors,[]);
 const report={result:'PASS retained evidence transport/UI; terrain FAIL',sizes,original_sha256:crypto.createHash('sha256').update(raw).digest('hex'),production_status:prod.status(),accounting:after,errors};
 fs.writeFileSync(out+'/browser-report.json',JSON.stringify(report,null,2));console.log(JSON.stringify(report));
}finally{await browser.close();}
