#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import animation_review
import pipeline
import spatial_export
from runner import sparse_cycle_sampling

BASE = ROOT / "review/minimax-480p-3s-punch-01"
SOURCE = BASE / "source-video.mp4"
CACHE = BASE / "cutout-cache"
OUT = ROOT / "review/action-timing-01"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    source = OUT / "source-original.mp4"
    if not source.exists():
        shutil.copyfile(SOURCE, source)
    analysis = animation_review.analyze_candidates(OUT, source.name, action="punch")
    write(OUT / "local-action-analysis.json", analysis)
    if analysis["status"] == "rejected" or len(analysis["candidates"]) != 1:
        raise RuntimeError(f"local action analysis failed closed: {analysis['hard_failures']}")
    candidate = analysis["candidates"][0]
    sampling = sparse_cycle_sampling(candidate, native_fps=analysis["source"]["native_fps"], frame_policy_name="8")
    extraction = OUT / "selected-originals"
    extraction.mkdir(exist_ok=True)
    target = extraction / source.name
    if not target.exists():
        shutil.copyfile(source, target)
    pipeline.run_stage("extract_frames", extraction, {
        "input": target.name, "fps": analysis["source"]["native_fps"],
        "indices": sampling["indices"], "output_prefix": "action",
    })
    originals = [extraction / f"action-frame-{order:04d}.png" for order in range(len(sampling["indices"]))]
    hits = [spatial_export.lookup_cached_cutout(item, CACHE, "waldlicht-removal-v1", "wavespeed-image-background-remover-output-v1") for item in originals]
    receipt = {
        "source": {"file": source.name, "sha256": sha(source)},
        "candidate": candidate,
        "sampling": sampling,
        "cache": {
            "hits": [sampling["indices"][i] for i, item in enumerate(hits) if item is not None],
            "missing": [sampling["indices"][i] for i, item in enumerate(hits) if item is None],
        },
        "paid_calls": 0,
    }
    write(OUT / "PREPARE.json", receipt)
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
