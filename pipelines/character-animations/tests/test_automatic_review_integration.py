from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from animation_review import DEFAULT_MODEL
from runner import Runner, frame_policy, sparse_cycle_sampling

ROOT = Path(__file__).parents[1]
REJECTED_VIDEO = ROOT / "artifacts/review-candidates/gemini-rejected-3s/source.mp4"
WAN_VIDEO = ROOT / "artifacts/review-candidates/wan-existing-accepted-window/source.mp4"
AUTH = {"Authorization": "Bearer test-token"}


def test_sparse_cycle_sampling_preserves_selected_duration() -> None:
    sampling = sparse_cycle_sampling(
        {"start_source_frame_index": 28, "end_source_frame_index": 75},
        native_fps=30.0,
        target_frames=10,
    )

    assert len(sampling["indices"]) == 10
    assert sampling["indices"] == sorted(set(sampling["indices"]))
    assert sampling["indices"][0] == 28
    assert sampling["indices"][-1] < 75
    assert sampling["cycle_duration_seconds"] == pytest.approx(47 / 30)
    assert len(sampling["indices"]) / sampling["playback_fps"] == pytest.approx(47 / 30)


@pytest.mark.parametrize("option,count", [("8", 8), ("12", 12), ("16", 16)])
def test_compact_frame_policies_select_distinct_originals_and_preserve_duration(option, count) -> None:
    sampling = sparse_cycle_sampling(
        {"start_source_frame_index": 28, "end_source_frame_index": 75},
        native_fps=30.0,
        frame_policy_name=option,
    )
    assert len(sampling["indices"]) == count
    assert sampling["indices"] == sorted(set(sampling["indices"]))
    assert sampling["selected_frame_count"] / sampling["playback_fps"] == pytest.approx(47 / 30)
    assert sampling["minimum_playback_fps"] is None
    assert sampling["frame_policy"]["option"] == option
    assert sampling["frame_policy"]["sha256"] == frame_policy(option)["sha256"]


def test_default_frame_policy_is_eight_and_native_remains_available() -> None:
    compact = sparse_cycle_sampling({"start_source_frame_index": 0, "end_source_frame_index": 30}, native_fps=30.0)
    native = sparse_cycle_sampling({"start_source_frame_index": 0, "end_source_frame_index": 30}, native_fps=30.0, frame_policy_name="native")
    assert compact["selected_frame_count"] == 8
    assert compact["frame_policy"]["option"] == "8"
    assert native["indices"] == list(range(30))
    assert native["frame_policy"]["revision"] == "native-density-v2"


def test_compact_policy_rejects_too_short_cycle_and_bad_option() -> None:
    with pytest.raises(ValueError, match="fewer than 8 distinct original frames"):
        sparse_cycle_sampling({"start_source_frame_index": 0, "end_source_frame_index": 7}, native_fps=30.0)
    with pytest.raises(ValueError, match="frame policy"):
        sparse_cycle_sampling({"start_source_frame_index": 0, "end_source_frame_index": 30}, native_fps=30.0, frame_policy_name="10")


def test_cycle_sampling_adapts_density_to_native_pose_gap() -> None:
    sampling = sparse_cycle_sampling(
        {
            "start_source_frame_index": 28,
            "end_source_frame_index": 75,
            "sampling_evidence": {"maximum_native_gap": 3},
        },
        native_fps=30.0,
        frame_policy_name="native",
    )

    assert len(sampling["indices"]) == 29
    assert max(right - left for left, right in zip(sampling["indices"], sampling["indices"][1:])) <= 2
    assert sampling["playback_fps"] == pytest.approx(29 / (47 / 30))
    assert sampling["playback_fps"] >= 18
    assert sampling["density_basis"] == "native_or_at_least_18fps_with_pose_gap"


def test_cycle_sampling_prefers_every_native_frame_when_bounded() -> None:
    sampling = sparse_cycle_sampling(
        {
            "start_source_frame_index": 44,
            "end_source_frame_index": 74,
            "sampling_evidence": {"maximum_native_gap": 3},
        },
        native_fps=24.0,
        frame_policy_name="native",
    )

    assert sampling["indices"] == list(range(44, 74))
    assert sampling["selected_frame_count"] == 30
    assert sampling["playback_fps"] == pytest.approx(24.0)
    assert sampling["exact_native_cadence"] is True
    assert sampling["duration_preserved"] is True


