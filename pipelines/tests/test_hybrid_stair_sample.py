import json,pytest

def target():
    from hybrid_layout import compile_layout
    return compile_layout(dict(schema='hybrid-layout/1',width=6,height=6,actor_width=.64,spawn=[1,1],goals=[[1,2]],
        cells=[['land']*6,['land']*6,['land','land','path','path','path','path'],['land','land','path','path','path','path'],
               ['land','land','square','square','square','square'],['land','land','stairs','stairs','stairs','stairs']],
        heights=[[0]*6 for _ in range(6)],transitions=[],unsupported=[]))

def test_sample_world_has_functional_stair_transition_with_wall_riser():
    from hybrid_sampling import sample_world
    from hybrid_layout import compile_layout,faces
    sw=sample_world(target())
    assert sw['transitions'],'sample needs a functional height transition'
    stairs=[(x,y) for y,row in enumerate(sw['cells']) for x,c in enumerate(row) if c=='stairs']
    assert stairs
    for pair in sw['transitions']:
        (ax,ay),(bx,by)=pair
        assert 'stairs' in [sw['cells'][ay][ax],sw['cells'][by][bx]]
        assert abs(sw['heights'][ay][ax]-sw['heights'][by][bx])==8
    zs=[sw['heights'][y][x] for x,y in stairs]
    assert min(zs)==0 and max(zs)==8
    # The visible step must expose a riser face on the stair boundary.
    assert any(tuple(f['cell']) in stairs for f in faces(sw))

def test_sample_world_stair_transition_is_walkable_both_ways():
    from hybrid_sampling import sample_world
    sw=sample_world(target())
    pairs=[tuple(map(tuple,p)) for p in sw['transitions']]
    assert pairs
    for a,b in pairs:
        assert sw['graph'][f'{a[0]},{a[1]}'] and list(b) in sw['graph'][f'{a[0]},{a[1]}']
        assert list(a) in sw['graph'][f'{b[0]},{b[1]}']

def test_review_prompt_separates_guide_placeholders_and_renderer_geometry():
    source=open('hybrid_worker.py').read()
    assert 'placeholders' in source and 'never material identity' in source
    assert 'renderer builds' in source
    assert 'absence of tread/riser shapes' in source
