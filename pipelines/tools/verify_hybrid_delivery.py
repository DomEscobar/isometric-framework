"""Read-back verifier for actual browser download and unchanged legacy evidence."""
import json,hashlib,sqlite3,subprocess,zipfile,os
from pathlib import Path
import numpy as np
from PIL import Image
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from hybrid_artifact import actor_scene
E=ROOT/'evidence/autonomous-hybrid';D=Path(os.environ.get('EVIDENCE',str(E/'browser-final'))).resolve();d=D/'extracted'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
with zipfile.ZipFile(D/'browser-diagnostic.zip') as z:
    assert z.testzip() is None
    for n in z.namelist():assert not Path(n).is_absolute() and '..' not in Path(n).parts
    checks=json.loads(z.read('checksums.json'))
    assert all(hashlib.sha256(z.read(n)).hexdigest()==h for n,h in checks.items())
    z.extractall(d)
subprocess.run(['node',str(ROOT/'tools/hybrid_artifact_probe.mjs'),str(d)],check=True,timeout=120)
rebuilt=D/'rebuilt'
if not rebuilt.exists():subprocess.run([sys.executable,str(d/'source/rebuild.py'),str(rebuilt)],check=True,timeout=180)
assert (rebuilt/'diagnostic.zip').read_bytes()==(D/'browser-diagnostic.zip').read_bytes()
w=json.loads((d/'world.json').read_text());w['spawn']=w['goals'][-1];im=np.array(Image.open(d/'terrain.png').convert('RGBA'));depth=np.fromfile(d/'depth.f32',dtype='<f4').reshape(im.shape[:2]);native=actor_scene(im,depth,w,(d/'character.png').read_bytes(),(d/'shadow.png').read_bytes(),json.loads((d/'character-manifest.json').read_text()));actual=np.array(Image.open(d/'browser-native.png').convert('RGBA'));assert np.array_equal(native,actual)
baseline=json.loads((E/'baseline.json').read_text());changed=[n for n,h in baseline.items() if sha(ROOT/n)!=h]
assert changed==['data/generation.sqlite3'],changed
old=json.loads((E/'ledger-baseline.json').read_text())
with sqlite3.connect('file:'+str(ROOT/'data/generation.sqlite3')+'?mode=ro',uri=True) as db:
    for table,rows in old.items():
        now={r[0]:hashlib.sha256(r[1].encode()).hexdigest() for r in db.execute('SELECT id,record FROM '+table)}
        assert now==rows,table
    ledger={t:db.execute('SELECT count(*),coalesce(sum(reserve),0) FROM '+t).fetchone() for t in ['jobs','reviews']}
    assert db.execute('SELECT count(*) FROM hybrid_calls').fetchone()[0]==0
proof={'download_sha256':sha(D/'browser-diagnostic.zip'),'members_verified':len(checks),'rebuild_byte_identical':True,'native_browser_pixel_differences':0,'legacy_file_changes':changed,'legacy_ledger_rows_unchanged':True,'ledger':ledger,'hybrid_paid_calls':0,'browser':json.loads((d/'browser-proof.json').read_text()),'run_id':json.loads((D/'run.json').read_text())['id'],'artifact':str(d),'mode':'REPLAY, not fresh autonomous provider proof'}
Path(os.environ.get('HYBRID_VERIFICATION',str(E/'verification-final.json'))).write_text(json.dumps(proof,indent=2));print(json.dumps(proof,indent=2))