def test_punch_sampling_keeps_detected_impact() -> None:
    candidate = {
        "action": "punch", "start_source_frame_index": 0, "end_source_frame_index": 72,
        "impact_source_frame_index": 31, "sampling_evidence": {"maximum_native_gap": 12},
        "phase_proposals": {"anticipation": 8, "maximum_extension": 31, "recovery": 56},
    }
    sampling = sparse_cycle_sampling(candidate, native_fps=24.0, frame_policy_name="8")
    assert len(sampling["indices"]) == 8
    assert 31 in sampling["indices"]
    assert sampling["indices"] == sorted(set(sampling["indices"]))


def test_punch_sampling_preserves_phase_keyposes_and_original_intervals() -> None:
    candidate = {
        "action": "punch", "start_source_frame_index": 10, "end_source_frame_index": 34,
        "phase_proposals": {"anticipation": 13, "maximum_extension": 19, "recovery": 27},
        "impact_source_frame_index": 19, "sampling_evidence": {"maximum_native_gap": 12},
    }
    sampling = sparse_cycle_sampling(candidate, native_fps=24.0, frame_policy_name="8")

    assert {10, 13, 19, 27} <= set(sampling["indices"])
    assert all(value > 0 for value in sampling["frame_durations_seconds"])
    assert sum(sampling["frame_durations_seconds"]) == pytest.approx(1.0)
    assert sampling["interval_end_timestamp_seconds"] == pytest.approx(34 / 24)


def test_punch_sampling_does_not_turn_sparse_anticipation_gap_into_long_static_hold() -> None:
    candidate = {
        "action": "punch", "start_source_frame_index": 14, "end_source_frame_index": 53,
        "phase_proposals": {"anticipation": 16, "maximum_extension": 26, "recovery": 38},
        "impact_source_frame_index": 26, "sampling_evidence": {"maximum_native_gap": 12},
    }

    sampling = sparse_cycle_sampling(candidate, native_fps=24.0, frame_policy_name="8")

    assert {14, 16, 26, 29, 38} <= set(sampling["indices"])
    assert sampling["maximum_native_gap"] <= 8
    assert max(sampling["frame_durations_seconds"]) <= 8 / 24 + 1e-12
    assert sum(sampling["frame_durations_seconds"]) == pytest.approx(39 / 24)


@pytest.mark.parametrize("candidate", [
    {"action": "punch", "start_source_frame_index": 10, "end_source_frame_index": 34,
     "impact_source_frame_index": 19, "phase_proposals": {"anticipation": 9, "maximum_extension": 19, "recovery": 27}},
    {"action": "punch", "start_source_frame_index": 10, "end_source_frame_index": 34,
     "impact_source_frame_index": 19, "phase_proposals": {"anticipation": 13, "maximum_extension": 19}},
])
def test_punch_sampling_fails_closed_on_invalid_or_incomplete_phases(candidate) -> None:
    with pytest.raises(ValueError, match="phase"):
        sparse_cycle_sampling(candidate, native_fps=24.0, frame_policy_name="8")


def test_cycle_sampling_fails_when_removal_bound_cannot_reach_density() -> None:
    with pytest.raises(ValueError, match="density target exceeds bounded frame count"):
        sparse_cycle_sampling(
            {
                "start_source_frame_index": 0,
                "end_source_frame_index": 75,
                "sampling_evidence": {"maximum_native_gap": 3},
            },
            native_fps=30.0,
            frame_policy_name="native",
        )


def _video_job(app, source: Path) -> tuple[str, dict]:
    store = app.state.store
    job = store.create_job("reference.png", {}, b"not-used")
    target = store.job_dir(job["id"]) / "video-output.mp4"
    shutil.copyfile(source, target)
    with store.connect() as connection:
        store.upsert_artifact(connection, job["id"], target.name, "smoke_fixture", target)
    return job["id"], store.get_artifact(job["id"], target.name)


def _request(artifact: dict, *, authorize: bool = False) -> dict:
    return {
        "artifact": artifact["name"],
        "sha256": artifact["sha256"],
        "revision": artifact["revision"],
        "authorize_paid_review": authorize,
        "budget_cap_usd": 0.05 if authorize else None,
        "frame_policy": "8",
    }


