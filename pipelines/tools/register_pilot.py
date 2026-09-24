"""One explicit pilot calibration; no candidate-dependent masks or artwork changes."""
from pathlib import Path
import json,io
import httpx,numpy as np
from PIL import Image,ImageDraw,ImageFilter
out=Path('evidence/paid-pilot');c=httpx.Client(base_url='http://127.0.0.1:33009',timeout=60)
assert c.get('/api/generation/status').status_code==200
old=json.loads((out/'candidate.json').read_text());rid=old['layout_revision']
# Manually inspected ground-corner baselines (not grass tips); independent pond check follows.
# Source ~= guide * 2.36 + (80,53), ONE common scale. No corner-to-corner per-axis warp.
body={'scale':1/2.36,'translation':[-80/2.36,-53/2.36],'notes':'Operator calibration from inspected diamond baseline corners: source ~= guide*2.36+(80,53). Ground baseline landmarks approximately guide [360,24],[24,192],[408,384],[744,216] -> source [929,105],[160,506],[1025,962],[1820,561]. Uniform least-rounded calibration, not exact image alignment. Independent pond/path proxy and model review required. No collision changes or generated repaint.'}
r=c.post('/api/terrain/'+old['id']+'/register',json=body);r.raise_for_status();reg=r.json()
assert c.get('/api/terrain/'+reg['id']).json()==reg
(out/'registration-request.json').write_text(json.dumps(body,indent=2));(out/'registered-candidate.json').write_text(json.dumps(reg,indent=2))
raw=c.get('/api/terrain/'+reg['id']+'/preview.png').content;(out/'registered.png').write_bytes(raw)
img=Image.open(io.BytesIO(raw)).convert('RGBA');guide=Image.open(out/'guide.png').convert('RGBA')
water=np.array(Image.open(io.BytesIO(c.get('/api/layouts/'+rid+'/artifacts/masks/material-water.png').content)))>0
route=np.array(Image.open(io.BytesIO(c.get('/api/layouts/'+rid+'/artifacts/masks/routes.png').content)))>0
# Same explicit registration applied to independent observed source-water color proxy.
srcmask=Image.open(out/'water-proxy.png')
scale=body['scale'];tx,ty=body['translation'];proxy=np.array(srcmask.transform(img.size,Image.Transform.AFFINE,(1/scale,0,-tx/scale,0,1/scale,-ty/scale),resample=Image.Resampling.NEAREST))>0
stats={'method':'largest closed blue/cyan source color component mapped by uniform registration; proxy NOT automatic semantic truth','water_proxy_pixels':int(proxy.sum()),'proxy_inside_planned_water':int((proxy&water).sum()),'proxy_outside_planned_water':int((proxy&~water).sum()),'proxy_on_required_routes':int((proxy&route).sum()),'planned_water_pixels':int(water.sum()),'local_review':'needs_attention','canonical_collision_unchanged':True}
layout=json.loads((out/'layout-response.json').read_text())['layout'];p=layout['projection'];cells=[]
for y in range(layout['height']):
 for x in range(layout['width']):
  if layout['materials'][y][x]=='water':continue
  px=p['origin_px'][0]+(x+.5)*p['column_basis_px'][0]+(y+.5)*p['row_basis_px'][0];py=p['origin_px'][1]+(x+.5)*p['column_basis_px'][1]+(y+.5)*p['row_basis_px'][1]
  if proxy[int(py),int(px)]:cells.append([x,y])
stats['planned_dry_centers_in_blue_proxy']=cells
(out/'registered-local-checks.json').write_text(json.dumps(stats,indent=2))
# Cyan = authoritative water boundary, magenta = route boundary; no hiding candidate pixels.
over=img.copy();a=np.array(over)
for mask,color in [(water,[0,255,255,255]),(route,[255,64,230,255])]:
 er=np.array(Image.fromarray((mask*255).astype('uint8')).filter(ImageFilter.MinFilter(3)))>0;a[mask&~er]=color
over=Image.fromarray(a);over.save(out/'registered-boundary-diagnostic.png')
board=Image.new('RGB',(1536,440),'#132b32');board.paste(guide,(0,32),guide);board.paste(over,(768,32),over);d=ImageDraw.Draw(board);d.text((10,10),'CANONICAL GUIDE: geometry authority',fill='white');d.text((778,10),'REGISTERED OUTPUT: cyan water edge, pink route edge; not approved',fill='white');board.save(out/'guide-vs-registered.png')
print(json.dumps({'candidate':reg['id'],'checks':stats}))
