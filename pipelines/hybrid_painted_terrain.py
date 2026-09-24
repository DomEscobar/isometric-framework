"""Flat, layout-bound painted terrain source for deterministic heightfield rendering.

The provider repaints a canonical orthographic cell-map. Output pixels remain the material
source; the runtime renderer projects them onto the frozen elevation geometry.
"""
import io
import numpy as np
from PIL import Image
from artifacts import digest

CELL_PX=48
GUIDE_SIZE=(2294,1608)
COLORS={'land':(98,145,82),'path':(168,127,77),'square':(191,177,139),'plateau':(133,160,99),'stairs':(179,149,100),'water':(49,120,166),'shore':(194,169,119),'wall':(99,91,82)}
WALL_BLOCK=[-2,0]
STAIR_BLOCK=[-2,1]


def semantic_regions(world):
    regions={name:[] for name in sorted({v for row in world['cells'] for v in row})}
    water={(x,y) for y,row in enumerate(world['cells']) for x,name in enumerate(row) if name=='water'}
    for y,row in enumerate(world['cells']):
        for x,name in enumerate(row):
            if name=='land' and any((x+dx,y+dy) in water for dx,dy in ((1,0),(-1,0),(0,1),(0,-1))):
                regions.setdefault('shore',[]).append([x,y])
            else:regions[name].append([x,y])
    return regions


def _cell_colors(world):
    regions=semantic_regions(world)
    result={}
    for name,cells in regions.items():
        for x,y in cells:result[x,y]=COLORS[name]
    return result


def cell_material(world,x,y):
    name=world['cells'][y][x]
    if name=='land' and [x,y] in semantic_regions(world).get('shore',[]):return 'shore'
    return name


def make_guide(world):
    im=Image.new('RGB',GUIDE_SIZE,(29,42,39));px=im.load()
    ox=(GUIDE_SIZE[0]-world['width']*CELL_PX)//2;oy=(GUIDE_SIZE[1]-world['height']*CELL_PX)//2
    colors=_cell_colors(world)
    for (x,y),color in colors.items():
        x0=ox+x*CELL_PX;y0=oy+y*CELL_PX
        for yy in range(y0,y0+CELL_PX):
            for xx in range(x0,x0+CELL_PX):px[xx,yy]=color
    wx0=ox+WALL_BLOCK[0]*CELL_PX;wy0=oy+WALL_BLOCK[1]*CELL_PX
    for yy in range(wy0,wy0+CELL_PX):
        for xx in range(wx0,wx0+CELL_PX):px[xx,yy]=COLORS['wall']
    sx0=ox+STAIR_BLOCK[0]*CELL_PX;sy0=oy+STAIR_BLOCK[1]*CELL_PX
    for yy in range(sy0,sy0+CELL_PX):
        for xx in range(sx0,sx0+CELL_PX):px[xx,yy]=COLORS['stairs']
    out=io.BytesIO();im.save(out,format='PNG',optimize=False);return out.getvalue()

def bind_source(world,source):
    try:
        im=Image.open(io.BytesIO(source))
        if im.format!='PNG':raise ValueError('provider output must be PNG canvas')
        im.load();im=im.convert('RGB')
    except Exception as e:raise ValueError('painted terrain image invalid') from e
    if im.size!=GUIDE_SIZE:raise ValueError('painted terrain canvas dimensions mismatch')
    ox=(GUIDE_SIZE[0]-world['width']*CELL_PX)//2;oy=(GUIDE_SIZE[1]-world['height']*CELL_PX)//2
    regions=semantic_regions(world)
    reps={name:coords[0] for name,coords in regions.items() if coords}
    regions['wall']=[list(WALL_BLOCK)];reps['wall']=list(WALL_BLOCK)
    reps['stairs']=list(STAIR_BLOCK)
    return {'mode':'flat-terrain-image/1','source_sha256':digest(source),'layout_revision':world['revision'],
        'source_size':list(im.size),'grid':{'origin':[ox,oy],'cell_px':CELL_PX,'width':world['width'],'height':world['height']},
        'regions':regions,'representatives':reps,'shore_cells':regions.get('shore',[]),
        'semantic_contract':'frozen layout grid; no props/structures; semantics come only from layout data'}