def _app(tmp_path: Path, monkeypatch, *, review_module=None):
    monkeypatch.setenv("ANIMATION_API_TOKEN", "test-token")
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("ANIMATION_REVIEW_ENABLED", raising=False)
    from app import create_app

    return create_app(
        db_path=tmp_path / "jobs.sqlite3",
        data_dir=tmp_path / "jobs",
        review_module=review_module,
        start_worker=False,
    )


def test_capabilities_truthfully_describe_local_and_blocked_reviewer(tmp_path, monkeypatch):
    app = _app(tmp_path, monkeypatch)
    with TestClient(app) as client:
        body = client.get("/v1/capabilities", headers=AUTH).json()

    assert body["automatic_review"]["model"] == DEFAULT_MODEL
    assert body["automatic_review"]["input_modalities"] == ["video", "image"]
    assert body["automatic_review"]["local_analysis"] == {"available": True, "paid": False}
    assert body["automatic_review"]["reviewer"]["available"] is False
    assert "disabled" in body["automatic_review"]["reviewer"]["blocked_reason"]
    assert body["stages"]["automatic_review"]["capability"] == "animation_review"


def test_reviewer_capability_rejects_stale_model_metadata(tmp_path, monkeypatch):
    metadata = tmp_path / "stale-model.json"
    metadata.write_text(json.dumps({
        "id": DEFAULT_MODEL,
        "source": "https://openrouter.ai/api/v1/models",
        "fetched_at_utc": "2000-01-01T00:00:00Z",
    }))
    app = _app(tmp_path, monkeypatch)
    monkeypatch.setenv("ANIMATION_REVIEW_ENABLED", "1")
    monkeypatch.setenv("OPENROUTER_API_KEY", "unit-test-not-real")
    monkeypatch.setenv("ANIMATION_REVIEW_MAX_USD", "0.05")
    monkeypatch.setenv("ANIMATION_REVIEW_MAX_INPUT_TOKENS", "1000")
    monkeypatch.setenv("ANIMATION_REVIEW_MAX_OUTPUT_TOKENS", "1200")
    monkeypatch.setenv("ANIMATION_REVIEW_MODEL_METADATA_FILE", str(metadata))

    with TestClient(app) as client:
        reviewer = client.get("/v1/capabilities", headers=AUTH).json()["automatic_review"]["reviewer"]

    assert reviewer["available"] is False
    assert "fresh" in reviewer["blocked_reason"]


def test_automatic_review_endpoint_is_authenticated_and_revision_bound(tmp_path, monkeypatch):
    app = _app(tmp_path, monkeypatch)
    job_id, artifact = _video_job(app, WAN_VIDEO)
    with TestClient(app) as client:
        assert client.post(f"/v1/jobs/{job_id}/automatic-review", json=_request(artifact)).status_code == 401
        stale = dict(_request(artifact))
        stale["revision"] += 1
        response = client.post(f"/v1/jobs/{job_id}/automatic-review", headers=AUTH, json=stale)
        assert response.status_code == 409
        queued = client.post(f"/v1/jobs/{job_id}/automatic-review", headers=AUTH, json=_request(artifact))
        assert queued.status_code == 202
        assert queued.json()["stage"] == "automatic_review"
        assert queued.json()["params"]["source_sha256"] == artifact["sha256"]
    assert queued.json()["params"]["frame_policy"] == "8"


def test_automatic_review_endpoint_validates_and_persists_frame_policy(tmp_path, monkeypatch):
    app = _app(tmp_path, monkeypatch)
    job_id, artifact = _video_job(app, WAN_VIDEO)
    with TestClient(app) as client:
        bad = client.post(f"/v1/jobs/{job_id}/automatic-review", headers=AUTH, json={**_request(artifact), "frame_policy": "10"})
        assert bad.status_code == 422
        queued = client.post(f"/v1/jobs/{job_id}/automatic-review", headers=AUTH, json={**_request(artifact), "frame_policy": "16"})
    assert queued.status_code == 202
    assert queued.json()["params"]["frame_policy"] == "16"


