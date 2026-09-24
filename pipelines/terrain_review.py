"""Visual acceptance of one painting against its guide. The model judges; code only reads its verdicts."""
from typing import Literal

from pydantic import Field

from hybrid_layout import Strict
from hybrid_painted_scene import _inventory_text

CRITERIA = ('layout', 'heights', 'clean', 'finish')
Criterion = Literal['layout', 'heights', 'clean', 'finish']


class Finding(Strict):
    criterion: Criterion
    verdict: Literal['pass', 'cosmetic', 'blocking']
    observation: str = Field(min_length=1, max_length=600)
    correction: str = Field(max_length=600, description='Concrete repaint instruction; empty when the verdict is pass')


class Review(Strict):
    findings: list[Finding] = Field(min_length=len(CRITERIA), max_length=len(CRITERIA))


def review_prompt(world):
    return (
        'Image guide is the flat technical-color blockout of a frozen collision grid (green ground, brown path, sand bank, '
        'blue water, pale stone stairs, grey-brown cliff faces); its colors are placeholders, never materials. Image final '
        'is the painted isometric game map that must match it; a player walks on final while collision follows the guide. '
        'Judge each criterion exactly once with a concrete observation. Verdict pass: no deviation. Verdict blocking: the '
        'deviation misleads the player about where they can walk or climb, for example missing, extra or clearly '
        'misplaced water, path, raised ground, cliff or stair, a stair that does not visibly join the ground below and '
        'the raised top, or any forbidden object. Verdict cosmetic: a visible deviation that leaves walkable and blocked '
        'areas readable as in the guide. For blocking and cosmetic give a concrete repaint instruction that names where '
        'in the image to change what. '
        'layout: every pond, path, branch, raised area and stair in final sits where the guide has it with the same size '
        'and course; the guide contains ' + _inventory_text(world) + ' and any extra or missing one fails. '
        'heights: each cliff face in final is about as high as in the guide and each stair climbs exactly one drawn cliff; '
        'no added terraces, walls or ledges. clean: no buildings, trees, bushes, fences, props, characters, text or cast '
        'shadows. finish: coherent pixel-art style, natural soft transitions between grass, path and shore, the path reads '
        'as one tile wide and walkable, the island has a soil side edge.')


def _text(findings):
    return ' '.join(f'{f.criterion}: {f.correction or f.observation}' for f in findings)


def verdict(review):
    """Returns (accepted, correction for the next repaint from blocking findings, cosmetic notes)."""
    by_criterion = {f.criterion: f for f in review.findings}
    if set(by_criterion) != set(CRITERIA):
        raise ValueError('Review deckt nicht jedes Kriterium genau einmal ab')
    ordered = [by_criterion[c] for c in CRITERIA]
    blocking = [f for f in ordered if f.verdict == 'blocking']
    return not blocking, _text(blocking), _text(f for f in ordered if f.verdict == 'cosmetic')


def review(model, ledger, role, world, guide, final):
    raw, _ = model.complete(ledger, role, review_prompt(world), Review.model_json_schema(), {'guide': guide, 'final': final})
    return Review.model_validate(raw)
