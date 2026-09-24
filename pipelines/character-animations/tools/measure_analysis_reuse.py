#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import animation_review
from runner import Runner
from store import Store

DEFAULT_SOURCE = ROOT / "review/cadence-uninterrupted/phase2-fresh-uninterrupted/source-video.mp4"
DEFAULT_OUTPUT = ROOT / "review/latency-step1/measurement.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description="Free real-video measurement of server-owned analysis reuse")
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    output = args.output.resolve()
    workspace = output.parent / "measurement-workspace"
    if workspace.exists():
        shutil.rmtree(workspace)
    workspace.mkdir(parents=True)

    class CountingProductionReview:
        calls = 0

        @classmethod
        def analyze_candidates(cls, workdir: Path, input_name: str, **kwargs: Any) -> dict[str, Any]:
            cls.calls += 1
            return animation_review.analyze_candidates(workdir, input_name, **kwargs)

        @staticmethod
        def submit_review(*args: Any, **kwargs: Any) -> dict[str, Any]:
            raise AssertionError("measurement must not call a paid reviewer")

    store = Store(workspace / "jobs.sqlite3", workspace / "jobs")
    job = store.create_job("reference.png", {"measurement": "analysis-reuse"}, b"not-used")
    job_id = job["id"]
    workdir = store.job_dir(job_id)
    source_path = workdir / "video-output.mp4"
    shutil.copyfile(args.source.resolve(strict=True), source_path)
    with store.connect() as connection:
        store.upsert_artifact(connection, job_id, source_path.name, "existing_real_video", source_path)
    source = store.get_artifact(job_id, source_path.name)
    assert source is not None

    runner = Runner(store, review_module=CountingProductionReview)
    started = time.monotonic()
    prepared = runner.prepare_automatic_review_analysis(job_id, source_path.name)
    preparation_seconds = time.monotonic() - started
    before = prepared["analysis"]

    store.enqueue_stage(job_id, "automatic_review", {
        "input": source_path.name,
        "source_sha256": source["sha256"],
        "source_revision": source["revision"],
        "authorize_paid_review": False,
        "budget_cap_usd": None,
    })
    started = time.monotonic()
    assert runner.process_once() is True
    handoff_seconds = time.monotonic() - started
    after = json.loads((workdir / "automatic-review-analysis.json").read_text(encoding="utf-8"))
    job_after = store.get_job(job_id)
    assert job_after is not None

    candidate_values_equal = before.get("candidates") == after.get("candidates")
    source_values_equal = before.get("source") == after.get("source")
    frame_indices_before = [sample.get("source_frame_index") for sample in before.get("samples", [])]
    frame_indices_after = [sample.get("source_frame_index") for sample in after.get("samples", [])]
    result = {
        "schema": "analysis-reuse-measurement-v1",
        "source": {"file": str(args.source.resolve()), "sha256": sha256(args.source.resolve()), "revision": source["revision"]},
        "paid_reviewer": {"called": False, "label": "mock guard; free orchestration only"},
        "production_analyzer_calls": CountingProductionReview.calls,
        "timings_seconds": {
            "server_analysis_preparation": round(preparation_seconds, 6),
            "automatic_review_handoff_with_reuse": round(handoff_seconds, 6),
            "combined": round(preparation_seconds + handoff_seconds, 6),
        },
        "analysis_recipe": prepared["recipe"],
        "analysis_sha256": prepared["analysis_sha256"],
        "candidate_count": len(before.get("candidates", [])),
        "candidate_values_equal_before_after": candidate_values_equal,
        "source_values_equal_before_after": source_values_equal,
        "source_frame_indices_equal_before_after": frame_indices_before == frame_indices_after,
        "source_frame_indices": frame_indices_before,
        "review_status": job_after["automatic_reviews"][0]["status"],
        "review_reason": job_after["automatic_reviews"][0]["reason"],
        "pass": CountingProductionReview.calls == 1 and candidate_values_equal and source_values_equal and frame_indices_before == frame_indices_after,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
