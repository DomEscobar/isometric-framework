"""Generate the host asset manifest (manifest.json for acceptance checks) and
art-urls.ts (?url imports for Vite builds) from one definition."""
import os, json
HOST = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def textures_from(pattern, keys):
    """1:1 image->texture for a set of frame files."""
    imgs, texs = {}, {}
    for key in keys:
        rel = pattern % key
        texs[key] = {'image': key}
        imgs[key] = {'url': f'art/{rel}'}
    return imgs, texs

def collect():
    imgs, texs, anims = {}, {}, {}
    # ---- units -----------------------------------------------------------
    models = ['witch_player', 'witch_enemy', 'fam_leaf', 'fam_ember']
    dirs = ['ne', 'se', 'sw', 'nw']
    states = ['idle0', 'idle1', 'walk0', 'walk1', 'hit', 'cast0', 'cast1']
    for model in models:
        for d in dirs:
            for st in states:
                key = f'{model}_{d}_{st}'
                imgs[key] = {'url': f'art/sprites/{key}.png'}
                texs[key] = {'image': key}
            def clip(states_used, fps, loop):
                cid = f'{model}_{d}_{"".join(states_used[0]) if False else states_used[0].rstrip("0123456789")}_{d}'
                return cid
        # build clips cleanly here
    # (cleaner: rebuild below per state group)
    models = ['witch_player', 'witch_enemy', 'fam_leaf', 'fam_ember']
    for model in models:
        for d in dirs:
            for st in states:
                key = f'{model}_{d}_{st}'
                imgs[key] = {'url': f'art/sprites/{key}.png'}
                texs[key] = {'image': key}
            for stname, frame_states, fps, loop in [
                    ('idle', ['idle0', 'idle1'], 3, True),
                    ('walk', ['walk0', 'walk1'], 6, True),
                    ('hit', ['hit'], 6, False),
                    ('cast', ['cast0', 'cast1'], 5, False)]:
                cid = f'{model}_{d}_{stname}'
                anims[cid] = {'frames': [f'{model}_{d}_{s}' for s in frame_states], 'fps': fps, 'loop': loop}
    # ---- water stream ----------------------------------------------------
    for r in range(7):
        for f in range(3):
            key = f'stream_{r}_{f}'
            imgs[key] = {'url': f'art/terrain/water_7_{r}_f{f}.png'}
            texs[key] = {'image': key}
        anims[f'stream_{r}'] = {'frames': [f'stream_{r}_{f}' for f in range(3)], 'fps': 5, 'loop': True}
    # ---- splash ------------------------------------------------------------
    for f in range(3):
        key = f'splash_{f}'
        imgs[key] = {'url': f'art/props/fountain_splash_{f}.png'}
        texs[key] = {'image': key}
    anims['splash'] = {'frames': ['splash_0', 'splash_1', 'splash_2'], 'fps': 6, 'loop': True}
    # ---- foliage ------------------------------------------------------------
    for name, path, fps in [('tree', 'tree_%d', 3), ('bush', 'bush_%d', 2.5), ('flower0', 'flowers_0_%d', 2.5),
                            ('flower1', 'flowers_1_%d', 2.5), ('flower2', 'flowers_2_%d', 2.5)]:
        for f in range(2):
            key = f'{name}_{f}'
            imgs[key] = {'url': f'art/props/{path % f}.png'}
            texs[key] = {'image': key}
        anims[f'{name}_sway'] = {'frames': [f'{name}_0', f'{name}_1'], 'fps': fps, 'loop': True}
    # ---- static props -------------------------------------------------------
    for name in ['bench', 'lamp', 'crates', 'signpost']:
        key = f'{name}_0'
        imgs[key] = {'url': f'art/props/{name}_0.png'}
        texs[key] = {'image': key}
    # ---- terrain tiles (ground + dais + step) -------------------------------
    for c in range(8):
        for r in range(7):
            key = f'tile_{c}_{r}'
            imgs[key] = {'url': f'art/terrain/tile_{c}_{r}.png'}
            texs[key] = {'image': key}
    for (c, r) in [(4, 2), (5, 2), (4, 3), (5, 3)]:
        key = f'dais_{c}_{r}'
        imgs[key] = {'url': f'art/terrain/dais_{c}_{r}.png'}
        texs[key] = {'image': key}
    imgs['step_top'] = {'url': 'art/terrain/step_top.png'}
    texs['step_top'] = {'image': 'step_top'}
    imgs['side_stone'] = {'url': 'art/terrain/side_stone.png'}
    texs['side_stone'] = {'image': 'side_stone'}
    imgs['fountain_basin'] = {'url': 'art/props/fountain_basin.png'}
    texs['fountain_basin'] = {'image': 'fountain_basin'}
    return imgs, texs, anims

def write_all():
    imgs, texs, anims = collect()
    manifest = {'images': imgs, 'textures': texs, 'animations': anims}
    with open(os.path.join(HOST, 'manifest.json'), 'w') as fh:
        json.dump(manifest, fh, indent=1, sort_keys=True)
    # art-urls.ts
    lines = []
    for key, defn in sorted(imgs.items()):
        # import key with sanitized identifier
        ident = 'i_' + ''.join(ch if ch.isalnum() else '_' for ch in key)
        lines.append(f"import {ident} from './art/{defn['url'][4:]}?url';")
    lines.append('')
    lines.append('export const assetUrls: Record<string, string> = {')
    for key in sorted(imgs):
        ident = 'i_' + ''.join(ch if ch.isalnum() else '_' for ch in key)
        lines.append(f"  {json.dumps(key)}: {ident},")
    lines.append('};')
    with open(os.path.join(HOST, 'art-urls.ts'), 'w') as fh:
        fh.write('\n'.join(lines))
    print('manifest.json:', len(json.dumps(manifest)), 'bytes; images:', len(imgs), 'textures:', len(texs), 'animations:', len(anims))

if __name__ == '__main__':
    write_all()
