"""Extract measured original-image pixels. Polygons are manual authoring work.

No independent tree regeneration. Two additional instances intentionally reuse
these newly generated host-owned trees; record that the whole-image model omitted them.
"""
from pathlib import Path
from PIL import Image, ImageDraw, ImageChops, ImageFilter
import json
A=Path(__file__).parent/'art'
src=Image.open(A/'scene-second.png').convert('RGBA')
shapes={
 'west':{'root':[45,130],'points':[(8,60),(16,45),(25,41),(29,32),(44,29),(55,38),(69,39),(78,48),(85,66),(84,82),(73,97),(56,102),(54,117),(58,123),(66,130),(61,134),(49,132),(40,138),(31,135),(34,126),(38,115),(37,99),(23,94),(12,79)]},
 'north':{'root':[126,88],'points':[(92,30),(102,23),(99,17),(106,9),(116,6),(123,1),(136,7),(145,15),(151,19),(150,30),(145,37),(134,46),(132,61),(130,70),(135,78),(144,85),(139,90),(129,88),(124,94),(119,88),(110,92),(110,87),(119,74),(120,66),(116,61),(99,57),(91,47)]},
 'east':{'root':[162,104],'points':[(137,29),(145,23),(160,25),(169,32),(179,31),(186,42),(190,56),(187,72),(177,78),(169,79),(167,89),(173,99),(181,102),(176,107),(167,105),(160,110),(153,108),(146,110),(145,106),(154,93),(155,81),(144,76),(133,66),(130,52),(134,42)]},
 'far':{'root':[219,136],'points':[(188,76),(192,65),(202,60),(207,50),(220,44),(233,48),(242,57),(248,64),(252,81),(248,91),(236,101),(226,102),(225,117),(229,127),(238,136),(233,141),(223,138),(219,144),(212,140),(205,143),(203,138),(212,125),(214,109),(212,104),(195,97),(186,87)]},
}
union=Image.new('L',src.size)
for name,item in shapes.items():
 mask=Image.new('L',src.size);ImageDraw.Draw(mask).polygon(item['points'],fill=255)
 # Exact flat exterior is not part of any tree. Do not erase similarly colored
 # dark internal foliage; only this source's corner-background RGB is removed.
 bg=src.getpixel((0,0))[:3]
 mask.putdata([0 if p[:3]==bg else a for p,a in zip(src.getdata(),mask.getdata())])
 union=ImageChops.lighter(union,mask)
 box=mask.getbbox();box=(box[0]-2,box[1]-2,box[2]+2,box[3]+2)
 cut=src.copy();cut.putalpha(mask);cut=cut.crop(box);cut.save(A/f'tree-source-{name}.png')
 item['box']=box;item['anchor']=[(item['root'][0]-box[0])/cut.width,(item['root'][1]-box[1])/cut.height]
 mask.save(A/f'tree-mask-{name}.png')
union.save(A/'tree-union-mask.png')
(A/'layer-measurements.json').write_text(json.dumps(shapes,indent=2)+'\n',encoding='utf8')
board=Image.new('RGBA',(320,160),'#bb87a4')
for i,name in enumerate(shapes):board.alpha_composite(Image.open(A/f'tree-source-{name}.png'),(i*80,0))
board.resize((960,480),Image.Resampling.NEAREST).save(A/'extraction-inspection.png')
print(json.dumps({'sourceTrees':len(shapes),'method':'four manually traced polygons, original pixels, no regeneration'}))
