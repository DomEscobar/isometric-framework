"""Small native material assembly and conservative, bounded source-only repair."""
import copy
from hybrid_layout import compile_layout
from artifacts import canonical,digest

def correct_sampling(binding,plan):
    if set(plan)!={'source_sha256','binding_sha256','materials'} or plan['source_sha256']!=binding['source_sha256'] or plan['binding_sha256']!=digest(canonical(binding)):
        raise ValueError('Lokale Korrektur: Source-/Samplingbindung falsch')
    out=copy.deepcopy(binding)
    if not plan['materials'] or not set(plan['materials'])<=set(binding['crops']):raise ValueError('Unbekanntes lokales Material')
    for name,p in plan['materials'].items():
        if set(p)!={'source_pixels_per_unit','offset'}:raise ValueError('Nur Sampling/Offset erlaubt')
        c=out['crops'][name];su=p['source_pixels_per_unit'];offset=p['offset'];w,h=c['xywh'][2:]
        if len(su)!=2 or len(offset)!=2 or any(type(v)!=int for v in su+offset):raise ValueError('Sampling muss ganzzahlig sein')
        if any(not 1<=v<=512 for v in su) or any(not 0<=v<limit for v,limit in zip(offset,[w,h])):raise ValueError('Sampling außerhalb Grenzen')
        if any(not old/2<=new<=old*2 for old,new in zip(c['source_pixels_per_unit'],su)):raise ValueError('Lokale Skalierung maximal Faktor2')
        c.update(source_pixels_per_unit=su,offset=offset)
    if all(out['crops'][n]['source_pixels_per_unit']==binding['crops'][n]['source_pixels_per_unit'] and out['crops'][n]['offset']==binding['crops'][n].get('offset',[0,0]) for n in plan['materials']):raise ValueError('Sampling unverändert')
    return out


def sample_world(world):
    names=sorted({c for row in world['cells'] for c in row})
    ground=next(n for n in names if n!='water')
    width=5 if world['actor_width']>1 else 4
    cells=[[ground]*width for _ in range(max(4,len(names)*2))]
    for i,name in enumerate(names):
        cells[i*2][-2:]=[name]*2
        cells[i*2+1][-2:]=[name]*2
    heights=[[0]*width for _ in cells]
    # A raised swatch exposes both wall light directions, without changing target geometry.
    for y in range(2):
        if cells[y][-1]!='water':heights[y][-1]=8
    transitions=[]
    if 'stairs' in names:
        # Functional stair step: far stair row raised, near row low; the renderer
        # draws the riser face from the wall material. Stairs geometry is real.
        i=names.index('stairs');far=i*2;near=i*2+1
        for x in [width-2,width-1]:
            heights[far][x]=8;transitions.append([[x,far],[x,near]])
    return compile_layout(dict(schema='hybrid-layout/1',width=width,height=len(cells),actor_width=world['actor_width'],spawn=[1,1],goals=[[1,2]],cells=cells,heights=heights,transitions=transitions,unsupported=[]))
