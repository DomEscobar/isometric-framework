"""Native source-pixel composition; diagnostic replay is never live model approval."""
import io,json,base64,zipfile
from pathlib import Path
import numpy as np
from PIL import Image
from artifacts import canonical,digest
from hybrid_render import render
ROOT=Path(__file__).resolve().parent
ACTOR=ROOT/'evidence/water-reference/character/artifact'
if not ACTOR.exists():ACTOR=ROOT.parent

def png(im):
    b=io.BytesIO();Image.fromarray(im).save(b,format='PNG');return b.getvalue()
def replay_materials():
    source=(ROOT/'evidence/hybrid-multilevel/generation/provider-original.png').read_bytes()
    old=json.loads((ROOT/'experiments/hybrid-multilevel/crops.json').read_bytes())
    mapping={'land':'grass','path':'sand','square':'paving','plateau':'paving','stairs':'stairs','wall':'masonry'}
    crops={k:{**old['crops'][v],'verdict':'pass','evidence_ids':['board'],'observation':'REPLAY: historical manually selected crop; NOT automatic extraction proof'} for k,v in mapping.items()}
    return source,{'source_sha256':old['source_sha256'],'crops':crops}
class Materials:
    def __init__(self,source,binding,world=None):
        if digest(source)!=binding['source_sha256']:raise ValueError('Materialsource-Drift')
        self.raw=np.array(Image.open(io.BytesIO(source)).convert('RGB'));self.binding=binding;self.flat=None
        if binding.get('mode')=='flat-terrain-image/1':
            if world is None:raise ValueError('Flat terrain source requires frozen world')
            from hybrid_painted_terrain import TerrainPixels
            self.flat=TerrainPixels(source,binding,world)
            return
        for c in binding['crops'].values():
            x,y,w,h=c['xywh']
            if min(x,y)<0 or min(w,h)<8 or x+w>self.raw.shape[1] or y+h>self.raw.shape[0]:raise ValueError('Crop außerhalb Source')
    def sample(self,name,u,v):
        if self.flat:return self.flat.sample(name,u,v)
        if name not in self.binding['crops']:raise ValueError('Fehlendes Material: '+name)
        c=self.binding['crops'][name];x,y,w,h=c['xywh'];su,sv=c['source_pixels_per_unit']
        ox,oy=c.get('offset',[0,0])
        ix=x+(np.floor(u*su).astype(int)+ox)%w;iy=y+(np.floor(v*sv).astype(int)+oy)%h
        return self.raw[iy,ix],np.stack([ix,iy],axis=-1).astype('<i2')
    def sample_wall(self,name,x,y,u,v,side):
        if self.flat:return self.flat.sample_wall(name,x,y,u,v,side)
        return self.sample(name,u,v)
