import io
import numpy as np
import pytest
from PIL import Image
from artifacts import digest
from test_hybrid_layout import sample
from hybrid_layout import compile_layout


def painted_world():
    raw=sample()
    raw['cells'][0][0]='path'
    raw['cells'][4][5]='water'
    return compile_layout(raw)


def test_semantic_probe_rejects_path_to_water_and_path_to_stairs_swaps():
    from hybrid_painted_terrain import make_guide, bind_source, validate_painted_source, CELL_PX
    world=painted_world();guide=make_guide(world);base=bind_source(world,guide)
    image=Image.open(io.BytesIO(guide)).convert('RGB');ox,oy=base['grid']['origin'];cell=base['grid']['cell_px']
    for substitute in ('water','stairs'):
        test=image.copy();pixels=test.load()
        name=world['cells'][0][0];assert name=='path'
        for yy in range(oy,oy+cell):
            for xx in range(ox,ox+cell):pixels[xx,yy]=__import__('hybrid_painted_terrain').COLORS[substitute]
        out=io.BytesIO();test.save(out,'PNG');source=out.getvalue();binding=bind_source(world,source)
        if substitute=='water':
            with pytest.raises(ValueError,match='semantic alignment'):
                validate_painted_source(world,binding,source)
        else:
            # warm-family swap (path <-> stairs): texture-level, accepted by
            # the family alignment; materials stay separated by grid position
            assert validate_painted_source(world,binding,source)['checked_cells']>0

def test_flat_paint_prompt_treats_stairs_as_flat_material_not_geometry():
    from hybrid_painted_terrain import prompt
    from hybrid_layout import compile_layout
    raw=sample();raw['cells'][0][0]='stairs';raw['heights'][0][0]=0
    world=compile_layout(raw)
    text=prompt(world)
    assert 'all stair treads, risers and walls are rendered later' in text
    assert 'stairs: flat pale stone tread material only' in text

