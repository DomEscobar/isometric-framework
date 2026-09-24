import importlib
import numpy as np
import pytest


def diagnostic():
    try:
        return importlib.import_module('registration_diagnostic')
    except ModuleNotFoundError:
        pytest.fail('read-only registration diagnostic is missing')


def diamond(width=800, height=440, sx=1., sy=1., offset=(0, 0)):
    y, x = np.indices((height, width))
    return abs((x-offset[0])/sx-400)/350 + abs((y-offset[1])/sy-220)/175 <= 1


def test_uniform_scale_translation_unbiased():
    d = diagnostic()
    target = diamond()
    source = diamond(1700, 950, 2., 2., (30, 20))
    result = d.fit_frame(source, target)
    assert result['scale'] == pytest.approx(.5, abs=.001)
    assert result['translation'] == pytest.approx([-15, -10], abs=.5)
    assert max(s['p95_px'] for s in result['holdout'].values()) < .8
    assert result['transform_model'] == 'one_uniform_scale_plus_translation'


def test_sparse_contour_outliers_do_not_bias_proposal():
    d = diagnostic()
    target = diamond()
    source = diamond(1700, 950, 2., 2., (30, 20))
    source[220:650:9, 20] = True
    result = d.fit_frame(source, target)
    assert result['scale'] == pytest.approx(.5, abs=.001)
    assert result['translation'] == pytest.approx([-15, -10], abs=.6)
    # Robust training must not suppress held-out outlier evidence.
    assert max(s['max_px'] for s in result['holdout'].values()) > 20


def test_anisotropic_deformation_is_not_hidden_by_uniform_fit():
    d = diagnostic()
    result = d.fit_frame(diamond(1700, 950, 2., 2.06, (30, 20)), diamond())
    assert result['diagnostic_alarm']
    assert result['source_per_target_spans_xy'][1]/result['source_per_target_spans_xy'][0] == pytest.approx(1.03, abs=.003)
    assert result['intersection_max_residual_px'] > 2.5
    assert result['production_approved'] is False


def test_internal_shift_is_holdout_not_refitted():
    d = diagnostic()
    mask = np.zeros((140, 200), bool)
    mask[40:100, 40:160] = True
    points = d.boundary_points(mask)
    exact = d.compare_boundaries(points, points)
    shifted = d.compare_boundaries(points + [0, 9], points)
    assert exact['source_to_target']['max_px'] == 0
    assert shifted['source_to_target']['p95_px'] == 9
    assert shifted['target_to_source']['p95_px'] == 9
    assert shifted['diagnostic_alarm']


def test_missing_evidence_cannot_pass():
    d = diagnostic()
    with pytest.raises(ValueError, match='insufficient'):
        d.fit_frame(np.zeros((100,100), bool), diamond())
    result = d.compare_boundaries(np.empty((0,2)), np.array([[1,2]]))
    assert result['status'] == 'uncertain_missing_boundary'
    assert result['diagnostic_alarm']


def test_internal_road_band_curbs_detect_shift_without_refit():
    d = diagnostic()
    y,x = np.indices((200,400))
    target = (x>20)&(x<380)&(y>x*.25+20)&(y<x*.25+55)
    source = np.roll(target, 10, axis=0)
    result = d.compare_road_band(source, target, 1., np.array([0.,0.]))
    assert result['upper']['p50_px'] == pytest.approx(10/np.hypot(1,.25), abs=.2)
    assert result['lower']['p50_px'] == pytest.approx(10/np.hypot(1,.25), abs=.2)
    assert result['transform_refitted'] is False


def test_road_band_ignores_thin_disconnected_clutter_not_real_curbs():
    d = diagnostic()
    y,x = np.indices((250,400))
    target = (x>20)&(x<380)&(y>x*.25+20)&(y<x*.25+55)
    source = target.copy()
    source[230,:] = True
    source[5,:] = True
    result = d.compare_road_band(source,target,1.,np.array([0.,0.]))
    assert result['upper']['p95_px'] < 1
    assert result['lower']['p95_px'] < 1


def test_contiguous_frame_holdout_displacement_does_not_change_fit():
    d = diagnostic()
    original = diamond()
    shifted = original.copy()
    for y in range(117,149):
        x = np.flatnonzero(shifted[y])
        shifted[y,x[:12]] = False
        shifted[y,x[-12:]] = False
    baseline = d.fit_frame(original, original)
    changed = d.fit_frame(shifted, original)
    assert changed['scale'] == pytest.approx(baseline['scale'], abs=1e-12)
    assert changed['translation'] == pytest.approx(baseline['translation'], abs=1e-10)
    assert changed['holdout']['upper_left']['max_px'] > 2.5
    assert changed['diagnostic_alarm']


def test_extrema_ties_report_centroid_not_only_first_point():
    d = diagnostic()
    mask = np.zeros((20,20),bool)
    mask[3:17,4:16] = True
    result = d.extrema_ties(mask)
    assert result['top']['first'] == [4,3]
    assert result['top']['centroid'] == [9.5,3.0]
    assert result['top']['count'] == 12


def test_cli_refuses_live_data_output():
    import subprocess, sys
    run = subprocess.run([sys.executable,'tools/diagnose_registration.py', '--source','missing.png',
                          '--layout','missing.json','--output','data/must-not-be-created'],
                         capture_output=True,text=True)
    assert run.returncode != 0
    assert 'output must be outside live data' in run.stderr


def test_offline_cli_writes_only_diagnostic_artifacts(tmp_path):
    import subprocess, sys, json
    from pathlib import Path
    from layout_core import generate
    from artifacts import export_files, canonical
    layout = generate({'kind':'urban', 'seed':17})
    files = export_files(layout)
    lp, sp, out = tmp_path/'layout.json', tmp_path/'source.png', tmp_path/'out'
    lp.write_bytes(canonical(layout))
    sp.write_bytes(files['clean-guide.png'])
    before = sp.read_bytes(), lp.read_bytes()
    run = subprocess.run([sys.executable, 'tools/diagnose_registration.py', '--source', str(sp),
                          '--layout', str(lp), '--output', str(out)], capture_output=True, text=True)
    assert run.returncode == 0, run.stderr
    result = json.loads((out/'diagnosis.json').read_text())
    assert result['production_approved'] is False
    assert result['registered_candidate_created'] is False
    assert len(result['frame_fits']) == 3
    assert {'street', 'planting'} == set(result['interior_proxies'])
    assert result['legacy_registration']['measurements']['limits']['residual_px'] == 2.5
    assert (out/'overlay-native.png').exists()
    assert (sp.read_bytes(), lp.read_bytes()) == before
