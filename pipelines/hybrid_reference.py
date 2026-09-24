"""Retained original upload -> once-decoded style PNG identity, never a URL."""
import io,re
from PIL import Image
from artifacts import digest

def reference_bytes(root,config):
    hashes=[config.get(k) for k in ['reference_sha256','reference_original_sha256']]
    if any(not isinstance(h,str) or not re.fullmatch('[0-9a-f]{64}',h) for h in hashes):raise ValueError('Originalreferenz-Bindung fehlt')
    try:
        normalized=(root/'hybrid-uploads'/(hashes[0]+'.png')).read_bytes()
        original=(root/'hybrid-uploads'/(hashes[1]+'.original')).read_bytes()
    except FileNotFoundError:raise ValueError('Gebundene Referenz fehlt') from None
    if [digest(normalized),digest(original)]!=hashes:raise ValueError('Referenzbytes verändert')
    decoded=[]
    for raw in [normalized,original]:
        im=Image.open(io.BytesIO(raw))
        if im.format not in ['PNG','JPEG','WEBP'] or im.width*im.height>8_000_000 or len(raw)>8_000_000:raise ValueError('Referenzformat/Größe falsch')
        decoded.append((im.size,im.convert('RGB').tobytes()))
    if decoded[0]!=decoded[1]:raise ValueError('Originalreferenz passt nicht zum Reviewbild')
    return normalized,original
