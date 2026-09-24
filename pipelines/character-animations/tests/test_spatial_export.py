from __future__ import annotations

import hashlib
import json
import random
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

import spatial_export


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _source(path: Path, offset: int = 0) -> None:
    image = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    ImageDraw.Draw(image).rectangle((20 + offset, 8, 43 + offset, 58), fill=(50, 90, 120, 255))
    image.save(path)


def _reference_premultiplied_resize(source: Image.Image, size: tuple[int, int]) -> Image.Image:
    rgba = source.convert("RGBA")
    red, green, blue, alpha = rgba.split()
    premult = [Image.new("L", rgba.size), Image.new("L", rgba.size), Image.new("L", rgba.size)]
    for target, channel in zip(premult, (red, green, blue)):
        target.putdata([
            (color * opacity + 127) // 255
            for color, opacity in zip(channel.get_flattened_data(), alpha.get_flattened_data())
        ])
    resized_alpha = alpha.resize(size, Image.Resampling.LANCZOS)
    resized_premult = [channel.resize(size, Image.Resampling.LANCZOS) for channel in premult]
    alpha_values = list(resized_alpha.get_flattened_data())
    colors = [list(channel.get_flattened_data()) for channel in resized_premult]
    pixels = []
    for index, opacity in enumerate(alpha_values):
        if opacity == 0:
            pixels.append((0, 0, 0, 0))
        else:
            values = [min(255, (channel[index] * 255 + opacity // 2) // opacity) for channel in colors]
            pixels.append((values[0], values[1], values[2], opacity))
    result = Image.new("RGBA", size)
    result.putdata(pixels)
    for image in [rgba, red, green, blue, alpha, resized_alpha, *premult, *resized_premult]:
        image.close()
    return result


def test_shared_master_preparation_preserves_exact_integer_rgba_rounding() -> None:
    randomizer = random.Random(20260921)
    source = Image.new("RGBA", (32, 16))
    source.putdata([
        (randomizer.randrange(256), randomizer.randrange(256), randomizer.randrange(256), alpha)
        for alpha in range(256)
        for _ in range(2)
    ])

    prepared = spatial_export._prepare_master(source)
    try:
        for size in ((19, 11), (7, 5), (64, 32)):
            expected = _reference_premultiplied_resize(source, size)
            actual = spatial_export._resize_prepared_master(prepared, size)
            assert actual.tobytes() == expected.tobytes()
            expected.close()
            actual.close()
    finally:
        spatial_export._close_prepared_master(prepared)
        source.close()


def test_cache_key_changes_with_source_and_corruption_fails_closed(tmp_path: Path) -> None:
    source = tmp_path / "source.png"
    master = tmp_path / "master.png"
    cache = tmp_path / "cache"
    _source(source)
    _source(master, 1)

    first = spatial_export.import_cached_cutout(source, master, cache, "remover-v1", "rgba-v1")
    assert spatial_export.lookup_cached_cutout(source, cache, "remover-v1", "rgba-v1") == first["path"]

    _source(source, 2)
    assert spatial_export.lookup_cached_cutout(source, cache, "remover-v1", "rgba-v1") is None
    _source(source)
    first["path"].write_bytes(b"corrupt")
    with pytest.raises(ValueError, match="cache output hash mismatch"):
        spatial_export.lookup_cached_cutout(source, cache, "remover-v1", "rgba-v1")


def test_export_variants_are_direct_from_immutable_masters(tmp_path: Path) -> None:
    masters = []
    for index in range(4):
        path = tmp_path / f"master-{index}.png"
        _source(path, index % 2)
        masters.append(path)
    output = tmp_path / "out"
    before = [_sha(path) for path in masters]
    config = {
        "job_id": "fixture-walk",
        "action": "walk",
        "direction": "ne",
        "native_fps": 24.0,
        "cycle_start": 10,
        "cycle_end_exclusive": 14,
        "selected_indices": [10, 11, 12, 13],
        "selection_mode": "explicit_human_reviewed",
        "source": {"file": "fixture.mp4", "sha256": "a" * 64},
        "geometry": {"source_root": [31.5, 58.0]},
        "variants": [
            {"canvas": 80, "scale": 1.0, "target_root": [40, 72]},
            {"canvas": 160, "scale": 2.0, "target_root": [80, 144]},
        ],
    }

    result = spatial_export.export_variants(masters, output, config)

    assert [item["canvas"] for item in result] == [80, 160]
    for item in result:
        manifest = json.loads((output / item["manifest"]).read_text())
        assert manifest["processing"]["direct_from_master"] is True
        assert manifest["processing"]["upscaled_from_other_variant"] is False
        assert all(frame["source_master_sha256"] == _sha(masters[frame["order"]]) for frame in manifest["frames"])
        assert all(frame["rect"]["width"] == item["canvas"] for frame in manifest["frames"])
    assert [_sha(path) for path in masters] == before


def test_punch_manifest_is_one_shot_not_walk_loop(tmp_path: Path) -> None:
    masters = []
    for index in range(4):
        path = tmp_path / f"punch-{index}.png"
        _source(path, index % 2)
        masters.append(path)
    config = {
        "job_id": "fixture", "action": "punch", "direction": "ne", "loop": False,
        "native_fps": 24.0, "cycle_start": 0, "cycle_end_exclusive": 12,
        "selected_indices": [0, 3, 6, 9], "selection_mode": "automatic_model_validated",
        "frame_durations_seconds": [0.125, 0.125, 0.125, 0.125],
        "source": {"file": "fixture.mp4", "sha256": "b" * 64},
        "geometry": {"source_root": [31.5, 58.0]},
        "variants": [{"canvas": 80, "scale": 1.0, "target_root": [40, 72]}],
    }
    result = spatial_export.export_variants(masters, tmp_path / "out-punch", config)
    manifest = json.loads((tmp_path / "out-punch" / result[0]["manifest"]).read_text())
    assert manifest["clip"]["action"] == "punch"
    assert manifest["clip"]["loop"] is False
    assert manifest["clip"]["frame_durations_seconds"] == [0.125, 0.125, 0.125, 0.125]
    assert sum(manifest["clip"]["frame_durations_seconds"]) == pytest.approx(manifest["clip"]["duration_seconds"])


def test_manifest_player_uses_variable_durations_and_stops_on_last_one_shot_frame(tmp_path: Path) -> None:
    spatial_export.write_player(tmp_path, 160)
    content = (tmp_path / "preview.html").read_text()
    assert "frame_durations_seconds" in content
    assert "manifest.clip.loop" in content
    assert "manifest.frames.length-1" in content


def test_manifest_player_is_generic_and_reports_runtime_state(tmp_path: Path) -> None:
    spatial_export.write_player(tmp_path, 160)

    content = (tmp_path / "preview.html").read_text()
    assert "atlas-160-manifest.json" in content
    assert "atlas-160.png" in content
    assert "window.__animationVerification" in content
    assert "frameAdvanceCount" in content


def test_completed_removal_batch_ingests_exact_receipt_and_derives_geometry(tmp_path: Path) -> None:
    cache = tmp_path / "cache"
    cutouts = []
    items = []
    for order, offset in enumerate((0, 2, -1)):
        source = tmp_path / f"selected-frame-{order:04d}.png"
        cutout = tmp_path / f"cutout-frame-{order:04d}.png"
        _source(source, offset)
        _source(cutout, offset)
        cutouts.append(cutout)
        items.append({
            "order": order, "input": source.name, "input_sha256": _sha(source),
            "status": "completed", "prediction_id": f"prediction-{order}",
            "output": {"file": cutout.name, "sha256": _sha(cutout)},
        })
    (tmp_path / "remove-background-state.json").write_text(json.dumps({
        "status": "completed", "provider": "wavespeed", "model": "remover",
        "preset": "waldlicht-removal-v1", "preset_revision": "1", "items": items,
    }))

    ingested = spatial_export.ingest_completed_removal_batch(
        tmp_path, cache, "waldlicht-removal-v1", "wavespeed-image-background-remover-output-v1",
    )
    geometry = spatial_export.derive_shared_geometry(cutouts, [
        {"canvas": 160, "target_visible_height": 116, "target_root": [80, 144]},
        {"canvas": 80, "target_visible_height": 58, "target_root": [40, 72]},
    ])

    assert len(ingested["items"]) == 3
    assert all(item["new_cache_entry"] for item in ingested["items"])
    assert geometry["evidence"]["frame_count"] == 3
    assert geometry["variants"][0]["scale"] == 2 * geometry["variants"][1]["scale"]
    for index in range(3):
        source = tmp_path / f"selected-frame-{index:04d}.png"
        assert spatial_export.lookup_cached_cutout(source, cache, "waldlicht-removal-v1", "wavespeed-image-background-remover-output-v1") is not None


def test_derived_geometry_scales_down_for_wide_action_extreme(tmp_path: Path) -> None:
    masters = []
    for index, box in enumerate(((28, 8, 36, 58), (1, 8, 63, 58), (28, 8, 36, 58))):
        path = tmp_path / f"wide-{index}.png"
        image = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        ImageDraw.Draw(image).rectangle(box, fill=(80, 100, 120, 255))
        image.save(path)
        masters.append(path)
    geometry = spatial_export.derive_shared_geometry(masters, [
        {"canvas": 80, "target_visible_height": 72, "target_root": [40, 72]},
    ])
    assert geometry["evidence"]["scale_limited_by_batch_bounds"] is True
    assert geometry["variants"][0]["scale"] < 72 / 51
def test_server_cutout_cache_defaults_to_private_jobs_root(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("ANIMATION_CUTOUT_CACHE_DIR", raising=False)
    workdir = tmp_path / "jobs" / "job-id"
    workdir.mkdir(parents=True)

    cache = spatial_export.server_cutout_cache_dir(workdir, create=True)

    assert cache == tmp_path / "jobs" / ".cutout-cache"
    assert cache.is_dir()


