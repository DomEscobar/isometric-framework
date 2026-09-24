import fs from 'node:fs';import path from 'node:path';import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),out='evidence/hybrid-reassessment-repair',RID='3c92b111114d479485d3aafe4991d441';
const links='/root/.cache/ms-playwright/.links',candidates=fs.readdirSync(links).map(f=>fs.readFileSync(path.join(links,f),'utf8')).filter(p=>fs.existsSync(p+'/package.json'));const {chromium}=require(candidates[0]);
const browser=await chromium.launch({executablePath:'/root/.cache/ms-playwright/chromium_headless_shell-1234/chrome-linux/headless_shell',headless:true,args:['--no-sandbox']});
try{const page=await browser.newPage({viewport:{width:800,height:600},deviceScaleFactor:1});
 // 1) extracted offline production HTML at native gameplay scale
 await page.goto('file://'+process.cwd()+'/'+out+'/extracted/index.html');
 await page.waitForTimeout(1500);
 const size=await page.evaluate(()=>{const c=document.querySelector('canvas');return {w:c.width,h:c.height}});
 await page.setViewportSize({width:size.w+40,height:size.h+40});
 await page.waitForTimeout(400);
 await page.locator('canvas').screenshot({path:out+'/offline-gameplay-native.png'});
 // 2) before/after and final scene at natural gameplay scale
 const scenes=[['before','file://'+process.cwd()+'/data/hybrid/b9a94348e6404358b353d3b3c5fd5f24/sample-1-0/scene.png'],
   ['after','file://'+process.cwd()+'/data/hybrid/'+RID+'/sample-3-0/scene.png'],
   ['final','file://'+process.cwd()+'/data/hybrid/'+RID+'/candidate-9/scene.png']];
 for(const [name,url] of scenes){
   await page.goto(url);
   await page.evaluate(()=>{document.body.style.margin='0';document.body.style.background='#282b28';const i=document.querySelector('img');i.style.cssText='display:block;position:absolute;left:0;top:0;max-width:none;image-rendering:pixelated;';});
   const dim=await page.evaluate(()=>{const i=document.querySelector('img');return {w:i.naturalWidth,h:i.naturalHeight}});
   await page.setViewportSize({width:dim.w,height:dim.h});
   await page.locator('img').screenshot({path:out+'/'+name+'-gameplay-native.png'});
 }
 // 3) terminal production UI + reload proof
 await page.setViewportSize({width:1440,height:1000});
 await page.goto('http://127.0.0.1:48765');
 await page.evaluate(r=>localStorage.hybridRun=r,RID);
 await page.reload();
 await page.waitForFunction(()=>document.querySelector('#status').textContent.includes('succeeded'));
 await page.locator('#status').screenshot({path:out+'/final-status.png'});
 await page.screenshot({path:out+'/final-ui.png',fullPage:true});
 await page.reload();
 await page.waitForFunction(()=>document.querySelector('#status').textContent.includes('succeeded'));
 console.log(JSON.stringify({captured:true,canvas:size}));
}finally{await browser.close()}