def test_server_prepared_analysis_is_reused_once_with_identical_candidates(tmp_path, monkeypatch):
    calls = []

    class CountingReview:
        @staticmethod
        def analyze_candidates(workdir, input_name, **kwargs):
            calls.append((input_name, kwargs))
            source = Path(workdir) / input_name
            return {
                "source": {"file": input_name, "sha256": hashlib.sha256(source.read_bytes()).hexdigest(), "native_fps": 30.0},
                "status": "requires_semantic_review", "hard_failures": [],
                "candidates": [{"id": "candidate-01", "start_source_frame_index": 2, "end_source_frame_index": 8}],
                "samples": [{"sample_index": 0, "source_frame_index": 0}],
            }

    app = _app(tmp_path, monkeypatch, review_module=CountingReview)
    job_id, artifact = _video_job(app, WAN_VIDEO)
    prepared = app.state.runner.prepare_automatic_review_analysis(job_id, artifact["name"])
    before = prepared["analysis"]
    with TestClient(app) as client:
        client.post(f"/v1/jobs/{job_id}/automatic-review", headers=AUTH, json=_request(artifact)).raise_for_status()
        app.state.runner.process_once()
    after = json.loads((app.state.store.job_dir(job_id) / "automatic-review-analysis.json").read_text())

    assert len(calls) == 1
    assert after["candidates"] == before["candidates"]
    assert after["samples"] == before["samples"]
    assert after["source"] == before["source"]


def test_prepared_analysis_is_not_reused_for_different_frame_policy(tmp_path, monkeypatch):
    class CountingReview:
        calls = 0

        @classmethod
        def analyze_candidates(cls, workdir, input_name, **kwargs):
            cls.calls += 1
            source = Path(workdir) / input_name
            return {"source": {"file": input_name, "sha256": hashlib.sha256(source.read_bytes()).hexdigest(), "native_fps": 30.0}, "hard_failures": [], "candidates": []}

    app = _app(tmp_path, monkeypatch, review_module=CountingReview)
    job_id, artifact = _video_job(app, WAN_VIDEO)
    app.state.runner.prepare_automatic_review_analysis(job_id, artifact["name"], "8")
    with TestClient(app) as client:
        client.post(f"/v1/jobs/{job_id}/automatic-review", headers=AUTH, json={**_request(artifact), "frame_policy": "12"}).raise_for_status()
        app.state.runner.process_once()
    assert CountingReview.calls == 2


@pytest.mark.parametrize("changed", ["source", "revision", "recipe"])
def test_stale_prepared_analysis_is_not_reused(tmp_path, monkeypatch, changed):
    class CountingReview:
        calls = 0

        @classmethod
        def analyze_candidates(cls, workdir, input_name, **kwargs):
            cls.calls += 1
            source = Path(workdir) / input_name
            return {"source": {"file": input_name, "sha256": hashlib.sha256(source.read_bytes()).hexdigest(), "native_fps": 30.0}, "hard_failures": [], "candidates": []}

    app = _app(tmp_path, monkeypatch, review_module=CountingReview)
    job_id, artifact = _video_job(app, WAN_VIDEO)
    app.state.runner.prepare_automatic_review_analysis(job_id, artifact["name"])
    if changed in {"source", "revision"}:
        path = app.state.store.job_dir(job_id) / artifact["name"]
        if changed == "source":
            path.write_bytes(path.read_bytes() + b"changed")
        with app.state.store.connect() as connection:
            app.state.store.upsert_artifact(connection, job_id, artifact["name"], "replacement", path)
        artifact = app.state.store.get_artifact(job_id, artifact["name"])
    else:
        monkeypatch.setattr("runner.ANALYSIS_RECIPE_REVISION", "changed-recipe")
    with TestClient(app) as client:
        client.post(f"/v1/jobs/{job_id}/automatic-review", headers=AUTH, json=_request(artifact)).raise_for_status()
        app.state.runner.process_once()

    assert CountingReview.calls == 2


def test_corrupt_or_unregistered_analysis_cache_is_never_trusted(tmp_path, monkeypatch):
    class CountingReview:
        calls = 0

        @classmethod
        def analyze_candidates(cls, workdir, input_name, **kwargs):
            cls.calls += 1
            source = Path(workdir) / input_name
            return {"source": {"file": input_name, "sha256": hashlib.sha256(source.read_bytes()).hexdigest(), "native_fps": 30.0}, "hard_failures": [], "candidates": []}

    app = _app(tmp_path, monkeypatch, review_module=CountingReview)
    job_id, artifact = _video_job(app, WAN_VIDEO)
    cache = app.state.store.job_dir(job_id) / "automatic-review-analysis-cache.json"
    cache.write_text(json.dumps({"analysis": {"candidates": [{"id": "client-crafted"}]}}))
    with TestClient(app) as client:
        client.post(f"/v1/jobs/{job_id}/automatic-review", headers=AUTH, json=_request(artifact)).raise_for_status()
        app.state.runner.process_once()
    assert CountingReview.calls == 1

    app.state.runner.prepare_automatic_review_analysis(job_id, artifact["name"])
    cache.write_text("corrupt")
    with TestClient(app) as client:
        client.post(f"/v1/jobs/{job_id}/automatic-review", headers=AUTH, json=_request(artifact)).raise_for_status()
        app.state.runner.process_once()
        job = client.get(f"/v1/jobs/{job_id}", headers=AUTH).json()
    assert CountingReview.calls == 2
    assert job["state"] == "failed"
    assert "cache" in job["message"]


