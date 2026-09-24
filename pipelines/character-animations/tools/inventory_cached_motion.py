#!/usr/bin/env python3
"""Inventory cached NE cutouts against exact native source frames."""
from __future__ import annotations

import hashlib
import json
import subprocess
import tempfile
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).parents[1]
WALDLICHT = Path("/root/games/waldlicht")
CACHE = WALDLICHT / "art/character-motion/ne-cutout-01"
SOURCE = WALDLICHT / "art/character-motion/ne-video-01/source-video.mp4"
LIVE_JOB = ROOT / "artifacts/live-e2e-20260920T223050Z-91b811/private-service-data/jobs/e0f2fc10ee3949ce89b31dd5d4444c86"
EXPECTED_SOURCE_SHA256 = "2ca54f300087f790fbc02f1e938ff979700a9e52077da07eff96c33fb6e4e18e"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def pixels(path: Path) -> bytes:
    with Image.open(path) as image:
        return image.convert("RGB").tobytes()


def main() -> int:
    if sha256(SOURCE) != EXPECTED_SOURCE_SHA256:
        raise RuntimeError("source video hash mismatch")
    source_chain = json.loads((CACHE / "source-chain.json").read_text())
    exact_extract = json.loads((LIVE_JOB / "extract-frames.json").read_text())
    with tempfile.TemporaryDirectory(prefix="cached-motion-native-") as temporary:
        native_dir = Path(temporary)
        subprocess.run(
            ["ffmpeg", "-v", "error", "-i", str(SOURCE), "-vsync", "0", str(native_dir / "frame-%04d.png")],
            check=True,
        )
        native_files = sorted(native_dir.glob("frame-*.png"))
        native_pixels = {index: pixels(path) for index, path in enumerate(native_files)}
        records = []
        for item in source_chain["directDecode"]["frames"]:
            selected = WALDLICHT / item["selectedCopy"]
            value = pixels(selected)
            matches = [index for index, candidate in native_pixels.items() if candidate == value]
            if len(matches) != 1:
                raise RuntimeError(f"old cache frame {item['order']} has {len(matches)} native pixel matches")
            native_index = matches[0]
            cutout = CACHE / "official-provider-export/frames" / f"frame-{item['order']:04d}.png"
            records.append({
                "cache": "waldlicht-ne-cutout-01",
                "cache_order": item["order"],
                "legacy_12fps_index": item["originalIndex"],
                "legacy_timestamp_seconds": item["timestampSeconds"],
                "native_source_index": native_index,
                "native_timestamp_seconds": native_index / 30.0,
                "source_frame_sha256": sha256(selected),
                "source_pixels_sha256": hashlib.sha256(value).hexdigest(),
                "cutout_file": str(cutout),
                "cutout_sha256": sha256(cutout),
            })
        for frame in exact_extract["frames"]:
            selected = LIVE_JOB / frame["file"]
            native_index = frame["source_index"]
            if pixels(selected) != native_pixels[native_index]:
                raise RuntimeError(f"service frame {frame['order']} does not pixel-match native {native_index}")
            cutout = LIVE_JOB / f"cutout-frame-{frame['order']:04d}.png"
            records.append({
                "cache": "service-live-e2e",
                "cache_order": frame["order"],
                "native_source_index": native_index,
                "native_timestamp_seconds": frame["timestamp_seconds"],
                "source_frame_sha256": sha256(selected),
                "source_pixels_sha256": hashlib.sha256(pixels(selected)).hexdigest(),
                "cutout_file": str(cutout),
                "cutout_sha256": sha256(cutout),
            })
    output = {
        "version": 1,
        "source": {"file": str(SOURCE), "sha256": EXPECTED_SOURCE_SHA256, "native_fps": 30.0},
        "mapping_method": "unique RGB pixel equality against ffmpeg exact native decode; legacy labels are 12 fps sample indices",
        "records": sorted(records, key=lambda item: (item["native_source_index"], item["cache"])),
    }
    target = ROOT / "artifacts/live-e2e-20260920T223050Z-91b811/export-motion-03/cache-inventory.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n")
    print(target)
    print("old native:", [item["native_source_index"] for item in records if item["cache"] == "waldlicht-ne-cutout-01"])
    print("service native:", [item["native_source_index"] for item in records if item["cache"] == "service-live-e2e"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
