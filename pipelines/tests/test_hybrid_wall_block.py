"""Vertical faces sample a reserved wall-texture block (brick walls), not ground."""
import io
import numpy as np
from PIL import Image

def _world():
    from hybrid_layout import compile_layout
    rows=['..........','..........','...XXX....','...XXX....','...XXX....','...SSS....','..........','..........']
    m={'.':'land','X':'plateau','S':'stairs'}
    cells=[[m[c] for c in row] for row in rows]
    heights=[[8 if cells[y][x]=='plateau' else 0 for x in range(10)] for y in range(8)]
    layout=dict(schema='hybrid-layout/1',width=10,height=8,actor_width=0.64,spawn=[2,5],goals=[[4,3]],cells=cells,
        heights=heights,transitions=[[[3,4],[3,5]],[[4,4],[4,5]],[[5,4],[5,5]]],unsupported=[])
    return compile_layout(layout)

def test_wall_block_is_painted_and_bound():
    from hybrid_painted_terrain import make_guide,bind_source,CELL_PX,COLORS,WALL_BLOCK
    w=_world()
    guide=make_guide(w)
    im=np.asarray(Image.open(io.BytesIO(guide)).convert('RGB'))
    binding=bind_source(w,guide)
    assert binding['representatives']['wall']==list(WALL_BLOCK)
    ox,oy=binding['grid']['origin']
    bx,by=WALL_BLOCK
    px0=ox+bx*CELL_PX;py0=oy+by*CELL_PX
    block=im[py0:py0+CELL_PX,px0:px0+CELL_PX]
    assert (block==np.array(COLORS['wall'])).all(axis=2).mean()>0.9,'wall block must be painted in the margin'

def test_stair_treads_sample_the_reserved_stone_block_and_alignment_ignores_stairs():
    # v26/v27 live stop: the painter kept repainting stairs cells in grass or
    # earth tones. Stair treads must sample a reserved stone block (like the
    # wall block), so stairs cells no longer need painter precision.
    from hybrid_painted_terrain import make_guide,bind_source,TerrainPixels,CELL_PX,COLORS,STAIR_BLOCK
    from test_hybrid_wall_block import _world
    w=_world();guide=make_guide(w);binding=bind_source(w,guide)
    assert binding['representatives']['stairs']==list(STAIR_BLOCK)
    im=np.array(Image.open(io.BytesIO(guide)).convert('RGB'))
    ox,oy=binding['grid']['origin'];bx,by=STAIR_BLOCK
    x0=ox+bx*CELL_PX;y0=oy+by*CELL_PX
    assert (im[y0:y0+CELL_PX,x0:x0+CELL_PX]==np.array(COLORS['stairs'])).all(axis=2).mean()>0.9
    tp=TerrainPixels(guide,binding,w)
    rgb,xy=tp.sample('stairs',np.array([.5,.5]),np.array([.5,.5]))
    px0=ox+bx*CELL_PX;py0=oy+by*CELL_PX
    assert all(px0<=int(p)<px0+CELL_PX for p in xy[:,0]) and all(py0<=int(p)<py0+CELL_PX for p in xy[:,1])
    # alignment: grass over a stairs cell is fine now (treads come from the block)
    block_origin=None
    sx,sy=next((x,y) for y,row in enumerate(w['cells']) for x,c in enumerate(row) if c=='stairs')
    b0=ox+sx*CELL_PX;c0=oy+sy*CELL_PX
    im[c0:c0+CELL_PX,b0:b0+CELL_PX]=np.array(COLORS['land'])
    buf=io.BytesIO();Image.fromarray(im).save(buf,format='PNG')
    b=bind_source(w,buf.getvalue())
    from hybrid_painted_terrain import validate_painted_source
    assert validate_painted_source(w,b,buf.getvalue())['checked_cells']>0

def test_wall_faces_sample_the_reserved_wall_block():
    from hybrid_painted_terrain import make_guide,bind_source,TerrainPixels,CELL_PX,WALL_BLOCK
    w=_world()
    guide=make_guide(w)
    binding=bind_source(w,guide)
    tp=TerrainPixels(guide,binding,w)
    ox,oy=binding['grid']['origin']
    bx,by=WALL_BLOCK
    u=np.full(5,3.5);v=-(np.arange(5)+2.0)
    _,xy=tp.sample_wall('wall',5,4,u,v,'south')
    px0=ox+bx*CELL_PX;py0=oy+by*CELL_PX
    assert all(px0<=int(p)<px0+CELL_PX for p in xy[:,0]),xy
    assert all(py0<=int(p)<py0+CELL_PX for p in xy[:,1]),xy