def test_real_local_hard_reject_records_no_provider_submission(tmp_path, monkeypatch):
    class GuardReview:
        analyze_candidates = staticmethod(__import__("animation_review").analyze_candidates)

        @staticmethod
        def submit_review(*args, **kwargs):
            raise AssertionError("hard-rejected source must not reach paid reviewer")

    app = _app(tmp_path, monkeypatch, review_module=GuardReview)
    job_id, artifact = _video_job(app, REJECTED_VIDEO)
    with TestClient(app) as client:
        queued = client.post(f"/v1/jobs/{job_id}/automatic-review", headers=AUTH, json=_request(artifact, authorize=True))
        assert queued.status_code == 202
        assert app.state.runner.process_once() is True
        job = client.get(f"/v1/jobs/{job_id}", headers=AUTH).json()

    assert job["state"] == "needs_attention"
    review = job["automatic_reviews"][0]
    assert review["status"] == "rejected"
    assert "foreground_touches_frame_edge" in review["local_hard_failures"]
    assert review["paid_transport_called"] is False
    assert review["source_sha256"] == artifact["sha256"]
    assert {"automatic-review-analysis.json", "automatic-review-result.json"} <= {item["name"] for item in job["artifacts"]}


def test_real_rotating_source_requires_semantic_reviewer_instead_of_color_hard_reject(tmp_path, monkeypatch):
    app = _app(tmp_path, monkeypatch)
    job_id, artifact = _video_job(app, WAN_VIDEO)
    with TestClient(app) as client:
        client.post(f"/v1/jobs/{job_id}/automatic-review", headers=AUTH, json=_request(artifact),).raise_for_status()
        app.state.runner.process_once()
        job = client.get(f"/v1/jobs/{job_id}", headers=AUTH).json()
        analysis_response = client.get(f"/v1/jobs/{job_id}/artifacts/automatic-review-analysis.json", headers=AUTH)

    assert job["state"] == "needs_attention"
    review = job["automatic_reviews"][0]
    assert review["status"] == "needs_attention"
    assert review["candidate_count"] > 0
    assert review["paid_transport_called"] is False
    assert review["local_hard_failures"] == []
    assert "disabled" in review["reason"]
    assert analysis_response.status_code == 200
    assert analysis_response.json()["source"]["sha256"] == artifact["sha256"]
    assert analysis_response.json()["status"] == "requires_semantic_review"


def test_mocked_unbound_approval_cannot_create_automatic_approval(tmp_path, monkeypatch):
    class ClearlyNamedTamperedMockReview:
        @staticmethod
        def analyze_candidates(workdir, input_name, **kwargs):
            source = Path(workdir) / input_name
            return {
                "source": {"file": input_name, "sha256": hashlib.sha256(source.read_bytes()).hexdigest(), "native_fps": 30.0},
                "hard_failures": [],
                "candidates": [{"id": "candidate-01", "start_source_frame_index": 1, "end_source_frame_index": 3}],
            }

        @staticmethod
        def submit_review(workdir, input_name, analysis, **kwargs):
            return {
                "status": "approved", "approved": True, "provider_decision": "approve",
                "model": DEFAULT_MODEL, "source_sha256": analysis["source"]["sha256"],
                "selected_candidate": {"id": "forged", "start_source_frame_index": 4, "end_source_frame_index": 6},
            }

    app = _app(tmp_path, monkeypatch, review_module=ClearlyNamedTamperedMockReview)
    monkeypatch.setenv("ANIMATION_REVIEW_ENABLED", "1")
    monkeypatch.setenv("OPENROUTER_API_KEY", "unit-test-not-real")
    monkeypatch.setenv("ANIMATION_REVIEW_MAX_USD", "0.05")
    monkeypatch.setenv("ANIMATION_REVIEW_MAX_INPUT_TOKENS", "1000")
    monkeypatch.setenv("ANIMATION_REVIEW_MAX_OUTPUT_TOKENS", "1200")
    monkeypatch.setenv("ANIMATION_REVIEW_MODEL_METADATA_FILE", str(ROOT / "artifacts/review-candidates/openrouter-model-metadata.json"))
    job_id, artifact = _video_job(app, WAN_VIDEO)
    with TestClient(app) as client:
        client.post(f"/v1/jobs/{job_id}/automatic-review", headers=AUTH, json=_request(artifact, authorize=True)).raise_for_status()
        app.state.runner.process_once()
        job = client.get(f"/v1/jobs/{job_id}", headers=AUTH).json()

    assert job["automatic_reviews"][0]["status"] == "needs_attention"
    assert app.state.store.has_approval(job_id, "video-output.mp4") is False


