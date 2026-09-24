"""Generated-material raster; geometry equations exactly retained from multilevel build."""
import numpy as np
from hybrid_layout import faces
from hybrid_painted_terrain import cell_material

def _transition_pairs(w):
    return {tuple(sorted(map(tuple,pair))) for pair in w['transitions']}

def visible_faces(w):
    """Cliff faces only where no stair transition runs; transition edges are
    covered by the stair treads/risers instead of an exposed vertical seam."""
    pairs=_transition_pairs(w);out=[]
    for f in faces(w):
        x,y=f['cell'];dx,dy=(1,0) if f['side']=='east' else (0,1)
        if tuple(sorted([(x,y),(x+dx,y+dy)])) in pairs:continue
        out.append(f)
    return out

def _stair_run(w,x,y):
    """(zl,zh,high_dir,low_dir) for a stair cell whose transitions change height."""
    z=w['heights'][y][x];neighbors=[]
    for pair in w['transitions']:
        a,b=pair
        if (a[0],a[1])==(x,y):n=(b[0],b[1])
        elif (b[0],b[1])==(x,y):n=(a[0],a[1])
        else:continue
        neighbors.append(((n[0]-x,n[1]-y),w['heights'][n[1]][n[0]]))
    if not neighbors:return None
    levels=[z]+[h for _,h in neighbors];zh=max(levels);zl=min(levels)
    if zh==zl:return None
    highs=sorted([d for d,h in neighbors if h==zh]);lows=sorted([d for d,h in neighbors if h==zl])
    if zh>z:high=highs[0];low=lows[0] if lows else (-high[0],-high[1])
    else:low=lows[0];high=highs[0] if highs else (-low[0],-low[1])
    return zl,zh,high,low

