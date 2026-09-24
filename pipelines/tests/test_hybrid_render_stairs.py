"""Stairs must render real stepped treads, not a flat tile plus a cliff seam."""
import numpy as np

def _stair_world():
    from hybrid_layout import compile_layout
    rows=['..........','..........','...XXX....','...XXX....','...XXX....','...SSS....','..........','..........']
    m={'.':'land','X':'plateau','S':'stairs'}
    cells=[[m[c] for c in row] for row in rows]
    heights=[[8 if cells[y][x]=='plateau' else 0 for x in range(10)] for y in range(8)]
    layout=dict(schema='hybrid-layout/1',width=10,height=8,actor_width=0.64,spawn=[2,5],goals=[[4,3]],cells=cells,
        heights=heights,transitions=[[[3,4],[3,5]],[[4,4],[4,5]],[[5,4],[5,5]]],unsupported=[])
    return compile_layout(layout)

def test_transition_edges_carry_stair_risers_instead_of_cliff_faces():
    # Live review fail: an exposed vertical cliff face sat between the flat
    # stairs and the plateau. Transition edges must not draw wall faces; the
    # stair risers take over. Plain non-transition cliffs still draw.
    from hybrid_render import visible_faces
    w=_stair_world()
    visible=visible_faces(w)
    assert not [f for f in visible if f['cell']==[4,4] and f['side']=='south']
    assert [f for f in visible if f['cell']==[5,4] and f['side']=='east']

def test_stair_renders_treads_and_risers_not_a_flat_tile():
    from hybrid_render import render,PreviewMaterials
    w=_stair_world()
    image,*_=render(w,PreviewMaterials())
    rgb=image[:,:,:3].astype(int)
    base=PreviewMaterials().colors['stairs']
    dark=[c*218//255 for c in base]
    treads=((rgb==base).all(axis=2)).sum()
    risers=((rgb==dark).all(axis=2)).sum()
    assert treads>20,('treads',treads)
    assert risers>20,('risers',risers)
