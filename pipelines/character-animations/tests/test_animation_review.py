from __future__ import annotations

import hashlib
import json
import subprocess
import base64
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

import animation_review


def _make_video(root: Path, positions: list[int], *, cropped: bool = False, fps: int = 6) -> Path:
    frames = root / "frames"
    frames.mkdir()
    for index, x in enumerate(positions):
        image = Image.new("RGB", (96, 96), "white")
        draw = ImageDraw.Draw(image)
        bottom = 96 if cropped else 86
        draw.rectangle((x, 30, x + 20, bottom), fill="black")
        image.save(frames / f"frame-{index:04d}.png")
    target = root / "source.mp4"
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-framerate",
            str(fps),
            "-i",
            str(frames / "frame-%04d.png"),
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            str(target),
        ],
        check=True,
    )
    return target


def test_analyze_candidates_preserves_original_timeline_and_ranks_motion(tmp_path: Path) -> None:
    source = _make_video(tmp_path, [20, 28, 36, 28, 20, 28, 36, 28, 20, 28, 36, 28])

    result = animation_review.analyze_candidates(
        tmp_path,
        source.name,
        sample_fps=3,
        minimum_loop_seconds=0.8,
        maximum_loop_seconds=1.8,
    )

    assert result["source"]["sha256"] == hashlib.sha256(source.read_bytes()).hexdigest()
    assert result["source"]["native_fps"] == pytest.approx(6.0)
    assert result["samples"][1]["sample_index"] == 1
    assert result["samples"][1]["timestamp_seconds"] == pytest.approx(1 / 3)
    assert result["samples"][1]["source_frame_index"] == 2
    assert result["status"] == "candidate_suggested"
    assert result["candidates"]
    assert result["candidates"][0]["heuristic_only"] is True
    assert result["candidates"][0]["start_source_frame_index"] in range(12)
    assert result["candidates"][0]["end_source_frame_index"] in range(12)


def test_analyze_candidates_rejects_static_source(tmp_path: Path) -> None:
    _make_video(tmp_path, [30] * 12)

    result = animation_review.analyze_candidates(tmp_path, "source.mp4", sample_fps=3)

    assert result["status"] == "rejected"
    assert "static_source" in result["hard_failures"]
    assert result["candidates"] == []


def test_punch_analysis_trims_only_excess_rest_and_proposes_semantic_phases(tmp_path: Path) -> None:
    frames = tmp_path / "frames"
    frames.mkdir()
    extensions = [0] * 6 + [2, 6, 12, 20, 12, 6, 2, 0] + [0] * 6
    for index, extension in enumerate(extensions):
        image = Image.new("RGB", (96, 96), "white")
        draw = ImageDraw.Draw(image)
        draw.rectangle((38, 25, 57, 85), fill="black")
        draw.rectangle((54, 38, 57 + extension, 45), fill="black")
        image.save(frames / f"frame-{index:04d}.png")
    source = tmp_path / "source.mp4"
    subprocess.run([
        "ffmpeg", "-v", "error", "-framerate", "12", "-i", str(frames / "frame-%04d.png"),
        "-c:v", "libx264", "-pix_fmt", "yuv420p", str(source),
    ], check=True)

    result = animation_review.analyze_candidates(
        tmp_path, source.name, sample_fps=12, minimum_loop_seconds=0.25,
        maximum_loop_seconds=2.5, action="punch",
    )

    assert result["status"] == "requires_semantic_review", result["hard_failures"]
    candidate = result["candidates"][0]
    assert 0 < candidate["start_source_frame_index"]
    assert candidate["end_source_frame_index"] < result["source"]["frame_count"]
    phases = candidate["phase_proposals"]
    assert candidate["start_source_frame_index"] < phases["anticipation"]
    assert phases["anticipation"] < phases["maximum_extension"] < phases["recovery"]
    assert phases["recovery"] < candidate["end_source_frame_index"]
    assert "semantic_confirmation_of_action_phases" in candidate["semantic_review_reasons"]


def test_analyze_candidates_rejects_edge_cropped_source(tmp_path: Path) -> None:
    _make_video(tmp_path, [20, 28, 36, 28, 20, 28, 36, 28, 20, 28, 36, 28], cropped=True)

    result = animation_review.analyze_candidates(tmp_path, "source.mp4", sample_fps=3)

    assert result["status"] == "rejected"
    assert "foreground_touches_frame_edge" in result["hard_failures"]
    assert result["framing"]["edge_touch_sample_indices"]


