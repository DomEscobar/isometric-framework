import {loadImage} from './asset-loader.ts';
import slices from './terrain-trial/slices.json';
import {project,riverCenter,riverHalf} from './world.ts';

const urls=import.meta.glob('./terrain-trial/slices/*.png',{eager:true,query:'?url',import:'default'}) as Record<string,string>;

/** Registered image slices provide all visible material; existing geometry clips support. */
export async function createGeneratedGround(supportAlpha:HTMLCanvasElement){
 const plate=document.createElement('canvas');plate.width=1536;plate.height=1060;
 const pc=plate.getContext('2d')!;pc.imageSmoothingEnabled=false;
 const loaded=await Promise.all(Object.entries(slices.images).map(async([id,entry])=>[id,await loadImage(urls['./terrain-trial/'+entry.url]!)] as const));
 const images=Object.fromEntries(loaded);
 for(const [id,placement]of Object.entries(slices.placements))pc.drawImage(images[id]!,placement.x-1,placement.y-1);
 const land=document.createElement('canvas');land.width=plate.width;land.height=plate.height;
 const lc=land.getContext('2d')!;lc.drawImage(plate,0,0);lc.globalCompositeOperation='destination-in';lc.drawImage(supportAlpha,0,0);lc.globalCompositeOperation='source-over';

 // Unwrap generated channel pixels along the same physical river curve. No painted water fallback.
 const raw=pc.getImageData(0,0,plate.width,plate.height),stripWidth=768,stripHeight=64,overlap=64,periodPixels=stripWidth-overlap;
 const strip=new Uint8ClampedArray(stripWidth*stripHeight*4);
 for(let x=0;x<stripWidth;x++)for(let y=0;y<stripHeight;y++){
  const c=(x+.5)/16,r=riverCenter(c)+(y/(stripHeight-1)*2-1)*riverHalf*.72,p=project({c,r});
  const src=(Math.round(p.y+140)*plate.width+Math.round(p.x))*4,dst=(y*stripWidth+x)*4;
  strip.set(raw.data.subarray(src,src+4),dst);
 }
 const texture=document.createElement('canvas');texture.width=periodPixels*2;texture.height=stripHeight;
 const tc=texture.getContext('2d')!,loop=tc.createImageData(periodPixels,stripHeight);
 for(let x=0;x<periodPixels;x++)for(let y=0;y<stripHeight;y++)for(let k=0;k<4;k++){
  const a=strip[(y*stripWidth+x)*4+k]!,b=x<overlap?strip[(y*stripWidth+x+periodPixels)*4+k]!:a,t=x<overlap?x/overlap:1;
  loop.data[(y*periodPixels+x)*4+k]=a*t+b*(1-t);
 }
 tc.putImageData(loop,0,0);tc.drawImage(texture,0,0,periodPixels,stripHeight,periodPixels,0,periodPixels,stripHeight);
 function water(ctx:CanvasRenderingContext2D,time:number){const offset=(time*32)%periodPixels;
  for(let c=0;c<48;c+=.5){const p=project({c,r:riverCenter(c)-riverHalf},-5),q=project({c:c+.5,r:riverCenter(c+.5)-riverHalf},-5),v=project({c,r:riverCenter(c)+riverHalf},-5),sx=((c*16-offset)%periodPixels+periodPixels)%periodPixels;
   ctx.save();ctx.transform((q.x-p.x)/8,(q.y-p.y)/8,(v.x-p.x)/stripHeight,(v.y-p.y)/stripHeight,p.x,p.y);ctx.drawImage(texture,sx,0,8.1,stripHeight,0,0,8.1,stripHeight);ctx.restore();
  }
 }
 return{land,plate,water,texture,period:periodPixels/32,sliceCount:loaded.length};
}
