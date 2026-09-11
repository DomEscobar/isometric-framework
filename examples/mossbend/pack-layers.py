"""Package the scene's original pixels as registered terrain and object layers.

The four traced cutouts are intentionally reused for six layout instances.
Water uses a code-authored, fixed-mask surface shimmer, not generated fluid motion.
"""
from pathlib import Path
from PIL import Image, ImageDraw, ImageChops, ImageFilter
import json, math, hashlib
A=Path(__file__).parent/'art'
source=Image.open(A/'scene-second.png').convert('RGBA')
clean=Image.open(A/'ground-raw.png').convert('RGBA')
if clean.size!=source.size:raise ValueError('Clean plate changed canvas size')
mask=Image.open(A/'tree-union-mask.png').convert('L').filter(ImageFilter.MaxFilter(9))
mask.save(A/'ground-edit-mask.png')
ground=Image.composite(clean,source,mask)
ground.save(A/'ground.png')
outside=ImageChops.multiply(ImageChops.difference(ground.convert('RGB'),source.convert('RGB')).convert('L'),ImageChops.invert(mask))
assert outside.getbbox() is None
measures=json.loads((A/'layer-measurements.json').read_text())
manifest={'images':{},'textures':{},'animations':{}}
def image(name,path):manifest['images'][name]={'url':path,'sampling':'nearest'}
def tex(name,img,box,anchor=None):
    d={'image':img,'frame':{'x':box[0],'y':box[1],'width':box[2],'height':box[3]}}
    if anchor:d['anchor']={'x':anchor[0],'y':anchor[1]}
    manifest['textures'][name]=d
image('ground','ground.png')
for r in range(12):
 for c in range(12):tex(f'ground-{c}-{r}','ground',(18+(c+r)*10-10,130+(r-c)*5-5,20,10))
bindings=[('oak-west','west',1),('oak-mid','far',.46),('oak-north','north',1),('oak-east','east',1),('oak-far','far',1),('tree-front','west',.34)]
for name,source_id,scale in bindings:
    cut=Image.open(A/f'tree-source-{source_id}.png');anchor=measures[source_id]['anchor']
    if scale!=1:
        cut=cut.resize((round(cut.width*scale),round(cut.height*scale)),Image.Resampling.NEAREST)
    cut.save(A/f'{name}.png');image(name,f'{name}.png');tex(name,name,(0,0,*cut.size),anchor)
empty=Image.new('RGBA',(4,4));empty.save(A/'empty.png');image('empty','empty.png');tex('empty','empty',(0,0,4,4))
# Blue material selection is authoring data, not navigation authority.
# Erode it so grass lips and stationary edge contacts cannot pulse.
wm=Image.new('L',source.size)
wm.putdata([255 if b>r*1.22 and g>r*1.15 and b>75 else 0 for r,g,b,a in ground.getdata()])
wm=wm.filter(ImageFilter.MinFilter(3));wm.save(A/'water-mask.png')
frames=[];atlas=Image.new('RGBA',(256,224*12))
for phase in range(12):
    frame=Image.new('RGBA',(256,224))
    for y in range(224):
      for x in range(256):
        if wm.getpixel((x,y)):
          red,green,blue,_=ground.getpixel((x,y))
          shift=round(7*math.sin(2*math.pi*((x+y*.5)/14-phase/12)))
          frame.putpixel((x,y),(max(0,min(255,red+shift)),max(0,min(255,green+shift)),max(0,min(255,blue+shift)),255))
    atlas.alpha_composite(frame,(0,phase*224));frames.append(frame)
# Pack actual diamond-alpha overlays per water cell into one small atlas.
cells=[(c,r) for r in range(12) for c in range(12) if abs(c-(5.5 if r<3 else 6.5 if r<8 else 7.5))<=.5 and r!=6]
wateratlas=Image.new('RGBA',(20*len(cells),10*12))
for idx,(c,r) in enumerate(cells):
    clip=[]
    for phase,frame in enumerate(frames):
        part=frame.crop((18+(c+r)*10-10,130+(r-c)*5-5,18+(c+r)*10+10,130+(r-c)*5+5))
        alpha=part.getchannel('A')
        for py in range(10):
          for px in range(20):
            if abs((px+.5-10)/10)+abs((py+.5-5)/5)>1:alpha.putpixel((px,py),0)
        part.putalpha(alpha);wateratlas.alpha_composite(part,(idx*20,phase*10))
        id=f'water-{c}-{r}-{phase}';tex(id,'water',(idx*20,phase*10,20,10),(.5,.5));clip.append(id)
    manifest['animations'][f'water-{c}-{r}']={'frames':clip,'fps':6,'loop':True}
wateratlas.save(A/'water-atlas.png');image('water','water-atlas.png')
(A/'runtime.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf8')
record={'outsideTreeMasksUnchanged':True,'manualPolygonCount':4,'originalTreeImages':4,'placedTrees':6,'reusedTreeInstances':['oak-mid','tree-front'],'resizedInstances':{'oak-mid':.46,'tree-front':.34},'water':'12-frame fixed-mask code-authored surface shimmer at 6fps; banks stationary','sourceHashes':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in [A/'scene-second.png',A/'ground-raw.png',A/'ground-edit-mask.png']}}
(A/'processing.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf8')
ground.resize((768,672),Image.Resampling.NEAREST).save(A/'ground-inspection.png')
print(json.dumps(record))