def test_real_analyzer_does_not_rank_known_rotating_interval_as_valid_cycle() -> None:
    workdir = Path(__file__).parents[1] / "artifacts/live-e2e-20260920T223050Z-91b811/preflight-analysis"

    result = animation_review.analyze_candidates(workdir, "video-output.mp4")

    assert result["source"]["sha256"] == "2ca54f300087f790fbc02f1e938ff979700a9e52077da07eff96c33fb6e4e18e"
    assert result["status"] == "requires_semantic_review"
    assert result["hard_failures"] == []
    assert result["candidates"]
    assert all(
        "color_specific_orientation_ambiguous" in item["semantic_review_reasons"]
        for item in result["candidates"]
    )
    assert result["source_pose_orientation"]["included"] is True
    assert result["source_pose_orientation"]["automatic_direction_pass"] is False


@pytest.mark.parametrize(
    ("relative_source", "expected_hash"),
    [
        ("artifacts/minimax-ne-source-01/video-output.mp4", "cd02ae6369794274e49df2253ee8c5b100d7192ba9a5c5c94d98fe59a41e42dd"),
        ("review/real-cold-e2e-01/source-video.mp4", "b0a962f49467df55859e838187430d05c3581e044e373f8f19655a1f0db4d2b2"),
    ],
)
def test_real_minimax_sources_route_color_orientation_to_semantic_review(relative_source: str, expected_hash: str) -> None:
    source = Path(__file__).parents[1] / relative_source

    result = animation_review.analyze_candidates(source.parent, source.name)

    assert result["source"]["sha256"] == expected_hash
    assert result["status"] == "requires_semantic_review"
    assert result["hard_failures"] == []
    assert result["candidates"]
    assert result["source_pose_orientation"]["method"] == "color_specific_head_roi_v1"
    assert result["source_pose_orientation"]["automatic_direction_pass"] is False


def test_real_clipped_omni_remains_a_deterministic_hard_rejection() -> None:
    source = Path(__file__).parents[1] / "artifacts/gemini-omni-video-3s-01/video-output.mp4"

    result = animation_review.analyze_candidates(source.parent, source.name)

    assert result["source"]["sha256"] == "c8ec28d43b069875b2a41174af60bbbe6113f6c13d149b92085f786edfaad34f"
    assert result["status"] == "rejected"
    assert "foreground_touches_frame_edge" in result["hard_failures"]


@pytest.mark.parametrize("unsafe", ["https://example.test/video.mp4", "../source.mp4", "/tmp/source.mp4"])
def test_analyze_candidates_rejects_remote_or_unconfined_input(tmp_path: Path, unsafe: str) -> None:
    with pytest.raises(ValueError, match="confined local video"):
        animation_review.analyze_candidates(tmp_path, unsafe)


def test_build_review_request_contains_exact_video_and_boundary_evidence(tmp_path: Path) -> None:
    source = _make_video(tmp_path, [20, 28, 36, 28, 20, 28, 36, 28, 20, 28, 36, 28])
    analysis = animation_review.analyze_candidates(tmp_path, source.name, sample_fps=3, minimum_loop_seconds=0.8, maximum_loop_seconds=1.8)

    request = animation_review.build_review_request(tmp_path, source.name, analysis, evidence_mode="native_video")

    assert request["model"] == "google/gemini-3.8-flash"
    assert request["provider"]["allow_fallbacks"] is False
    assert request["provider"]["data_collection"] == "deny"
    assert request["provider"]["require_parameters"] is True
    assert request["reasoning"] == {"effort": "low", "exclude": True}
    assert request["response_format"]["type"] == "json_schema"
    content = request["messages"][0]["content"]
    video_items = [item for item in content if item["type"] == "video_url"]
    assert len(video_items) == 1
    encoded_video = video_items[0]["video_url"]["url"].split(",", 1)[1]
    assert base64.b64decode(encoded_video) == source.read_bytes()
    labels = [item["text"] for item in content if item["type"] == "text" and item["text"].startswith("FRAME EVIDENCE")]
    assert labels
    assert all("sample_index=" in label and "timestamp_seconds=" in label and "source_frame_index=" in label for label in labels)
    assert "deepseek" not in json.dumps(request).lower()


def test_build_review_request_uses_bounded_numbered_image_sequence_by_default(tmp_path: Path) -> None:
    source = _make_video(tmp_path, [20, 28, 36, 28, 20, 28, 36, 28, 20, 28, 36, 28])
    analysis = animation_review.analyze_candidates(tmp_path, source.name, sample_fps=3, minimum_loop_seconds=0.8, maximum_loop_seconds=1.8)

    request = animation_review.build_review_request(tmp_path, source.name, analysis, max_tokens=300)

    content = request["messages"][0]["content"]
    assert not [item for item in content if item["type"] == "video_url"]
    images = [item for item in content if item["type"] == "image_url"]
    assert len(images) == min(12, len(analysis["samples"]))
    labels = [item["text"] for item in content if item["type"] == "text" and item["text"].startswith("FRAME EVIDENCE")]
    assert len(labels) == len(images)
    assert request["_review_evidence"]["mode"] == "numbered_image_sequence"
    assert request["_review_evidence"]["image_count"] == len(images)
    assert request["_review_evidence"]["conservative_input_token_bound"] >= len(images) * 1120
    assert request["_review_evidence"]["native_video_sent"] is False


