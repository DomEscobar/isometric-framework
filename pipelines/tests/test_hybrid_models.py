import importlib.util,pytest

def test_crop_uncertainty_and_citations_fail_closed():
    assert importlib.util.find_spec('hybrid_models'), 'provider contracts missing'
    from hybrid_models import validate_crops,review_gate
    crop={'source_sha256':'a'*64,'crops':{'land':{'xywh':[0,0,16,16],'source_pixels_per_unit':[16,16],'verdict':'uncertain','evidence_ids':['board'],'observation':'unclear'}}}
    with pytest.raises(ValueError):validate_crops(crop,'a'*64,[32,32],{'land'})
    crop['crops']['land']['verdict']='pass';validate_crops(crop,'a'*64,[32,32],{'land'})
    crop['crops']['land']['xywh']=[20,20,16,16]
    with pytest.raises(ValueError):validate_crops(crop,'a'*64,[32,32],{'land'})
    assert not review_gate({'criteria':{}},['final','guide','reference'])['approved']

def test_zero_price_preview_model_admitted_with_nominal_reserve():
    # stealth/space-bunny-alpha is routable with zero preview pricing and no
    # structured_outputs marker. Zero-priced models cannot overspend; admit
    # them (response_format required), reserve a nominal micro-dollar, and keep
    # the price-change guard. Priced models keep the old strict gates.
    from hybrid_models import OpenRouter
    base={'id':'mock/preview','context_length':1000000,'top_provider':{'max_completion_tokens':524288},'pricing':{'prompt':'0','completion':'0'},'architecture':{'input_modalities':['text','image'],'output_modalities':['text']},'reasoning':{'supported_efforts':['low']},'supported_parameters':['response_format','max_tokens','reasoning','reasoning_effort']}
    priced=dict(base);priced['id']='mock/priced';priced['pricing']={'prompt':'0.001','completion':'0.002'}
    seen={}
    def transport(method,path,body=None):
        if path=='/auth/key':return {'data':{}}
        if path=='/models':return {'data':[base,priced]}
        seen[path]=body;return {'id':'mock-receipt'}
    p=OpenRouter('mock/preview',transport=transport)
    meta=p.preflight()
    assert meta['id']=='mock/preview'
    q=OpenRouter('mock/priced',transport=transport)
    try:q.preflight()
    except ValueError:pass
    else:raise AssertionError('priced model without structured_outputs must stay rejected')

def test_cost_covers_image_tokens_and_no_tool_fees():
    from hybrid_models import OpenRouter
    m={'context_length':100,'pricing':{'prompt':'0.001','image':'0.002','completion':'0.003','internal_reasoning':'0.003','web_search':'1','audio':'0.005','input_audio_cache':'0.001'}}
    assert OpenRouter('test').cost(m,tokens=10)==230000

def test_strict_schema_strips_validation_only_keywords():
    # OpenAI/Gemini grammar subsets reject constraint keywords; they must not
    # reach the wire (local validators still enforce them).
    import json
    from hybrid_models import strict_schema
    schema={'title':'Probe','type':'object','properties':{'x':{'type':'integer'},'note':{'type':'string','minLength':3,'maxLength':20},'tags':{'type':'array','items':{'type':'string'},'minItems':1,'maxItems':4}},'required':['x','note','tags'],'additionalProperties':False}
    wire=strict_schema(schema)
    text=json.dumps(wire)
    for keyword in ['minLength','maxLength','minItems','maxItems']:
        assert keyword not in text,wire
    assert 'minLength' in json.dumps(schema),'original local schema must stay untouched'

def test_map_fields_are_wire_valid_and_round_trip():
    # Free-form maps (dict[str,str]) are unrepresentable in OpenAI strict
    # schemas (live HTTP400: required/materials mismatch). They must travel as
    # key/value entry arrays and convert back before local validation.
    import json
    from hybrid_models import strict_schema,output_from_wire,Plan,Review,CropMap
    from hybrid_layout_review import LayoutAssessment
    for cls in [Plan,Review,CropMap,LayoutAssessment]:
        wire=strict_schema(cls.model_json_schema())
        def check(node,path):
            if isinstance(node,dict):
                if node.get('type')=='object':
                    props=set((node.get('properties') or {}).keys());req=set(node.get('required') or [])
                    assert req==props,(cls.__name__,path,sorted(req-props),sorted(props-req))
                    assert node.get('additionalProperties') is False,(cls.__name__,path)
                assert 'const' not in node,(cls.__name__,path)
                for k,v in node.items():check(v,path+'/'+str(k))
            elif isinstance(node,list):
                for i,v in enumerate(node):check(v,path+'/'+str(i))
        check(wire,'')
    schema={'title':'M','type':'object','properties':{'materials':{'type':'object','additionalProperties':{'type':'string'}}},'required':['materials']}
    assert output_from_wire(schema,{'materials':[{'key':'land','value':'grass'}]})=={'materials':{'land':'grass'}}
    assert output_from_wire(schema,{'materials':{'land':'grass'}})=={'materials':{'land':'grass'}}