class TerrainPixels:
    def __init__(self,source,binding,world):
        if binding.get('mode')!='flat-terrain-image/1' or binding.get('source_sha256')!=digest(source):
            raise ValueError('painted source binding mismatch')
        self.im=np.asarray(Image.open(io.BytesIO(source)).convert('RGB'));self.binding=binding;self.world=world
        if (self.im.shape[1],self.im.shape[0])!=GUIDE_SIZE:raise ValueError('painted terrain canvas mismatch')
        self.grid=binding['grid'];self.ox,self.oy=self.grid['origin'];self.cell=self.grid['cell_px']
        self.same_world=(binding['layout_revision']==world['revision'])
        if self.same_world and (self.grid['width']!=world['width'] or self.grid['height']!=world['height']):raise ValueError('painted grid mismatch')
    def _sample_cell(self,name,u,v):
        if name=='stairs':
            # Stair treads always draw from the reserved stone block (the
            # painter cannot hold per-cell stair categories reliably).
            bx,by=self.binding['representatives'].get('stairs',STAIR_BLOCK)
            cx=np.full(np.shape(u),bx,dtype=int);cy=np.full(np.shape(v),by,dtype=int)
            fx=np.mod(np.asarray(u),1.0);fy=np.mod(np.asarray(v),1.0)
        elif self.same_world:
            cx=np.floor(np.asarray(u)).astype(int);cy=np.floor(np.asarray(v)).astype(int)
            fx=np.mod(np.asarray(u),1.0);fy=np.mod(np.asarray(v),1.0)
        else:
            if name=='wall':name='square' if 'square' in self.binding['representatives'] else 'plateau' if 'plateau' in self.binding['representatives'] else 'land'
            if name not in self.binding['representatives']:name=next(iter(self.binding['representatives']))
            cx=np.full(np.shape(u),self.binding['representatives'][name][0],dtype=int)
            cy=np.full(np.shape(v),self.binding['representatives'][name][1],dtype=int)
            fx=np.mod(np.asarray(u),1.0);fy=np.mod(np.asarray(v),1.0)
        px=self.ox+cx*self.cell+np.clip((fx*self.cell).astype(int),0,self.cell-1)
        py=self.oy+cy*self.cell+np.clip((fy*self.cell).astype(int),0,self.cell-1)
        px=np.clip(px,0,self.im.shape[1]-1);py=np.clip(py,0,self.im.shape[0]-1)
        return self.im[py,px].copy(),np.stack([px,py],axis=-1).astype('<i2')
    def sample(self,name,u,v):
        if name=='land' and 'shore' in self.binding['regions']:
            landx=np.floor(np.asarray(u)).astype(int);landy=np.floor(np.asarray(v)).astype(int)
            shores={tuple(q) for q in self.binding['shore_cells']}
            shoremask=np.vectorize(lambda x,y:(int(x),int(y)) in shores,otypes=[bool])(landx,landy)
            if np.any(shoremask):
                regular,regular_xy=self._sample_cell(name,u,v)
                shore,shore_xy=self._sample_cell('shore',u,v)
                regular[shoremask]=shore[shoremask];regular_xy[shoremask]=shore_xy[shoremask]
                return regular,regular_xy
        return self._sample_cell(name,u,v)
    def sample_wall(self,name,x,y,u,v,side):
        # Exposed height faces inherit texture from the adjacent frozen ground
        # cell. The vertical axis sweeps the whole 48px block (steps of one
        # texture pixel per screen row); mod-1 froze one row per column and
        # produced comb-like stripes on every vertical face.
        fx=np.mod(np.asarray(u),1.0);fy=np.mod(np.asarray(v),float(self.cell))/self.cell
        bx,by=self.binding['representatives'].get('wall',WALL_BLOCK)
        cx=np.full(np.shape(fx),bx,dtype=int);cy=np.full(np.shape(fy),by,dtype=int)
        px=self.ox+cx*self.cell+np.clip((fx*self.cell).astype(int),0,self.cell-1)
        py=self.oy+cy*self.cell+np.clip((fy*self.cell).astype(int),0,self.cell-1)
        return self.im[py,px].copy(),np.stack([px,py],axis=-1).astype('<i2')