def test_build_review_request_rejects_stale_hash_or_other_model(tmp_path: Path) -> None:
    source = _make_video(tmp_path, [20, 28, 36, 28, 20, 28, 36, 28, 20, 28, 36, 28])
    analysis = animation_review.analyze_candidates(tmp_path, source.name, sample_fps=3)
    analysis["source"]["sha256"] = "0" * 64

    with pytest.raises(ValueError, match="source provenance"):
        animation_review.build_review_request(tmp_path, source.name, analysis)
    with pytest.raises(ValueError, match="exact configured review model"):
        animation_review.build_review_request(tmp_path, source.name, analysis, model="google/gemini-3-flash")


def test_validate_review_result_binds_candidate_to_server_owned_bounds(tmp_path: Path) -> None:
    source = _make_video(tmp_path, [20, 28, 36, 28, 20, 28, 36, 28, 20, 28, 36, 28])
    analysis = animation_review.analyze_candidates(tmp_path, source.name, sample_fps=3, minimum_loop_seconds=0.8, maximum_loop_seconds=1.8)
    candidate = analysis["candidates"][0]
    provider_result = {
        "decision": "approve", "candidate_id": candidate["id"],
        "issues": [], "rejection_reason": None,
    }

    validated = animation_review.validate_review_result(analysis, json.dumps(provider_result))

    assert validated["status"] == "approved"
    assert validated["source_sha256"] == analysis["source"]["sha256"]
    assert validated["selected_candidate"] == candidate
    assert validated["self_reported_confidence"] is None


def test_semantic_reviewer_rejection_of_visual_turn_is_final(tmp_path: Path) -> None:
    source = _make_video(tmp_path, [20, 28, 36, 28, 20, 28, 36, 28, 20, 28, 36, 28])
    analysis = animation_review.analyze_candidates(
        tmp_path, source.name, sample_fps=3, minimum_loop_seconds=0.8, maximum_loop_seconds=1.8,
    )

    validated = animation_review.validate_review_result(analysis, {
        "decision": "reject",
        "candidate_id": None,
        "issues": [{"type": "direction", "severity": "hard_failure", "detail": "Visible turn away from the requested facing."}],
        "rejection_reason": "The source visibly rotates during every candidate interval.",
    })

    assert validated["status"] == "rejected"
    assert validated["approved"] is False
    assert validated["provider_decision"] == "reject"


def test_provider_cannot_approve_a_candidate_while_reporting_hard_failure(tmp_path: Path) -> None:
    source = _make_video(tmp_path, [20, 28, 36, 28, 20, 28, 36, 28, 20, 28, 36, 28])
    analysis = animation_review.analyze_candidates(
        tmp_path, source.name, sample_fps=3, minimum_loop_seconds=0.8, maximum_loop_seconds=1.8,
    )
    candidate = analysis["candidates"][0]

    with pytest.raises(animation_review.ReviewValidationError, match="hard failure"):
        animation_review.validate_review_result(analysis, {
            "decision": "approve",
            "candidate_id": candidate["id"],
            "issues": [{"type": "direction", "severity": "hard_failure", "detail": "Visible turn."}],
            "rejection_reason": None,
        })


def test_unit_minimal_review_output_uses_server_owned_provenance(tmp_path: Path) -> None:
    source = _make_video(tmp_path, [20, 28, 36, 28, 20, 28, 36, 28, 20, 28, 36, 28])
    analysis = animation_review.analyze_candidates(
        tmp_path, source.name, sample_fps=3, minimum_loop_seconds=0.8, maximum_loop_seconds=1.8,
    )
    candidate = analysis["candidates"][0]

    validated = animation_review.validate_review_result(analysis, {
        "decision": "approve",
        "candidate_id": candidate["id"],
        "issues": [],
        "rejection_reason": None,
    })

    assert validated["status"] == "approved"
    assert validated["source_sha256"] == analysis["source"]["sha256"]
    assert validated["selected_candidate"] == candidate
    assert validated["self_reported_confidence"] is None


