import importlib.util,zipfile,json
from pathlib import Path
from test_hybrid_layout import sample

def test_replay_package_exact_source_diagnostic(tmp_path):
    assert importlib.util.find_spec('hybrid_artifact'), 'offline hybrid package missing'
    from hybrid_layout import compile_layout
    from hybrid_artifact import build,replay_materials
    source,binding=replay_materials()
    w=compile_layout(sample())
    result=build(tmp_path,w,source,binding,{'mode':'replay','production_approved':False})
    with zipfile.ZipFile(result) as z:
        assert z.read('provider-original.png')==source
        assert not json.loads(z.read('provenance.json'))['production_approved']
        assert z.testzip() is None
        assert 'window.multilevel' in z.read('index.html').decode()
        assert 'source/rebuild.py' in z.namelist()
    import subprocess
    other=tmp_path/'rebuilt'
    subprocess.run(['python3',str(tmp_path/'source/rebuild.py'),str(other)],check=True)
    assert (other/'diagnostic.zip').read_bytes()==result.read_bytes()
