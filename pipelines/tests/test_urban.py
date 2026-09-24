import io
import numpy as np
from PIL import Image
import pytest
from layout_core import generate, validate
from artifacts import export_files, canonical, digest


def test_urban_has_distinct_materials_safe_sidewalk_route_and_reservations():
    l = generate({'kind':'urban','seed':20260922})
    assert set(sum(l['materials'],[])) == {'street','sidewalk','planting'}
    assert l['urban_semantics']['street_walkable'] is True
    v=validate(l)
    assert v['valid']
    assert all(l['materials'][r][c]=='sidewalk' for route in v['routes'] for c,r in route)
    assert [4,7] in v['safe_cells'] # technical player may cross empty road; no traffic simulation
    assert [3,1] not in v['safe_cells'] # protected planting
    assert l['objects'] and all('no production prop' in o['art_extent_status'] for o in l['objects'])
    f=export_files(l)
    masks=[np.array(Image.open(io.BytesIO(f['masks/material-'+m+'.png'])),dtype=np.uint16) for m in ('street','sidewalk','planting')]
    assert all(a.any() for a in masks)
    assert np.array_equal(sum(masks),np.array(Image.open(io.BytesIO(f['clean-guide.png'])))[:,:,3])
    route=np.array(Image.open(io.BytesIO(f['masks/routes.png'])))>0
    assert not np.any(route & (masks[1]==0))


def test_urban_ui_exposes_material_masks_and_preset():
    from pathlib import Path
    ui=Path('static/index.html').read_text()
    for m in ('street','sidewalk','planting'):
        assert f'value="{m}"' in ui
        assert f"{m}:'#" in ui
    assert 'value="urban"' in ui


def test_original_forest_revision_is_unchanged():
    l=generate({'width':16,'height':14,'seed':20260921,'tile_width':48,'density':1,'actor_width':0.8,'brief':'Teich im Nordosten; Weg West-Ost; 1 Haus; 3 Bäume'})
    from pathlib import Path
    import json
    old=json.loads(Path('evidence/paid-pilot/layout-response.json').read_text())
    assert digest(canonical(l))==old['revision']
