from __future__ import annotations

import hashlib
import json
from pathlib import Path

from PIL import Image, ImageDraw

import quality_gates


ROOT = Path(__file__).parents[1]
BAD_MOTION_JOB = ROOT / "artifacts/live-e2e-20260920T223050Z-91b811/private-service-data/jobs/e0f2fc10ee3949ce89b31dd5d4444c86"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _cutout(path: Path, *, x: int = 10, bottom: int = 28, opaque_background: bool = False) -> None:
    image = Image.new("RGBA", (40, 32), (255, 0, 255, 255) if opaque_background else (0, 0, 0, 0))
    if not opaque_background:
        draw = ImageDraw.Draw(image)
        draw.rectangle((x, 5, x + 12, bottom), fill=(90, 120, 70, 255))
    image.save(path)


def test_cutout_gate_accepts_consistent_true_alpha_and_records_hashes(tmp_path: Path) -> None:
    names = []
    for index, x in enumerate((10, 11, 10, 9)):
        name = f"cutout-frame-{index:04d}.png"
        _cutout(tmp_path / name, x=x)
        names.append(name)

    result = quality_gates.evaluate_cutouts(tmp_path, names)

    assert result["status"] == "passed"
    assert result["visual_quality_certified"] is False
    assert [frame["sha256"] for frame in result["frames"]] == [_sha(tmp_path / name) for name in names]
    assert result["rejection_reasons"] == []


def test_cutout_gate_rejects_opaque_background_without_weakening_threshold(tmp_path: Path) -> None:
    _cutout(tmp_path / "cutout-frame-0000.png", opaque_background=True)

    result = quality_gates.evaluate_cutouts(tmp_path, ["cutout-frame-0000.png"])

    assert result["status"] == "rejected"
    assert "missing_true_alpha" in result["rejection_reasons"]


def test_atlas_gate_verifies_timing_anchor_hash_and_transparency(tmp_path: Path) -> None:
    atlas = Image.new("RGBA", (84, 42), (0, 0, 0, 0))
    atlas.rectangle = None if False else None
    draw = ImageDraw.Draw(atlas)
    draw.rectangle((4, 4, 30, 36), fill=(80, 110, 60, 255))
    draw.rectangle((46, 4, 72, 36), fill=(80, 110, 60, 255))
    atlas.save(tmp_path / "atlas.png")
    manifest = {
        "schema": "animation-pipeline-atlas-v1",
        "image": {"file": "atlas.png", "sha256": _sha(tmp_path / "atlas.png"), "width": 84, "height": 42},
        "clip": {"fps": 10.0, "loop": True, "frames": ["clip.0000", "clip.0001"]},
        "frames": [
            {"id": "clip.0000", "order": 0, "rect": {"x": 1, "y": 1, "width": 40, "height": 40}, "anchor": {"x": 0.5, "y": 0.9}},
            {"id": "clip.0001", "order": 1, "rect": {"x": 43, "y": 1, "width": 40, "height": 40}, "anchor": {"x": 0.5, "y": 0.9}},
        ],
    }
    (tmp_path / "atlas-manifest.json").write_text(json.dumps(manifest))

    result = quality_gates.evaluate_atlas(tmp_path, "atlas.png", "atlas-manifest.json")

    assert result["status"] == "passed"
    assert result["duration_seconds"] == 0.2
    assert result["foot_anchor"] == {"x": 0.5, "y": 0.9}
    assert result["visual_quality_certified"] is False


def test_atlas_gate_rejects_opaque_magenta_sheet(tmp_path: Path) -> None:
    Image.new("RGBA", (16, 16), (255, 0, 255, 255)).save(tmp_path / "atlas.png")
    manifest = {
        "schema": "animation-pipeline-atlas-v1",
        "image": {"file": "atlas.png", "sha256": _sha(tmp_path / "atlas.png"), "width": 16, "height": 16},
        "clip": {"fps": 12, "loop": True, "frames": ["x"]},
        "frames": [{"id": "x", "order": 0, "rect": {"x": 0, "y": 0, "width": 16, "height": 16}, "anchor": {"x": 0.5, "y": 0.9}}],
    }
    (tmp_path / "atlas-manifest.json").write_text(json.dumps(manifest))

    result = quality_gates.evaluate_atlas(tmp_path, "atlas.png", "atlas-manifest.json")

    assert result["status"] == "rejected"
    assert "atlas_has_no_transparency" in result["rejection_reasons"]
    assert "opaque_magenta_background" in result["rejection_reasons"]


