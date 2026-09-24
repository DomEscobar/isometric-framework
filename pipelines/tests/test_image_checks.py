import io
import numpy as np
from PIL import Image
from artifacts import export_files,png
from layout_core import generate
from terrain import image_checks


def test_local_regions_measure_pixels_but_never_semantic_pass():
    l=generate({'kind':'pond-ne','path':'west-east'})
    f=export_files(l); guide=f['clean-guide.png']
    a=np.array(Image.open(io.BytesIO(guide)).convert('RGBA'))
    mask=np.array(Image.open(io.BytesIO(f['masks/material-water.png'])))>0
    a[mask,3]=0
    checks=image_checks(png(a),guide,f)
    assert checks['semantic_verdict']=='unverified'
    assert checks['regions']['water']['uncovered_pixels']==int(mask.sum())
    assert checks['regions']['grass']['uncovered_pixels']==0
    a[:,:,:]=[255,0,0,255] # wrong picture, matching dimensions
    checks=image_checks(png(a),guide,f)
    assert checks['semantic_verdict']=='unverified'
    assert checks['uncovered_guide_pixels']==0
    assert checks['regions']['water']['mean_rgb']==[255.0,0.0,0.0]
