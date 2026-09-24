#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))

import quality_gates
import animation_review

JOB = ROOT / "artifacts/live-e2e-20260920T223050Z-91b811/private-service-data/jobs/e0f2fc10ee3949ce89b31dd5d4444c86"
result = quality_gates.evaluate_motion_sequence(
    JOB,
    [f"selected-frame-{index:04d}.png" for index in range(10)],
    native_indices=[28, 33, 37, 42, 47, 52, 56, 61, 66, 70],
    native_fps=30.0,
    cycle_end_exclusive=75,
    expected_facing="ne",
)
analysis_dir = ROOT / "artifacts/live-e2e-20260920T223050Z-91b811/preflight-analysis"
analysis = animation_review.analyze_candidates(analysis_dir, "video-output.mp4")
output = ROOT / "artifacts/live-e2e-20260920T223050Z-91b811/export-motion-03"
output.mkdir(parents=True, exist_ok=True)
(output / "known-bad-10-motion-gate.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
(output / "source-candidate-analysis-v2.json").write_text(json.dumps(analysis, indent=2, sort_keys=True) + "\n")
print(json.dumps({
    "known_bad": result["rejection_reasons"],
    "analysis_status": analysis["status"],
    "hard_failures": analysis["hard_failures"],
    "candidate_count": len(analysis["candidates"]),
    "candidates": analysis["candidates"],
    "rejected_top": analysis["rejected_candidates"][:5],
}, indent=2))
