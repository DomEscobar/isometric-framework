"""Description -> TerrainSpec by a language model; code rejects geometry and feeds its issues back."""
import json

from pydantic import ValidationError

from terrain_spec import TerrainSpec
from terrain_validate import check

MAX_ATTEMPTS = 3


class IntentError(ValueError):
    def __init__(self, history):
        super().__init__('Keine gültige TerrainSpec nach %d Versuchen: %s' % (len(history), '; '.join(history[-1]['issues'])))
        self.history = history


def intent_prompt(description, width, height, issues=(), previous=None):
    prompt = (
        f'Translate the terrain description into one TerrainSpec JSON object for a {width}x{height} cell grid '
        f'(width={width}, height={height}). Coordinates are integer cells: x is the column 0..{width - 1}, y is the row '
        f'0..{height - 1}. In the isometric view (0,0) is the top corner, x grows towards the lower right edge and y '
        'towards the lower left edge, so the lower left of the view has small x and large y, the upper right has '
        'large x and small y. Ponds are water rectangles; the service rounds their shoreline. Keep at least one '
        'land cell between a pond and the grid border, any plateau, its stairs and other ponds. Plateaus are raised '
        'rectangles, each level one full tile height high (at most 2 levels); their stairs flight leaves the given '
        'side outwards with three cells per level and must fit on free land. Paths are waypoint lists; the service routes them one cell wide between the '
        'waypoints, so waypoints only express the intended course. A path whose first waypoint lies on an earlier '
        'path is a branch. Paths may climb a plateau only over its stairs. Spawn and goals are walkable cells; put '
        'goals where the description wants the player to arrive. Model only features the description asks for; '
        'buildings, trees and props are not representable and must be left out. Return JSON only.\n'
        'DESCRIPTION:\n' + description)
    if issues:
        prompt += ('\nTHE PREVIOUS SPEC WAS REJECTED BY THE GEOMETRY CHECK. Fix exactly these issues and keep '
                   'everything else:\n- ' + '\n- '.join(issues) + '\nPREVIOUS SPEC:\n' + json.dumps(previous, sort_keys=True))
    return prompt


def _validate(raw, width, height):
    try:
        spec = TerrainSpec.model_validate(raw)
    except ValidationError as error:
        return None, None, ['.'.join(map(str, e['loc'])) + ': ' + e['msg'] for e in error.errors()]
    if (spec.width, spec.height) != (width, height):
        return None, None, [f'width/height müssen {width}x{height} sein']
    world, issues = check(spec)
    return spec, world, issues


def plan_terrain(description, width, height, model, ledger, attempts=MAX_ATTEMPTS):
    """Returns (spec, compiled world, history) or raises IntentError with every attempt and its issues."""
    history, issues, previous = [], [], None
    for attempt in range(1, attempts + 1):
        raw, _ = model.complete(ledger, f'intent-{attempt}', intent_prompt(description, width, height, issues, previous),
                                TerrainSpec.model_json_schema())
        spec, world, issues = _validate(raw, width, height)
        history.append({'attempt': attempt, 'spec': raw, 'issues': issues})
        if world is not None:
            return spec, world, history
        previous = raw
    raise IntentError(history)
