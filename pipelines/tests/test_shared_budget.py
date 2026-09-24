import pytest
from generation import Generation
from test_generation import MockProvider
from artifacts import digest

def test_reviewer_and_generation_share_one_ceiling(tmp_path):
    g=Generation(tmp_path,MockProvider(),{'approved':True,'total_usd':'0.02','max_attempts':2})
    assert hasattr(g,'reserve_review'), 'external review must reserve in the central project ledger'
    g.reserve_review('review-1',15000,{'model':'test-only'})
    assert g.status()['reserved_usd']=='0.015'
    b=dict(layout_revision='r',guide_sha256=digest(b'g'),style_id='s',style_sha256=digest(b's'),prompt='x')
    q=g.quote(b)
    with pytest.raises(ValueError,match='budget'):g.confirm(q['id'],'r',b'g',b's')
    assert g.provider.submitted==0
    assert g.reserve_review('review-1',15000,{'model':'test-only'})['reserve_microusd']==15000
    with pytest.raises(ValueError,match='budget'):g.reserve_review('review-2',6000,{})
    with pytest.raises(ValueError):g.reserve_review('review-1',1,{})

def test_review_reservations_are_positive_and_authorized(tmp_path):
    g=Generation(tmp_path,MockProvider())
    with pytest.raises(ValueError):g.reserve_review('r',100,{})
    g.policy={'approved':True,'total_usd':'1','max_attempts':1}
    for invalid in [0,-1,True,1.2]:
        with pytest.raises(ValueError):g.reserve_review('r',invalid,{})
