"""Local role-tagged references and generation HTTP stages."""
import base64
import io
import json
import re
from pathlib import Path
from typing import Literal
from fastapi import HTTPException
from fastapi.responses import Response
from pydantic import BaseModel,ConfigDict,Field
from PIL import Image
from artifacts import canonical,digest
from generation import Generation,DEFAULT_POLICY
from provider import WaveSpeed
from style_specs import Styles, StyleSpec, Preset, Hash
from pydantic import model_validator


class Strict(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)

class StyleRequest(Strict):
    png_base64: str=Field(max_length=12_000_000)
    role: Literal['style_only']

class QuoteRequest(Strict):
    model_config=ConfigDict(extra='forbid',strict=True,json_schema_extra={'examples':[{'revision':'057137d51849cde09c0d12565f3232267e1b1dee239c14e8de64bb6b6c49ffb1','style_spec_id':'d02eb595824e1632a68c50e3b201e7b27bada67f93b20bc1df0bbe60813419f5'}]})
    revision: str
    style_id: str | None = None
    prompt: str | None=Field(default=None,min_length=1,max_length=2000)
    style_spec_id: Hash | None = None
    @model_validator(mode='after')
    def exclusive(self):
        if self.style_spec_id:
            if self.style_id is not None or self.prompt is not None: raise ValueError('spec cannot be overridden by legacy fields')
        elif not self.style_id or not self.prompt: raise ValueError('style spec or legacy reference+prompt required')
        return self

class ConfirmRequest(Strict):
    quote_id: str
    revision: str
    style_spec_id: Hash | None = None


