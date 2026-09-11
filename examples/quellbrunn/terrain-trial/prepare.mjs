import {chromium} from 'playwright';
import {mkdir,readFile,writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
const base='examples/quellbrunn/terrain-trial',analysis=JSON.parse(await readFile(base+'/registration.json','utf8'));
await mkdir(base+'/slices',{recursive:true});
const browser=await chromium.launch();
try{const page=await browser.newPage();await page.goto('http://127.0.0.1:4202/');await page.waitForFunction(()=>window.quellbrunn?.ready);
const result=await page.evaluate(async analysis=>{
 const {project,unproject,riverCenter,riverHalf,WIDTH,HEIGHT}=await import('/world.ts');
 const source=new Image();source.src='/terrain-trial/source-v1.png';await source.decode();
 const input=document.createElement('canvas');input.width=source.width;input.height=source.height;input.getContext('2d').drawImage(source,0,0);const rgba=input.getContext('2d').getImageData(0,0,input.width,input.height).data;
 const out=document.createElement('canvas');out.width=1536;out.height=1024;const oc=out.getContext('2d'),pixels=oc.createImageData(out.width,out.height),matrix=analysis.original_to_generated_affine_3x3;
 const rows=analysis.source_banks_in_authoritative_world_r.samples.filter(p=>p.valid&&p.source_north_bank_r!==null&&p.source_south_bank_r!==null);
 function banks(c){let i=0;while(i<rows.length-2&&rows[i+1].c<c)i++;const a=rows[i],b=rows[i+1],t=Math.max(0,Math.min(1,(c-a.c)/(b.c-a.c)));return[a.source_north_bank_r*(1-t)+b.source_north_bank_r*t,a.source_south_bank_r*(1-t)+b.source_south_bank_r*t];}
 let waterOnLand=0,landPixels=0,waterPixels=0,nonWaterInside=0,farContamination=0,maxLandBlueDistance=0;
 for(let y=0;y<out.height;y++)for(let x=0;x<out.width;x++){
  const p=unproject({x:x+.5,y:y+.5-140}),i=(y*out.width+x)*4;
  if(p.c<0||p.c>WIDTH||p.r<0||p.r>HEIGHT){pixels.data.set([36,77,57,255],i);continue;}
  const north=riverCenter(p.c)-riverHalf,south=north+2*riverHalf,[sn,ss]=banks(p.c);
  const mappedR=p.r<north?p.r*sn/north:p.r>south?ss+(p.r-south)*(HEIGHT-ss)/(HEIGHT-south):sn+(p.r-north)/(south-north)*(ss-sn);
  const q=project({c:p.c,r:mappedR});q.y+=140;
  const sx=Math.max(0,Math.min(input.width-1,Math.round(matrix[0][0]*q.x+matrix[0][1]*q.y+matrix[0][2]))),sy=Math.max(0,Math.min(input.height-1,Math.round(matrix[1][0]*q.x+matrix[1][1]*q.y+matrix[1][2]))),si=(sy*input.width+sx)*4;
  pixels.data.set(rgba.subarray(si,si+4),i);
  const r=rgba[si],g=rgba[si+1],b=rgba[si+2],blue=b>r+35&&g>r+25&&b>g-30&&b>90,wet=p.r>north&&p.r<south;
  if(wet){waterPixels++;if(!blue)nonWaterInside++;}else{landPixels++;if(blue){waterOnLand++;const distance=Math.min(Math.abs(p.r-north),Math.abs(p.r-south));maxLandBlueDistance=Math.max(maxLandBlueDistance,distance);if(distance>.3)farContamination++;}}
 }
 oc.putImageData(pixels,0,0);const chunks=[];
 for(let row=0;row<4;row++)for(let col=0;col<6;col++){const c=document.createElement('canvas');c.width=258;c.height=258;const ctx=c.getContext('2d');ctx.drawImage(out,col*256,row*256,256,256,1,1,256,256);chunks.push({id:row*6+col,x:col*256,y:row*256,data:c.toDataURL().split(',')[1]});}
 return{sourceSize:[source.width,source.height],registered:out.toDataURL().split(',')[1],chunks,measurement:{waterOnLand,landPixels,waterPixels,nonWaterInside,farContamination,maxLandBlueDistance,maxLandBlueDistanceScreen: maxLandBlueDistance*Math.hypot(16,8),bankSamples:rows.length,method:'Inverse outer affine followed by continuous world-r material registration to both riverbanks; nearest pixel sampling, original geometry unchanged.'}};
},analysis);
await writeFile(base+'/registered-v1.png',Buffer.from(result.registered,'base64'));
const manifest={images:{},textures:{},placements:{}};
for(const chunk of result.chunks){const id='slice-'+chunk.id,file='slices/'+id+'.png';await writeFile(base+'/'+file,Buffer.from(chunk.data,'base64'));manifest.images[id]={url:file,sampling:'nearest'};manifest.textures[id]={image:id,frame:{x:0,y:0,width:258,height:258},anchor:{x:1/258,y:1/258}};manifest.placements[id]={x:chunk.x,y:chunk.y};}
await writeFile(base+'/slices.json',JSON.stringify(manifest,null,2));
await writeFile(base+'/registration.json',JSON.stringify(analysis,null,2));
const sha=async file=>createHash('sha256').update(await readFile(file)).digest('hex');
await writeFile(base+'/provenance.json',JSON.stringify({provider:'built-in ImageGen',prompt:'prompt.txt',source:'source-v1.png',sourceSha256:await sha(base+'/source-v1.png'),registered:'registered-v1.png',registeredSha256:await sha(base+'/registered-v1.png'),referenceRoles:{layout:'actual host ground-only native1536x1024',style:'original user forest image',context:'existing Quellbrunn village'},processing:result.measurement.method,slicing:'24 adjacent256x256 crops with1px transparent padding; runtime draws full258px images at shared origin minus1px, then original terrain alpha clips land support. Crops are positioned map patches, not a universal tileset.',water:'Unwrapped generated centre72percent of channel;64px head/tail crossfade creates704px periodic current. No procedural water pixels in generated mode.'},null,2));
await writeFile('test-results/quellbrunn/ground-trial/registration-after.json',JSON.stringify(result.measurement,null,2));console.log(JSON.stringify(result.measurement));
}finally{await browser.close()}
