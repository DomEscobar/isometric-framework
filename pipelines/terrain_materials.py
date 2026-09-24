"""Paid Muse jobs: style-guided material swatches and flat surface plates.

usage: terrain_materials.py <run-dir> <style-reference.png> <flat-guide.png> [--only job,job] [--ledger path] [--paid]
Without --paid only exact quotes are printed. Every prediction id is stored before polling; a rerun resumes it.
A shared --ledger keeps one budget cap across several run directories.
"""
import json
import os
import sys
import time
from decimal import Decimal
from pathlib import Path

from provider import WaveSpeed
from terrain_llm import Ledger

ENV = Path(os.environ.get('TERRAIN_ENV_FILE', '/mnt/c/Users/dhuec/.config/layout-terrain-hybrid/environment'))
MODEL = 'meta/muse-image/edit'
MAX_USD = '0.30'
STYLE = ('Image 1 is STYLE ONLY: match its pixel-art palette, pixel clusters, outlines and lighting; never copy its '
         'layout, island, objects or camera. ')
SWATCH = (' The texture fills the whole image edge to edge with even detail, no border, frame, vignette, horizon, '
          'objects, props, characters, text or cast shadows.')
MATERIALS = {
    'grass': ('3:2', 'One seamless top-down meadow grass ground texture with small tufts and a few tiny yellow flowers.'),
    'path': ('3:2', 'One seamless top-down packed brown dirt path ground texture with small pebbles.'),
    'sand': ('3:2', 'One seamless top-down light sandy shore ground texture with a few small stones.'),
    'water': ('3:2', 'One seamless top-down calm clear pond water texture with a few small light sparkles.'),
    'stone': ('3:2', 'One seamless top-down texture of weathered grey stone step slabs laid in regular blocks.'),
    'cliff': ('21:9', 'One flat front view of a continuous natural rock-and-soil cliff wall, horizontally seamless, '
                      'with a row of overhanging grass blades along the very top edge; no perspective, no sky and no '
                      'ground in front of it.'),
    'soil': ('21:9', 'One flat front view of a continuous earthen island side edge of packed soil, small roots and '
                     'pebbles, horizontally seamless, with a thin grass fringe along the very top edge; no perspective.'),
}
FLAT = ('Image 1 is a flat-colored isometric blockout and the exact geometry authority; its colors are placeholders. '
        'Paint it with the same camera, framing and scale, keeping every region exactly where and as large as it is. '
        'Finished hand-painted pixel-art isometric game map in the style of classic handheld monster-collecting RPGs: '
        'one completely flat grassy island on a flat dark background, with the dirt path, the pond with its sandy '
        'bank and the pale stone patch exactly where drawn. Everything lies on one flat ground level: no raised ground, '
        'cliffs, terraces, walls, ledges or stairs. Soft irregular edges between grass, path and shore, small grass '
        'tufts overhanging path edges, a soil side edge around the island. No buildings, trees, bushes, fences, props, '
        'characters, text or cast shadows.')


def jobs(style_url, guide_url):
    out = {f'material-{name}': {'prompt': STYLE + text + SWATCH, 'image_urls': [style_url], 'aspect_ratio': aspect, 'output_format': 'png'}
           for name, (aspect, text) in MATERIALS.items()}
    for i in range(2):
        out[f'plate-{i}'] = {'prompt': FLAT, 'image_urls': [guide_url], 'aspect_ratio': '3:2', 'output_format': 'png'}
    return out


def main():
    run, style, guide, paid = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]), '--paid' in sys.argv
    if 'WAVESPEED_API_KEY' not in os.environ and ENV.exists():
        for line in ENV.read_text().splitlines():
            name, _, value = line.partition('=')
            if name.strip() == 'WAVESPEED_API_KEY':
                os.environ['WAVESPEED_API_KEY'] = value.strip()
    run.mkdir(parents=True, exist_ok=True)
    state_path = run / 'state.json'
    state = json.loads(state_path.read_text()) if state_path.exists() else {}
    client = WaveSpeed()
    client.model_id, client.requires_size = MODEL, False
    client.discover()
    if 'urls' not in state:
        state['urls'] = {'style': client.upload(style.read_bytes(), 'style.png'), 'guide': client.upload(guide.read_bytes(), 'guide.png')}
        state_path.write_text(json.dumps(state, indent=1))
    plan = jobs(state['urls']['style'], state['urls']['guide'])
    if '--only' in sys.argv:
        plan = {name: plan[name] for name in sys.argv[sys.argv.index('--only') + 1].split(',')}
    quotes = {name: Decimal(str(client.quote(inputs)['discounted_price'])) for name, inputs in plan.items()}
    ledger = Ledger(Path(sys.argv[sys.argv.index('--ledger') + 1]) if '--ledger' in sys.argv else run / 'ledger.jsonl', MAX_USD)
    print(json.dumps({'quotes': {k: str(v) for k, v in quotes.items()}, 'total_usd': str(sum(quotes.values())),
                      'spent_usd': str(ledger.spent()), 'cap_usd': MAX_USD}))
    if not paid:
        return
    lock = ledger.path.with_suffix('.lock')
    try:
        lock.open('x').close()
    except FileExistsError:
        raise SystemExit(f'{lock} existiert: ein anderer Lauf kauft gerade oder brach ab; erst prüfen, dann löschen')
    try:
        buy(client, run, state, state_path, plan, quotes, ledger)
    finally:
        lock.unlink()


def buy(client, run, state, state_path, plan, quotes, ledger):
    for name, inputs in plan.items():
        target = run / f'{name}.png'
        if target.exists():
            continue
        tickets = state.setdefault('predictions', {})
        if name not in tickets:
            call = ledger.reserve(name, quotes[name])
            tickets[name] = {'id': client.submit(inputs)['id'], 'call': call, 'price': str(quotes[name]), 'inputs': inputs}
            state_path.write_text(json.dumps(state, indent=1))
        ticket, deadline = tickets[name], time.time() + 600
        while (result := client.poll(ticket['id'])).get('status') != 'completed':
            if result.get('status') in ('failed', 'cancelled', 'deleted', 'timeout') or time.time() > deadline:
                raise SystemExit(f"{name}: Provider lieferte nicht ({result.get('status')}); Prediction {ticket['id']} bleibt erhalten")
            time.sleep(5)
        target.write_bytes(client.download(result['outputs'][0]))
        ledger.settle(ticket['call'], Decimal(ticket['price']), 'wavespeed:' + ticket['id'])
        print(name, 'fertig')
    print(json.dumps({'spent_usd': str(ledger.spent())}))


if __name__ == '__main__':
    main()
