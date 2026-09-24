"""Loopback API factory; import never initializes production storage."""
import io,json,base64,re,os,time,zipfile
from pathlib import Path
from urllib.parse import urlparse
from typing import Literal
from fastapi import FastAPI,HTTPException,Request
from fastapi.responses import HTMLResponse,Response,JSONResponse
from pydantic import Field
from PIL import Image
from artifacts import canonical,digest
from hybrid_layout import Strict,compile_layout
from hybrid_models import OpenRouter,MaterialImage,Plan
from hybrid_artifact import ROOT,ACTOR,verify_artifact
from hybrid_worker import Worker,default_store,immutable,authorization,runtime_version

class Constraints(Strict):
    width:int=Field(default=18,ge=4,le=28)
    height:int=Field(default=16,ge=4,le=28)
    actor_width:float=Field(default=.64,ge=.2,le=2)
class TokenGroup(Strict):
    max_tokens:int=Field(ge=8192,le=65536)
    reasoning_effort:Literal['none','low','medium','high']

class TokenPolicy(Strict):
    planner:TokenGroup|None=None
    layout_review:TokenGroup|None=None
    extraction:TokenGroup|None=None
    review:TokenGroup|None=None

class Start(Strict):
    mode:Literal['live','replay']='live'
    description:str=Field(min_length=3,max_length=5000)
    reference_sha256:str|None=None
    reference_original_sha256:str|None=None
    layout_contract:Literal['flat-pond-path-plateau/1']|None=None
    constraints:Constraints=Field(default_factory=Constraints)
    budget_microusd:int=Field(default=0,ge=0,le=57_315_000)
    max_images:int=Field(default=3,ge=1,le=15)
    max_local_corrections:int=Field(default=2,ge=0,le=2)
    max_calls:int=Field(default=12,ge=3,le=64)
    max_seconds:int=Field(default=1800,ge=60,le=7200)
    auto_continue:bool=False
    terrain_flow:Literal['tile_board','painted_flat']='tile_board'
    confirm_paid:bool=False
    token_policy:TokenPolicy|None=None
    layout_review_iterations:int=Field(default=5,ge=1,le=5)
class Continuation(Strict):
    budget_microusd:int=Field(gt=0,le=10_000_000)
    max_seconds:int=Field(default=1800,ge=60,le=7200)
    confirm_paid:bool=False

class SourceContinuation(Continuation):
    approval_text:str=Field(min_length=10,max_length=4000)

class RepairContinuation(SourceContinuation):
    owner_style_directive:str=Field(min_length=10,max_length=2000)
    flow:Literal['board','scene_concept']='board'

class Upload(Strict):
    base64_data:str=Field(max_length=11_000_000)

def replay_layout():
    p=ROOT/'evidence/hybrid-multilevel/artifact/world.json'
    old=json.loads(p.read_bytes());mapping={'grass':'land','sand':'path','paving':'plateau','stairs':'stairs'}
    return dict(schema='hybrid-layout/1',width=old['width'],height=old['height'],actor_width=old['actor_width'],spawn=old['spawn'],goals=[[8,5]],cells=[[mapping[x] for x in row] for row in old['materials']],heights=old['heights'],transitions=old['transitions'],unsupported=[])
def models_config(store):
    path=store.g.root/'reviewer-config.json';legacy=json.loads(path.read_bytes()) if path.exists() else {}
    planner=os.environ.get('HYBRID_PLANNER_MODEL',legacy.get('model','stealth/space-bunny-alpha'))
    reviewer=os.environ.get('HYBRID_REVIEWER_MODEL','google/gemini-3.8-flash')
    # Do not silently replace a configured reviewer identity: same-model
    # deployments must fail closed rather than appear independent in readback.
    return {'planner_model':planner,'reviewer_model':reviewer}
def public_events(store,rid):
    allowed={'at','phase','call_id','role','reserved_microusd','cancel_requested','layout_frozen'}
    return [{k:v for k,v in e.items() if k in allowed} for e in store.events(rid)]
def public(store,r):
    # Exact paid request/upload URLs stay in ledger, never in browser response.
    result={k:v for k,v in r.items() if k not in ['prepared_image','metadata','prediction_id']}
    result['calls']=store.calls(r['id']);result['events']=public_events(store,r['id'])
    result['config_sha256']=digest(canonical(r['config']))
    result['held_microusd']=sum(x['amount'] for x in result['calls'])
    return result

