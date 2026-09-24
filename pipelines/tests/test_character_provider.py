import importlib
from artifacts import digest,canonical
from generation import Generation

def test_character_scope_template_and_shared_ledger(tmp_path):
    from character_provider import CharacterProvider
    calls=[]
    schema={'properties':{'prompt':{},'image_urls':{},'output_format':{'enum':['png']}},'required':['prompt','image_urls']}
    def transport(method,path,body):
        if path=='/models':return [{'model_id':'meta/muse-image/edit','api_schema':{'api_schemas':[{'type':'model_run','request_schema':schema}]}}]
        if path=='/model/price':return {'price':.011,'currency':'USD'}
        calls.append(path);return {'id':'test-character-id'}
    p=CharacterProvider(key='test',transport=transport)
    p.upload=lambda raw,name:'https://example.com/'+name
    g=Generation(tmp_path,p,{'approved':True,'total_usd':'10','max_attempts':1})
    b={'scope':'single-static-character-v1','layout_revision':'independent-character','guide_sha256':digest(b'blank'),'style_sha256':digest(b'reference'),'prompt':'Image 1 framing only. Image 2 style only. One traveller.'}
    q=g.quote(b)
    assert q['inputs_template']['prompt']==b['prompt']
    assert set(q['inputs_template'])=={'prompt','image_urls','output_format','aspect_ratio'}
    j=g.confirm(q['id'],b['layout_revision'],b'blank',b'reference')
    assert j['prediction_id']=='test-character-id'
    assert g.confirm(q['id'],b['layout_revision'],b'blank',b'reference')['id']==j['id']
    assert calls==['/meta/muse-image/edit']
    assert g.status()['reserved_usd']=='0.011'
