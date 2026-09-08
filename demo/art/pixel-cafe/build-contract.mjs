/**
 * Rebuild measured calibration sidecars; does not modify any image or scene.
 * Landmark observations and uncertainties are documented in measurement-notes.md.
 * Fixed hashes deliberately reject changed artwork until it is remeasured.
 */
import { readFileSync, writeFileSync } from 'node:fs';
import { createHash } from 'node:crypto';

const hashes = {
  'garden-atlas.png': '7f08b2abb668528fb81c82e99bd8dae6ddd68ad9d1fd6e0dede2292d626c4fe9',
  'gardener-atlas.png': '7bb2356b28300c152f0878a2d7b4996eb6c41ddb22c6800721a74b41bf67487a',
  'planter-bases.png': '1e2e0b0d81621bc66c4dfe526d862c19ead022acdc7443c363d438b0ddf42440',
};
for (const [file, expected] of Object.entries(hashes)) {
  const actual = createHash('sha256').update(readFileSync(new URL(file, import.meta.url))).digest('hex');
  if (actual !== expected) throw new Error(file + ' changed: remeasure artwork before updating its recorded hash.');
}
const xy = (x,y) => ({x,y});
const grid = (c,r) => ({c,r});
const frame = (x,y,width,height) => ({x,y,width,height});
const height = (reference,base,top) => ({reference,base:xy(...base),top:xy(...top)});
const canonical = [grid(-.5,-.5),grid(.5,-.5),grid(.5,.5),grid(-.5,.5)];
const envelope = (sources) => sources.map((source,i)=>({source:xy(...source),grid:canonical[i]}));
const asset = (id,kind,image,crop,anchor,render,groundPoints,heights=[],allowedOverhang='',footprint={columns:1,rows:1}) =>
  ({id,kind,image,sha256:hashes[image],frame:crop,anchor,render,footprint,groundPoints,heights,allowedOverhang});
const contract = {
  version:1,pack:'Sunflower courtyard measured integration; metadata scope only',
  projection:{tileWidth:80,tileHeight:40,heightPixelsPerUnit:40},
  tolerances:{groundErrorPx:2,heightErrorPx:4},
  heightReferences:{standing:1.85,leftSeat:.52,rightSeat:.49,tabletop:.74,parasolApex:3.28,soil:.25,lantern:1.9,palm:2.65,orangePlant:1.43,shrub:1.62},
  assets:[],
};
for (const [id,crop,points] of [
  ['terracotta',[10,992,299,197],[[4,97.5],[147.5,6],[292,97.5],[146,191]]],
  ['grass',[318,991,306,198],[[5,99],[152.5,5],[299,98.5],[152.5,193]]],
  ['sandstone',[947,991,301,198],[[5,99],[151,5],[294,98],[151,193]]],
]) contract.assets.push(asset(id,'terrain','garden-atlas.png',frame(...crop),xy(.5,.5),{width:80,height:40},envelope(points)));
for(let mask=0;mask<16;mask++) {
  contract.assets.push(asset('planter-base-'+mask,'prop','planter-bases.png',
    frame((mask%4)*160,Math.floor(mask/4)*128,160,128),xy(.5,88/128),{width:80},
    envelope([[0,88],[80,48],[160,88],[80,128]]),
    [height('soil',[80,88],[80,68])],
    'No rigid overhang. Ground envelope is known authored geometry; removed or hidden walls do not expose all four contacts. Separate flower sprites may overhang.'));
}
for (const [i,direction] of ['ne','se','sw','nw'].entries()) {
  const y=[25,328,635,939][i],contact=[261,261,260,258][i],top=[13,12,15,11][i];
  contract.assets.push(asset('gardener-'+direction+'-0','actor','gardener-atlas.png',
    frame(82,y,160,280),xy(.52,contact/280),{width:48},
    [{source:xy(83,contact),grid:grid(0,0)}],
    [height('standing',[83,contact],[83,top])],
    'Hat and limbs intentionally extend beyond the compact foot contact. Height includes the hat.'));
}
// These grids are INFERRED placements of independently observed contacts.
// They support containment, not independent proof of the drawing's projection.
const inferredContacts = (sources,crop,anchor,render) => sources.map(([x,y])=>{
  const scale=render.width/crop.width,offset=render.offset??xy(0,0);
  const rx=(x-anchor.x*crop.width)*scale+offset.x,ry=(y-anchor.y*crop.height)*scale+offset.y;
  return {source:xy(x,y),grid:grid(Math.round((rx/80-ry/40)*100)/100,Math.round((rx/80+ry/40)*100)/100)};
});
const parasolFrame=frame(42,6,275,342),parasolAnchor=xy(138/275,304/342),parasolRender={width:120,offset:xy(40,0)};
contract.assets.push(asset('parasol','prop','garden-atlas.png',parasolFrame,parasolAnchor,parasolRender,
  inferredContacts([[25,303],[70,327],[134,327],[203,316],[254,289]],parasolFrame,parasolAnchor,parasolRender),
  [height('leftSeat',[70,327],[69,279]),height('rightSeat',[203,316],[204,271]),height('tabletop',[134,327],[134,259]),height('parasolApex',[138,304],[138,3])],
  'Canopy and tight shadow may overhang the separate support contacts. Inferred support grids establish containment only. Composite remains a blocked decorative seating group, not walk-under furniture.',
  {columns:2,rows:2}));
const lampFrame=frame(742,635,110,337);
contract.assets.push(asset('lantern','prop','garden-atlas.png',lampFrame,xy(44/110,313/337),{width:27},
  // A independently fitted small 2:1 diamond (16 by 8 world pixels).
  [[13,310,-.1,-.1],[44,295,.1,-.1],[76,312,.1,.1],[44,329,-.1,.1]].map(([x,y,c,r])=>({source:xy(x,y),grid:grid(c,r)})),
  [height('lantern',[44,313],[44,3])],'Tight source shadow may extend beyond the footing.'));
for (const [id,crop,anchor,width,points,reference,base,top] of [
  ['orange-pot',[977,59,236,277],[.5,.92],54,[[77,249],[163,249],[120,264]],'orangePlant',[120,253],[120,3]],
  ['shrub',[993,357,223,277],[.5,.93],58,[[65,249],[153,249],[110,265]],'shrub',[110,257],[110,8]],
  ['palm',[945,642,292,325],[153/292,300/325],104,[[118,296],[189,296],[153,310]],'palm',[153,300],[153,3]],
]) {
  const f=frame(...crop),a=xy(...anchor),render={width};
  contract.assets.push(asset(id,'prop','garden-atlas.png',f,a,render,inferredContacts(points,f,a,render),
    [height(reference,base,top)],
    'Foliage and tight shadow may overhang the curved pot bottom. Contact grids are inferred from the observed curve; this checks containment, not independent projection compatibility.'));
}
const before=structuredClone(contract);
before.pack='Sunflower courtyard original purple planter diagnostic; expected failure';
before.assets=[asset('purple-bed-before','prop','garden-atlas.png',frame(15,366,300,278),xy(.5,.79),{width:82},
  envelope([[4,169],[115,104],[294,219],[188,271]]),[],
  'Foliage may overhang; stone may not. Preserved approximate source corners from the original diagnostic.')];
for (const [name,data] of [['art-contract.json',contract],['art-contract.before.json',before]]) {
  writeFileSync(new URL(name,import.meta.url),JSON.stringify(data,null,2)+'\n');
}
console.log('Wrote '+contract.assets.length+' current assets and '+before.assets.length+' preserved failing baseline asset.');

