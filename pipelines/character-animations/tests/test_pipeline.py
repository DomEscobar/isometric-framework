from __future__ import annotations

import hashlib
import json
import subprocess
import threading
import time
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

import pipeline


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_inspect_reference_reports_real_alpha_and_is_idempotent(tmp_path: Path) -> None:
    image = Image.new("RGBA", (7, 5), (10, 20, 30, 255))
    image.putpixel((0, 0), (90, 80, 70, 0))
    image.putpixel((1, 0), (90, 80, 70, 128))
    image.save(tmp_path / "reference.png")

    first = pipeline.run_stage("inspect_reference", tmp_path, {"input": "reference.png"})
    second = pipeline.run_stage("inspect_reference", tmp_path, {"input": "reference.png"})

    assert first == second
    assert first["status"] == "completed"
    assert first["artifacts"] == ["inspect-reference.json"]
    assert first["details"]["width"] == 7
    assert first["details"]["height"] == 5
    assert first["details"]["sha256"] == sha256(tmp_path / "reference.png")
    assert first["details"]["alpha"] == {
        "minimum": 0,
        "maximum": 255,
        "transparent_pixels": 1,
        "semi_transparent_pixels": 1,
        "opaque_pixels": 33,
        "visible_bounds": [0, 0, 7, 5],
        "has_true_alpha": True,
    }
    assert json.loads((tmp_path / "inspect-reference.json").read_text())["result"] == first


def test_inspect_reference_rejects_paths_outside_job(tmp_path: Path) -> None:
    outside = tmp_path.parent / "outside.png"
    Image.new("RGBA", (1, 1), (0, 0, 0, 0)).save(outside)
    with pytest.raises(ValueError, match="safe relative"):
        pipeline.run_stage("inspect_reference", tmp_path, {"input": "../outside.png"})


def make_cutout(path: Path, x: int, bottom: int, color: tuple[int, int, int, int]) -> None:
    image = Image.new("RGBA", (20, 24), (0, 0, 0, 0))
    for py in range(bottom - 9, bottom):
        for px in range(x, x + 6):
            image.putpixel((px, py), color)
    image.putpixel((x, bottom - 5), (color[0], color[1], color[2], 128))
    image.save(path)


def pack_params() -> dict:
    return {
        "inputs": ["cutout-0.png", "cutout-1.png"],
        "image_id": "keeper-walk-ne",
        "action": "walk",
        "direction": "ne",
        "fps": 12,
        "loop": True,
        "canvas": {"width": 24, "height": 24},
        "target_visible_height": 12,
        "target_root": {"x": 12, "y": 21},
        "anchor": {"x": 0.5, "y": 0.875},
        "gutter": 1,
        "columns": 2,
        "resample": "nearest",
    }


def test_pack_uses_one_shared_transform_preserves_alpha_and_binds_hashes(tmp_path: Path) -> None:
    make_cutout(tmp_path / "cutout-0.png", 5, 20, (80, 120, 60, 255))
    make_cutout(tmp_path / "cutout-1.png", 7, 21, (90, 130, 70, 255))

    first = pipeline.run_stage("pack", tmp_path, pack_params())
    second = pipeline.run_stage("pack", tmp_path, pack_params())

    assert first == second
    assert first["status"] == "needs_review"
    normalization = json.loads((tmp_path / "normalization.json").read_text())
    assert normalization["shared_transform"]["per_frame_recenter"] is False
    assert normalization["shared_transform"]["per_frame_scale"] is False
    assert len({tuple(item["scaled_full_canvas"]) for item in normalization["frames"]}) == 1
    manifest = json.loads((tmp_path / "atlas-manifest.json").read_text())
    assert manifest["schema"] == "animation-pipeline-atlas-v1"
    assert manifest["certification"]["stock_framework_v4_claimed"] is False
    assert manifest["clip"]["frames"] == ["keeper-walk-ne.walk.ne.0000", "keeper-walk-ne.walk.ne.0001"]
    assert first["details"]["atlas_sha256"] == sha256(tmp_path / "atlas.png")
    assert first["details"]["manifest_sha256"] == sha256(tmp_path / "atlas-manifest.json")
    with Image.open(tmp_path / "normalized-frame-0000.png") as normalized:
        assert normalized.mode == "RGBA"
        assert 128 in normalized.getchannel("A").get_flattened_data()


