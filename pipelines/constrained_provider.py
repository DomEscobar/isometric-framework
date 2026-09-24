"""Supported provider-side masked edit; no output compositing or paint.
Only the registered source and canonical edit mask are submitted as images.
The guide remains bound evidence; this schema has no separate reference field.
"""
from provider import WaveSpeed
import io
import numpy as np
from PIL import Image, ImageFilter
from artifacts import png


def build_edit_mask(sidewalk,terrain):
    s=np.array(Image.open(io.BytesIO(sidewalk)).convert('L'))
    t=Image.open(io.BytesIO(terrain)).convert('L')
    # Protect frozen outer frame with a predeclared 3px inset. Do not erode
    # planting holes: the canonical sidewalk border is the correction target.
    inner=np.array(t.filter(ImageFilter.MinFilter(7)))
    if inner.shape!=s.shape:raise ValueError('mask frame mismatch')
    m=(s==255)&(inner==255)
    if not m.any() or m.all():raise ValueError('empty or full-frame edit prohibited')
    return png(m.astype('uint8')*255)


def preservation_check(source,output,mask):
    a=np.array(Image.open(io.BytesIO(source)).convert('RGBA'))
    b=np.array(Image.open(io.BytesIO(output)).convert('RGBA'))
    m=np.array(Image.open(io.BytesIO(mask)).convert('L'))
    if a.shape!=b.shape or m.shape!=a.shape[:2]:
        return dict(preserved=False,blocker='constrained_canvas_changed',source_size=list(a.shape[1::-1]),output_size=list(b.shape[1::-1]))
    if not set(np.unique(m))<={0,255}:raise ValueError('nonbinary mask')
    changed=np.any(a!=b,axis=2)
    count=int((changed & (m==0)).sum())
    return dict(preserved=count==0,unmasked_changed_pixels=count,masked_changed_pixels=int((changed & (m==255)).sum()),
                blocker=None if count==0 else 'constrained_unmasked_pixels_changed',output_size=list(b.shape[1::-1]))


class MaskedWaveSpeed(WaveSpeed):
    model_id='wavespeed-ai/z-image/turbo-inpaint'

    def require_output_contract(self):
        schema=self.discover()
        if 'png' not in schema.get('properties',{}).get('output_format',{}).get('enum',[]):
            raise ValueError('constrained model has no supported lossless PNG output contract; no purchase')
        # A changed catalog is not proof that the observed 768x512 resize is gone.
        raise ValueError('constrained native 768x408 preservation is not verified; model retired after incompatible live result')

    def discover(self):
        models=self.request('GET','/models')
        model=next((m for m in models if m['model_id']==self.model_id),None)
        if model is None:raise ValueError('masked model absent from live catalog')
        schema=next(s['request_schema'] for s in model['api_schema']['api_schemas'] if s['type']=='model_run')
        keys={'prompt','image','mask_image','size'}
        if not keys<=schema.get('properties',{}).keys() or set(schema.get('required',[]))-keys:
            raise ValueError('masked live schema incompatible')
        return schema

    def input_template(self,binding):
        c=binding['constrained']
        if c['strategy']!='canonical-sidewalk-mask-v1' or c['size']!='768*408':
            raise ValueError('unsupported constrained strategy/frame')
        refs=binding['style_references']
        if [r['role'] for r in refs]!=['correction_target','edit_mask']:
            raise ValueError('masked input roles mismatch')
        return dict(prompt=binding['prompt'],image='https://example.invalid/registered.png',mask_image='https://example.invalid/mask.png',size=c['size'])

    def bind_inputs(self,template,urls):
        if len(urls)!=3:raise ValueError('masked source/guide/mask count mismatch')
        return {**template,'image':urls[1],'mask_image':urls[2]}

    def quote(self,inputs):
        return self.request('POST','/model/price',{'model_id':self.model_id,'inputs':inputs})

    def submit(self,inputs):
        if set(inputs)!={'prompt','image','mask_image','size'}:raise ValueError('unsupported masked request fields')
        return self.request('POST','/'+self.model_id,inputs)
