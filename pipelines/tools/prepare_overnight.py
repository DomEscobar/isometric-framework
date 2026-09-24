"""Offline reference lineage and new technical layout; NEVER calls paid providers."""
import sys, json, io, hashlib
from pathlib import Path
from decimal import Decimal
from PIL import Image,ImageDraw
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from artifacts import canonical,digest,export_files
from layout_core import generate,validate
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'evidence/overnight-two-styles';OUT.mkdir(exist_ok=True)
refs=[('warm','/root/.hermes/cache/images/img_6c8d5452390d.jpg',{'path':[294,195,70,26],'grass':[306,337,30,14],'soil':[103,126,46,26]}),('fantasy','/root/.hermes/cache/images/img_632abdd839ed.jpg',{'path':[578,448,64,48],'grass':[556,226,32,28],'soil':[514,504,48,34]})]
lineage=[]
for label,source,crops in refs:
 d=OUT/label;d.mkdir(exist_ok=True);raw=Path(source).read_bytes();(d/'reference-original.jpg').write_bytes(raw)
 im=Image.open(io.BytesIO(raw)).convert('RGB');im.save(d/'reference-decoded.png');png=(d/'reference-decoded.png').read_bytes();decoded=Image.open(io.BytesIO(png)).convert('RGB');assert im.tobytes()==decoded.tobytes()
 rec=dict(style=label,jpeg_sha256=digest(raw),png_sha256=digest(png),decoded_rgb_sha256=digest(im.tobytes()),size=im.size,pixel_equal=True,decode='Pillow JPEG to RGB once; lossless PNG; no recovered JPEG information',crops=crops)
 board=Image.new('RGB',(720,180),'#1b252b');draw=ImageDraw.Draw(board)
 for i,(material,box) in enumerate(crops.items()):
  x,y,w,h=box;crop=im.crop((x,y,x+w,y+h));crop.save(d/(material+'-crop.png'));board.paste(crop.resize((w*2,h*2),Image.Resampling.NEAREST),(i*240,35));draw.text((i*240+4,10),material+' native crop shown x2',fill='white')
 board.save(d/'material-crops.png');(d/'reference-lineage.json').write_bytes(canonical(rec));lineage.append(rec)
params=dict(width=14,height=14,seed=2026092101,tile_width=48,density=1,actor_width=.8,kind='plaza',path='cross',trees=0,houses=0,brief='')
for label,seed in [('common',2026092101),('second-seed-free-only',2026092102)]:
 params['seed']=seed;layout=generate(params);assert validate(layout)['valid'];files=export_files(layout);d=OUT/label;d.mkdir(exist_ok=True)
 (d/'request.json').write_bytes(canonical(params));(d/'layout.json').write_bytes(canonical(layout));(d/'clean-guide.png').write_bytes(files['clean-guide.png']);(d/'collision.json').write_bytes(files['collision.json']);(d/'validation.json').write_bytes(canonical(validate(layout)))
fx=dict(checked_utc='2026-09-21',source='https://www.ecb.europa.eu/stats/policy_and_exchange_rates/euro_reference_exchange_rates/html/eurofxref-graph-usd.en.html',search_result_date='2026-09-21',search_usd_per_eur='1.1490',extracted_page_latest_visible_date='2026-09-15',extracted_usd_per_eur='1.1539',caveat='Search and extracted calendar are temporally inconsistent; no execution FX quote claimed. Both observations support the very conservative bound.',conservative_eur_per_usd='1.25',extra_fees_eur='2.50',shared_usd_cap='10.00',max_conservative_eur=str(Decimal('10')*Decimal('1.25')+Decimal('2.50')),search_implied_eur_per_usd=str(Decimal(1)/Decimal('1.1490')),no_holds_released=True)
assert Decimal(fx['search_implied_eur_per_usd'])<Decimal('1.25');assert Decimal(fx['max_conservative_eur'])<=15
(OUT/'fx-budget.json').write_bytes(canonical(fx));print(json.dumps(dict(references=lineage,common_revision=digest((OUT/'common/layout.json').read_bytes()),fx=fx),indent=2))