def actor_scene(image,depth,w,actor_raw,shadow_raw,manifest):
    out=image.copy();x,y=w['spawn'];z=w['heights'][y][x];wx,wy=x+.5,y+.5
    px=w['origin'][0]+24*(wx-wy);py=w['origin'][1]+12*(wx+wy)-z
    for raw,anchor in [(shadow_raw,manifest['shadow_anchor_px']),(actor_raw,manifest['foot_anchor_px'])]:
        a=np.array(Image.open(io.BytesIO(raw)).convert('RGBA'));dx=int(px-anchor[0]+.5);dy=int(py-anchor[1]+.5)
        for sy in range(a.shape[0]):
            for sx in range(a.shape[1]):
                X,Y=dx+sx,dy+sy;alpha=int(a[sy,sx,3])
                if alpha and 0<=X<out.shape[1] and 0<=Y<out.shape[0] and depth[Y,X]<=wx+wy+.045:
                    out[Y,X,:3]=((a[sy,sx,:3].astype('uint32')*alpha+127)//255+(out[Y,X,:3].astype('uint32')*(255-alpha)+127)//255).astype('uint8')
    return out

def artifact_binding(directory):
    d=Path(directory);names=json.loads((d/'checksums.json').read_bytes())
    return {**names,'checksums.json':digest((d/'checksums.json').read_bytes()),'diagnostic.zip':digest((d/'diagnostic.zip').read_bytes())}
def verify_artifact(directory,binding):
    if not binding:raise ValueError('Artefaktbindung fehlt')
    for name,sha in binding.items():
        if digest((Path(directory)/name).read_bytes())!=sha:raise ValueError('Artefakt wurde nach Review verändert')
    return True

def build(directory,w,source,binding,provenance):
    d=Path(directory);d.mkdir(parents=True,exist_ok=True)
    im,depth,xy,flags=render(w,Materials(source,binding,w))
    # Independent direct RGB replay from retained per-pixel source addressing.
    original=np.array(Image.open(io.BytesIO(source)).convert('RGB'));hit=flags>0
    expected=original[xy[hit,1],xy[hit,0]].copy();east=flags[hit]==2
    expected[east]=(expected[east].astype('uint16')*218//255).astype('uint8')
    if not np.array_equal(expected,im[hit,:3]):raise ValueError('Source-Pixel-Replay fehlgeschlagen')
    actor=(ACTOR/'character.png').read_bytes();shadow=(ACTOR/'shadow.png').read_bytes();manifest=json.loads((ACTOR/'character-manifest.json').read_bytes())
    files={'terrain.png':png(im),'depth.f32':depth.tobytes(),'world.json':canonical(w),'provider-original.png':source,'material-binding.json':canonical(binding),'character.png':actor,'shadow.png':shadow,'character-manifest.json':canonical(manifest)}
    for name,array in [('source-xy.npy',xy),('pixel-flags.npy',flags)]:
        b=io.BytesIO();np.save(b,array);files[name]=b.getvalue()
    files['scene.png']=png(actor_scene(im,depth,w,actor,shadow,manifest))
    if binding.get('mode')=='flat-terrain-image/1':
        ox,oy=binding['grid']['origin'];cell=binding['grid']['cell_px']
        for name,coords in binding['regions'].items():
            x,y=coords[0];files[name+'-crop.png']=png(original[oy+y*cell:oy+(y+1)*cell,ox+x*cell:ox+(x+1)*cell])
    else:
        for name,c in binding['crops'].items():
            x,y,ww,hh=c['xywh'];files[name+'-crop.png']=png(original[y:y+hh,x:x+ww])
    data={'world':w,'character':manifest,'depth':base64.b64encode(depth.tobytes()).decode()}
    for k,v in [('terrain','terrain.png'),('sprite','character.png'),('shadow','shadow.png')]:data[k]='data:image/png;base64,'+base64.b64encode(files[v]).decode()
    template=(ROOT/'static/hybrid-navigator.html').read_text()
    files['index.html']=template.replace('__SCENE_DATA__',canonical(data).decode()).replace('__WIDTH__',str(w['canvas'][0])).replace('__HEIGHT__',str(w['canvas'][1])).encode()
    files['provenance.json']=canonical({**provenance,'layout_revision':w['revision'],'source_sha256':digest(source),'actor_sha256':digest(actor),'shadow_sha256':digest(shadow),'renderer_sha256':digest((ROOT/'hybrid_render.py').read_bytes()),'sampling':'floor/nearest source RGB; east faces multiply218/255; opaque synthesized background','user_acceptance':'pending','pixel_replay':True})
    files['README.txt']=b'Hybrid single-height terrain. Open index.html offline. Diagnostic unless provenance explicitly approves. No bridges/stacked surfaces. Static retained64px actor. Source XY replay included. Provider signed URLs/credentials intentionally omitted.\n'
    for n in ['hybrid_package.py','hybrid_artifact.py','hybrid_render.py','hybrid_painted_terrain.py','hybrid_layout.py','artifacts.py','layout_core.py','static/hybrid-navigator.html']:
        files['source/'+n]=(ROOT/n).read_bytes()
    files['source/rebuild.py']=b'''import sys,json\nfrom pathlib import Path\nfrom hybrid_artifact import build\nfrom hybrid_package import rebuild_extension\nd=Path(__file__).resolve().parents[1]\nout=Path(sys.argv[1])\nif out.exists():raise ValueError('Destination must not exist')\nprovenance=json.loads((d/'production-extension.json').read_bytes())['base_provenance'] if (d/'production-extension.json').exists() else json.loads((d/'provenance.json').read_bytes())\nbuild(out,json.loads((d/'world.json').read_bytes()),(d/'provider-original.png').read_bytes(),json.loads((d/'material-binding.json').read_bytes()),provenance)\nrebuild_extension(d,out)\n'''
    files['checksums.json']=canonical({n:digest(b) for n,b in files.items()})
    for n,b in files.items():
        (d/n).parent.mkdir(parents=True,exist_ok=True);(d/n).write_bytes(b)
    archive=d/'diagnostic.zip'
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
        for n,b in sorted(files.items()):
            info=zipfile.ZipInfo(n,(2026,1,1,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;z.writestr(info,b)
    with zipfile.ZipFile(archive) as z:
        if z.testzip():raise ValueError('ZIP CRC fehlgeschlagen')
        for n,h in json.loads(z.read('checksums.json')).items():
            if digest(z.read(n))!=h:raise ValueError('ZIP SHA fehlgeschlagen')
    return archive
