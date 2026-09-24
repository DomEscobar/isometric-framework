// Mock receipt fixture only. Real HTTP/UI/download; never starts provider work.
import fs from 'node:fs';import path from 'node:path';import assert from 'node:assert/strict';import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),base=process.env.BASE_URL,out=path.resolve(process.env.EVIDENCE),rid=process.env.RUN_ID;
const links='/root/.cache/ms-playwright/.links',candidates=fs.readdirSync(links).map(f=>fs.readFileSync(path.join(links,f),'utf8')).filter(p=>fs.existsSync(p+'/package.json'));const {chromium}=require(process.env.PLAYWRIGHT_CORE||candidates[0]);
fs.mkdirSync(out,{recursive:true});const browser=await chromium.launch({executablePath:process.env.CHROMIUM||'/root/.cache/ms-playwright/chromium_headless_shell-1234/chrome-linux/headless_shell',headless:true,args:['--no-sandbox']});
try{
 const page=await browser.newPage({viewport:{width:1280,height:1000},acceptDownloads:true});const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto(base);await page.selectOption('#runs',rid);await page.click('#load');await page.waitForFunction(()=>document.querySelector('#status').textContent.includes('succeeded'));
 await page.waitForFunction(()=>document.querySelector('#sample').naturalWidth>0);await page.locator('#sample').screenshot({path:path.join(out,'sample-native.png')});
 const [download]=await Promise.all([page.waitForEvent('download'),page.locator('#downloads a').filter({hasText:'Produktions-ZIP'}).click()]);await download.saveAs(path.join(out,'browser-production.zip'));
 await page.screenshot({path:path.join(out,'mock-production-ui.png'),fullPage:true});await page.reload();await page.waitForFunction(()=>document.querySelector('#status').textContent.includes('succeeded'));
 assert.deepEqual(errors,[]);fs.writeFileSync(path.join(out,'browser-proof.json'),JSON.stringify({mock_receipts:true,no_provider_calls:true,real_browser_download:true,errors,rid},null,2));
}finally{await browser.close()}
