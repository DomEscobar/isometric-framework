import {findPath,type Cell} from '../../src/core.ts';
export type Point={c:number;r:number};
export type Screen={x:number;y:number};
export const WIDTH=48,HEIGHT=40,SUB=4;
export const projection={tileWidth:32,tileHeight:16,heightPixelsPerUnit:20};
export const project=(p:Point,z=0):Screen=>({x:64+(p.c+p.r)*16,y:450+(p.r-p.c)*8-z});
export const unproject=(p:Screen):Point=>({c:(p.x-64)/32-(p.y-450)/16,r:(p.x-64)/32+(p.y-450)/16});
export const riverCenter=(c:number)=>25+1.3*Math.sin(c/8)+.4*Math.sin(c/3);
export const riverHalf=2.6;
export const houses=[{id:'house-1',name:'Backstube',c:8,r:6,tint:0},{id:'house-2',name:'Kräuterhaus',c:21,r:6,tint:1},{id:'house-3',name:'Mühle',c:35,r:9,tint:2},{id:'house-4',name:'Gärtnerhaus',c:2,r:34,tint:3},{id:'house-5',name:'Gasthaus',c:30,r:32,tint:4}].map(h=>({...h,columns:5,rows:5,door:{c:h.c-.7,r:h.r+2.6}}));
export const bridges=[{id:'west-bridge',c:14.5},{id:'east-bridge',c:34.5}].map(b=>({...b,minC:b.c-1.6,maxC:b.c+1.6,minR:riverCenter(b.c)-4.4,maxR:riverCenter(b.c)+4.4}));
export const gardens=[{id:'herbs',c:15,r:6,w:4,h:4},{id:'vegetables',c:37,r:33,w:4,h:4}];
export const roads=[
 {points:[[3,12],[12,15],[20,16],[28,15],[38,18],[45,18]],width:2.1},
 {points:[[1.3,32],[12,33],[20,33],[28,30.5],[38,31],[45,34]],width:1.8},
 ...bridges.map(b=>({points:[[b.c,15],[b.c,b.minR],[b.c,b.maxR],[b.c,33]],width:1.5})),
 ...houses.map(h=>({points:[[h.door.c,h.door.r],[h.door.c,h.r<20?15.5:33]],width:1.2})),
 ];
export const square={c:23,r:17,rx:6,ry:3.1};
export const distSegment=(p:Point,a:number[],b:number[])=>{const dc=b[0]!-a[0]!,dr=b[1]!-a[1]!,t=Math.max(0,Math.min(1,((p.c-a[0]!)*dc+(p.r-a[1]!)*dr)/(dc*dc+dr*dr||1)));return Math.hypot(p.c-a[0]!-t*dc,p.r-a[1]!-t*dr)};
export function roadDistance(p:Point){let d=100;for(const road of roads)for(let i=1;i<road.points.length;i++)d=Math.min(d,distSegment(p,road.points[i-1]!,road.points[i]!)-road.width);const sq=(Math.hypot((p.c-square.c)/square.rx,(p.r-square.r)/square.ry)-1)*3;return Math.min(d,sq);}
export const trees:{id:string;c:number;r:number;kind:'oak'|'pine';scale:number;phase:number}[]=[];
function tree(c:number,r:number,kind:'oak'|'pine',scale=1){if(c<.6||c>WIDTH-.6||r<.6||r>HEIGHT-.6||roadDistance({c,r})<1.5||Math.abs(r-riverCenter(c))<4||trees.some(t=>Math.hypot(t.c-c,t.r-r)<2.4)||houses.some(h=>(c>h.c-.9&&c<h.c+5.9&&r>h.r-.9&&r<h.r+5.9)||(r>h.r+5&&r<h.r+10&&c>h.c-2&&c<h.c+7)||Math.hypot(c-h.door.c,r-h.door.r)<1.8))return;trees.push({id:'tree-'+trees.length,c,r,kind,scale,phase:(c*7+r*11)%10})}
for(let c=1;c<48;c+=3.8){tree(c,1.5,'pine',.85+(c%3)*.08);tree(c+1.4,38.7,'oak',.85)}
for(let r=5;r<38;r+=4){tree(1.3,r,'oak',.95);tree(46.6,r,'pine',1)}
for(const [c,r]of [[4,6],[17,3],[29,6],[43,8],[41,12],[5,21],[9,20],[25,21],[40,22],[22,37],[26,37],[44,37],[4,29]])tree(c!,r!,(c!%3)?'oak':'pine',.85);
export const insideRect=(p:Point,c:number,r:number,w:number,h:number)=>p.c>=c&&p.c<=c+w&&p.r>=r&&p.r<=r+h;
export const bridgeAt=(p:Point)=>bridges.find(b=>insideRect(p,b.minC,b.minR,b.maxC-b.minC,b.maxR-b.minR));
export function solid(p:Point){
 if(houses.some(h=>insideRect(p,h.c,h.r,h.columns,h.rows)))return true;
 if(gardens.some(g=>insideRect(p,g.c,g.r,g.w,g.h)))return true;
 if(trees.some(t=>Math.hypot(p.c-t.c,p.r-t.r)<.55))return true;
 for(const b of bridges)if(p.r>=b.minR&&p.r<=b.maxR&&(Math.abs(p.c-b.minC)<.17||Math.abs(p.c-b.maxC)<.17))return true;
 return false;
}
export function support(p:Point){return p.c>=0&&p.c<=WIDTH&&p.r>=0&&p.r<=HEIGHT&&(Math.abs(p.r-riverCenter(p.c))>riverHalf||!!bridgeAt(p));}
export function canStand(p:Point,radius=.22){for(let i=0;i<8;i++){const a=i*Math.PI/4,q={c:p.c+Math.cos(a)*radius,r:p.r+Math.sin(a)*radius};if(!support(q)||solid(q))return false;}return support(p)&&!solid(p);}
export const toCell=(p:Point):Cell=>({c:Math.round(p.c*SUB),r:Math.round(p.r*SUB)});
export const fromCell=(p:Cell):Point=>({c:p.c/SUB,r:p.r/SUB});
export const cells:Cell[]=[];const permitted=new Set<string>();
for(let r=0;r<=HEIGHT*SUB;r++)for(let c=0;c<=WIDTH*SUB;c++){const cell={c,r};if(canStand(fromCell(cell))){cells.push(cell);permitted.add(c+','+r)}}
export const canEnter=(p:Cell)=>permitted.has(p.c+','+p.r);
export function nearest(p:Point,radius=.6){let best=radius,result:Cell|null=null;for(let r=Math.floor((p.r-radius)*SUB);r<=Math.ceil((p.r+radius)*SUB);r++)for(let c=Math.floor((p.c-radius)*SUB);c<=Math.ceil((p.c+radius)*SUB);c++){const q={c,r},d=Math.hypot(c/SUB-p.c,r/SUB-p.r);if(d<best&&canEnter(q)){best=d;result=q}}return result;}
export const spawn={c:22,r:18};
export function route(start:Point,end:Point){if(!canStand(end))return null;const a=nearest(start),b=nearest(end);return a&&b?findPath(a,b,canEnter,()=>true,false):null;}
export const landmarks=[{id:'square',name:'Dorfplatz',c:22,r:18},...houses.map(h=>({id:h.id,name:h.name,...h.door})),{id:'garden',name:'Gemüsegarten',c:36,r:35},...bridges.map(b=>({id:b.id,name:b.id==='west-bridge'?'Westbrücke':'Mühlbrücke',c:b.c,r:(b.minR+b.maxR)/2}))];
