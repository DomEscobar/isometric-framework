#!/usr/bin/env python3
"""Verify a reusable spatial replay against an accepted pixel baseline."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

from PIL import Image


def rgba_hash(path: Path) -> str:
    with Image.open(path) as opened:
        return hashlib.sha256(opened.convert("RGBA").tobytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run", type=Path)
    parser.add_argument("baseline", type=Path)
    args = parser.parse_args()
    run = args.run.resolve(strict=True)
    baseline = args.baseline.resolve(strict=True)
    comparisons = []
    for size in (160, 80):
        for order in range(24):
            left = run / f"export-{size}" / f"frame-{order:04d}.png"
            right = baseline / f"export-{size}" / f"frame-{order:04d}.png"
            comparisons.append({"kind": f"rgba-{size}", "order": order, "equal": rgba_hash(left) == rgba_hash(right)})
        comparisons.append({"kind": f"atlas-rgba-{size}", "equal": rgba_hash(run / f"atlas-{size}.png") == rgba_hash(baseline / f"atlas-{size}.png")})
    for order in range(24):
        left = run / "selected-originals" / f"original-frame-{order:04d}.png"
        right = baseline / "selected-originals" / f"original-frame-{order:04d}.png"
        comparisons.append({"kind": "source-rgba", "order": order, "equal": rgba_hash(left) == rgba_hash(right)})
    probes = {}
    for size in (160, 80):
        preview = run / f"preview-{size}-native-petrol-3loops.mp4"
        probe = subprocess.run([
            "ffprobe", "-v", "error", "-count_frames",
            "-show_entries", "stream=width,height,avg_frame_rate,nb_read_frames",
            "-show_entries", "format=duration", "-of", "json", str(preview),
        ], check=True, capture_output=True, text=True, timeout=30)
        probes[str(size)] = json.loads(probe.stdout)
    failed = [item for item in comparisons if not item["equal"]]
    result = {
        "status": "passed" if not failed else "failed",
        "pixel_comparisons": len(comparisons),
        "pixel_equal": len(comparisons) - len(failed),
        "failures": failed,
        "encoded_previews": probes,
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
