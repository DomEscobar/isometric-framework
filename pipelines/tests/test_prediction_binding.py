import pytest
from test_generation import MockProvider
from generation import Generation
from artifacts import digest,canonical


def test_prediction_id_cannot_be_rebound(tmp_path):
    p=MockProvider();g=Generation(tmp_path,p,{'approved':True,'total_usd':'1','max_attempts':2})
    q=g.quote({'layout_revision':'r','guide_sha256':digest(b'g'),'style_id':'s','style_sha256':digest(b's'),'prompt':'x'})
    j=g.confirm(q['id'],'r',b'g',b's')
    j['prediction_id']='other-prediction'
    with g.connect() as db:db.execute('UPDATE jobs SET record=? WHERE id=?',(canonical(j).decode(),j['id']))
    with pytest.raises(ValueError,match='prediction'):g.resume(j['id'])


def test_crash_after_receipt_recovers_exact_prediction(tmp_path):
    p=MockProvider();g=Generation(tmp_path,p,{'approved':True,'total_usd':'1','max_attempts':2})
    q=g.quote({'layout_revision':'r','guide_sha256':digest(b'g'),'style_id':'s','style_sha256':digest(b's'),'prompt':'x'})
    j=g.confirm(q['id'],'r',b'g',b's')
    j.update(prediction_id=None,status='submitting')
    with g.connect() as db:db.execute('UPDATE jobs SET record=? WHERE id=?',(canonical(j).decode(),j['id']))
    result=g.resume(j['id'])
    assert result['prediction_id']=='prediction-1'
    assert result['status']=='processing'
    assert p.submitted==1
    sources=tmp_path/'generation-sources'
    assert (sources/(q['binding']['guide_sha256']+'.png')).read_bytes()==b'g'
    assert (sources/(q['binding']['style_sha256']+'.png')).read_bytes()==b's'
    (sources/(q['binding']['style_sha256']+'.png')).write_bytes(b'drift')
    with pytest.raises(ValueError,match='source'):g.resume(j['id'])
