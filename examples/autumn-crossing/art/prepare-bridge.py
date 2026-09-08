"""Measured face extraction from generated bridge artwork; no painted stone.

Run: uv run --python 3.12 --with Pillow==11.3.0 python prepare-bridge.py
The original and rembg cutout are intentionally retained. This fits separate
r/z planes, NOT the flattened bridge. Vertical image lines remain vertical.
"""
from pathlib import Path
import hashlib
import json
from PIL import Image, ImageDraw, ImageChops

HERE = Path(__file__).resolve().parent
SOURCE = HERE / 'bridge-source-v2.png'
CUTOUT = HERE / 'bridge-cutout.png'
im = Image.open(CUTOUT).convert('RGBA')

# Authored polygon follows the visible long facade and end posts. The generated
# floor and perpendicular end wall must not enter these depth-separated layers.
NEAR = [(190,276),(255,241),(323,273),(323,309),(899,580),
        (957,583),(1027,611),(1027,901),(965,928),(898,896),
        (897,865),(852,877),(785,844),(760,762),(712,677),
        (667,623),(614,576),(548,551),(480,547),(423,562),
        (389,594),(385,677),(312,642),(307,598),(258,585),(189,550)]
FAR = [(468,126),(527,91),(597,119),(599,160),(1214,438),
       (1278,426),(1339,456),(1341,744),(470,342)]

def line_y(point, end, x):
    return point[1] + (end[1]-point[1]) * (x-point[0]) / (end[0]-point[0])

def clipped_polygon(points, baseline, keep_above):
    mask = Image.new('L', im.size)
    ImageDraw.Draw(mask).polygon(points, fill=255)
    half = Image.new('L', im.size)
    draw = ImageDraw.Draw(half)
    start, end = baseline
    for x in range(im.width):
        y = line_y(start,end,x)
        draw.line((x,0 if keep_above else y,x,y if keep_above else im.height),fill=255)
    return ImageChops.multiply(mask,half)

def make(name, polygon, source_contacts, target_contacts, vertical_scale,
         clip_contacts, keep_above, origin, body_height):
    # Forward transform: X=sx*x+tx, Y=sy*y+k*x+ty. This leaves every
    # source vertical post vertical while correcting the measured r-axis slope.
    a,b = source_contacts
    u,v = target_contacts
    sx = (v[0]-u[0])/(b[0]-a[0])
    sy = vertical_scale
    k = ((v[1]-u[1])-sy*(b[1]-a[1]))/(b[0]-a[0])
    tx = u[0]-sx*a[0]
    ty = u[1]-sy*a[1]-k*a[0]
    mask = clipped_polygon(polygon,clip_contacts,keep_above)
    layer = im.copy()
    layer.putalpha(ImageChops.multiply(layer.getchannel('A'),mask))
    # Render directly at the host's common one-pixel world sampling density.
    # Source high-frequency details are prefiltered, then runtime uses nearest.
    left,top,width,height = -64,-112,352,288
    inv = (1/sx,0,(left-tx)/sx,-k/(sx*sy),1/sy,
           (top-ty-k*(left-tx)/sx)/sy)
    result = layer.transform((width,height),Image.Transform.AFFINE,inv,
                             resample=Image.Resampling.BICUBIC)
    # Removing the rembg soft fringe is deliberate for this opaque masonry;
    # pixels below half alpha are background, not translucent stone.
    result.putalpha(result.getchannel('A').point(lambda alpha: 255 if alpha>=128 else 0))
    output = HERE / f'bridge-{name}.png'
    result.save(output)
    contacts = []
    for point,target in zip(source_contacts,target_contacts):
        actual = [sx*point[0]+tx,sy*point[1]+k*point[0]+ty]
        contacts.append({'source':point,'target':target,'actual':actual,
                         'errorPixels':max(abs(actual[i]-target[i]) for i in [0,1])})
    return {'file':output.name,'sha256':hashlib.sha256(output.read_bytes()).hexdigest(),
      'frame':{'x':0,'y':0,'width':width,'height':height},'width':width,
      'anchor':{'x':-left/width,'y':-top/height},
      'origin':origin,'footprint':{'columns':1,'rows':6},
      'bodyHeight':body_height,'blocking':False,
      'sourcePolygon':polygon,'clipBaseline':clip_contacts,'keepAbove':keep_above,
      'sourceToWorld':{'sx':sx,'sy':sy,'k':k,'tx':tx,'ty':ty},
      'contacts':contacts,'alphaBounds':result.getbbox()}

near_ground = [(190,549),(963,923)]
near_deck = [(190,335),(963,709)]
far_deck = [(470,211),(1278,581)]
parts = {
  'arch':make('arch',NEAR,near_ground,[(-32,0),(160,96)],64/214,
              near_deck,False,{'c':6,'r':6,'level':'ground'},64),
  'nearRail':make('near-rail',NEAR,near_deck,[(-32,0),(160,96)],24/126,
                  near_deck,True,{'c':6,'r':6,'level':'bridge'},24),
  'farRail':make('far-rail',FAR,far_deck,[(0,-16),(192,80)],24/149,
                 far_deck,True,{'c':8,'r':6,'level':'bridge'},24),
}
metadata = {'source':SOURCE.name,'sourceSha256':hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
  'cutout':{'file':CUTOUT.name,'tool':'rembg','version':'2.0.75','model':'u2netp'},
  'preparation':'Pillow 11.3.0; measured polygon masks and separate r/z face transforms',
  'projection':{'tileWidth':64,'tileHeight':32},
  'measurement':'Manually measured visible post contacts; inferred deck plane +/- 3 source pixels.',
  'limitations':['Render-only arch opening. Host must separately declare physical piers and underpass.',
                'Near arch and parapet are independently height fitted, meeting at the same deck plane.',
                'End-post caps intentionally overhang the edge endpoints; they do not expand collision.',
                'No original generated floor or perpendicular end wall is included.'],
  'acceptance':{'metadata':'measured','alpha':'inspected','inGame':'unverified'},'parts':parts}
(HERE/'bridge-metadata.json').write_text(json.dumps(metadata,indent=2)+'\n')

# One explicit contact board makes the three layered extraction results reviewable.
board = Image.new('RGBA',(1056,288),(57,74,62,255))
for i,part in enumerate(parts.values()):
    board.alpha_composite(Image.open(HERE/part['file']),(352*i,0))
    draw=ImageDraw.Draw(board)
    draw.text((352*i+8,8),part['file'],fill='white')
    for contact in part['contacts']:
        x,y=contact['target'];x+=64+352*i;y+=112
        draw.ellipse((x-2,y-2,x+2,y+2),fill='magenta')
board.save(HERE/'bridge-registration.png')
print(json.dumps({key:{'file':p['file'],'width':p['width'],'anchor':p['anchor'],
                      'origin':p['origin'],'bodyHeight':p['bodyHeight']} for key,p in parts.items()},indent=2))
