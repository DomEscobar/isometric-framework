#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import gait_selection

WORKDIR = ROOT / "artifacts" / "minimax-ne-source-01"


def main() -> int:
    paths = sorted((WORKDIR / "native-frames").glob("frame-*.png"))
    result = gait_selection.analyze_gait_frames(paths, native_fps=24.0, maximum_results=100)
    target = WORKDIR / "gait-candidate-search.json"
    target.write_text(json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({
        "intervals_examined": result["intervals_examined"],
        "accepted_candidate_count": result["accepted_candidate_count"],
        "top": result["accepted_candidates"][:10],
        "best_rejected": result["rejected_candidates"][:5],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
