"""Vertical face sampling must sweep texture rows, not freeze one row per column."""

def _painted():
    from hybrid_painted_terrain import make_guide,bind_source,TerrainPixels
    from hybrid_layout import compile_layout
    from test_hybrid_layout import sample
    w=compile_layout(sample())
    guide=make_guide(w)
    return w,guide,bind_source(w,guide)

def test_wall_sampling_sweeps_texture_rows_down_the_face():
    import numpy as np
    from hybrid_painted_terrain import TerrainPixels
    w,guide,binding=_painted()
    tp=TerrainPixels(guide,binding,w)
    x,y=binding['representatives']['land']
    u=np.full(8,float(x)+0.5)
    v=-(np.arange(8)+10)  # face heights stepping one screen row apart
    _,xy=tp.sample_wall('wall',x,y,u,v,'south')
    assert len({int(q) for q in xy[:,1]})>=6,('vertical texture must move down the face',xy[:,1])

def test_stair_risers_and_flanks_use_wall_sampling():
    # Risers painted with the top sampler freeze texture rows into stripes;
    # they must use the wall sampler like every other vertical face.
    import numpy as np
    from hybrid_painted_terrain import make_guide,bind_source,TerrainPixels
    from hybrid_layout import compile_layout
    from hybrid_render import render
    from test_hybrid_render_stairs import _stair_world
    w=_stair_world()
    guide=make_guide(w);binding=bind_source(w,guide)
    calls=[]
    tp=TerrainPixels(guide,binding,w)
    class Spy:
        binding=tp.binding
        def sample(self,name,u,v):return tp.sample(name,u,v)
        def sample_wall(self,name,x,y,u,v,side):
            calls.append((name,x,y,side));return tp.sample_wall(name,x,y,u,v,side)
    render(w,Spy())
    # fixture stair cells are x=3..5,y=5 with visible south/east skirts+risers
    assert any(c[1:3]==(5,5) for c in calls),('stair flank must sample as wall',calls[:10])