def test_pack_rejects_clipping_instead_of_silently_cropping(tmp_path: Path) -> None:
    make_cutout(tmp_path / "cutout-0.png", 5, 20, (80, 120, 60, 255))
    make_cutout(tmp_path / "cutout-1.png", 7, 21, (90, 130, 70, 255))
    params = pack_params()
    params["target_root"] = {"x": 0, "y": 0}
    with pytest.raises(ValueError, match="clips or touches"):
        pipeline.run_stage("pack", tmp_path, params)


def test_pack_explicit_cleanup_removes_weak_fringe_and_preserves_disconnected_detail(tmp_path: Path) -> None:
    for name, x in (("cutout-0.png", 5), ("cutout-1.png", 7)):
        make_cutout(tmp_path / name, x, 20, (80, 120, 60, 255))
        with Image.open(tmp_path / name) as opened:
            image = opened.convert("RGBA")
        image.putpixel((3, 15), (20, 30, 40, 4))
        image.putpixel((14, 17), (240, 180, 40, 255))  # legitimate detached lantern/detail
        image.save(tmp_path / name)
        image.close()
    params = pack_params()
    params["cleanup"] = {"recipe": "conservative-alpha-fringe-v1", "minimum_visible_alpha": 8}

    result = pipeline.run_stage("pack", tmp_path, params)

    assert result["status"] == "needs_review"
    normalization = json.loads((tmp_path / "normalization.json").read_text())
    cleanup = normalization["quality_cleanup"]
    assert cleanup["recipe"] == "conservative-alpha-fringe-v1"
    assert len(cleanup["recipe_sha256"]) == 64
    assert cleanup["total_pixels_cleared"] > 0
    with Image.open(tmp_path / "normalized-frame-0000.png") as normalized:
        pixels = list(normalized.get_flattened_data())
        assert all(not 0 < pixel[3] < 8 for pixel in pixels)
        assert (240, 180, 40, 255) in pixels
    manifest = json.loads((tmp_path / "atlas-manifest.json").read_text())
    assert manifest["quality_cleanup"]["recipe_sha256"] == cleanup["recipe_sha256"]


def test_mirror_is_exact_rgba_derivation_and_is_labelled(tmp_path: Path) -> None:
    make_cutout(tmp_path / "cutout-0.png", 5, 20, (80, 120, 60, 255))
    make_cutout(tmp_path / "cutout-1.png", 7, 21, (90, 130, 70, 255))
    pipeline.run_stage("pack", tmp_path, pack_params())

    result = pipeline.run_stage("mirror", tmp_path, {
        "atlas": "atlas.png",
        "manifest": "atlas-manifest.json",
        "target_direction": "nw",
        "target_image_id": "keeper-walk-nw-derived",
    })

    assert result["status"] == "needs_review"
    derived = json.loads((tmp_path / "mirror-manifest.json").read_text())
    assert derived["derivation_status"] == "DERIVED_NOT_PROVIDER_GENERATED"
    assert "handed" in derived["warning"].lower()
    source_manifest = json.loads((tmp_path / "atlas-manifest.json").read_text())
    with Image.open(tmp_path / "atlas.png") as source, Image.open(tmp_path / "mirror-atlas.png") as mirror:
        for source_frame, target_frame in zip(source_manifest["frames"], derived["frames"]):
            s = source.crop((source_frame["rect"]["x"], source_frame["rect"]["y"], source_frame["rect"]["x"] + source_frame["rect"]["width"], source_frame["rect"]["y"] + source_frame["rect"]["height"]))
            t = mirror.crop((target_frame["rect"]["x"], target_frame["rect"]["y"], target_frame["rect"]["x"] + target_frame["rect"]["width"], target_frame["rect"]["y"] + target_frame["rect"]["height"]))
            assert t.tobytes() == s.transpose(Image.Transpose.FLIP_LEFT_RIGHT).tobytes()


