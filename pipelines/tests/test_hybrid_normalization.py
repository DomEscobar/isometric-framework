import copy
import pytest
from artifacts import canonical,digest
from hybrid_layout import compile_layout
from test_hybrid_layout import sample

def test_material_wall_alias_preserves_description():
    from hybrid_recovery import normalize_material_plan
    mp={'materials':{'land':'grass','cliff_wall':'the exact cliff material'},'intent':'unchanged'}
    result=normalize_material_plan(mp,{'land','wall'})
    assert result['materials']=={'land':'grass','wall':'the exact cliff material'}
    assert 'cliff_wall' in mp['materials']
    with pytest.raises(ValueError):normalize_material_plan({'materials':{'land':'grass','wall':'stone','cliff_wall':'different'}},{'land','wall'})

def stairs():
    raw=sample();raw['heights'][2][2]=8;raw['cells'][2][2]='stairs'
    raw['transitions']=[[[1,2],[2,2]]]
    return raw

def test_reverse_duplicate_normalizes_without_mutating_authority():
    raw=stairs();expected=compile_layout(raw)
    raw['transitions'] += [[[2,2],[1,2]],[[1,2],[2,2]]]
    original=copy.deepcopy(raw)
    actual=compile_layout(raw)
    assert raw==original
    assert actual['revision']==expected['revision']
    assert actual['graph']==expected['graph']
    assert actual['normalization']['input_sha256']==digest(canonical(original['transitions']))
    assert actual['normalization']['canonical_edges']==expected['transitions']
    assert actual['normalization']['removed_count']==2

@pytest.mark.parametrize('change',['attribute','height','water','diagonal'])
def test_normalization_never_accepts_conflicting_semantics(change):
    raw=stairs();raw['transitions'].append([[2,2],[1,2]])
    if change=='attribute':raw['transitions'].append({'from':[1,2],'to':[2,2],'height':16})
    if change=='height':raw['heights'][2][2]=16
    if change=='water':raw['cells'][2][1]='water'
    if change=='diagonal':raw['transitions'].append([[1,1],[2,2]])
    with pytest.raises(ValueError):compile_layout(raw)
