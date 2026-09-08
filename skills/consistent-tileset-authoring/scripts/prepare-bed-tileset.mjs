import { readFile, writeFile, mkdir } from 'node:fs/promises';
import { existsSync } from 'node:fs';
import { resolve, dirname } from 'node:path';
import { createHash } from 'node:crypto';
import { chromium } from 'playwright';

// Authoring dependency only. The runtime never imports this script or Playwright.
const core = new URL('../../../src/core.ts', import.meta.url);
const { autotileMasks } = await import(existsSync(core) ? core.href : new URL('../../../dist/core.js', import.meta.url).href);
const [recipePath, outputPath] = process.argv.slice(2);
if (!recipePath || !outputPath) throw new Error('Usage: node --experimental-strip-types prepare-bed-tileset.mjs recipe.json output-directory');
const recipe = JSON.parse(await readFile(recipePath, 'utf8'));
if (recipe.version !== 1) throw new Error('Unsupported material recipe version');
if(recipe.rimWidth!==undefined&&(!Number.isFinite(recipe.rimWidth)||recipe.rimWidth<=0||recipe.rimWidth>.25))throw new Error('rimWidth must be in (0,.25] tile units');
if(recipe.alphaMode!==undefined&&!['require-opaque','opaque-material-rgb'].includes(recipe.alphaMode))throw new Error('Unknown alphaMode');
const materialResolution = recipe.materialResolution ?? 32;
if (!Number.isInteger(materialResolution) || materialResolution < 8 || materialResolution > 256) throw new Error('materialResolution must be an integer8..256');
const width = recipe.tileWidth ?? 64, height = recipe.tileHeight ?? 32, wall = recipe.wallHeight ?? 12;
if (!Number.isInteger(width) || width < 32 || width > 256 || width % 4 || height !== width / 2
  || !Number.isInteger(wall) || wall < 1 || wall > height) throw new Error('Use 2:1 integer geometry; width32..256 divisible by4, wall1..tileHeight');
