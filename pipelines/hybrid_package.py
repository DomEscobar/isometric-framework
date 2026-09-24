"""Offline deterministic production overlay; no service credentials or network."""
import io,json,zipfile
from pathlib import Path
from artifacts import canonical,digest

def archive(files):
    files={**files,'checksums.json':canonical({n:digest(b) for n,b in files.items() if n!='checksums.json'})}
    stream=io.BytesIO()
    with zipfile.ZipFile(stream,'w',zipfile.ZIP_DEFLATED) as z:
        for n,b in sorted(files.items()):
            info=zipfile.ZipInfo(n,(2026,1,1,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;z.writestr(info,b)
    return stream.getvalue()

def extend(base,extra):
    with zipfile.ZipFile(io.BytesIO(base)) as z:files={n:z.read(n) for n in z.namelist()}
    manifest={'base_zip_sha256':digest(base),'base_provenance':json.loads(files['provenance.json']),'extra':{n:digest(b) for n,b in extra.items()}}
    return archive({**files,**extra,'production-extension.json':canonical(manifest)})

def rebuild_extension(directory,out):
    d=Path(directory);out=Path(out);p=d/'production-extension.json'
    if not p.exists():return
    manifest=json.loads(p.read_bytes());base=(out/'diagnostic.zip').read_bytes()
    if digest(base)!=manifest['base_zip_sha256']:raise ValueError('Base rebuild differs')
    extra={}
    for n,sha in manifest['extra'].items():
        if Path(n).is_absolute() or '..' in Path(n).parts:raise ValueError('Unsafe package path')
        raw=(d/n).read_bytes()
        if digest(raw)!=sha:raise ValueError('Production evidence changed')
        extra[n]=raw
    raw=extend(base,extra)
    (out/'production.zip').write_bytes(raw)
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        for n in z.namelist():
            p=out/n;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(z.read(n))
