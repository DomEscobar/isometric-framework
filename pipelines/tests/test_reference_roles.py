from auto_adapter import reference_prompt


def test_provider_roles_number_actual_material_crops_not_scene_materials():
    refs=[dict(role='style_only',material=None),dict(role='material_only',material='sidewalk'),dict(role='material_only',material='street'),dict(role='correction_target',material=None)]
    text=reference_prompt(refs)
    assert 'Image 1: immutable geometry guide' in text
    assert 'Image 2: style_only' in text
    assert 'Image 3: material_only sidewalk' in text
    assert 'Image 4: material_only street' in text
    assert 'Image 5: correction_target' in text
    assert 'material_only crop takes priority' in text
    assert 'passing materials' in text
    assert 'asphalt' not in text and 'cream' not in text
