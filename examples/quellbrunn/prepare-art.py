"""Deterministic packing; retain generated alpha, original RGB and exact crop offsets."""
from pathlib import Path
import json,hashlib
from PIL import Image,ImageDraw
root=Path(__file__).resolve().parent;source=Image.open(root/'art/source.png').convert('RGBA');w,h=source.size
manifest={'images':{},'textures':{},'sprites':{}};board=Image.new('RGB',(w,h),'#704c70')
windows={'cottage':(65,30,610,610),'oak':(650,25,1292,640),'pine':(80,615,600,1218),'shrub':(745,770,1185,1180)}
for name,(x,y,right,bottom) in windows.items():
 crop=source.crop((x,y,right,bottom));alpha=crop.getchannel('A').point(lambda a:0 if a<32 else a);crop.putalpha(alpha);box=alpha.getbbox()
 if not box:raise ValueError(name+' empty')
 image=crop.crop(box);padded=Image.new('RGBA',(image.width+8,image.height+8));padded.paste(image,(4,4));padded.save(root/'art'/f'{name}.png');board.paste(padded,(x,y),padded)
 manifest['images'][name]={'url':name+'.png','sampling':'nearest'};manifest['textures'][name]={'image':name,'frame':{'x':0,'y':0,'width':padded.width,'height':padded.height}}
 manifest['sprites'][name]={'sourceCrop':[x+box[0],y+box[1],image.width,image.height],'width':padded.width,'height':padded.height}
(root/'art/manifest.json').write_text(json.dumps(manifest,indent=2));(root/'art/provenance.json').write_text(json.dumps({'provider':'built-in ImageGen','sourceSha256':hashlib.sha256((root/'art/source.png').read_bytes()).hexdigest(),'prompt':'prompt.txt','referenceRole':'user forest style only','processing':'Measured per-object windows, not assumed equal cells; alpha below32 removed as near-transparent fringe; source RGB unchanged; tight crop plus4px transparent padding','sourceSize':source.size,'sprites':manifest['sprites']},indent=2));board.save(root.parents[1]/'test-results/quellbrunn/packed-board.png');print(json.dumps({'size':source.size,'alpha':source.getchannel('A').getextrema(),'sprites':manifest['sprites']}))