def test_atlas_gate_rejects_observed_low_alpha_resample_fringe(tmp_path: Path) -> None:
    atlas = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
    draw = ImageDraw.Draw(atlas)
    draw.rectangle((4, 4, 10, 12), fill=(80, 110, 60, 255))
    atlas.putpixel((3, 3), (0, 0, 0, 4))
    atlas.save(tmp_path / "atlas.png")
    manifest = {
        "schema": "animation-pipeline-atlas-v1",
        "image": {"file": "atlas.png", "sha256": _sha(tmp_path / "atlas.png"), "width": 16, "height": 16},
        "clip": {"fps": 12, "loop": True, "frames": ["x"]},
        "frames": [{"id": "x", "order": 0, "rect": {"x": 0, "y": 0, "width": 16, "height": 16}, "anchor": {"x": 0.5, "y": 0.9}}],
    }
    (tmp_path / "atlas-manifest.json").write_text(json.dumps(manifest))

    result = quality_gates.evaluate_atlas(tmp_path, "atlas.png", "atlas-manifest.json")

    assert result["status"] == "rejected"
    assert result["low_alpha_fringe_pixels"] == 1
    assert "low_alpha_resample_fringe" in result["rejection_reasons"]


def test_atlas_gate_preserves_legitimate_disconnected_opaque_detail(tmp_path: Path) -> None:
    atlas = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
    draw = ImageDraw.Draw(atlas)
    draw.rectangle((3, 3, 8, 13), fill=(80, 110, 60, 255))
    draw.rectangle((11, 7, 12, 9), fill=(240, 180, 40, 255))
    atlas.save(tmp_path / "atlas.png")
    manifest = {
        "schema": "animation-pipeline-atlas-v1",
        "image": {"file": "atlas.png", "sha256": _sha(tmp_path / "atlas.png"), "width": 16, "height": 16},
        "clip": {"fps": 12, "loop": True, "frames": ["x"]},
        "frames": [{"id": "x", "order": 0, "rect": {"x": 0, "y": 0, "width": 16, "height": 16}, "anchor": {"x": 0.5, "y": 0.9}}],
    }
    (tmp_path / "atlas-manifest.json").write_text(json.dumps(manifest))

    result = quality_gates.evaluate_atlas(tmp_path, "atlas.png", "atlas-manifest.json")

    assert result["status"] == "passed"
    assert result["low_alpha_fringe_pixels"] == 0


def test_motion_gate_rejects_known_sparse_rotating_ten_frame_export() -> None:
    indices = [28, 33, 37, 42, 47, 52, 56, 61, 66, 70]
    names = [f"selected-frame-{order:04d}.png" for order in range(10)]

    result = quality_gates.evaluate_motion_sequence(
        BAD_MOTION_JOB,
        names,
        native_indices=indices,
        native_fps=30.0,
        cycle_end_exclusive=75,
        expected_facing="ne",
    )

    assert result["status"] == "rejected"
    assert "sparse_temporal_sampling" in result["rejection_reasons"]
    assert {"orientation_drift", "loop_pose_discontinuity"} & set(result["rejection_reasons"])
    assert result["source_pose_orientation"]["included"] is True
    assert result["visual_quality_certified"] is False


def test_motion_feature_computes_foot_mean_once(monkeypatch) -> None:
    image = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
    ImageDraw.Draw(image).rectangle((70, 20, 190, 240), fill=(80, 110, 60, 255))
    calls = 0
    real_mean = quality_gates.mean

    def counted_mean(values):
        nonlocal calls
        calls += 1
        return real_mean(values)

    monkeypatch.setattr(quality_gates, "mean", counted_mean)
    feature = quality_gates._motion_feature(image)
    feature["normalized"].close()
    image.close()

    assert calls <= 12
