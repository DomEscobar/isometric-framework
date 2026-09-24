import importlib.util


def test_generate_deterministic_partition():
    assert importlib.util.find_spec('layout_core'), 'layout generator missing'
    from layout_core import generate, validate
    a = generate({'seed': 17})
    assert a == generate({'seed': 17})
    assert a['width'] == 16 and a['height'] == 14
    assert len(a['materials']) == 14
    assert all(len(row) == 16 for row in a['materials'])
    assert validate(a)['valid']


def test_actor_clearance_connectivity_and_invalid_geometry():
    from layout_core import generate, validate, coordinate_manifest
    import copy
    base = generate({'seed': 17})
    # A complete water barrier disconnects the required route.
    closed = copy.deepcopy(base)
    for row in closed['materials']:
        row[8] = 'water'
    assert 'disconnected_route' in validate(closed)['errors']
    # One open cell is reachable by a point, but not by a 1.2-cell actor.
    narrow = copy.deepcopy(closed)
    narrow['materials'][7][8] = 'grass'
    narrow['actor_width'] = 1.2
    assert 'disconnected_route' in validate(narrow)['errors']
    narrow['actor_width'] = 0.8
    assert validate(narrow)['valid']
    overlap = copy.deepcopy(base)
    overlap['objects'] = [dict(id='a', x=5, y=5, w=2, h=2, solid=True),
                          dict(id='b', x=6, y=6, w=2, h=2, solid=True)]
    assert 'object_overlap' in validate(overlap)['errors']
    mismatch = copy.deepcopy(base)
    mismatch['projection']['origin_px'][1] += 12
    assert 'geometry_transform_mismatch' in validate(mismatch)['errors']
    assert coordinate_manifest(base)['origin_convention'] == 'grid-vertex-0-0'
    assert validate(base)['reachable_goals'] == 1


def test_constrained_brief_and_distinct_seeded_examples():
    import pytest
    from layout_core import generate, validate
    examples = [
        {'brief': 'Wiese; Weg West-Ost; 2 Bäume', 'seed': 3},
        {'brief': 'Teich im Nordosten; Weg West-Ost; 1 Haus; 3 Bäume', 'seed': 19},
        {'brief': 'Platz; Weg Kreuz; 4 Bäume', 'seed': 81},
    ]
    layouts = [generate(p) for p in examples]
    assert len({str(a['materials']) for a in layouts}) == 3
    for p, a in zip(examples, layouts):
        assert a == generate(p)
        assert validate(a)['valid'], validate(a)
        assert a['objects']
        assert a['interpretation']['mode'] == 'exact-german-clauses-v1'
    assert layouts[0]['objects'] != generate(dict(examples[0], seed=4))['objects']
    assert any('water' in row for row in layouts[1]['materials'])
    for brief in ['Ein schöner Wald mit Bergen', 'Wiese; ohne Teich', 'Teich im Nordosten; Teich im Südwesten']:
        with pytest.raises(ValueError):
            generate({'brief': brief})
    with pytest.raises(ValueError, match='conflict'):
        generate({'brief': 'Weg Kreuz', 'path': 'west-east'})
