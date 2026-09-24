#!/usr/bin/env python3
"""Render free, source-bound previews for the top diverse MiniMax gait candidates."""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from pathlib import Path
from statistics import median

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
WORKDIR = ROOT / "artifacts" / "minimax-ne-source-01"
FRAMES = WORKDIR / "native-frames"
OUT = WORKDIR / "gait-candidate-previews"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def ffmpeg_sequence(directory: Path, fps: float, target: Path) -> None:
    subprocess.run([
        "ffmpeg", "-v", "error", "-y", "-framerate", f"{fps:.12g}",
        "-i", str(directory / "frame-%04d.png"), "-an", "-c:v", "libx264",
        "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(target),
    ], check=True, timeout=180)


def choose_diverse(candidates: list[dict]) -> list[dict]:
    chosen: list[dict] = []
    for candidate in candidates:
        if not chosen or all(abs(candidate["start_native_index"] - item["start_native_index"]) >= 12 for item in chosen):
            chosen.append(candidate)
        if len(chosen) == 3:
            return chosen
    raise RuntimeError("fewer than three phase-diverse candidates passed local gates")


def shared_transform(indices: list[int], canvas: int) -> dict:
    sequence = json.loads((WORKDIR / "source-frame-sequence.json").read_text())
    records = [sequence["frames"][index]["foreground"] for index in indices]
    height = median(record["height"] for record in records)
    source_root_x = median(record["center_x"] for record in records)
    source_root_y = median(record["bottom"] for record in records)
    target_height = 58 * canvas / 80
    scale = target_height / height
    return {
        "scale": scale,
        "source_root": [source_root_x, source_root_y],
        "target_root": [canvas / 2, 72 * canvas / 80],
        "target_visible_height": target_height,
        "per_frame_recentered": False,
    }


def transformed_source(index: int, canvas: int, transform: dict) -> Image.Image:
    with Image.open(FRAMES / f"frame-{index + 1:04d}.png") as opened:
        source = opened.convert("RGB")
    size = (round(source.width * transform["scale"]), round(source.height * transform["scale"]))
    resized = source.resize(size, Image.Resampling.LANCZOS)
    background = source.getpixel((0, 0))
    output = Image.new("RGB", (canvas, canvas), background)
    x = round(transform["target_root"][0] - transform["source_root"][0] * transform["scale"])
    y = round(transform["target_root"][1] - transform["source_root"][1] * transform["scale"])
    output.paste(resized, (x, y))
    resized.close()
    source.close()
    return output


def render_candidate(candidate: dict, rank: int) -> dict:
    label = f"candidate-{rank:02d}-{candidate['start_native_index']}-{candidate['end_exclusive_native_index']}"
    target = OUT / label
    target.mkdir(parents=True)
    indices = list(range(candidate["start_native_index"], candidate["end_exclusive_native_index"]))
    repeated = indices * 3
    native_dir = target / "native-sequence"
    native_dir.mkdir()
    for order, index in enumerate(repeated):
        shutil.copyfile(FRAMES / f"frame-{index + 1:04d}.png", native_dir / f"frame-{order:04d}.png")
    native_video = target / "source-native-3loops.mp4"
    ffmpeg_sequence(native_dir, 24.0, native_video)
    shutil.rmtree(native_dir)

    previews = {}
    transforms = {}
    for canvas in (80, 160):
        transform = shared_transform(indices, canvas)
        transforms[str(canvas)] = transform
        directory = target / f"preview-{canvas}-sequence"
        directory.mkdir()
        for order, index in enumerate(repeated):
            frame = transformed_source(index, canvas, transform)
            frame.save(directory / f"frame-{order:04d}.png")
            frame.close()
        video = target / f"proposed-display-{canvas}-3loops.mp4"
        ffmpeg_sequence(directory, 24.0, video)
        shutil.rmtree(directory)
        previews[str(canvas)] = {"file": video.name, "sha256": sha256(video)}

    sheet = Image.new("RGB", (8 * 192, 4 * 220), (24, 29, 32))
    draw = ImageDraw.Draw(sheet)
    for order, index in enumerate(indices):
        with Image.open(FRAMES / f"frame-{index + 1:04d}.png") as opened:
            tile = opened.convert("RGB").resize((192, 192), Image.Resampling.LANCZOS)
        x, y = (order % 8) * 192, (order // 8) * 220
        sheet.paste(tile, (x, y))
        draw.text((x + 5, y + 196), f"n{index} {index/24:.3f}s", fill=(255, 220, 90))
        tile.close()
    sheet_path = target / "all-native-frames.png"
    sheet.save(sheet_path)
    sheet.close()

    seam_indices = [indices[-2], indices[-1], indices[0], indices[1], candidate["end_exclusive_native_index"]]
    seam = Image.new("RGB", (len(seam_indices) * 320, 356), (24, 29, 32))
    seam_draw = ImageDraw.Draw(seam)
    for order, index in enumerate(seam_indices):
        with Image.open(FRAMES / f"frame-{index + 1:04d}.png") as opened:
            tile = opened.convert("RGB").resize((320, 320), Image.Resampling.LANCZOS)
        seam.paste(tile, (order * 320, 0))
        role = ("last-1", "last", "FIRST/wrap", "first+1", "boundary recurrence")[order]
        seam_draw.text((order * 320 + 6, 326), f"{role}: n{index}", fill=(255, 220, 90))
        tile.close()
    seam_path = target / "encoded-seam-evidence.png"
    seam.save(seam_path)
    seam.close()
    record = {
        "id": label,
        "bounds": [indices[0], candidate["end_exclusive_native_index"]],
        "frame_count": len(indices),
        "duration_seconds": candidate["duration_seconds"],
        "metrics": candidate["metrics"],
        "local_rejection_reasons": [],
        "native_preview": {"file": native_video.name, "sha256": sha256(native_video)},
        "display_previews": previews,
        "shared_transforms": transforms,
        "contact_sheet": {"file": sheet_path.name, "sha256": sha256(sheet_path)},
        "seam_evidence": {"file": seam_path.name, "sha256": sha256(seam_path)},
        "source_background_retained": True,
        "cutout_claimed": False,
    }
    (target / "candidate.json").write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    return record


def main() -> int:
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir()
    search = json.loads((WORKDIR / "gait-candidate-search.json").read_text())
    if search["method"] != "native-silhouette-lower-body-phase-v1":
        raise RuntimeError("unexpected gait search method")
    selected = choose_diverse(search["accepted_candidates"])
    records = [render_candidate(candidate, rank) for rank, candidate in enumerate(selected, start=1)]
    manifest = {
        "version": 1,
        "source_file": "provider-original.mp4",
        "source_sha256": sha256(WORKDIR / "provider-original.mp4"),
        "source_probe": {"frame_count": 124, "native_fps": 24, "width": 768, "height": 768},
        "selection_method": search["method"],
        "intervals_examined": search["intervals_examined"],
        "candidates": records,
        "paid_calls": 0,
        "visual_quality_certified": False,
    }
    (OUT / "preview-manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
