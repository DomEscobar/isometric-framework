"""Independent verification of the browser-served production ZIP: checksums, rebuild, offline probe."""
import hashlib,io,json,os,shlex,subprocess,sys,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from artifacts import digest
RID=sys.argv[1] if len(sys.argv)>1 else '3c92b111114d479485d3aafe4991d441'
OUT=sys.argv[2] if len(sys.argv)>2 else 'evidence/hybrid-reassessment-repair'
out=ROOT/OUT;out.mkdir(exist_ok=True)
import httpx
with httpx.Client(base_url='http://127.0.0.1:48765',timeout=120) as c:
    r=c.get(f'/api/hybrid-runs/{RID}/download',params={'mode':'production'})
    assert r.status_code==200,r.status_code
    raw=r.content
(out/'production-download.zip').write_bytes(raw)
print('zip_sha256',digest(raw),'bytes',len(raw))
extract=out/'extracted';rebuild=out/'rebuilt'
import shutil
for d in [extract,rebuild]:
    if d.exists():shutil.rmtree(d)
with zipfile.ZipFile(io.BytesIO(raw)) as z:
    assert z.testzip() is None
    z.extractall(extract)
checks=json.loads((extract/'checksums.json').read_bytes())
bad=[n for n,h in checks.items() if digest((extract/n).read_bytes())!=h]
print('checksum_files',len(checks),'bad',bad)
# Byte-identical rebuild from the extracted offline sources.
res=subprocess.run(['python3',str(extract/'source/rebuild.py'),str(rebuild)],capture_output=True,timeout=300)
print('rebuild_rc',res.returncode,res.stderr.decode()[:300])
rebuilt=(rebuild/'production.zip').read_bytes() if (rebuild/'production.zip').exists() else b''
print('rebuild_byte_identical',rebuilt==raw)
# Offline navigation over the height/transition graph.
probe=subprocess.run(['node',str(ROOT/'tools/hybrid_artifact_probe.mjs'),str(extract)],capture_output=True,timeout=180)
print('probe_rc',probe.returncode)
print('probe_out',probe.stdout.decode()[:500])
summary=dict(zip_sha256=digest(raw),zip_bytes=len(raw),checksum_files=len(checks),checksum_failures=bad,rebuild_byte_identical=rebuilt==raw,probe_rc=probe.returncode,probe=probe.stdout.decode()[:500])
(out/'zip-verification.json').write_text(json.dumps(summary,indent=1))
