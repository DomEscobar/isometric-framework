import pytest

META={'id':'openai/gpt-6-luna-pro','context_length':1050000,
 'pricing':{'prompt':'0.0000001','completion':'0.0000005','web_search':'0.01','input_cache_read':'0.00000001','input_cache_write':'0.000000125',
   'overrides':[{'min_prompt_tokens':272000,'prompt':'0.0000002','completion':'0.00000075','input_cache_read':'0.00000002','input_cache_write':'0.00000025'}]},
 'supported_parameters':['include_reasoning','max_tokens','reasoning','reasoning_effort','response_format','seed','structured_outputs','tool_choice','tools'],
 'reasoning':{'mandatory':False,'default_enabled':True,'supported_efforts':['max','xhigh','high','medium','low','none'],'default_effort':'medium'},
 'top_provider':{'context_length':1050000,'max_completion_tokens':128000,'is_moderated':True},
 'architecture':{'input_modalities':['file','image','text'],'output_modalities':['text']}}

def test_structured_model_without_temperature_is_valid_and_gets_no_temperature():
    from evaluations import validate_model
    from hybrid_models import OpenRouter
    validate_model(META)
    # Still reject genuinely unstructured models.
    import copy
    bad=copy.deepcopy(META);bad['supported_parameters']=['max_tokens','response_format']
    bad['supported_parameters']=['max_tokens']
    with pytest.raises(ValueError):validate_model(bad)
    o=OpenRouter(META['id'])
    body_meta=dict(META)
    token=o.policy({'token_policy':{'extraction':{'max_tokens':32768,'reasoning_effort':'medium'}}},'extraction',body_meta)
    body=dict(model=META['id'],messages=[],temperature=0,response_format={'type':'json_object'},**token)
    body=o.finalize_body(body,body_meta)
    assert 'temperature' not in body and body['response_format']=={'type':'json_object'}

def test_cost_uses_conservative_worst_tier_of_overrides():
    from hybrid_models import OpenRouter
    o=OpenRouter(META['id'])
    q=o.cost(META,32768)
    # Full-context estimate lands above the 272k override tier: prompt 2e-7, completion 7.5e-7.
    assert q==234576
    low=OpenRouter('m').cost({**META,'context_length':1000},32768)
    assert low==16484
    import copy
    weird=copy.deepcopy(META);weird['pricing']['overrides']='broken'
    with pytest.raises(Exception):OpenRouter('m').cost(weird,32768)
