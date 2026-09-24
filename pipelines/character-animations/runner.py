from __future__ import annotations

import importlib
import hashlib
import json
import math
import os
import threading
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from store import Store, safe_basename, sanitize_message

PAID_STAGES = {"generate_facing", "generate_video", "remove_background"}
ALLOWED_STAGES = {"inspect_reference", "generate_facing", "generate_video", "extract_frames", "remove_background", "pack", "mirror", "spatial_export"}
FORGED_BUDGET_KEYS = {"paid", "authorized", "allow_paid", "budget_cents", "budget", "max_cost", "approved", "automatic_review"}
AUTOMATIC_REVIEW_MODEL = "google/gemini-3.8-flash"
DENSITY_POLICY = {
    "revision": "native-density-v2",
    "minimum_playback_fps": 18.0,
    "maximum_export_frames": 40,
    "prefer_every_native_frame_when_bounded": True,
    "synthetic_frames_allowed": False,
}
DENSITY_POLICY_HASH = hashlib.sha256(
    json.dumps(DENSITY_POLICY, sort_keys=True, separators=(",", ":")).encode("utf-8")
).hexdigest()
FRAME_POLICY_OPTIONS = ("8", "12", "16", "native")
ANALYSIS_CACHE_NAME = "automatic-review-analysis-cache.json"
ANALYSIS_RECIPE_REVISION = "automatic-candidate-analysis-v1"
ANALYSIS_PARAMETERS = {
    "sample_fps": 12.0,
    "minimum_loop_seconds": 0.5,
    "maximum_loop_seconds": 2.5,
}


