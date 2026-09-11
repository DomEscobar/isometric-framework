from PIL import Image
import numpy as np
from pathlib import Path
from math import sqrt
from scipy.ndimage import binary_fill_holes
try:
    from scipy.spatial import cKDTree
except ImportError:
    cKDTree = None

ROOT=Path(__file__).resolve().parents[3]
A_PATH=Path(__file__).resolve().with_name('layout-input.png')
B_PATH=ROOT/'examples/quellbrunn/terrain-trial/source-v1.png'
OUT=Path(__file__).resolve().with_name('registration.json')

def rgb(path): return np.asarray(Image.open(path).convert('RGB'), dtype=np.int16)

def fg_mask(im):
    h,w,_=im.shape
    # Perimeter samples establish dark-green backdrop even where a soft gradient is present.
    edge=np.concatenate((im[:60].reshape(-1,3),im[-60:].reshape(-1,3),im[:,:60].reshape(-1,3),im[:,-60:].reshape(-1,3)))
    bg=np.median(edge,axis=0)
    # The background is green-dominant and dark; map materials are materially brighter or blue.
    dist=np.sqrt(((im-bg)**2).sum(axis=2))
    mask=(dist>48) & ((im.max(axis=2)>105) | (im[:,:,2]>im[:,:,1]+20))
    return mask, bg.astype(int)

def diamond(mask):
    ys,xs=np.where(mask)
    # Axis extrema identify the four visible diamond tips.  Median within 2 px
    # prevents isolated texture/anti-alias pixels from moving a corner.
    def tip(values):
        limit=values.min()+2
        sel=values<=limit
        return np.array([float(np.median(xs[sel])),float(np.median(ys[sel]))])
    top=tip(ys); bottom=tip(-ys); left=tip(xs); right=tip(-xs)
    return np.array([top,right,bottom,left])

def affine(src,dst):
    X=np.c_[src, np.ones(len(src))]
    coef=np.linalg.lstsq(X,dst,rcond=None)[0] # columns x,y,1 -> dst x,y
    M=np.array([[coef[0,0],coef[1,0],coef[2,0]],[coef[0,1],coef[1,1],coef[2,1]],[0,0,1.]])
    return M

def transform(points,M):
    q=np.c_[points,np.ones(len(points))]@M.T
    return q[:,:2]/q[:,2:3]

def water(im):
    r,g,b=im[:,:,0],im[:,:,1],im[:,:,2]
    # Cyan foam may have B close to G, unlike the deep-blue base. Fill its
    # enclosed texture holes so boundary() reports the two outside banks only.
    raw=(b>r+30)&(g>r+30)&(b>105)&(g>90)
    return binary_fill_holes(raw)

def boundary(mask):
    # foreground-side pixels immediately adjacent to non-mask; excludes image perimeter
    core=mask.copy()
    interior=np.zeros_like(mask)
    interior[1:-1,1:-1]=mask[1:-1,1:-1] & mask[:-2,1:-1] & mask[2:,1:-1] & mask[1:-1,:-2] & mask[1:-1,2:]
    return core & ~interior

def nearest_stats(points, target):
    if cKDTree is None: raise RuntimeError('scipy is required for boundary distance measurement')
    d,_=cKDTree(target).query(points,k=1)
    return {'mean_px':float(np.mean(d)),'median_px':float(np.median(d)),'p90_px':float(np.quantile(d,.9)),'p95_px':float(np.quantile(d,.95)),'max_px':float(np.max(d)),'count':int(len(d))}

