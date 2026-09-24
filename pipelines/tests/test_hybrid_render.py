import importlib.util
import numpy as np
from test_hybrid_layout import sample

def test_geometry_preview_is_free_and_native_rectangular():
    assert importlib.util.find_spec('hybrid_render'), 'parametric renderer missing'
    from hybrid_layout import compile_layout
    from hybrid_render import render,PreviewMaterials
    w=compile_layout(sample());im,depth,xy,flags=render(w,PreviewMaterials())
    assert im.shape==(w['canvas'][1],w['canvas'][0],4)
    assert (depth>-1000).any()
    assert np.all(im[:,:,3]==255)