def test_unit_schema_diagnostic_reports_precise_keys_and_type_paths(tmp_path: Path) -> None:
    source = _make_video(tmp_path, [20, 28, 36, 28, 20, 28, 36, 28, 20, 28, 36, 28])
    analysis = animation_review.analyze_candidates(tmp_path, source.name, sample_fps=3)

    with pytest.raises(animation_review.ReviewValidationError) as captured:
        animation_review.validate_review_result(analysis, {
            "decision": "approve",
            "candidate_id": 7,
            "issues": "none",
            "unexpected": True,
        })

    assert captured.value.code == "schema_keys_or_types"
    assert captured.value.details == {
        "expected_keys": ["candidate_id", "decision", "issues", "rejection_reason"],
        "missing_keys": ["rejection_reason"],
        "extra_keys": ["unexpected"],
        "type_errors": [
            {"path": "$.candidate_id", "expected": "string|null", "actual": "integer"},
            {"path": "$.issues", "expected": "array", "actual": "string"},
        ],
    }


def test_unit_failed_validation_retains_bounded_private_message_content(tmp_path: Path) -> None:
    _make_video(tmp_path, [20, 28, 36, 28, 20, 28, 36, 28, 20, 28, 36, 28])
    analysis = animation_review.analyze_candidates(tmp_path, "source.mp4", sample_fps=3)
    raw_content = json.dumps({"unexpected": True})
    envelope = {
        "id": "gen-invalid-output",
        "provider": "Google AI Studio",
        "choices": [{"finish_reason": "stop", "message": {"content": raw_content}}],
        "usage": {"prompt_tokens": 321, "completion_tokens": 7, "total_tokens": 328, "cost": 0.000267},
    }

    result = _submit_mocked_review(
        tmp_path, analysis, _RawPaidTransport(body=json.dumps(envelope).encode()),
    )

    retained = tmp_path / "automatic-review-raw-message.txt"
    assert retained.read_text(encoding="utf-8") == raw_content
    assert retained.stat().st_mode & 0o777 == 0o600
    assert result["raw_message"] == {
        "artifact": retained.name,
        "bytes": len(raw_content.encode()),
        "sha256": hashlib.sha256(raw_content.encode()).hexdigest(),
        "truncated": False,
    }
    assert result["diagnostic"]["type"] == "schema_keys_or_types"
    assert result["diagnostic"]["validation"]["extra_keys"] == ["unexpected"]


def test_validate_review_result_rejects_bad_candidate_or_provenance(tmp_path: Path) -> None:
    source = _make_video(tmp_path, [20, 28, 36, 28, 20, 28, 36, 28, 20, 28, 36, 28])
    analysis = animation_review.analyze_candidates(tmp_path, source.name, sample_fps=3)
    invalid = {
        "schema_version": 1,
        "model": animation_review.DEFAULT_MODEL,
        "source_sha256": "f" * 64,
        "decision": "approve",
        "candidate_id": "candidate-99",
        "start_source_frame_index": 0,
        "end_source_frame_index": 1,
        "start_timestamp_seconds": 0.0,
        "end_timestamp_seconds": 0.1,
        "issues": [],
        "rejection_reason": None,
        "confidence": 0.5,
    }

    with pytest.raises(animation_review.ReviewValidationError):
        animation_review.validate_review_result(analysis, invalid)


def test_local_hard_failure_cannot_be_overridden_by_provider_approval(tmp_path: Path) -> None:
    source = _make_video(tmp_path, [30] * 12)
    analysis = animation_review.analyze_candidates(tmp_path, source.name, sample_fps=3)
    provider_result = {
        "decision": "approve", "candidate_id": None,
        "issues": [], "rejection_reason": None,
    }

    validated = animation_review.validate_review_result(analysis, provider_result)

    assert validated["status"] == "rejected"
    assert validated["provider_decision"] == "approve"
    assert validated["local_hard_failures"] == ["static_source"]


class _MockPaidTransport:
    def __init__(self, response: object) -> None:
        self.response = response
        self.calls: list[tuple[str, str, dict[str, str], bytes, int]] = []

    def request(self, method: str, url: str, headers: dict[str, str], body: bytes, timeout: int) -> tuple[int, dict[str, str], bytes]:
        self.calls.append((method, url, headers, body, timeout))
        return 200, {"content-type": "application/json"}, json.dumps(self.response).encode()


class _RawPaidTransport:
    def __init__(
        self,
        status: int = 200,
        headers: dict[str, str] | None = None,
        body: bytes = b"",
        error: Exception | None = None,
    ) -> None:
        self.status = status
        self.headers = headers or {}
        self.body = body
        self.error = error
        self.calls = 0

    def request(self, method: str, url: str, headers: dict[str, str], body: bytes, timeout: int) -> tuple[int, dict[str, str], bytes]:
        self.calls += 1
        if self.error is not None:
            raise self.error
        return self.status, self.headers, self.body


