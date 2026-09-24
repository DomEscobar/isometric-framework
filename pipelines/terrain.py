"""Non-semantic image diagnostics and reproducible derivation from retained originals."""
import io
import zipfile
import numpy as np
from PIL import Image
from artifacts import canonical, digest, export_files, png


def image_checks(source, guide, files):
    a = np.array(Image.open(io.BytesIO(source)).convert('RGBA'))
    g = np.array(Image.open(io.BytesIO(guide)).convert('RGBA'))
    result = dict(semantic_verdict='unverified', visual_review='unreviewed',
                  method='alpha coverage and RGB statistics, no material classifier or registration fit',
                  uncertainty='Opaque coverage cannot identify water, obstacles, material identity or correct landmark positions.')
    if a.shape != g.shape:
        return dict(result, measurable=False, reason='dimensions differ; no implicit registration or stretching')
    inside = g[:,:,3] > 0
    opaque = a[:,:,3] >= 250
    route = np.array(Image.open(io.BytesIO(files['masks/routes.png']))) > 0
    result.update(measurable=True, guide_pixels=int(inside.sum()),
                  uncovered_guide_pixels=int((inside & ~opaque).sum()),
                  uncovered_route_pixels=int((route & ~opaque).sum()),
                  opaque_outside_guide_pixels=int((~inside & opaque).sum()),
                  exact_guide_rgb_fraction=float(np.all(a[:,:,:3] == g[:,:,:3],axis=2)[inside].mean()),
                  note='Exact guide RGB can identify a technical fixture; it does not certify art semantics.')
    result['regions']={}
    for name,raw in files.items():
        if not name.startswith('masks/material-'): continue
        mask=np.array(Image.open(io.BytesIO(raw)))>0
        visible=mask & opaque
        rgb=a[:,:,:3][visible]
        result['regions'][name.removeprefix('masks/material-').removesuffix('.png')]=dict(
            planned_pixels=int(mask.sum()),uncovered_pixels=int((mask & ~opaque).sum()),
            mean_rgb=rgb.mean(axis=0).tolist() if len(rgb) else None,
            rgb_standard_deviation=rgb.std(axis=0).tolist() if len(rgb) else None,
            interpretation='Measured pixels inside planned region, NOT classified material identity.')
    return result


def render_original(layout, record, source, density):
    original=Image.open(io.BytesIO(source)).convert('RGBA')
    p=layout['projection'];ratio=density/p['density']
    size=tuple(int(n*ratio) for n in p['image_size'])
    reg=record.get('processing_registration')
    if reg:
        scale=reg['scale']*ratio;tx,ty=[n*ratio for n in reg['translation']]
        # One uniform inverse affine map directly from retained original; no axis stretch.
        return original.transform(size,Image.Transform.AFFINE,(1/scale,0,-tx/scale,0,1/scale,-ty/scale),resample=Image.Resampling.NEAREST)
    return original.resize(size,Image.Resampling.NEAREST) if original.size!=size else original


def candidate_files(layout, record, source, density):
    if not record.get('guide_sha256'):
        raise ValueError('legacy import lacks guide binding; re-import retained original to create a new candidate')
    if density not in (1,2):
        raise ValueError('density must be 1 or 2')
    if record['status'] == 'rejected':
        raise ValueError('rejected candidate cannot be exported as terrain')
    original = Image.open(io.BytesIO(source)).convert('RGBA')
    p = layout['projection']
    size = tuple(n//p['density']*density for n in p['image_size'])
    final = render_original(layout,record,source,density)
    files = export_files(layout)
    files.pop('checksums.json')
    files['sources/original.png'] = source
    files['terrain.png'] = png(np.array(final))
    files['candidate.json'] = canonical(record)
    files['terrain-provenance.json'] = canonical(dict(
        candidate_id=record['id'],layout_revision=record['layout_revision'],
        source_sha256=digest(source),guide_sha256=record['guide_sha256'],
        terrain_sha256=digest(files['terrain.png']),production_approved=False,
        status='needs_attention',visual_review='unreviewed',image_alignment='unverified',
        processing=dict(version=1,from_original=True,density=density,source_size=list(original.size),
                        output_size=list(size),sampler='NEAREST',crop='canonical frame after uniform transform' if record.get('processing_registration') else None,mask=None,palette=None,
                        registration=record.get('processing_registration')),
        output_projection={**p,'density':density,'image_size':list(size),
          **{k:[v/p['density']*density for v in p[k]] for k in ('origin_px','column_basis_px','row_basis_px')}},
        caveat='Layout/guide/masks retain canonical source density; terrain output_projection is separate. No measured image alignment or semantic approval.'))
    files['README.txt'] += b'\nUNREVIEWED CANDIDATE: terrain.png is NOT production-approved. sources/original.png retains exact bytes. See terrain-provenance.json for output density and source projection.\n'
    files['checksums.json'] = canonical({n:digest(b) for n,b in sorted(files.items())})
    return files


def bundle(files):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream,'w') as z:
        for name,raw in sorted(files.items()):
            i=zipfile.ZipInfo(name,(1980,1,1,0,0,0)); i.compress_type=zipfile.ZIP_DEFLATED; i.external_attr=0o644<<16
            z.writestr(i,raw)
    return stream.getvalue()
