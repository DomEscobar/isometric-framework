#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import quality_gates

WORKDIR = ROOT / "artifacts" / "minimax-ne-source-01"
FRAMES = WORKDIR / "native-frames"
START = 42
END_EXCLUSIVE = 74
INDICES = list(range(START, END_EXCLUSIVE, 2))


def main() -> int:
    names = [f"frame-{index + 1:04d}.png" for index in INDICES]
    result = quality_gates.evaluate_motion_sequence(
        FRAMES,
        names,
        native_indices=INDICES,
        native_fps=24.0,
        cycle_end_exclusive=END_EXCLUSIVE,
        expected_facing="ne",
    )
    target = WORKDIR / "selected-42-74-motion-gate.json"
    target.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": result["status"],
        "rejection_reasons": result["rejection_reasons"],
        "gait_cycle": result["gait_cycle"],
        "orientation": result["source_pose_orientation"],
        "pose_velocity": result["pose_velocity"],
    }, indent=2))
    return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