def test_review_receipt_and_diagnostic_survive_runner_and_store(tmp_path, monkeypatch):
    class ClearlyNamedMockInvalidReview:
        @staticmethod
        def analyze_candidates(workdir, input_name, **kwargs):
            source = Path(workdir) / input_name
            return {
                "source": {"file": input_name, "sha256": hashlib.sha256(source.read_bytes()).hexdigest(), "native_fps": 30.0},
                "hard_failures": [],
                "candidates": [{"id": "candidate-01", "start_source_frame_index": 1, "end_source_frame_index": 3}],
            }

        @staticmethod
        def submit_review(workdir, input_name, analysis, **kwargs):
            return {
                "status": "needs_attention", "approved": False, "model": DEFAULT_MODEL,
                "source_sha256": analysis["source"]["sha256"], "reason": "schema mismatch",
                "response_id": "gen-invalid-output", "provider": "Google AI Studio",
                "usage": {"prompt_tokens": 321, "completion_tokens": 7, "total_tokens": 328},
                "budget": {"actual_cost_usd": 0.000267, "actual_cost_known": True},
                "diagnostic": {
                    "phase": "output_validation", "type": "schema_mismatch", "http_status": 200,
                    "request_id": "req-invalid-output", "response_id": "gen-invalid-output",
                    "finish_reason": "stop", "usage": {"prompt_tokens": 321, "completion_tokens": 7, "total_tokens": 328},
                    "cost_usd": 0.000267, "submission_state": "response_received",
                },
            }

    app = _app(tmp_path, monkeypatch, review_module=ClearlyNamedMockInvalidReview)
    monkeypatch.setenv("ANIMATION_REVIEW_ENABLED", "1")
    monkeypatch.setenv("OPENROUTER_API_KEY", "unit-test-not-real")
    monkeypatch.setenv("ANIMATION_REVIEW_MAX_USD", "0.05")
    monkeypatch.setenv("ANIMATION_REVIEW_MAX_INPUT_TOKENS", "1000")
    monkeypatch.setenv("ANIMATION_REVIEW_MAX_OUTPUT_TOKENS", "1200")
    monkeypatch.setenv("ANIMATION_REVIEW_MODEL_METADATA_FILE", str(ROOT / "artifacts/review-candidates/openrouter-model-metadata.json"))
    job_id, artifact = _video_job(app, WAN_VIDEO)

    with TestClient(app) as client:
        client.post(f"/v1/jobs/{job_id}/automatic-review", headers=AUTH, json=_request(artifact, authorize=True)).raise_for_status()
        app.state.runner.process_once()
        job = client.get(f"/v1/jobs/{job_id}", headers=AUTH).json()

    review = job["automatic_reviews"][0]
    assert review["response_id"] == "gen-invalid-output"
    assert review["provider"] == "Google AI Studio"
    assert review["usage"]["total_tokens"] == 328
    assert review["budget"]["actual_cost_usd"] == 0.000267
    assert review["diagnostic"]["phase"] == "output_validation"
    assert review["diagnostic"]["submission_state"] == "response_received"