def create_app(store=None):
    s=store or default_store();app=FastAPI(title='Autonomes Hybrid-Terrain',version='0.1-bounded');app.state.hybrid=s;worker=Worker(s)
    @app.middleware('http')
    async def guard(req,call_next):
        if req.url.hostname not in ['127.0.0.1','localhost','::1','testserver']:return JSONResponse({'detail':'Nur Loopback'},403)
        if req.headers.get('origin') and urlparse(req.headers['origin']).netloc!=req.url.netloc:return JSONResponse({'detail':'Fremder Origin'},403)
        if req.method=='POST' and len(await req.body())>12_000_000:return JSONResponse({'detail':'Request zu groß'},413)
        try:response=await call_next(req)
        except (ValueError,KeyError,FileNotFoundError):return JSONResponse({'detail':'Ungültige, fehlende oder veränderte Evidenz; kein Paid-Retry'},409)
        response.headers['Cache-Control']='no-store';response.headers['X-Content-Type-Options']='nosniff';return response
    @app.get('/',response_class=HTMLResponse)
    def index():return (ROOT/'static/hybrid.html').read_text()
    @app.get('/api/hybrid/config')
    def config():return {'models':models_config(s),'ledger':s.g.status(),'scope':'single height/XY,4..28 cells,48x24 tile,static64px actor; no bridges/buildings/props','paid_enabled':False,'authorization':'Neue serverseitige laufgebundene Freigabe erforderlich','planner_cost':'OpenRouter-Aufrufe kostenpflichtig; lokaler Compiler/Preview kostenlos'}
    @app.get('/api/hybrid/schema')
    def schema():return Plan.model_json_schema()
    @app.post('/api/hybrid/preflight')
    def preflight():
        result={};models=models_config(s)
        for role,model in models.items():
            try:
                p=OpenRouter(model);meta=p.preflight();result[role]={'model':model,'authenticated':True,'reserve_microusd':p.cost(meta)}
            except ValueError as e:result[role]={'model':model,'authenticated':False,'error':str(e)}
        try:
            p=MaterialImage();p.discover();result['image_quote']=p.quote(p.inputs('material board',['https://example.invalid/reference.png']))
        except ValueError as e:result['image_error']=str(e)
        return result
    @app.post('/api/hybrid/uploads',status_code=201)
    def upload(body:Upload):
        raw=base64.b64decode(body.base64_data,validate=True);im=Image.open(io.BytesIO(raw))
        if len(raw)>8_000_000 or im.width*im.height>8_000_000 or im.format not in ['PNG','JPEG','WEBP']:raise HTTPException(422,'Bildgrenze/Format')
        im.load();buf=io.BytesIO();im.convert('RGB').save(buf,format='PNG');normalized=buf.getvalue();sha=digest(normalized)
        immutable(s.g.root/'hybrid-uploads'/(sha+'.png'),normalized);immutable(s.g.root/'hybrid-uploads'/(digest(raw)+'.original'),raw)
        return {'sha256':sha,'original_sha256':digest(raw),'size':list(im.size),'role':'style_only'}
    @app.post('/api/hybrid-runs',status_code=201)
    def start(body:Start,req:Request):
        cfg=body.model_dump();cfg.update(models_config(s),runtime_version=runtime_version(),actor_sha256=digest((ACTOR/'character.png').read_bytes()),shadow_sha256=digest((ACTOR/'shadow.png').read_bytes()))
        if cfg['mode']=='live':
            if not cfg['confirm_paid'] or not cfg['budget_microusd']:raise HTTPException(409,'Kostenpflichtigen Planner und Laufbudget ausdrücklich bestätigen')
            if cfg.get('terrain_flow')=='painted_flat' and (cfg.get('max_calls')<3 or cfg.get('max_images')<1):raise HTTPException(422,'painted_flat benötigt Planner, Bildbearbeitung und zwei Reviews')
            sha=cfg['reference_sha256']
            if not sha or not re.fullmatch('[0-9a-f]{64}',sha) or not (s.g.root/'hybrid-uploads'/(sha+'.png')).exists():raise HTTPException(422,'Stilreferenz fehlt')
            from hybrid_reference import reference_bytes
            reference_bytes(s.g.root,cfg)
            if not all(cfg[k] for k in ['planner_model','reviewer_model']):raise HTTPException(409,'Explizite Modellkonfiguration fehlt')
            if cfg['planner_model']==cfg['reviewer_model']:raise HTTPException(409,'Layout-Reviewer muss ein unabhängiges, separates Modell verwenden')
            if cfg['max_calls']<2*cfg['layout_review_iterations']:raise HTTPException(422,'Paid-Call-Limit reicht nicht für alle genehmigten Planner/Reviewer-Runden')
        else:cfg['layout_fixture']=replay_layout();cfg['budget_microusd']=0
        return public(s,s.create(req.headers.get('Idempotency-Key'),cfg))
    @app.post('/api/hybrid-runs/{rid}/continue',status_code=201)
    def continuation(rid:str,body:Continuation,req:Request):
        if not body.confirm_paid:raise HTTPException(409,'Fortsetzung ausdrücklich bestätigen')
        from hybrid_recovery import continue_planner
        return public(s,continue_planner(s,rid,req.headers.get('Idempotency-Key'),body.budget_microusd,body.max_seconds))
    @app.post('/api/hybrid-runs/{rid}/continue-source',status_code=201)
    def source_continuation(rid:str,body:SourceContinuation,req:Request):
        if not body.confirm_paid:raise HTTPException(409,'Fortsetzung ausdrücklich bestätigen')
        from hybrid_source_recovery import continue_source
        return public(s,continue_source(s,rid,req.headers.get('Idempotency-Key'),body.budget_microusd,body.max_seconds,body.approval_text))
    @app.post('/api/hybrid-runs/{rid}/continue-material',status_code=201)
    def material_continuation(rid:str,body:SourceContinuation,req:Request):
        if not body.confirm_paid:raise HTTPException(409,'Fortsetzung ausdrücklich bestätigen')
        from hybrid_material_repair import continue_material
        return public(s,continue_material(s,rid,req.headers.get('Idempotency-Key'),body.budget_microusd,body.max_seconds,body.approval_text))
    @app.post('/api/hybrid-runs/{rid}/reassess-source',status_code=201)
    def reassess_source(rid:str,body:SourceContinuation,req:Request):
        if not body.confirm_paid:raise HTTPException(409,'Fortsetzung ausdrücklich bestätigen')
        from hybrid_reassessment import continue_archive
        return public(s,continue_archive(s,rid,req.headers.get('Idempotency-Key'),body.budget_microusd,body.max_seconds,body.approval_text))
    @app.post('/api/hybrid-runs/{rid}/continue-repair',status_code=201)
    def repair_continuation(rid:str,body:RepairContinuation,req:Request):
        if not body.confirm_paid:raise HTTPException(409,'Fortsetzung ausdrücklich bestätigen')
        from hybrid_reassessment_repair import continue_repair
        return public(s,continue_repair(s,rid,req.headers.get('Idempotency-Key'),body.budget_microusd,body.max_seconds,body.approval_text,body.owner_style_directive))
    @app.post('/api/hybrid-runs/{rid}/continue-sampling-repair',status_code=201)
    def sampling_repair_continuation(rid:str,body:SourceContinuation,req:Request):
        if not body.confirm_paid:raise HTTPException(409,'Fortsetzung ausdrücklich bestätigen')
        from hybrid_sampling_repair import continue_sampling_repair
        return public(s,continue_sampling_repair(s,rid,req.headers.get('Idempotency-Key'),body.budget_microusd,body.max_seconds,body.approval_text))
    @app.post('/api/hybrid-runs/{rid}/continue-directive',status_code=201)
    def directive_continuation(rid:str,body:RepairContinuation,req:Request):
        if not body.confirm_paid:raise HTTPException(409,'Fortsetzung ausdrücklich bestätigen')
        from hybrid_directive_repair import continue_directive
        return public(s,continue_directive(s,rid,req.headers.get('Idempotency-Key'),body.budget_microusd,body.max_seconds,body.approval_text,body.owner_style_directive,body.flow))
    @app.get('/api/hybrid-runs/{rid}/sources/{name}')
    def source_image(rid:str,name:str):
        r=s.get(rid)
        if not re.fullmatch(r'source-\d+\.png',name):raise HTTPException(404,'Unbekannte Quelle')
        sha=None
        if name==f"source-{r.get('attempt',0)}.png" and r['phase'] not in ['generating','polling']:sha=r.get('source_sha256')
        if name==r.get('previous_source'):sha=r.get('correction',{}).get('source_sha256')
        sha=sha or r['config'].get('continuation',{}).get('files',{}).get(name)
        if not sha:raise HTTPException(404,'Quelle noch nicht hashgebunden')
        raw=(worker.root/rid/name).read_bytes()
        if digest(raw)!=sha:raise ValueError('Source drift')
        return Response(raw,media_type='image/png')
    @app.get('/api/hybrid-runs')
    def runs():return [public(s,r) for r in s.list()]
    @app.get('/api/hybrid-runs/{rid}')
    def read(rid:str):return public(s,s.get(rid))
    @app.get('/api/hybrid-runs/{rid}/events')
    def events(rid:str):s.get(rid);return public_events(s,rid)
    @app.post('/api/hybrid-runs/{rid}/accept-layout')
    def accept(rid:str,body:dict):return public(s,worker.accept(rid,body))
    @app.post('/api/hybrid-runs/{rid}/preview')
    def preview(rid:str,body:dict):
        r=s.get(rid)
        if r['phase']!='layout_preview':raise HTTPException(409,'Layout bereits eingefroren')
        from hybrid_render import render,PreviewMaterials
        from hybrid_artifact import png
        w=compile_layout(body);image,*_=render(w,PreviewMaterials());return Response(png(image),media_type='image/png')
    @app.post('/api/hybrid-runs/{rid}/cancel')
    def cancel(rid:str):return public(s,s.cancel(rid))
    @app.post('/api/hybrid-runs/{rid}/resume')
    def resume(rid:str):
        r=s.get(rid)
        if r['phase']=='await_authorization':
            authorization(s,r)
            with s.g.connect() as db:db.execute("UPDATE hybrid_runs SET phase='queued' WHERE id=? AND phase='await_authorization' AND cancel=0",(rid,))
        return public(s,s.resume(rid))
    @app.get('/api/hybrid-runs/{rid}/artifacts/{name:path}')
    def artifact(rid:str,name:str):
        r=s.get(rid)
        if name=='layout-preview.png':p=worker.root/rid/name
        elif r.get('sample_directory') and name==r['sample_directory']+'/scene.png':
            verify_artifact(worker.root/rid/r['sample_directory'],r['sample_binding']);p=worker.root/rid/name
        elif re.fullmatch(r'candidate-\d+/(scene\.png|terrain\.png|index\.html|world\.json|material-binding\.json|[a-z]+-crop\.png)',name):p=worker.root/rid/name
        else:raise HTTPException(404,'Artefakt nicht freigegeben')
        media='image/png' if name.endswith('.png') else 'text/html' if name.endswith('.html') else 'application/json'
        return Response(p.read_bytes(),media_type=media,headers={'Content-Security-Policy':"default-src 'none'; img-src data:; script-src 'unsafe-inline'; style-src 'unsafe-inline'"} if name.endswith('.html') else {})
    @app.get('/api/hybrid-runs/{rid}/download')
    def download(rid:str,mode:Literal['diagnostic','production']='diagnostic'):
        r=s.get(rid)
        if mode=='production':
            from hybrid_export import production_bundle
            try:raw=production_bundle(s,r)
            except ValueError:raise HTTPException(409,'Produktionsgate fehlt/abgewiesen; Diagnose bleibt separat') from None
            return Response(raw,media_type='application/zip',headers={'Content-Disposition':f'attachment; filename="production-{rid}.zip"'})
        if not r.get('latest'):raise HTTPException(409,'Noch kein Terrain-Artefakt')
        verify_artifact(worker.root/rid/r['latest'],r.get('artifact_binding'))
        p=worker.root/rid/r['latest']/'diagnostic.zip'
        return Response(p.read_bytes(),media_type='application/zip',headers={'Content-Disposition':f'attachment; filename="diagnostic-{rid}.zip"'})
    return app
