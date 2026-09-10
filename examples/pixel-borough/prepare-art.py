"""Deterministic extraction/registration of generated originals; no painted assets.
Run with Pillow. Original files are never changed. All generated decisions are recorded.
"""
from pathlib import Path
from PIL import Image
import json, hashlib

ROOT = Path(__file__).resolve().parent
ART = ROOT / 'art'
OUT = ART / 'packed'
OUT.mkdir(exist_ok=True)
images, textures, animations, records = {}, {}, {}, []

def keyed(name):
    path = ART / 'originals' / (name + '.png')
    im = Image.open(path).convert('RGBA')
    # The source deliberately excludes saturated magenta from its subjects.
    pixels = list(im.getdata())
    im.putdata([(r,g,b,0 if (min(r,b)>g+25 and min(r,b)>50 and r>.6*b and b>.6*r) or a<16 else a) for r,g,b,a in pixels])
    records.append({'source':str(path.relative_to(ROOT)), 'sha256':hashlib.sha256(path.read_bytes()).hexdigest(), 'decodedSize':im.size, 'processing':'magenta-only alpha extraction; nearest resampling; measured crop registration'})
    return im

def save(name, im):
    im.save(OUT / (name+'.png'))
    images[name] = {'url':'packed/'+name+'.png','sampling':'nearest'}

def texture(name, image, frame=None, anchor=(.5,1)):
    textures[name] = {'image':image,'anchor':{'x':anchor[0],'y':anchor[1]}}
    if frame: textures[name]['frame']=dict(zip(['x','y','width','height'],frame))

def isolated(name, source, width, anchor=(.5,1), window=None):
    im=keyed(source)
    if window: im=im.crop(window)
    box=im.getbbox()
    if not box: raise ValueError('empty '+source)
    crop=im.crop(box)
    h=round(crop.height*width/crop.width)
    small=crop.resize((width,h),Image.Resampling.NEAREST)
    padded=Image.new('RGBA',(width+4,h+4))
    padded.paste(small,(2,2))
    save(name,padded)
    texture(name,name,anchor=anchor)
    records[-1].update({'output':name,'crop':box,'outputSize':padded.size,'anchor':anchor})
    return padded

