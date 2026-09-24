"""Local-only terrain workbench; server-side explicit project spending policy."""
import base64
import binascii
from functools import lru_cache
import io
import json
from pathlib import Path
import re
from typing import Literal
from urllib.parse import urlparse
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, Response, JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from PIL import Image, UnidentifiedImageError
from artifacts import RevisionStore, canonical, digest, export_bundle, export_files
from layout_core import generate, validate
from terrain import image_checks, candidate_files, bundle, render_original
from artifacts import png
import numpy as np

BASE = Path(__file__).resolve().parent


class GenerateRequest(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    width: int = Field(default=16, ge=10, le=28)
    height: int = Field(default=14, ge=10, le=28)
    seed: int = Field(default=17, ge=0, le=2147483647)
    tile_width: int = 48
    density: int = 1
    actor_width: float = Field(default=0.8, ge=0.2, le=2)
    brief: str = Field(default='', max_length=1000)
    kind: str | None = None
    path: str | None = None
    trees: int | None = None
    houses: int | None = None


class TerrainRequest(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    png_base64: str = Field(max_length=12_000_000)
    projection: dict


class RegistrationRequest(BaseModel):
    model_config = ConfigDict(extra='forbid',strict=True,allow_inf_nan=False)
    scale: float = Field(gt=0.05,le=8)
    translation: list[float] = Field(min_length=2,max_length=2)
    notes: str = Field(min_length=20,max_length=2000)


def create_app(data_dir=None, provider=None, policy=None):
    data_dir = Path(data_dir or BASE/'data')
    store = RevisionStore(data_dir/'revisions')
    imports = data_dir/'terrain'
    imports.mkdir(parents=True, exist_ok=True)
    app = FastAPI(title='Layout / Terrain — local technical workbench',version='0.1.0')

    @app.middleware('http')
    async def local_guard(request: Request, call_next):
        # No permissive CORS; reject foreign browser origins and DNS rebinding hosts.
        host = request.url.hostname
        if host not in ('127.0.0.1','localhost','::1','testserver'):
            return JSONResponse({'detail':'local hosts only'},status_code=403)
        origin = request.headers.get('origin')
        if origin and urlparse(origin).netloc != request.url.netloc:
            return JSONResponse({'detail':'foreign origin rejected'},status_code=403)
        if request.method == 'POST':
            body = await request.body()
            if len(body) > 13_000_000:
                return JSONResponse({'detail':'request too large'},status_code=413)
        response = await call_next(request)
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Cache-Control'] = 'no-store'
        return response

    def load(rid):
        try:
            return store.load(rid)
        except FileNotFoundError:
            raise HTTPException(404,'revision not found')
        except ValueError as exc:
            raise HTTPException(422,str(exc))

    @lru_cache(maxsize=4)
    def cached_files(rid):
        return export_files(load(rid))

    def representation(rid,layout):
        return dict(revision=rid,immutable=True,layout=layout,validation=validate(layout))

    @app.get('/',response_class=HTMLResponse)
    def index():
        ui = BASE/'static/index.html'
        return ui.read_text() if ui.exists() else '<h1>Technischer Blockout — keine finale Grafik</h1>'

    @app.get('/workflows.js')
    def workflows():
        return Response((BASE/'static/workflows.js').read_bytes(),media_type='application/javascript')

    @app.get('/api/capabilities')
    def capabilities():
        return dict(paid_generation=app.state.generation.status()['enabled'],terrain_provider='wavespeed adapter; approval is candidate-specific, never implied by provider completion',arbitrary_language=False,
                    scope='one bounded flat map; technical guide, reservations and cardinal square-actor navigation',
                    clauses=['Wiese','Platz','Teich im Nordosten','Teich im Südwesten','Weg West-Ost',
                             'Weg Nord-Süd','Weg Kreuz','Kein Weg','0–8 Bäume','0–1 Haus'],
                    limitations=['no height/bridges/tileset/autotiling','no production prop extents',
                                 'no image semantic or visual approval','no engine-specific adapter'])

    @app.post('/api/layouts',status_code=201)
    def create(body: GenerateRequest):
        try:
            layout = generate(body.model_dump(exclude_none=True))
            rid = store.save(layout)
        except ValueError as exc:
            raise HTTPException(422,str(exc))
        # Verify persisted bytes on the exact revision before returning success.
        return representation(rid,store.load(rid))

    @app.get('/api/layouts/{rid}')
    def read(rid: str):
        return representation(rid,load(rid))

    @app.post('/api/validate')
    def validation(body: dict):
        return validate(body)

    @app.get('/api/layouts/{rid}/download')
    def download(rid: str):
        return Response(export_bundle(load(rid)),media_type='application/zip',
                        headers={'Content-Disposition':f'attachment; filename="layout-{rid[:12]}.zip"'})

    @app.get('/api/layouts/{rid}/artifacts/{name:path}')
    def artifact(rid: str,name: str):
        load(rid)  # Integrity is rechecked even if derived bytes are cached.
        files = cached_files(rid)
        if name not in files:
            raise HTTPException(404,'artifact not found')
        return Response(files[name],media_type='image/png' if name.endswith('.png') else 'application/json' if name.endswith('.json') else 'text/plain')

    def terrain_path(tid, name):
        if not re.fullmatch('[0-9a-f]{64}',tid):
            raise HTTPException(422,'invalid terrain id')
        path = imports/tid/name
        if not path.exists():
            raise HTTPException(404,'terrain import not found')
        return path

    @app.get('/api/terrain/{tid}')
    def terrain_record(tid: str):
        record = json.loads(terrain_path(tid,'record.json').read_bytes())
        content = {k:v for k,v in record.items() if k != 'id'}
        if digest(canonical(content)) != tid or record.get('id') != tid:
            raise HTTPException(409,'terrain manifest integrity failure')
        source = terrain_path(tid,'source.png').read_bytes()
        if digest(source) != record['source_sha256']:
            raise HTTPException(409,'terrain source integrity failure')
        layout = load(record['layout_revision'])
        if record.get('guide_sha256') and digest(cached_files(record['layout_revision'])['clean-guide.png']) != record['guide_sha256']:
            raise HTTPException(409,'guide integrity failure')
        return record

    @app.get('/api/terrain/{tid}/review')
    def terrain_review(tid: str):
        candidate=terrain_record(tid);path=imports/tid/'review.json'
        if not path.exists():return dict(status='needs_attention',production_approved=False,semantic_verdict='unverified',visual_verdict='unreviewed')
        review=json.loads(path.read_bytes())
        if digest(canonical({k:v for k,v in review.items() if k!='id'}))!=review.get('id') or any(review.get(k)!=candidate.get(k) for k in ('layout_revision','source_sha256','guide_sha256')) or review.get('candidate_id')!=tid or review.get('production_approved') is not False:
            raise HTTPException(409,'review binding integrity failure')
        return review

    @app.get('/api/terrain/{tid}/download')
    def terrain_download(tid: str, revision: str, density: int = 1, mode: Literal['diagnostic','production'] = 'diagnostic', style_spec_id: str | None = None, evaluation_id: str | None = None):
        record = terrain_record(tid)
        evaluation=None
        if evaluation_id:
            try:
                evaluation=app.state.evaluations.get(evaluation_id)
                b=evaluation['binding']
                if (b['candidate_id'],b['layout_revision'],b['density'],b['style_spec_id'])!=(tid,revision,density,style_spec_id):raise ValueError('stale export binding')
            except (ValueError,KeyError,FileNotFoundError):raise HTTPException(409,'Stale candidate/style/layout/density/evidence binding') from None
        if mode=='production' and (not evaluation or not evaluation['gate']['production_approved']):
            raise HTTPException(409,'Production blocked: strict review missing, failed, uncertain or locally blocked. Diagnostic export is UNAPPROVED.')
        if revision != record['layout_revision']:
            raise HTTPException(409,'stale revision: candidate belongs to another layout')
        try:
            files = candidate_files(load(revision), record, terrain_path(tid,'source.png').read_bytes(), density)
            review=terrain_review(tid)
            if review.get('id'):
                files['review.json']=canonical(review)
                prov=json.loads(files['terrain-provenance.json']);prov.update(review_id=review['id'],visual_review=review['visual_verdict'],semantic_review=review['semantic_verdict'],review_scope='See review.json for exact reviewed resolution/hash; no production approval')
                files['terrain-provenance.json']=canonical(prov)
            origin=record.get('provider_origin')
            if origin:
                gen=app.state.generation;j=gen.get(origin['job_id']);q=gen.get_quote(j['quote_id'])
                if j['prediction_id']!=origin['prediction_id'] or j['request_sha256']!=origin['request_sha256'] or j['binding']['layout_revision']!=revision: raise ValueError('provider provenance drift')
                style=(app.state.styles.inputs(origin['style_spec_id'])[0]['raw'] if origin.get('style_spec_id') else (data_dir/'styles'/origin['style_id']/'source.png').read_bytes())
                if digest(style)!=origin['style_sha256']:raise ValueError('style source drift')
                files['sources/style-only.png']=style
                files['generation/quote.json']=canonical(q)
                files['generation/prediction-receipt.json']=(data_dir/(j['id']+'.receipt.json')).read_bytes()
                files['generation/request-provenance.json']=canonical(dict(request_sha256=j['request_sha256'],request_without_media_urls={k:v for k,v in j['request'].items() if k!='image_urls'},
                    media_roles=[dict(role='geometry_authority',sha256=j['binding']['guide_sha256'])]+([dict(role=r['role'],material=r['material'],sha256=r['input_sha256'],source_sha256=r['source_sha256'],crop=r['crop']) for r in j['binding']['style_references']] if j['binding'].get('style_references') else [dict(role='style_only',sha256=j['binding']['style_sha256'])]),
                    exact_quote=j['exact_quote'],reserved_microusd=j['reserved_microusd'],model=q['model'],job_id=j['id'],prediction_id=j['prediction_id'],
                    note='Exact request including transient remote media URLs remains server-side; exact request hash retained. Quote is not a billing receipt.'))
            sid=style_spec_id or (origin or {}).get('style_spec_id')
            if sid:
                files['style-spec.json']=canonical(app.state.styles.get(sid))
                for i,ref in enumerate(app.state.styles.inputs(sid)):
                    files[f'sources/reference-{i}.png']=ref['raw']
                    files[f'sources/reference-{i}-original.png']=(data_dir/'styles'/ref['reference_id']/'source.png').read_bytes()
            if evaluation:
                files['evaluation.json']=canonical(evaluation)
                for e in evaluation['binding']['evidence']:
                    files['review-inputs/'+e['id']+'.png']=(data_dir/'evaluations'/evaluation_id/(e['id']+'.png')).read_bytes()
            approved=mode=='production'
            prov=json.loads(files['terrain-provenance.json'])
            prov.update(export_mode=mode,production_approved=approved,style_spec_id=sid,evaluation_id=evaluation_id,user_acceptance='pending')
            files['terrain-provenance.json']=canonical(prov)
            files['README.txt']+=f'\nExport mode: {mode}. Production approved by automated gate: {approved}. Final user acceptance pending.\n'.encode()
            files['checksums.json']=canonical({n:digest(b) for n,b in sorted(files.items()) if n!='checksums.json'})
        except ValueError as exc:
            raise HTTPException(422,str(exc))
        return Response(bundle(files),media_type='application/zip',headers={'Content-Disposition':f'attachment; filename="{mode}-candidate-{tid[:12]}-d{density}.zip"','X-Production-Approved':str(mode=='production').lower()})

    @app.get('/api/terrain/{tid}/source.png')
    def terrain_source(tid: str):
        terrain_record(tid)
        return Response(terrain_path(tid,'source.png').read_bytes(),media_type='image/png')

    @app.get('/api/terrain/{tid}/preview.png')
    def terrain_preview(tid: str):
        record=terrain_record(tid)
        if record['status']=='rejected': raise HTTPException(422,'rejected candidate')
        layout=load(record['layout_revision'])
        return Response(png(np.array(render_original(layout,record,terrain_path(tid,'source.png').read_bytes(),layout['projection']['density']))),media_type='image/png')

    @app.post('/api/terrain/{tid}/register',status_code=201)
    def register_terrain(tid: str,body: RegistrationRequest):
        parent=terrain_record(tid);layout=load(parent['layout_revision'])
        if parent.get('processing_registration'): raise HTTPException(422,'register retained unprocessed original, never chain transformations')
        if any(abs(v)>max(layout['projection']['image_size']) for v in body.translation): raise HTTPException(422,'translation outside bounded frame')
        source=terrain_path(tid,'source.png').read_bytes()
        record={k:v for k,v in parent.items() if k!='id'}
        record.update(parent_candidate_id=tid,status='needs_attention',processing_registration=body.model_dump(),
                      transform='explicit uniform scale plus translation from retained original; clipped to canonical frame; NEAREST; no masking or collision changes')
        record['registration']={**record['registration'],'image_alignment':'operator_registration_unverified','output_dimensions':'canonical','decoded_dimensions':'source retained at original size'}
        files=cached_files(parent['layout_revision'])
        preview=png(np.array(render_original(layout,record,source,layout['projection']['density'])))
        record['image_checks']=image_checks(preview,files['clean-guide.png'],files)
        newid=digest(canonical(record));record['id']=newid;target=imports/newid;target.mkdir(exist_ok=True)
        for name,raw in [('source.png',source),('record.json',canonical(record))]:
            try:
                with (target/name).open('xb') as f:f.write(raw)
            except FileExistsError:
                if (target/name).read_bytes()!=raw:raise HTTPException(409,'immutable registration conflict')
        return terrain_record(newid)

    @app.post('/api/layouts/{rid}/terrain',status_code=201)
    def import_terrain(rid: str,body: TerrainRequest):
        return save_terrain(rid,body)

    def save_terrain(rid,body,provider_origin=None):
        layout = load(rid)
        try:
            source = base64.b64decode(body.png_base64,validate=True)
            with Image.open(io.BytesIO(source)) as im:
                if im.format != 'PNG' or im.width*im.height > 8_000_000:
                    raise ValueError('PNG required; maximum 8 million pixels')
                dimensions = list(im.size)
                im.verify()
        except (ValueError,binascii.Error,UnidentifiedImageError,OSError,Image.DecompressionBombError) as exc:
            raise HTTPException(422,'invalid image: '+str(exc))
        frame_ok = body.projection == layout['projection']
        size_ok = dimensions == layout['projection']['image_size']
        record = dict(layout_revision=rid,source_sha256=digest(source),decoded_size=dimensions,
                      declared_projection=body.projection,status='needs_attention' if frame_ok and size_ok else 'rejected',
                      registration=dict(declared_frame='matches' if frame_ok else 'mismatch',
                                        decoded_dimensions='matches' if size_ok else 'mismatch',image_alignment='unverified'),
                      local_semantic_compliance='not_assessed',visual_review='not_assessed',
                      production_approved=False,source='user-supplied local PNG; not provider output',
                      transform='identity declaration only; source bytes preserved; no resampling',
                      caveat='Matching metadata does not prove painted landmarks or local material boundaries align.')
        if provider_origin:
            record['source'] = 'provider output; unreviewed'
            record['provider_origin'] = provider_origin
        files = cached_files(rid)
        record['guide_sha256'] = digest(files['clean-guide.png'])
        record['image_checks'] = image_checks(source, files['clean-guide.png'], files)
        tid = digest(canonical(record))
        record['id'] = tid
        target = imports/tid
        target.mkdir(exist_ok=True)
        for name,raw in [('source.png',source),('record.json',canonical(record))]:
            try:
                with (target/name).open('xb') as f:
                    f.write(raw)
            except FileExistsError:
                if (target/name).read_bytes() != raw:
                    raise HTTPException(409,'immutable import conflict')
        return terrain_record(tid)

    from generation_api import install
    def generated_candidate(rid,raw,origin):
        return save_terrain(rid,TerrainRequest(png_base64=base64.b64encode(raw).decode(),projection=load(rid)['projection']),origin)
    install(app,data_dir,load,cached_files,generated_candidate,provider,policy)
    from evaluations import install as install_evaluations
    install_evaluations(app,terrain_record,load,cached_files,terrain_review)
    from corrections import install as install_corrections
    install_corrections(app,cached_files)
    from auto_adapter import install as install_auto
    install_auto(app,cached_files,terrain_record,load,register_terrain,app.state.resume_generation)
    from overnight_batch import install as install_overnight
    install_overnight(app,cached_files,terrain_record,load,register_terrain,app.state.resume_generation)
    return app


app = create_app()
