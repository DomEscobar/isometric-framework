import type { Scene, AssetManifest } from '../../src/index.ts';
import packed from './art/runtime.json';
import navigation from './art/navigation.json';
const imageUrls=import.meta.glob<string>('./art/packed/*.png',{eager:true,query:'?url',import:'default'});
export const creatureNames:Record<string,string>={nib:'Nib',bramble:'Bramble',pip:'Pip'};
export const bridgeRoute=Array.from({length:6},(_,i)=>({c:11,r:18+i}));
export function makeScene(groundOnly=false): Scene {
 const assets=structuredClone(packed) as AssetManifest;
 for(const image of Object.values(assets.images)){const url=imageUrls['./art/'+image.url];if(!url)throw new Error('Missing packed image: '+image.url);image.url=url;}
 const tiles:Scene['tiles']={};
 const map=navigation.map((row,r)=>row.map((kind,c)=>{const id=`cell.${c}.${r}`;const deck=(c===11&&r>=18)||(c===10&&r===23);tiles[id]={color:deck?0xa59f87:0x629b50,texture:deck?`deck.${r}`:`ground.${c}.${r}`,walkable:kind!=='water'||deck,elevation:deck?2:0};return id;}));
 tiles['cell.0.0']!.elevation=-2;
 const entityTypes:Scene['entityTypes']={explorer:{blocking:true,bodyHeight:44,visual:{kind:'sprite',texture:'explorer.se.1',width:72,animations:{directions:Object.fromEntries(['ne','se','sw','nw'].map(d=>[d,{idle:`explorer.idle.${d}`,walk:`explorer.walk.${d}`}]))}}}};
 const entities:Scene['entities']=[{id:'explorer',type:'explorer',c:11,r:13}];
 function prop(id:string,texture:string,c:number,r:number,columns=1,rows=1,bodyHeight=0,offset={x:0,y:0}){entityTypes[id]={blocking:bodyHeight>0,columns,rows,...(bodyHeight?{bodyHeight}:{}),visual:{kind:'sprite',texture,offset}};entities.push({id,type:id,c,r,data:{decoration:true}});}
 // A flat full-map carrier volume prevents conflicting geographic depth axes
 // for this joined water image. The alpha contains only the actual river.
 // Its carrier corner is lowered 2px; the image offset preserves world samples.
 entityTypes.river={blocking:false,bodyHeight:.01,columns:24,rows:24,visual:{kind:'sprite',animation:'river.flow',offset:{x:0,y:-2}}};
 entities.push({id:'river',type:'river',c:0,r:0,data:{water:true}});
 if(!groundOnly){
  prop('seed-shop','seed-shop',13,7,3,3,105,{x:48,y:0});
  prop('bakery','bakery',18,10,3,3,105,{x:48,y:0});
  prop('field-station','station',8,6,3,3,98,{x:48,y:0});
  prop('blue-cottage','blue-house',19,16,3,3,105,{x:48,y:0});
  prop('sage-cottage','sage-house',6,12,3,3,105,{x:48,y:0});
  prop('fruit-market','fruit-stall',17,14,1,1,44);prop('bread-market','bread-stall',15,17,1,1,44);
  entityTypes.fountain={blocking:true,columns:2,rows:2,bodyHeight:60,visual:{kind:'sprite',animation:'fountain.flow',offset:{x:24,y:0}}};entities.push({id:'fountain',type:'fountain',c:13,r:14,data:{decoration:true}});
  prop('bridge-back','bridge-back',10,18,3,6,0,{x:24,y:-12});
  entityTypes['bridge-back']!.bodyHeight=.01;
  // Same pixels, separate near-rail depth origin. Ground map owns occupancy.
  prop('bridge-front','bridge-front',10,21,1,1,0,{x:-48,y:-48});
  entityTypes['bridge-front']!.bodyHeight=20;
  const trees:[string,number,number][]=[['oak',1,1],['orchard',4,1],['oak',7,1],['fir',10,1],['fir',12,0],['pine',14,1],['fir',16,0],['oak',18,1],['fir',20,0],['fir',22,1],['pine',23,3],['fir',21,4],['pine',19,3],['orchard',16,4],['pine',14,3],['fir',11,3],['oak',2,5],['orchard',3,9],['oak',1,13],['fir',2,15],['pine',3,17],['orchard',5,18],['fir',1,18],['pine',5,21],['pine',18,23],['pine',22,22]];
  trees.forEach(([type,c,r],i)=>prop('tree-'+i,type,c===3&&r===9?0:c,c===3&&r===9?8:(c===5&&r===21)||(c===22&&r===22)?23:r,1,1,76));
  for(let r=3;r<=11;r++)for(let c=1;c<=7;c++){if((c===7&&r>7)||(c<3&&r>8)||(r===3&&c<3)||((c*17+r*11)%9===0)||(Math.abs(c-5)+Math.abs(r-7)<=2)||(c===6&&r>=7))continue;prop(`grass-${c}-${r}`,'meadow-'+((c*7+r*11)%3),c,r,1,1,0,{x:((c*7+r*3)%9)-4,y:((c+r*2)%5)-2});}
  const shrubs:[string,number,number][]=[['berry',4,4],['flowers',6,2],['flower-bush',9,4],['flowers',12,5],['berry',18,6],['rock',22,6],['flowers',20,8],['flowers',10,9],['flower-bush',8,10],['flowers',5,15],['berry',4,16],['flowers',8,18],['flower-bush',9,19],['flowers',13,19],['flower-bush',17,19],['flowers',20,20],['flowers',12,23],['flowers',15,23],['berry',20,23]];
  shrubs.forEach(([type,c,r],i)=>prop('plant-'+i,type,c,r));
  [[9,11],[12,17],[17,12],[20,14],[9,23],[16,23],[15,5]].forEach(([c,r],i)=>prop('lamp-'+i,'lamp',c!,r!,1,1,50));
  prop('bench-0','bench',12,11,1,1,15);prop('bench-1','bench',16,18,1,1,15);
  for(let c=1;c<=5;c+=2)prop('fence-left-'+c,'fence-ne',c,12,1,1,20);
  for(let r=1;r<=5;r+=2)prop('fence-back-'+r,'fence-se',17,r,1,1,20);
  for(const [id,c,r] of [['nib',20,5],['bramble',5,7],['pip',14,23]] as const){entityTypes[id]={blocking:true,bodyHeight:32,visual:{kind:'sprite',animation:id+'.idle',width:67}};entities.push({id,type:id,c,r,data:{creature:true,name:creatureNames[id]}});}
  entities.push({id:'resident-1',type:'explorer',c:17,r:13,data:{resident:true}},{id:'resident-2',type:'explorer',c:10,r:10,data:{resident:true}});
 }
 return {version:1,name:'Pixel Borough',tileWidth:48,tileHeight:24,map,tiles,assets,diagonal:false,maxStepHeight:2,entityTypes,entities,controlledId:'explorer'};
}
