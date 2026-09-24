"""Register the owner's terrain reference image (JPEG original + lossless PNG)."""
import io,sys
from pathlib import Path
ROOT=Path('/root/services/layout-terrain-pipeline');sys.path.insert(0,str(ROOT))
from PIL import Image
from artifacts import digest
from hybrid_reference import reference_bytes

def main():
    root=Path('/root/services/layout-terrain-pipeline/data')
    up=root/'hybrid-uploads'
    src=Path('/root/.hermes/cache/images/img_6f4143b8da4b.jpg')
    original=src.read_bytes()
    im=Image.open(io.BytesIO(original));im.load();im=im.convert('RGB')
    out=io.BytesIO();im.save(out,format='PNG',optimize=False);normalized=out.getvalue()
    for data,suffix in [(normalized,'.png'),(original,'.original')]:
        p=up/(digest(data)+suffix)
        if not p.exists():p.write_bytes(data);print('wrote',p.name)
        else:print('exists',p.name)
    n,o=reference_bytes(root,{'reference_sha256':digest(normalized),'reference_original_sha256':digest(original)})
    print('reference_sha256',digest(normalized))
    print('reference_original_sha256',digest(original))
    print('verified',bool(n and o),Image.open(io.BytesIO(n)).size)

if __name__=='__main__':main()
