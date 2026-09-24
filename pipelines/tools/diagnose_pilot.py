from pathlib import Path
from PIL import Image,ImageDraw
import numpy as np,json
from PIL import ImageFilter
from collections import deque
out=Path('evidence/paid-pilot');im=Image.open(out/'original.png').convert('RGB');a=np.array(im).astype(float);r,g,b=a.transpose(2,0,1)
# Explicit color proxies; never a general semantic classifier.
water=(b>r*1.2)&(g>r*1.15)&(b>85)&(g>85)
path=(r>g*1.10)&(g>b*1.2)&(r>140)&(g>100)
land=np.linalg.norm(a-a[0,0],axis=2)>35
def largest(m):
 m=np.array(Image.fromarray((m*255).astype('uint8')).filter(ImageFilter.MaxFilter(7)).filter(ImageFilter.MinFilter(7)))>0
 seen=np.zeros_like(m);best=[]
 for y,x in zip(*np.where(m)):
  if seen[y,x]:continue
  q=deque([(y,x)]);seen[y,x]=True;comp=[]
  while q:
   yy,xx=q.popleft();comp.append((yy,xx))
   for dy,dx in [(0,1),(0,-1),(1,0),(-1,0)]:
    ny,nx=yy+dy,xx+dx
    if 0<=ny<m.shape[0] and 0<=nx<m.shape[1] and m[ny,nx] and not seen[ny,nx]:seen[ny,nx]=True;q.append((ny,nx))
  if len(comp)>len(best):best=comp
 result=np.zeros_like(m)
 for y,x in best:result[y,x]=True
 return result
water=largest(water);path=largest(path);land=largest(land)
stats={}
for name,mask in [('water',water),('path',path),('land',land)]:
 y,x=np.where(mask);stats[name]={'pixels':len(x),'bbox':[int(x.min()),int(y.min()),int(x.max()),int(y.max())],'centroid':[float(x.mean()),float(y.mean())]}
 Image.fromarray((mask*255).astype('uint8')).save(out/(name+'-proxy.png'))
# Fit the two long path edges from per-x quantiles in central segment, avoiding end margins.
for name,mask in [('path',path)]:
 pts=[]
 for x in range(650,1350,10):
  ys=np.where(mask[:,x])[0]
  if len(ys)>20:pts.append([x,float(np.percentile(ys,3)),float(np.percentile(ys,97))])
 pts=np.array(pts);stats['path_line_fits']={'upper':np.polyfit(pts[:,0],pts[:,1],1).tolist(),'lower':np.polyfit(pts[:,0],pts[:,2],1).tolist()}
(out/'raw-diagnostics.json').write_text(json.dumps(stats,indent=2));print(json.dumps(stats))