def test_extract_frames_keeps_only_explicit_selected_indices(tmp_path: Path) -> None:
    for index, color in enumerate(((255, 0, 0, 255), (0, 255, 0, 255), (0, 0, 255, 255))):
        Image.new("RGBA", (6, 4), color).save(tmp_path / f"video-{index:04d}.png")
    subprocess.run([
        "ffmpeg", "-v", "error", "-framerate", "3", "-i", str(tmp_path / "video-%04d.png"),
        "-c:v", "png", "-pix_fmt", "rgba", str(tmp_path / "source.mov"),
    ], check=True)

    result = pipeline.run_stage("extract_frames", tmp_path, {"input": "source.mov", "fps": 3, "indices": [0, 2], "output_prefix": "chosen"})

    assert result["status"] == "needs_review"
    assert (tmp_path / "chosen-frame-0000.png").is_file()
    assert (tmp_path / "chosen-frame-0001.png").is_file()
    assert not (tmp_path / "chosen-frame-0002.png").exists()
    record = json.loads((tmp_path / "extract-frames.json").read_text())
    assert [item["source_index"] for item in record["frames"]] == [0, 2]
    assert [item["timestamp_seconds"] for item in record["frames"]] == [0.0, pytest.approx(2 / 3)]


def test_automatic_extract_supports_sparse_native_indices(tmp_path: Path) -> None:
    for index, color in enumerate(((255, 0, 0, 255), (0, 255, 0, 255), (0, 0, 255, 255))):
        Image.new("RGBA", (6, 4), color).save(tmp_path / f"video-{index:04d}.png")
    subprocess.run([
        "ffmpeg", "-v", "error", "-framerate", "3", "-i", str(tmp_path / "video-%04d.png"),
        "-c:v", "png", "-pix_fmt", "rgba", str(tmp_path / "source.mov"),
    ], check=True)
    receipt = {"id": "review-1", "model": "google/gemini-3.8-flash", "source_sha256": sha256(tmp_path / "source.mov")}

    result = pipeline.run_stage("extract_frames", tmp_path, {
        "input": "source.mov", "fps": 2, "indices": [0, 2], "output_prefix": "selected", "automatic_review": receipt,
    })

    assert result["status"] == "needs_review"
    record = json.loads((tmp_path / "extract-frames.json").read_text())
    assert [item["source_index"] for item in record["frames"]] == [0, 2]
    assert record["decode"]["selection"] == "exact_sparse_native_frame_indices"
    assert record["automatic_selection"] is True


