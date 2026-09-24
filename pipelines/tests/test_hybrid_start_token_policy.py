import pytest

def test_start_model_binds_explicit_token_policy_and_rejects_junk():
    from hybrid_api import Start
    from hybrid_models import OpenRouter
    policy={'extraction':{'max_tokens':32768,'reasoning_effort':'medium'},'review':{'max_tokens':32768,'reasoning_effort':'medium'}}
    s=Start(description='Mehrstufiges Dorf-Terrain mit See und Treppen',mode='live',token_policy=policy)
    cfg=s.model_dump()
    assert cfg['token_policy']['extraction']['max_tokens']==32768
    o=OpenRouter('google/gemini-3.8-flash')
    meta={'id':'google/gemini-3.8-flash','top_provider':{'max_completion_tokens':65536},'reasoning':{'supported_efforts':['low','medium','high']},'supported_parameters':['reasoning']}
    assert o.policy(cfg,'extraction',meta)['max_tokens']==32768
    assert o.policy(cfg,'review_sample',meta)['reasoning']=={'effort':'medium'}
    assert o.policy(cfg,'review_final',meta)['max_tokens']==32768
    # No silent fallback: a run without explicit policy keeps the historical default.
    assert OpenRouter('m').policy(Start(description='kleine Beschreibung').model_dump(),'extraction',meta)=={'max_tokens':8192}
    with pytest.raises(Exception):Start(description='kleine Beschreibung',token_policy={'extraction':{'max_tokens':70000,'reasoning_effort':'medium'}})
    with pytest.raises(Exception):Start(description='kleine Beschreibung',token_policy={'extraction':{'max_tokens':32768,'reasoning_effort':'ultra'}})
    with pytest.raises(Exception):Start(description='kleine Beschreibung',token_policy={'bogus':{'max_tokens':32768,'reasoning_effort':'medium'}})
