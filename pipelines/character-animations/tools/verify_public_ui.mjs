import {chromium} from '/root/games/waldlicht/node_modules/playwright/index.mjs';
import fs from 'node:fs/promises';
import assert from 'node:assert/strict';
const browser=await chromium.launch({headless:true,executablePath:'/root/.cache/ms-playwright/chromium_headless_shell-1234/chrome-linux/headless_shell',args:['--no-sandbox']});
try{
const p=await browser.newPage({viewport:{width:1280,height:900}});const errors=[];p.on('pageerror',e=>errors.push(e.message));
await p.goto('https://huecki.com/animation/ui/',{waitUntil:'networkidle'});
await p.waitForFunction(()=>document.querySelector('canvas')?.dataset.frame!==undefined);
const a=await p.locator('canvas').first().getAttribute('data-frame');await p.waitForTimeout(300);const b=await p.locator('canvas').first().getAttribute('data-frame');assert.notEqual(a,b);assert.equal(errors.length,0);
const env=await fs.readFile('/etc/animation-pipeline.env','utf8');const token=env.split('\n').find(l=>l.startsWith('ANIMATION_API_TOKEN=')).split('=').slice(1).join('=');
const r=await p.request.get('https://huecki.com/animation/v1/capabilities',{headers:{Authorization:`Bearer ${token}`}});assert.equal(r.status(),200);
const denied=await p.request.get('https://huecki.com/animation/v1/jobs');assert.equal(denied.status(),401);
await p.screenshot({path:'/root/services/animation-pipeline/artifacts/public-ui.png'});console.log(JSON.stringify({publicUI:true,frameBefore:a,frameAfter:b,errors,authenticatedCapabilities:r.status(),unauthorizedJobs:denied.status()}));
}finally{await browser.close();}
