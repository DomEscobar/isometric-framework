// Deterministic assembly of generated orthographic materials into shared geometry.
import { chromium } from 'playwright';
import { readFile, writeFile } from 'node:fs/promises';
const masks=Object.keys(JSON.parse(await readFile(new URL('../../willow-quay/art/ground-tiles.json',import.meta.url),'utf8')).variants).map(Number);
const source=await readFile(new URL('forest-materials.png',import.meta.url));
const browser=await chromium.launch({channel:'chrome'});
try{
  const page=await browser.newPage();
  const result=await page.evaluate(async({data,masks})=>{
    const img=new Image();img.src=data;await img.decode();
    const material=(x)=>{const canvas=document.createElement('canvas');canvas.width=canvas.height=128;const ctx=canvas.getContext('2d');ctx.imageSmoothingQuality='high';ctx.drawImage(img,x,24,580,1180,0,0,128,128);return ctx.getImageData(0,0,128,128).data;};
    const moss=material(20),soil=material(652),entries=[];
    for(const mask of [-1,...masks])for(let c=0;c<4;c++)for(let r=0;r<4;r++)entries.push({mask,c,r});
    const atlas=document.createElement('canvas');atlas.width=1024;atlas.height=Math.ceil(entries.length/16)*32;const ctx=atlas.getContext('2d'),textures={};
    const smooth=x=>Math.min(1,Math.max(0,x));
    for(const [index,{mask,c,r}] of entries.entries()){
      const pixels=ctx.createImageData(64,32);
      for(let y=0;y<32;y++)for(let x=0;x<64;x++){
        const u=(x+.5)/2-(y+.5)+16,v=(x+.5)/2+(y+.5)-16,U=c*32+u,V=r*32+v;
        let distance=100;
        if(!(mask&1))distance=Math.min(distance,u-5);if(!(mask&2))distance=Math.min(distance,27-u);if(!(mask&4))distance=Math.min(distance,v-5);if(!(mask&8))distance=Math.min(distance,27-v);
        for(const [a,b,bit,card] of [[0,0,16,5],[32,0,32,6],[0,32,64,9],[32,32,128,10]])if((mask&card)===card&&!(mask&bit))distance=Math.min(distance,Math.hypot(u-a,v-b)-8);
        const wiggle=Math.sin(U*.5+Math.sin(V*.3))*1.15+Math.sin(V*.71+U*.13)*.7;
        const w=mask===-1?0:smooth((distance+wiggle)/3),src=(((Math.floor(V)%128+128)%128)*128+(Math.floor(U)%128+128)%128)*4,dest=(y*64+x)*4;
        for(let k=0;k<3;k++){const a=moss[src+k]*1.28+[8,12,13][k],b=soil[src+k]*1.35+[17,20,24][k];pixels.data[dest+k]=Math.min(255,a*(1-w)+b*w);}pixels.data[dest+3]=255;
      }
      const x=(index%16)*64,y=Math.floor(index/16)*32;ctx.putImageData(pixels,x,y);textures[`forest-${mask===-1?'grass':`path-${mask}`}-${c}-${r}`]={image:'forest-terrain',frame:{x,y,width:64,height:32},anchor:{x:.5,y:.5}};
    }
    return{png:atlas.toDataURL().split(',')[1],textures};
  },{data:`data:image/png;base64,${source.toString('base64')}`,masks});
  await writeFile(new URL('forest-atlas.png',import.meta.url),Buffer.from(result.png,'base64'));
  await writeFile(new URL('forest-frames.json',import.meta.url),JSON.stringify(result.textures));
  console.log(`Prepared ${Object.keys(result.textures).length} terrain frames with shared contacts.`);
}finally{await browser.close();}
