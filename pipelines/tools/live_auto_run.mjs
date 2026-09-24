/* REAL paid run only with explicit AUTO_REPAIR_AUTHORIZATION.md. Never use as regression. */
import fs from 'node:fs';import path from 'node:path';import assert from 'node:assert/strict';import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),links='/root/.cache/ms-playwright/.links';const roots=fs.readdirSync(links).map(f=>fs.readFileSync(path.join(links,f),'utf8')).filter(p=>fs.existsSync(p+'/package.json'));
const {chromium}=require(roots[0]);const browser=await chromium.launch({executablePath:'/root/.cache/ms-playwright/chromium_headless_shell-1234/chrome-linux/headless_shell',headless:true,args:['--no-sandbox']});
const base=process.env.BASE_URL||'http://127.0.0.1:59649',out='evidence/auto-repair/browser';fs.mkdirSync(out,{recursive:true});
try{
 const page=await browser.newPage({viewport:{width:1440,height:1000},acceptDownloads:true});const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto(base);await page.locator('#brief').fill('');await page.getByText('Explizite Formparameter (optional)',{exact:true}).click();await page.locator('#kind').selectOption('urban');await page.locator('#seed').fill('20260922');await page.locator('#generate').click();await page.waitForFunction(()=>window.workbench?.revision);
 await page.locator('#candidateId').fill('f3bdc310f809cf7a6b95015cc16af343e337a192e1865432ac530eb2b02fa96a');await page.locator('#loadCandidate').click();await page.waitForFunction(()=>window.candidateImage?.complete);
 await page.locator('#stylePreset').selectOption('urban-calm-warm');await page.locator('#loadPreset').click();await page.waitForFunction(()=>window.styleSpec?.id);
 await page.locator('#prepareEvaluation').click();await page.waitForFunction(()=>window.currentEvaluation?.status==='reviewed');
 await page.locator('#view').selectOption('candidate');await page.locator('#diagnostics').uncheck();await page.locator('#zoom').click();await page.locator('#scene').screenshot({path:out+'/before-native.png'});
 await page.locator('#autoRepairMax').fill('15');page.once('dialog',d=>d.accept());await page.locator('#autoRepairStart').click();await page.waitForFunction(()=>window.autoRun?.id);
 const rid=await page.evaluate(()=>window.autoRun.id);fs.writeFileSync('evidence/auto-repair/run-id.txt',rid);await page.locator('#autoRepairPanel').screenshot({path:out+'/running.png'});
 let w;let last='';
 for(let i=0;i<240;i++){
  w=await (await page.request.get(base+'/api/auto-repair/'+rid)).json();
  if(w.phase!==last){last=w.phase;await page.evaluate(id=>showAutoRun(id),rid);await page.locator('#autoRepairPanel').screenshot({path:out+'/phase-'+last+'.png'});}
  if(w.status!=='running')break;
  await page.waitForTimeout(2500);
 }
 assert.notEqual(w.status,'running','bounded observation timeout, do not buy another run');
 await page.evaluate(id=>showAutoRun(id),rid);await page.locator('#autoRepairPanel').screenshot({path:out+'/final-status.png'});
 fs.writeFileSync('evidence/auto-repair/run-final.json',JSON.stringify(w,null,2));fs.writeFileSync(out+'/live-browser.json',JSON.stringify({rid,status:w.status,stop_reason:w.stop_reason,errors},null,2));assert.deepEqual(errors,[]);console.log(JSON.stringify({rid,status:w.status,stop_reason:w.stop_reason,iterations:w.iterations.length}));
}finally{await browser.close();}