def render(w,materials):
    WIDTH,HEIGHT=w['canvas'];ORIGIN=w['origin']
    image=np.zeros((HEIGHT,WIDTH,4),dtype='uint8');image[:]=[28,43,40,255]
    depth=np.full((HEIGHT,WIDTH),-1000,dtype='<f4');source=np.full((HEIGHT,WIDTH,2),-1,dtype='<i2');flags=np.zeros((HEIGHT,WIDTH),dtype='uint8')
    yy,xx=np.mgrid[:HEIGHT,:WIDTH];sx=(xx+.5-ORIGIN[0])/24;sy=yy+.5-ORIGIN[1]
    def paint(mask,d,rgb,xy,flag=1):
        hit=mask&(d>depth);image[hit,:3]=rgb[hit];depth[hit]=d[hit];source[hit]=xy[hit];flags[hit]=flag
    for y,row in enumerate(w['heights']):
        for x,z in enumerate(row):
            mat=w['cells'][y][x]
            name=cell_material(w,x,y)
            run=_stair_run(w,x,y) if mat=='stairs' else None
            if run:
                # Two stepped treads ascend across the tile from the low edge
                # to the high edge; the top tread is flush with the plateau.
                zl,zh,high,low=run;steps=2
                axis='x' if low[0] else 'y'
                edge=(x+1) if (axis=='x' and low==(1,0)) else (x if axis=='x' else (y+1 if low==(0,1) else y))
                step=-1 if (axis=='x' and low==(1,0)) or (axis=='y' and low==(0,1)) else 1
                for i in range(1,steps+1):
                    zt=zl+(zh-zl)*i//steps;z0=zl+(zh-zl)*(i-1)//steps
                    a=edge+step*(i-1)/steps;b=edge+step*i/steps;u0,u1=(a,b) if a<b else (b,a)
                    summ=(sy+zt)/12;wx=(summ+sx)/2;wy=(summ-sx)/2
                    strip=((wx>=u0)&(wx<u1)) if axis=='x' else ((wy>=u0)&(wy<u1))
                    mask=(wx>=x)&(wx<x+1)&(wy>=y)&(wy<y+1)&strip
                    rgb,xy=materials.sample(name,wx,wy)
                    paint(mask,summ,rgb,xy)
                    # Visible flank skirt: closes the void under raised treads.
                    if axis=='y':
                        if x+1>=w['width'] or w['cells'][y][x+1]!='stairs':
                            wx2=np.full_like(sx,x+1);wy2=wx2-sx;u=wy2;m2=(wy2>=u0)&(wy2<u1)
                        else:m2=None
                    else:
                        if y+1>=w['height'] or w['cells'][y+1][x]!='stairs':
                            wy2=np.full_like(sx,y+1);wx2=wy2+sx;u=wx2;m2=(wx2>=u0)&(wx2<u1)
                        else:m2=None
                    if m2 is not None:
                        summ2=wx2+wy2;hz=12*summ2-sy
                        m2=m2&(hz>=zl)&(hz<zt)
                        if hasattr(materials,'sample_wall'):rgb2,xy2=materials.sample_wall(name,x,y,u,-hz,'east' if axis=='y' else 'south')
                        else:rgb2,xy2=materials.sample(name,u,-hz)
                        rgb2=(rgb2.astype('uint16')*218//255).astype('uint8')
                        paint(m2,summ2,rgb2,xy2,2)
                    if low in [(0,1),(1,0)]:
                        if axis=='y':wy2=np.full_like(sx,a);wx2=wy2+sx;u=wx2
                        else:wx2=np.full_like(sx,a);wy2=wx2-sx;u=wy2
                        summ2=wx2+wy2;hz=12*summ2-sy
                        m2=((wx2>=x)&(wx2<x+1)) if axis=='y' else ((wy2>=y)&(wy2<y+1))
                        m2=m2&(hz>=z0)&(hz<zt)
                        if hasattr(materials,'sample_wall'):rgb2,xy2=materials.sample_wall(name,x,y,u,-hz,'south' if axis=='y' else 'east')
                        else:rgb2,xy2=materials.sample(name,u,-hz)
                        rgb2=(rgb2.astype('uint16')*218//255).astype('uint8')
                        paint(m2,summ2,rgb2,xy2,2)
                continue
            summ=(sy+z)/12;wx=(summ+sx)/2;wy=(summ-sx)/2
            mask=(wx>=x)&(wx<x+1)&(wy>=y)&(wy<y+1)
            rgb,xy=materials.sample(name,wx,wy)
            paint(mask,summ,rgb,xy)
    for f in visible_faces(w):
        x,y=f['cell'];side=f['side'];z=f['height'];lo=f['bottom']
        if side not in ['east','south']:continue
        if side=='east':
            wx=np.full_like(sx,x+1);wy=wx-sx;u=wy;mask=(wy>=y)&(wy<y+1)
        else:
            wy=np.full_like(sx,y+1);wx=wy+sx;u=wx;mask=(wx>=x)&(wx<x+1)
        summ=wx+wy;hz=12*summ-sy;mask=mask&(hz>=lo)&(hz<z)
        if hasattr(materials,'sample_wall'):rgb,xy=materials.sample_wall('wall',x,y,u,-hz,side)
        else:rgb,xy=materials.sample('wall',u,-hz)
        if side=='east':rgb=(rgb.astype('uint16')*218//255).astype('uint8')
        paint(mask,summ,rgb,xy,2 if side=='east' else 1)
    return image,depth,source,flags

class PreviewMaterials:
 """Technical colors ONLY; never a generated terrain substitute."""
 colors={'land':[92,139,88],'water':[54,110,161],'path':[176,143,94],'square':[189,183,155],'plateau':[131,145,111],'stairs':[206,180,122],'wall':[99,91,82],'shore':[194,169,119]}
 def sample(self,name,u,v):
  rgb=np.empty((*u.shape,3),dtype='uint8');rgb[:]=self.colors[name]
  return rgb,np.full((*u.shape,2),-1,dtype='<i2')
