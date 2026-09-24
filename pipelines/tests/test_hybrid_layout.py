import pytest
import importlib.util
from pathlib import Path

def sample():
    return dict(schema='hybrid-layout/1',width=6,height=5,actor_width=0.64,spawn=[1,1],goals=[[4,3]],cells=[['land']*6 for _ in range(5)],heights=[[0]*6 for _ in range(5)],transitions=[],unsupported=[])

def test_compiler_rectangular_and_geometry_only():
    assert importlib.util.find_spec('hybrid_layout'), 'material-independent compiler missing'
    from hybrid_layout import compile_layout
    w=compile_layout(sample())
    assert w['width']==6 and w['height']==5
    assert [4,3] in w['reachable']
    assert len(w['graph'])==30
    assert 'materials' not in w