const input = await readFile(resolve(dirname(recipePath), recipe.source));
const masks = [...autotileMasks('blob47')];
const browser = await chromium.launch();
let result;
try {
  const page = await browser.newPage();
  result = await page.evaluate(async ({ data, recipe, masks, width, height, wall, materialResolution }) => {
    const image = new Image(); image.src = `data:image/png;base64,${data}`; await image.decode();
    const source = document.createElement('canvas'); source.width=image.width;source.height=image.height;
    const sourceContext=source.getContext('2d');sourceContext.drawImage(image,0,0);
    const pixels=sourceContext.getImageData(0,0,image.width,image.height).data;
    const materials = {};
    for(const name of ['soil','cap','wall','grass']){
      const rect=recipe.materials?.[name];
      if(!Array.isArray(rect)||rect.length!==4||!rect.every(Number.isInteger)||rect[0]<0||rect[1]<0||rect[2]<2||rect[3]<2||rect[0]+rect[2]>image.width||rect[1]+rect[3]>image.height)throw new Error(`Invalid ${name} material rectangle`);
      const [x,y,w,h] = rect;
      for(let sy=y;sy<y+h;sy++)for(let sx=x;sx<x+w;sx++){
        const alpha=pixels[(sy*image.width+sx)*4+3];
        if(alpha!==255 && !(recipe.alphaMode==='opaque-material-rgb'&&alpha>=200))throw new Error(`Material ${name} must be opaque, or explicitly normalize a nearly opaque material sheet`);
      }
      // Prefilter once to a shared pixel density; direct sparse sampling of a large
      // generated image aliases fine details into unrelated bright/dark speckles.
      const swatch=document.createElement('canvas');swatch.width=swatch.height=materialResolution;
      const swatchContext=swatch.getContext('2d');swatchContext.imageSmoothingEnabled=true;swatchContext.imageSmoothingQuality='high';
      swatchContext.drawImage(image,x,y,w,h,0,0,materialResolution,materialResolution);
      materials[name]=swatchContext.getImageData(0,0,materialResolution,materialResolution).data;
    }
    // Mirrored repeat samples opposite boundaries from the same generated pixels.
    // This supplies repeat continuity, not new painted materials; symmetry is disclosed.
    const mirror=value=>{const p=((value%1)+1)%1;return p<.5?p*2:(1-p)*2;};
    const sample=(name,u,v,shade=1)=>{
      const sx=Math.round(mirror(u)*(materialResolution-1)),sy=Math.round(mirror(v)*(materialResolution-1));
      const at=(sy*materialResolution+sx)*4,swatch=materials[name];
      return [Math.round(swatch[at]*shade),Math.round(swatch[at+1]*shade),Math.round(swatch[at+2]*shade),255];
    };
    const frameWidth=width+16,frameHeight=height+wall+28,rootX=frameWidth/2,rootY=height/2+wall+20;
    const columns=8,rows=Math.ceil((masks.length+1)/columns),atlas=document.createElement('canvas');
    atlas.width=frameWidth*columns;atlas.height=frameHeight*rows;
    const context=atlas.getContext('2d'),output=context.createImageData(atlas.width,atlas.height),textures={},variants={},signatures=[];
    const inside=v=>v>=-.5&&v<.5;
    for(let index=0;index<=masks.length;index++){
      const grass=index===masks.length,mask=masks[index]??255,lift=grass?0:wall;
      const ox=index%columns*frameWidth,oy=Math.floor(index/columns)*frameHeight;
      let signature=2166136261,visible=0;
      for(let py=0;py<frameHeight;py++)for(let px=0;px<frameWidth;px++){
        const x=px+.5-rootX,y=py+.5-rootY;
        const c=x/width-(y+lift)/height,r=x/width+(y+lift)/height;
        let rgba;
        if(inside(c)&&inside(r)){
          const edge=.5-(recipe.rimWidth??.125);
          const exposed=(!(mask&1)&&c< -edge)||(!(mask&2)&&c>edge)||(!(mask&4)&&r< -edge)||(!(mask&8)&&r>edge);
          const inner=(!(mask&16)&&(mask&5)===5&&c< -edge&&r< -edge)
            ||(!(mask&32)&&(mask&6)===6&&c>edge&&r< -edge)
            ||(!(mask&64)&&(mask&9)===9&&c< -edge&&r>edge)
            ||(!(mask&128)&&(mask&10)===10&&c>edge&&r>edge);
          rgba=sample(grass?'grass':exposed||inner?'cap':'soil',c+.5,r+.5);
        }else if(!grass&&Math.abs(x)<width/2){
          const depth=y-(height/2-Math.abs(x)*height/width-wall);
          const frontLeft=x<0&&!(mask&1),frontRight=x>=0&&!(mask&8);
          if(depth>=0&&depth<wall&&(frontLeft||frontRight))rgba=sample('wall',Math.abs(x)/(width/2),depth/(wall*4),frontLeft?.84:1);
        }
        if(rgba){const at=((oy+py)*atlas.width+ox+px)*4;output.data.set(rgba,at);visible++;for(const v of rgba)signature=Math.imul(signature^v,16777619)>>>0;}
      }
      if(grass)textures.grass={image:'beds',frame:{x:ox+8,y:oy+rootY-height/2,width,height},anchor:{x:.5,y:.5}};
      else{const id=`bed-${mask}`;variants[mask]=id;textures[id]={image:'beds',frame:{x:ox,y:oy,width:frameWidth,height:frameHeight},anchor:{x:rootX/frameWidth,y:rootY/frameHeight}};signatures.push({mask,signature,visible});}
    }
    context.putImageData(output,0,0);
    return {png:atlas.toDataURL('image/png').split(',')[1],metadata:{version:1,mode:'blob47',tileWidth:width,tileHeight:height,bodyHeight:wall,frameWidth,frameHeight,anchor:{x:rootX/frameWidth,y:rootY/frameHeight},variants,textures},sourceDimensions:{width:image.width,height:image.height},signatures};
  }, { data:input.toString('base64'),recipe,masks,width,height,wall,materialResolution });
} finally { await browser.close(); }
if(new Set(result.signatures.map(s=>s.signature)).size!==47)throw new Error('Some corner states produced identical artwork; inspect rim resolution/materials');
await mkdir(outputPath,{recursive:true});
await writeFile(resolve(outputPath,'bed-atlas.png'),Buffer.from(result.png,'base64'));
await writeFile(resolve(outputPath,'tileset.json'),JSON.stringify(result.metadata,null,2)+'\n');
await writeFile(resolve(outputPath,'preparation.json'),JSON.stringify({source:recipe.source,sourceSHA256:createHash('sha256').update(input).digest('hex'),sourceDimensions:result.sourceDimensions,recipe,variants:result.signatures,scope:'Generated materials on deterministic 2:1 bed geometry, mirrored texture repetition. Not independently generated full-tile sprites or universal Wang terrain transitions.'},null,2)+'\n');
console.log(`Prepared47 distinct corner-aware variants and grass from ${result.sourceDimensions.width}x${result.sourceDimensions.height} generated material source.`);
