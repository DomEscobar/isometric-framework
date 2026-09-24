import importlib.util
from hybrid_artifact import replay_materials,build
from hybrid_layout import compile_layout
from test_hybrid_layout import sample

def test_small_sample_is_distinct_native_source_scene(tmp_path):
    assert importlib.util.find_spec('hybrid_sampling'), 'separate material scene missing'
    from hybrid_sampling import sample_world
    w=compile_layout(sample()); sw=sample_world(w)
    assert sw['revision']!=w['revision'] and sw['width']==4
    source,binding=replay_materials()
    build(tmp_path,sw,source,binding,{'mode':'sample'})
    assert (tmp_path/'scene.png').exists()
    assert {c for row in sw['cells'] for c in row}=={'land'}

def test_local_sampling_bound_to_source_and_prior_parameters():
    import hybrid_sampling as hs
    from artifacts import canonical,digest
    import pytest
    source,binding=replay_materials()
    plan={'source_sha256':digest(source),'binding_sha256':digest(canonical(binding)),
          'materials':{'land':{'source_pixels_per_unit':binding['crops']['land']['source_pixels_per_unit'],'offset':[1,2]}}}
    assert hasattr(hs,'correct_sampling'), 'bounded local correction missing'
    corrected=hs.correct_sampling(binding,plan)
    assert corrected['crops']['land']['offset']==[1,2]
    assert corrected['crops']['land']['xywh']==binding['crops']['land']['xywh']
    assert binding['crops']['land'].get('offset') is None
    for key in ['source_sha256','binding_sha256']:
        with pytest.raises(ValueError):hs.correct_sampling(binding,{**plan,key:'0'*64})
    with pytest.raises(ValueError):hs.correct_sampling(binding,{**plan,'materials':{'land':{'source_pixels_per_unit':[513,1],'offset':[0,0]}}})
    with pytest.raises(ValueError):hs.correct_sampling(corrected,{**plan,'binding_sha256':digest(canonical(corrected))})

def test_sample_keeps_wide_actor_clear_of_water():
    from hybrid_sampling import sample_world
    raw=sample();raw['actor_width']=2.0;raw['cells'][0][5]='water'
    world=sample_world(compile_layout(raw))
    assert world['actor_width']==2.0
    assert 'water' in {c for row in world['cells'] for c in row}

