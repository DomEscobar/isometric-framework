"""Bounded single-height geometry compiler. No provider, material or app side effects."""
import math
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field
from artifacts import canonical,digest

class Strict(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True,allow_inf_nan=False)
class Layout(Strict):
    schema: Literal['hybrid-layout/1']
    width:int=Field(ge=4,le=28)
    height:int=Field(ge=4,le=28)
    actor_width:float=Field(ge=.2,le=2)
    spawn:list[int]=Field(min_length=2,max_length=2)
    goals:list[list[int]]=Field(min_length=1,max_length=12)
    cells:list[list[Literal['land','water','path','square','plateau','stairs']]]
    heights:list[list[int]]
    transitions:list[list[list[int]]]=Field(max_length=256)
    unsupported:list[str]=Field(max_length=32)

def inside(w,p):return len(p)==2 and 0<=p[0]<w['width'] and 0<=p[1]<w['height']
def edge(w,a,b):
    return w['heights'][a[1]][a[0]]==w['heights'][b[1]][b[0]] or [list(a),list(b)] in w['transitions'] or [list(b),list(a)] in w['transitions']
def supported(w,a,b=None):
    b=b or a
    if not inside(w,a) or not inside(w,b):return False
    half=w['actor_width']/2
    x0=min(a[0],b[0])+.5-half;x1=max(a[0],b[0])+.5+half
    y0=min(a[1],b[1])+.5-half;y1=max(a[1],b[1])+.5+half
    if x0<0 or y0<0 or x1>w['width'] or y1>w['height']:return False
    cells={(x,y) for y in range(math.floor(y0),math.ceil(y1)) for x in range(math.floor(x0),math.ceil(x1))}
    if any(w['cells'][y][x]=='water' for x,y in cells):return False
    return all(edge(w,p,q) for p in cells for q in [(p[0]+1,p[1]),(p[0],p[1]+1)] if q in cells)
def allowed(w,a,b):return abs(a[0]-b[0])+abs(a[1]-b[1])==1 and supported(w,a,b)
def faces(w):
    out=[]
    for y,row in enumerate(w['heights']):
        for x,z in enumerate(row):
            for side,dx,dy in [('east',1,0),('south',0,1)]:
                n=x+dx,y+dy;lo=w['heights'][n[1]][n[0]] if inside(w,n) else -5
                if z>lo:out.append(dict(cell=[x,y],side=side,height=z,bottom=lo))
    return out

def compile_layout(raw):
    w=Layout.model_validate(raw).model_dump()
    if w['unsupported']:raise ValueError('Nicht unterstützt: '+', '.join(w['unsupported']))
    W,H=w['width'],w['height']
    for field in ['cells','heights']:
        if len(w[field])!=H or any(len(row)!=W for row in w[field]):raise ValueError('Rechteckige Rastergröße falsch')
    if any(z<0 or z>64 or z%8 for row in w['heights'] for z in row):raise ValueError('Höhen nur 0..64 in 8px-Stufen')
    for y,row in enumerate(w['cells']):
        for x,c in enumerate(row):
            if c=='water' and w['heights'][y][x]!=0:raise ValueError('Nur Wasser auf Ebene 0 unterstützt')
    original_transitions=w['transitions']
    seen=set();normalized=[]
    for pair in w['transitions']:
        if len(pair)!=2 or any(not inside(w,p) for p in pair):raise ValueError('Ungültiger Übergang')
        a,b=pair;key=tuple(sorted(map(tuple,pair)))
        if key not in seen:normalized.append([list(p) for p in key])
        seen.add(key)
        if abs(a[0]-b[0])+abs(a[1]-b[1])!=1 or abs(w['heights'][a[1]][a[0]]-w['heights'][b[1]][b[0]])!=8:raise ValueError('Treppe nur kardinal, 8px je Stufe')
        if 'stairs' not in [w['cells'][p[1]][p[0]] for p in pair] or any(w['cells'][p[1]][p[0]]=='water' for p in pair):raise ValueError('Übergang benötigt Treppenfläche; kein Wasser '+str(pair))
    w['transitions']=normalized
    if any(not inside(w,p) or not supported(w,p) for p in [w['spawn'],*w['goals']]):raise ValueError('Spawn/Ziel hat keinen vollständigen Actor-Support')
    graph={f'{x},{y}':[[x+dx,y+dy] for dx,dy in [(1,0),(-1,0),(0,1),(0,-1)] if allowed(w,[x,y],[x+dx,y+dy])] for y in range(H) for x in range(W)}
    reachable={tuple(w['spawn'])};stack=list(reachable)
    while stack:
        p=stack.pop()
        for q in graph[f'{p[0]},{p[1]}']:
            if tuple(q) not in reachable:reachable.add(tuple(q));stack.append(tuple(q))
    if any(tuple(p) not in reachable for p in w['goals']):raise ValueError('Pflichtziele nicht verbunden')
    revision=digest(canonical(w));z=max(map(max,w['heights']))
    w.update(revision=revision,graph=graph,reachable=[list(p) for p in sorted(reachable)],tile=[48,24],origin=[H*24+24,z+80],canvas=[(W+H)*24+48,(W+H)*12+z+112],actor_visible_height_px=64,faces=faces(w))
    w['normalization']=dict(contract='undirected-exact-edges/1',input_edges=original_transitions,input_sha256=digest(canonical(original_transitions)),canonical_edges=normalized,canonical_sha256=digest(canonical(normalized)),removed_count=len(original_transitions)-len(normalized))
    return w
