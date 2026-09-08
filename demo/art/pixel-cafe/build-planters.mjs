/** Original code-authored stone/soil geometry. Does not process any source artwork.
 * 16 adjacency variants, two source pixels per world pixel; regenerate with Node.
 */
import { writeFileSync } from 'node:fs';
import { deflateSync } from 'node:zlib';
const S=2, W=160, H=128, atlasW=W*4, atlasH=H*4;
const pixels=Buffer.alloc(atlasW*atlasH*4);
const noise=(x,y)=>{let n=Math.imul(x+17,374761393)^Math.imul(y+41,668265263);n=Math.imul(n^(n>>>13),1274126177);return (n^(n>>>16))>>>0;};
const color=(hex,variation=0)=>[parseInt(hex.slice(0,2),16)+variation,parseInt(hex.slice(2,4),16)+variation,parseInt(hex.slice(4,6),16)+variation,255];
const within=(v)=>v>=-.5&&v<=.5;
for(let mask=0;mask<16;mask++)for(let py=0;py<H;py++)for(let px=0;px<W;px++){
  const x=(px+.5)/S-40,y=(py+.5)/S;
  const c=x/80-(y-34)/40,r=x/80+(y-34)/40;
  let rgba;
  const n=noise(px,py),grain=(n%7)-3;
  if(within(c)&&within(r)){
    const cap=(!(mask&1)&&c<-.42)||(!(mask&2)&&c>.42)||(!(mask&4)&&r<-.42)||(!(mask&8)&&r>.42);
    if(cap){
      rgba=color('d8bb86',grain);
      const along=(Math.abs(c)>.42?r:c)+.5;
      if((along*4)%1<.025)rgba=color('a48761',grain);
      if(Math.min(.5-Math.abs(c),.5-Math.abs(r))<.012)rgba=color('f0d3a1',grain);
    }else{
      rgba=color('514728',grain);
      if(n%17===0)rgba=color('78623b');
      if(n%29===0)rgba=color('354523');
    }
  }else{
    // Front-left and front-right vertical faces, ten world pixels high.
    const left=x<=0&&x>=-40, right=x>=0&&x<=40;
    const surface=left?54+x/2:54-x/2;
    const edgeOpen=left?!(mask&1):!(mask&8);
    if((left||right)&&edgeOpen&&y>=surface&&y<surface+10){
      const along=left?(x+40)/40:x/40,depth=y-surface;
      rgba=color(left?'b99869':'95734f',grain);
      if(depth<.8)rgba=color('e2c48e',grain);
      if(depth>9.1)rgba=color('765b3e',grain);
      if((along*4+(depth>5?.5:0))%1<.025||Math.abs(depth-5)<.25)rgba=color('806444',grain);
    }
  }
  if(rgba){const ax=(mask%4)*W+px,ay=Math.floor(mask/4)*H+py,at=(ay*atlasW+ax)*4;rgba.forEach((v,i)=>pixels[at+i]=Math.max(0,Math.min(255,v)));}
}
function crc32(bytes){let v=0xffffffff;for(const b of bytes){v^=b;for(let i=0;i<8;i++)v=(v>>>1)^((v&1)?0xedb88320:0);}return(v^0xffffffff)>>>0;}
function chunk(type,data){const b=Buffer.alloc(data.length+12);b.writeUInt32BE(data.length);b.write(type,4);data.copy(b,8);b.writeUInt32BE(crc32(b.subarray(4,-4)),b.length-4);return b;}
const ihdr=Buffer.alloc(13);ihdr.writeUInt32BE(atlasW);ihdr.writeUInt32BE(atlasH,4);ihdr[8]=8;ihdr[9]=6;
const scanlines=Buffer.alloc(atlasH*(atlasW*4+1));for(let y=0;y<atlasH;y++)pixels.copy(scanlines,y*(atlasW*4+1)+1,y*atlasW*4,(y+1)*atlasW*4);
writeFileSync(new URL('./planter-bases.png',import.meta.url),Buffer.concat([Buffer.from([137,80,78,71,13,10,26,10]),chunk('IHDR',ihdr),chunk('IDAT',deflateSync(scanlines)),chunk('IEND',Buffer.alloc(0))]));
console.log('Authored planter-bases.png: 16 exact 80×40 footprints, 10px height.');
