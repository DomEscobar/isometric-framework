"""Register generated cutouts at a shared world-pixel density; no painted assets.
uv run --python 3.12 --with Pillow==11.3.0 python prepare-props.py
Cutout: uv tool run --python 3.12 --from 'rembg[cpu,cli]==2.0.75' rembg i -m u2netp props-source.png props-cutout.png
"""
from pathlib import Path
import hashlib, json
from PIL import Image, ImageEnhance

HERE = Path(__file__).resolve().parent
source = Image.open(HERE/'props-source.png').convert('RGBA')
cutout = Image.open(HERE/'props-cutout.png').convert('RGBA')
# The generated background is a baked neutral checkerboard. rembg leaves a pale
# fringe; reject only bright near-neutral background colors, not colored foliage.
pixels = cutout.load()
raw = source.load()
for y in range(cutout.height):
    for x in range(cutout.width):
        r,g,b,a = pixels[x,y]
        sr,sg,sb,_ = raw[x,y]
        background = max(sr,sg,sb)-min(sr,sg,sb) < 14 and min(sr,sg,sb) > 110
        pixels[x,y] = (r,g,b,255 if a >= 205 and not background else 0)

specs = [
 ('tree-gold',(0,110,424,738),(207,686),210,True),
 ('tree-rust',(426,110,848,738),(630,690),218,True),
 ('tree-olive',(850,110,1254,738),(1052,689),202,True),
 ('rock',(0,760,421,1130),(214,1070),61,False),
 ('shrub',(423,760,841,1130),(630,1073),54,False),
 ('bench',(846,760,1254,1130),(1033,1072),72,False),
]
atlas = Image.new('RGBA',(768,512))
textures, records = {}, []
for index,(name,region,contact,size,by_height) in enumerate(specs):
    sprite = cutout.crop(region)
    box = sprite.getbbox()
    sprite = sprite.crop(box)
    factor = size/(sprite.height if by_height else sprite.width)
    dimensions = (round(sprite.width*factor),round(sprite.height*factor))
    sprite = sprite.resize(dimensions,Image.Resampling.LANCZOS)
    sprite = ImageEnhance.Color(sprite).enhance(.72)
    sprite = ImageEnhance.Brightness(sprite).enhance(.87)
    sprite.putalpha(sprite.getchannel('A').point(lambda a:255 if a>=128 else 0))
    x,y = (index%3)*256,(index//3)*256
    atlas.alpha_composite(sprite,(x,y))
    anchor = {'x':(contact[0]-region[0]-box[0])*factor/dimensions[0],
              'y':(contact[1]-region[1]-box[1])*factor/dimensions[1]}
    textures[name]={'image':'autumn-props','frame':{'x':x,'y':y,'width':dimensions[0],'height':dimensions[1]},'anchor':anchor}
    records.append({'name':name,'sourceCrop':region,'alphaBounds':box,'sourceContact':contact,'worldSize':dimensions,'anchor':anchor,
                    'limit':'Outer golden/olive canopy touches source sheet edge; use in framing foliage, not as an isolated silhouette specimen.' if name in ['tree-gold','tree-olive'] else ''})
atlas.save(HERE/'props-atlas.png')
(HERE/'props-frames.json').write_text(json.dumps(textures,indent=2)+'\n')
(HERE/'props-metadata.json').write_text(json.dumps({'source':'props-source.png','sourceSha256':hashlib.sha256((HERE/'props-source.png').read_bytes()).hexdigest(),
 'cutout':'rembg2.0.75 u2netp','preparation':'Opaque asset alpha threshold205, remove bright near-neutral baked background (spread<14,min>110); Lanczos registration to world pixel density; color factor0.72 and brightness0.87 to target muted palette; final alpha threshold128.',
 'parts':records},indent=2)+'\n')
print(json.dumps(records))

# A rectified r/z material patch from the generated left stone abutment.
# This is a material derivative, not a new painted stone pattern.
bridge = Image.open(HERE/'bridge-source-v2.png').convert('RGB')
wall = bridge.transform((32,32),Image.Transform.AFFINE,(4,0,256,1.92,4,370),Image.Resampling.BICUBIC)
wall.save(HERE/'wall-material.png')
(HERE/'wall-material.json').write_text(json.dumps({'source':'bridge-source-v2.png','sourcePlane':'near r/z masonry above left arch spring',
 'inverseMatrix':[4,0,256,1.92,4,370],'size':[32,32],'purpose':'Repeatable vertical stair/slab face material; appearance only.'},indent=2)+'\n')
