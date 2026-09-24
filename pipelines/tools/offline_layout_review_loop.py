"""Bounded offline compiler/structural review loop for a retained planner result."""
import io,json,hashlib,sys
from pathlib import Path
from PIL import Image
ROOT=Path('/root/services/layout-terrain-pipeline');sys.path.insert(0,str(ROOT))
from artifacts import canonical,digest
from hybrid_layout import compile_layout
from hybrid_layout_review import CRITERIA
from hybrid_render import render,PreviewMaterials
from hybrid_artifact import png


def remove_orchestration_unsupported(raw):
    clean=json.loads(json.dumps(raw));clean['unsupported']=[]
    return clean


def semantic_corrections(raw):
    cells=[list(row) for row in raw['cells']];heights=[list(row) for row in raw['heights']]
    water={(x,y) for y,row in enumerate(cells) for x,name in enumerate(row) if name=='water'}
    if water:
        minx=min(x for x,y in water);maxx=max(x for x,y in water);miny=min(y for x,y in water);maxy=max(y for x,y in water)
        cx=(minx+maxx)//2;cy=(miny+maxy)//2
        target={(x,y) for y in range(max(0,cy-1),min(len(cells),cy+2)) for x in range(max(0,cx-1),min(len(cells[0]),cx+2))}
        for x,y in target:
            if cells[y][x] in ('land','water') and heights[y][x]==0:cells[y][x]='water'
        for y,row in enumerate(cells):
            for x,name in enumerate(row):
                if name=='water' and (x,y) not in target:cells[y][x]='land'
    path={(x,y) for y,row in enumerate(cells) for x,name in enumerate(row) if name=='path'}
    rows={y for x,y in path}
    if path and len(rows)>=2 and len(path)>len(rows):
        center=sorted(rows)[len(rows)//2]
        for y,row in enumerate(cells):
            for x,name in enumerate(row):
                if name=='path' and y!=center:cells[y][x]='land'
    return {**raw,'cells':cells,'heights':heights,'unsupported':[]}


def render_candidate(raw,out):
    world=compile_layout(raw);image=png(render(world,PreviewMaterials())[0]);out.parent.mkdir(parents=True,exist_ok=True)
    if out.exists():raise FileExistsError(f'refuse overwrite: {out}')
    out.write_bytes(image)
    with Image.open(io.BytesIO(image)) as im:size=list(im.size)
    layout_sha=digest(canonical(raw));preview_sha=hashlib.sha256(image).hexdigest()
    water={(x,y) for y,row in enumerate(raw['cells']) for x,n in enumerate(row) if n=='water'}
    shore={(x,y) for y,row in enumerate(raw['cells']) for x,n in enumerate(row) if n=='land' and any((x+dx,y+dy) in water for dx,dy in ((1,0),(-1,0),(0,1),(0,-1)))}
    return {'layout':raw,'world':world,'image':image,'layout_sha256':layout_sha,'preview_sha256':preview_sha,
       'water_cells':len(water),'shore_cells':len(shore),'path_cells':sum(n=='path' for row in raw['cells'] for n in row),
       'stairs_cells':sum(n=='stairs' for row in raw['cells'] for n in row),'transition_count':len(raw['transitions']),'preview_dimensions':size}


def local_review(candidate):
    raw=candidate['layout'];w=candidate['world'];water={(x,y) for y,row in enumerate(raw['cells']) for x,n in enumerate(row) if n=='water'}
    shore={(x,y) for y,row in enumerate(raw['cells']) for x,n in enumerate(row) if n=='land' and any((x+dx,y+dy) in water for dx,dy in ((1,0),(-1,0),(0,1),(0,-1)))}
    path={(x,y) for y,row in enumerate(raw['cells']) for x,n in enumerate(row) if n=='path'};rows={y for x,y in path}
    widths={sum((x,y) in path for x in range(raw['width'])) for y in rows}
    reached={tuple(q) for q in w['reachable']};goal_reached=all(tuple(g) in reached for g in raw['goals'])
    stair={(x,y) for y,row in enumerate(raw['cells']) for x,n in enumerate(row) if n=='stairs'}
    distinct=bool(stair) and all(any(tuple(p) in stair for p in edge) for edge in raw['transitions'])
    heights_ok=all(raw['heights'][y][x]==0 for x,y in water|shore)
    findings={'water_shore':(bool(water) and bool(shore),'Add a compact water patch and flat land shore.'),
      'path_shape':(bool(path) and len(rows)==1 and widths=={1},'Use a continuous one-cell-wide straight path.'),
      'stair_visibility':(distinct,'Make one distinct stair strip at every height transition.'),
      'plateau':(any(n=='plateau' for row in raw['cells'] for n in row),'Keep one raised plateau.'),
      'walkability':(goal_reached,'Connect spawn to all goals.'),
      'height_consistency':(heights_ok,'Keep water and shoreline at base height.')}
    criteria={k:{'verdict':'pass' if ok else 'fail','observation':'Deterministic grid criterion '+('passed.' if ok else 'failed.'),'correction':'' if ok else correction} for k,(ok,correction) in findings.items()}
    return {'decision':'approve' if all(v['verdict']=='pass' for v in criteria.values()) else 'revise','criteria':criteria,
      'summary':'Free deterministic code review; NOT an independent model judgement.','layout_sha256':candidate['layout_sha256'],'preview_sha256':candidate['preview_sha256']}


def run(run_id,max_iterations=5):
    if not 1<=max_iterations<=5:raise ValueError('review loop limit must be 1..5')
    root=ROOT/'data/hybrid'/run_id;plan_path=root/'planner-result.json';plan=json.loads(plan_path.read_bytes())
    parent_unsupported=list(plan['unsupported'])+list(plan['layout']['unsupported']);parent_uncertainty=list(plan['material_plan']['uncertainty'])
    raw=remove_orchestration_unsupported(plan['layout']);raw['unsupported']=[]
    outdir=ROOT/'evidence'/'offline-layout-review'/run_id;records=[]
    for index in range(1,max_iterations+1):
        candidate_raw=raw if index==1 else semantic_corrections(raw)
        candidate=render_candidate(candidate_raw,outdir/f'iteration-{index}.png')
        local=local_review(candidate)
        approved=(local['decision']=='approve' and not parent_unsupported and not parent_uncertainty)
        records.append({'iteration':index,'max_iterations':max_iterations,'layout_sha256':candidate['layout_sha256'],'preview_sha256':candidate['preview_sha256'],
          'water_cells':candidate['water_cells'],'shore_cells':candidate['shore_cells'],'path_cells':candidate['path_cells'],'stairs_cells':candidate['stairs_cells'],
          'transition_count':candidate['transition_count'],'preview_dimensions':candidate['preview_dimensions'],'local_structural_review':local,
          'planner_unsupported_preserved':parent_unsupported,'planner_uncertainty_preserved':parent_uncertainty,
          'provider_review':'NOT CALLED','paid_calls':0,'approved_for_freeze':approved})
        if approved:break
        raw=semantic_corrections(candidate_raw)
    manifest={'run_id':run_id,'max_iterations':max_iterations,'iterations':records,
      'terminal':'offline only; no plan records changed, no API/DB writes, no model/provider calls, no image generation or freeze'}
    outdir.mkdir(parents=True,exist_ok=True);mpath=outdir/'manifest.json'
    if mpath.exists():raise FileExistsError(f'refuse overwrite: {mpath}')
    mpath.write_bytes(canonical(manifest));return manifest

if __name__=='__main__':
    if len(sys.argv)!=2:raise SystemExit('usage: offline_layout_review_loop.py RUN_ID')
    print(json.dumps(run(sys.argv[1],5),ensure_ascii=False))
