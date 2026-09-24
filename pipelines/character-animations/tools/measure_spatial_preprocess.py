"""Measure exact-pixel spatial preprocessing on the retained 30-master source."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import spatial_export

SOURCE_RUN = ROOT / "review/cadence-uninterrupted/phase2-fresh-uninterrupted"
JOB = SOURCE_RUN / "private-service-data/jobs/0ce217a9c0e74549a956ef1591a7c639"
CACHE = SOURCE_RUN / "cutout-cache"
REFERENCE_MANIFEST = JOB / "atlas-160-manifest.json"
RESULT = JOB / "spatial-export-result.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def decoded_rgba_equal(left: Path, right: Path) -> bool:
    with Image.open(left) as left_opened, Image.open(right) as right_opened:
        left_rgba = left_opened.convert("RGBA")
        right_rgba = right_opened.convert("RGBA")
    try:
        return left_rgba.size == right_rgba.size and left_rgba.tobytes() == right_rgba.tobytes()
    finally:
        left_rgba.close()
        right_rgba.close()


def ffprobe_frame_count(path: Path) -> int:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0", "-show_entries", "stream=nb_read_frames", "-of", "default=nw=1:nk=1", str(path)],
        check=True,
        capture_output=True,
        text=True,
        timeout=60,
    )
    return int(result.stdout.strip())


def write_native_grid(output: Path, canvas: int, frame_count: int, columns: int = 6) -> str:
    rows = (frame_count + columns - 1) // columns
    color = spatial_export.BG["petrol"]
    grid = Image.new("RGB", (columns * canvas, rows * canvas), color)
    try:
        for order in range(frame_count):
            with Image.open(output / f"export-{canvas}/frame-{order:04d}.png") as opened:
                sprite = opened.convert("RGBA")
            background = Image.new("RGBA", sprite.size, color + (255,))
            background.alpha_composite(sprite)
            grid.paste(background.convert("RGB"), ((order % columns) * canvas, (order // columns) * canvas))
            sprite.close()
            background.close()
        name = f"native-grid-{canvas}-petrol.png"
        grid.save(output / name)
        return name
    finally:
        grid.close()


def build_inputs() -> tuple[list[Path], dict[str, Any]]:
    manifest = json.loads(REFERENCE_MANIFEST.read_text(encoding="utf-8"))
    result = json.loads(RESULT.read_text(encoding="utf-8"))
    masters = [CACHE / frame["source_master"] for frame in manifest["frames"]]
    if len(masters) != 30 or not all(path.is_file() for path in masters):
        raise RuntimeError("retained phase-2 master set is incomplete")
    variants = result["geometry"]["variants"]
    config = {
        "job_id": "character",
        "action": manifest["clip"]["action"],
        "direction": manifest["clip"]["direction"],
        "native_fps": manifest["clip"]["fps"],
        "cycle_start": manifest["selection"]["cycle_start"],
        "cycle_end_exclusive": manifest["selection"]["cycle_end_exclusive"],
        "selected_indices": manifest["selection"]["indices"],
        "selection_mode": manifest["selection"]["mode"],
        "selection_receipt": manifest["selection"]["receipt"],
        "source": manifest["source"],
        "geometry": {"source_root": result["geometry"]["source_root"]},
        "variants": variants,
    }
    return masters, config


def run(label: str, output: Path, baseline: Path | None) -> dict[str, Any]:
    if output.exists():
        raise RuntimeError(f"output already exists: {output}")
    output.mkdir(parents=True)
    masters, config = build_inputs()
    master_hashes_before = [sha256(path) for path in masters]
    started = time.monotonic()
    variants = spatial_export.export_variants(masters, output, config)
    elapsed = time.monotonic() - started
    frame_count = len(config["selected_indices"])
    fps = frame_count / ((config["cycle_end_exclusive"] - config["cycle_start"]) / config["native_fps"])
    for variant in variants:
        variant["preview"] = spatial_export._encode_preview(output, variant["canvas"], fps, frame_count)
        variant["native_grid"] = write_native_grid(output, variant["canvas"], frame_count)
    verification = spatial_export._verify_all_frames(output, variants)
    master_hashes_after = [sha256(path) for path in masters]
    if master_hashes_after != master_hashes_before:
        raise RuntimeError("immutable source master changed")
    comparison = None
    if baseline is not None:
        frame_results = []
        for canvas in (160, 80):
            for order in range(frame_count):
                relative = Path(f"export-{canvas}/frame-{order:04d}.png")
                frame_results.append({"file": relative.as_posix(), "rgba_equal": decoded_rgba_equal(baseline / relative, output / relative)})
        atlas_results = [
            {"file": f"atlas-{canvas}.png", "rgba_equal": decoded_rgba_equal(baseline / f"atlas-{canvas}.png", output / f"atlas-{canvas}.png")}
            for canvas in (160, 80)
        ]
        comparison = {
            "normalized_frames": frame_results,
            "normalized_equal_count": sum(item["rgba_equal"] for item in frame_results),
            "normalized_total": len(frame_results),
            "atlases": atlas_results,
            "all_rgba_equal": all(item["rgba_equal"] for item in frame_results + atlas_results),
        }
        if not comparison["all_rgba_equal"]:
            raise RuntimeError("candidate output differs from frozen decoded RGBA baseline")
    summary = {
        "schema": "animation-spatial-preprocess-measurement-v1",
        "label": label,
        "source_run": SOURCE_RUN.relative_to(ROOT).as_posix(),
        "master_count": len(masters),
        "master_sha256": master_hashes_before,
        "config": config,
        "export_wall_seconds": round(elapsed, 6),
        "timings": [timing for variant in variants for timing in variant.pop("_timings")],
        "variants": variants,
        "verification": verification,
        "preview_decoded_frame_counts": {
            str(variant["canvas"]): ffprobe_frame_count(output / variant["preview"])
            for variant in variants
        },
        "expected_preview_frames": frame_count * 3,
        "comparison": comparison,
        "provider_calls": 0,
    }
    (output / "measurement.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("label", choices=("before", "after"))
    parser.add_argument("output", type=Path)
    parser.add_argument("--baseline", type=Path)
    args = parser.parse_args()
    if args.label == "after" and args.baseline is None:
        parser.error("after requires --baseline")
    print(json.dumps(run(args.label, args.output.resolve(), args.baseline.resolve() if args.baseline else None), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