def test_mocked_approved_automatic_review_extracts_native_indices_and_creates_typed_approval(tmp_path, monkeypatch):
    class ClearlyNamedMockApprovedReview:
        @staticmethod
        def analyze_candidates(workdir, input_name, **kwargs):
            source = Path(workdir) / input_name
            return {
                "source": {
                    "file": input_name,
                    "sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
                    "bytes": source.stat().st_size,
                    "native_fps": 30.0,
                },
                "hard_failures": [],
                "candidates": [{
                    "id": "candidate-01",
                    "start_source_frame_index": 1,
                    "end_source_frame_index": 13,
                    "sampling_evidence": {"maximum_native_gap": 3},
                }],
            }

        @staticmethod
        def submit_review(workdir, input_name, analysis, **kwargs):
            candidate = analysis["candidates"][0]
            return {
                "status": "approved",
                "approved": True,
                "model": DEFAULT_MODEL,
                "source_sha256": analysis["source"]["sha256"],
                "provider_decision": "approve",
                "selected_candidate": candidate,
                "self_reported_confidence": {"value": 0.99, "calibrated": False},
                "budget": {"cap_usd": 0.05, "actual_cost_usd": None, "actual_cost_known": False},
            }

    app = _app(tmp_path, monkeypatch, review_module=ClearlyNamedMockApprovedReview)
    monkeypatch.setenv("ANIMATION_REVIEW_ENABLED", "1")
    monkeypatch.setenv("OPENROUTER_API_KEY", "unit-test-not-real")
    monkeypatch.setenv("ANIMATION_REVIEW_MAX_USD", "0.05")
    monkeypatch.setenv("ANIMATION_REVIEW_MAX_INPUT_TOKENS", "1000")
    monkeypatch.setenv("ANIMATION_REVIEW_MAX_OUTPUT_TOKENS", "1200")
    metadata = ROOT / "artifacts/review-candidates/openrouter-model-metadata.json"
    monkeypatch.setenv("ANIMATION_REVIEW_MODEL_METADATA_FILE", str(metadata))
    job_id, artifact = _video_job(app, WAN_VIDEO)
    with TestClient(app) as client:
        response = client.post(f"/v1/jobs/{job_id}/automatic-review", headers=AUTH, json=_request(artifact, authorize=True))
        assert response.status_code == 202
        review_stage_id = response.json()["id"]
        app.state.runner.process_once()
        job = client.get(f"/v1/jobs/{job_id}", headers=AUTH).json()

    assert job["automatic_reviews"], job.get("message")
    review = job["automatic_reviews"][0]
    assert review["status"] == "approved"
    assert review["approval_type"] == "automatic_model_validated"
    assert review["model"] == DEFAULT_MODEL
    assert review["stage_job_id"] == review_stage_id
    assert review["server_request_binding"]["request_id"] == review_stage_id
    assert app.state.store.has_approval(job_id, "video-output.mp4") is True
    extraction = json.loads((app.state.store.job_dir(job_id) / "extract-frames.json").read_text())
    selected = review["selected_candidate"]
    expected = review["selected_sampling"]["indices"]
    assert [frame["source_index"] for frame in extraction["frames"]] == expected
    assert len(expected) == 8
    assert review["selected_sampling"]["density_basis"] == "compact_exact_original_frames"
    assert review["selected_sampling"]["duration_preserved"] is True
    assert extraction["source"]["sha256"] == artifact["sha256"]
    assert extraction["automatic_selection"] is True
    assert extraction["automatic_review_id"] == review["id"]
    density_receipt = json.loads((app.state.store.job_dir(job_id) / "selection-density-receipt.json").read_text())
    review_receipt = app.state.store.job_dir(job_id) / "automatic-review-result.json"
    assert density_receipt["reviewer_receipt"]["sha256"] == hashlib.sha256(review_receipt.read_bytes()).hexdigest()
    assert density_receipt["sampling"]["indices"] == expected
    assert extraction["density_selection"]["receipt_sha256"] == hashlib.sha256(
        (app.state.store.job_dir(job_id) / "selection-density-receipt.json").read_bytes()
    ).hexdigest()
    assert extraction["decode"]["selection"] == "exact_sparse_native_frame_indices"
    assert all(app.state.store.has_approval(job_id, frame["file"]) for frame in extraction["frames"])
    assert app.state.store.has_approval(job_id, "unrelated-frame.png") is False
    source_path = app.state.store.job_dir(job_id) / "video-output.mp4"
    source_path.write_bytes(b"replacement")
    with app.state.store.connect() as connection:
        app.state.store.upsert_artifact(connection, job_id, "video-output.mp4", "replacement", source_path)
    assert app.state.store.has_approval(job_id, "video-output.mp4") is False
