/* Authorized service start/resume observer. No provider calls or candidate handoffs. */
import fs from 'node:fs';import path from 'node:path';import assert from 'node:assert/strict';import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),links='/root/.cache/ms-playwright/.links';const roots=fs.readdirSync(links).map(f=>fs.readFileSync(path.join(links,f),'utf8')).filter(p=>fs.existsSync(p+'/package.json'));
const {chromium}=require(roots[0]);const browser=await chromium.launch({executablePath:'/root/.cache/ms-playwright/chromium_headless_shell-1234/chrome-linux/headless_shell',headless:true,args:['--no-sandbox']});
const base=process.env.BASE_URL||'http://127.0.0.1:38363',out='evidence/quality-recovery/browser';fs.mkdirSync(out,{recursive:true});
const parent='8e96cc6e6289256aead3f64d8ea86bfc132d7c47dee27898749bf43428cc1577',resume=process.argv.includes('--resume');
try{
 const page=await browser.newPage({viewport:{width:1440,height:1100},acceptDownloads:true});const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto(base);await page.locator('#brief').fill('');await page.getByText('Explizite Formparameter (optional)',{exact:true}).click();await page.locator('#kind').selectOption('urban');await page.locator('#seed').fill('20260922');await page.locator('#generate').click();await page.waitForFunction(()=>window.workbench?.revision);
 await page.locator('#candidateId').fill('f3bdc310f809cf7a6b95015cc16af343e337a192e1865432ac530eb2b02fa96a');await page.locator('#loadCandidate').click();await page.waitForFunction(()=>window.candidateImage?.complete);
 await page.locator('#stylePreset').selectOption('urban-calm-warm');await page.locator('#loadPreset').click();await page.waitForFunction(()=>window.styleSpec?.id);
 await page.locator('#view').selectOption('candidate');await page.locator('#diagnostics').uncheck();await page.locator('#zoom').click();
 if(!resume)await page.locator('#scene').screenshot({path:out+'/before-native.png'});
 const target=resume?fs.readFileSync('evidence/quality-recovery/run-id.txt','utf8').trim():parent;
 const endpoint='/api/auto-repair/'+target+'/recover-seed'+(resume?'/resume':'');
 const body={confirm_paid:true};fs.writeFileSync(out+'/'+(resume?'resume':'start')+'-request.json',JSON.stringify({endpoint,body},null,2));
 const response=await page.request.post(base+endpoint,{data:body});assert(response.ok(),await response.text());let w=await response.json();
 fs.writeFileSync(out+'/'+(resume?'resume':'start')+'-response.json',JSON.stringify(w,null,2));
 const rid=w.id;fs.writeFileSync('evidence/quality-recovery/run-id.txt',rid);
 let last='';const seen=[];
 for(let i=0;i<360;i++){
  w=await (await page.request.get(base+'/api/auto-repair/'+rid)).json();
  const key=w.iterations.length+'-'+w.phase+'-'+w.status;
  if(key!==last){last=key;seen.push({phase:w.phase,status:w.status,iterations:w.iterations.length});await page.evaluate(id=>showAutoRun(id),rid);await page.locator('#autoRepairPanel').screenshot({path:out+'/phase-'+key+'.png'});fs.writeFileSync(out+'/phase-'+key+'.json',JSON.stringify(w,null,2));}
  if(w.status!=='running')break;
  await page.waitForTimeout(1500);
 }
 assert.notEqual(w.status,'running','observation timeout: inspect existing service run; NEVER resubmit');
 fs.writeFileSync('evidence/quality-recovery/run-final.json',JSON.stringify(w,null,2));
 fs.writeFileSync(out+'/'+(resume?'resume':'start')+'-observation.json',JSON.stringify({rid,seen,errors},null,2));
 assert.deepEqual(errors,[]);console.log(JSON.stringify({rid,status:w.status,phase:w.phase,stop_reason:w.stop_reason,latest:w.latest_candidate_id,iterations:w.iterations.length,inherited:w.inherited_iterations}));
}finally{await browser.close();}
