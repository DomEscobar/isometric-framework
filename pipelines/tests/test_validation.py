import copy
import pytest
from layout_core import generate, validate, project


@pytest.mark.parametrize('change,error',[
    (lambda a:a.update(schema='invented'), 'schema'),
    (lambda a:a.update(materials=[{}]*14), 'material_partition'),
    (lambda a:a.update(actor_width=0), 'actor_width'),
    (lambda a:a.update(spawn=[-1,2]), 'endpoint_bounds'),
    (lambda a:a['materials'][2].__setitem__(2,'water'), 'disconnected_route'),
    (lambda a:a.update(goals=[[999,1]]), 'endpoint_bounds'),
    (lambda a:a.update(density=9), 'projection_parameters'),
])
def test_invalid_layout_rejected(change,error):
    a=generate({})
    change(a)
    report=validate(a)
    assert not report['valid']
    assert error in report['errors']


def test_house_has_reachable_reserved_approach_and_support_is_verified():
    layout=generate({'brief':'Teich im Nordosten; Weg West-Ost; 1 Haus; 3 Bäume','seed':19})
    house=next(o for o in layout['objects'] if o['kind']=='house')
    assert 'approach' in house, 'house reservation needs a reachable entrance approach'
    assert house['approach'] in layout['goals']
    assert validate(layout)['valid']
    bad=copy.deepcopy(layout)
    bad['objects'][0]['support_materials']=['water']
    assert 'object_support_mismatch' in validate(bad)['errors']
    bad=copy.deepcopy(layout)
    bad['objects'][0]['approach']=[bad['objects'][0]['x'],bad['objects'][0]['y']]
    assert 'object_approach' in validate(bad)['errors']


def test_projection_density_preserves_world_and_roundtrips():
    a=generate({'brief':'Platz; Weg Kreuz; 4 Bäume','seed':81})
    b=generate({'brief':'Platz; Weg Kreuz; 4 Bäume','seed':81,'density':2})
    assert a['materials']==b['materials'] and a['objects']==b['objects']
    assert project(a,0,0)==[360,24]
    assert project(a,1,0)==[384,36]
    assert project(a,0,1)==[336,36]
    for c,r in [(0,0),(2.5,8.5),(16,14)]:
        x,y=project(b,c,r)
        assert [v*2 for v in project(a,c,r)]==[x,y]
        dx=(x-b['projection']['origin_px'][0])/48
        dy=(y-b['projection']['origin_px'][1])/24
        assert (dx+dy)/2==c and (dy-dx)/2==r