def _review_metadata() -> dict:
    return {
        "id": animation_review.DEFAULT_MODEL,
        "architecture": {"input_modalities": ["text", "image", "video"]},
        "supported_parameters": ["response_format", "max_tokens"],
        "pricing": {"prompt": "0.00000075", "completion": "0.00000375"},
        "context_length": 100_000,
    }


def test_exact_model_metadata_loader_unwraps_live_api_shape_and_requires_context() -> None:
    exact = {
        "id": animation_review.DEFAULT_MODEL,
        "canonical_slug": "google/gemini-3.8-flash-20260902",
        "context_length": 1_048_576,
        "architecture": {"input_modalities": ["text", "image", "video", "file", "audio"]},
        "supported_parameters": ["max_tokens", "response_format", "structured_outputs"],
        "pricing": {"prompt": "0.00000075", "completion": "0.00000375", "image": "0.00000075"},
    }

    loaded = animation_review.load_openrouter_model_metadata({"data": [{"id": "other/model"}, exact]})

    assert loaded["id"] == animation_review.DEFAULT_MODEL
    assert loaded["context_length"] == 1_048_576
    assert loaded["pricing"]["prompt"] == "0.00000075"
    assert loaded["source"] == "https://openrouter.ai/api/v1/models"
    assert loaded["response_shape"] == "openrouter_models_api_envelope"
    with pytest.raises(ValueError, match="context length"):
        animation_review.load_openrouter_model_metadata(
            {"data": [{key: value for key, value in exact.items() if key != "context_length"}]}
        )
    with pytest.raises(ValueError, match="absent or ambiguous"):
        animation_review.load_openrouter_model_metadata({"data": [exact, exact]})


def _submit_mocked_review(tmp_path: Path, analysis: dict, transport: object) -> dict:
    return animation_review.submit_review(
        tmp_path,
        "source.mp4",
        analysis,
        paid_enabled=True,
        api_key="test-key-not-real",
        budget_cap_usd=0.2,
        max_input_tokens=50_000,
        max_tokens=100,
        capability_metadata=_review_metadata(),
        transport=transport,
    )


def test_paid_review_records_sanitized_definite_http_rejection(tmp_path: Path) -> None:
    _make_video(tmp_path, [20, 28, 36, 28, 20, 28, 36, 28, 20, 28, 36, 28])
    analysis = animation_review.analyze_candidates(tmp_path, "source.mp4", sample_fps=3)
    transport = _RawPaidTransport(
        status=400,
        headers={"X-Request-ID": "req-http-400", "Authorization": "must-not-leak"},
        body=json.dumps({"error": {"code": "invalid_request", "message": "secret signed URL https://example.test/token"}}).encode(),
    )

    result = _submit_mocked_review(tmp_path, analysis, transport)

    assert result["status"] == "needs_attention"
    assert result["diagnostic"] == {
        "phase": "http_response",
        "type": "http_rejection",
        "http_status": 400,
        "error_code": "invalid_request",
        "request_id": "req-http-400",
        "response_id": None,
        "finish_reason": None,
        "usage": None,
        "cost_usd": None,
        "submission_state": "definite_rejection",
    }
    assert "secret" not in json.dumps(result)


def test_paid_review_records_timeout_as_ambiguous_submission(tmp_path: Path) -> None:
    _make_video(tmp_path, [20, 28, 36, 28, 20, 28, 36, 28, 20, 28, 36, 28])
    analysis = animation_review.analyze_candidates(tmp_path, "source.mp4", sample_fps=3)
    transport = _RawPaidTransport(error=TimeoutError("signed URL and secret must not leak"))

    result = _submit_mocked_review(tmp_path, analysis, transport)

    assert result["status"] == "needs_attention"
    assert result["diagnostic"] == {
        "phase": "transport",
        "type": "timeout_ambiguous",
        "http_status": None,
        "error_code": None,
        "request_id": None,
        "response_id": None,
        "finish_reason": None,
        "usage": None,
        "cost_usd": None,
        "submission_state": "ambiguous",
    }
    assert "signed URL" not in json.dumps(result)


def test_paid_review_records_connection_failure_as_ambiguous_transport(tmp_path: Path) -> None:
    _make_video(tmp_path, [20, 28, 36, 28, 20, 28, 36, 28, 20, 28, 36, 28])
    analysis = animation_review.analyze_candidates(tmp_path, "source.mp4", sample_fps=3)
    transport = _RawPaidTransport(error=ConnectionError("credential must not leak"))

    result = _submit_mocked_review(tmp_path, analysis, transport)

    assert result["diagnostic"]["phase"] == "transport"
    assert result["diagnostic"]["type"] == "connection_error_ambiguous"
    assert result["diagnostic"]["submission_state"] == "ambiguous"
    assert "credential" not in json.dumps(result)