def install(app,root,load,files,import_candidate,provider=None,policy=None):
    root=Path(root); styles=root/'styles';styles.mkdir(parents=True,exist_ok=True)
    # No HTTP endpoint grants budget. Explicit project-local operator policy only.
    policy_path=root/'generation-policy.json'
    if policy is None:
        policy=json.loads(policy_path.read_bytes()) if policy_path.exists() else DEFAULT_POLICY.copy()
    gen=Generation(root,provider or WaveSpeed(),policy=policy)
    app.state.generation=gen

    def style_read(sid):
        if not re.fullmatch('[0-9a-f]{64}',sid): raise ValueError('invalid style id')
        record=json.loads((styles/sid/'record.json').read_bytes())
        raw=(styles/sid/'source.png').read_bytes()
        if digest(canonical({k:v for k,v in record.items() if k!='id'}))!=sid or digest(raw)!=record['source_sha256']:
            raise ValueError('style source/manifest integrity failure')
        return record,raw

    def guarded(fn):
        try: return fn()
        except HTTPException: raise
        except (ValueError,KeyError,FileNotFoundError):
            raise HTTPException(422,'Invalid or changed source/binding, missing quote/auth, or provider metadata unavailable; no automatic retry.') from None

    specs=Styles(gen,style_read);app.state.styles=specs
    @app.post('/api/style-specs',status_code=201)
    def spec_create(body:StyleSpec): return guarded(lambda:specs.save(body))
    @app.get('/api/style-specs/{sid}')
    def spec_read(sid:str): return guarded(lambda:specs.get(sid))
    @app.get('/api/style-presets')
    def presets(): return specs.presets()
    @app.put('/api/style-presets/{name}')
    def preset(name:str,body:Preset):return guarded(lambda:specs.preset(name,body.style_spec_id))

    @app.post('/api/styles',status_code=201)
    def style_create(body:StyleRequest):
        try:
            raw=base64.b64decode(body.png_base64,validate=True)
            with Image.open(io.BytesIO(raw)) as im:
                if im.format!='PNG' or im.width*im.height>8_000_000: raise ValueError()
                size=list(im.size);im.verify()
            record=dict(role=body.role,source_sha256=digest(raw),decoded_size=size,review='unreviewed',layout_authority=False)
            sid=digest(canonical(record));record['id']=sid
            directory=styles/sid;directory.mkdir(exist_ok=True)
            for name,b in [('source.png',raw),('record.json',canonical(record))]:
                try:
                    with (directory/name).open('xb') as f:f.write(b)
                except FileExistsError:
                    if (directory/name).read_bytes()!=b:raise ValueError()
            return style_read(sid)[0]
        except Exception:
            raise HTTPException(422,'Invalid PNG or immutable style conflict') from None

    @app.get('/api/styles/{sid}')
    def style(sid:str): return guarded(lambda:style_read(sid)[0])

    @app.get('/api/styles/{sid}/source.png')
    def source(sid:str): return Response(guarded(lambda:style_read(sid)[1]),media_type='image/png')

    @app.get('/api/generation/status')
    def status(): return gen.status()

    @app.post('/api/generation/quote')
    def quote(body:QuoteRequest):
        def make():
            load(body.revision)
            if body.style_spec_id:
                refs=specs.inputs(body.style_spec_id)
                first=refs[0]
                return gen.quote(dict(layout_revision=body.revision,guide_sha256=digest(files(body.revision)['clean-guide.png']),style_spec_id=body.style_spec_id,
                    style_id=first['reference_id'],style_sha256=first['input_sha256'],style_references=[{k:v for k,v in x.items() if k!='raw'} for x in refs],prompt=specs.prompt(body.style_spec_id)))
            s,raw=style_read(body.style_id)
            guide=files(body.revision)['clean-guide.png']
            return gen.quote(dict(layout_revision=body.revision,guide_sha256=digest(guide),
                                  style_id=s['id'],style_sha256=digest(raw),prompt=body.prompt))
        return guarded(make)

    @app.get('/api/generation/quotes/{qid}')
    def quote_get(qid:str): return guarded(lambda:gen.get_quote(qid))

    @app.post('/api/generation/confirm')
    def confirm(body:ConfirmRequest):
        def run():
            q=gen.get_quote(body.quote_id)
            load(body.revision)
            if q['binding'].get('style_spec_id')!=body.style_spec_id:raise ValueError('stale style spec')
            if body.style_spec_id:
                refs=specs.inputs(body.style_spec_id)
                return gen.public(gen.confirm(body.quote_id,body.revision,files(body.revision)['clean-guide.png'],refs[0]['raw'],[r['raw'] for r in refs[1:]]))
            _,raw=style_read(q['binding']['style_id'])
            return gen.public(gen.confirm(body.quote_id,body.revision,files(body.revision)['clean-guide.png'],raw))
        if not gen.policy.get('approved'):raise HTTPException(403,'Project paid budget unapproved; no upload or paid submission allowed.')
        return guarded(run)

    @app.get('/api/generation/jobs/{jid}')
    def job(jid:str):return guarded(lambda:gen.public(gen.get(jid)))

    @app.post('/api/generation/jobs/{jid}/resume')
    def resume(jid:str):
        def run():
            j=gen.resume(jid)
            if j['status']=='completed':
                try:
                    raw=gen.provider.download(j['output_url'])
                    record=import_candidate(j['binding']['layout_revision'],raw,{
                        'provider':'wavespeed','model':gen.get_quote(j['quote_id'])['model'],
                        'job_id':jid,'prediction_id':j['prediction_id'],'request_sha256':j['request_sha256'],
                        'style_id':j['binding']['style_id'],'style_sha256':j['binding']['style_sha256'],
                        **({k:j['binding'][k] for k in ('style_spec_id','style_references')} if j['binding'].get('style_spec_id') else {})})
                    j.update(status='candidate_ready',candidate_id=record['id']);j.pop('output_error',None)
                except Exception:
                    j['output_error']='Output import/download failed. Resume same prediction; never regenerate.'
                j=gen.save(j)
            return gen.public(j)
        return guarded(run)
    app.state.resume_generation=resume
    return gen
