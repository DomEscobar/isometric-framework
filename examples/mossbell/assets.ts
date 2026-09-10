import type { AssetManifest, EntityType, TextureDefinition } from '../../src/index';
import ground from '../willow-quay/art/ground-tiles.json';
import groundUrl from '../willow-quay/art/ground-atlas.png?url';
import oldHouse from './art/bakery.png?url';
import bookHouse from './art/bookshop.png?url';
import gardener from '../../demo/art/pixel-cafe/gardener-atlas.png?url';
import flowers from '../../demo/art/pixel-cafe/flowers-v2.png?url';
import garden from '../../demo/art/pixel-cafe/garden-atlas.png?url';
import propsUrl from '../autumn-crossing/art/props-atlas.png?url';
import props from '../autumn-crossing/art/props-frames.json';
import tree from './art/bell-tree.png?url';
import cottage from './art/apothecary.png?url';
import spruce from './art/spruce.png?url';
import greenhouse from './art/greenhouse.png?url';
import fernSheet from './art/fern-sheet.png?url';
import beds from '../autotile-lab/art/tileset.json';
import bedsUrl from '../autotile-lab/art/bed-atlas.png?url';
import forestAtlas from './art/forest-atlas.png?url';
import forestFrames from './art/forest-frames.json';

export const pathCatalog = ground.variants;
export const bedCatalog = beds.variants;
const svg = (body: string, w = 64, h = 64) => `data:image/svg+xml,${encodeURIComponent(`<svg xmlns="http://www.w3.org/2000/svg" width="${w}" height="${h}" viewBox="0 0 ${w} ${h}">${body}</svg>`)}`;
const image = (url: string) => ({ url, sampling: 'nearest' as const });
const sprite = (texture: string, width: number, bodyHeight: number, blocking = false): EntityType => ({ blocking, bodyHeight, visual: { kind: 'sprite', texture, width } });

