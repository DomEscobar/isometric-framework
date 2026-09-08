#!/usr/bin/env node
import { readFile, writeFile } from 'node:fs/promises';
import { resolve } from 'node:path';
import { pathToFileURL } from 'node:url';
import { checkFile } from './check-art.mjs';

/** Inspection board only: no runtime state or image mutation. */
export async function createPreview(contractPath, outputPath) {
  const report = await checkFile(resolve(contractPath));
  const candidates = [];
  const images = {}, imageKeys = new Map();
  for (const asset of report.assets) {
    if (!imageKeys.has(asset.imagePath)) {
      const key = `image-${imageKeys.size}`;
      imageKeys.set(asset.imagePath, key);
      images[key] = `data:image/png;base64,${(await readFile(asset.imagePath)).toString('base64')}`;
    }
    candidates.push({ ...asset, imageKey: imageKeys.get(asset.imagePath) });
  }
  const payload = JSON.stringify({
    projection: report.contract?.projection,
    heightReferences: report.contract?.heightReferences,
    assets: candidates, images, errors: report.errors, passed: report.passed,
  }).replaceAll('<', '\\u003c');
  const html = `<!doctype html>
<html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Isometric art calibration</title>
<style>
body{margin:24px;font:16px system-ui;background:#f1f0e8;color:#20332a}h1{font-size:26px}
header{max-width:1000px}label{display:inline-block;margin:8px 20px 8px 0}select{font:inherit}
#status{font-weight:700}#errors{white-space:pre-wrap;color:#922f22}#board{display:flex;flex-wrap:wrap;gap:20px}
article{background:#fff;padding:16px;max-width:100%;overflow:auto}h2{font-size:18px;margin:0 0 6px}
canvas{display:block;background:repeating-conic-gradient(#f1f1ed 0 25%,#e6e8e2 0 50%) 0/20px 20px}
.note{font-size:13px;max-width:600px}.decode{color:#922f22}
</style>
<header><h1>Isometric art calibration</h1>
<p id="status"></p><p>This board checks supplied measurements against a common scale. It does not certify art quality, seams, occlusion, or gameplay. Verify landmarks against the pixels, then use the host's playable calibration scene.</p>
<label>Shared zoom <select id="zoom"><option value="0.5">0.5×</option><option value="1">1×</option><option value="2" selected>2×</option><option value="3">3×</option><option value="4">4×</option></select></label>
<label><input id="overlay" type="checkbox" checked> Ground and height overlays</label>
<p class="note">Cyan: expected ground contacts / footprint. Magenta: measured contacts. Gold: measured base outline and heights. Blue: reference heights. All cards share one scale and baseline. If art clips, lower the shared zoom; no card auto-fits.</p>
<pre id="errors"></pre></header><main id="board"></main>
<script type="application/json" id="data">${payload}</script>
<script>
const data=JSON.parse(document.getElementById('data').textContent);
document.getElementById('status').textContent=data.passed?'Metadata checks passed — visual compatibility UNVERIFIED':'Metadata checks FAILED — do not accept this pack';
document.getElementById('errors').textContent=data.errors.map(e=>(e.assetId||'contract')+': '+e.message).join(String.fromCharCode(10));
const cards=[];
const project=(p)=>({x:(p.c+p.r)*data.projection.tileWidth/2,y:(p.r-p.c)*data.projection.tileHeight/2});
function paint(card){
 const {asset:a,ctx,image,note}=card, zoom=Number(document.getElementById('zoom').value), overlays=document.getElementById('overlay').checked;
 ctx.clearRect(0,0,640,520);ctx.save();ctx.translate(320,420);ctx.scale(zoom,zoom);ctx.imageSmoothingEnabled=false;
 const f=a.frame, off=a.render.offset||{x:0,y:0}, actual=p=>({x:(p.x-a.anchor.x*f.width)*a.scaleX+off.x,y:(p.y-a.anchor.y*f.height)*a.scaleY+off.y});
 const left=-a.anchor.x*f.width*a.scaleX+off.x,top=-a.anchor.y*f.height*a.scaleY+off.y;
 const right=left+f.width*a.scaleX,bottom=top+f.height*a.scaleY;
 ctx.drawImage(image,f.x,f.y,f.width,f.height,left,top,f.width*a.scaleX,f.height*a.scaleY);
 note.textContent=(320+left*zoom<0||320+right*zoom>640||420+top*zoom<0||420+bottom*zoom>520)?'Preview clipped at this shared zoom; lower zoom before reviewing.':'Full frame visible at shared zoom. Verify source landmarks manually.';
 function line(points,color,closed=false){ctx.strokeStyle=color;ctx.lineWidth=1.5/zoom;ctx.beginPath();points.forEach((p,i)=>i?ctx.lineTo(p.x,p.y):ctx.moveTo(p.x,p.y));if(closed)ctx.closePath();ctx.stroke();}
 function dot(p,color){ctx.fillStyle=color;ctx.beginPath();ctx.arc(p.x,p.y,3/zoom,0,Math.PI*2);ctx.fill();}
 if(overlays){
  const C=a.footprint.columns,R=a.footprint.rows;
  line([{c:-.5,r:-.5},{c:C-.5,r:-.5},{c:C-.5,r:R-.5},{c:-.5,r:R-.5}].map(project),'#008f99',true);
  if(a.groundPoints.length>1)line(a.groundPoints.map(p=>actual(p.source)),'#b87b00',true);
  for(const p of a.groundPoints){const source=actual(p.source),expected=project(p.grid);line([source,expected],'#d62a83');dot(expected,'#008f99');dot(source,'#d62a83');}
  for(const h of a.heights){const base=actual(h.base),top=actual(h.top),reference={x:base.x,y:base.y-data.heightReferences[h.reference]*data.projection.heightPixelsPerUnit};line([base,top],'#b87b00');line([{x:base.x+6/zoom,y:base.y},{x:reference.x+6/zoom,y:reference.y}],'#2459c4');dot(top,'#b87b00');dot(reference,'#2459c4');}
 }
 ctx.restore();
}
for(const asset of data.assets){
 const article=document.createElement('article'),title=document.createElement('h2'),caption=document.createElement('p'),canvas=document.createElement('canvas'),note=document.createElement('p'),decode=document.createElement('p');
 title.textContent=asset.id+' · '+asset.kind;caption.className=note.className='note';
 caption.textContent='Footprint '+asset.footprint.columns+'×'+asset.footprint.rows+'; overhang: '+(asset.allowedOverhang||'none declared');
 canvas.width=640;canvas.height=520;decode.className='decode';article.append(title,caption,canvas,note,decode);document.getElementById('board').append(article);
 const image=new Image(),card={asset,ctx:canvas.getContext('2d'),image,note};
 image.onload=()=>{if(image.naturalWidth!==asset.imageWidth||image.naturalHeight!==asset.imageHeight){decode.textContent='Decoded dimensions disagree with checked PNG metadata.';return;}cards.push(card);paint(card);};
 image.onerror=()=>{decode.textContent='Image decoding FAILED — do not accept this asset.';};image.src=data.images[asset.imageKey];
}
for(const id of ['zoom','overlay'])document.getElementById(id).addEventListener('change',()=>cards.forEach(paint));
</script></html>`;
  await writeFile(resolve(outputPath), html, 'utf8');
  return report;
}

if (process.argv[1] && import.meta.url === pathToFileURL(resolve(process.argv[1])).href) {
  if (process.argv.length !== 4) {
    console.error('Usage: node preview-art.mjs contract.json output.html');
    process.exitCode = 1;
  } else {
    try {
      const report = await createPreview(process.argv[2], process.argv[3]);
      console.log(JSON.stringify({ output: resolve(process.argv[3]), candidates: report.assets.length, metadataPassed: report.passed, visualCompatibility: 'unverified' }));
      if (!report.passed) process.exitCode = 1;
    } catch (error) { console.error(error.message); process.exitCode = 1; }
  }
}
