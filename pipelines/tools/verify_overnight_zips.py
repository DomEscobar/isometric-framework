"""No network, no writes outside evidence; verify all downloaded ZIPs in this phase."""
import sys,json,zipfile,io
from pathlib import Path
import numpy as np
from PIL import Image
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from artifacts import digest,canonical,export_files
from terrain import render_original
root=Path(__file__).resolve().parents[1];out=root/'evidence/overnight-two-styles';results=[]
for p in sorted(out.rglob('*.zip')):
 with zipfile.ZipFile(p) as z:
  assert z.testzip() is None;f={n:z.read(n) for n in z.namelist()};checks=json.loads(f['checksums.json']);assert set(checks)==set(f)-{'checksums.json'}
  for n,sha in checks.items():assert digest(f[n])==sha
  layout=json.loads(f['layout.json']);assert f['collision.json']==export_files(layout)['collision.json'];replay=False
  if 'terrain.png' in f:
   rec=json.loads(f['candidate.json']);prov=json.loads(f['terrain-provenance.json']);raw=f['sources/original.png'];assert digest(raw)==rec['source_sha256'];density=prov['output_projection']['density'];im=render_original(layout,rec,raw,density);assert np.array_equal(np.array(im),np.array(Image.open(io.BytesIO(f['terrain.png']))));replay=True
  results.append(dict(path=str(p.relative_to(root)),sha256=digest(p.read_bytes()),members=len(f),crc=True,all_checksums=True,collision_unchanged=True,direct_source_pixel_replay=replay,scope='technical fixture' if 'candidate-regression' in str(p) else 'retained historical result' if any(s in str(p) for s in ('auto-regression','forest-regression','urban-regression','style-regression')) else 'new phase artifact'))
(out/'all-zip-verification.json').write_bytes(json.dumps(dict(count=len(results),zips=results),indent=2).encode());print(json.dumps(dict(count=len(results),zips=results),indent=2))
