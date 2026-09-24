"""Offline evidence only: never imports app, writes a candidate, or overrides a gate."""
import numpy as np
import io
from PIL import Image, ImageDraw, ImageFilter
from artifacts import digest
from auto_adapter import measure_registration

SIDE_NAMES = ('upper_left', 'upper_right', 'lower_left', 'lower_right')
LIMITS = dict(residual_px=2.5, relative_scale=.01, translation_px=1.5)


def boundary_points(mask):
    """Four-neighbour inner boundary at original integer pixel indices."""
    m = np.pad(np.asarray(mask, bool), 1)
    interior = m[1:-1,1:-1] & m[:-2,1:-1] & m[2:,1:-1] & m[1:-1,:-2] & m[1:-1,2:]
    y, x = np.where(np.asarray(mask, bool) & ~interior)
    return np.column_stack((x, y)).astype(float)


def compare_boundaries(source, target):
    """Independent symmetric holdout; no transform optimisation or distance censoring."""
    if len(source) < 10 or len(target) < 10:
        return dict(status='uncertain_missing_boundary', diagnostic_alarm=True)
    def nearest(a, b):
        result = []
        for i in range(0, len(a), 128):
            dist2 = ((a[i:i+128,None,:]-b[None,:,:])**2).sum(2)
            result.extend(np.sqrt(dist2.min(1)))
        return _stats(result)
    forward, backward = nearest(source, target), nearest(target, source)
    return dict(status='proxy_measurement_not_semantic_ground_truth', source_to_target=forward,
                target_to_source=backward,
                diagnostic_alarm=max(forward['max_px'], backward['max_px']) > LIMITS['residual_px'])


def _edges(mask):
    mask = np.asarray(mask, dtype=bool)
    y = np.flatnonzero(mask.any(axis=1))
    if len(y) < 40:
        raise ValueError('insufficient foreground rows')
    left = mask[y].argmax(axis=1)
    right = mask.shape[1]-1-mask[y, ::-1].argmax(axis=1)
    # Widest row plateau is centered, never first-argmax biased.
    widths = right-left
    widths = np.median(np.lib.stride_tricks.sliding_window_view(np.pad(widths, 4, mode='edge'), 9), axis=1)
    middle = np.median(y[widths >= np.quantile(widths, .98)])
    result = {}
    for lower in (False, True):
        lo, hi = (middle, y[-1]) if lower else (y[0], middle)
        fraction = (y-lo)/(hi-lo)
        usable = (fraction >= .12) & (fraction <= .88)
        holdout = (fraction >= .4) & (fraction <= .6)
        for side, x in (('left', left), ('right', right)):
            key = ('lower_' if lower else 'upper_')+side
            result[key] = (np.column_stack((x[usable & ~holdout], y[usable & ~holdout])),
                           np.column_stack((x[usable & holdout], y[usable & holdout])))
    return result


def _line(points):
    x, y = np.asarray(points, float).T
    if len(x) < 10 or np.ptp(y) < 5:
        raise ValueError('insufficient long contour')
    sample = np.linspace(0, len(x)-1, min(64, len(x))).astype(int)
    dx = x[sample, None]-x[sample][None, :]
    dy = y[sample, None]-y[sample][None, :]
    valid = abs(dy) >= np.ptp(y)*.2
    a = np.median(dx[valid]/dy[valid])
    b = np.median(x-a*y)
    design = np.column_stack((y, np.ones(len(y))))
    for _ in range(20):
        residual = x-(a*y+b)
        sigma = max(.5, 1.4826*np.median(abs(residual-np.median(residual))))
        weights = np.minimum(1., 1.345*sigma/np.maximum(abs(residual), 1e-12))
        a, b = np.linalg.lstsq(design*np.sqrt(weights[:,None]), x*np.sqrt(weights), rcond=None)[0]
    return np.array([1., -a, -b])/np.hypot(1, a)


def _intersections(lines):
    pairs = [('upper_left','lower_left'), ('upper_left','upper_right'),
             ('upper_right','lower_right'), ('lower_left','lower_right')]
    return np.array([np.linalg.solve(np.array([lines[a][:2], lines[b][:2]]),
                                     -np.array([lines[a][2], lines[b][2]])) for a,b in pairs])


def _stats(distances):
    d = np.asarray(distances, float)
    return dict(count=len(d), p50_px=float(np.median(abs(d))),
                p95_px=float(np.quantile(abs(d), .95)), max_px=float(abs(d).max()),
                signed_median_px=float(np.median(d)), within_2_5_px=float(np.mean(abs(d) <= 2.5)))


