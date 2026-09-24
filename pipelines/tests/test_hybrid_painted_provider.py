"""The painted-terrain provider must expose an explicit pixel-size contract."""

def _catalog(model_id,props,required):
    return {'model_id':model_id,'api_schema':{'api_schemas':[{'type':'model_run','request_schema':{'type':'object','properties':props,'required':required}}]}}

def test_discover_requires_explicit_size_and_accepts_images_key():
    # Live mismatch: muse-image returned 1904x1328 for a 1920x1344 canvas and
    # broke the grid binding. The adapter must target a model with explicit
    # size output and accept the 'images' input key.
    from provider import WaveSpeed
    size={'type':'string','minimum':512,'maximum':8192}
    good=_catalog('mock/edit-with-size',{'prompt':{'type':'string'},'images':{'type':'array'},'output_format':{'type':'string','enum':['png','webp']},'size':size},['prompt','images'])
    def transport(method,path,body=None):
        if path=='/models':return [good]
        raise AssertionError('unexpected '+path)
    p=WaveSpeed(key='test',transport=transport);p.model_id='mock/edit-with-size'
    schema=p.discover()
    assert 'size' in schema['properties'] and 'images' in schema['properties']
    no_size=_catalog('mock/edit-no-size',{'prompt':{'type':'string'},'image_urls':{'type':'array'},'output_format':{'type':'string','enum':['png']}},['prompt','image_urls'])
    def transport2(method,path,body=None):
        if path=='/models':return [no_size]
        raise AssertionError('unexpected '+path)
    q=WaveSpeed(key='test',transport=transport2);q.model_id='mock/edit-no-size'
    try:q.discover()
    except ValueError:pass
    else:raise AssertionError('missing explicit size contract must fail closed')

def test_painted_image_request_pins_exact_canvas():
    from hybrid_models import MaterialImage
    size={'type':'string','minimum':512,'maximum':8192}
    schema={'type':'object','properties':{'prompt':{'type':'string'},'images':{'type':'array'},'output_format':{'type':'string','enum':['png','webp']},'size':size},'required':['prompt','images']}
    p=MaterialImage(key='test')
    p.discover=lambda:schema
    body=p.inputs('Repaint the board.',['https://mock.invalid/guide.png','https://mock.invalid/style.png'],size=(1920,1344))
    assert body['size']=='1920*1344' and body['output_format']=='png'
    assert body['images']==['https://mock.invalid/guide.png','https://mock.invalid/style.png']
    import jsonschema
    jsonschema.validate(body,schema)

def test_provider_model_targets_the_exact_size_edit_endpoint():
    import provider
    assert provider.MODEL=='bytedance/seedream-v5.0-lite/edit'
