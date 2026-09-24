import importlib.util
import io
import json
import zipfile
import hashlib
from PIL import Image
from layout_core import generate


def test_immutable_revision_export_and_mask_partition(tmp_path):
    assert importlib.util.find_spec('artifacts'), 'export boundary missing'
    from artifacts import RevisionStore, export_bundle, canonical
    store = RevisionStore(tmp_path)
    layout = generate({'brief':'Teich im Nordosten; Weg West-Ost; 1 Haus; 3 Bäume','seed':19})
    rid = store.save(layout)
    assert rid == hashlib.sha256(canonical(layout)).hexdigest()
    assert store.save(layout) == rid
    assert store.load(rid) == layout
    raw = export_bundle(layout)
    assert raw == export_bundle(layout)
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        assert z.testzip() is None
        assert json.loads(z.read('layout.json')) == layout
        assert json.loads(z.read('provenance.json'))['production_art'] is False
        assert {'manifest.json','regions.json','objects.json','collision.json','validation.json','clean-guide.png','masks/routes.png','masks/reservations.png'} <= set(z.namelist())
        masks = [Image.open(io.BytesIO(z.read('masks/material-'+m+'.png'))) for m in ['grass','soil','path','water']]
        guide = Image.open(io.BytesIO(z.read('clean-guide.png')))
        assert guide.size == tuple(layout['projection']['image_size'])
        import numpy as np
        assert np.array_equal(sum(np.asarray(im, dtype=np.uint16) for im in masks), np.asarray(guide.getchannel('A'))), 'material masks must partition guide exactly'
    # Tampering must be detected, never silently accepted as the same revision.
    (tmp_path / (rid+'.json')).write_text('{}')
    import pytest
    with pytest.raises(ValueError, match='integrity'):
        store.load(rid)