A=rgb(A_PATH); B=rgb(B_PATH)
fa,bga=fg_mask(A); fb,bgb=fg_mask(B)
da=diamond(fa); db=diamond(fb)
M=affine(db,da); Inv=np.linalg.inv(M)
corner_res=np.linalg.norm(transform(db,M)-da,axis=1)
wa=water(A); wb=water(B)
# Sample generated river boundary then map it into A coordinate system.
yb,xb=np.where(boundary(wb)); pb=np.c_[xb,yb]; mapped=transform(pb,M)
ya,xa=np.where(boundary(wa)); pa=np.c_[xa,ya]
riv_ab=nearest_stats(mapped,pa)
# inverse comparison measures both bank directions
mapped_a=transform(pa,Inv)
riv_ba=nearest_stats(mapped_a,pb)
# rasterize transformed source river at target pixels and quantify target land contamination.
h,w=wa.shape
Y,X=np.indices((h,w)); q=transform(np.c_[X.ravel(),Y.ravel()],Inv).reshape(h,w,2)
qi=np.rint(q).astype(int); valid=(qi[:,:,0]>=0)&(qi[:,:,0]<wb.shape[1])&(qi[:,:,1]>=0)&(qi[:,:,1]<wb.shape[0])
warped=np.zeros((h,w),bool); warped[valid]=wb[qi[:,:,1][valid],qi[:,:,0][valid]]
target_land=fa & ~wa
contam=warped & target_land
missing=wa & ~warped
# Read the affine-warped source river back on the authoritative world grid.
# The export plate uses project(c,r) with a +140 screen-y offset.
def world_screen(c,r): return 64+(c+r)*16,590+(r-c)*8
bank_samples=[]
for c in np.arange(0,48.0001,.5):
    rs=np.arange(0,40.0001,.025)
    sx,sy=world_screen(c,rs)
    ix=np.rint(sx).astype(int); iy=np.rint(sy).astype(int)
    in_frame=(ix>=0)&(ix<w)&(iy>=0)&(iy<h)
    hit=np.zeros(len(rs),bool); hit[in_frame]=warped[iy[in_frame],ix[in_frame]]
    runs=np.where(hit)[0]
    coverage=float(len(runs)/(runs[-1]-runs[0]+1)) if len(runs) else 0.0
    valid=bool(len(runs) and coverage>=.85)
    north=float(rs[runs[0]]) if len(runs) else None
    south=float(rs[runs[-1]]) if len(runs) else None
    center=25+1.3*np.sin(c/8)+.4*np.sin(c/3)
    bank_samples.append({'c':round(float(c),3),'valid':valid,'water_run_coverage':round(coverage,4),'source_north_bank_r':north,'source_south_bank_r':south,'authoritative_north_bank_r':round(float(center-2.6),4),'authoritative_south_bank_r':round(float(center+2.6),4),'north_delta_r':(round(north-(center-2.6),4) if north is not None else None),'south_delta_r':(round(south-(center+2.6),4) if south is not None else None)})
# Regions are left/right bank based on central vertical division; display exact extents where river crosses land.
res={
 'inputs':{'original':str(A_PATH.relative_to(ROOT)).replace('\\','/'),'generated':str(B_PATH.relative_to(ROOT)).replace('\\','/'),'original_size':[int(A.shape[1]),int(A.shape[0])],'generated_size':[int(B.shape[1]),int(B.shape[0])]},
 'method':{'foreground':'perimeter median dark-green RGB background; Euclidean RGB distance >48 plus brightness/blue guard','diamond':'axis extrema (top, right, bottom, left), median within 2px','water':'B>R+30, G>R+30, B>105, G>90; enclosed texture holes filled before boundary extraction','registration':'least-squares affine fit of four outer diamond vertices, generated to original','bank_distance':'one-pixel 4-neighbor external mask boundaries after hole fill; nearest-point Euclidean distance'},
 'background_rgb_median':{'original':bga.tolist(),'generated':bgb.tolist()},
 'foreground_pixels':{'original':int(fa.sum()),'generated':int(fb.sum())},
 'outer_diamond_corners_xy':{'original':da.round(3).tolist(),'generated':db.round(3).tolist(),'order':['top','right','bottom','left']},
 'generated_to_original_affine_3x3':M.tolist(),
 'original_to_generated_affine_3x3':Inv.tolist(),
 'outer_boundary_corner_residual_px':{'per_corner':corner_res.tolist(),'mean':float(corner_res.mean()),'max':float(corner_res.max())},
 'river_blue_mask_pixels':{'original':int(wa.sum()),'generated':int(wb.sum())},
 'river_bank_boundary_residual_after_affine_px':{'generated_bank_to_original_bank':riv_ab,'original_bank_to_generated_bank_inverse':riv_ba},
 'warped_generated_water_vs_original':{'overlap_px':int((warped&wa).sum()),'generated_water_on_original_land_px':int(contam.sum()),'generated_water_on_original_land_fraction_of_warped':float(contam.sum()/max(1,warped.sum())),'original_water_missing_from_warped_px':int(missing.sum()),'original_water_missing_fraction':float(missing.sum()/max(1,wa.sum())),'contamination_bbox_xyxy':([int(np.where(contam)[1].min()),int(np.where(contam)[0].min()),int(np.where(contam)[1].max()),int(np.where(contam)[0].max())] if contam.any() else None)},
 'source_banks_in_authoritative_world_r':{'sample_step_c':0.5,'scan_step_r':0.025,'projection':'x=64+(c+r)*16; y=590+(r-c)*8, including the export plate +140 y offset','samples':bank_samples},
 'conclusion':'Global outer-diamond affine fit is insufficient for placing the generated source as terrain under the authoritative river: it produces measured river-on-land contamination. Use a piecewise registration/deformation anchored to both visible riverbanks (at least upstream, bend, downstream control pairs), then remeasure; do not accept the global transform for final slicing.'
}
import json
OUT.write_text(json.dumps(res,indent=2)+'\n',encoding='utf-8')
print(json.dumps(res,indent=2))
