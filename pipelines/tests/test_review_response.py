import json
from PIL import Image
from generation import Generation
from test_generation import MockProvider

def test_truncated_or_wrong_model_cannot_return_pass(tmp_path):
 from review import run_review
 image=tmp_path/'a.png';Image.new('RGB',(20,20)).save(image)
 meta={'id':'test-vision','context_length':1000,'pricing':{'prompt':'0.000001','completion':'0.000001'},'architecture':{'input_modalities':['image','text']}}
 for i,(model,finish) in enumerate([('wrong','stop'),('test-vision','length')]):
  g=Generation(tmp_path/str(i),MockProvider(),{'approved':True,'total_usd':'1','max_attempts':1})
  response={'id':'fixture','model':model,'choices':[{'finish_reason':finish,'message':{'content':json.dumps({'semantic_verdict':'pass','visual_verdict':'pass','findings':[]})}}]}
  result=run_review(g,'r',[(image,'test')],'fixture',meta,lambda _:response)
  assert result['verdict']['semantic_verdict']=='needs_attention'
  assert result['verdict']['visual_verdict']=='needs_attention'
