"""Explicit scalar registration from observed source frame corners; no warp or masks."""
import os,json,io
from pathlib import Path
import httpx,numpy as np
from PIL import Image,ImageDraw,ImageFilter
out=Path(os.environ.get('EVIDENCE','evidence/urban-pilot'));c=httpx.Client(base_url=os.environ.get('BASE_URL','http://127.0.0.1:53047'),timeout=60)
old=json.loads((out/'candidate.json').read_text());v=json.loads((out/'layout-response.json').read_text());l=v['layout'];p=l['projection']
# Source was visually inspected first. >80 brightness separates light ground from black backdrop.
a=np.array(Image.open(out/'original.png').convert('RGB'));y,x=np.where(a.max(2)>80)
source=np.array([[x[i],y[i]] for i in [np.argmin(x),np.argmin(y),np.argmax(x),np.argmax(y)]],dtype=float)
guide=np.array([[24,192],[360,24],[744,216],[408,384]],dtype=float)
g=guide-guide.mean(0);s=source-source.mean(0);k=float((g*s).sum()/(g*g).sum());t=source.mean(0)-k*guide.mean(0)
body={'scale':1/k,'translation':(-t/k).tolist(),'notes':'Uniform least squares from four observed outer ground extrema on original (>80 RGB max against black backdrop), visually checked. Source landmarks '+str(source.tolist())+' versus canonical '+str(guide.tolist())+'. One scale only, no axis warp, no collision changes; residuals retained and interior materials assessed independently.'}
evidence={'source_corners':source.tolist(),'canonical_corners':guide.tolist(),'source_per_canonical_scale':k,'source_translation':t.tolist(),'canonical_residual_vectors':((source-(guide*k+t))/k).tolist(),'method':'four frame landmarks uniform least squares, not semantic alignment proof'}
(out/'registration-evidence.json').write_text(json.dumps(evidence,indent=2));(out/'registration-request.json').write_text(json.dumps(body,indent=2))
r=c.post('/api/terrain/'+old['id']+'/register',json=body);r.raise_for_status();reg=r.json();assert c.get('/api/terrain/'+reg['id']).json()==reg
(out/'registered-candidate.json').write_text(json.dumps(reg,indent=2));raw=c.get('/api/terrain/'+reg['id']+'/preview.png').content;(out/'registered.png').write_bytes(raw)
img=Image.open(io.BytesIO(raw)).convert('RGBA');rgb=np.array(img)[:,:,:3].astype(int);red,green,blue=rgb[:,:,0],rgb[:,:,1],rgb[:,:,2]
# Separately defined urban proxies, NOT the forest water heuristic. Green first.
plant=(green>red+10)&(green>blue+15)&(green>65)
street=(abs(red-green)<22)&(blue>=red-8)&(red>70)&(red<185)&~plant
sidewalk=(red>145)&(green>130)&(red>blue+18)&~plant
proxies={'planting':plant,'street':street,'sidewalk':sidewalk};masks={}
for name in ('planting','street','sidewalk','routes'):
 url='/api/layouts/'+old['layout_revision']+'/artifacts/masks/'+('material-' if name!='routes' else '')+name+'.png'
 masks[name]=np.array(Image.open(io.BytesIO(c.get(url).content)))>0
stats={'method':'Observed source-color thresholds applied to direct-original scalar export. Green first, then neutral gray and warm light paving; uncertain outlines/shadows unclassified. Proxies are not semantic truth.','materials':{},'canonical_collision_unchanged':True}
for m,proxy in proxies.items():
 plan=masks[m];stats['materials'][m]={'planned_pixels':int(plan.sum()),'proxy_pixels':int(proxy.sum()),'proxy_inside_plan':int((proxy&plan).sum()),'proxy_outside_plan':int((proxy&~plan).sum()),'planned_proxy_agreement':float((proxy&plan).sum()/plan.sum())}
route=masks['routes'];stats['sidewalk_clearance']={'required_route_pixels':int(route.sum()),'route_green_proxy_pixels':int((route&plant).sum()),'route_street_proxy_pixels':int((route&street).sum()),'route_warm_paving_proxy_pixels':int((route&sidewalk).sum())}
# Full stationary actor footprints at ALL canonical safe sidewalk centers, separate from one goal route.
yy,xx=np.indices(plant.shape);dx=(xx+.5-p['origin_px'][0])/p['column_basis_px'][0];dy=(yy+.5-p['origin_px'][1])/p['column_basis_px'][1];cc=(dx+dy)/2;rr=(dy-dx)/2
hits=[]
for cx,cy in v['validation']['safe_cells']:
 if l['materials'][cy][cx]!='sidewalk':continue
 footprint=(abs(cc-cx-.5)<l['actor_width']/2)&(abs(rr-cy-.5)<l['actor_width']/2)
 n=int((footprint&plant).sum())
 if n:hits.append({'cell':[cx,cy],'green_proxy_pixels':n})
stats['sidewalk_clearance']['safe_sidewalk_actor_footprints_with_green_overlap']=hits
(out/'registered-local-checks.json').write_text(json.dumps(stats,indent=2))
over=np.array(img)
for m,color in [('street',[80,190,255,255]),('planting',[255,80,255,255]),('routes',[255,70,40,255])]:
 mask=masks[m];er=np.array(Image.fromarray((mask*255).astype('uint8')).filter(ImageFilter.MinFilter(3)))>0;over[mask&~er]=color
Image.fromarray(over).save(out/'registered-boundary-diagnostic.png')
board=Image.new('RGB',(1536,440),'#172025');guideim=Image.open(out/'guide.png').convert('RGBA');board.paste(guideim,(0,32),guideim);board.paste(Image.fromarray(over),(768,32));d=ImageDraw.Draw(board);d.text((12,10),'URBAN GUIDE: geometry only',fill='white');d.text((780,10),'GENERATED: blue street / magenta planting / red route boundaries',fill='white');board.save(out/'guide-vs-registered.png')
print(json.dumps({'candidate':reg['id'],'registration':evidence,'local':stats},indent=2))
