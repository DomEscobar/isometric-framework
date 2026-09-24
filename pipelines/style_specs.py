"""Immutable style semantics in the existing project database; references reuse styles/."""
import io
import json
import re
from typing import Literal, Annotated
from pydantic import BaseModel, ConfigDict, Field, model_validator, field_validator
from PIL import Image
import numpy as np
from artifacts import canonical, digest, png

Hash = Annotated[str, Field(pattern=r'^[0-9a-f]{64}$')]
Text = Annotated[str, Field(min_length=1,max_length=2000)]
Material = Literal['street','sidewalk','planting','grass','path','water','soil']

class Strict(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)

class Reference(Strict):
    reference_id: Hash
    role: Literal['style_only','material_only']
    material: Material | None = None
    crop: list[Annotated[int,Field(ge=0)]] | None = Field(default=None,min_length=4,max_length=4,description='[x,y,width,height] in retained source pixels; never geometry authority')
    @model_validator(mode='after')
    def roles(self):
        if (self.role=='material_only') != (self.material is not None): raise ValueError('material_only requires material; style_only forbids it')
        if self.crop and (self.crop[2]==0 or self.crop[3]==0): raise ValueError('empty crop')
        return self

class MaterialDefinition(Strict):
    prompt: Text
    reference_ids: list[Hash] = Field(default_factory=list,max_length=8)

class StyleSpec(Strict):
    model_config=ConfigDict(extra='forbid',strict=True,json_schema_extra={'examples':[{
        'version':1,'prompt':'Calm warm urban pixel ground; canonical guide owns geometry.',
        'avoid':['tiny uniform noisy pavers','cool speckled asphalt'],
        'materials':{'sidewalk':{'prompt':'Large warm cream slabs with broad faces and sparse seams.','reference_ids':[]}},
        'references':[{'reference_id':'ef8024f3b713242c25da8df0c70b13b19b7adaac34a534766b0e2a4c5edccc69','role':'style_only','material':None,'crop':None}]}]})
    version: Literal[1]
    @field_validator('version',mode='before')
    @classmethod
    def strict_version(cls,v):
        if type(v) is not int:raise ValueError('version must be integer 1')
        return v
    prompt: Text
    avoid: list[Annotated[str,Field(min_length=1,max_length=160)]] = Field(default_factory=list,max_length=24)
    materials: dict[Material,MaterialDefinition] = Field(default_factory=dict,max_length=7)
    references: list[Reference] = Field(min_length=1,max_length=8)
    @model_validator(mode='after')
    def coherent(self):
        ids=[canonical(r.model_dump()) for r in self.references]
        if len(set(ids))!=len(ids): raise ValueError('duplicate reference role/crop')
        if not any(r.role=='style_only' for r in self.references): raise ValueError('style_only reference required')
        for material,definition in self.materials.items():
            for rid in definition.reference_ids:
                if not any(r.reference_id==rid and r.material==material and r.role=='material_only' for r in self.references): raise ValueError('material reference role mismatch')
        for r in self.references:
            if r.role=='material_only' and (r.material not in self.materials or r.reference_id not in self.materials[r.material].reference_ids): raise ValueError('unused material reference')
        return self

class Preset(Strict):
    style_spec_id: Hash

class Styles:
    def __init__(self,g,read_reference):
        self.g=g;self.read_reference=read_reference
        with g.connect() as db:
            db.executescript('CREATE TABLE IF NOT EXISTS style_specs(id TEXT PRIMARY KEY,record TEXT NOT NULL);CREATE TABLE IF NOT EXISTS style_presets(name TEXT PRIMARY KEY,style_spec_id TEXT NOT NULL);')
    def resolve(self,spec):
        result=[]
        for ref in spec.references:
            record,raw=self.read_reference(ref.reference_id)
            im=Image.open(io.BytesIO(raw)).convert('RGBA')
            if ref.crop:
                x,y,w,h=ref.crop
                if x+w>im.width or y+h>im.height: raise ValueError('crop outside retained reference')
                raw=png(np.array(im.crop((x,y,x+w,y+h))))
            result.append(dict(**ref.model_dump(),source_sha256=record['source_sha256'],input_sha256=digest(raw),raw=raw))
        return result
    def save(self,spec):
        refs=self.resolve(spec)
        record=dict(spec=spec.model_dump(),reference_lineage=[{k:v for k,v in r.items() if k!='raw'} for r in refs])
        sid=digest(canonical(record));record['id']=sid
        with self.g.connect() as db:db.execute('INSERT OR IGNORE INTO style_specs VALUES (?,?)',(sid,canonical(record).decode()))
        return self.get(sid)
    def get(self,sid):
        with self.g.connect() as db:row=db.execute('SELECT record FROM style_specs WHERE id=?',(sid,)).fetchone()
        if not row:raise ValueError('style spec missing')
        r=json.loads(row[0]);spec=StyleSpec.model_validate(r['spec'])
        lineage=[{k:v for k,v in x.items() if k!='raw'} for x in self.resolve(spec)]
        if digest(canonical({k:v for k,v in r.items() if k!='id'}))!=sid or lineage!=r['reference_lineage']:raise ValueError('style binding drift')
        return r
    def inputs(self,sid):return self.resolve(StyleSpec.model_validate(self.get(sid)['spec']))
    def prompt(self,sid):
        r=self.get(sid)
        return 'Exact versioned style specification (references never control geometry): '+canonical(r).decode()
    def preset(self,name,sid):
        if not re.fullmatch('[a-z][a-z0-9-]{0,47}',name):raise ValueError('invalid preset name')
        self.get(sid)
        with self.g.connect() as db:db.execute('INSERT INTO style_presets VALUES (?,?) ON CONFLICT(name) DO UPDATE SET style_spec_id=excluded.style_spec_id',(name,sid))
        return next(p for p in self.presets() if p['name']==name)
    def presets(self):
        with self.g.connect() as db:return [dict(r) for r in db.execute('SELECT name,style_spec_id FROM style_presets ORDER BY name')]
