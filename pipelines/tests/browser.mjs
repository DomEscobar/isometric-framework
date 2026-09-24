import fs from 'node:fs';
import path from 'node:path';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url);
const base=process.env.BASE_URL || 'http://127.0.0.1:8766';
// Use installed tooling read-only; no installation into another project.
const links='/root/.cache/ms-playwright/.links';
const candidates=fs.readdirSync(links).map(f=>fs.readFileSync(path.join(links,f),'utf8')).filter(p=>fs.existsSync(p+'/package.json'));
const {chromium}=require(process.env.PLAYWRIGHT_CORE || candidates[0]);
const executablePath=process.env.CHROMIUM || '/root/.cache/ms-playwright/chromium_headless_shell-1234/chrome-linux/headless_shell';
const out=path.resolve(process.env.EVIDENCE || 'evidence/browser-01');
fs.mkdirSync(out,{recursive:true});
const browser=await chromium.launch({executablePath,headless:true,args:['--no-sandbox']});
try {
  const page=await browser.newPage({viewport:{width:1440,height:1050},acceptDownloads:true,hasTouch:true});
  const errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  const response=await page.goto(base+'/');
  assert.equal(response.status(),200);
  await page.locator('#generate').waitFor({timeout:5000});
  await page.locator('#brief').fill('Teich im Nordosten; Weg West-Ost; 1 Haus; 3 Bäume');
  await page.locator('#seed').fill('19');
  await page.locator('#generate').click();
  await page.waitForFunction(()=>window.workbench?.revision && document.querySelector('#status').dataset.state==='ready');
  const initial=await page.evaluate(()=>structuredClone(window.workbench));
  assert.equal(initial.layout.objects.length,4);
  assert(initial.validation.valid);
  await page.locator('#scene').focus();
  await page.keyboard.press('ArrowRight');
  const moved=await page.evaluate(()=>window.workbench.actor);
  assert.notDeepEqual(moved,initial.actor,'real keyboard input must move actor');
  // Walk to eastern map edge; one additional key must be blocked by swept-AABB graph.
  for(let i=0;i<35;i++) await page.keyboard.press('ArrowRight');
  const edge=await page.evaluate(()=>[...window.workbench.actor]);
  await page.keyboard.press('ArrowRight');
  assert.deepEqual(await page.evaluate(()=>window.workbench.actor),edge);
  assert.match(await page.locator('#motion').innerText(),/Blockiert/);
  const graph=initial.validation.graph;
  const keyFor=(a,b)=>b[0]>a[0]?'ArrowRight':b[0]<a[0]?'ArrowLeft':b[1]>a[1]?'ArrowDown':'ArrowUp';
  async function walkTo(goal) {
    const start=await page.evaluate(()=>[...window.workbench.actor]);
    const parents=new Map([[start.join(','),null]]),queue=[start];
    for(let i=0;i<queue.length;i++)for(const b of graph[queue[i].join(',')]||[])if(!parents.has(b.join(','))){parents.set(b.join(','),queue[i]);queue.push(b);}
    assert(parents.has(goal.join(',')),'navigation goal unreachable');
    const route=[];for(let at=goal;at!==null;at=parents.get(at.join(',')))route.push(at);route.reverse();
    await page.locator('#scene').focus();
    for(let i=1;i<route.length;i++)await page.keyboard.press(keyFor(route[i-1],route[i]));
    assert.deepEqual(await page.evaluate(()=>window.workbench.actor),goal);
    return route.length-1;
  }
  const navigation=[];
  for(const goal of initial.layout.goals)navigation.push({kind:'goal',goal,steps:await walkTo(goal)});
  const water=[];
  initial.layout.materials.forEach((row,r)=>row.forEach((m,c)=>{if(m==='water')water.push([c,r]);}));
  const blockers=[['water',water],...initial.layout.objects.map(o=>[o.id,Array.from({length:o.w*o.h},(_,i)=>[o.x+i%o.w,o.y+Math.floor(i/o.w)])])];
  for(const [kind,cells] of blockers){
    let pair;
    for(const target of cells){for(const delta of [[1,0],[-1,0],[0,1],[0,-1]]){const near=[target[0]+delta[0],target[1]+delta[1]];if(graph[near.join(',')]){pair=[near,target];break;}}if(pair)break;}
    assert(pair,'blocker must have a reachable test approach');
    const [near,target]=pair,steps=await walkTo(near);
    await page.keyboard.press(keyFor(near,target));
    assert.deepEqual(await page.evaluate(()=>window.workbench.actor),near);
    assert.match(await page.locator('#motion').innerText(),/Blockiert/);
    navigation.push({kind,near,target,steps,blocked:true});
  }
  await walkTo(initial.layout.spawn);
  await page.screenshot({path:path.join(out,'pond-blockout.png'),fullPage:true});
  await page.locator('#view').selectOption('guide');
  await page.waitForFunction(()=>document.querySelector('#image').complete && document.querySelector('#image').naturalWidth>0 && document.querySelector('#image').src.endsWith('clean-guide.png'));
  await page.screenshot({path:path.join(out,'clean-guide.png'),fullPage:true});
  await page.locator('#view').selectOption('water');
  await page.waitForFunction(()=>document.querySelector('#image').complete && document.querySelector('#image').naturalWidth>0 && document.querySelector('#image').src.endsWith('material-water.png'));
  await page.screenshot({path:path.join(out,'water-mask.png'),fullPage:true});
  // Local import uses the technical guide as an explicitly labelled test fixture, not art.
  const fixture=path.join(out,'technical-import-fixture.png');
  fs.writeFileSync(fixture,await (await page.request.get(`${base}/api/layouts/${initial.revision}/artifacts/clean-guide.png`)).body());
  await page.locator('#terrainFile').setInputFiles(fixture);
  await page.locator('#importTerrain').click();
  await page.waitForFunction(()=>document.querySelector('#terrainReport').textContent.includes('needs_attention'));
  const imported=JSON.parse(await page.locator('#terrainReport').innerText());
  assert.equal(imported.registration.image_alignment,'unverified');
  assert.equal(imported.production_approved,false);
  assert.deepEqual(await (await page.request.get(base+'/api/terrain/'+imported.id)).json(),imported);
  await page.screenshot({path:path.join(out,'local-import-needs-attention.png'),fullPage:true});
  const dl=page.waitForEvent('download');
  await page.locator('#download').click();
  const download=await dl;
  await download.saveAs(path.join(out,download.suggestedFilename()));
  assert.equal(await download.failure(),null);
  // Unknown brief is a visible error, not a silently simplified success.
  await page.locator('#brief').fill('Berge und Brücke');
  await page.locator('#generate').click();
  await page.waitForFunction(()=>document.querySelector('#status').dataset.state==='error');
  assert.match(await page.locator('#status').innerText(),/unsupported/);
  await page.screenshot({path:path.join(out,'unsupported-brief.png'),fullPage:true});
  const examples=[];
  for(const [name,brief,seed] of [['meadow','Wiese; Weg West-Ost; 2 Bäume',3],['plaza','Platz; Weg Kreuz; 4 Bäume',81]]) {
    await page.locator('#brief').fill(brief); await page.locator('#seed').fill(String(seed));
    await page.locator('#generate').click();
    await page.waitForFunction(()=>document.querySelector('#status').dataset.state==='ready');
    await page.locator('#view').selectOption('blockout');
    examples.push(await page.evaluate(()=>({revision:window.workbench.revision,layout:window.workbench.layout})));
    await page.screenshot({path:path.join(out,name+'-blockout.png'),fullPage:true});
  }
  await page.setViewportSize({width:390,height:844});
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'mobile must not overflow horizontally');
  const beforeTouch=await page.evaluate(()=>[...window.workbench.actor]);
  await page.locator('[data-key="ArrowRight"]').tap();
  assert.deepEqual(await page.evaluate(()=>window.workbench.actor),[beforeTouch[0]+1,beforeTouch[1]]);
  await page.screenshot({path:path.join(out,'mobile.png'),fullPage:true});
  assert.deepEqual(errors,[]);
  fs.writeFileSync(path.join(out,'browser-report.json'),JSON.stringify({url:page.url(),revision:initial.revision,initialActor:initial.actor,moved,edge,navigation,imported,touch:{before:beforeTouch,after:await page.evaluate(()=>window.workbench.actor)},errors,download:download.suggestedFilename(),examples,executablePath},null,2));
  console.log(JSON.stringify({result:'PASS',out,revision:initial.revision,download:download.suggestedFilename(),errors}));
} finally {await browser.close();}