# Source poses were visually inspected: row order really is NE, SE, SW, NW.
# Measured full-pose windows isolate bodies; all poses use the same scale 0.135.
actor=keyed('explorer')
sheet=Image.new('RGBA',(48*4,48*4))
rows=[(30,305),(325,596),(620,896),(918,1215)]
cols=[(70,258),(378,558),(686,866),(994,1175)]
for row,direction in enumerate(['ne','se','sw','nw']):
    ids=[]
    for col,(left,right) in enumerate(cols):
        top,bottom=rows[row]
        crop=actor.crop((left,top,right,bottom))
        bounds=crop.getbbox()
        if not bounds: raise ValueError('empty actor frame')
        body=crop.crop(bounds)
        small=body.resize((round(body.width*.135),round(body.height*.135)),Image.Resampling.NEAREST)
        # Foot plane registered; no per-frame scale fit. Preserve measured relative dimensions.
        sheet.paste(small,(col*48+24-small.width//2,row*48+42-small.height))
        tid='explorer.'+direction+'.'+str(col)
        texture(tid,'explorer',(col*48,row*48,48,48),(.5,42/48))
        ids.append(tid)
    animations['explorer.walk.'+direction]={'frames':ids,'fps':7,'loop':True}
    animations['explorer.idle.'+direction]={'frames':[ids[1]],'fps':1,'loop':True}
save('explorer',sheet)
isolated('seed-shop','seed-shop-chroma',150,(.48,.85))

if (ART/'originals/plants.png').exists():
    for name,window,width in [
        ('oak',(20,20,400,460),88),('fir',(465,15,800,460),68),('orchard',(865,20,1230,460),84),
        ('pine',(25,485,325,845),55),('tall-grass',(350,485,880,845),64),('flower-bush',(895,485,1230,845),38),
        ('berry',(10,890,390,1230),40),('flowers',(420,890,800,1230),25),('rock',(850,880,1245,1240),42)]:
        isolated(name,'plants',width,(.5,.94),window)
if (ART/'originals/buildings.png').exists():
    for name,window,width,anchor in [
        ('bakery',(15,30,620,620),158,(.38,.87)),('station',(630,50,1240,620),176,(.5,.88)),
        ('blue-house',(15,640,620,1220),144,(.36,.87)),('sage-house',(635,645,1240,1230),138,(.6,.88))]:
        isolated(name,'buildings',width,anchor,window)
if (ART/'originals/grass2.png').exists():
    for i in range(3):
        isolated('meadow-'+str(i),'grass2',[62,48,55][i],(.5,.93),(i*724,90,(i+1)*724,600))
if (ART/'originals/props.png').exists():
    for name,window,width,anchor in [
        ('fruit-stall',(50,20,595,510),62,(.5,.84)),('lamp',(680,40,915,495),18,(.5,.97)),
        ('fence-ne',(1020,80,1470,490),48,(.5,.7)),('bread-stall',(50,515,595,990),62,(.5,.84)),
        ('bench',(630,550,990,960),42,(.5,.85)),('fence-se',(1025,550,1480,965),48,(.5,.7))]:
        isolated(name,'props',width,anchor,window)
if (ART/'originals/creatures.png').exists():
    src=keyed('creatures')
    atlas=Image.new('RGBA',(4*48,3*48))
    for row,name in enumerate(['nib','bramble','pip']):
        ids=[]
        for col in range(4):
            tile=src.crop((col*384,row*330,(col+1)*384,(row+1)*330))
            box=tile.getbbox(); crop=tile.crop(box)
            small=crop.resize((round(crop.width*.11),round(crop.height*.11)),Image.Resampling.NEAREST)
            atlas.paste(small,(col*48+24-small.width//2,row*48+42-small.height))
            tid=name+'.'+str(col);ids.append(tid)
            texture(tid,'creatures',(col*48,row*48,48,48),(.5,42/48))
        animations[name+'.idle']={'frames':[ids[0],ids[0],ids[0],ids[1]],'fps':2,'loop':True}
        animations[name+'.greet']={'frames':[ids[0],ids[2],ids[2],ids[3]],'fps':4,'loop':False}
    save('creatures',atlas)
if (ART/'originals/fountain.png').exists():
    src=keyed('fountain')
    atlas=Image.new('RGBA',(96*4,80))
    frames=[]
    # Measured source spacing 543; fixed source scale and baseline.
    base=src.crop((0,128,543,568))
    for i in range(4):
        frame=src.crop((i*543,128,(i+1)*543,568))
        # Hold masonry exactly fixed below the spray. Basin motion is authored
        # from blue source pixels only; column and stone never change.
        for y in range(175,440):
            for x in range(543):
                bp=base.getpixel((x,y));cp=frame.getpixel((x,y))
                if not (bp[2]>bp[0]*1.3 and bp[1]>bp[0]*1.2 and cp[2]>cp[0]*1.3): frame.putpixel((x,y),bp)
        small=frame.resize((92,75),Image.Resampling.NEAREST)
        atlas.paste(small,(i*96+2,2))
        tid='fountain.'+str(i);frames.append(tid)
        texture(tid,'fountain',(i*96,0,96,80),(.5,.79))
    save('fountain',atlas)
    animations['fountain.flow']={'frames':frames,'fps':5,'loop':True}
if (ART/'originals/bridge.png').exists():
    src=keyed('bridge').crop((130,300,1120,975))
    bridge=src.resize((180,123),Image.Resampling.NEAREST)
    # Split source along the front rail's inner lip, retaining original pixels.
    front=Image.new('RGBA',bridge.size);back=bridge.copy()
    lip=[(0,26),(13,29),(40,36),(73,48),(104,66),(135,88),(147,91),(154,107)]
    for x in range(bridge.width):
        if x>154: continue
        threshold=26
        for j in range(len(lip)-1):
            a,b=lip[j],lip[j+1]
            if a[0]<=x<=b[0]: threshold=a[1]+(b[1]-a[1])*(x-a[0])/(b[0]-a[0]);break
        for y in range(max(0,round(threshold)),bridge.height):
            front.putpixel((x,y),bridge.getpixel((x,y)));back.putpixel((x,y),(0,0,0,0))
    for name,im in [('bridge-back',back),('bridge-front',front)]:
        save(name,im);texture(name,name,anchor=(.24,.30))
if (ART/'originals/bridge-kit.png').exists():
    kit=keyed('bridge-kit')
    # The generated orthographic stone swatch supplies the authoritative deck.
    # Ground samples share world UVs; this is generated material + fixed geometry.
    stone=kit.crop((1606,173,1980,535)).resize((128,128),Image.Resampling.NEAREST)
    deck_atlas=Image.new('RGBA',(6*48,24))
    for r in range(18,24):
        tile=Image.new('RGBA',(48,24))
        for y in range(24):
            for x in range(48):
                dc=(x-24)/48-(y-12)/24;dr=(x-24)/48+(y-12)/24
                tile.putpixel((x,y),stone.getpixel((int((11+dc)*16)%128,int((r+dr)*16)%128)))
        deck_atlas.paste(tile,((r-18)*48,0));texture('deck.'+str(r),'deck',((r-18)*48,0,48,24),(.5,.5))
    save('deck',deck_atlas)

# A generated composed ground patch is rectified as terrain only. No vertical
# props are sheared. Shared samples are extracted into adjacent runtime tile frames.
ground=keyed('ground4').crop((24,34,1512,922)).resize((1152,576),Image.Resampling.NEAREST)
save('ground-overview',ground)
tile_atlas=Image.new('RGBA',(24*48,24*24))
navigation=[]
for r in range(24):
    line=[]
    for c in range(24):
        cx=(c+r+1)*24; cy=(r-c)*12+288
        tile=ground.crop((cx-24,cy-12,cx+24,cy+12))
        tile_atlas.paste(tile,(c*48,r*24))
        texture('ground.'+str(c)+'.'+str(r),'terrain',(c*48,r*24,48,24),(.5,.5))
        blue=0
        for dx in [-5,0,5]:
            for dy in [-3,0,3]:
                rr,gg,bb,aa=ground.getpixel((min(1151,max(0,cx+dx)),min(575,max(0,cy+dy))))
                blue+=bb-rr>70 and gg-rr>35 and bb>gg*1.1
        line.append('water' if blue>=2 else 'land')
    navigation.append(line)
save('terrain',tile_atlas)

# Flow translates generated surface pixels in one shared world coordinate space.
# Banks remain the original static terrain. Frame canvases carry diamond alpha.
# Dual scrolling full-river samples blend at their cyclic join, without drawing
# procedural water artwork or repeating a small distinctive panel.
water_atlas=Image.new('RGBA',(8*48,24*24*24))
river_atlas=Image.new('RGBA',(4*1154,2*578))
water_index=[]
def blue(p): return p[3]>16 and p[2]-p[0]>70 and p[1]-p[0]>35 and p[2]>p[1]*1.1
for r in range(24):
    for c in range(24):
        cx=(c+r+1)*24;cy=(r-c)*12+288
        mask=[]
        for y in range(24):
            for x in range(48):
                gx=cx-24+x;gy=cy-12+y
                if 0<=gx<1152 and 0<=gy<576 and abs((x+.5-24)/24)+abs((y+.5-12)/12)<=1 and blue(ground.getpixel((gx,gy))):mask.append((x,y,gx,gy))
        if not mask:continue
        idx=len(water_index);water_index.append({'c':c,'r':r})
        ids=[]
        for phase in range(8):
            frame=Image.new('RGBA',(48,24))
            for x,y,gx,gy in mask:
                # Dual scrolling samples from the entire generated river, not
                # a tiny repeated panel. Crossfade phase branches so the wrap
                # is continuous; sample motion follows (-2,+1) in screen space.
                base=ground.getpixel((gx,gy))
                samples=[]
                for shift in [phase,phase-8]:
                    sx=max(0,min(1151,gx+shift*2));sy=max(0,min(575,gy-shift))
                    sample=ground.getpixel((sx,sy))
                    samples.append(sample if blue(sample) else base)
                t=phase/8
                p=tuple(round(samples[0][j]*(1-t)+samples[1][j]*t) for j in range(3))+(255,)
                frame.putpixel((x,y),p)
                river_atlas.putpixel(((phase%4)*1154+gx+1,(phase//4)*578+gy+1),p)
            water_atlas.paste(frame,(phase*48,idx*24))
            tid=f'water.{idx}.{phase}';ids.append(tid);texture(tid,'water',(phase*48,idx*24,48,24),(.5,.5))
        animations[f'water.flow.{idx}']={'frames':ids,'fps':8,'loop':True}

water_atlas=water_atlas.crop((0,0,384,max(24,len(water_index)*24)))
save('water',water_atlas)
save('river-strip',river_atlas)
river_frames=[]
for phase in range(8):
    tid=f'river.{phase}';river_frames.append(tid)
    texture(tid,'river-strip',((phase%4)*1154,(phase//4)*578,1154,578),(25/1154,289/578))
animations['river.flow']={'frames':river_frames,'fps':8,'loop':True}
if water_index: animations['water.flow']=animations['water.flow.'+str(len(water_index)//2)]
(ART/'water-cells.json').write_text(json.dumps(water_index),encoding='utf8')
(ART/'navigation.json').write_text(json.dumps(navigation),encoding='utf8')

(ART/'runtime.json').write_text(json.dumps({'images':images,'textures':textures,'animations':animations},indent=2),encoding='utf8')
(ART/'processing.json').write_text(json.dumps(records,indent=2),encoding='utf8')
print(json.dumps({'images':len(images),'textures':len(textures),'clips':len(animations),'waterCells':sum(x=='water' for row in navigation for x in row)}))