def test_flat_water_layout_derives_and_binds_sandy_shore_cells():
    from hybrid_painted_terrain import make_guide, bind_source, COLORS, semantic_regions
    world=painted_world();guide=make_guide(world);binding=bind_source(world,guide)
    water={(x,y) for y,row in enumerate(world['cells']) for x,name in enumerate(row) if name=='water'}
    expected={(x,y) for y,row in enumerate(world['cells']) for x,name in enumerate(row)
              if name=='land' and any((x+dx,y+dy) in water for dx,dy in ((1,0),(-1,0),(0,1),(0,-1)))}
    assert set(map(tuple,binding['shore_cells']))==expected
    im=Image.open(io.BytesIO(guide)).convert('RGB')
    ox,oy=binding['grid']['origin'];cell=binding['grid']['cell_px']
    for x,y in expected:
        assert im.getpixel((ox+x*cell+cell//2,oy+y*cell+cell//2))==COLORS['shore']

def test_painted_prompt_carries_alignment_repair_feedback():
    from hybrid_painted_terrain import prompt
    world=painted_world()
    assert 'CORRECTIVE REPAINT' not in prompt(world)
    text=prompt(world,'stairs at [12, 6] was painted in the wrong material category')
    assert 'CORRECTIVE REPAINT: stairs at [12, 6]' in text and 'keep every other cell identical' in text
    # v28 review fail: the painter leaked building fragments and lily pads
    assert 'lily pads' not in prompt(world)
    assert 'architecture fragments' in prompt(world) and 'never as texture hints' in prompt(world)


def test_painted_alignment_accepts_plurality_with_split_distractors():
    # v24 live stop: lush grass scattered between land/plateau/shore greens
    # pushed cells under the 50% rule. The expected category only needs the
    # LARGEST share (plurality); a real flip must still fail.
    from hybrid_painted_terrain import make_guide,bind_source,validate_painted_source,COLORS,CELL_PX
    world=painted_world()
    lx,ly=next((x,y) for y,row in enumerate(world['cells']) for x,c in enumerate(row) if c=='land')
    guide=make_guide(world)
    im=np.array(Image.open(io.BytesIO(guide)).convert('RGB'))
    ox,oy=bind_source(world,guide)['grid']['origin']
    x0=ox+lx*CELL_PX;y0=oy+ly*CELL_PX
    block=im[y0:y0+CELL_PX,x0:x0+CELL_PX]
    land=np.array(COLORS['land']);plateau=np.array(COLORS['plateau']);square=np.array(COLORS['square'])
    block[:]=land
    block[:17,:]=plateau      # 35% distractor
    block[17:27,:]=square     # 21% distractor; land keeps 45% = plurality
    buf=io.BytesIO();Image.fromarray(im).save(buf,format='PNG')
    b=bind_source(world,buf.getvalue())
    assert validate_painted_source(world,b,buf.getvalue())['checked_cells']>0
    block[14:,:]=square         # warm family 71% > green 29%: family flip
    buf=io.BytesIO();Image.fromarray(im).save(buf,format='PNG')
    b=bind_source(world,buf.getvalue())
    try:
        validate_painted_source(world,b,buf.getvalue())
    except ValueError as e:
        assert 'alignment' in str(e)
    else:
        raise AssertionError('plurality flip must fail')


def test_painted_alignment_uses_whole_cell_proportions():
    # v23 live stop: land at [9,4] held ~64% land-colored pixels but failed
    # the 5/9 point probes on painted detail noise. The gate's stated intent
    # is color PROPORTIONS, so the whole cell must decide.
    from hybrid_painted_terrain import make_guide,bind_source,validate_painted_source,COLORS,CELL_PX
    world=painted_world()
    lx,ly=next((x,y) for y,row in enumerate(world['cells']) for x,c in enumerate(row) if c=='land')
    guide=make_guide(world);binding=bind_source(world,guide)
    im=np.array(Image.open(io.BytesIO(guide)).convert('RGB'))
    ox=binding['grid']['origin'][0];oy=binding['grid']['origin'][1]
    x0=ox+lx*CELL_PX;y0=oy+ly*CELL_PX
    block=im[y0:y0+CELL_PX,x0:x0+CELL_PX]
    detail=np.array(COLORS['plateau'])
    # live failure shape: detail over 5 of 9 probe points (rows 0:8, plus two
    # corners) while land keeps 61% of the cell
    block[:8,:]=detail;block[32:,32:]=detail;block[32:,:16]=detail
    buf=io.BytesIO();Image.fromarray(im).save(buf,format='PNG')
    b2=bind_source(world,buf.getvalue())
    assert validate_painted_source(world,b2,buf.getvalue())['checked_cells']>0
    flipped=block.copy();flipped[16:,:]=np.array(COLORS['water'])  # family flip
    im[y0:y0+CELL_PX,x0:x0+CELL_PX]=flipped  # now mostly non-land
    buf=io.BytesIO();Image.fromarray(im).save(buf,format='PNG')
    b3=bind_source(world,buf.getvalue())
    try:
        validate_painted_source(world,b3,buf.getvalue())
    except ValueError as e:
        assert 'alignment' in str(e)
    else:
        raise AssertionError('flipped cell must fail')


def test_sampled_shoreland_draws_from_sandy_shore_pixels():
    from hybrid_painted_terrain import make_guide,bind_source,TerrainPixels,COLORS
    world=painted_world();raw=make_guide(world);binding=bind_source(world,raw);mat=TerrainPixels(raw,binding,world)
    x,y=binding['shore_cells'][0]
    rgb,coords=mat.sample('land',np.array([x+.5]),np.array([y+.5]))
    im=np.asarray(Image.open(io.BytesIO(raw)).convert('RGB'))
    sx,sy=coords[0]
    assert tuple(rgb[0])==COLORS['shore']
    assert tuple(im[sy,sx])==COLORS['shore']


def test_water_material_prompt_cannot_reintroduce_depressed_geometry():
    from hybrid_painted_terrain import prompt
    text=prompt(painted_world()).lower()
    assert 'flat water surface' in text
    assert 'no basin or depression' in text

def test_flat_paint_prompt_matches_supported_canvas_dimensions():
    from hybrid_painted_terrain import prompt, GUIDE_SIZE
    text=prompt(painted_world())
    assert f'{GUIDE_SIZE[0]}x{GUIDE_SIZE[1]}' in text

def test_layout_becomes_flat_semantic_image_guide_with_exact_world_grid():
    from hybrid_painted_terrain import GUIDE_SIZE, CELL_PX, make_guide, COLORS
    world=painted_world()
    raw=make_guide(world)
    image=np.array(Image.open(io.BytesIO(raw)).convert('RGB'))
    assert image.shape[:2]==(GUIDE_SIZE[1],GUIDE_SIZE[0])==(1608,2294)
    assert CELL_PX==48
    x0=(GUIDE_SIZE[0]-world['width']*CELL_PX)//2
    y0=(GUIDE_SIZE[1]-world['height']*CELL_PX)//2
    for y,row in enumerate(world['cells']):
        for x,name in enumerate(row):
            px=x0+x*CELL_PX+CELL_PX//2
            py=y0+y*CELL_PX+CELL_PX//2
            regions=__import__('hybrid_painted_terrain').semantic_regions(world)
            category='shore' if [x,y] in regions.get('shore',[]) else name
            assert tuple(image[py,px])==__import__('hybrid_painted_terrain').COLORS[category]
    assert {c for row in world['cells'] for c in row} <= set(COLORS)
    from hybrid_layout import compile_layout
    tall=sample();tall['height']=28;tall['cells']=[['land']*6 for _ in range(28)];tall['heights']=[[0]*6 for _ in range(28)];tall=compile_layout(tall)
    assert Image.open(io.BytesIO(make_guide(tall))).size==GUIDE_SIZE
    assert {'land','path','water'} <= {c for row in world['cells'] for c in row}


def test_image_edit_output_is_bound_to_exact_layout_and_canvas():
    from hybrid_painted_terrain import GUIDE_SIZE, make_guide, bind_source
    world=painted_world();src=make_guide(world)
    binding=bind_source(world,src)
    assert binding['mode']=='flat-terrain-image/1'
    assert binding['layout_revision']==world['revision']
    assert binding['source_sha256']==digest(src)
    assert binding['grid']['cell_px']==48
    assert binding['grid']['width']==world['width'] and binding['grid']['height']==world['height']
    wrong=io.BytesIO();Image.new('RGB',(GUIDE_SIZE[0]-1,GUIDE_SIZE[1])).save(wrong,'PNG')
    with pytest.raises(ValueError,match='canvas'):
        bind_source(world,wrong.getvalue())


def test_semantic_cell_color_identity_must_match_the_frozen_layout():
    from hybrid_painted_terrain import make_guide, bind_source, validate_painted_source, CELL_PX
    world=painted_world();guide=make_guide(world);binding=bind_source(world,guide)
    assert validate_painted_source(world,binding,guide)['checked_probes']==world['width']*world['height']*CELL_PX*CELL_PX
    image=Image.open(io.BytesIO(guide)).convert('RGB');pixels=image.load()
    ox,oy=binding['grid']['origin'];cell=binding['grid']['cell_px']
    # Paint a whole path cell as water: must not pass under the frozen layout labels.
    x,y=0,0;water=__import__('hybrid_painted_terrain').COLORS['water']
    for yy in range(oy+y*cell,oy+(y+1)*cell):
        for xx in range(ox+x*cell,ox+(x+1)*cell):pixels[xx,yy]=water
    bad=io.BytesIO();image.save(bad,'PNG');wrong=bad.getvalue();wrong_binding=bind_source(world,wrong)
    with pytest.raises(ValueError,match='semantic|alignment'):
        validate_painted_source(world,wrong_binding,wrong)


def test_renderer_samples_painted_world_pixels_not_operator_crops():
    from hybrid_painted_terrain import GUIDE_SIZE, make_guide, bind_source, TerrainPixels
    world=painted_world()
    raw=make_guide(world)
    # Give each semantic-cell center a unique actual provider pixel.
    im=Image.open(io.BytesIO(raw)).convert('RGB')
    pix=im.load();cell=48;x0=(GUIDE_SIZE[0]-world['width']*cell)//2;y0=(GUIDE_SIZE[1]-world['height']*cell)//2
    for y,row in enumerate(world['cells']):
        for x,name in enumerate(row):
            px=x0+x*cell+cell//2;py=y0+y*cell+cell//2
            pix[px,py]=(x*7%256,y*11%256,(x+y)*13%256)
    out=io.BytesIO();im.save(out,'PNG');source=out.getvalue()
    binding=bind_source(world,source)
    materials=TerrainPixels(source,binding,world)
    for y,row in enumerate(world['cells']):
        for x,name in enumerate(row):
            rgb,xy=materials.sample(name,np.array([x+.5]),np.array([y+.5]))
            assert tuple(rgb[0])== (x*7%256,y*11%256,(x+y)*13%256)
            assert xy.shape==(1,2) and xy[0,0]>=0 and xy[0,1]>=0
    assert 'crops' not in binding