export function makeArt(): { assets: AssetManifest; types: Record<string, EntityType> } {
  const textures: Record<string, TextureDefinition> = { ...structuredClone(ground.textures), ...structuredClone(props) };
  const assets: AssetManifest = { images: { ground: image(groundUrl), 'autumn-props': image(propsUrl), cottage: image(cottage), oldHouse: image(oldHouse), bookHouse: image(bookHouse), tree: image(tree), spruce: image(spruce), actor: image(gardener), flowers: image(flowers), garden: image(garden) }, textures, animations: {} };
  const procedural = (id: string, body: string, w = 64, h = 64, anchor = { x: .5, y: 1 }) => {
    assets.images[id] = image(svg(body, w, h)); textures[id] = { image: id, anchor };
  };
  assets.images.beds=image(bedsUrl);
  assets.images['forest-terrain']=image(forestAtlas);Object.assign(textures,forestFrames);
  for(const [id,texture] of Object.entries(beds.textures))if(id!=='grass')textures[id]=structuredClone(texture);
  // Quiet authored ground in one shared 2:1 plane. The same grain continues at joins.
  const grain=(color:string)=>`<path fill="${color}" opacity=".22" d="${Array.from({length:40},(_,i)=>`M${i*17%32} ${i*23%32}h1v1h-1z`).join('' )}"/>`;
  const plane=(body:string)=>`<g transform="matrix(1 -.5 1 .5 0 16)">${body}</g>`;
  const moss=`<rect width="32" height="32" fill="#354f49"/>${grain('#83a082')}`;
  procedural('forest-grass',plane(moss),64,32,{x:.5,y:.5});
  for(const maskText of Object.keys(pathCatalog)){
    const mask=Number(maskText),left=mask&1?0:6,right=mask&2?32:26,top=mask&4?0:6,bottom=mask&8?32:26;
    procedural(`forest-path-${mask}`,plane(`${moss}<rect x="${left}" y="${top}" width="${right-left}" height="${bottom-top}" rx="3" fill="#62685b"/>${grain('#9b9d7d')}`),64,32,{x:.5,y:.5});
  }
  procedural('water-base','<path d="M0 16 32 0 64 16 32 32Z" fill="#214d59"/>',64,32,{x:.5,y:.5});
  for(let i=0;i<12;i++){
    const phase=i/12;
    let lines='';
    for(let lane=0;lane<4;lane++)for(let repeat=-2;repeat<3;repeat++){
      const c=phase+repeat+lane*.19,r=lane*.27;
      const x=32+(c+r-1)*32,y=16+(r-c)*16;
      lines+=`<path d="M${x} ${y}l12 -6" stroke="${lane%2?'#87b9be':'#57979e'}" stroke-width=".8" opacity=".44"/>`;
    }
    procedural(`flow-${i}`,`<defs><clipPath id="d"><path d="M0 16 32 0 64 16 32 32Z"/></clipPath></defs><g clip-path="url(#d)">${lines}</g>`,64,32,{x:.5,y:.5});
  }
  assets.animations!.flow={frames:Array.from({length:12},(_,i)=>`flow-${i}`),fps:5,loop:true};
  procedural('log-top',plane('<rect width="32" height="32" fill="#6b5852"/><path d="M4 0v32m8-32v32m8-32v32m8-32v32" stroke="#3e4240" stroke-width="1.5"/><path d="M6 0v32m8-32v32m8-32v32m8-32v32" stroke="#897562" stroke-width=".8"/>'),64,32,{x:.5,y:.5});
  const rows = [25, 328, 635, 939], columns = [82, 395, 710, 1025], contacts = [261, 261, 260, 258];
  for (const [row, dir] of ['ne', 'se', 'sw', 'nw'].entries()) {
    for (let i = 0; i < 4; i++) textures[`actor-${dir}-${i}`] = { image: 'actor', frame: { x: columns[i]!, y: rows[row]!, width: 160, height: 280 }, anchor: { x: .52, y: contacts[row]! / 280 } };
    assets.animations![`idle-${dir}`] = { frames: [`actor-${dir}-0`], fps: 1, loop: true };
    assets.animations![`walk-${dir}`] = { frames: [1, 0, 2, 0].map(i => `actor-${dir}-${i}`), fps: 8, loop: true };
    assets.animations![`gesture-${dir}`] = { frames: [0, 2, 1, 0].map(i => `actor-${dir}-${i}`), fps: 4, loop: false };
  }
  const facing = (d: string) => ({ idle: `idle-${d}`, walk: `walk-${d}`, jump: `idle-${d}` });
  const actor = sprite('actor-se-0', 28.4, 44, true);
  actor.visual.animations = { ...facing('se'), directions: Object.fromEntries(['ne', 'se', 'sw', 'nw', 'n', 'e', 's', 'w'].map((d, i) => [d, facing(['ne', 'se', 'sw', 'nw'][i % 4]!)])) };
  textures.cottage = { image: 'cottage', anchor: { x: .524, y: .79 } };
  textures.oldHouse = { image: 'oldHouse', anchor: { x: 626 / 1254, y: 970 / 1254 } };
  textures.bookHouse = { image: 'bookHouse', anchor: { x: 626 / 1254, y: 970 / 1254 } };
  textures.tree = { image: 'tree', anchor: { x: .527, y: .91 } };
  textures.spruce = { image: 'spruce', anchor: { x: .5, y: .956 } };
  textures.lantern = { image: 'garden', frame: { x: 742, y: 635, width: 110, height: 337 }, anchor: { x: .4, y: 313 / 337 } };
  for (const [i, id] of ['lavender', 'marigold', 'daisy'].entries()) textures[id] = { image: 'flowers', frame: { x: 12 + i * 591, y: 160, width: 576, height: 584 }, anchor: { x: .5, y: 480 / 584 } };
  procedural('invisible', '', 1, 1);
  procedural('mushrooms', '<path fill="#526479" d="M22 44h4v17h-4zm20 3h3v14h-3z"/><path fill="#86d9c7" d="M10 42h6v-7h7v-4h6v5h7v9H10zm24 4h5v-6h8v4h6v5H34z"/><path fill="#dcfff0" d="M17 37h5v3h-5zm10 2h4v3h-4zm14 4h4v3h-4z"/>');
  procedural('seedbed', '<ellipse cx="32" cy="49" rx="28" ry="13" fill="#34333d"/><path d="M7 48 32 35 57 48 32 61Z" fill="none" stroke="#858080" stroke-width="5"/><path d="M32 51v-15m0 8-9-7m9 2 9-7" fill="none" stroke="#76aaa0" stroke-width="3"/>');
  procedural('bloom', '<path d="M32 59V30m0 15-12-7m12 3 12-8" stroke="#69b9a4" stroke-width="3"/><g fill="#a7ffe0"><ellipse cx="32" cy="20" rx="6" ry="11"/><ellipse cx="22" cy="27" rx="11" ry="6" transform="rotate(30 22 27)"/><ellipse cx="43" cy="27" rx="11" ry="6" transform="rotate(-30 43 27)"/><ellipse cx="26" cy="36" rx="6" ry="10" transform="rotate(30 26 36)"/><ellipse cx="38" cy="36" rx="6" ry="10" transform="rotate(-30 38 36)"/></g><circle cx="32" cy="29" r="5" fill="#ffe9b0"/>');
  procedural('sign', '<path d="M30 60V20" stroke="#494149" stroke-width="6"/><path d="m8 15 41 3 10 9-10 7-41-4z" fill="#80766e"/><path d="m18 23 25 2m-6-5 6 5-7 5" fill="none" stroke="#c0cdb4" stroke-width="2"/>');
  procedural('cat', '<path d="M10 39q-8-17-5-20" stroke="#4b4257" stroke-width="7" fill="none"/><path fill="#554c63" d="M10 28h23v20H10zm21-8 3-11 8 10 7-9 3 13v17H31z"/><path fill="#e5c58d" d="M36 25h3v3h-3zm10 0h3v3h-3z"/><path d="M15 46v6m15-6v6" stroke="#65576f" stroke-width="5"/>', 64, 56);
  for (let i = 0; i < 8; i++) {
    const sway = Math.sin(i / 8 * Math.PI * 2) * 4;
    let fern = '<path d="M32 62V36" stroke="#395e58" stroke-width="2"/>';
    for (const side of [-1, 1]) for (let j = 0; j < 5; j++) {
      const x = 32 + side * (24 - j * 4) + sway * (1 - j * .12), y = 28 + j * 5;
      fern += `<path d="M32 59Q${x} ${y+10} ${x} ${y}" fill="none" stroke="${j%2 ? '#538573' : '#679b83'}" stroke-width="3"/><path d="M${x} ${y}l${side*8} -2 -3 8z" fill="#5e917e"/>`;
    }
    procedural(`fern-${i}`, fern);
    const blink = i === 6, bob = i < 4 ? 0 : 1;
    procedural(`wisp-${i}`, `<g transform="translate(0 ${bob})"><path fill="#5d9b8b" d="m17 28-4-17 12 10 11-10 5 17z"/><path fill="#a1d9bd" d="M14 25h25v17H14zm6 17h5v5h-5zm12 0h5v5h-5z"/><path d="m39 31 11-6-4 14-10 1z" fill="#79b8a3"/><path fill="#243b48" d="M20 29h3v${blink?1:4}h-3zm11 0h3v${blink?1:4}h-3z"/><path fill="#ebedc7" d="M24 36h6v5h-6z"/></g>`, 64, 52);
  }
  assets.images.fernSheet=image(fernSheet);
  for(let i=0;i<4;i++)textures[`fern-art-${i}`]={image:'fernSheet',frame:{x:(i%2)*627,y:Math.floor(i/2)*627,width:627,height:627},anchor:{x:310/627,y:548/627}};
  assets.animations!.fern = { frames: [0,0,1,1,2,2,3,3].map(i=>`fern-art-${i}`), fps: 3, loop: true };
  assets.animations!.fernB = { frames: [2,2,3,3,0,0,1,1].map(i=>`fern-art-${i}`), fps: 2.5, loop: true };
  assets.animations!.wisp = { frames: Array.from({ length: 8 }, (_, i) => `wisp-${i}`), fps: 2, loop: true };
  // Glass geometry is authored against the same 2:1 ground axes.
  procedural('greenhouse', '<path d="M16 152 96 112 176 152 96 192Z" fill="#6b6773"/><path d="M16 152V78L96 118V192Z" fill="#477273"/><path d="m96 192 80-40V78l-80 40z" fill="#375960"/><path d="m16 78 80-66 80 66-80 40z" fill="#72928c" fill-opacity=".7"/><g fill="none" stroke="#b8aa83" stroke-width="4"><path d="M16 152V78L96 12 176 78V152L96 192ZM16 78 96 118 176 78M96 12V118V192M56 98V172M136 98V172M16 114 96 154 176 114M56 45 136 98M136 45 56 98"/></g><g fill="#82a783"><path d="m35 141 9-29 6 33zm26 13 9-38 7 46zm50 13 9-40 8 32zm30-17 9-35 7 24z"/></g>', 192, 208, { x: .5, y: 152 / 208 });
  assets.images.greenhouse=image(greenhouse);textures.greenhouse={image:'greenhouse',anchor:{x:.51,y:.723}};
  const house = (texture: string, width: number): EntityType => ({ ...sprite(texture, width, 215, true), columns: 3, rows: 3, visual: { kind: 'sprite', texture, width, offset: { x: 64, y: 0 } } });
  const types: Record<string, EntityType> = {
    traveler: actor, villager: { ...structuredClone(actor), blocking: false },
    cottage: house('cottage', 266), bakery: house('oldHouse', 274), bookshop: house('bookHouse', 276),
    greenhouse: house('greenhouse', 258), tree: sprite('tree', 268, 230, true), spruce: sprite('spruce', 181, 174, true),
    smallSpruce: sprite('spruce', 143, 137, true), rock: sprite('rock', 52, 36, true), shrub: sprite('shrub', 45, 30),
    lantern: sprite('lantern', 20, 59, true), lavender: sprite('lavender', 36, 25), daisy: sprite('daisy', 29, 18),
    marigold: sprite('marigold', 31, 22), mushrooms: sprite('mushrooms', 35, 17), cat: sprite('cat', 30, 20),
    sign: sprite('sign', 41, 34, true), seedbed: sprite('seedbed', 51, 12, true), bloom: sprite('bloom', 54, 45),
    fern: { blocking: false, bodyHeight: 24, visual: { kind: 'sprite', animation: 'fern', width: 46 } },
    fernB: { blocking: false, bodyHeight: 24, visual: { kind: 'sprite', animation: 'fernB', width: 53 } },
    wisp: { blocking: false, bodyHeight: 20, visual: { kind: 'sprite', animation: 'wisp', width: 35 } },
    invisible: sprite('invisible', 1, 1), railBlock: { ...sprite('invisible', 1, 24, true) },
    railNear: sprite('parapet-left', 80, 24), railFar: sprite('parapet-right', 80, 24), bank: sprite('quay-wall', 80, 16),
    flow: {blocking:false,bodyHeight:1,visual:{kind:'sprite',animation:'flow',width:64}}, bench:sprite('bench',60,34,true),
  };
  for(const id of Object.values(bedCatalog))types[id]={blocking:true,bodyHeight:12,visual:{kind:'sprite',texture:id}};
  types.villager!.visual.tint = 0xd6c5e9;
  return { assets, types };
}

