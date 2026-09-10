import type { Runtime, Cell } from '../../src/index';
import type { Progress, World } from './scene';

/** Host-owned light and particle layer. Physical geometry stays in scene.ts. */
export class Atmosphere {
  private ctx:CanvasRenderingContext2D;
  time=0;
  private world:World;
  private progress:Progress;
  private width=0;
  private height=0;
  constructor(private canvas:HTMLCanvasElement,private runtime:Runtime,world:World,progress:Progress){this.ctx=canvas.getContext('2d')!;this.world=world;this.progress=progress;}
  setWorld(world:World,progress:Progress){this.world=world;this.progress=progress;this.time=0;this.draw();}
  setProgress(progress:Progress){this.progress=progress;}
  step(dt:number){this.time+=dt;this.draw();}
  private point(cell:Cell){return this.runtime.cellToScreen(cell);}
  private glow(x:number,y:number,r:number,color:string,alpha:number){
    const ctx=this.ctx,g=ctx.createRadialGradient(x,y,0,x,y,r);g.addColorStop(0,`rgba(${color},${alpha})`);g.addColorStop(.35,`rgba(${color},${alpha*.35})`);g.addColorStop(1,`rgba(${color},0)`);ctx.fillStyle=g;ctx.fillRect(x-r,y-r,r*2,r*2);
  }
  draw(){
    const canvas=this.canvas,ctx=this.ctx,rect=canvas.getBoundingClientRect(),dpr=Math.min(devicePixelRatio,2);
    if(this.width!==rect.width||this.height!==rect.height){this.width=rect.width;this.height=rect.height;canvas.width=Math.round(rect.width*dpr);canvas.height=Math.round(rect.height*dpr);}
    ctx.setTransform(dpr,0,0,dpr,0,0);ctx.clearRect(0,0,this.width,this.height);
    const z=this.runtime.getCamera().zoom,t=this.time,forest=this.world.region==='forest';
    // Water and crossing art are depth-sorted runtime sprites/terrain.
    ctx.globalCompositeOperation='screen';
    for(const cell of this.world.lamps){const p=this.point(cell);this.glow(p.x,p.y-48*z,67*z,'249,183,105',.23+Math.sin(t*2.7+cell.c)*.016);this.glow(p.x,p.y,75*z,'234,167,91',.09);}
    for(const smoke of this.world.smoke){
      const p=this.point(smoke.cell);
      for(let i=0;i<5;i++){const q=(t*.12+i*.2+smoke.cell.c*.023)%1,x=p.x+(smoke.x+Math.sin(q*5+t*.3)*q*17)*z,y=p.y+(smoke.y-q*73)*z;
        this.glow(x,y,(8+q*17)*z,'171,166,197',Math.sin(q*Math.PI)*.085);
      }
      this.glow(p.x,p.y-70*z,77*z,'243,152,98',.07);
    }
    if(this.world.spring){
      const p=this.point(this.world.spring),awakened=this.progress!=='seeking';
      this.glow(p.x,p.y-9*z,155*z,'75,226,206',awakened?.38:.23);
      ctx.save();ctx.translate(p.x,p.y);ctx.scale(z,z*.48);
      const g=ctx.createRadialGradient(0,0,2,0,0,61);g.addColorStop(0,'#aaffd6');g.addColorStop(.25,'#58bcbd');g.addColorStop(.75,'#286b80');g.addColorStop(1,'rgba(33,80,92,0)');ctx.fillStyle=g;ctx.beginPath();ctx.ellipse(0,0,64,64,0,0,Math.PI*2);ctx.fill();
      for(let i=0;i<4;i++){const q=(t*.19+i*.25)%1;ctx.strokeStyle=`rgba(163,255,226,${(1-q)*.6})`;ctx.lineWidth=1.7;ctx.beginPath();ctx.arc(0,0,8+q*51,0,Math.PI*2);ctx.stroke();}
      ctx.restore();
      for(let i=0;i<7;i++){const a=i*.91+t*.14;const x=p.x+Math.cos(a)*45*z,y=p.y+Math.sin(a)*20*z-(7+Math.sin(t+i)*4)*z;this.glow(x,y,8*z,'134,255,215',.45);}
    }
    if(this.progress==='planted'&&!forest){const p=this.point({c:8,r:6});this.glow(p.x,p.y-27*z,100*z,'144,255,199',.32);}
    // Small independent insects, not a replacement for the flowing water above.
    for(let i=0;i<(forest?42:17);i++){
      const c=2+(i*7%19)+Math.sin(t*.23+i)*.38,r=2+(i*11%19)+Math.cos(t*.19+i*2)*.5;
      const p=this.point({c,r}),a=Math.max(0,Math.sin(t*.8+i*1.73));
      const y=p.y-(14+Math.sin(t*.9+i)*7)*z;
      this.glow(p.x,y,8*z,forest?'135,250,220':'252,209,142',a*.23);
      ctx.fillStyle=`rgba(${forest?'171,255,218':'255,224,160'},${a*.75})`;ctx.fillRect(p.x,y,1.7*z,1.7*z);
    }
    ctx.globalCompositeOperation='source-over';
    // Pendulums pivot at fixed branch attachments; trunks never translate.
    for(const bell of this.world.bells){const p=this.point(bell.cell),swing=Math.sin(t*1.85+bell.x)*.11*(.55+.45*Math.sin(t*.2)**2);
      ctx.save();ctx.translate(p.x+bell.x*z,p.y+bell.y*z);ctx.rotate(swing);ctx.scale(z,z);ctx.strokeStyle='#9c9c82';ctx.lineWidth=1;ctx.beginPath();ctx.moveTo(0,0);ctx.lineTo(0,19);ctx.stroke();ctx.fillStyle='#bda46c';ctx.beginPath();ctx.moveTo(-3,19);ctx.lineTo(-5,26);ctx.lineTo(5,26);ctx.lineTo(3,19);ctx.closePath();ctx.fill();ctx.fillStyle='#e8cd8c';ctx.fillRect(-6,25,12,2);ctx.fillRect(-1,27,2,2);ctx.restore();
    }
    // Detached falling leaves curve downwind, with resting roots underneath.
    for(let i=0;i<12;i++){const q=(t*.055+i/12)%1,cell={c:2+i*5%19,r:1+i*7%19},p=this.point(cell);ctx.save();ctx.translate(p.x+(q*43+Math.sin(q*10)*9)*z,p.y+(-95+q*112)*z);ctx.rotate(q*8+i);ctx.fillStyle=`rgba(123,166,143,${Math.sin(q*Math.PI)*.45})`;ctx.fillRect(-2*z,-z,5*z,2*z);ctx.restore();}
    const hero=this.runtime.getEntityPose('traveler');if(hero){const cam=this.runtime.getCamera(),p={x:(hero.position.c+hero.position.r)*32*z+cam.x,y:(hero.position.r-hero.position.c)*16*z+cam.y-hero.elevation*z};ctx.strokeStyle='rgba(218,230,192,.55)';ctx.lineWidth=1;ctx.beginPath();ctx.ellipse(p.x,p.y,13*z,6*z,0,0,Math.PI*2);ctx.stroke();}
  }
}