def test_call_rejects_unrepresentable_wire_schema_before_any_reservation(tmp_path,monkeypatch):
    # A schema the strict grammar cannot express must fail before any
    # reserve/POST: no provider call, no new hold.
    from generation import Generation
    from provider import WaveSpeed
    from hybrid_store import Store
    from hybrid_models import OpenRouter
    from artifacts import canonical,digest
    model='mock/planner'
    meta={'id':model,'context_length':100000,'top_provider':{'max_completion_tokens':32768},'pricing':{'prompt':'0.000001','completion':'0.000001'},'architecture':{'input_modalities':['text','image'],'output_modalities':['text']},'reasoning':{'supported_efforts':['low']},'supported_parameters':['response_format','max_tokens','structured_outputs','reasoning']}
    def request(self,method,path,body=None):raise AssertionError('no provider call allowed')
    monkeypatch.setattr(OpenRouter,'request',request)
    s=Store(Generation(tmp_path,WaveSpeed(key=''),{'approved':False,'total_usd':'10','max_attempts':0}))
    r=s.create('run',{'mode':'live','token_policy':{}});claim=s.claim()
    auth=dict(config_sha256=digest(canonical(claim['config'])),budget_microusd=1_000_000,max_calls=5,max_images=3,expires=9999999999)
    schema={'type':'object','properties':{'x':{'type':'crypto'}},'required':['x']}
    try:OpenRouter(model).call(s,claim,'planner','Probe',{},schema,auth,meta)
    except ValueError:pass
    else:raise AssertionError('unrepresentable schema must fail closed')
    assert s.calls(claim['id'])==[],'no reservation may be created for an invalid wire schema'

def test_prompt_shows_the_wire_schema_not_a_conflicting_local_shape(tmp_path,monkeypatch):
    # Live truncation: prompt said maps are dicts while the grammar forced
    # entry arrays; the model looped on whitespace until max_output_tokens.
    # One schema only — the wire form.
    import json
    from generation import Generation
    from provider import WaveSpeed
    from hybrid_store import Store
    from hybrid_models import OpenRouter,strict_schema
    from artifacts import canonical,digest
    model='mock/planner'
    meta={'id':model,'context_length':100000,'top_provider':{'max_completion_tokens':32768},'pricing':{'prompt':'0.000001','completion':'0.000001'},'architecture':{'input_modalities':['text','image'],'output_modalities':['text']},'reasoning':{'supported_efforts':['low']},'supported_parameters':['response_format','max_tokens','structured_outputs','reasoning']}
    captured=[]
    def request(self,method,path,body=None):
        if path=='/auth/key':return {'data':{}}
        if path=='/models':return {'data':[meta]}
        captured.append(body)
        return {'id':'mock-1','model':model,'choices':[{'finish_reason':'stop','message':{'content':'{"materials":[]}'}}],'usage':{}}
    monkeypatch.setattr(OpenRouter,'request',request)
    s=Store(Generation(tmp_path,WaveSpeed(key=''),{'approved':False,'total_usd':'10','max_attempts':0}))
    r=s.create('run',{'mode':'live','token_policy':{}});claim=s.claim()
    auth=dict(config_sha256=digest(canonical(claim['config'])),budget_microusd=1_000_000,max_calls=5,max_images=3,expires=9999999999)
    schema={'title':'Probe','type':'object','properties':{'materials':{'type':'object','additionalProperties':{'type':'string'}}},'required':['materials']}
    OpenRouter(model).call(s,claim,'planner','Probe',{},schema,auth,meta)
    system=captured[-1]['messages'][0]['content']
    shown=json.loads(system.split('LOCAL_JSON_SCHEMA:\n')[1])
    assert shown==strict_schema(schema),'prompt must show exactly the wire schema'
    assert 'additionalProperties":{"type":"string"' not in json.dumps(shown),'free-form map must not be advertised to the model'

def test_call_enforces_strict_json_schema_on_the_wire(tmp_path,monkeypatch):
    # Regression: prompt-only schema let a provider omit required fields
    # (Plan.unsupported). The wire request must use strict json_schema
    # structured outputs with every property required and optionals nullable.
    from generation import Generation
    from provider import WaveSpeed
    from hybrid_store import Store
    from hybrid_models import OpenRouter
    from artifacts import canonical,digest
    model='mock/planner'
    meta={'id':model,'context_length':100000,'top_provider':{'max_completion_tokens':32768},'pricing':{'prompt':'0.000001','completion':'0.000001'},'architecture':{'input_modalities':['text','image'],'output_modalities':['text']},'reasoning':{'supported_efforts':['low']},'supported_parameters':['response_format','max_tokens','structured_outputs','reasoning']}
    captured=[]
    def request(self,method,path,body=None):
        if path=='/auth/key':return {'data':{}}
        if path=='/models':return {'data':[meta]}
        captured.append(body)
        return {'id':'mock-1','model':model,'choices':[{'finish_reason':'stop','message':{'content':'{"x":2}'}}],'usage':{}}
    monkeypatch.setattr(OpenRouter,'request',request)
    s=Store(Generation(tmp_path,WaveSpeed(key=''),{'approved':False,'total_usd':'10','max_attempts':0}))
    r=s.create('run',{'mode':'live','token_policy':{}});claim=s.claim()
    auth=dict(config_sha256=digest(canonical(claim['config'])),budget_microusd=1_000_000,max_calls=5,max_images=3,expires=9999999999)
    schema={'title':'Probe','type':'object','properties':{'x':{'type':'integer'},'note':{'type':'string'}},'required':['x'],'additionalProperties':False}
    result=OpenRouter(model).call(s,claim,'planner','Probe prompt',{},schema,auth,meta)
    assert result=={'x':2}
    rf=captured[-1]['response_format']
    assert rf['type']=='json_schema'
    js=rf['json_schema'];assert js['strict'] is True
    wire=js['schema']
    assert set(wire['required'])=={'x','note'},'every property must be required in strict mode'
    assert wire['additionalProperties'] is False
    assert 'null' in str(wire['properties']['note']),'originally optional fields must stay nullable'