WALL_TEXTURE_ALGORITHM='reserved-wall-block/2'

def prompt(world,correction=None):
    names=sorted({v for row in world['cells'] for v in row})
    categories=', '.join(name+': '+{"land":"lush green meadow with tiny grass tufts and occasional small flowers, texture only","path":"warm earth path with soft irregular edges","square":"flat stone paving","plateau":"lush green grass top matching the meadow","stairs":"flat pale stone tread material only","water":"flat water surface, calm, no pads, no plants, no basin or depression"}[name] for name in names)
    if 'water' in names:categories+=', shore: narrow flat sandy bank in land cells immediately adjacent to the water patch'
    return ('Image 1 is the frozen, exact, FLAT ORTHOGRAPHIC terrain layout guide. Repaint ONLY each existing cell as coherent detailed pixel-art ground texture. Preserve every semantic cell location and exact 48x48 cell grid; never move, merge, split, recolor or change category boundaries. '
        'The reserved WALL block in the left margin is face-on vertical stone brick wall texture: neat grey bricks with visible mortar lines, no perspective. The reserved STONE block below it is flat pale stone tread texture for stair treads. '
        'This is a top-down flat terrain atlas for later deterministic isometric projection, NOT an isometric scene. No perspective, buildings, architecture fragments, building walls, roofs, windows, trees, bushes, houses, props, fences, stairs, risers, cliffs, actors, text, shadows or objects — never as objects and never as texture hints, even if the style reference shows them. Stair cells receive only flat stone floor texture; all stair treads, risers and walls are rendered later from frozen layout data. Keep every category strictly inside its exact guide cells. '
        'Image 2 is STYLE ONLY (palette and surface treatment), never geometry authority. Frozen material categories: '+categories+'. Output lossless PNG exactly '+str(GUIDE_SIZE[0])+'x'+str(GUIDE_SIZE[1])+' with same grid, margins and canvas.'+
        ((' CORRECTIVE REPAINT: '+correction+' Fix ONLY these named cells with their exact listed category material; keep every other cell identical.') if correction else ''))

def validate_painted_source(world,binding,source):
    """Validate that every layout cell retains its original categorical material."""
    t=TerrainPixels(source,binding,world);checked=0
    palette=np.asarray([v for k,v in COLORS.items() if k!='wall'],dtype=np.float32);names=list(COLORS)
    for y,row in enumerate(world['cells']):
        for x,name in enumerate(row):
            if name=='stairs':
                checked+=CELL_PX*CELL_PX;continue
            x0=t.ox+x*CELL_PX;y0=t.oy+y*CELL_PX
            block=t.im[y0:y0+CELL_PX,x0:x0+CELL_PX].reshape(-1,3).astype(np.float32)
            near=np.argmin(np.linalg.norm(block[:,None,:]-palette[None,:,:],axis=2),axis=1)
            checked+=len(block)
            counts=np.bincount(near,minlength=len(palette))
            expected=_cell_colors(world)[x,y]
            expected_index=int(np.argmin(np.linalg.norm(palette-np.asarray(expected,dtype=np.float32),axis=1)))
            keys=[k for k in COLORS if k!='wall']
            fam={n:('water' if n=='water' else 'green' if n in ('land','plateau') else 'warm') for n in keys}
            family=fam[keys[expected_index]]
            share=sum(int(counts[i]) for i,k in enumerate(keys) if fam[k]==family)
            rival=max((sum(int(counts[i]) for i,k in enumerate(keys) if fam[k]==other) for other in ['water','green','warm'] if other!=family),default=0)
            if share<=rival:
                semantic='shore' if name=='land' and expected==COLORS['shore'] else name
                raise ValueError('painted semantic alignment mismatch: '+semantic+' at '+str([x,y]))
    return {'checked_probes':checked,'checked_cells':world['width']*world['height'],'layout_revision':world['revision'],'source_sha256':binding['source_sha256'],'mapping':'frozen-cell-grid/palette-family-plurality/v6'}

def verify_alignment(world,binding,source):return bool(validate_painted_source(world,binding,source))