def test_paid_stage_rejects_missing_budget_before_provider(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    Image.new("RGB", (4, 4), (1, 2, 3)).save(tmp_path / "reference.png")
    monkeypatch.setattr(pipeline, "_provider_for", lambda name: (_ for _ in ()).throw(AssertionError("provider touched")), raising=False)
    with pytest.raises(ValueError, match="authorized budget"):
        pipeline.run_stage("generate_facing", tmp_path, {"input": "reference.png", "prompt": "rotate", "budget": {"authorized": False, "max_usd": 1}})


def test_ambiguous_paid_submit_is_durable_needs_attention_and_not_retried(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import provider
    Image.new("RGB", (4, 4), (1, 2, 3)).save(tmp_path / "reference.png")

    class AmbiguousAdapter:
        submissions = 0
        def upload(self, path, content_type=None):
            return "https://media.example/owned.png"
        def submit(self, model, payload):
            self.submissions += 1
            raise provider.AmbiguousSubmission("lost")

    adapter = AmbiguousAdapter()
    monkeypatch.setattr(pipeline, "_provider_for", lambda name: adapter, raising=False)
    params = {"input": "reference.png", "prompt": "rotate", "budget": {"authorized": True, "max_usd": 0.011}}

    first = pipeline.run_stage("generate_facing", tmp_path, params)
    second = pipeline.run_stage("generate_facing", tmp_path, params)

    assert first == second
    assert first["status"] == "needs_attention"
    assert adapter.submissions == 1
    state = json.loads((tmp_path / "generate-facing-state.json").read_text())
    assert state["submission_status"] == "submission_unknown"


def test_remove_background_mocked_batch_validates_alpha_and_is_idempotent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    Image.new("RGB", (8, 8), (100, 110, 120)).save(tmp_path / "selected-frame-0000.png")

    class CompletedAdapter:
        submissions = 0
        def upload(self, path, content_type=None):
            return "https://media.example/job-owned.png"
        def submit(self, model, payload):
            self.submissions += 1
            return {"id": "removal_1", "status": "created"}
        def poll(self, prediction_id):
            return {"id": prediction_id, "status": "completed", "outputs": ["https://output.example/cutout.png"]}
        def download(self, url, target):
            image = Image.new("RGBA", (8, 8), (10, 20, 30, 0))
            for y in range(2, 7):
                for x in range(2, 6):
                    image.putpixel((x, y), (70, 100, 50, 255 if x > 2 else 128))
            image.save(target)

    adapter = CompletedAdapter()
    monkeypatch.setattr(pipeline, "_provider_for", lambda name: adapter)
    params = {"inputs": ["selected-frame-0000.png"], "budget": {"authorized": True, "max_usd": 0.004}}

    first = pipeline.run_stage("remove_background", tmp_path, params)
    second = pipeline.run_stage("remove_background", tmp_path, params)

    assert first == second
    assert first["status"] == "needs_review"
    assert adapter.submissions == 1
    assert first["details"]["frames"][0]["alpha"]["has_true_alpha"] is True
    assert first["details"]["quote"]["quoted_usd"] == 0.004


def test_remove_background_submits_only_bounded_inflight_predictions(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    for order in range(4):
        Image.new("RGB", (8, 8), (100, 110, 120)).save(tmp_path / f"selected-frame-{order:04d}.png")

    class PendingAdapter:
        def __init__(self):
            self.submissions = []
        def upload(self, path, content_type=None):
            return f"https://media.example/{path.name}"
        def submit(self, model, payload):
            prediction_id = f"removal_{len(self.submissions)}"
            self.submissions.append(prediction_id)
            return {"id": prediction_id, "status": "created"}
        def poll(self, prediction_id):
            return {"id": prediction_id, "status": "pending", "outputs": []}

    adapter = PendingAdapter()
    monkeypatch.setenv("ANIMATION_REMOVAL_MAX_INFLIGHT", "2")
    monkeypatch.setattr(pipeline, "_provider_for", lambda name: adapter)
    params = {"inputs": [f"selected-frame-{order:04d}.png" for order in range(4)], "budget": {"authorized": True, "max_usd": 0.016}}

    first = pipeline.run_stage("remove_background", tmp_path, params)
    second = pipeline.run_stage("remove_background", tmp_path, params)

    assert first["status"] == second["status"] == "needs_attention"
    assert len(adapter.submissions) == 2
    state = json.loads((tmp_path / "remove-background-state.json").read_text())
    assert [item["status"] for item in state["items"]] == ["known_prediction", "known_prediction", "not_submitted", "not_submitted"]
    assert first["details"]["inflight"] == 2


def test_remove_background_accepts_five_as_bounded_default(monkeypatch):
    monkeypatch.delenv("ANIMATION_REMOVAL_MAX_INFLIGHT", raising=False)
    assert pipeline._removal_maximum_inflight() == 5
    monkeypatch.setenv("ANIMATION_REMOVAL_MAX_INFLIGHT", "6")
    with pytest.raises(ValueError, match="between 1 and 5"):
        pipeline._removal_maximum_inflight()


def test_remove_background_overlaps_bounded_uploads_and_completed_downloads(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    for order in range(2):
        Image.new("RGB", (8, 8), (100, 110, 120)).save(tmp_path / f"selected-frame-{order:04d}.png")

    class NetworkAdapter:
        def __init__(self):
            self.lock = threading.Lock()
            self.active_uploads = 0
            self.maximum_uploads = 0
            self.active_downloads = 0
            self.maximum_downloads = 0
            self.submissions = []
            self.poll_counts = {}
        def upload(self, path, content_type=None):
            with self.lock:
                self.active_uploads += 1
                self.maximum_uploads = max(self.maximum_uploads, self.active_uploads)
            time.sleep(0.05)
            with self.lock:
                self.active_uploads -= 1
            return f"https://media.example/{path.name}"
        def submit(self, model, payload):
            prediction_id = f"removal_{len(self.submissions)}"
            self.submissions.append(prediction_id)
            return {"id": prediction_id}
        def poll(self, prediction_id):
            self.poll_counts[prediction_id] = self.poll_counts.get(prediction_id, 0) + 1
            if self.poll_counts[prediction_id] == 1:
                return {"id": prediction_id, "status": "pending", "outputs": []}
            return {"id": prediction_id, "status": "completed", "outputs": [f"https://output.example/{prediction_id}.png"]}
        def download(self, url, target):
            with self.lock:
                self.active_downloads += 1
                self.maximum_downloads = max(self.maximum_downloads, self.active_downloads)
            time.sleep(0.05)
            image = Image.new("RGBA", (8, 8), (0, 0, 0, 0))
            ImageDraw.Draw(image).rectangle((2, 2, 5, 6), fill=(70, 100, 50, 255))
            image.save(target)
            with self.lock:
                self.active_downloads -= 1

    adapter = NetworkAdapter()
    monkeypatch.setenv("ANIMATION_REMOVAL_MAX_INFLIGHT", "2")
    monkeypatch.setattr(pipeline, "_provider_for", lambda name: adapter)
    params = {"inputs": [f"selected-frame-{order:04d}.png" for order in range(2)], "budget": {"authorized": True, "max_usd": 0.008}}

    assert pipeline.run_stage("remove_background", tmp_path, params)["status"] == "needs_attention"
    assert pipeline.run_stage("remove_background", tmp_path, params)["status"] == "needs_review"

    assert adapter.maximum_uploads == 2
    assert adapter.maximum_downloads == 2
    state = json.loads((tmp_path / "remove-background-state.json").read_text())
    assert [item["status"] for item in state["items"]] == ["completed", "completed"]
    assert [item["prediction_id"] for item in state["items"]] == ["removal_0", "removal_1"]


def test_remove_background_ambiguous_submit_holds_uploaded_later_item_without_paid_retry(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import provider
    for order in range(2):
        Image.new("RGB", (8, 8), (100, 110, 120)).save(tmp_path / f"selected-frame-{order:04d}.png")

    class AmbiguousBatchAdapter:
        def __init__(self):
            self.submissions = 0
        def upload(self, path, content_type=None):
            return f"https://media.example/{path.name}"
        def submit(self, model, payload):
            self.submissions += 1
            raise provider.AmbiguousSubmission("lost response")

    adapter = AmbiguousBatchAdapter()
    monkeypatch.setenv("ANIMATION_REMOVAL_MAX_INFLIGHT", "2")
    monkeypatch.setattr(pipeline, "_provider_for", lambda name: adapter)
    params = {"inputs": [f"selected-frame-{order:04d}.png" for order in range(2)], "budget": {"authorized": True, "max_usd": 0.008}}

    first = pipeline.run_stage("remove_background", tmp_path, params)
    second = pipeline.run_stage("remove_background", tmp_path, params)

    assert first == second
    assert adapter.submissions == 1
    state = json.loads((tmp_path / "remove-background-state.json").read_text())
    assert state["items"][0]["status"] == "submission_unknown"
    assert state["items"][1]["status"] == "uploaded"


def test_remove_background_interrupted_submit_becomes_unknown_and_is_never_retried(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    Image.new("RGB", (8, 8), (100, 110, 120)).save(tmp_path / "selected-frame-0000.png")

    class InterruptedAdapter:
        def __init__(self):
            self.submissions = 0
        def upload(self, path, content_type=None):
            return "https://media.example/frame.png"
        def submit(self, model, payload):
            self.submissions += 1
            raise RuntimeError("simulated process interruption during POST")

    adapter = InterruptedAdapter()
    monkeypatch.setattr(pipeline, "_provider_for", lambda name: adapter)
    params = {"inputs": ["selected-frame-0000.png"], "budget": {"authorized": True, "max_usd": 0.004}}

    with pytest.raises(RuntimeError, match="interruption"):
        pipeline.run_stage("remove_background", tmp_path, params)
    resumed = pipeline.run_stage("remove_background", tmp_path, params)
    repeated = pipeline.run_stage("remove_background", tmp_path, params)

    assert resumed == repeated
    assert resumed["status"] == "needs_attention"
    assert resumed["details"]["safe_to_resubmit"] is False
    assert adapter.submissions == 1
    state = json.loads((tmp_path / "remove-background-state.json").read_text())
    assert state["items"][0]["status"] == "submission_unknown"


def test_remove_background_resumes_known_ids_before_submitting_next_order(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    for order in range(3):
        Image.new("RGB", (8, 8), (100, 110, 120)).save(tmp_path / f"selected-frame-{order:04d}.png")

    class ResumingAdapter:
        def __init__(self):
            self.submissions = []
            self.polls = {}
        def upload(self, path, content_type=None):
            return f"https://media.example/{path.name}"
        def submit(self, model, payload):
            prediction_id = f"removal_{len(self.submissions)}"
            self.submissions.append(prediction_id)
            return {"id": prediction_id}
        def poll(self, prediction_id):
            self.polls[prediction_id] = self.polls.get(prediction_id, 0) + 1
            if self.polls[prediction_id] == 1:
                return {"id": prediction_id, "status": "pending", "outputs": []}
            return {"id": prediction_id, "status": "completed", "outputs": [f"https://output.example/{prediction_id}.png"]}
        def download(self, url, target):
            image = Image.new("RGBA", (8, 8), (0, 0, 0, 0))
            ImageDraw.Draw(image).rectangle((2, 2, 5, 6), fill=(70, 100, 50, 255))
            image.save(target)

    adapter = ResumingAdapter()
    monkeypatch.setenv("ANIMATION_REMOVAL_MAX_INFLIGHT", "2")
    monkeypatch.setattr(pipeline, "_provider_for", lambda name: adapter)
    params = {"inputs": [f"selected-frame-{order:04d}.png" for order in range(3)], "budget": {"authorized": True, "max_usd": 0.012}}

    assert pipeline.run_stage("remove_background", tmp_path, params)["status"] == "needs_attention"
    final = pipeline.run_stage("remove_background", tmp_path, params)

    assert final["status"] == "needs_attention"
    assert adapter.submissions == ["removal_0", "removal_1", "removal_2"]
    state = json.loads((tmp_path / "remove-background-state.json").read_text())
    assert [item["prediction_id"] for item in state["items"]] == adapter.submissions
    assert [item["status"] for item in state["items"]] == ["completed", "completed", "known_prediction"]


def test_remove_background_partial_failure_never_submits_remaining_items(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    for order in range(3):
        Image.new("RGB", (8, 8), (100, 110, 120)).save(tmp_path / f"selected-frame-{order:04d}.png")

    class PartialFailureAdapter:
        def __init__(self):
            self.submissions = []
            self.poll_counts = {}
        def upload(self, path, content_type=None):
            return f"https://media.example/{path.name}"
        def submit(self, model, payload):
            prediction_id = f"removal_{len(self.submissions)}"
            self.submissions.append(prediction_id)
            return {"id": prediction_id}
        def poll(self, prediction_id):
            self.poll_counts[prediction_id] = self.poll_counts.get(prediction_id, 0) + 1
            if self.poll_counts[prediction_id] == 1:
                return {"id": prediction_id, "status": "pending", "outputs": []}
            if prediction_id == "removal_1":
                return {"id": prediction_id, "status": "failed", "outputs": []}
            return {"id": prediction_id, "status": "completed", "outputs": [f"https://output.example/{prediction_id}.png"]}
        def download(self, url, target):
            image = Image.new("RGBA", (8, 8), (0, 0, 0, 0))
            ImageDraw.Draw(image).rectangle((2, 2, 5, 6), fill=(70, 100, 50, 255))
            image.save(target)

    adapter = PartialFailureAdapter()
    monkeypatch.setenv("ANIMATION_REMOVAL_MAX_INFLIGHT", "2")
    monkeypatch.setattr(pipeline, "_provider_for", lambda name: adapter)
    params = {"inputs": [f"selected-frame-{order:04d}.png" for order in range(3)], "budget": {"authorized": True, "max_usd": 0.012}}

    assert pipeline.run_stage("remove_background", tmp_path, params)["status"] == "needs_attention"
    with pytest.raises(ValueError, match="prediction failed"):
        pipeline.run_stage("remove_background", tmp_path, params)
    with pytest.raises(ValueError, match="previous provider failure"):
        pipeline.run_stage("remove_background", tmp_path, params)

    assert adapter.submissions == ["removal_0", "removal_1"]
    state = json.loads((tmp_path / "remove-background-state.json").read_text())
    assert state["items"][1]["status"] == "provider_failed"
    assert state["items"][2]["status"] == "not_submitted"


def test_gemini_video_stage_submits_exact_model_request_without_wan_fields(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    Image.new("RGBA", (16, 16), (1, 2, 3, 255)).save(tmp_path / "reference.png")

    class CompletedAdapter:
        submitted = None
        def upload(self, path, content_type=None):
            return "https://media.example/accepted-se.png"
        def submit(self, model, payload):
            self.submitted = (model, payload)
            return {"id": "gemini_video_1", "status": "created"}
        def poll(self, prediction_id):
            return {"id": prediction_id, "status": "completed", "outputs": ["https://output.example/video.mp4"]}
        def download(self, url, target):
            target.write_bytes(b"mock video")

    adapter = CompletedAdapter()
    monkeypatch.setattr(pipeline, "_provider_for", lambda name: adapter)
    params = {
        "input": "reference.png",
        "preset": "gemini-omni-video-3s-v1",
        "prompt": "same SE character walking in place",
        "duration": 3,
        "resolution": "360p",
        "aspect_ratio": "16:9",
        "budget": {"authorized": True, "max_usd": 0.10},
    }

    result = pipeline.run_stage("generate_video", tmp_path, params)

    assert result["status"] == "needs_review"
    assert adapter.submitted == (
        "google/gemini-omni-1.1-flash/image-to-video",
        {
            "image": "https://media.example/accepted-se.png",
            "prompt": "same SE character walking in place",
            "duration": 3,
            "resolution": "360p",
            "aspect_ratio": "16:9",
        },
    )
    state = json.loads((tmp_path / "generate-video-state.json").read_text())
    assert state["provider_request"] == adapter.submitted[1]
    assert state["quote"]["quoted_usd"] == 0.09


def test_minimax_video_stage_submits_same_uploaded_image_as_first_and_last(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    Image.new("RGB", (16, 16), (210, 210, 210)).save(tmp_path / "reference.png")

    class CompletedAdapter:
        submitted = None
        def upload(self, path, content_type=None):
            return "https://media.example/approved-ne.png"
        def submit(self, model, payload):
            self.submitted = (model, payload)
            return {"id": "minimax_video_1", "status": "created"}
        def poll(self, prediction_id):
            return {"id": prediction_id, "status": "completed", "outputs": ["https://output.example/video.mp4"]}
        def download(self, url, target):
            target.write_bytes(b"mock video")

    adapter = CompletedAdapter()
    monkeypatch.setattr(pipeline, "_provider_for", lambda name: adapter)
    params = {
        "input": "reference.png",
        "preset": "minimax-h3-ne-source-5s-768p-v1",
        "prompt": "fixed-camera NE walk in place",
        "duration": 5,
        "resolution": "768p",
        "budget": {"authorized": True, "max_usd": 0.50},
    }

    result = pipeline.run_stage("generate_video", tmp_path, params)

    assert result["status"] == "needs_review"
    assert adapter.submitted == (
        "wavespeed-ai/minimax-h3/image-to-video",
        {
            "prompt": "fixed-camera NE walk in place",
            "image": "https://media.example/approved-ne.png",
            "last_image": "https://media.example/approved-ne.png",
            "duration": 5,
            "resolution": "768p",
        },
    )


def test_minimax_selected_options_bind_quote_payload_and_provenance(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    Image.new("RGB", (16, 16), (210, 210, 210)).save(tmp_path / "reference.png")

    class CompletedAdapter:
        submitted = None
        def upload(self, path, content_type=None):
            return "https://media.example/approved-ne.png"
        def submit(self, model, payload):
            self.submitted = (model, payload)
            return {"id": "minimax_video_10s", "status": "created"}
        def poll(self, prediction_id):
            return {"id": prediction_id, "status": "completed", "outputs": ["https://output.example/video.mp4"]}
        def download(self, url, target):
            target.write_bytes(b"mock video")

    adapter = CompletedAdapter()
    monkeypatch.setattr(pipeline, "_provider_for", lambda name: adapter)
    params = {
        "input": "reference.png", "preset": "minimax-h3-action-3s-480p-v1",
        "prompt": "one in-place punch", "duration": 10, "resolution": "768p",
        "budget": {"authorized": True, "max_usd": 0.40},
    }
    result = pipeline.run_stage("generate_video", tmp_path, params)
    state = json.loads((tmp_path / "generate-video-state.json").read_text())

    assert result["status"] == "needs_review"
    assert adapter.submitted[1]["duration"] == 10
    assert adapter.submitted[1]["resolution"] == "768p"
    assert state["request"]["params"]["duration"] == 10
    assert state["request"]["params"]["resolution"] == "768p"
    assert state["provider_request"]["duration"] == 10
    assert state["provider_request"]["resolution"] == "768p"
    assert state["quote"]["priced_inputs"] == {"duration": 10, "resolution": "768p"}
    assert state["quote"]["quoted_usd"] == 0.4


def test_minimax_selected_quote_is_reserved_before_provider_upload(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    Image.new("RGB", (16, 16), (210, 210, 210)).save(tmp_path / "reference.png")

    class NoCallAdapter:
        uploads = 0
        def upload(self, path, content_type=None):
            self.uploads += 1
            raise AssertionError("provider upload must not run below the selected quote")

    adapter = NoCallAdapter()
    monkeypatch.setattr(pipeline, "_provider_for", lambda name: adapter)
    with pytest.raises(ValueError, match="below the recorded quote"):
        pipeline.run_stage("generate_video", tmp_path, {
            "input": "reference.png", "preset": "minimax-h3-action-3s-480p-v1",
            "prompt": "one in-place punch", "duration": 10, "resolution": "768p",
            "budget": {"authorized": True, "max_usd": 0.39},
        })
    assert adapter.uploads == 0
