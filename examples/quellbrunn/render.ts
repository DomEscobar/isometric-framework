import {loadImage} from './asset-loader.ts';
import manifest from './art/manifest.json';
import binding from './art/binding.json';
import {project,unproject,riverCenter,riverHalf,roadDistance,bridges,houses,trees,gardens,insideRect,WIDTH,HEIGHT,type Point,type Screen} from './world.ts';
export type Person=Point&{facing:number;walk:number;moving:boolean;color:number};
const urls=import.meta.glob('./art/*.png',{eager:true,query:'?url',import:'default'}) as Record<string,string>;
const hash=(x:number,y:number)=>{let n=Math.imul(Math.floor(x),374761393)^Math.imul(Math.floor(y),668265263);n=Math.imul(n^(n>>>13),1274126177);return((n^(n>>>16))>>>0)/4294967295};
const blend=(a:number[],b:number[],t:number)=>a.map((v,i)=>Math.round(v+(b[i]!-v)*t));
const color=(rgb:number[])=>`rgb(${rgb.join(',')})`;
export async function createView(canvas:HTMLCanvasElement){
 const sprites=Object.fromEntries(await Promise.all(Object.keys(manifest.images).map(async id=>[id,await loadImage(urls['./art/'+manifest.images[id as keyof typeof manifest.images].url]!)]))) as Record<string,HTMLImageElement>;
 const ctx=canvas.getContext('2d')!,terrain=document.createElement('canvas');terrain.width=1536;terrain.height=1060;const ground=terrain.getContext('2d')!;
 const image=ground.createImageData(768,530),pixels=image.data;
 for(let y=0;y<530;y++)for(let x=0;x<768;x++){
  const p=unproject({x:x*2,y:y*2-140}),i=(y*768+x)*4;if(p.c<0||p.c>WIDTH||p.r<0||p.r>HEIGHT)continue;
  const wet=Math.abs(p.r-riverCenter(p.c))-riverHalf;if(wet<0)continue;
  const n=hash(Math.floor(p.c*3),Math.floor(p.r*3)),broad=Math.sin(p.c*.35)*Math.cos(p.r*.25),rd=roadDistance(p)+(Math.sin(p.c*4.1+p.r*1.8)+Math.cos(p.r*5.4-p.c))*0.08;
  let rgb=blend([115,151,65],[139,171,78],.5+broad*.25+(n-.5)*.35);
  if(rd<.05){rgb=blend([185,148,91],[220,185,120],.3+n*.5+broad*.1);if(rd>-.28&&n>.52)rgb=blend(rgb,[118,152,65],.7);if(n<.04)rgb=[164,137,86];}
  else if(n<.055)rgb=blend(rgb,[76,119,58],.45);
  const lip=.32+(Math.sin(p.c*5.7)+Math.cos(p.c*2.8))*.07;
  if(wet<lip){rgb=wet<.09?[65,78,43]:blend([108,78,45],[157,118,62],n);if(n>.68&&wet>.15)rgb=[99,127,49];}
  else if(wet<lip+.24&&n<.6)rgb=blend([72,108,43],[149,177,77],n);
  if(gardens.some(g=>insideRect(p,g.c,g.r,g.w,g.h)))rgb=blend([95,68,44],[126,91,52],n*.75);
  pixels[i]=rgb[0]!;pixels[i+1]=rgb[1]!;pixels[i+2]=rgb[2]!;pixels[i+3]=255;
 }
 const low=document.createElement('canvas');low.width=768;low.height=530;low.getContext('2d')!.putImageData(image,0,0);ground.imageSmoothingEnabled=false;ground.drawImage(low,0,0,1536,1060);ground.translate(0,140);
 function poly(c:CanvasRenderingContext2D,points:Screen[],fill:string,stroke?:string){c.beginPath();points.forEach((p,i)=>i?c.lineTo(p.x,p.y):c.moveTo(p.x,p.y));c.closePath();c.fillStyle=fill;c.fill();if(stroke){c.strokeStyle=stroke;c.lineWidth=1;c.stroke();}}
 function line(c:CanvasRenderingContext2D,a:Screen,b:Screen,stroke:string,width=1){c.strokeStyle=stroke;c.lineWidth=width;c.beginPath();c.moveTo(a.x,a.y);c.lineTo(b.x,b.y);c.stroke()}
 // Vegetation and wear are sampled continuously in world space, never stamped per tile.
 for(let i=0;i<7800;i++){const p={c:hash(i,1)*WIDTH,r:hash(i,2)*HEIGHT};if(Math.abs(p.r-riverCenter(p.c))<riverHalf+.45||roadDistance(p)<.1||houses.some(h=>insideRect(p,h.c-.25,h.r-.25,5.5,5.5))||gardens.some(g=>insideRect(p,g.c,g.r,g.w,g.h)))continue;const q=project(p),n=hash(i,3);if(n<.7){ground.strokeStyle=n<.3?'#648844':'#a2b963';ground.lineWidth=1;ground.beginPath();ground.moveTo(q.x-2,q.y);ground.lineTo(q.x-3,q.y-3);ground.moveTo(q.x,q.y+1);ground.lineTo(q.x+1,q.y-4);ground.stroke();}else if(n>.96){ground.fillStyle='#e9d89a';ground.fillRect(q.x,q.y-3,2,2);ground.fillStyle='#638840';ground.fillRect(q.x,q.y,3,1);}}
 // Source sprite variations preserve exactly the calibrated footprint and alpha.
 const houseImages:HTMLCanvasElement[]=[];for(let tint=0;tint<5;tint++){const im=document.createElement('canvas');im.width=sprites.cottage!.width;im.height=sprites.cottage!.height;const c=im.getContext('2d')!;c.drawImage(sprites.cottage!,0,0);if(tint){const data=c.getImageData(0,0,im.width,im.height);const colors=[[1,1,1],[.45,.85,1.12],[.6,.77,.72],[1.15,1.05,.55],[.83,.63,1]];const shade=colors[tint]!;for(let y=0;y<im.height*.69;y++)for(let x=0;x<im.width;x++){const k=(y*im.width+x)*4,r=data.data[k]!,g=data.data[k+1]!,b=data.data[k+2]!;if(r>110&&r-g>24&&g>b*1.15){const l=r*.7+g*.3;data.data[k]=l*shade[0]!;data.data[k+1]=l*shade[1]!;data.data[k+2]=l*shade[2]!;}}c.putImageData(data,0,0);}houseImages.push(im);}
 let width=0,height=0,zoom=1,groundOnly=false,activeTerrain=terrain,camera={x:770,y:340};
 function resize(){width=innerWidth;height=innerHeight;const dpr=Math.min(devicePixelRatio,2);canvas.width=Math.round(width*dpr);canvas.height=Math.round(height*dpr);ctx.imageSmoothingEnabled=false;}
 function screen(p:Point){const q=project(p);return{x:(q.x-camera.x)*zoom+width/2,y:(q.y-camera.y)*zoom+height/2};}
 function world(p:Screen){return unproject({x:(p.x-width/2)/zoom+camera.x,y:(p.y-height/2)/zoom+camera.y});}
 function clamp(){camera.x=Math.max(100,Math.min(1450,camera.x));camera.y=Math.max(-30,Math.min(780,camera.y))}
 function overview(){zoom=Math.min(width/1510,height/970);camera={x:770,y:345};}
 function focus(p:Point,scale?:number){camera=project(p);if(scale)zoom=scale;clamp()}
 resize();overview();
 const bounds=binding.assets.cottage;const s=bounds.render.width/bounds.frame.width;
 function houseRect(h:typeof houses[number]){const p=project({c:h.c+.5,r:h.r+.5});return{x:p.x+bounds.render.offset.x-bounds.anchor.x*bounds.frame.width*s,y:p.y+bounds.render.offset.y-bounds.anchor.y*bounds.frame.height*s,width:bounds.render.width,height:bounds.frame.height*s};}
 function drawPerson(p:Person){const q=project(p),back=p.facing<2,right=true,mirror=p.facing===0||p.facing===2,t=p.moving?Math.sin(p.walk*Math.PI*2):0,bob=p.moving?Math.abs(t):0;ctx.save();ctx.translate(Math.round(q.x),Math.round(q.y));ctx.scale(mirror?1:-1,1);ctx.fillStyle='#293a3266';ctx.beginPath();ctx.ellipse(0,0,11,3,0,0,Math.PI*2);ctx.fill();const r=(c:string,x:number,y:number,w:number,h:number)=>{ctx.fillStyle=c;ctx.fillRect(Math.round(x),Math.round(y-bob),w,h)};
 for(const [x,shift]of[[-7,t*2],[1,-t*2]]){r('#303938',x!,-10,7,9);r('#6f7b7c',x!+1,-9,3,5);r('#403a30',x!-1,-3+shift!,9,3);r('#ae9162',x!,-3+shift!,5,1)}
 const coat=['#568cad','#b67759','#8ba75f','#a67eab'][p.color]!,dark=['#355c77','#784833','#546c38','#6e4e77'][p.color]!;
 r('#303f35',-10,-23,20,15);r(dark,-9,-22,18,12);r(coat,-8,-22,14,10);r('#bdcbae',-6,-22,4,2);r('#514732',-8,-11,16,3);r('#d5b86d',-1,-11,3,2);
 for(const [x,swing]of[[-13,t],[8,-t]]){r('#374237',x!,-21+swing!*2,5,10);r(coat,x!+1,-20+swing!*2,3,6);r('#e8bd86',x!+1,-14+swing!*2,4,4);r('#ae7953',x!+3,-12+swing!*2,2,2)}
 r('#594431',-9,-33,18,11);r('#e9b981',-8,-32,16,10);r('#f7d59b',-6,-32,12,8);r('#ce925e',right?7:-9,-29,3,5);r('#a9774f',-5,-24,10,2);r('#69492f',-9,-32,3,7);
 if(back){r('#69492f',-8,-31,15,7);r('#85633c',-6,-29,11,3);r('#e9b981',7,-29,3,5);r('#f7d59b',8,-28,2,2);}else{r('#3b3930',right?-1:-5,-28,2,3);r('#3b3930',right?5:1,-28,2,3);r('#fff0c3',right?-1:-5,-28,1,1);r('#fff0c3',right?5:1,-28,1,1);r('#cf925f',right?3:-2,-25,3,2);r('#82533b',0,-23,4,1);}
 r('#514330',-10,-34,20,3);r('#a97948',-8,-37,16,5);r('#d4a966',-6,-37,10,2);r('#e6c689',-7,-34,14,1);r('#634a32',-12,-32,25,2);r('#d9b776',-10,-32,20,1);
 if(back){r('#4b4330',-7,-22,14,13);r('#a77b46',-6,-21,12,11);r('#d4af6b',-5,-20,10,4);r('#745333',-4,-14,8,3);r('#e0c081',-1,-16,3,3);}ctx.restore();}
 function draw(time:number,people:Person[],debug=false,water?:(ctx:CanvasRenderingContext2D)=>void,target?:Point,decor?:{under:(ctx:CanvasRenderingContext2D)=>void;over:(ctx:CanvasRenderingContext2D)=>void}){
  const dpr=Math.min(devicePixelRatio,2);ctx.setTransform(dpr,0,0,dpr,0,0);ctx.fillStyle='#244d39';ctx.fillRect(0,0,width,height);ctx.translate(width/2-camera.x*zoom,height/2-camera.y*zoom);ctx.scale(zoom,zoom);ctx.imageSmoothingEnabled=false;
  const channel:Screen[]=[];for(let c=0;c<=48;c+=.5)channel.push(project({c,r:riverCenter(c)-riverHalf}));for(let c=48;c>=0;c-=.5)channel.push(project({c,r:riverCenter(c)+riverHalf}));poly(ctx,channel,'#264f54');water?.(ctx);ctx.drawImage(activeTerrain,0,-140);
  for(const b of bridges){const a=project({c:b.minC,r:b.minR}),d=project({c:b.maxC,r:b.maxR});poly(ctx,[a,project({c:b.maxC,r:b.minR}),d,project({c:b.minC,r:b.maxR})],'#c7a06b','#68513a');for(let r=b.minR;r<b.maxR;r+=.38){line(ctx,project({c:b.minC,r}),project({c:b.maxC,r}),'#80633f',1);line(ctx,project({c:b.minC+.12,r:r+.06}),project({c:b.maxC-.12,r:r+.06}),'#e1bb7c',1);}}
  for(const h of houses){const p=project({c:h.c+2.2,r:h.r+2.8});ctx.fillStyle='#324a3044';ctx.beginPath();ctx.ellipse(p.x+13,p.y+5,72,27,-.03,0,Math.PI*2);ctx.fill();const door=project(h.door);poly(ctx,[{x:door.x-11,y:door.y-3},{x:door.x+4,y:door.y-9},{x:door.x+15,y:door.y-2},{x:door.x,y:door.y+5}],'#b4b19a','#888a75');}
  if(groundOnly)return;
  decor?.under(ctx);
  const items:{depth:number;draw:()=>void}[]=[];
  const player=people[0]!,feet=project(player);
  for(const h of houses){const rect=houseRect(h);items.push({depth:project({c:h.c,r:h.r+5}).y,draw:()=>{ctx.save();if(player.c>=h.c&&player.r<=h.r+5&&feet.x>rect.x-8&&feet.x<rect.x+rect.width+8&&feet.y-18>rect.y&&feet.y-18<rect.y+rect.height)ctx.globalAlpha=.35;ctx.drawImage(houseImages[h.tint]!,rect.x,rect.y,rect.width,rect.height);ctx.restore()}});}
  for(const t of trees){const p=project(t),im=sprites[t.kind]!,height=(t.kind==='pine'?155:132)*t.scale,scale=height/im.height;items.push({depth:p.y,draw:()=>{ctx.fillStyle='#335a3040';ctx.beginPath();ctx.ellipse(p.x+10,p.y+1,height*.33,height*.11,-.2,0,Math.PI*2);ctx.fill();ctx.save();if(feet.y<p.y&&Math.abs(feet.x-p.x)<height*.45&&feet.y-18>p.y-height)ctx.globalAlpha=.32;ctx.translate(p.x,p.y);ctx.transform(1,0,Math.sin(time*1.4+t.phase)*.009,1,0,0);ctx.drawImage(im,-im.width*scale*.5,-height*.97,im.width*scale,height);ctx.restore()}});}
  for(const g of gardens){for(let c=g.c+.4;c<g.c+g.w-.2;c+=.8)for(let r=g.r+.4;r<g.r+g.h-.2;r+=.8){const p=project({c,r}),n=hash(c*17,r*19);items.push({depth:p.y,draw:()=>{ctx.save();ctx.translate(Math.round(p.x),Math.round(p.y));const leaf=(x:number,y:number,size:number,fill:string)=>poly(ctx,[{x:x-size,y},{x:x-size,y:y-2},{x:x-1,y:y-size-2},{x:x+2,y:y-size},{x:x+size,y:y-2},{x:x+size-1,y:y+1},{x,y:y+2}],fill);leaf(0,-1,6,'#3c5933');leaf(-3,-3,4,'#6e9244');leaf(3,-4,4,'#87a451');leaf(0,-6,3,'#a2b969');ctx.fillStyle='#516c35';ctx.fillRect(-1,-6,1,6);if(g.id==='vegetables'&&n>.35){leaf(2,-1,3,'#be763d');ctx.fillStyle='#e8ad59';ctx.fillRect(1,-4,3,2);}ctx.restore()}});}for(const c of[g.c,g.c+g.w]){for(let r=g.r;r<g.r+g.h;r+=.8){const end=Math.min(r+.8,g.r+g.h);items.push({depth:project({c,r:end}).y,draw:()=>{line(ctx,project({c,r},7),project({c,r:end},7),'#70563a',3);line(ctx,project({c,r},8),project({c,r:end},8),'#b28d59',1)}});}for(let r=g.r;r<=g.r+g.h;r+=.8)post({c,r},11,items);}for(const r of[g.r,g.r+g.h]){items.push({depth:project({c:g.c,r}).y,draw:()=>line(ctx,project({c:g.c,r},7),project({c:g.c+g.w,r},7),'#9d794b',3)});for(let c=g.c;c<=g.c+g.w;c+=.8)post({c,r},11,items);}}
  function post(p:Point,h:number,list:typeof items){const q=project(p);list.push({depth:q.y,draw:()=>{ctx.fillStyle='#70563a';ctx.fillRect(q.x-2,q.y-h,4,h);ctx.fillStyle='#c49b63';ctx.fillRect(q.x-2,q.y-h,2,h-1)}})}
  for(const b of bridges)for(const c of [b.minC,b.maxC])for(let r=b.minR;r<b.maxR;r+=.7){const end=Math.min(r+.7,b.maxR),q=project({c,r:end});items.push({depth:q.y,draw:()=>{line(ctx,project({c,r},15),project({c,r:end},15),'#6a5139',4);line(ctx,project({c,r},17),project({c,r:end},17),'#d0ad77',2)}});post({c,r},18,items)}
  // Low flower beds use the same generated shrub, grounded in the existing soil/grass.
  for(const h of houses)for(const side of[0,1]){const p=project({c:h.c-.7,r:h.r+(side?4.4:.7)}),im=sprites.shrub!;items.push({depth:p.y,draw:()=>ctx.drawImage(im,p.x-18,p.y-25,36,31)});}
  // A point outside a visible wall must draw in front of that whole rigid footprint,
  // even when its feet are above the footprint's nearest corner in screen Y.
  for(const p of people){let depth=project(p).y;for(const h of houses){const box=houseRect(h),q=project(p);if((p.c<h.c||p.r>h.r+5)&&q.x>box.x-12&&q.x<box.x+box.width+12&&q.y>box.y&&q.y<box.y+box.height+38)depth=Math.max(depth,project({c:h.c,r:h.r+5}).y+.1)}items.push({depth,draw:()=>drawPerson(p)});}
  items.sort((a,b)=>a.depth-b.depth);for(const item of items)item.draw();decor?.over(ctx);
  const hero=people[0]!;const hp=project(hero);const hidden=houses.some(h=>{const r=houseRect(h);return hero.c>=h.c&&hero.r<=h.r+5&&hp.y<project({c:h.c,r:h.r+5}).y&&hp.x>r.x&&hp.x<r.x+r.width&&hp.y-20>r.y&&hp.y-20<r.y+r.height})||trees.some(t=>{const p=project(t);return hp.y<p.y&&Math.abs(hp.x-p.x)<48&&hp.y>p.y-120});
  if(hidden||zoom<.85){ctx.fillStyle='#ffe5a0';ctx.strokeStyle='#35503c';ctx.lineWidth=1;ctx.beginPath();ctx.moveTo(hp.x,hp.y-43);ctx.lineTo(hp.x-4,hp.y-49);ctx.lineTo(hp.x+4,hp.y-49);ctx.closePath();ctx.fill();ctx.stroke();}
  if(target){const p=project(target);ctx.strokeStyle='#ffedb499';ctx.lineWidth=1.5;ctx.beginPath();ctx.ellipse(p.x,p.y,9,4,0,0,Math.PI*2);ctx.stroke();}
  if(debug){for(const h of houses)poly(ctx,[project(h),project({c:h.c+5,r:h.r}),project({c:h.c+5,r:h.r+5}),project({c:h.c,r:h.r+5})],'#f65d5544','#ff897a');for(const b of bridges)poly(ctx,[project({c:b.minC,r:b.minR}),project({c:b.maxC,r:b.minR}),project({c:b.maxC,r:b.maxR}),project({c:b.minC,r:b.maxR})],'#72d9fb44','#a0eaff');}
 }
 return{draw,resize,overview,focus,screen,world,setGroundOnly(value:boolean){groundOnly=value},setTerrain(value?:HTMLCanvasElement){activeTerrain=value??terrain},pan(dx:number,dy:number){camera.x-=dx/zoom;camera.y-=dy/zoom;clamp()},zoom(f:number){zoom=Math.max(.4,Math.min(2.5,zoom*f))},get scale(){return zoom},get terrain(){return terrain},get sprites(){return sprites}};
}
