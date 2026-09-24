#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import real_cold_e2e as harness

ROOT = Path(__file__).resolve().parents[1]
PARENT = ROOT / "review/cadence-uninterrupted"
OUT = PARENT / "phase2-fresh-uninterrupted"
FREEZE = PARENT / "FROZEN_RUN_CONFIG.json"
FILES = [
    "animation_review.py", "pipeline.py", "provider.py", "quality_gates.py", "runner.py",
    "spatial_export.py", "store.py", "app.py", "tools/real_cold_e2e.py",
    "tools/cadence_uninterrupted_full_run.py",
]
PRIOR = 2.19847175


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def prior_reconciliation() -> dict:
    phase1 = json.loads((PARENT / "phase1-density-proof/REPORT.json").read_text(encoding="utf-8"))
    if phase1["status"] != "phase1_artifact_ready_pending_independent_visual_inspection":
        raise RuntimeError("phase 1 is not a completed density proof")
    if float(phase1["cost"]["cumulative_conservative_maximum_usd"]) != PRIOR:
        raise RuntimeError("phase-1 cumulative ledger changed")
    return {
        "maximum_accounted_usd": PRIOR,
        "sources": [
            "review/real-cold-e2e-01/REPORT.md",
            "review/cadence-uninterrupted/phase1-density-proof/REPORT.json",
        ],
        "provider_ids": [],
        "unique_provider_ids": 0,
        "deduplicated_repeated_id_occurrences": 0,
        "newer_cost_ledgers_found": False,
        "basis": "retained cumulative conservative maximum 2.11847175 plus phase-1 missing-frame liability 0.08",
    }


def main() -> int:
    if OUT.exists():
        raise RuntimeError("fresh phase-2 output already exists; refusing to overwrite")
    PARENT.mkdir(parents=True, exist_ok=True)
    file_hashes = {name: sha(ROOT / name) for name in FILES}
    revision_hash = hashlib.sha256(
        json.dumps(file_hashes, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    frozen = {
        "schema": "cadence-uninterrupted-frozen-run-v1",
        "implementation_revision_sha256": revision_hash,
        "files": file_hashes,
        "harness": "tools/real_cold_e2e.py via bounded parameter wrapper",
        "output": str(OUT.relative_to(ROOT)),
        "task_incremental_cap_usd": 2.0,
        "prior_cumulative_conservative_usd": PRIOR,
        "source": {
            "model": "wavespeed-ai/minimax-h3/image-to-video",
            "preset": "minimax-h3-ne-source-5s-768p-v1",
            "duration_seconds": 5,
            "resolution": "768p",
            "first_image_equals_last_image": True,
            "fresh_quote_usd": {"discounted": 0.2, "undiscounted": 0.4, "source_cap": 0.5},
            "seed": "new_random_recorded_by_harness",
        },
        "reviewer": {
            "model": "google/gemini-3.8-flash",
            "calls_maximum": 1,
            "fallback_allowed": False,
            "max_output_tokens": 600,
            "input_bound": "constructed numbered-image bound refreshed before call",
            "max_price": "live exact-model per-token prices",
        },
        "removal": {
            "model": "wavespeed-ai/image-background-remover",
            "unit_quote_usd": 0.004,
            "maximum_frames": 40,
            "maximum_inflight": 1,
        },
        "density_policy": {
            "revision": "native-density-v2",
            "minimum_playback_fps": 18.0,
            "prefer_all_native_frames_when_bounded": True,
            "maximum_frames": 40,
            "synthetic_frames": False,
        },
        "no_source_retry": True,
        "no_reviewer_retry": True,
        "public_policy_changed": False,
        "deployment_changed": False,
    }
    FREEZE.write_text(json.dumps(frozen, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    FREEZE.chmod(0o444)

    harness.OUT = OUT
    harness.INCREMENTAL_CAP = 2.0
    harness.MAX_REMOVALS = 40
    harness.PORT = 4408
    harness.BASE = "http://127.0.0.1:4408"
    harness.prior_reconciliation = prior_reconciliation
    code = harness.run()
    if OUT.exists():
        target = OUT / "FROZEN_RUN_CONFIG.json"
        target.write_bytes(FREEZE.read_bytes())
        target.chmod(0o444)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
