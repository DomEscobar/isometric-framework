import copy,pytest

def plan():
    return dict(intent='Materialien fuer ein Dorf',materials={'land':'Gras','water':'Wasser','wall':'Mauer'},avoid=[],uncertainty=[])

def test_wall_alias_normalizes_without_loosening_contract():
    from hybrid_recovery import normalize_material_plan
    required={'land','water','wall'}
    p=plan();p['materials']['walls']=p['materials'].pop('wall')
    before=copy.deepcopy(p)
    out=normalize_material_plan(p,required)
    assert set(out['materials'])==required and out['materials']['wall']=='Mauer'
    assert out['materials'].get('walls') is None
    assert p==before
    # cliff_wall alias keeps working.
    p2=plan();p2['materials']['cliff_wall']=p2['materials'].pop('wall')
    assert set(normalize_material_plan(p2,required)['materials'])==required
    # Ambiguous or genuinely missing semantics still fail closed.
    with pytest.raises(ValueError):
        p3=plan();p3['materials']['walls']='zweite Mauer'
        normalize_material_plan(p3,required)
    with pytest.raises(ValueError):
        p4=plan();p4['materials'].pop('wall')
        normalize_material_plan(p4,required)
    with pytest.raises(ValueError):
        normalize_material_plan(plan(),required|{'stairs'})