def test_paid_review_records_truncated_provider_envelope(tmp_path: Path) -> None:
    _make_video(tmp_path, [20, 28, 36, 28, 20, 28, 36, 28, 20, 28, 36, 28])
    analysis = animation_review.analyze_candidates(tmp_path, "source.mp4", sample_fps=3)
    transport = _RawPaidTransport(
        headers={"x-request-id": "req-truncated"},
        body=b'{"id":"gen-partial","usage":{"cost":0.012',
    )

    result = _submit_mocked_review(tmp_path, analysis, transport)

    assert result["status"] == "needs_attention"
    assert result["diagnostic"]["phase"] == "response_envelope"
    assert result["diagnostic"]["type"] == "malformed_json"
    assert result["diagnostic"]["http_status"] == 200
    assert result["diagnostic"]["request_id"] == "req-truncated"
    assert result["diagnostic"]["response_id"] is None
    assert result["diagnostic"]["usage"] is None
    assert result["diagnostic"]["cost_usd"] is None
    assert result["diagnostic"]["submission_state"] == "response_received"


def test_paid_review_preserves_receipt_when_output_validation_fails(tmp_path: Path) -> None:
    _make_video(tmp_path, [20, 28, 36, 28, 20, 28, 36, 28, 20, 28, 36, 28])
    analysis = animation_review.analyze_candidates(tmp_path, "source.mp4", sample_fps=3)
    envelope = {
        "id": "gen-invalid-output",
        "provider": "Google AI Studio",
        "choices": [{"finish_reason": "stop", "message": {"content": json.dumps({"unexpected": True})}}],
        "usage": {"prompt_tokens": 321, "completion_tokens": 7, "total_tokens": 328, "cost": 0.000267},
    }
    transport = _RawPaidTransport(
        headers={"X-Request-Id": "req-invalid-output", "Set-Cookie": "must-not-leak"},
        body=json.dumps(envelope).encode(),
    )

    result = _submit_mocked_review(tmp_path, analysis, transport)

    assert result["status"] == "needs_attention"
    assert result["response_id"] == "gen-invalid-output"
    assert result["provider"] == "Google AI Studio"
    assert result["usage"] == {"prompt_tokens": 321, "completion_tokens": 7, "total_tokens": 328}
    assert result["budget"]["actual_cost_usd"] == pytest.approx(0.000267)
    assert result["budget"]["actual_cost_known"] is True
    assert result["diagnostic"] == {
        "phase": "output_validation",
        "type": "schema_keys_or_types",
        "http_status": 200,
        "error_code": None,
        "request_id": "req-invalid-output",
        "response_id": "gen-invalid-output",
        "finish_reason": "stop",
        "usage": {"prompt_tokens": 321, "completion_tokens": 7, "total_tokens": 328},
        "cost_usd": 0.000267,
        "submission_state": "response_received",
        "validation": {
            "expected_keys": ["candidate_id", "decision", "issues", "rejection_reason"],
            "missing_keys": ["candidate_id", "decision", "issues", "rejection_reason"],
            "extra_keys": ["unexpected"],
            "type_errors": [],
        },
    }
    assert "must-not-leak" not in json.dumps(result)


def test_paid_review_marks_missing_usage_without_discarding_valid_decision(tmp_path: Path) -> None:
    _make_video(tmp_path, [20, 28, 36, 28, 20, 28, 36, 28, 20, 28, 36, 28])
    analysis = animation_review.analyze_candidates(tmp_path, "source.mp4", sample_fps=3)
    candidate = analysis["candidates"][0]
    content = {
        "decision": "approve", "candidate_id": candidate["id"],
        "issues": [], "rejection_reason": None,
    }
    envelope = {
        "id": "gen-no-usage",
        "provider": "Google AI Studio",
        "choices": [{"finish_reason": "stop", "message": {"content": json.dumps(content)}}],
    }
    transport = _RawPaidTransport(headers={"x-request-id": "req-no-usage"}, body=json.dumps(envelope).encode())

    result = _submit_mocked_review(tmp_path, analysis, transport)

    assert result["status"] == "approved"
    assert result["usage"] is None
    assert result["budget"]["actual_cost_known"] is False
    assert result["diagnostic"] == {
        "phase": "accounting",
        "type": "missing_usage",
        "http_status": 200,
        "error_code": None,
        "request_id": "req-no-usage",
        "response_id": "gen-no-usage",
        "finish_reason": "stop",
        "usage": None,
        "cost_usd": None,
        "submission_state": "response_received",
    }


