"""Painted-scene artifact packaging for the terrain pipeline."""
import io, json, base64, zipfile
from pathlib import Path
import numpy as np
from PIL import Image
from artifacts import canonical, digest

ROOT = Path(__file__).resolve().parent
ACTOR = ROOT / 'assets/actor'
SOURCES = [
    'hybrid_package.py', 'hybrid_artifact.py', 'hybrid_painted_scene.py',
    'hybrid_layout.py', 'artifacts.py', 'layout_core.py', 'static/hybrid-navigator.html',
]


def png(im):
    b = io.BytesIO()
    Image.fromarray(im).save(b, format='PNG')
    return b.getvalue()


def actor_scene(image, depth, w, actor_raw, shadow_raw, manifest):
    out = image.copy()
    x, y = w['spawn']
    z = w['heights'][y][x]
    wx, wy = x + .5, y + .5
    px = w['origin'][0] + 24 * (wx - wy)
    py = w['origin'][1] + 12 * (wx + wy) - z
    for raw, anchor in [(shadow_raw, manifest['shadow_anchor_px']), (actor_raw, manifest['foot_anchor_px'])]:
        a = np.array(Image.open(io.BytesIO(raw)).convert('RGBA'))
        dx = int(px - anchor[0] + .5)
        dy = int(py - anchor[1] + .5)
        for sy in range(a.shape[0]):
            for sx in range(a.shape[1]):
                X, Y = dx + sx, dy + sy
                alpha = int(a[sy, sx, 3])
                if alpha and 0 <= X < out.shape[1] and 0 <= Y < out.shape[0] and depth[Y, X] <= wx + wy + .045:
                    out[Y, X, :3] = ((a[sy, sx, :3].astype('uint32') * alpha + 127) // 255 + (out[Y, X, :3].astype('uint32') * (255 - alpha) + 127) // 255).astype('uint8')
    return out


def artifact_binding(directory):
    d = Path(directory)
    names = json.loads((d / 'checksums.json').read_bytes())
    return {**names, 'checksums.json': digest((d / 'checksums.json').read_bytes()), 'diagnostic.zip': digest((d / 'diagnostic.zip').read_bytes())}


def verify_artifact(directory, binding):
    if not binding:
        raise ValueError('Artefaktbindung fehlt')
    for name, sha in binding.items():
        if digest((Path(directory) / name).read_bytes()) != sha:
            raise ValueError('Artefakt wurde nach Review verändert')
    return True


def _navigator(w, files, manifest, depth):
    data = {'world': w, 'character': manifest, 'depth': base64.b64encode(depth.tobytes()).decode()}
    for k, v in [('terrain', 'terrain.png'), ('sprite', 'character.png'), ('shadow', 'shadow.png')]:
        data[k] = 'data:image/png;base64,' + base64.b64encode(files[v]).decode()
    template = (ROOT / 'static/hybrid-navigator.html').read_text()
    return template.replace('__SCENE_DATA__', canonical(data).decode()).replace('__WIDTH__', str(w['canvas'][0])).replace('__HEIGHT__', str(w['canvas'][1])).encode()


def build_scene(directory, w, source, provenance):
    """Registered provider pixels over the frozen collision world."""
    from hybrid_painted_scene import register, render_guide, guide_png
    d = Path(directory)
    d.mkdir(parents=True, exist_ok=True)
    terrain, registration = register(w, source)
    _, depth = render_guide(w)
    actor = (ACTOR / 'character.png').read_bytes()
    shadow = (ACTOR / 'shadow.png').read_bytes()
    manifest = json.loads((ACTOR / 'character-manifest.json').read_bytes())
    files = {
        'terrain.png': png(terrain), 'depth.f32': depth.tobytes(), 'world.json': canonical(w),
        'provider-original.png': source, 'scene-registration.json': canonical(registration),
        'guide.png': guide_png(w), 'character.png': actor, 'shadow.png': shadow,
        'character-manifest.json': canonical(manifest),
    }
    files['scene.png'] = png(actor_scene(terrain, depth, w, actor, shadow, manifest))
    files['index.html'] = _navigator(w, files, manifest, depth)
    files['provenance.json'] = canonical({
        **provenance, 'layout_revision': w['revision'], 'source_sha256': digest(source),
        'actor_sha256': digest(actor), 'shadow_sha256': digest(shadow),
        'renderer_sha256': digest((ROOT / 'hybrid_painted_scene.py').read_bytes()),
        'sampling': 'one uniform LANCZOS rescale of the painted frame, canvas crop; depth from the organic guide geometry',
        'registration': registration, 'user_acceptance': 'pending', 'pixel_replay': False,
    })
    files['README.txt'] = (
        b'Painted-scene terrain. Open index.html offline. Collision from world.json only; '
        b'terrain.png is the registered painting. Diagnostic unless provenance approves.\n'
    )
    for n in SOURCES:
        files['source/' + n] = (ROOT / n).read_bytes()
    files['source/rebuild.py'] = (
        b"import sys,json\nfrom pathlib import Path\nfrom hybrid_artifact import build_scene\n"
        b"from hybrid_package import rebuild_extension\n"
        b"d=Path(__file__).resolve().parents[1]\nout=Path(sys.argv[1])\n"
        b"if out.exists():raise ValueError('Destination must not exist')\n"
        b"provenance=json.loads((d/'production-extension.json').read_bytes())['base_provenance'] "
        b"if (d/'production-extension.json').exists() else json.loads((d/'provenance.json').read_bytes())\n"
        b"build_scene(out,json.loads((d/'world.json').read_bytes()),(d/'provider-original.png').read_bytes(),provenance)\n"
        b"rebuild_extension(d,out)\n"
    )
    return _seal(d, files)


def _seal(d, files):
    files['checksums.json'] = canonical({n: digest(b) for n, b in files.items()})
    for n, b in files.items():
        (d / n).parent.mkdir(parents=True, exist_ok=True)
        (d / n).write_bytes(b)
    archive = d / 'diagnostic.zip'
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as z:
        for n, b in sorted(files.items()):
            info = zipfile.ZipInfo(n, (2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(info, b)
    with zipfile.ZipFile(archive) as z:
        if z.testzip():
            raise ValueError('ZIP CRC fehlgeschlagen')
        for n, h in json.loads(z.read('checksums.json')).items():
            if digest(z.read(n)) != h:
                raise ValueError('ZIP SHA fehlgeschlagen')
    return archive
