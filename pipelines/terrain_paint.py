"""Whole-scene painting from the guide alone: a style reference leaks its layout, so none is sent."""
import time
from decimal import Decimal

from hybrid_painted_scene import _inventory_text
from provider import WaveSpeed

MODEL = 'meta/muse-image/edit'
ASPECT_RATIO = '3:2'
POLL_SECONDS = 600
FAILED = ('failed', 'cancelled', 'deleted', 'timeout')


def paint_prompt(world, correction=None):
    """Without correction: paint image 1. With correction: image 2 is the rejected painting and is edited, not redrawn."""
    task = ('Image 2 is a previous painting of image 1 that was rejected. Edit image 2: keep its style, framing and every '
            'correct region unchanged and fix only these findings so that it matches image 1: ' + correction + ' ') if correction else ''
    return (task + 'Image 1 is a flat-colored isometric blockout and the exact geometry authority; its colors are placeholders. '
            'Paint it with the same camera, framing and scale, keeping every region exactly where and as large as it is. '
            'Finished hand-painted pixel-art isometric game map in the style of classic handheld monster-collecting RPGs, '
            '2:1 isometric camera, one small natural grassy terrain island on a flat dark background. It contains '
            + _inventory_text(world) + ': a one-tile-wide dirt path, water with a natural sandy bank, raised grassy '
            'ground with a natural rock-and-soil cliff face exactly as high as drawn and clear individual stone stair '
            'steps exactly where drawn. Soft irregular edges between grass, path and shore, small grass tufts '
            'overhanging path edges, a soil side edge around the island. No buildings, trees, bushes, fences, props, '
            'characters, text or cast shadows. Paths on raised ground lie flush on its top, never sunken.')


class ScenePainter:
    """One purchased image per submit. The caller persists the returned ticket before collect, so a restart never re-buys."""
    model = MODEL

    def __init__(self, client=None):
        self.client = client or WaveSpeed()
        self.client.model_id = MODEL
        self.client.requires_size = False

    def submit(self, ledger, role, world, guide, correction=None, rejected=None):
        if bool(correction) != bool(rejected):
            raise ValueError('Korrektur braucht das abgelehnte Bild und umgekehrt')
        self.client.discover()
        urls = [self.client.upload(guide, 'guide.png')] + ([self.client.upload(rejected, 'rejected.png')] if rejected else [])
        inputs = {'prompt': paint_prompt(world, correction), 'image_urls': urls, 'aspect_ratio': ASPECT_RATIO, 'output_format': 'png'}
        price = Decimal(str(self.client.quote(inputs)['discounted_price']))
        call = ledger.reserve(role, price)
        return {'call': call, 'price': str(price), 'id': self.client.submit(inputs)['id']}

    def collect(self, ledger, ticket):
        deadline = time.time() + POLL_SECONDS
        while (result := self.client.poll(ticket['id'])).get('status') != 'completed':
            if result.get('status') in FAILED or time.time() > deadline:
                raise ValueError(f"Maler lieferte nicht ({result.get('status')}); Prediction {ticket['id']} bleibt erhalten")
            time.sleep(5)
        if len(result.get('outputs', [])) != 1:
            raise ValueError('Maler lieferte nicht genau ein Bild')
        raw = self.client.download(result['outputs'][0])
        ledger.settle(ticket['call'], Decimal(ticket['price']), 'wavespeed:' + ticket['id'])
        return raw
