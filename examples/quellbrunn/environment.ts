import {project,riverCenter,riverHalf,houses} from './world.ts';
import binding from './art/binding.json';
const noise=(x:number,y:number)=>{let n=Math.imul(x,374761393)^Math.imul(y,668265263);n=Math.imul(n^(n>>>13),1274126177);return((n^(n>>>16))>>>0)/4294967295};
export function createEnvironment(){
 const texture=document.createElement('canvas');texture.width=512;texture.height=64;const tc=texture.getContext('2d')!,data=tc.createImageData(256,64);
 for(let y=0;y<64;y++)for(let x=0;x<256;x++){
  const wave=Math.sin(x*Math.PI/32+Math.sin(y*.13)*2)+.45*Math.sin(x*Math.PI/8-y*.19),n=noise(x>>1,y>>1),i=(y*256+x)*4;
  const colors=wave>1.08?[100,190,196]:wave>.45?[63,157,178]:wave>-.5?[40,129,157]:[30,107,142];
  data.data[i]=colors[0]!+n*8;data.data[i+1]=colors[1]!+n*8;data.data[i+2]=colors[2]!+n*7;data.data[i+3]=255;
 }
 tc.putImageData(data,0,0);tc.strokeStyle='#a9e0d9';tc.lineWidth=1;
 for(let i=0;i<48;i++){const x=Math.floor(noise(i,1)*250),y=Math.floor(noise(i,2)*60)+2;tc.beginPath();tc.moveTo(x,y);tc.lineTo(x+3,y);tc.lineTo(x+5,y+1);tc.lineTo(x+10,y+1);tc.stroke();}
 tc.drawImage(texture,0,0,256,64,256,0,256,64);
 function water(ctx:CanvasRenderingContext2D,time:number){
  const offset=(time*32)%256;
  for(let c=0;c<48;c+=.5){const p=project({c,r:riverCenter(c)-riverHalf},-5),q=project({c:c+.5,r:riverCenter(c+.5)-riverHalf},-5),v=project({c,r:riverCenter(c)+riverHalf},-5),sx=((c*16-offset)%256+256)%256;
   ctx.save();ctx.transform((q.x-p.x)/8,(q.y-p.y)/8,(v.x-p.x)/64,(v.y-p.y)/64,p.x,p.y);ctx.drawImage(texture,sx,0,8.1,64,0,0,8.1,64);ctx.restore();
  }
 }
 function wheel(ctx:CanvasRenderingContext2D,time:number){
  const p=project({c:37,r:riverCenter(37)}),x=p.x,y=p.y-17;ctx.save();ctx.translate(x,y);ctx.fillStyle='#483e30';ctx.fillRect(-4,-4,8,32);ctx.strokeStyle='#523f2c';ctx.lineWidth=7;ctx.beginPath();ctx.ellipse(0,0,21,27,-.18,0,Math.PI*2);ctx.stroke();ctx.strokeStyle='#c59b61';ctx.lineWidth=3;ctx.beginPath();ctx.ellipse(-2,-2,21,27,-.18,0,Math.PI*2);ctx.stroke();
  for(let i=0;i<10;i++){const angle=time*Math.PI/4+i*Math.PI/5,a={x:Math.cos(angle)*19,y:Math.sin(angle)*25};ctx.strokeStyle='#8d683e';ctx.lineWidth=3;ctx.beginPath();ctx.moveTo(0,0);ctx.lineTo(a.x,a.y);ctx.stroke();ctx.fillStyle='#c9a370';ctx.fillRect(Math.round(a.x)-4,Math.round(a.y)-2,8,4);ctx.fillStyle='#57442e';ctx.fillRect(Math.round(a.x)-4,Math.round(a.y)+2,8,2);}ctx.fillStyle='#b1aaa0';ctx.fillRect(-3,-3,6,6);ctx.fillStyle='#f0d698';ctx.fillRect(-2,-2,2,2);ctx.restore();
  for(let i=0;i<7;i++){const phase=(time*1.8+i/7)%1;ctx.globalAlpha=(1-phase)*.7;ctx.fillStyle='#c0e6dd';ctx.fillRect(x-15+i*5+phase*3,y+24-Math.sin(phase*Math.PI)*7,2,2)}ctx.globalAlpha=1;
 }
 function smoke(ctx:CanvasRenderingContext2D,time:number){const b=binding.assets.cottage,s=b.render.width/b.frame.width;
  houses.forEach((h,index)=>{const p=project({c:h.c+.5,r:h.r+.5}),x=p.x+b.render.offset.x+(331-b.anchor.x*b.frame.width)*s,y=p.y+b.render.offset.y+(14-b.anchor.y*b.frame.height)*s;
   for(let i=0;i<3;i++){const phase=(time/6+i/3+index*.17)%1;ctx.globalAlpha=Math.sin(phase*Math.PI)*.5;ctx.fillStyle='#e9e6cd';ctx.beginPath();ctx.ellipse(x+Math.sin(phase*5+index)*5+phase*8,y-phase*48,4+phase*7,4+phase*5,0,0,Math.PI*2);ctx.fill();}ctx.globalAlpha=1;
  });
 }
 return{water,wheel,smoke,period:8};
}