def test_paid_review_distinguishes_request_build_failure_before_send(tmp_path: Path, monkeypatch) -> None:
    _make_video(tmp_path, [20, 28, 36, 28, 20, 28, 36, 28, 20, 28, 36, 28])
    analysis = animation_review.analyze_candidates(tmp_path, "source.mp4", sample_fps=3)
    transport = _RawPaidTransport()

    def fail_before_send(*args, **kwargs):
        raise ValueError("base64 and signed URL must not leak")

    monkeypatch.setattr(animation_review, "build_review_request", fail_before_send)
    result = _submit_mocked_review(tmp_path, analysis, transport)

    assert transport.calls == 0
    assert result["diagnostic"] == {
        "phase": "request_construction",
        "type": "no_send_failure",
        "http_status": None,
        "error_code": None,
        "request_id": None,
        "response_id": None,
        "finish_reason": None,
        "usage": None,
        "cost_usd": None,
        "submission_state": "not_sent",
    }
    assert "signed URL" not in json.dumps(result)


def test_mocked_paid_transport_fails_closed_when_disabled_or_key_missing(tmp_path: Path) -> None:
    source = _make_video(tmp_path, [20, 28, 36, 28, 20, 28, 36, 28, 20, 28, 36, 28])
    analysis = animation_review.analyze_candidates(tmp_path, source.name, sample_fps=3)
    transport = _MockPaidTransport({})

    disabled = animation_review.submit_review(tmp_path, source.name, analysis, transport=transport)
    missing_key = animation_review.submit_review(tmp_path, source.name, analysis, paid_enabled=True, transport=transport)

    assert disabled["status"] == "needs_attention"
    assert missing_key["status"] == "needs_attention"
    assert transport.calls == []


def test_paid_review_rejects_declared_input_bound_below_constructed_evidence(tmp_path: Path) -> None:
    source = _make_video(tmp_path, [20, 28, 36, 28, 20, 28, 36, 28, 20, 28, 36, 28])
    analysis = animation_review.analyze_candidates(tmp_path, source.name, sample_fps=3)
    transport = _RawPaidTransport()

    result = animation_review.submit_review(
        tmp_path, source.name, analysis, paid_enabled=True, api_key="test-key-not-real",
        budget_cap_usd=0.2, max_input_tokens=100, max_tokens=100,
        capability_metadata=_review_metadata(), transport=transport,
    )

    assert transport.calls == 0
    assert result["status"] == "needs_attention"
    assert "constructed evidence" in result["reason"]


def test_mocked_paid_transport_validates_response_and_never_falls_back(tmp_path: Path) -> None:
    source = _make_video(tmp_path, [20, 28, 36, 28, 20, 28, 36, 28, 20, 28, 36, 28])
    analysis = animation_review.analyze_candidates(tmp_path, source.name, sample_fps=3, minimum_loop_seconds=0.8, maximum_loop_seconds=1.8)
    candidate = analysis["candidates"][0]
    content = {
        "decision": "approve", "candidate_id": candidate["id"],
        "issues": [], "rejection_reason": None,
    }
    transport = _MockPaidTransport({"choices": [{"message": {"content": json.dumps(content)}}]})
    metadata = {
        "id": animation_review.DEFAULT_MODEL,
        "architecture": {"input_modalities": ["text", "image", "video", "file", "audio"]},
        "supported_parameters": ["response_format", "structured_outputs", "max_tokens"],
        "pricing": {"prompt": "0.00000075", "completion": "0.00000375"},
        "context_length": 100_000,
    }

    result = animation_review.submit_review(
        tmp_path,
        source.name,
        analysis,
        paid_enabled=True,
        api_key="test-key-not-real",
        budget_cap_usd=0.2,
        max_input_tokens=50_000,
        max_tokens=100,
        capability_metadata=metadata,
        transport=transport,
    )

    assert result["status"] == "approved"
    assert len(transport.calls) == 1
    sent = json.loads(transport.calls[0][3])
    assert sent["model"] == animation_review.DEFAULT_MODEL
    assert sent["provider"]["allow_fallbacks"] is False


