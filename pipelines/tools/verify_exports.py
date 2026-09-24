"""Exercise the actual local API, save three distinct exports, verify downloaded bytes."""
import hashlib
import io
import json
from pathlib import Path
import urllib.request
import zipfile
import numpy as np
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
BASE='http://127.0.0.1:8766'
OUT=ROOT/'evidence'/'exports-final'
EXAMPLES=[('meadow',{'brief':'Wiese; Weg West-Ost; 2 Bäume','seed':3}),
          ('pond',{'brief':'Teich im Nordosten; Weg West-Ost; 1 Haus; 3 Bäume','seed':19}),
          ('plaza',{'brief':'Platz; Weg Kreuz; 4 Bäume','seed':81})]


def get(route):
    return urllib.request.urlopen(BASE+route).read()


def verify_zip(raw):
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        assert archive.testzip() is None
        checks=json.loads(archive.read('checksums.json'))
        assert set(checks)==set(archive.namelist())-{'checksums.json'}
        assert all(hashlib.sha256(archive.read(name)).hexdigest()==sha for name,sha in checks.items())
        layout=json.loads(archive.read('layout.json'))
        guide=Image.open(io.BytesIO(archive.read('clean-guide.png')))
        masks=[np.asarray(Image.open(io.BytesIO(archive.read('masks/material-'+name+'.png'))),dtype=np.uint16) for name in ['grass','soil','path','water']]
        assert np.array_equal(sum(masks),np.asarray(guide.getchannel('A')))
        regions=json.loads(archive.read('regions.json'))
        cells=[tuple(cell) for region in regions for cell in region['cells']]
        assert len(cells)==len(set(cells))==layout['width']*layout['height']
        rmasks=[np.asarray(Image.open(io.BytesIO(archive.read('masks/'+region['id']+'.png'))),dtype=np.uint16) for region in regions]
        assert np.array_equal(sum(rmasks),np.asarray(guide.getchannel('A')))
        route=np.asarray(Image.open(io.BytesIO(archive.read('masks/routes.png'))))
        reservations=np.asarray(Image.open(io.BytesIO(archive.read('masks/reservations.png'))))
        assert not np.any((route>0)&(reservations>0))
        assert not np.any((route>0)&(masks[3]>0))
        return dict(revision=hashlib.sha256(archive.read('layout.json')).hexdigest(),members=len(archive.namelist()),
                    bytes=len(raw),regions=len(regions),objects=len(layout['objects']),
                    material_signature=hashlib.sha256(json.dumps(layout['materials']).encode()).hexdigest(),
                    zip_sha256=hashlib.sha256(raw).hexdigest())


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    results=[]
    for name,params in EXAMPLES:
        request=urllib.request.Request(BASE+'/api/layouts',data=json.dumps(params).encode(),headers={'Content-Type':'application/json'},method='POST')
        with urllib.request.urlopen(request) as response:
            assert response.status==201
            created=json.load(response)
        rid=created['revision']
        assert created==json.loads(get('/api/layouts/'+rid))
        raw=get('/api/layouts/'+rid+'/download')
        assert raw==get('/api/layouts/'+rid+'/download')
        result=verify_zip(raw)
        assert result['revision']==rid
        (OUT/(name+'.zip')).write_bytes(raw)
        (OUT/(name+'-request.json')).write_text(json.dumps(params,ensure_ascii=False,indent=2))
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            (OUT/(name+'-clean-guide.png')).write_bytes(archive.read('clean-guide.png'))
        results.append(dict(name=name,**result))
    assert len(results)==3 and len({r['material_signature'] for r in results})==3
    browser=ROOT/'evidence/browser-03'
    report=json.loads((browser/'browser-report.json').read_text())
    browser_check=verify_zip((browser/report['download']).read_bytes())
    assert browser_check['revision']==report['revision']
    evidence={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(browser.glob('*')) if p.is_file()}
    summary=dict(examples=results,browser_download=browser_check,evidence_sha256=evidence,
                 status='technical assertions passed; no production-art or visual PASS')
    (OUT/'verification.json').write_text(json.dumps(summary,indent=2))
    print(json.dumps(summary,indent=2))


if __name__=='__main__':
    main()
