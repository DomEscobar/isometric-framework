import pytest
from test_generation import MockProvider
from generation import Generation
from artifacts import digest


def ready(tmp_path,p=None,policy=None):
    p=p or MockProvider()
    g=Generation(tmp_path,p,policy or {'approved':True,'total_usd':'0.02','max_attempts':3})
    q=g.quote({'layout_revision':'r','guide_sha256':digest(b'g'),'style_id':'s','style_sha256':digest(b's'),'prompt':'x'})
    return p,g,q


def test_missing_auth_never_uploads_or_submits(tmp_path):
    p,g,q=ready(tmp_path);p.authenticated=False
    with pytest.raises(ValueError,match='authentication'):g.confirm(q['id'],'r',b'g',b's')
    assert p.submitted==0


@pytest.mark.parametrize('bad_price',[-1,0,0.1])
def test_exact_quote_invalid_or_above_reserve_never_submits(tmp_path,bad_price):
    p,g,q=ready(tmp_path)
    p.quote=lambda inputs:{'price':bad_price,'currency':'USD'}
    assert g.confirm(q['id'],'r',b'g',b's')['status']=='preparation_failed'
    assert p.submitted==0


def test_schema_drift_stops_before_upload(tmp_path):
    p,g,q=ready(tmp_path)
    p.discover=lambda:{'changed':True}
    p.upload=lambda *args:pytest.fail('should not upload after schema drift')
    assert g.confirm(q['id'],'r',b'g',b's')['status']=='preparation_failed'
    assert p.submitted==0


def test_poll_wrong_prediction_preserves_original_binding(tmp_path):
    p,g,q=ready(tmp_path);j=g.confirm(q['id'],'r',b'g',b's')
    p.poll=lambda pid:{'id':'wrong','status':'completed','outputs':['https://example.org/x']}
    result=g.resume(j['id'])
    assert result['prediction_id']=='prediction-1'
    assert result['status']=='submitted'
    assert 'poll_error' in result
    assert p.submitted==1


def test_project_total_reservations_not_per_call_limit(tmp_path):
    p,g,q=ready(tmp_path);g.confirm(q['id'],'r',b'g',b's')
    q2=g.quote({**q['binding'],'prompt':'different request'})
    with pytest.raises(ValueError,match='total budget'):g.confirm(q2['id'],'r',b'g',b's')
    assert p.submitted==1
