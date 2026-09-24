"""Content-addressed local revisions and reproducible, clean technical exports."""
import hashlib
import io
import json
import os
from pathlib import Path
import re
import zipfile
import numpy as np
from PIL import Image, ImageColor
from layout_core import MATERIALS, validate


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode()


def digest(data):
    return hashlib.sha256(data).hexdigest()


class RevisionStore:
    def __init__(self, root):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def save(self, layout):
        report = validate(layout)
        if not report['valid']:
            raise ValueError('invalid revision: '+str(report['errors']))
        raw = canonical(layout)
        rid = digest(raw)
        # Exclusive creation: an existing canonical revision is never rewritten.
        path = self.root / (rid+'.json')
        try:
            with path.open('xb') as f:
                f.write(raw)
                f.flush()
                os.fsync(f.fileno())
        except FileExistsError:
            if path.read_bytes() != raw:
                raise ValueError('revision integrity failure')
        return rid

    def load(self, rid):
        if not re.fullmatch('[0-9a-f]{64}', rid):
            raise ValueError('invalid revision id')
        raw = (self.root / (rid+'.json')).read_bytes()
        if digest(raw) != rid:
            raise ValueError('revision integrity failure')
        return json.loads(raw)


def region_map(layout):
    w, h = layout['width'], layout['height']
    labels = np.full((h,w), -1, dtype=np.int16)
    regions = []
    for r in range(h):
        for c in range(w):
            if labels[r,c] >= 0:
                continue
            idx = len(regions)
            material = layout['materials'][r][c]
            todo, cells = [(c,r)], []
            labels[r,c] = idx
            while todo:
                x,y = todo.pop()
                cells.append([x,y,0])
                for a,b in ((x-1,y),(x+1,y),(x,y-1),(x,y+1)):
                    if 0 <= a < w and 0 <= b < h and labels[b,a] < 0 and layout['materials'][b][a] == material:
                        labels[b,a] = idx
                        todo.append((a,b))
            regions.append(dict(id=f'region-{idx:03}',material=material,cells=sorted(cells)))
    return labels, regions


def png(array):
    stream = io.BytesIO()
    Image.fromarray(array).save(stream, format='PNG', optimize=False)
    return stream.getvalue()


def export_files(layout):
    report = validate(layout)
    if not report['valid']:
        raise ValueError('cannot export invalid layout')
    p = layout['projection']
    iw, ih = p['image_size']
    yy, xx = np.ogrid[:ih,:iw]
    # Pixel-center inverse of the SAME exported basis, not polygon overdraw.
    dx = (xx+.5-p['origin_px'][0]) / p['column_basis_px'][0]
    dy = (yy+.5-p['origin_px'][1]) / p['column_basis_px'][1]
    cc, rr = (dx+dy)/2, (dy-dx)/2
    ci, ri = np.floor(cc).astype(int), np.floor(rr).astype(int)
    inside = (ci>=0)&(ci<layout['width'])&(ri>=0)&(ri<layout['height'])
    ci = ci.clip(0,layout['width']-1)
    ri = ri.clip(0,layout['height']-1)
    materials = [m for m in MATERIALS if m in ('grass','soil','path','water') or any(m in row for row in layout['materials'])]
    grid = np.array([[materials.index(m) for m in row] for row in layout['materials']])
    ids = grid[ri,ci]
    rgba = np.zeros((ih,iw,4),dtype=np.uint8)
    files = {}
    for n, material in enumerate(materials):
        mask = inside & (ids==n)
        rgba[mask] = (*ImageColor.getrgb(MATERIALS[material]),255)
        files['masks/material-'+material+'.png'] = png(mask.astype('uint8')*255)
    labels, regions = region_map(layout)
    for i, region in enumerate(regions):
        files['masks/'+region['id']+'.png'] = png((inside & (labels[ri,ci]==i)).astype('uint8')*255)
    reservation = np.zeros((ih,iw),dtype=bool)
    for o in layout['objects']:
        reservation |= inside & (cc>=o['x']) & (cc<o['x']+o['w']) & (rr>=o['y']) & (rr<o['y']+o['h'])
    route = np.zeros((ih,iw),dtype=bool)
    half = layout['actor_width']/2
    for path in report['routes']:
        for a,b in zip(path, path[1:] or path):
            route |= inside & (cc>=min(a[0],b[0])+.5-half) & (cc<max(a[0],b[0])+.5+half) & (rr>=min(a[1],b[1])+.5-half) & (rr<max(a[1],b[1])+.5+half)
    safe = np.zeros((layout['height'],layout['width']),dtype=bool)
    for c,r in report['safe_cells']:
        safe[r,c] = True
    files.update({'clean-guide.png':png(rgba), 'masks/reservations.png':png(reservation.astype('uint8')*255),
                  'masks/routes.png':png(route.astype('uint8')*255),
                  'masks/actor-safe-centers.png':png((inside & safe[ri,ci]).astype('uint8')*255)})
    rid = digest(canonical(layout))
    records = {'layout.json':layout, 'manifest.json':dict(layout_revision=rid, **p),
               'regions.json':regions, 'objects.json':layout['objects'], 'validation.json':report,
               'collision.json':dict(actor_width=layout['actor_width'],model=report['clearance_model'],
                                     graph=report['graph'], safe_centers=report['safe_cells']),
               'provenance.json':dict(layout_revision=rid, generator='bounded-layout-v1',seed=layout['seed'],
                                       source='local deterministic semantic construction', production_art=False,
                                       paid_generation=False, terrain_provider='missing / disabled',
                                       image_semantic_compliance='not assessed', visual_review='not assessed',
                                       recipe='pixel-center inverse projection; flat material labels; no generated pixels')}
    files.update({name:canonical(record) for name,record in records.items()})
    files['README.txt'] = ('TECHNICAL BLOCKOUT ONLY — no generated production terrain or props.\n'
                          'clean-guide.png: unlabeled material geometry, not final art.\n'
                          'masks/routes.png: swept actor corridor. actor-safe-centers: safe cell centers, NOT every pixel position.\n'
                          'Global coordinate metadata is not local painted-image compliance. No engine adapter is included.\n').encode()
    files['checksums.json'] = canonical({name:digest(raw) for name,raw in sorted(files.items())})
    return files


def export_bundle(layout):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream,'w',compression=zipfile.ZIP_DEFLATED) as archive:
        for name,raw in sorted(export_files(layout).items()):
            info = zipfile.ZipInfo(name, date_time=(1980,1,1,0,0,0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info,raw)
    return stream.getvalue()