def compare_road_band(source, target, scale, translation, strategy='longest_run'):
    """Independent central60% long curb evidence. No transform optimisation."""
    def band(mask):
        x = np.flatnonzero(mask.any(0))
        if strategy == 'longest_run':
            columns = []
            for column in x:
                transitions = np.diff(np.pad(mask[:,column].astype(int),(1,1)))
                starts, ends = np.flatnonzero(transitions==1), np.flatnonzero(transitions==-1)
                best = int(np.argmax(ends-starts))
                if ends[best]-starts[best] >= 10:
                    columns.append((column, starts[best], ends[best]-1))
            if len(columns)<40:
                raise ValueError('insufficient road band')
            values = np.array(columns)
            x = values[:,0]
            use = (x>=np.quantile(x,.2))&(x<=np.quantile(x,.8))
            return dict(upper=values[use,:2], lower=values[use][:,[0,2]])
        if strategy != 'extrema':
            raise ValueError('unknown band strategy')
        if len(x)<40:
            raise ValueError('insufficient road band')
        x = x[(x>=np.quantile(x,.2))&(x<=np.quantile(x,.8))]
        upper = mask[:,x].argmax(0)
        lower = mask.shape[0]-1-mask[::-1,x].argmax(0)
        return dict(upper=np.column_stack((x,upper)), lower=np.column_stack((x,lower)))
    try:
        observed, expected = band(source), band(target)
    except ValueError:
        return dict(status='uncertain_missing_road_band', transform_refitted=False)
    result = dict(transform_refitted=False, status='color_proxy_long_curbs_not_ground_truth')
    for key in ('upper','lower'):
        # _line fits its first coordinate against its second; reverse for y(x).
        line = _line(expected[key][:,::-1])[[1,0,2]]
        transformed = observed[key]*scale+translation
        fitted = _line(transformed[:,::-1])[[1,0,2]]
        result[key] = dict(**_stats(transformed@line[:2]+line[2]),
                           source_slope=float(-fitted[0]/fitted[1]), target_slope=float(-line[0]/line[1]),
                           target_line=line.tolist(), observed_line=fitted.tolist())
    return result


def extrema_ties(mask):
    y, x = np.where(mask)
    if not len(x):
        return {}
    points = np.column_stack((x,y))
    result = {}
    for name, axis, value in (('left',0,x.min()), ('top',1,y.min()),
                              ('right',0,x.max()), ('bottom',1,y.max())):
        ties = points[points[:,axis] == value]
        result[name] = dict(count=len(ties), first=ties[0].tolist(), centroid=ties.mean(0).tolist(),
                            minimum=ties.min(0).tolist(), maximum=ties.max(0).tolist())
    return result


def _away_from_frame(points, lines):
    if not len(points):
        return points
    distances = np.array([abs(points@np.array(line[:2])+line[2]) for line in lines.values()])
    return points[distances.min(0) > 8]