def _canonical_sha256(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def frame_policy(option: str = "8") -> dict[str, Any]:
    if option not in FRAME_POLICY_OPTIONS:
        raise ValueError(f"frame policy must be one of {', '.join(FRAME_POLICY_OPTIONS)}")
    if option == "native":
        policy = {"option": option, **DENSITY_POLICY}
    else:
        policy = {
            "option": option,
            "revision": f"compact-exact-{option}-v1",
            "frame_count": int(option),
            "preserve_cycle_duration": True,
            "exact_original_frames_only": True,
            "synthetic_frames_allowed": False,
        }
    return {**policy, "sha256": _canonical_sha256(policy)}


def _analysis_recipe(frame_policy_name: str = "8", action: str = "walk") -> dict[str, Any]:
    policy = frame_policy(frame_policy_name)
    recipe = {
        "revision": ANALYSIS_RECIPE_REVISION,
        "parameters": ANALYSIS_PARAMETERS,
        "frame_policy": policy,
        "action": action,
    }
    return {**recipe, "sha256": _canonical_sha256(recipe)}


def sparse_cycle_sampling(
    candidate: dict[str, Any], *, native_fps: float, target_frames: int | None = None,
    frame_policy_name: str = "8",
) -> dict[str, Any]:
    start = candidate.get("start_source_frame_index")
    end = candidate.get("end_source_frame_index")
    if type(start) is not int or type(end) is not int or not 0 <= start < end:
        raise ValueError("selected candidate has invalid native frame bounds")
    if type(native_fps) not in (int, float) or native_fps <= 0:
        raise ValueError("native fps is invalid")
    count = end - start
    evidence = candidate.get("sampling_evidence") if isinstance(candidate.get("sampling_evidence"), dict) else {}
    maximum_gap = evidence.get("maximum_native_gap", 3)
    if type(maximum_gap) is not int or not 1 <= maximum_gap <= 12:
        raise ValueError("candidate sampling evidence has invalid maximum native gap")
    policy = frame_policy(frame_policy_name)
    if target_frames is None and frame_policy_name == "native":
        duration = count / float(native_fps)
        minimum_fps = min(float(native_fps), DENSITY_POLICY["minimum_playback_fps"])
        density_frames = max(2, math.ceil(duration * minimum_fps - 1e-12))
        pose_gap_frames = max(2, (count + maximum_gap - 1) // maximum_gap)
        if count <= DENSITY_POLICY["maximum_export_frames"]:
            target_frames = count
        else:
            target_frames = max(density_frames, pose_gap_frames)
        if target_frames > DENSITY_POLICY["maximum_export_frames"]:
            raise ValueError("density target exceeds bounded frame count")
        density_basis = "native_or_at_least_18fps_with_pose_gap"
        minimum_playback_fps: float | None = minimum_fps
    elif target_frames is None:
        target_frames = int(policy["frame_count"])
        if count < target_frames:
            raise ValueError(f"selected cycle has fewer than {target_frames} distinct original frames")
        density_basis = "compact_exact_original_frames"
        minimum_playback_fps = None
    else:
        density_basis = "explicit_legacy_target"
        minimum_playback_fps = None
    if type(target_frames) is not int or not 2 <= target_frames <= DENSITY_POLICY["maximum_export_frames"]:
        raise ValueError("cycle sampling target must be between 2 and 40 frames")
    output_count = min(target_frames, count)
    indices = [start + round(order * count / output_count) for order in range(output_count)]
    if candidate.get("action") == "punch":
        phases = candidate.get("phase_proposals")
        if not isinstance(phases, dict) or set(phases) != {"anticipation", "maximum_extension", "recovery"}:
            raise ValueError("punch candidate has incomplete phase proposals")
        phase_indices = [phases[name] for name in ("anticipation", "maximum_extension", "recovery")]
        if any(type(value) is not int for value in phase_indices) or not start < phase_indices[0] < phase_indices[1] < phase_indices[2] < end:
            raise ValueError("punch candidate phase bounds are invalid")
        impact = candidate.get("impact_source_frame_index")
        if type(impact) is not int or not start <= impact < end:
            raise ValueError("punch candidate lacks a valid detected impact frame")
        impact_transition = min(phase_indices[2] - 1, impact + max(1, round(float(native_fps) * 0.125)))
        mandatory = sorted(set([start, *phase_indices, impact_transition]))
        if len(mandatory) > output_count:
            raise ValueError("frame policy cannot retain distinct action phase keyposes")
        indices = mandatory
        while len(indices) < output_count:
            boundaries = [*indices, end]
            gaps = [(boundaries[order + 1] - boundaries[order], boundaries[order], boundaries[order + 1]) for order in range(len(boundaries) - 1)]
            gap, left, right = max(gaps, key=lambda item: (item[0], item[1]))
            if gap <= 1:
                raise ValueError("frame policy cannot retain distinct action phase keyposes")
            indices.append(left + gap // 2)
            indices.sort()
    if indices != sorted(set(indices)) or indices[-1] >= end:
        raise ValueError("sparse cycle sampling failed")
    duration = count / float(native_fps)
    frame_durations = [
        ((indices[order + 1] if order + 1 < len(indices) else end) - index) / float(native_fps)
        for order, index in enumerate(indices)
    ]
    return {
        "indices": indices,
        "native_interval": {"start_inclusive": start, "end_exclusive": end},
        "cycle_duration_seconds": duration,
        "playback_fps": output_count / duration,
        "frame_durations_seconds": frame_durations,
        "interval_end_timestamp_seconds": end / float(native_fps),
        "target_frames": target_frames,
        "selected_frame_count": output_count,
        "maximum_native_gap": max(
            [right - left for left, right in zip(indices, indices[1:])] + [end - indices[-1]]
        ),
        "density_basis": density_basis,
        "frame_policy": policy,
        "density_policy_revision": policy["revision"],
        "density_policy_sha256": policy["sha256"],
        "minimum_playback_fps": minimum_playback_fps,
        "density_target_met": None if minimum_playback_fps is None else output_count / duration + 1e-12 >= minimum_playback_fps,
        "exact_native_cadence": output_count == count,
        "synthetic_frames_used": False,
        "duration_preserved": True,
    }


class Runner:
    def __init__(self, store: Store, pipeline_module: Any | None = None, worker_id: str | None = None, review_module: Any | None = None):
        self.store = store
        self.pipeline = pipeline_module if pipeline_module is not None else self._load_pipeline()
        self.worker_id = worker_id or f"worker-{uuid.uuid4().hex[:8]}"
        self.review = review_module if review_module is not None else importlib.import_module("animation_review")
        self._stop = threading.Event()
        self._process_lock = threading.Lock()
        self._thread: threading.Thread | None = None

    def _load_pipeline(self) -> Any | None:
        try:
            return importlib.import_module("pipeline")
        except Exception:
            return None

    def prepare_automatic_review_analysis(self, job_id: str, source_name: str, frame_policy_name: str = "8", action: str = "walk") -> dict[str, Any]:
        """Create a server-owned immutable analysis receipt for later review."""
        source = self.store.get_artifact(job_id, source_name)
        if not source:
            raise ValueError("automatic review analysis source artifact is unavailable")
        workdir = self.store.job_dir(job_id)
        analysis = self.review.analyze_candidates(workdir, source_name, **ANALYSIS_PARAMETERS, action=action)
        if (analysis.get("source") or {}).get("sha256") != source["sha256"]:
            raise ValueError("automatic review analysis source hash mismatch")
        receipt = {
            "schema": "animation-automatic-analysis-cache-v1",
            "source": {"file": source_name, "sha256": source["sha256"], "revision": source["revision"]},
            "recipe": _analysis_recipe(frame_policy_name, action),
            "analysis_sha256": _canonical_sha256(analysis),
            "analysis": analysis,
            "server_generated": True,
        }
        target = workdir / ANALYSIS_CACHE_NAME
        _atomic_json(target, receipt)
        with self.store.connect() as connection:
            self.store.upsert_artifact(connection, job_id, target.name, "automatic_analysis_preparation", target)
        return receipt

    def _prepared_analysis(self, job_id: str, source: dict[str, Any], frame_policy_name: str, action: str) -> dict[str, Any] | None:
        record = self.store.get_artifact(job_id, ANALYSIS_CACHE_NAME)
        if not record or record.get("stage") != "automatic_analysis_preparation":
            return None
        path = self.store.job_dir(job_id) / ANALYSIS_CACHE_NAME
        try:
            raw = path.read_bytes()
        except OSError as exc:
            raise ValueError("server analysis cache is corrupt") from exc
        if hashlib.sha256(raw).hexdigest() != record["sha256"]:
            raise ValueError("server analysis cache is corrupt")
        try:
            receipt = json.loads(raw)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise ValueError("server analysis cache is corrupt") from exc
        expected_source = {"file": source["name"], "sha256": source["sha256"], "revision": source["revision"]}
        if receipt.get("source") != expected_source or receipt.get("recipe") != _analysis_recipe(frame_policy_name, action):
            return None
        analysis = receipt.get("analysis")
        if (
            receipt.get("schema") != "animation-automatic-analysis-cache-v1"
            or receipt.get("server_generated") is not True
            or not isinstance(analysis, dict)
            or receipt.get("analysis_sha256") != _canonical_sha256(analysis)
            or (analysis.get("source") or {}).get("sha256") != source["sha256"]
        ):
            raise ValueError("server analysis cache is corrupt")
        return analysis

    def start_background(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self.store.recover_incomplete("runner start")
        self._thread = threading.Thread(target=self._loop, name="animation-pipeline-runner", daemon=True)
        self._thread.start()

    def stop_background(self, timeout: float = 5) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=timeout)

    def _loop(self) -> None:
        while not self._stop.is_set():
            processed = self.process_once()
            if not processed:
                self._stop.wait(0.2)

    def process_all_available(self, limit: int = 20) -> int:
        count = 0
        for _ in range(limit):
            if not self.process_once():
                break
            count += 1
        return count

    def process_once(self) -> bool:
        with self._process_lock:
            return self._process_once_locked()

    def _process_once_locked(self) -> bool:
        stage_job = self.store.claim_next_stage(self.worker_id)
        if not stage_job:
            return False
        if self.pipeline is None or not hasattr(self.pipeline, "run_stage"):
            self.store.fail_stage(stage_job, "pipeline module unavailable: run_stage(stage, workdir, params) is required", state="failed")
            return True
        stage = stage_job["stage"]
        params = dict(stage_job.get("params") or {})
        workdir = self.store.job_dir(stage_job["job_id"])
        try:
            if stage == "automatic_review":
                self._run_automatic_review(stage_job, workdir, params)
                return True
            result = self.pipeline.run_stage(stage, workdir, params)
            if not isinstance(result, dict):
                raise ValueError("pipeline returned non-dict result")
            artifacts = result.get("artifacts") or []
            if not isinstance(artifacts, list):
                raise ValueError("pipeline artifacts must be a list")
            if stage == "remove_background" and result.get("status") == "needs_review":
                spatial_export = importlib.import_module("spatial_export")
                ingest = spatial_export.ingest_completed_removal_batch(
                    workdir,
                    spatial_export.server_cutout_cache_dir(workdir, create=True),
                    str(params.get("preset", "waldlicht-removal-v1")),
                    "wavespeed-image-background-remover-output-v1",
                )
                artifacts = [*artifacts, ingest["receipt"]]
                details = dict(result.get("details") or {})
                details["cutout_cache_ingest"] = ingest
                result = {**result, "artifacts": artifacts, "details": details}
            safe_artifacts = []
            for name in artifacts:
                if not safe_basename(name):
                    raise ValueError(f"unsafe artifact name from pipeline: {name!r}")
                path = workdir / name
                try:
                    path.relative_to(workdir)
                except ValueError as exc:
                    raise ValueError("artifact escaped job directory") from exc
                safe_artifacts.append(name)
            status = result.get("status")
            if status not in {"completed", "needs_review", "needs_attention"}:
                raise ValueError("pipeline status must be completed, needs_review, or needs_attention")
            self.store.finish_stage(stage_job, result, safe_artifacts)
        except Exception as exc:  # sanitized at store boundary
            self.store.fail_stage(stage_job, sanitize_message(exc) or "stage failed", state="failed")
        return True

    def _run_automatic_review(self, stage_job: dict[str, Any], workdir: Path, params: dict[str, Any]) -> None:
        source_name = params["input"]
        source = self.store.get_artifact(stage_job["job_id"], source_name)
        if not source or source["sha256"] != params["source_sha256"] or source["revision"] != params["source_revision"]:
            raise ValueError("automatic review source revision is stale")
        frame_policy_name = params.get("frame_policy", "8")
        action = params.get("action", "walk")
        if action not in {"walk", "punch"}:
            raise ValueError("unsupported animation action")
        selected_frame_policy = frame_policy(frame_policy_name)
        analysis = self._prepared_analysis(stage_job["job_id"], source, frame_policy_name, action)
        if analysis is None:
            analysis = self.prepare_automatic_review_analysis(stage_job["job_id"], source_name, frame_policy_name, action)["analysis"]
        _atomic_json(workdir / "automatic-review-analysis.json", analysis)
        review_id = uuid.uuid4().hex
        paid_transport_called = False
        if analysis.get("hard_failures"):
            review_result = {
                "status": "rejected", "approved": False, "model": AUTOMATIC_REVIEW_MODEL,
                "source_sha256": source["sha256"], "local_hard_failures": list(analysis["hard_failures"]),
                "reason": "local hard failure rejected source before paid review",
            }
        elif not params.get("authorize_paid_review"):
            review_result = {
                "status": "needs_attention", "approved": False, "model": AUTOMATIC_REVIEW_MODEL,
                "source_sha256": source["sha256"], "reason": "automatic paid review is disabled for this request",
            }
        else:
            policy = automatic_review_policy()
            request_cap = params.get("budget_cap_usd")
            if not policy["available"]:
                review_result = {
                    "status": "needs_attention", "approved": False, "model": AUTOMATIC_REVIEW_MODEL,
                    "source_sha256": source["sha256"], "reason": policy["blocked_reason"],
                }
            elif type(request_cap) not in (int, float) or request_cap <= 0 or request_cap > policy["max_review_usd"]:
                review_result = {
                    "status": "needs_attention", "approved": False, "model": AUTOMATIC_REVIEW_MODEL,
                    "source_sha256": source["sha256"], "reason": "review budget cap is missing or exceeds server policy",
                }
            else:
                paid_transport_called = True
                review_result = self.review.submit_review(
                    workdir, source_name, analysis, paid_enabled=True,
                    api_key=os.environ.get("OPENROUTER_API_KEY"), budget_cap_usd=request_cap,
                    max_input_tokens=policy["max_input_tokens"], max_tokens=policy["max_output_tokens"],
                    capability_metadata=policy["metadata"],
                    request_binding={
                        "request_id": stage_job["id"],
                        "source_sha256": source["sha256"],
                        "source_revision": source["revision"],
                    },
                )
                current_source = self.store.get_artifact(stage_job["job_id"], source_name)
                if (
                    not current_source
                    or current_source["sha256"] != source["sha256"]
                    or current_source["revision"] != source["revision"]
                ):
                    raise ValueError("automatic review source revision became stale during provider review")
        provider_receipt = {
            key: review_result.get(key)
            for key in ("response_id", "provider", "usage", "budget", "diagnostic")
            if review_result.get(key) is not None
        }
        if review_result.get("model") != AUTOMATIC_REVIEW_MODEL or review_result.get("source_sha256") != source["sha256"]:
            review_result = {
                "status": "needs_attention", "approved": False, "model": AUTOMATIC_REVIEW_MODEL,
                "source_sha256": source["sha256"], "reason": "review result provenance validation failed",
                **provider_receipt,
            }
        if review_result.get("status") == "approved":
            selected_result = review_result.get("selected_candidate")
            bound_candidate = next(
                (candidate for candidate in analysis.get("candidates", []) if candidate.get("id") == (selected_result or {}).get("id")),
                None,
            )
            if review_result.get("provider_decision") != "approve" or selected_result != bound_candidate:
                review_result = {
                    "status": "needs_attention", "approved": False, "model": AUTOMATIC_REVIEW_MODEL,
                    "source_sha256": source["sha256"], "reason": "approved review candidate is not exactly bound to local analysis",
                    **provider_receipt,
                }
        review_result = {**review_result, "frame_policy": selected_frame_policy}
        artifacts = ["automatic-review-analysis.json"]
        selected = review_result.get("selected_candidate") if review_result.get("status") == "approved" else None
        selected_sampling = None
        if review_result.get("status") == "approved":
            if not review_result.get("approved") or not isinstance(selected, dict):
                raise ValueError("approved automatic review lacks a validated selected candidate")
            start = selected.get("start_source_frame_index")
            end = selected.get("end_source_frame_index")
            if type(start) is not int or type(end) is not int or not 0 <= start < end:
                raise ValueError("approved candidate has invalid native frame bounds")
            selected_sampling = sparse_cycle_sampling(
                selected, native_fps=analysis["source"]["native_fps"], frame_policy_name=frame_policy_name,
            )
            _atomic_json(workdir / "automatic-review-result.json", review_result)
            reviewer_receipt_sha256 = hashlib.sha256((workdir / "automatic-review-result.json").read_bytes()).hexdigest()
            density_receipt = {
                "schema": "animation-selection-density-v1",
                "policy": selected_frame_policy,
                "frame_policy_option": frame_policy_name,
                "source": {"file": source_name, "sha256": source["sha256"], "revision": source["revision"]},
                "reviewer_receipt": {"file": "automatic-review-result.json", "sha256": reviewer_receipt_sha256},
                "review_id": review_id,
                "review_model": AUTOMATIC_REVIEW_MODEL,
                "approved_candidate": {
                    "id": selected["id"],
                    "start_source_frame_index": start,
                    "end_source_frame_index": end,
                },
                "sampling": selected_sampling,
                "action": action,
                "loop": action == "walk",
                "representation_only": True,
                "reviewer_decision_mutated": False,
            }
            _atomic_json(workdir / "selection-density-receipt.json", density_receipt)
            density_receipt_sha256 = hashlib.sha256((workdir / "selection-density-receipt.json").read_bytes()).hexdigest()
            extract = self.pipeline.run_stage("extract_frames", workdir, {
                "input": source_name, "fps": analysis["source"]["native_fps"],
                "indices": selected_sampling["indices"], "output_prefix": "selected",
                "automatic_review": {
                    "id": review_id,
                    "model": AUTOMATIC_REVIEW_MODEL,
                    "source_sha256": source["sha256"],
                    "density_receipt": "selection-density-receipt.json",
                    "density_receipt_sha256": density_receipt_sha256,
                    "density_policy_sha256": selected_frame_policy["sha256"],
                },
            })
            artifacts.append("selection-density-receipt.json")
            artifacts.extend(extract.get("artifacts") or [])
        if not (workdir / "automatic-review-result.json").exists():
            _atomic_json(workdir / "automatic-review-result.json", review_result)
        artifacts.append("automatic-review-result.json")
        record = {
            "id": review_id, "status": review_result.get("status", "needs_attention"), "model": AUTOMATIC_REVIEW_MODEL,
            "source_artifact": source_name, "source_sha256": source["sha256"], "source_revision": source["revision"],
            "analysis_artifact": "automatic-review-analysis.json", "result_artifact": "automatic-review-result.json",
            "candidate_count": len(analysis.get("candidates") or []), "local_hard_failures": list(analysis.get("hard_failures") or []),
            "selected_candidate": selected, "selected_sampling": selected_sampling,
            "reason": review_result.get("reason"), "usage": review_result.get("usage"),
            "budget": review_result.get("budget"), "paid_transport_called": paid_transport_called,
            "response_id": review_result.get("response_id"), "provider": review_result.get("provider"),
            "diagnostic": review_result.get("diagnostic"),
            "frame_policy": selected_frame_policy,
            "action": action,
            "server_request_binding": {
                "request_id": stage_job["id"],
                "source_sha256": source["sha256"],
                "source_revision": source["revision"],
            },
        }
        result = {
            "status": "needs_review" if record["status"] == "approved" else "needs_attention",
            "artifacts": artifacts,
            "details": {
                "message": record["reason"], "response_id": record["response_id"],
                "provider": record["provider"], "usage": record["usage"],
                "budget": record["budget"], "diagnostic": record["diagnostic"],
            },
        }
        self.store.finish_automatic_review(stage_job, result, list(dict.fromkeys(artifacts)), record)


def _atomic_json(path: Path, value: dict[str, Any]) -> None:
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    temporary.write_text(json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def automatic_review_policy() -> dict[str, Any]:
    if os.environ.get("ANIMATION_REVIEW_ENABLED") != "1":
        return {"available": False, "blocked_reason": "automatic paid reviewer is disabled"}
    if not os.environ.get("OPENROUTER_API_KEY"):
        return {"available": False, "blocked_reason": "OpenRouter credential is unavailable"}
    try:
        maximum = float(os.environ.get("ANIMATION_REVIEW_MAX_USD", "0"))
        max_input = int(os.environ.get("ANIMATION_REVIEW_MAX_INPUT_TOKENS", "0"))
        max_output = int(os.environ.get("ANIMATION_REVIEW_MAX_OUTPUT_TOKENS", "0"))
    except ValueError:
        return {"available": False, "blocked_reason": "automatic review budget or token bounds are invalid"}
    if maximum <= 0 or max_input <= 0 or not 64 <= max_output <= 4096:
        return {"available": False, "blocked_reason": "automatic review cost cap and token bounds are not configured"}
    metadata_name = os.environ.get("ANIMATION_REVIEW_MODEL_METADATA_FILE")
    try:
        metadata = json.loads(Path(metadata_name or "").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"available": False, "blocked_reason": "fresh exact-model capability metadata is unavailable"}
    if metadata.get("id") != AUTOMATIC_REVIEW_MODEL:
        return {"available": False, "blocked_reason": "configured reviewer metadata is not for the exact model"}
    try:
        fetched_at = datetime.fromisoformat(str(metadata["fetched_at_utc"]).replace("Z", "+00:00"))
    except (KeyError, TypeError, ValueError):
        return {"available": False, "blocked_reason": "fresh exact-model capability metadata is unavailable"}
    current = datetime.now(timezone.utc)
    if fetched_at.tzinfo is None or fetched_at < current - timedelta(hours=24) or fetched_at > current + timedelta(minutes=5):
        return {"available": False, "blocked_reason": "fresh exact-model capability metadata is unavailable"}
    if metadata.get("source") != "https://openrouter.ai/api/v1/models":
        return {"available": False, "blocked_reason": "exact-model metadata source is invalid"}
    normalized = dict(metadata)
    if "pricing" not in normalized and isinstance(normalized.get("pricing_usd_per_token"), dict):
        normalized["pricing"] = normalized["pricing_usd_per_token"]
    if "supported_parameters" not in normalized and isinstance(normalized.get("supported_parameters_used_by_reviewer"), list):
        normalized["supported_parameters"] = normalized["supported_parameters_used_by_reviewer"]
    return {
        "available": True, "blocked_reason": None, "max_review_usd": maximum,
        "max_input_tokens": max_input, "max_output_tokens": max_output, "metadata": normalized,
    }


def validate_stage_request(stage: str, params: dict[str, Any]) -> dict[str, Any]:
    if stage not in ALLOWED_STAGES:
        raise ValueError("unknown stage")
    if not isinstance(params, dict):
        raise ValueError("params must be an object")
    for key in params:
        if key in FORGED_BUDGET_KEYS:
            raise ValueError("budget/authorization flags are server-owned and cannot be supplied in params")
        if len(key) > 80:
            raise ValueError("param key too long")
    validated = dict(params)
    if stage == "generate_video":
        import provider

        preset = provider.get_preset(validated.get("preset", "waldlicht-video-v1"), "image_to_video")
        options = {key: value for key, value in validated.items() if key not in {"input", "preset"}}
        for key, value in preset.defaults.items():
            if key != "first_equals_last":
                options.setdefault(key, value)
                validated.setdefault(key, value)
        preset.build_payload(options, ["https://validation.invalid/job-owned-input"])
        preset.quote(options)
    return validated