def test_mocked_paid_transport_invalid_json_is_needs_attention(tmp_path: Path) -> None:
    source = _make_video(tmp_path, [20, 28, 36, 28, 20, 28, 36, 28, 20, 28, 36, 28])
    analysis = animation_review.analyze_candidates(tmp_path, source.name, sample_fps=3)
    # Sanitized shape of the retained malformed provider response from the cold run.
    malformed = '{\n  "candidate_id": "candidate-01",\n  "decision": "approve",\n  '
    transport = _MockPaidTransport({"choices": [{"message": {"content": malformed}}]})
    metadata = {
        "id": animation_review.DEFAULT_MODEL,
        "architecture": {"input_modalities": ["text", "image", "video", "file", "audio"]},
        "supported_parameters": ["response_format", "structured_outputs", "max_tokens"],
        "pricing": {"prompt": "0.00000075", "completion": "0.00000375"},
        "context_length": 100_000,
    }

    result = animation_review.submit_review(
        tmp_path,
        source.name,
        analysis,
        paid_enabled=True,
        api_key="test-key-not-real",
        budget_cap_usd=0.2,
        max_input_tokens=50_000,
        max_tokens=100,
        capability_metadata=metadata,
        transport=transport,
    )

    assert result["status"] == "needs_attention"
    assert result["approved"] is False
    assert result["diagnostic"]["type"] == "invalid_json"


def test_mocked_paid_transport_records_returned_usage_and_actual_cost(tmp_path: Path) -> None:
    source = _make_video(tmp_path, [20, 28, 36, 28, 20, 28, 36, 28, 20, 28, 36, 28])
    analysis = animation_review.analyze_candidates(tmp_path, source.name, sample_fps=3, minimum_loop_seconds=0.8, maximum_loop_seconds=1.8)
    candidate = analysis["candidates"][0]
    content = {
        "decision": "approve", "candidate_id": candidate["id"],
        "issues": [], "rejection_reason": None,
    }
    transport = _MockPaidTransport({
        "choices": [{"message": {"content": json.dumps(content)}}],
        "usage": {"prompt_tokens": 321, "completion_tokens": 45, "total_tokens": 366, "cost": 0.0004095},
    })
    metadata = {
        "id": animation_review.DEFAULT_MODEL,
        "architecture": {"input_modalities": ["text", "image", "video"]},
        "supported_parameters": ["response_format", "max_tokens"],
        "pricing": {"prompt": "0.00000075", "completion": "0.00000375"},
        "context_length": 100_000,
    }

    result = animation_review.submit_review(
        tmp_path, source.name, analysis, paid_enabled=True, api_key="test-key-not-real",
        budget_cap_usd=0.2, max_input_tokens=50_000, max_tokens=100,
        capability_metadata=metadata, transport=transport,
    )

    assert result["usage"] == {"prompt_tokens": 321, "completion_tokens": 45, "total_tokens": 366}
    assert result["budget"]["actual_cost_usd"] == pytest.approx(0.0004095)
    assert result["budget"]["actual_cost_known"] is True
    assert result["budget"]["maximum_token_price_estimate_is_quote"] is True


def test_paid_review_reserves_full_context_and_caps_provider_prices(tmp_path: Path) -> None:
    source = _make_video(tmp_path, [20, 28, 36, 28, 20, 28, 36, 28, 20, 28, 36, 28])
    analysis = animation_review.analyze_candidates(tmp_path, source.name, sample_fps=3, minimum_loop_seconds=0.8, maximum_loop_seconds=1.8)
    candidate = analysis["candidates"][0]
    content = {
        "decision": "approve", "candidate_id": candidate["id"],
        "issues": [], "rejection_reason": None,
    }
    transport = _MockPaidTransport({
        "id": "gen-test-123", "provider": "Google AI Studio",
        "choices": [{"message": {"content": json.dumps(content)}}],
        "usage": {"prompt_tokens": 321, "completion_tokens": 45, "total_tokens": 366, "cost": 0.0004095},
    })
    metadata = {
        "id": animation_review.DEFAULT_MODEL,
        "context_length": 1_048_576,
        "architecture": {"input_modalities": ["text", "image", "video"]},
        "supported_parameters": ["response_format", "max_tokens"],
        "pricing": {"prompt": "0.00000075", "completion": "0.00000375"},
    }
    max_output = 1200
    max_input = metadata["context_length"] - max_output

    result = animation_review.submit_review(
        tmp_path, source.name, analysis, paid_enabled=True, api_key="test-key-not-real",
        budget_cap_usd=0.80, max_input_tokens=max_input, max_tokens=max_output,
        capability_metadata=metadata, transport=transport,
    )

    sent = json.loads(transport.calls[0][3])
    assert sent["provider"]["max_price"] == {"prompt": 0.75, "completion": 3.75}
    assert result["response_id"] == "gen-test-123"
    assert result["provider"] == "Google AI Studio"
    assert result["budget"]["context_length_tokens"] == 1_048_576
    assert result["budget"]["reserved_worst_case_usd"] == pytest.approx(0.790032)