def diagnose(source_bytes, files):
    """Returns JSON-compatible measurements and an explicitly labelled native panel."""
    image = Image.open(io.BytesIO(source_bytes)).convert('RGBA')
    src = np.array(image)
    guide = np.array(Image.open(io.BytesIO(files['clean-guide.png'])).convert('RGBA'))
    foreground = guide[:,:,3] > 0
    fits, ties = [], {}
    for threshold in (60,80,100):
        mask = (src[:,:,:3].max(2)>threshold) & (src[:,:,3]>0)
        fits.append(dict(threshold=threshold, **fit_frame(mask, foreground)))
        ties[str(threshold)] = extrema_ties(mask)
    chosen = fits[1]
    scale, translation = chosen['scale'], np.array(chosen['translation'])
    rgb = src[:,:,:3].astype(int)
    r,g,b = rgb.transpose(2,0,1)
    proxies = dict(planting=(g-r>8)&(g-b>12)&(g>65),
                   street=(rgb.max(2)-rgb.min(2)<35)&(rgb.max(2)>60)&(rgb.max(2)<190))
    width, height = guide.shape[1], guide.shape[0]
    inverse = (1/scale,0,-translation[0]/scale,0,1/scale,-translation[1]/scale)
    proposed = image.transform((width,height),Image.Transform.AFFINE,inverse,resample=Image.Resampling.NEAREST)
    panel = Image.new('RGB',(width*2,height+76),'#18212a')
    panel.paste(proposed,(0,76),proposed)
    panel.paste(proposed,(width,76),proposed)
    draw = ImageDraw.Draw(panel)
    draw.text((8,8),'PROPOSED FIT DIAGNOSTIC - NOT REGISTERED / NOT GAMEPLAY',fill='white')
    draw.text((8,28),'LEFT: cyan canonical / magenta observed frame holdouts',fill='white')
    draw.text((width+8,28),'RIGHT: cyan canonical / orange street / magenta planting proxies',fill='white')
    draw.text((8,48),'Native canonical pixels; proxy boundaries are NOT semantic ground truth.',fill='white')
    def plot(points, color, offset=0):
        for x,y in np.rint(points).astype(int):
            if 0 <= x < width and 0 <= y < height:
                draw.point((x+offset,y+76),fill=color)
    plot(boundary_points(foreground),'cyan')
    source_edges = _edges((src[:,:,:3].max(2)>80)&(src[:,:,3]>0))
    for train, held in source_edges.values():
        plot(train*scale+translation, '#d9ad55')
        plot(held*scale+translation, '#ff48df')
    interior = {}
    for name, proxy in proxies.items():
        proxy &= src[:,:,3]>0
        clean = np.array(Image.fromarray(proxy.astype('uint8')*255).filter(ImageFilter.MedianFilter(5))) > 0
        target = np.array(Image.open(io.BytesIO(files['masks/material-'+name+'.png'])))>0
        observed = _away_from_frame(boundary_points(clean)*scale+translation, chosen['target_lines'])
        expected = _away_from_frame(boundary_points(target), chosen['target_lines'])
        interior[name] = compare_boundaries(observed, expected)
        interior[name]['source_proxy_pixels'] = int(clean.sum())
        interior[name]['canonical_mask_pixels'] = int(target.sum())
        if name == 'street':
            interior[name]['long_band_curbs'] = compare_road_band(clean, target, scale, translation, strategy='extrema')
            interior[name]['supplemental_longest_run_curbs'] = compare_road_band(clean, target, scale, translation)
        plot(expected,'cyan',width)
        plot(observed,'#ff48df' if name=='planting' else '#ffae32',width)
    result = dict(schema='registration-diagnostic-v1', production_approved=False,
                  registered_candidate_created=False, live_gate_replaced=False,
                  source_sha256=digest(source_bytes), guide_sha256=digest(files['clean-guide.png']),
                  source_size=list(image.size), canonical_size=[width,height], limits=LIMITS,
                  legacy_registration=measure_registration(source_bytes,files['clean-guide.png']),
                  source_extrema_ties=ties, canonical_extrema_ties=extrema_ties(foreground),
                  frame_fits=fits, proposed_fit=dict(scale=scale,translation=translation.tolist()),
                  relative_scale_spread=max(abs(f['scale']/scale-1) for f in fits),
                  translation_spread_px=max(float(np.linalg.norm(np.array(f['translation'])-translation)) for f in fits),
                  interior_proxies=interior,
                  conclusion='UNCERTAIN: diagnostic evidence only; original gate and terminal stop retained',
                  limitations=['No semantic ground truth from color proxies',
                               'Plant tuft silhouettes need not equal ground-plane planting limits',
                               'Perpendicular frame holdouts do not observe tangential corner drift',
                               'No anisotropic transformation applied; span ratios are descriptive only'])
    return result, panel


def fit_frame(source_mask, target_mask):
    source_edges, target_edges = _edges(source_mask), _edges(target_mask)
    sl = {k:_line(v[0]) for k,v in source_edges.items()}
    tl = {k:_line(v[0]) for k,v in target_edges.items()}
    source, target = _intersections(sl), _intersections(tl)
    sc, tc = source-source.mean(0), target-target.mean(0)
    scale = float((sc*tc).sum()/(sc*sc).sum())
    translation = target.mean(0)-scale*source.mean(0)
    if not np.isfinite(scale) or scale <= 0:
        raise ValueError('invalid uniform scalar')
    holdout = {k:_stats((v[1]*scale+translation)@tl[k][:2]+tl[k][2]) for k,v in source_edges.items()}
    return dict(transform_model='one_uniform_scale_plus_translation', scale=scale,
                translation=translation.tolist(), holdout=holdout,
                source_intersections=source.tolist(), target_intersections=target.tolist(),
                intersection_max_residual_px=float(np.linalg.norm(source*scale+translation-target,axis=1).max()),
                source_per_target_spans_xy=[float((source[2,0]-source[0,0])/(target[2,0]-target[0,0])),
                                            float((source[3,1]-source[1,1])/(target[3,1]-target[1,1]))],
                diagnostic_alarm=bool(any(v['max_px'] > LIMITS['residual_px'] for v in holdout.values()) or
                                  np.linalg.norm(source*scale+translation-target,axis=1).max() > LIMITS['residual_px']),
                production_approved=False,
                source_lines={k:v.tolist() for k,v in sl.items()}, target_lines={k:v.tolist() for k,v in tl.items()},
                sample_counts={k:dict(training=len(v[0]),holdout=len(v[1])) for k,v in source_edges.items()})
