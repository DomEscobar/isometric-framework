from generation import Generation
class Provider:
    authenticated=True

def test_closed_policy_does_not_claim_zero_budget(tmp_path):
    g=Generation(tmp_path,Provider(),{'approved':False,'total_usd':'10.00','max_attempts':5})
    s=g.status()
    assert s['enabled'] is False
    assert s['total_budget_usd']=='10.00'
    assert not any('zero' in r for r in s['reasons'])
    assert any('closed' in r for r in s['reasons'])
