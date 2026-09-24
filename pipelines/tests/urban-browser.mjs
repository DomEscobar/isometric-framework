import fs from 'node:fs';import path from 'node:path';import assert from 'node:assert/strict';import {createRequire} from 'node:module';
const require=createRequire(import.meta.url), links='/root/.cache/ms-playwright/.links';
const candidates=fs.readdirSync(links).map(f=>fs.readFileSync(path.join(links,f),'utf8')).filter(p=>fs.existsSync(p+'/package.json'));
const {chromium}=require(process.env.PLAYWRIGHT_CORE||candidates[0]);
const browser=await chromium.launch({executablePath:process.env.CHROMIUM||'/root/.cache/ms-playwright/chromium_headless_shell-1234/chrome-linux/headless_shell',headless:true,args:['--no-sandbox']});
const base=process.env.BASE_URL||'http://127.0.0.1:53047',out=path.resolve(process.env.EVIDENCE||'evidence/urban-pilot/browser');fs.mkdirSync(out,{recursive:true});
try{
const page=await browser.newPage({viewport:{width:1440,height:1000},acceptDownloads:true});const errors=[];page.on('pageerror',e=>errors.push(e.message));
await page.goto(base);await page.locator('#brief').fill('');await page.getByText('Explizite Formparameter (optional)',{exact:true}).click();await page.locator('#kind').selectOption('urban');await page.locator('#seed').fill('20260922');await page.locator('#generate').click();await page.waitForFunction(()=>window.workbench?.revision);
const initial=await page.evaluate(()=>structuredClone(window.workbench));const reg=JSON.parse(fs.readFileSync(process.env.CANDIDATE_RECORD||'evidence/urban-pilot/registered-candidate.json','utf8'));assert.equal(initial.revision,reg.layout_revision);
await page.locator('#candidateId').fill(reg.id);await page.locator('#loadCandidate').click();await page.waitForFunction(()=>window.candidateImage?.complete);
assert.equal(await page.locator('#diagnostics').count(),1,'clean playable view needs an explicit diagnostic-overlay toggle');
assert(!(await page.locator('.badge').innerText()).includes('Budget 0'),'UI must not claim zero budget after authorization');
assert.match(await page.locator('#candidateStatus').innerText(),/needs_attention/,'saved grounded review must be visible independently of technical candidate metadata');
const graph=initial.validation.graph;
const keyFor=(a,b)=>b[0]>a[0]?'ArrowRight':b[0]<a[0]?'ArrowLeft':b[1]>a[1]?'ArrowDown':'ArrowUp';
async function walkTo(goal){const start=await page.evaluate(()=>[...window.workbench.actor]);const parents=new Map([[start.join(','),null]]),queue=[start];for(let i=0;i<queue.length;i++)for(const b of graph[queue[i].join(',')]||[])if(!parents.has(b.join(','))){parents.set(b.join(','),queue[i]);queue.push(b);}assert(parents.has(goal.join(',')));const route=[];for(let at=goal;at!==null;at=parents.get(at.join(',')))route.push(at);route.reverse();await page.locator('#scene').focus();for(let i=1;i<route.length;i++)await page.keyboard.press(keyFor(route[i-1],route[i]));assert.deepEqual(await page.evaluate(()=>window.workbench.actor),goal);return route.length-1;}
const navigation=[];for(const goal of initial.layout.goals)navigation.push({kind:'goal',goal,steps:await walkTo(goal)});
const water=[];initial.layout.materials.forEach((row,r)=>row.forEach((m,c)=>{if(m==='planting')water.push([c,r]);}));
const blockers=[['planting',water],...initial.layout.objects.map(o=>[o.id,Array.from({length:o.w*o.h},(_,i)=>[o.x+i%o.w,o.y+Math.floor(i/o.w)])])];
for(const [kind,cells] of blockers){let pair;for(const target of cells){for(const delta of [[1,0],[-1,0],[0,1],[0,-1]]){const near=[target[0]+delta[0],target[1]+delta[1]];if(graph[near.join(',')]){pair=[near,target];break;}}if(pair)break;}assert(pair);const [near,target]=pair,steps=await walkTo(near);await page.keyboard.press(keyFor(near,target));assert.deepEqual(await page.evaluate(()=>window.workbench.actor),near);assert.match(await page.locator('#motion').innerText(),/Blockiert/);navigation.push({kind,near,target,steps,blocked:true});}
navigation.push({kind:'technical-road-traversal-no-traffic',goal:[4,7],steps:await walkTo([4,7])});
await walkTo([0,4]);await page.keyboard.press('ArrowLeft');assert.deepEqual(await page.evaluate(()=>window.workbench.actor),[0,4]);navigation.push({kind:'world-edge',blocked:true});
for(const material of ['street','sidewalk','planting']){await page.locator('#view').selectOption(material);await page.waitForFunction(()=>document.querySelector('#image').complete&&document.querySelector('#image').naturalWidth>0);await page.locator('#image').screenshot({path:path.join(out,material+'-mask.png')});}await page.locator('#view').selectOption('candidate');
await walkTo(initial.layout.spawn);await page.locator('#zoom').click();
await page.locator('#stage').screenshot({path:path.join(out,'playable-diagnostics.png')});
await page.locator('#diagnostics').uncheck();await page.locator('#stage').screenshot({path:path.join(out,'play-scale-clean.png')});
await page.locator('#scene').screenshot({path:path.join(out,'canvas-native.png')});
const sampling=await page.evaluate(()=>{const c=document.querySelector('#scene'),r=c.getBoundingClientRect();return {canvas:[c.width,c.height],css:[r.width,r.height],dpr:devicePixelRatio,stageBackground:getComputedStyle(document.querySelector('#stage')).backgroundColor,canvasBackground:getComputedStyle(c).backgroundColor,canvasPosition:[r.x,r.y],actor:window.workbench.actor,diagnostics:document.querySelector('#diagnostics').checked,image:[window.candidateImage.naturalWidth,window.candidateImage.naturalHeight],source:window.candidateImage.src};});
assert(sampling.canvasPosition.every(v=>Number.isInteger(v)), 'play canvas must align to physical pixels at DPR1, not half-pixel CSS centering');assert.deepEqual(sampling.canvas,sampling.css);assert.equal(sampling.diagnostics,false);
await page.locator('#view').selectOption('comparison');await page.locator('#comparison').screenshot({path:path.join(out,'original-vs-guide.png')});
if(process.env.EVALUATE_SPEC==='1'){
 await page.locator('#finalDensity').selectOption('1');
 await page.locator('#stylePreset').selectOption('urban-calm-warm');await page.locator('#loadPreset').click();await page.waitForFunction(()=>window.styleSpec?.id);
 await page.locator('#prepareEvaluation').click();await page.waitForFunction(()=>window.currentEvaluation?.status==='reviewed');
 await page.locator('#strictReviewStatus').screenshot({path:path.join(out,'strict-review-native.png')});
 const prod=await page.request.get(base+await page.evaluate(()=>exportUrl('production')));assert.equal(prod.status(),409);
}
if(process.env.EVALUATE_SPEC!=='1')await page.locator('#finalDensity').selectOption('1');const dl=page.waitForEvent('download');await page.locator('#candidateDownload').click();const download=await dl;await download.saveAs(path.join(out,download.suggestedFilename()));assert.equal(await download.failure(),null);
await page.locator('#view').selectOption('candidate');
if(process.env.CAPTURE_TRAVERSAL==='1'){
 const frames=path.join(out,'traversal-frames');fs.mkdirSync(frames,{recursive:true});await page.locator('#diagnostics').uncheck();let i=0;
 for(const key of [...Array(11).fill('ArrowRight'),...Array(11).fill('ArrowLeft')]){await page.locator('#scene').focus();await page.keyboard.press(key);await page.locator('#scene').evaluate(e=>e.blur());await page.locator('#scene').screenshot({path:path.join(frames,String(i++).padStart(3,'0')+'.png')});}
 assert.deepEqual(await page.evaluate(()=>window.workbench.actor),initial.layout.spawn);
}
await page.locator('#diagnostics').check();await page.screenshot({path:path.join(out,'ui.png'),fullPage:true});
assert.deepEqual(errors,[]);fs.writeFileSync(path.join(out,'browser-report.json'),JSON.stringify({result:'PASS',candidate:reg.id,revision:initial.revision,download:download.suggestedFilename(),sampling,navigation,errors},null,2));console.log(JSON.stringify({result:'PASS',out,download:download.suggestedFilename(),errors}));
}finally{await browser.close();}
